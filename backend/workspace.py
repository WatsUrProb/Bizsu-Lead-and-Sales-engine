"""Persistent partner acquisition workspace. Public research and demo data stay separate."""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, HttpUrl, field_validator

from backend.candidates import load_catalog
from backend.contact_discovery import EMAIL_RE, contact_type, discover_public_emails, valid_email
from backend.db import now, session
from backend.outreach_ai import (PROMPT_VERSION, REPLY_TO, SENDER_NAME, analyse_company,
                                 company_snapshot, generate_outreach, profile_version)

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
    to_email: str | None = None
    recipient_name: str = Field(default="", max_length=100)
    reply_to: str = REPLY_TO
    sender_name: str = Field(default=SENDER_NAME, min_length=2, max_length=80)
    generation_method: str = "manual"
    facts_used: list[dict] = Field(default_factory=list)
    profile_version: str | None = None
    prompt_version: str | None = None
    style: str = "Short and direct"
    contact_provenance: str = "unknown"

    @field_validator("to_email")
    @classmethod
    def check_to_address(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if not valid_email(value):
            raise ValueError("Enter a valid email address")
        return value.strip().lower()

    @field_validator("reply_to")
    @classmethod
    def check_reply_address(cls, value: str) -> str:
        if not valid_email(value):
            raise ValueError("Enter a valid reply-to address")
        return value.strip().lower()


class SelectContactInput(BaseModel):
    contact_id: int | None = None
    email_address: str | None = None
    recipient_name: str = Field(default="", max_length=100)


class OutreachSettingsInput(BaseModel):
    reply_to: str = REPLY_TO
    sender_name: str = Field(default=SENDER_NAME, min_length=2, max_length=80)
    approved_product_claims: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("reply_to")
    @classmethod
    def check_reply_to(cls, value: str) -> str:
        if not valid_email(value):
            raise ValueError("Enter a valid reply-to address")
        return value.strip().lower()


class GenerateInput(BaseModel):
    purpose: str = Field(pattern="^(Initial proposal|Follow-up|Meeting request)$")
    tone: str = Field(pattern="^(Professional|Friendly|Concise)$")
    angle: str = Field(pattern="^(AI recommended|Potential referral commission|Customer value|Installation collaboration)$")
    instructions: str = Field(default="", max_length=500)
    style: str = Field(default="Short and direct", pattern="^(Short and direct|Slightly detailed)$")
    to_email: str | None = None
    recipient_name: str = Field(default="", max_length=100)
    sender_name: str | None = Field(default=None, min_length=2, max_length=80)
    reply_to: str | None = None

    @field_validator("to_email", "reply_to")
    @classmethod
    def check_address(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if not valid_email(value):
            raise ValueError("Enter a valid email address")
        return value.strip().lower()


def ingest_recorded_email(db, company: dict) -> None:
    """Import literal addresses in stored contact text without inferring any address."""
    for address in EMAIL_RE.findall(company["contact"]):
        address = address.lower()
        if not valid_email(address):
            continue
        if db.execute("SELECT 1 FROM prospect_contact_emails WHERE company_id=? AND email_address=?",
                      (company["id"], address)).fetchone():
            continue
        selected = db.execute("SELECT 1 FROM prospect_contact_emails WHERE company_id=? AND selected=1",
                              (company["id"],)).fetchone()
        is_research = company["origin"] == "Public research"
        db.execute("""INSERT INTO prospect_contact_emails
            (company_id,email_address,source_url,retrieved_at,contact_type,verification_status,evidence_snippet,selected)
            VALUES (?,?,?,?,?,?,?,?)""",
            (company["id"], address, company["source"] if is_research else "",
             company["retrieved_on"] if is_research else now(), contact_type(address),
             "unverified" if is_research else "staff-provided",
             "Recorded in company contact field; confirm before sending", int(not selected)))


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
          updated_at TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS prospect_contact_emails (
          id INTEGER PRIMARY KEY, company_id TEXT NOT NULL REFERENCES prospect_companies(id),
          email_address TEXT NOT NULL, source_url TEXT NOT NULL DEFAULT '', retrieved_at TEXT NOT NULL,
          contact_type TEXT NOT NULL, verification_status TEXT NOT NULL,
          evidence_snippet TEXT NOT NULL DEFAULT '', recipient_name TEXT NOT NULL DEFAULT '',
          selected INTEGER NOT NULL DEFAULT 0,
          UNIQUE(company_id,email_address,source_url)
        );
        CREATE TABLE IF NOT EXISTS prospect_contact_checks (
          company_id TEXT PRIMARY KEY REFERENCES prospect_companies(id), checked_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS prospect_analyses (
          company_id TEXT PRIMARY KEY REFERENCES prospect_companies(id),
          profile_version TEXT NOT NULL, prompt_version TEXT NOT NULL,
          result_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS prospect_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        if "metadata_json" not in {row["name"] for row in db.execute("PRAGMA table_info(prospect_drafts)")}:
            db.execute("ALTER TABLE prospect_drafts ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'")
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
        db.execute("INSERT OR IGNORE INTO prospect_settings VALUES ('outreach',?)", (json.dumps({
            "reply_to": REPLY_TO, "sender_name": SENDER_NAME, "approved_product_claims": []}),))
        # A recorded email in the research snapshot is useful, but remains unverified
        # until the public source itself is checked by the discovery action.
        for candidate in PILOT_RESEARCH["candidates"]:
            address = (candidate.get("contact") or {}).get("email")
            if not address or not valid_email(address):
                continue
            company_id = re.sub(r"[^a-z0-9]+", "-", candidate["name"].lower()).strip("-")
            if not db.execute("SELECT id FROM prospect_companies WHERE id=?", (company_id,)).fetchone():
                continue
            db.execute("""INSERT OR IGNORE INTO prospect_contact_emails
                (company_id,email_address,source_url,retrieved_at,contact_type,verification_status,evidence_snippet,selected)
                VALUES (?,?,?,?,?,?,?,?)""",
                (company_id, address.lower(), candidate["website"], PILOT_RESEARCH["retrieved_on"],
                 contact_type(address), "unverified", "Recorded in public research snapshot; confirm on company site", 1))
        for company in db.execute("SELECT id,contact,source,retrieved_on,origin FROM prospect_companies"):
            ingest_recorded_email(db, dict(company))


def make_router(path: Path) -> APIRouter:
    router = APIRouter(prefix="/api/workspace")

    def company_or_404(db, company_id):
        row = db.execute("SELECT * FROM prospect_companies WHERE id=?", (company_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Company not found")
        return dict(row)

    def contacts_for(db, company_id):
        rows = [dict(row) for row in db.execute("""SELECT * FROM prospect_contact_emails
            WHERE company_id=? ORDER BY selected DESC,
            CASE verification_status WHEN 'source-confirmed' THEN 0 WHEN 'staff-provided' THEN 1 ELSE 2 END,
            CASE contact_type WHEN 'general' THEN 0 WHEN 'sales' THEN 1 ELSE 2 END,email_address""", (company_id,))]
        return rows

    def settings_for(db):
        row = db.execute("SELECT value FROM prospect_settings WHERE key='outreach'").fetchone()
        return json.loads(row["value"]) if row else {"reply_to": REPLY_TO, "sender_name": SENDER_NAME,
                                                    "approved_product_claims": []}

    @router.get("/outreach-settings")
    def get_outreach_settings():
        with session(path) as db:
            return settings_for(db)

    @router.put("/outreach-settings")
    def save_outreach_settings(payload: OutreachSettingsInput):
        value = payload.model_dump()
        if any(len(claim) > 240 for claim in value["approved_product_claims"]):
            raise HTTPException(422, "Approved claims must be 240 characters or fewer")
        with session(path) as db:
            db.execute("INSERT INTO prospect_settings(key,value) VALUES ('outreach',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (json.dumps(value),))
        return value

    @router.get("")
    def list_workspace():
        with session(path) as db:
            companies = [with_pilot_research(dict(row)) for row in db.execute("""SELECT c.*,p.stage,p.note,p.follow_up,p.last_contacted,p.updated_at AS stage_updated_at,
              (SELECT COUNT(*) FROM prospect_drafts d WHERE d.company_id=c.id) AS draft_count,
              (SELECT r.referral_code FROM partners r WHERE r.company_id=c.id AND r.id LIKE 'scenario-%' AND r.active=1 LIMIT 1) AS demo_referral_code,
              (SELECT COUNT(*) FROM leads l JOIN partners r ON r.id=l.partner_id
               WHERE r.company_id=c.id AND r.id LIKE 'scenario-%' AND l.data_kind='synthetic submitted enquiry') AS referral_enquiry_count
              FROM prospect_companies c JOIN prospect_pipeline p ON p.company_id=c.id ORDER BY c.name""")]
            weights = json.loads(db.execute("SELECT value FROM prospect_settings WHERE key='weights'").fetchone()[0])
        return {"companies": companies, "weights": weights, "stages": STAGES}

    @router.get("/companies/{company_id}")
    def get_company(company_id: str):
        with session(path) as db:
            company = company_or_404(db, company_id)
            pipeline = dict(db.execute("SELECT * FROM prospect_pipeline WHERE company_id=?", (company_id,)).fetchone())
            events = [dict(row) for row in db.execute("SELECT * FROM prospect_events WHERE company_id=? ORDER BY id DESC", (company_id,))]
            drafts = [{**dict(row), "metadata": json.loads(row["metadata_json"])} for row in db.execute(
                "SELECT * FROM prospect_drafts WHERE company_id=? ORDER BY id DESC", (company_id,))]
            contacts = contacts_for(db, company_id)
            referral = db.execute("SELECT referral_code FROM partners WHERE company_id=? AND id LIKE 'scenario-%' AND active=1 LIMIT 1", (company_id,)).fetchone()
            referral_count = db.execute("""SELECT COUNT(*) FROM leads l JOIN partners r ON r.id=l.partner_id
                WHERE r.company_id=? AND r.id LIKE 'scenario-%' AND l.data_kind='synthetic submitted enquiry'""", (company_id,)).fetchone()[0]
        return {**with_pilot_research(company), **pipeline, "events": events, "drafts": drafts,
                "demo_referral_code": referral["referral_code"] if referral else None,
                "referral_enquiry_count": referral_count, "contact_emails": contacts,
                "selected_contact": next((item for item in contacts if item["selected"]), None)}

    @router.post("/companies/{company_id}/discover-contact")
    def discover_contact(company_id: str):
        with session(path) as db:
            company = company_or_404(db, company_id)
            prior = db.execute("SELECT checked_at FROM prospect_contact_checks WHERE company_id=?", (company_id,)).fetchone()
            if prior and datetime.fromisoformat(prior["checked_at"]) > datetime.now(timezone.utc) - timedelta(minutes=10):
                return {"candidates": contacts_for(db, company_id), "checked_at": prior["checked_at"],
                        "rate_limited": True}
        found = discover_public_emails(company["website"], company["source"])
        checked_at = now()
        with session(path) as db:
            for item in found:
                existing = db.execute("""SELECT id,selected FROM prospect_contact_emails
                    WHERE company_id=? AND email_address=? AND source_url=?""",
                    (company_id, item["email_address"], item["source_url"])).fetchone()
                if existing:
                    db.execute("""UPDATE prospect_contact_emails SET retrieved_at=?,contact_type=?,
                        verification_status='source-confirmed',evidence_snippet=? WHERE id=?""",
                        (checked_at, item["contact_type"], item["evidence_snippet"], existing["id"]))
                else:
                    has_selected = db.execute("SELECT 1 FROM prospect_contact_emails WHERE company_id=? AND selected=1", (company_id,)).fetchone()
                    db.execute("""INSERT INTO prospect_contact_emails
                        (company_id,email_address,source_url,retrieved_at,contact_type,verification_status,evidence_snippet,selected)
                        VALUES (?,?,?,?,?,?,?,?)""",
                        (company_id, item["email_address"], item["source_url"], checked_at,
                         item["contact_type"], item["verification_status"], item["evidence_snippet"],
                         int(not has_selected)))
            preferred = db.execute("""SELECT id FROM prospect_contact_emails WHERE company_id=?
                AND verification_status='source-confirmed'
                ORDER BY CASE contact_type WHEN 'general' THEN 0 WHEN 'sales' THEN 1 ELSE 2 END,id LIMIT 1""",
                (company_id,)).fetchone()
            selected = db.execute("SELECT verification_status FROM prospect_contact_emails WHERE company_id=? AND selected=1",
                                  (company_id,)).fetchone()
            if preferred and (not selected or selected["verification_status"] == "unverified"):
                db.execute("UPDATE prospect_contact_emails SET selected=0 WHERE company_id=?", (company_id,))
                db.execute("UPDATE prospect_contact_emails SET selected=1 WHERE id=?", (preferred["id"],))
            db.execute("""INSERT INTO prospect_contact_checks(company_id,checked_at) VALUES (?,?)
                ON CONFLICT(company_id) DO UPDATE SET checked_at=excluded.checked_at""", (company_id, checked_at))
            contacts = contacts_for(db, company_id)
        return {"candidates": contacts, "checked_at": checked_at, "rate_limited": False}

    @router.post("/companies/{company_id}/select-contact")
    def select_contact(company_id: str, payload: SelectContactInput):
        with session(path) as db:
            company_or_404(db, company_id)
            if payload.contact_id is not None:
                row = db.execute("SELECT * FROM prospect_contact_emails WHERE id=? AND company_id=?",
                                 (payload.contact_id, company_id)).fetchone()
                if not row:
                    raise HTTPException(404, "Contact address not found")
                selected_id = row["id"]
            elif payload.email_address and valid_email(payload.email_address):
                address = payload.email_address.strip().lower()
                db.execute("""INSERT OR IGNORE INTO prospect_contact_emails
                    (company_id,email_address,source_url,retrieved_at,contact_type,verification_status,evidence_snippet,recipient_name)
                    VALUES (?,?,'',?,?, 'staff-provided','Entered by staff',?)""",
                    (company_id, address, now(), contact_type(address), payload.recipient_name.strip()))
                selected_id = db.execute("""SELECT id FROM prospect_contact_emails
                    WHERE company_id=? AND email_address=? AND source_url=''""", (company_id, address)).fetchone()[0]
            else:
                raise HTTPException(422, "Choose a public address or enter a valid email")
            db.execute("UPDATE prospect_contact_emails SET selected=0 WHERE company_id=?", (company_id,))
            db.execute("UPDATE prospect_contact_emails SET selected=1,recipient_name=? WHERE id=?",
                       (payload.recipient_name.strip(), selected_id))
            return {"candidates": contacts_for(db, company_id), "selected_contact_id": selected_id}

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
            ingest_recorded_email(db, {"id": company_id, "contact": item["contact"],
                                       "source": str(item["source"]), "retrieved_on": str(item["retrieved_on"]),
                                       "origin": "User-entered"})
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
            company = company_or_404(db, company_id)
            ingest_recorded_email(db, company)
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
            settings = settings_for(db)
            selected = next((item for item in contacts_for(db, company_id) if item["selected"]), None)
        controls = payload.model_dump(exclude={"to_email", "recipient_name", "sender_name", "reply_to"})
        address = payload.to_email or (selected["email_address"] if selected else None)
        recipient_name = payload.recipient_name or (selected["recipient_name"] if selected else "")
        result = generate_outreach(company_snapshot(company), controls, to_email=address,
                                   recipient_name=recipient_name,
                                   sender_name=payload.sender_name or settings["sender_name"],
                                   reply_to=payload.reply_to or settings["reply_to"],
                                   approved_claims=settings.get("approved_product_claims", []))
        result["contact_provenance"] = (selected["verification_status"] if selected and address == selected["email_address"]
                                         else "staff-provided" if address else "unknown")
        result["source"] = company["source"]
        return result

    @router.post("/companies/{company_id}/analyse")
    def analyse(company_id: str):
        with session(path) as db:
            company = company_or_404(db, company_id)
            snapshot = company_snapshot(company)
            version = profile_version(snapshot)
            cached = db.execute("SELECT * FROM prospect_analyses WHERE company_id=?", (company_id,)).fetchone()
            if cached and cached["profile_version"] == version and cached["prompt_version"] == PROMPT_VERSION:
                result = json.loads(cached["result_json"])
                # A template saved before credentials were configured must not
                # prevent a later staff-triggered AI analysis.
                if result.get("generation_method") == "llm" or not os.environ.get("OPENAI_API_KEY") or not snapshot["facts"]:
                    return result
        result = analyse_company(snapshot)
        with session(path) as db:
            db.execute("""INSERT INTO prospect_analyses(company_id,profile_version,prompt_version,result_json,created_at)
                VALUES (?,?,?,?,?) ON CONFLICT(company_id) DO UPDATE SET
                profile_version=excluded.profile_version,prompt_version=excluded.prompt_version,
                result_json=excluded.result_json,created_at=excluded.created_at""",
                (company_id, version, PROMPT_VERSION, json.dumps(result), now()))
        return result

    @router.post("/companies/{company_id}/drafts", status_code=201)
    def save_draft(company_id: str, payload: DraftInput):
        with session(path) as db:
            company_or_404(db, company_id)
            metadata = payload.model_dump(exclude={"purpose", "tone", "angle", "instructions", "subject", "body"})
            cursor = db.execute("""INSERT INTO prospect_drafts(company_id,purpose,tone,angle,instructions,subject,body,updated_at,metadata_json)
              VALUES (?,?,?,?,?,?,?,?,?)""", (company_id, payload.purpose, payload.tone, payload.angle,
              payload.instructions, payload.subject, payload.body, now(), json.dumps(metadata)))
        return {"id": cursor.lastrowid, "sent": False}

    @router.patch("/companies/{company_id}/drafts/{draft_id}")
    def edit_draft(company_id: str, draft_id: int, payload: DraftInput):
        with session(path) as db:
            company_or_404(db, company_id)
            if not db.execute("SELECT id FROM prospect_drafts WHERE id=? AND company_id=?", (draft_id, company_id)).fetchone():
                raise HTTPException(404, "Draft not found")
            metadata = payload.model_dump(exclude={"purpose", "tone", "angle", "instructions", "subject", "body"})
            db.execute("""UPDATE prospect_drafts SET purpose=?,tone=?,angle=?,instructions=?,subject=?,body=?,
                updated_at=?,metadata_json=? WHERE id=? AND company_id=?""",
                (payload.purpose, payload.tone, payload.angle, payload.instructions, payload.subject,
                 payload.body, now(), json.dumps(metadata), draft_id, company_id))
        return {"id": draft_id, "sent": False}

    return router
