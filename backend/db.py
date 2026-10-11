"""SQLite schema and synthetic seed records."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import joblib

from backend.domain import rank_partner

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "demo.db"

DEMO_PARTNERS = [
    {"id": "partner001", "name": "Demo Partner A · North", "description": "Fictional residential air-conditioning servicing business used only for this hackathon.", "customer_focus": "residential", "service_areas": ["Ang Mo Kio", "Bishan", "Sembawang", "Woodlands", "Yishun"], "services": ["aircon_servicing", "maintenance"], "engagement_fit": 0.9, "referral_code": "partner001"},
    {"id": "partner002", "name": "Demo Partner B · East", "description": "Fictional mixed-service business used only for this hackathon.", "customer_focus": "mixed", "service_areas": ["Bedok", "Pasir Ris", "Punggol", "Sengkang", "Tampines"], "services": ["aircon_servicing", "maintenance"], "engagement_fit": 0.75, "referral_code": "partner002"},
    {"id": "partner003", "name": "Demo Partner C · West", "description": "Fictional HVAC service business used only for this hackathon.", "customer_focus": "residential", "service_areas": ["Bukit Batok", "Bukit Panjang", "Choa Chu Kang", "Clementi", "Jurong West"], "services": ["hvac", "maintenance"], "engagement_fit": 0.7, "referral_code": "partner003"},
    {"id": "partner004", "name": "Demo Partner D · Central", "description": "Fictional commercial-first business used only for this hackathon.", "customer_focus": "commercial", "service_areas": ["Bukit Merah", "Kallang", "Queenstown"], "services": ["hvac"], "engagement_fit": 0.5, "referral_code": "partner004"},
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path = DEFAULT_DB) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def session(path: Path = DEFAULT_DB):
    connection = connect(path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS partners (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
 customer_focus TEXT NOT NULL, service_areas TEXT NOT NULL, services TEXT NOT NULL,
 engagement_fit REAL NOT NULL, referral_code TEXT NOT NULL UNIQUE,
 source_notes TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS leads (
 id INTEGER PRIMARY KEY AUTOINCREMENT, partner_id TEXT REFERENCES partners(id), referral_code TEXT,
 area TEXT NOT NULL, property_type TEXT NOT NULL, ac_type TEXT NOT NULL,
 ac_units INTEGER NOT NULL, daily_hours REAL NOT NULL, estimated_ac_spend REAL,
 contact_name TEXT NOT NULL, contact_email TEXT NOT NULL, consent INTEGER NOT NULL,
 qualification_status TEXT NOT NULL, qualification_reasons TEXT NOT NULL,
 stage TEXT NOT NULL DEFAULT 'new', ml_score REAL, model_version TEXT,
 data_kind TEXT NOT NULL DEFAULT 'synthetic', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stage_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER NOT NULL REFERENCES leads(id),
 from_stage TEXT, to_stage TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS followup_drafts (
 id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER NOT NULL REFERENCES leads(id),
 message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft', created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS referral_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, partner_id TEXT NOT NULL REFERENCES partners(id),
 session_id TEXT NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(partner_id, session_id)
);
CREATE TABLE IF NOT EXISTS candidate_actions (
 candidate_id TEXT PRIMARY KEY, shortlisted INTEGER NOT NULL DEFAULT 0,
 outreach_draft TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS leads_partner_stage ON leads(partner_id, stage);
CREATE INDEX IF NOT EXISTS stage_events_lead ON stage_events(lead_id);
"""


def initialize(path: Path = DEFAULT_DB, seed: bool = True) -> None:
    with session(path) as connection:
        connection.executescript(SCHEMA)
        if seed and connection.execute("SELECT COUNT(*) FROM partners").fetchone()[0] == 0:
            for partner in DEMO_PARTNERS:
                connection.execute(
                    "INSERT INTO partners VALUES (?,?,?,?,?,?,?,?,?,1)",
                    (partner["id"], partner["name"], partner["description"], partner["customer_focus"],
                     json.dumps(partner["service_areas"]), json.dumps(partner["services"]),
                     partner["engagement_fit"], partner["referral_code"], "Fictional demo partner; no real company facts"),
                )
        if seed and connection.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0:
            records = [row for row in json.loads((ROOT / "data" / "processed" / "synthetic_training.json").read_text()) if row["ac_type"] == "split"][:12]
            model_card = json.loads((ROOT / "data" / "models" / "conversion_card.json").read_text())
            model = joblib.load(ROOT / "data" / "models" / "conversion.joblib")
            for index, record in enumerate(records, start=1):
                partner = DEMO_PARTNERS[(index - 1) % len(DEMO_PARTNERS)]
                stage = ["new", "qualified", "assessment_booked", "assessed", "quoted", "won", "lost"][index % 7]
                model_input = {key: record[key] for key in model_card["feature_keys"]}
                ml_score = round(float(model.predict_proba([model_input])[0, 1]) * 100, 1)
                connection.execute(
                    """INSERT INTO leads (partner_id,referral_code,area,property_type,ac_type,ac_units,daily_hours,
                       contact_name,contact_email,consent,qualification_status,qualification_reasons,stage,
                       ml_score,model_version,data_kind,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (partner["id"], partner["referral_code"], record["area"], record["property_type"],
                     record["ac_type"], record["ac_units"], record["daily_hours"], f"Demo Resident {index:02d}",
                     f"resident{index:02d}@example.test", 1, "qualified",
                     json.dumps(["Synthetic seeded record; eligibility is illustrative"]), stage,
                     ml_score, model_card["version"], "synthetic seeded enquiry", now()),
                )
                lead_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
                connection.execute("INSERT INTO stage_events (lead_id,from_stage,to_stage,created_at) VALUES (?,?,?,?)", (lead_id, None, "new", now()))
                path = ["qualified", "assessment_booked", "assessed", "quoted", "won"]
                if stage == "lost":
                    path = ["qualified", "assessment_booked", "lost"]
                elif stage != "new":
                    path = path[:path.index(stage) + 1]
                else:
                    path = []
                previous = "new"
                for step in path:
                    connection.execute("INSERT INTO stage_events (lead_id,from_stage,to_stage,created_at) VALUES (?,?,?,?)", (lead_id, previous, step, now()))
                    previous = step
        if seed:
            # Backfill earlier local demo databases created before seeded visits were added.
            for row in connection.execute("SELECT id,partner_id FROM leads WHERE data_kind='synthetic seeded enquiry' AND partner_id IS NOT NULL"):
                connection.execute("INSERT OR IGNORE INTO referral_events (partner_id,session_id,created_at) VALUES (?,?,?)", (row["partner_id"], f"seed-lead-{row['id']}", now()))


def partner_from_row(row: sqlite3.Row) -> dict:
    partner = dict(row)
    partner["service_areas"] = json.loads(partner["service_areas"])
    partner["services"] = json.loads(partner["services"])
    partner["active"] = bool(partner["active"])
    partner["synthetic"] = True
    partner["ranking"] = rank_partner(partner)
    return partner


def lead_from_row(row: sqlite3.Row) -> dict:
    lead = dict(row)
    lead["qualification_reasons"] = json.loads(lead["qualification_reasons"])
    lead["consent"] = bool(lead["consent"])
    return lead
