"""Customer workflow regression tests for existing and migrated demo databases."""

import sqlite3
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.db import SCHEMA, initialize
from backend.domain import draft_message
from backend.main import create_app
from backend.product_copy import CUSTOMER_FEATURES


def create_review_lead(client):
    response = client.post("/api/leads", json={
        "property_type": "HDB", "area": "Bukit Batok", "ac_type": "central",
        "ac_units": 2, "daily_hours": 6, "contact_name": "Review Resident",
        "contact_email": "review@example.test", "consent": True,
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_review_decisions_and_action_persistence(tmp_path):
    db_path = tmp_path / "demo.db"
    with TestClient(create_app(db_path)) as client:
        lead_id = create_review_lead(client)
        assert client.patch(f"/api/leads/{lead_id}/stage", json={"stage": "qualified"}).status_code == 422
        needs_info = client.post(f"/api/leads/{lead_id}/review", json={
            "decision": "need_more_information", "reason": "Need to confirm the installed system by phone.",
        })
        assert needs_info.status_code == 200, needs_info.text
        lead = client.get(f"/api/leads/{lead_id}").json()
        assert lead["stage"] == "new" and lead["qualification_status"] == "needs_review"
        assert lead["next_action"] and lead["follow_up_due_at"] and lead["reviewed_at"]
        assert lead["review_outcome"] == "need_more_information"
        assert client.patch(f"/api/leads/{lead_id}/stage", json={"stage": "qualified"}).status_code == 422

        # The original homeowner answer remains intact; staff confirmation is separate.
        invalid = client.post(f"/api/leads/{lead_id}/review", json={
            "decision": "potentially_compatible", "area": "Bukit Batok", "reason": "Confirmed by homeowner over the phone.",
        })
        assert invalid.status_code == 422
        approved = client.post(f"/api/leads/{lead_id}/review", json={
            "decision": "potentially_compatible", "area": "Bukit Batok", "ac_type": "split",
            "reason": "Confirmed split system by homeowner over the phone.",
        })
        assert approved.status_code == 200, approved.text
        lead = client.get(f"/api/leads/{lead_id}").json()
        assert lead["ac_type"] == "central" and lead["confirmed_ac_type"] == "split"
        assert lead["review_outcome"] == "potentially_compatible"
        assert [item["kind"] for item in lead["activity"]] == ["screening", "review", "review"]
        assert client.patch(f"/api/leads/{lead_id}/stage", json={"stage": "qualified"}).status_code == 200

        due = datetime(2026, 11, 1, 9, tzinfo=timezone.utc).isoformat()
        saved = client.patch(f"/api/leads/{lead_id}/actions", json={
            "assigned_to": "Ella", "next_action": "Arrange customer assessment",
            "follow_up_due_at": due, "priority": "high", "internal_notes": "Call after lunch.",
        })
        assert saved.status_code == 200, saved.text
    with TestClient(create_app(db_path)) as client:
        lead = client.get(f"/api/leads/{lead_id}").json()
        assert lead["assigned_to"] == "Ella" and lead["priority"] == "high"
        assert lead["next_action"] == "Arrange customer assessment"
        assert lead["follow_up_due_at"] == due and lead["internal_notes"] == "Call after lunch."
        assert any(item["kind"] == "follow_up" for item in lead["activity"])


def test_incompatible_review_closes_with_recorded_reason(tmp_path):
    with TestClient(create_app(tmp_path / "demo.db")) as client:
        lead_id = create_review_lead(client)
        response = client.post(f"/api/leads/{lead_id}/review", json={
            "decision": "not_compatible", "reason": "Central system is outside this demo offer.",
        })
        assert response.status_code == 200, response.text
        lead = client.get(f"/api/leads/{lead_id}").json()
        assert lead["stage"] == "lost" and lead["outcome_reason"] == "Central system is outside this demo offer."
        assert lead["stage_events"][-1]["to_stage"] == "lost"
        assert client.patch(f"/api/leads/{lead_id}/stage", json={"stage": "qualified"}).status_code == 422


def test_existing_lead_table_migrates_without_losing_rows(tmp_path):
    db_path = tmp_path / "old.db"
    with sqlite3.connect(db_path) as db:
        db.executescript(SCHEMA)
        db.execute("DROP TABLE lead_activity")
        db.execute("""INSERT INTO leads (id,area,property_type,ac_type,ac_units,daily_hours,contact_name,contact_email,consent,qualification_status,qualification_reasons,stage,created_at)
                      VALUES (7,'Bukit Batok','HDB','central',2,6,'Existing Resident','existing@example.test',1,'needs_review','[]','new','2026-10-01T00:00:00+00:00')""")
    initialize(db_path, seed=False)
    with sqlite3.connect(db_path) as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(leads)")}
        assert {"assigned_to", "next_action", "follow_up_due_at", "priority", "review_outcome", "reviewed_at", "confirmed_ac_type"} <= columns
        assert db.execute("SELECT area FROM leads WHERE id=7").fetchone()[0] == "Bukit Batok"
        assert db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lead_activity'").fetchone()


def test_customer_message_is_formal_and_links_to_official_site():
    message = draft_message({
        "contact_name": "Alex Tan", "area": "Not provided", "stage": "new",
        "qualification_status": "needs_review",
    })
    assert message.startswith("Dear Alex Tan,")
    assert "https://www.bizsu.co/" in message
    assert "physical assessment" in message
    assert "draft" not in message.lower() and "demo" not in message.lower()
    assert "Not provided" not in message
    assert "25%" not in message and "guaranteed" not in message.lower()
    for detail in ("Our CONTINEWM®", "static charge", "heat exchange", "odour"):
        assert detail.lower() in message.lower()
    assert len(CUSTOMER_FEATURES.split()) <= 45
    assert message.count("https://www.bizsu.co/") == 1
