"""Persistent partner acquisition workspace. Public research and demo data stay separate."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from backend.candidates import load_catalog
from backend.db import now, session

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "partner_prospects.json"
PILOT_RESEARCH = load_catalog()
PILOT_BY_NAME = {item["name"].casefold(): item for item in PILOT_RESEARCH["candidates"]}
STAGES = ("Discovered", "Shortlisted", "Contacted", "Interested", "Negotiating", "Onboarded", "Rejected / Archived")
DEFAULT_WEIGHTS = {"residential": 35, "maintenance": 30, "coverage": 20, "installation": 15}


def with_pilot_research(company: dict) -> dict:
    """Add read-only pilot research without changing a staff-edited company record."""
    candidate = PILOT_BY_NAME.get(company["name"].casefold()) if company["origin"] == "Public research" else None
    if not candidate:
        return {**company, "pilot_research": None}
    return {
        **company,
        "pilot_research": {
            "rank": candidate["pilot_rank"],
            "tier": candidate["pilot_tier"],
            "idea": candidate["partnership_idea"],
            "rationale": candidate["ranking_rationale"],
            "evidence_score": candidate["evidence_score"],
            "evidence": candidate["evidence"],
            "retrieved_on": PILOT_RESEARCH["retrieved_on"],
        },
    }


class CompanyInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    website: HttpUrl
    residential_evidence: str = Field(min_length=3, max_length=500)
    maintenance: str = Field(min_length=2, max_length=300)
    installation: str = Field(pattern="^(yes|no|unverified)$")
    coverage: str = Field(min_length=2, max_length=300)
    contact: str = Field(min_length=2, max_length=200)
    source: HttpUrl
    retrieved_on: date
    unknowns: str = Field(default="", max_length=500)


class StageInput(BaseModel):
    stage: str
    note: str = Field(default="", max_length=1500)
    confirmed: bool = False
    follow_up: date | None = None


class DraftInput(BaseModel):
    purpose: str
    tone: str
    angle: str
    instructions: str = Field(default="", max_length=500)
    subject: str = Field(min_length=2, max_length=300)
    body: str = Field(min_length=10, max_length=5000)


class GenerateInput(BaseModel):
    purpose: str = Field(pattern="^(Initial proposal|Follow-up|Meeting request)$")
    tone: str = Field(pattern="^(Professional|Friendly|Concise)$")
    angle: str = Field(pattern="^(Potential referral commission|Customer value|Installation collaboration)$")
    instructions: str = Field(default="", max_length=500)


def initialize_workspace(path: Path):
    with session(path) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS prospect_companies (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, website TEXT NOT NULL,
          residential_evidence TEXT NOT NULL, maintenance TEXT NOT NULL,
          installation TEXT NOT NULL, coverage TEXT NOT NULL, contact TEXT NOT NULL,
          source TEXT NOT NULL, retrieved_on TEXT NOT NULL, unknowns TEXT NOT NULL,
          origin TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS prospect_pipeline (
          company_id TEXT PRIMARY KEY REFERENCES prospect_companies(id), stage TEXT NOT NULL,
          note TEXT NOT NULL DEFAULT '', follow_up TEXT, last_contacted TEXT, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS prospect_events (
          id INTEGER PRIMARY KEY, company_id TEXT NOT NULL REFERENCES prospect_companies(id),
          from_stage TEXT, to_stage TEXT NOT NULL, note TEXT NOT NULL, occurred_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS prospect_drafts (
          id INTEGER PRIMARY KEY, company_id TEXT NOT NULL REFERENCES prospect_companies(id),
          purpose TEXT NOT NULL, tone TEXT NOT NULL, angle TEXT NOT NULL,
          instructions TEXT NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS prospect_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        for item in json.loads(SEED.read_text()):
            slug = re.sub(r"[^a-z0-9]+", "-", item["name"].lower()).strip("-")
            db.execute("""INSERT OR IGNORE INTO prospect_companies VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (slug, item["name"], item["source"], item["residential_evidence"], item["maintenance"],
                 item["installation"], item["coverage"], item["contact"], item["source"],
                 "2026-10-11", item["unknowns"], "Public research", now(), now()))
            db.execute("INSERT OR IGNORE INTO prospect_pipeline(company_id,stage,updated_at) VALUES (?,'Discovered',?)", (slug, now()))
        # The newer sourced catalogue includes two prospects absent from the original PDF.
        # INSERT OR IGNORE preserves any existing staff edits and pipeline activity.
        seeded_names = {item["name"].casefold() for item in json.loads(SEED.read_text())}
        for candidate in PILOT_RESEARCH["candidates"]:
            if candidate["name"].casefold() in seeded_names:
                continue
            company_id = re.sub(r"[^a-z0-9]+", "-", candidate["name"].lower()).strip("-")
            contact = " · ".join(value for value in candidate["contact"].values() if value) or "Website contact page"
            db.execute("""INSERT OR IGNORE INTO prospect_companies VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (company_id, candidate["name"], candidate["website"], candidate["summary"],
                 candidate["maintenance_plan"], "yes" if candidate["signals"]["servicing_and_installation"] else "unverified",
                 candidate["coverage"], contact, candidate["evidence"][0]["url"],
                 PILOT_RESEARCH["retrieved_on"], "Partnership interest and suitability",
                 "Public research", now(), now()))
            db.execute("INSERT OR IGNORE INTO prospect_pipeline(company_id,stage,updated_at) VALUES (?,'Discovered',?)", (company_id, now()))
        db.execute("INSERT OR IGNORE INTO prospect_settings VALUES ('weights',?)", (json.dumps(DEFAULT_WEIGHTS),))


def make_router(path: Path) -> APIRouter:
    router = APIRouter(prefix="/api/workspace")

    def company_or_404(db, company_id):
        row = db.execute("SELECT * FROM prospect_companies WHERE id=?", (company_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Company not found")
        return dict(row)

    @router.get("")
    def list_workspace():
        with session(path) as db:
            companies = [with_pilot_research(dict(row)) for row in db.execute("""SELECT c.*,p.stage,p.note,p.follow_up,p.last_contacted,p.updated_at AS stage_updated_at,
              (SELECT COUNT(*) FROM prospect_drafts d WHERE d.company_id=c.id) AS draft_count
              FROM prospect_companies c JOIN prospect_pipeline p ON p.company_id=c.id ORDER BY c.name""")]
            weights = json.loads(db.execute("SELECT value FROM prospect_settings WHERE key='weights'").fetchone()[0])
        return {"companies": companies, "weights": weights, "stages": STAGES}

    @router.get("/companies/{company_id}")
    def get_company(company_id: str):
        with session(path) as db:
            company = company_or_404(db, company_id)
            pipeline = dict(db.execute("SELECT * FROM prospect_pipeline WHERE company_id=?", (company_id,)).fetchone())
            events = [dict(row) for row in db.execute("SELECT * FROM prospect_events WHERE company_id=? ORDER BY id DESC", (company_id,))]
            drafts = [dict(row) for row in db.execute("SELECT * FROM prospect_drafts WHERE company_id=? ORDER BY id DESC", (company_id,))]
            referral = db.execute("SELECT referral_code FROM partners WHERE company_id=? AND id LIKE 'scenario-%' LIMIT 1", (company_id,)).fetchone()
        return {**with_pilot_research(company), **pipeline, "events": events, "drafts": drafts,
                "demo_referral_code": referral["referral_code"] if referral else None}

    @router.post("/companies/{company_id}/demo-referral")
    def create_demo_referral(company_id: str):
        with session(path) as db:
            company = company_or_404(db, company_id)
            existing = db.execute("SELECT id,referral_code FROM partners WHERE company_id=? AND id LIKE 'scenario-%' LIMIT 1", (company_id,)).fetchone()
            if existing:
                return {"partner_id": existing["id"], "referral_code": existing["referral_code"], "company_id": company_id, "scenario_only": True}
            partner_id = "scenario-" + uuid4().hex[:12]
            referral_code = "demo-" + uuid4().hex[:16]
            db.execute("""INSERT INTO partners(id,name,description,customer_focus,service_areas,services,engagement_fit,referral_code,source_notes,active,company_id)
                VALUES (?,?,?,?,?,?,?,?,?,1,?)""",
                (partner_id, company["name"] + " demo scenario", "Simulated referral source; no partnership is implied",
                 "mixed", "[]", "[]", 0, referral_code, "Created for an internal referral walkthrough only", company_id))
        return {"partner_id": partner_id, "referral_code": referral_code, "company_id": company_id, "scenario_only": True}

    @router.post("/companies", status_code=201)
    def add_company(payload: CompanyInput):
        item = payload.model_dump(mode="json")
        company_id = "manual-" + uuid4().hex[:12]
        with session(path) as db:
            db.execute("INSERT INTO prospect_companies VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (company_id, item["name"].strip(), item["website"], item["residential_evidence"], item["maintenance"],
                 item["installation"], item["coverage"], item["contact"], item["source"], item["retrieved_on"],
                 item["unknowns"], "User-entered", now(), now()))
            db.execute("INSERT INTO prospect_pipeline(company_id,stage,updated_at) VALUES (?,'Discovered',?)", (company_id, now()))
        return {"id": company_id}

    @router.put("/companies/{company_id}")
    def edit_company(company_id: str, payload: CompanyInput):
        item = payload.model_dump(mode="json")
        with session(path) as db:
            company_or_404(db, company_id)
            db.execute("""UPDATE prospect_companies SET name=?,website=?,residential_evidence=?,maintenance=?,installation=?,
              coverage=?,contact=?,source=?,retrieved_on=?,unknowns=?,updated_at=? WHERE id=?""",
              (item["name"].strip(), item["website"], item["residential_evidence"], item["maintenance"],
               item["installation"], item["coverage"], item["contact"], item["source"], item["retrieved_on"],
               item["unknowns"], now(), company_id))
        return {"id": company_id}

    @router.put("/weights")
    def save_weights(weights: dict[str, int]):
        if set(weights) != set(DEFAULT_WEIGHTS) or any(not isinstance(v, int) or v < 0 or v > 100 for v in weights.values()) or sum(weights.values()) != 100:
            raise HTTPException(422, "Weights must be non-negative whole numbers that add to 100")
        with session(path) as db:
            db.execute("UPDATE prospect_settings SET value=? WHERE key='weights'", (json.dumps(weights),))
        return weights

    @router.post("/companies/{company_id}/stage")
    def change_stage(company_id: str, payload: StageInput):
        if payload.stage not in STAGES:
            raise HTTPException(422, "Unknown stage")
        with session(path) as db:
            company_or_404(db, company_id)
            previous = db.execute("SELECT stage FROM prospect_pipeline WHERE company_id=?", (company_id,)).fetchone()[0]
            if payload.stage != previous and payload.stage in ("Contacted", "Onboarded") and not payload.confirmed:
                raise HTTPException(422, "Confirm actual outreach or agreement before selecting this stage")
            db.execute("""UPDATE prospect_pipeline SET stage=?,note=?,follow_up=?,last_contacted=CASE WHEN ?='Contacted' THEN ? ELSE last_contacted END,updated_at=? WHERE company_id=?""",
                (payload.stage, payload.note, str(payload.follow_up) if payload.follow_up else None, payload.stage, now(), now(), company_id))
            if previous != payload.stage:
                db.execute("INSERT INTO prospect_events(company_id,from_stage,to_stage,note,occurred_at) VALUES (?,?,?,?,?)",
                    (company_id, previous, payload.stage, payload.note, now()))
        return {"stage": payload.stage}

    @router.post("/companies/{company_id}/generate")
    def generate(company_id: str, payload: GenerateInput):
        with session(path) as db:
            company = company_or_404(db, company_id)
        facts = [company["residential_evidence"]]
        if company["maintenance"].lower() != "unverified":
            facts.append(company["maintenance"])
        if company["installation"] == "yes" and payload.angle == "Installation collaboration":
            facts.append("installation offered")
        detail = facts[0].rstrip(".").lower()
        repeat = f" Your published {company['maintenance'].lower()} offering suggests a useful point of contact with homeowners over time." if len(facts) > 1 and company["maintenance"].lower() != "unverified" else ""
        angle = {
            "Potential referral commission": "If there is mutual interest, a referral arrangement could include a commission, subject to discussion and agreement.",
            "Customer value": "A referral arrangement could give interested homeowners another option to explore alongside your existing services.",
            "Installation collaboration": "We could also discuss whether installation collaboration is feasible, subject to technical approval.",
        }[payload.angle]
        opening = {"Initial proposal": "I am reaching out from Bizsu to explore a potential referral partnership.",
                   "Follow-up": "I am following up on a possible referral partnership with Bizsu.",
                   "Meeting request": "Would your team be open to a short meeting about a possible referral partnership with Bizsu?"}[payload.purpose]
        close = "Would a short conversation next week be convenient?" if payload.purpose != "Meeting request" else "Please let me know if a short call would be useful."
        if payload.tone == "Friendly":
            opening = "Hello from Bizsu! " + opening
            close = "Happy to find a time that works for you."
        if payload.tone == "Concise":
            repeat = ""
            close = "Would you be open to a brief call?"
        subject = f"{payload.purpose}: potential Bizsu referral partnership with {company['name']}"
        body = f"Hello {company['name']} team,\n\n{opening} Your website describes {detail}.{repeat} {angle}\n\n{close}\n\nBest,\nBizsu team"
        return {"subject": subject, "body": body, "facts_used": facts, "source": company["source"], "generation_method": "Template-generated", "sent": False}

    @router.post("/companies/{company_id}/drafts", status_code=201)
    def save_draft(company_id: str, payload: DraftInput):
        with session(path) as db:
            company_or_404(db, company_id)
            cursor = db.execute("""INSERT INTO prospect_drafts(company_id,purpose,tone,angle,instructions,subject,body,updated_at)
              VALUES (?,?,?,?,?,?,?,?)""", (company_id, payload.purpose, payload.tone, payload.angle,
              payload.instructions, payload.subject, payload.body, now()))
        return {"id": cursor.lastrowid, "sent": False}

    return router
