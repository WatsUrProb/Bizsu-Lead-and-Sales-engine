"""FastAPI service for the Bizsu partner and customer pipeline."""

from __future__ import annotations

import json
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from backend.candidates import SCENARIO_COMPANY_BY_PARTNER, WEIGHTS, load_catalog, outreach_template
from backend.db import DEFAULT_DB, ROOT, initialize, lead_from_row, now, partner_from_row, session
from backend.domain import NEXT_STAGE, STAGES, draft_message, qualify, stage_allowed
from backend.scoring import ConversionScorer
from backend.workspace import initialize_workspace, make_router

DATA = ROOT / "data"


class LeadInput(BaseModel):
    referral_code: str | None = None
    area: str = "Not provided"
    property_type: Literal["HDB", "Condo", "Landed", "Other", "HDB 1–2 room", "HDB 3 room", "HDB 4 room", "HDB 5 room/executive", "Condo/apartment"]
    ac_type: Literal["split", "multi_split", "window", "central", "unknown"] = "unknown"
    ac_units: int = Field(ge=1, le=12)
    daily_hours: float = Field(gt=0, le=24)
    estimated_ac_spend: float | None = Field(default=None, ge=0, le=10000)
    contact_name: str = Field(min_length=2, max_length=80)
    contact_email: str = Field(min_length=3, max_length=160)
    contact_phone: str | None = Field(default=None, max_length=30)
    enquiry_note: str | None = Field(default=None, max_length=1000)
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
    def valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("consent")
    @classmethod
    def consent_required(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Consent is required to submit the demo enquiry")
        return value

    @field_validator("contact_phone")
    @classmethod
    def valid_phone(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip()
        if not all(char.isdigit() or char in "+- ()" for char in value) or sum(char.isdigit() for char in value) < 8:
            raise ValueError("Enter a valid phone number or leave it blank")
        return value


class StageInput(BaseModel):
    stage: str
    reason: str | None = Field(default=None, max_length=500)


class ReviewInput(BaseModel):
    decision: Literal["potentially_compatible", "not_compatible", "need_more_information"] = "potentially_compatible"
    area: str | None = None
    ac_type: Literal["split", "multi_split"] | None = None
    reason: str = Field(min_length=10, max_length=500)


class LeadActionInput(BaseModel):
    assigned_to: str | None = Field(default=None, max_length=80)
    next_action: str | None = Field(default=None, max_length=200)
    follow_up_due_at: datetime | None = None
    priority: Literal["low", "normal", "high"] = "normal"
    internal_notes: str | None = Field(default=None, max_length=3000)


class ReferralVisitInput(BaseModel):
    referral_code: str
    session_id: str = Field(min_length=8, max_length=100)


class DraftInput(BaseModel):
    message: str = Field(min_length=5, max_length=3000)


class SentConfirmation(BaseModel):
    confirmed: bool


class CandidateActionInput(BaseModel):
    shortlisted: bool
    outreach_draft: str = Field(max_length=3000)


def create_app(db_path: Path | None = None, seed: bool = True, scorer: ConversionScorer | None = None,
               seed_enquiries: bool = False) -> FastAPI:
    path = Path(db_path or os.environ.get("BIZSU_DB_PATH", DEFAULT_DB))
    area_data = json.loads((DATA / "processed" / "areas.json").read_text())
    cluster_data = json.loads((DATA / "processed" / "clusters.json").read_text())
    sources = json.loads((DATA / "sources.json").read_text())
    catalog = load_catalog()
    candidates_by_id = {item["id"]: item for item in catalog["candidates"]}

    def with_company(record: dict) -> dict:
        partner_id = record["partner_id"] if "partner_id" in record else record.get("id")
        company_id = record.get("company_id")
        company_name = None
        if partner_id:
            with session(path) as db:
                partner = db.execute("SELECT company_id FROM partners WHERE id=?", (partner_id,)).fetchone()
                company_id = company_id or (partner["company_id"] if partner else None)
                if company_id:
                    company = db.execute("SELECT name FROM prospect_companies WHERE id=?", (company_id,)).fetchone()
                    company_name = company["name"] if company else candidates_by_id.get(company_id, {}).get("name")
        return {
            **record,
            "company_id": company_id,
            "company_name": company_name,
            "scenario_only": True,
        }
    scorer = scorer or ConversionScorer()
    areas = [
        {**area, **cluster_data["assignments"].get(area["name"], {"cluster_id": None, "cluster_label": None})}
        for area in area_data["areas"]
    ]
    known_areas = {area["name"] for area in areas if area["name"] != "Others"}
    area_lookup = {area["name"]: area for area in areas}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        initialize(path, seed=seed, scorer=scorer, seed_enquiries=seed_enquiries)
        initialize_workspace(path)
        with session(path) as db:
            for partner_id, company_id in SCENARIO_COMPANY_BY_PARTNER.items():
                db.execute("UPDATE partners SET company_id=? WHERE id=? AND company_id IS NULL",
                           (company_id, partner_id))
        yield

    app = FastAPI(title="Bizsu Hackathon Demo API", version="0.1.0", lifespan=lifespan)
    app.include_router(make_router(path))

    @app.middleware("http")
    async def restrict_internal_records(request: Request, call_next):
        if os.environ.get("VERCEL") or os.environ.get("DATABASE_URL"):
            if not os.environ.get("DATABASE_URL"):
                return JSONResponse(status_code=503, content={"detail": "Database is not configured"})
            route = request.url.path
            public_form = os.environ.get("BIZSU_PUBLIC_FORM") == "1"
            public = (route == "/api/health"
                      or route == "/api/areas" and request.method == "GET"
                      or route == "/api/partners" and request.method == "GET"
                      or public_form and route == "/api/referral-visits" and request.method == "POST"
                      or public_form and route == "/api/leads" and request.method == "POST")
            if route.startswith("/api/") and not public:
                expected = os.environ.get("BIZSU_ADMIN_KEY", "")
                supplied = request.headers.get("x-bizsu-admin-key", "")
                if not expected or not secrets.compare_digest(supplied, expected):
                    return JSONResponse(status_code=401, content={"detail": "Staff access key required"})
        if os.environ.get("BIZSU_PUBLIC_MODE") == "1":
            route = request.url.path
            internal = (
                route.startswith("/api/workspace")
                or route.startswith("/api/candidates")
                or route == "/api/dashboard"
                or route.startswith("/api/drafts")
                or (route.startswith("/api/leads") and not (route == "/api/leads" and request.method == "POST"))
            )
            if internal:
                return JSONResponse(status_code=403, content={"detail": "Internal demo records are unavailable in public mode"})
        return await call_next(request)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": "supabase" if os.environ.get("DATABASE_URL") else "local demo"}

    @app.get("/api/meta")
    def meta():
        return {
            "sources": sources,
            "clusters": {key: value for key, value in cluster_data.items() if key != "assignments"},
            "model": scorer.metadata(),
            "stages": STAGES,
            "demo_note": "Company profiles are public research. Every company-level referral and sales figure is a simulated scenario, not company or Bizsu performance.",
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
        return [with_company(partner) for partner in partners]

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
            "candidates": sorted(candidates, key=lambda item: (-item["evidence_score"], item["pilot_rank"])),
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
        if record["area"] != "Not provided" and record["area"] not in known_areas:
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
                   estimated_ac_spend,contact_name,contact_email,contact_phone,enquiry_note,consent,qualification_status,qualification_reasons,
                   stage,ml_score,model_version,data_kind,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (partner["id"] if partner else None, record["referral_code"], record["area"], record["property_type"],
                 record["ac_type"], record["ac_units"], record["daily_hours"], record["estimated_ac_spend"],
                 record["contact_name"], record["contact_email"], record["contact_phone"], record["enquiry_note"], int(record["consent"]), qualification["status"],
                 json.dumps(qualification["reasons"]), "new", score, model_version, "synthetic submitted enquiry", now()),
            )
            lead_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute("INSERT INTO stage_events (lead_id,from_stage,to_stage,reason,created_at) VALUES (?,?,?,?,?)", (lead_id, None, "new", "Homeowner submitted the enquiry form with contact consent.", now()))
            db.execute("INSERT INTO lead_activity (lead_id,kind,detail,created_at) VALUES (?,?,?,?)",
                       (lead_id, "screening", "Initial screening: " + qualification["status"].replace("_", " ") + ". " + "; ".join(qualification["reasons"]), now()))
            row = db.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
        return {**with_company(lead_from_row(row)), "area_context": area_lookup.get(record["area"], {}).get("cluster_label"), "score_warning": scorer.warning(score)}

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
            return [with_company(lead_from_row(row)) for row in db.execute(query, params)]

    @app.get("/api/leads/{lead_id}")
    def get_lead(lead_id: int):
        with session(path) as db:
            row = db.execute("SELECT leads.*,partners.name AS partner_name FROM leads LEFT JOIN partners ON partners.id=leads.partner_id WHERE leads.id=?", (lead_id,)).fetchone()
            if not row:
                raise HTTPException(404, "Lead not found")
            events = [dict(event) for event in db.execute("SELECT * FROM stage_events WHERE lead_id=? ORDER BY id", (lead_id,))]
            activity = [dict(event) for event in db.execute("SELECT * FROM lead_activity WHERE lead_id=? ORDER BY id", (lead_id,))]
            drafts = [dict(draft) for draft in db.execute("SELECT * FROM followup_drafts WHERE lead_id=? ORDER BY id DESC", (lead_id,))]
        return {**with_company(lead_from_row(row)), "stage_events": events, "activity": activity, "drafts": drafts, "area_context": area_lookup.get(row["area"], {}).get("cluster_label"), "score_warning": scorer.warning(row["ml_score"])}

    @app.patch("/api/leads/{lead_id}/actions")
    def update_lead_actions(lead_id: int, payload: LeadActionInput):
        details = payload.model_dump()
        for field in ("assigned_to", "next_action", "internal_notes"):
            details[field] = (details[field] or "").strip() or None
        due = details["follow_up_due_at"]
        if due and due.tzinfo is None:
            raise HTTPException(422, "Follow-up time must include a timezone")
        due_value = due.astimezone(timezone.utc).isoformat(timespec="seconds") if due else None
        with session(path) as db:
            row = db.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
            if not row:
                raise HTTPException(404, "Lead not found")
            db.execute("""UPDATE leads SET assigned_to=?,next_action=?,follow_up_due_at=?,priority=?,internal_notes=? WHERE id=?""",
                       (details["assigned_to"], details["next_action"], due_value, details["priority"], details["internal_notes"], lead_id))
            changes = [label for column, label, value in (
                ("assigned_to", "owner", details["assigned_to"]), ("next_action", "next action", details["next_action"]),
                ("follow_up_due_at", "follow-up date", due_value), ("priority", "priority", details["priority"]),
                ("internal_notes", "internal notes", details["internal_notes"]),
            ) if (row[column] or None) != value]
            if changes:
                db.execute("INSERT INTO lead_activity (lead_id,kind,detail,created_at) VALUES (?,?,?,?)",
                           (lead_id, "follow_up", "Updated " + ", ".join(changes) + ".", now()))
        return {"id": lead_id, "updated": changes}

    @app.patch("/api/leads/{lead_id}/stage")
    def change_stage(lead_id: int, payload: StageInput):
        with session(path) as db:
            row = db.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
            if not row:
                raise HTTPException(404, "Lead not found")
            if not stage_allowed(row["stage"], payload.stage, row["qualification_status"]):
                raise HTTPException(422, f"Cannot move from {row['stage']} to {payload.stage} under demo pipeline rules")
            reason = (payload.reason or "").strip()
            if payload.stage != "qualified" and len(reason) < 10:
                raise HTTPException(422, "Record at least 10 characters of evidence or an outcome reason")
            if payload.stage == "qualified":
                reason = "Initial screening passed or staff review confirmed suitability."
            db.execute("UPDATE leads SET stage=? WHERE id=?", (payload.stage, lead_id))
            if payload.stage == "lost":
                db.execute("UPDATE leads SET outcome_reason=? WHERE id=?", (reason, lead_id))
            db.execute("INSERT INTO stage_events (lead_id,from_stage,to_stage,reason,created_at) VALUES (?,?,?,?,?)", (lead_id, row["stage"], payload.stage, reason, now()))
        return {"id": lead_id, "from_stage": row["stage"], "stage": payload.stage, "reason": reason}

    @app.post("/api/leads/{lead_id}/review")
    def approve_after_review(lead_id: int, payload: ReviewInput):
        reason = payload.reason.strip()
        if len(reason) < 10:
            raise HTTPException(422, "Record at least 10 characters explaining the review decision")
        if payload.area is not None and payload.area not in known_areas:
            raise HTTPException(422, "Confirm a listed Singapore planning area")
        with session(path) as db:
            row = db.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
            if not row:
                raise HTTPException(404, "Lead not found")
            if row["stage"] != "new" or row["qualification_status"] != "needs_review":
                raise HTTPException(422, "Only new enquiries awaiting review can be reviewed")
            area = payload.area or row["area"]
            ac_type = payload.ac_type or row["ac_type"]
            reviewed_at = now()
            if payload.decision == "potentially_compatible":
                if area not in known_areas:
                    raise HTTPException(422, "Confirm a listed Singapore planning area")
                if ac_type not in {"split", "multi_split"}:
                    raise HTTPException(422, "Confirm a supported split or multi-split AC system")
                eligibility = qualify({"area": area, "ac_type": ac_type, "ac_units": row["ac_units"], "daily_hours": row["daily_hours"]}, known_areas)
                if eligibility["status"] != "qualified":
                    raise HTTPException(422, "Eligibility requirements are not met: " + "; ".join(eligibility["reasons"]))
                reasons = ["Initial review flag: " + item for item in json.loads(row["qualification_reasons"])]
                reasons += ["Staff confirmed planning area: " + area, "Staff confirmed supported AC system: " + ac_type.replace("_", " "), "Staff review: " + reason]
                db.execute("""UPDATE leads SET qualification_status='qualified',qualification_reasons=?,review_outcome=?,review_notes=?,reviewed_at=?,confirmed_area=?,confirmed_ac_type=? WHERE id=?""",
                           (json.dumps(reasons), payload.decision, reason, reviewed_at, area, ac_type, lead_id))
            elif payload.decision == "not_compatible":
                db.execute("""UPDATE leads SET review_outcome=?,review_notes=?,reviewed_at=?,confirmed_area=?,confirmed_ac_type=?,stage='lost',outcome_reason=? WHERE id=?""",
                           (payload.decision, reason, reviewed_at, payload.area, payload.ac_type, reason, lead_id))
                db.execute("INSERT INTO stage_events (lead_id,from_stage,to_stage,reason,created_at) VALUES (?,?,?,?,?)",
                           (lead_id, "new", "lost", reason, reviewed_at))
            else:
                due = row["follow_up_due_at"] or (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(timespec="seconds")
                db.execute("""UPDATE leads SET review_outcome=?,review_notes=?,reviewed_at=?,confirmed_area=?,confirmed_ac_type=?,next_action=?,follow_up_due_at=? WHERE id=?""",
                           (payload.decision, reason, reviewed_at, payload.area, payload.ac_type, "Contact homeowner to confirm compatibility details", due, lead_id))
            db.execute("INSERT INTO lead_activity (lead_id,kind,detail,created_at) VALUES (?,?,?,?)",
                       (lead_id, "review", payload.decision.replace("_", " ").capitalize() + ": " + reason, reviewed_at))
        return {"id": lead_id, "decision": payload.decision, "qualification_status": "qualified" if payload.decision == "potentially_compatible" else "needs_review", "reason": reason}

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
            existing = db.execute("SELECT id,status FROM followup_drafts WHERE id=?", (draft_id,)).fetchone()
            if not existing:
                raise HTTPException(404, "Draft not found")
            if existing["status"] != "draft":
                raise HTTPException(422, "Create a new draft to change a recorded sent message")
            db.execute("UPDATE followup_drafts SET message=?,updated_at=? WHERE id=?", (payload.message, now(), draft_id))
            result = db.execute("SELECT * FROM followup_drafts WHERE id=?", (draft_id,)).fetchone()
        return dict(result)

    @app.post("/api/drafts/{draft_id}/mark-sent")
    def mark_draft_sent(draft_id: int, payload: SentConfirmation):
        if not payload.confirmed:
            raise HTTPException(422, "Confirm that you sent this message outside the prototype")
        with session(path) as db:
            existing = db.execute("SELECT * FROM followup_drafts WHERE id=?", (draft_id,)).fetchone()
            if not existing:
                raise HTTPException(404, "Draft not found")
            if existing["status"] != "draft":
                raise HTTPException(422, "This message was already marked sent")
            db.execute("UPDATE followup_drafts SET status='sent',sent_at=?,updated_at=? WHERE id=?",
                       (now(), now(), draft_id))
            db.execute("INSERT INTO lead_activity (lead_id,kind,detail,created_at) VALUES (?,?,?,?)",
                       (existing["lead_id"], "follow_up", "Staff marked a follow-up message sent outside the prototype.", now()))
            result = db.execute("SELECT * FROM followup_drafts WHERE id=?", (draft_id,)).fetchone()
        return dict(result)

    @app.get("/api/dashboard")
    def dashboard():
        with session(path) as db:
            active_partners = [dict(row) for row in db.execute("SELECT id,company_id FROM partners WHERE active=1")]
            active_ids = {row["id"] for row in active_partners}
            companies = {item["id"]: {"id": item["id"], "name": item["name"]} for item in candidates_by_id.values()}
            companies.update({row["id"]: dict(row) for row in db.execute("SELECT id,name FROM prospect_companies")})
            visits = [row["partner_id"] for row in db.execute("SELECT partner_id FROM referral_events")]
            leads = [dict(row) for row in db.execute("SELECT id,partner_id,qualification_status,stage FROM leads")]
            booked_ids = {row["lead_id"] for row in db.execute("SELECT lead_id FROM stage_events WHERE to_stage='assessment_booked'")}

        def summary(partner_ids: set[str] | None) -> dict:
            scoped_leads = [lead for lead in leads if partner_ids is None or lead["partner_id"] in partner_ids]
            submitted = len(scoped_leads)
            qualified = sum(lead["qualification_status"] == "qualified" for lead in scoped_leads)
            booked = sum(lead["id"] in booked_ids for lead in scoped_leads)
            won = sum(lead["stage"] == "won" for lead in scoped_leads)
            percent = lambda numerator, denominator: round(100 * numerator / denominator, 1) if denominator else None
            return {
                "synthetic": True,
                "active_partners": len(active_ids if partner_ids is None else active_ids & partner_ids),
                "referral_visits": sum(partner_ids is None or visit in partner_ids for visit in visits),
                "submitted_enquiries": submitted,
                "qualified_enquiries": qualified,
                "assessments_booked": booked,
                "won_deals": won,
                "stage_counts": {stage: sum(lead["stage"] == stage for lead in scoped_leads) for stage in STAGES},
                "conversion_rates": {
                    "enquiry_to_qualified_percent": percent(qualified, submitted),
                    "qualified_to_booked_percent": percent(booked, qualified),
                    "booked_to_won_percent": percent(won, booked),
                },
            }

        company_breakdown = {
            company["id"]: {
                "company_name": company["name"],
                **summary({partner["id"] for partner in active_partners if partner["company_id"] == company["id"]}),
            }
            for company in companies.values()
        }
        return {
            **summary(None),
            "company_breakdown": company_breakdown,
            "note": "All company-level visits, enquiries and outcomes are simulated scenarios. They are not activity by, or partnerships with, the listed companies.",
        }

    return app


app = create_app()
