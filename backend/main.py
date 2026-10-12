"""Local-only FastAPI service for the Bizsu synthetic hackathon demo."""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator

from backend.candidates import WEIGHTS, load_catalog, outreach_template
from backend.db import DEFAULT_DB, ROOT, initialize, lead_from_row, now, partner_from_row, session
from backend.domain import NEXT_STAGE, STAGES, draft_message, qualify, stage_allowed
from backend.scoring import ConversionScorer

DATA = ROOT / "data"


class LeadInput(BaseModel):
    referral_code: str | None = None
    area: str
    property_type: Literal["HDB 1–2 room", "HDB 3 room", "HDB 4 room", "HDB 5 room/executive", "Condo/apartment", "Landed"]
    ac_type: Literal["split", "multi_split", "window", "central"]
    ac_units: int = Field(ge=1, le=12)
    daily_hours: float = Field(gt=0, le=24)
    estimated_ac_spend: float | None = Field(default=None, ge=0, le=10000)
    contact_name: str = Field(min_length=2, max_length=80)
    contact_email: str = Field(min_length=5, max_length=160)
    consent: bool

    @field_validator("contact_name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Enter a demo name with at least two characters")
        return value

    @field_validator("contact_email")
    @classmethod
    def synthetic_email_only(cls, value: str) -> str:
        value = value.strip().lower()
        if not value.endswith(".test") or "@" not in value:
            raise ValueError("Use a synthetic .test email address in this demo")
        return value

    @field_validator("consent")
    @classmethod
    def consent_required(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Consent is required to submit the demo enquiry")
        return value


class StageInput(BaseModel):
    stage: str


class ReferralVisitInput(BaseModel):
    referral_code: str
    session_id: str = Field(min_length=8, max_length=100)


class DraftInput(BaseModel):
    message: str = Field(min_length=5, max_length=3000)


class CandidateActionInput(BaseModel):
    shortlisted: bool
    outreach_draft: str = Field(max_length=3000)


def create_app(db_path: Path | None = None, seed: bool = True, scorer: ConversionScorer | None = None) -> FastAPI:
    path = Path(db_path or os.environ.get("BIZSU_DB_PATH", DEFAULT_DB))
    area_data = json.loads((DATA / "processed" / "areas.json").read_text())
    cluster_data = json.loads((DATA / "processed" / "clusters.json").read_text())
    sources = json.loads((DATA / "sources.json").read_text())
    catalog = load_catalog()
    candidates_by_id = {item["id"]: item for item in catalog["candidates"]}
    scorer = scorer or ConversionScorer()
    areas = [
        {**area, **cluster_data["assignments"].get(area["name"], {"cluster_id": None, "cluster_label": None})}
        for area in area_data["areas"]
    ]
    known_areas = {area["name"] for area in areas if area["name"] != "Others"}
    area_lookup = {area["name"]: area for area in areas}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        initialize(path, seed=seed, scorer=scorer)
        yield

    app = FastAPI(title="Bizsu Hackathon Demo API", version="0.1.0", lifespan=lifespan)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": "local synthetic demo"}

    @app.get("/api/meta")
    def meta():
        return {
            "sources": sources,
            "clusters": {key: value for key, value in cluster_data.items() if key != "assignments"},
            "model": scorer.metadata(),
            "stages": STAGES,
            "demo_note": "Planning-area figures and sourced company profiles are real public information; referral partners, enquiries and outcomes are synthetic.",
            "ema_note": "The available area electricity context is historical 2013 whole-home consumption. EMA's current source page was reviewed, but the workbook could not be inspected through automated retrieval, so it was not integrated.",
        }

    @app.get("/api/areas")
    def list_areas(cluster_id: int | None = None, min_households: int = Query(default=0, ge=0), min_large_hdb_share: float = Query(default=0, ge=0, le=1)):
        result = [area for area in areas if area["name"] != "Others" and area["households"] >= min_households]
        if cluster_id is not None:
            result = [area for area in result if area["cluster_id"] == cluster_id]
        if min_large_hdb_share:
            result = [area for area in result if (area["features"]["large_hdb_share"] or 0) >= min_large_hdb_share]
        return {"areas": result, "count": len(result), "filters_are_descriptive": True}

    @app.get("/api/partners")
    def list_partners():
        with session(path) as db:
            partners = [partner_from_row(row) for row in db.execute("SELECT * FROM partners WHERE active=1")]
        return sorted(partners, key=lambda partner: partner["ranking"]["score"], reverse=True)

    @app.get("/api/candidates")
    def list_candidates():
        with session(path) as db:
            actions = {row["candidate_id"]: dict(row) for row in db.execute("SELECT * FROM candidate_actions")}
        candidates = []
        for candidate in catalog["candidates"]:
            action = actions.get(candidate["id"], {})
            candidates.append({
                **candidate,
                "shortlisted": bool(action.get("shortlisted", 0)),
                "outreach_draft": action["outreach_draft"] if action else outreach_template(candidate),
            })
        return {
            "candidates": sorted(candidates, key=lambda item: (-item["evidence_score"], item["name"])),
            "weights": WEIGHTS,
            "retrieved_on": catalog["retrieved_on"],
            "note": catalog["note"],
        }

    @app.patch("/api/candidates/{candidate_id}")
    def update_candidate(candidate_id: str, payload: CandidateActionInput):
        if candidate_id not in candidates_by_id:
            raise HTTPException(404, "Candidate not found")
        with session(path) as db:
            db.execute(
                """INSERT INTO candidate_actions (candidate_id,shortlisted,outreach_draft,updated_at)
                   VALUES (?,?,?,?) ON CONFLICT(candidate_id) DO UPDATE SET
                   shortlisted=excluded.shortlisted,outreach_draft=excluded.outreach_draft,
                   updated_at=excluded.updated_at""",
                (candidate_id, int(payload.shortlisted), payload.outreach_draft, now()),
            )
        return {"candidate_id": candidate_id, **payload.model_dump(), "sent": False}

    @app.post("/api/referral-visits")
    def record_visit(payload: ReferralVisitInput):
        with session(path) as db:
            partner = db.execute("SELECT id FROM partners WHERE referral_code=? AND active=1", (payload.referral_code,)).fetchone()
            if not partner:
                raise HTTPException(404, "Referral code not found")
            db.execute("INSERT OR IGNORE INTO referral_events (partner_id,session_id,created_at) VALUES (?,?,?)", (partner["id"], payload.session_id, now()))
        return {"partner_id": partner["id"], "recorded": True}

    @app.post("/api/leads", status_code=201)
    def create_lead(payload: LeadInput):
        record = payload.model_dump()
        if record["area"] not in known_areas:
            raise HTTPException(422, "Select a listed Singapore planning area")
        with session(path) as db:
            partner = None
            if record["referral_code"]:
                partner = db.execute("SELECT id FROM partners WHERE referral_code=? AND active=1", (record["referral_code"],)).fetchone()
                if not partner:
                    raise HTTPException(422, "Referral code is invalid")
            qualification = qualify(record, known_areas)
            score = scorer.score(record)
            model_version = scorer.model_version if score is not None else None
            db.execute(
                """INSERT INTO leads (partner_id,referral_code,area,property_type,ac_type,ac_units,daily_hours,
                   estimated_ac_spend,contact_name,contact_email,consent,qualification_status,qualification_reasons,
                   stage,ml_score,model_version,data_kind,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (partner["id"] if partner else None, record["referral_code"], record["area"], record["property_type"],
                 record["ac_type"], record["ac_units"], record["daily_hours"], record["estimated_ac_spend"],
                 record["contact_name"], record["contact_email"], int(record["consent"]), qualification["status"],
                 json.dumps(qualification["reasons"]), "new", score, model_version, "synthetic submitted enquiry", now()),
            )
            lead_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute("INSERT INTO stage_events (lead_id,from_stage,to_stage,created_at) VALUES (?,?,?,?)", (lead_id, None, "new", now()))
            row = db.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
        return {**lead_from_row(row), "area_context": area_lookup[record["area"]]["cluster_label"], "score_warning": scorer.warning(score)}

    @app.get("/api/leads")
    def list_leads(partner_id: str | None = None, stage: str | None = None):
        query = "SELECT leads.*,partners.name AS partner_name FROM leads LEFT JOIN partners ON partners.id=leads.partner_id WHERE 1=1"
        params = []
        if partner_id:
            query += " AND partner_id=?"
            params.append(partner_id)
        if stage:
            query += " AND stage=?"
            params.append(stage)
        query += " ORDER BY leads.id DESC"
        with session(path) as db:
            return [lead_from_row(row) for row in db.execute(query, params)]

    @app.get("/api/leads/{lead_id}")
    def get_lead(lead_id: int):
        with session(path) as db:
            row = db.execute("SELECT leads.*,partners.name AS partner_name FROM leads LEFT JOIN partners ON partners.id=leads.partner_id WHERE leads.id=?", (lead_id,)).fetchone()
            if not row:
                raise HTTPException(404, "Lead not found")
            events = [dict(event) for event in db.execute("SELECT * FROM stage_events WHERE lead_id=? ORDER BY id", (lead_id,))]
            drafts = [dict(draft) for draft in db.execute("SELECT * FROM followup_drafts WHERE lead_id=? ORDER BY id DESC", (lead_id,))]
        return {
            **lead_from_row(row), "stage_events": events, "drafts": drafts,
            "area_context": area_lookup[row["area"]]["cluster_label"],
            "score_warning": scorer.warning(row["ml_score"]),
        }

    @app.patch("/api/leads/{lead_id}/stage")
    def change_stage(lead_id: int, payload: StageInput):
        with session(path) as db:
            row = db.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
            if not row:
                raise HTTPException(404, "Lead not found")
            if not stage_allowed(row["stage"], payload.stage, row["qualification_status"]):
                raise HTTPException(422, f"Cannot move from {row['stage']} to {payload.stage} under demo pipeline rules")
            db.execute("UPDATE leads SET stage=? WHERE id=?", (payload.stage, lead_id))
            db.execute("INSERT INTO stage_events (lead_id,from_stage,to_stage,created_at) VALUES (?,?,?,?)", (lead_id, row["stage"], payload.stage, now()))
        return {"id": lead_id, "from_stage": row["stage"], "stage": payload.stage}

    @app.post("/api/leads/{lead_id}/draft", status_code=201)
    def create_draft(lead_id: int):
        with session(path) as db:
            row = db.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
            if not row:
                raise HTTPException(404, "Lead not found")
            message = draft_message(lead_from_row(row))
            db.execute("INSERT INTO followup_drafts (lead_id,message,status,created_at,updated_at) VALUES (?,?,?,?,?)", (lead_id, message, "draft", now(), now()))
            draft_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            result = db.execute("SELECT * FROM followup_drafts WHERE id=?", (draft_id,)).fetchone()
        return dict(result)

    @app.patch("/api/drafts/{draft_id}")
    def edit_draft(draft_id: int, payload: DraftInput):
        with session(path) as db:
            if not db.execute("SELECT id FROM followup_drafts WHERE id=?", (draft_id,)).fetchone():
                raise HTTPException(404, "Draft not found")
            db.execute("UPDATE followup_drafts SET message=?,updated_at=? WHERE id=?", (payload.message, now(), draft_id))
            result = db.execute("SELECT * FROM followup_drafts WHERE id=?", (draft_id,)).fetchone()
        return dict(result)

    @app.get("/api/dashboard")
    def dashboard():
        with session(path) as db:
            partners = db.execute("SELECT COUNT(*) FROM partners WHERE active=1").fetchone()[0]
            visits = db.execute("SELECT COUNT(*) FROM referral_events").fetchone()[0]
            submitted = db.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
            qualified = db.execute("SELECT COUNT(*) FROM leads WHERE qualification_status='qualified'").fetchone()[0]
            booked = db.execute("SELECT COUNT(DISTINCT lead_id) FROM stage_events WHERE to_stage='assessment_booked'").fetchone()[0]
            won = db.execute("SELECT COUNT(*) FROM leads WHERE stage='won'").fetchone()[0]
            stages = {stage: db.execute("SELECT COUNT(*) FROM leads WHERE stage=?", (stage,)).fetchone()[0] for stage in STAGES}
        percent = lambda n, d: round(100 * n / d, 1) if d else None
        return {
            "synthetic": True,
            "active_partners": partners, "referral_visits": visits, "submitted_enquiries": submitted,
            "qualified_enquiries": qualified, "assessments_booked": booked, "won_deals": won,
            "stage_counts": stages,
            "conversion_rates": {
                "enquiry_to_qualified_percent": percent(qualified, submitted),
                "qualified_to_booked_percent": percent(booked, qualified),
                "booked_to_won_percent": percent(won, booked),
            },
            "note": "All demo funnel records and outcomes are synthetic; rates are descriptive of this small sample, not Bizsu results.",
        }

    return app


app = create_app()
