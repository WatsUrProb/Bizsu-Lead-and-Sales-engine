import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.domain import qualify, rank_partner, stage_allowed
from backend.scoring import ConversionScorer, UNAVAILABLE_MESSAGE
from pipeline.build_data import build


ROOT = Path(__file__).resolve().parents[1]


def lead_payload() -> dict:
    return {
        "area": "Ang Mo Kio", "property_type": "HDB 4 room", "ac_type": "split",
        "ac_units": 2, "daily_hours": 6, "estimated_ac_spend": None,
        "contact_name": "Test Resident", "contact_email": "resident@example.test", "consent": True,
    }


def test_real_data_join_keeps_aggregate_level_and_suppressed_values():
    result = build()
    assert result["unit"].startswith("planning area")
    assert len(result["areas"]) == 31
    assert sum(area["cluster_eligible"] for area in result["areas"]) == 28
    assert next(area for area in result["areas"] if area["name"] == "River Valley")["features"]["hdb_share"] is None
    assert next(area for area in result["areas"] if area["name"] == "Others")["cluster_eligible"] is False
    clusters = json.loads((ROOT / "data/processed/clusters.json").read_text())
    assert [item["k"] for item in clusters["candidate_metrics"]] == [2, 3, 4]
    assert "electricity" not in " ".join(clusters["feature_keys"])


def test_referral_qualification_stage_and_metrics(tmp_path):
    app = create_app(tmp_path / "demo.db", seed=False)
    with TestClient(app) as client:
        # Seed partners while leaving leads empty, so metrics can be checked from zero.
        from backend.db import initialize
        initialize(tmp_path / "demo.db", seed=True)
        with sqlite3.connect(tmp_path / "demo.db") as db:
            db.execute("DELETE FROM stage_events")
            db.execute("DELETE FROM leads")
            db.execute("DELETE FROM referral_events")
            db.commit()
        assert client.get("/api/dashboard").json()["conversion_rates"]["enquiry_to_qualified_percent"] is None
        partner = client.get("/api/partners").json()[0]
        assert partner["ranking"]["score"] == rank_partner(partner)["score"]
        visit = {"referral_code": partner["referral_code"], "session_id": "test-session-001"}
        assert client.post("/api/referral-visits", json=visit).status_code == 200
        assert client.post("/api/referral-visits", json=visit).status_code == 200
        payload = {
            "referral_code": partner["referral_code"], "area": "Ang Mo Kio", "property_type": "HDB 4 room",
            "ac_type": "split", "ac_units": 2, "daily_hours": 6, "estimated_ac_spend": None,
            "contact_name": "Test Resident", "contact_email": "resident@example.test", "consent": True,
        }
        response = client.post("/api/leads", json=payload)
        assert response.status_code == 201, response.text
        lead = response.json()
        assert lead["partner_id"] == partner["id"]
        assert lead["referral_code"] == partner["referral_code"]
        assert lead["qualification_status"] == "qualified"
        assert "unvalidated" in lead["score_warning"]
        assert client.patch(f"/api/leads/{lead['id']}/stage", json={"stage": "won"}).status_code == 422
        assert client.patch(f"/api/leads/{lead['id']}/stage", json={"stage": "qualified"}).status_code == 200
        assert [event["to_stage"] for event in client.get(f"/api/leads/{lead['id']}").json()["stage_events"]] == ["new", "qualified"]
        draft = client.post(f"/api/leads/{lead['id']}/draft").json()
        assert draft["status"] == "draft"
        saved = client.patch(f"/api/drafts/{draft['id']}", json={"message": "Reviewed local demo draft."}).json()
        assert saved["message"] == "Reviewed local demo draft."
        metrics = client.get("/api/dashboard").json()
        assert metrics["submitted_enquiries"] == 1
        assert metrics["qualified_enquiries"] == 1
        assert metrics["referral_visits"] == 1


def test_synthetic_only_contact_and_review_rules(tmp_path):
    assert qualify({"area": "Ang Mo Kio", "ac_type": "window", "ac_units": 1, "daily_hours": 3}, {"Ang Mo Kio"})["status"] == "needs_review"
    assert not stage_allowed("new", "qualified", "needs_review")
    with TestClient(create_app(tmp_path / "demo.db")) as client:
        payload = {"area": "Ang Mo Kio", "property_type": "HDB 4 room", "ac_type": "split", "ac_units": 1,
                   "daily_hours": 5, "contact_name": "Real Contact", "contact_email": "person@example.com", "consent": True}
        assert client.post("/api/leads", json=payload).status_code == 422
        payload["contact_email"] = "person@example.test"
        payload["consent"] = False
        assert client.post("/api/leads", json=payload).status_code == 422
        payload["consent"] = True
        payload["property_type"] = "Unknown property"
        assert client.post("/api/leads", json=payload).status_code == 422
        payload["property_type"] = "HDB 4 room"
        payload["contact_name"] = "  "
        assert client.post("/api/leads", json=payload).status_code == 422


def test_sourced_candidates_stay_separate_from_demo_referrals(tmp_path):
    with TestClient(create_app(tmp_path / "demo.db")) as client:
        catalog = client.get("/api/candidates").json()
        assert len(catalog["candidates"]) == 3
        candidate = catalog["candidates"][0]
        assert candidate["evidence"] and candidate["website"].startswith("https://")
        assert candidate["shortlisted"] is False
        assert "Unverified" in next(item["coverage"] for item in catalog["candidates"] if item["id"] == "gain-city")
        assert candidate["id"] not in {partner["id"] for partner in client.get("/api/partners").json()}
        response = client.patch(f"/api/candidates/{candidate['id']}", json={
            "shortlisted": True, "outreach_draft": "Draft for human review only.",
        })
        assert response.status_code == 200
        assert response.json()["sent"] is False
        saved = next(item for item in client.get("/api/candidates").json()["candidates"] if item["id"] == candidate["id"])
        assert saved["shortlisted"] is True
        assert saved["outreach_draft"] == "Draft for human review only."
        client.patch(f"/api/candidates/{candidate['id']}", json={"shortlisted": True, "outreach_draft": ""})
        cleared = next(item for item in client.get("/api/candidates").json()["candidates"] if item["id"] == candidate["id"])
        assert cleared["outreach_draft"] == ""
        assert client.patch("/api/candidates/unknown", json={"shortlisted": True, "outreach_draft": "x"}).status_code == 404
        assert client.get("/api/dashboard").json()["active_partners"] == 4


def test_missing_model_disables_only_synthetic_scoring(tmp_path):
    scorer = ConversionScorer(tmp_path / "missing.joblib", tmp_path / "missing-card.json")
    assert scorer.available is False
    with TestClient(create_app(tmp_path / "demo.db", scorer=scorer)) as client:
        metadata = client.get("/api/meta").json()["model"]
        assert metadata == {
            "available": False,
            "version": None,
            "unavailable_reason": "Synthetic scoring model is unavailable.",
        }
        seeded = client.get("/api/leads").json()
        assert len(seeded) == 12
        assert all(lead["ml_score"] is None and lead["model_version"] is None for lead in seeded)
        response = client.post("/api/leads", json=lead_payload())
        assert response.status_code == 201, response.text
        lead = response.json()
        assert lead["qualification_status"] == "qualified"
        assert lead["ml_score"] is None
        assert lead["model_version"] is None
        assert lead["score_warning"] == UNAVAILABLE_MESSAGE
        detail = client.get(f"/api/leads/{lead['id']}").json()
        assert detail["score_warning"] == UNAVAILABLE_MESSAGE


def test_invalid_model_artifacts_are_contained(tmp_path):
    valid_card = ROOT / "data/models/conversion_card.json"
    corrupt_model = tmp_path / "corrupt.joblib"
    corrupt_model.write_bytes(b"not a joblib model")
    assert ConversionScorer(corrupt_model, valid_card).available is False

    invalid_card = tmp_path / "invalid-card.json"
    invalid_card.write_text("not json")
    assert ConversionScorer(ROOT / "data/models/conversion.joblib", invalid_card).available is False


def test_prediction_failure_still_saves_lead(tmp_path):
    class BrokenModel:
        def predict_proba(self, _records):
            raise RuntimeError("prediction failed")

    scorer = ConversionScorer()
    assert scorer.available is True
    scorer.model = BrokenModel()
    with TestClient(create_app(tmp_path / "demo.db", seed=False, scorer=scorer)) as client:
        response = client.post("/api/leads", json=lead_payload())
        assert response.status_code == 201, response.text
        lead = response.json()
        assert lead["qualification_status"] == "qualified"
        assert lead["ml_score"] is None
        assert lead["model_version"] is None
        assert lead["score_warning"] == UNAVAILABLE_MESSAGE
