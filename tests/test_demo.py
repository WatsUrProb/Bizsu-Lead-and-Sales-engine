import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.domain import qualify, rank_partner, stage_allowed
from backend.scoring import ConversionScorer, UNAVAILABLE_MESSAGE
from pipeline.build_data import build


ROOT = Path(__file__).resolve().parents[1]


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
                   "daily_hours": 5, "contact_name": "Real Contact", "contact_email": "not-an-email", "consent": True}
        assert client.post("/api/leads", json=payload).status_code == 422
        payload["contact_email"] = "person@example.com"
        payload["consent"] = False
        assert client.post("/api/leads", json=payload).status_code == 422
        payload["consent"] = True
        payload["property_type"] = "Unknown property"
        assert client.post("/api/leads", json=payload).status_code == 422
        payload["property_type"] = "HDB 4 room"
        payload["contact_name"] = "  "
        assert client.post("/api/leads", json=payload).status_code == 422
        payload["contact_name"] = "Real Contact"
        assert client.post("/api/leads", json=payload).status_code == 201


def test_sourced_candidates_stay_separate_from_demo_referrals(tmp_path):
    with TestClient(create_app(tmp_path / "demo.db")) as client:
        catalog = client.get("/api/candidates").json()
        assert len(catalog["candidates"]) == 8
        assert sorted(item["pilot_rank"] for item in catalog["candidates"]) == list(range(1, 9))
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


def test_company_scenario_counts_follow_attributed_demo_leads(tmp_path):
    with TestClient(create_app(tmp_path / "demo.db")) as client:
        partners = client.get("/api/partners").json()
        company_ids = {item["id"] for item in client.get("/api/candidates").json()["candidates"]}
        assert {partner["company_id"] for partner in partners} <= company_ids
        assert all(partner["scenario_only"] for partner in partners)

        before = client.get("/api/dashboard").json()["company_breakdown"]
        target = partners[0]
        payload = {
            "referral_code": target["referral_code"], "area": "Ang Mo Kio", "property_type": "HDB 4 room",
            "ac_type": "split", "ac_units": 2, "daily_hours": 6,
            "contact_name": "Demo Resident", "contact_email": "resident@example.test", "consent": True,
        }
        created = client.post("/api/leads", json=payload).json()
        assert created["company_id"] == target["company_id"]
        assert created["company_name"] == target["company_name"]
        assert client.get(f"/api/leads/{created['id']}").json()["company_id"] == target["company_id"]

        after = client.get("/api/dashboard").json()["company_breakdown"]
        for company_id in company_ids:
            expected_delta = 1 if company_id == target["company_id"] else 0
            assert after[company_id]["submitted_enquiries"] - before[company_id]["submitted_enquiries"] == expected_delta
        assert sum(item["submitted_enquiries"] for item in after.values()) == len(
            [lead for lead in client.get("/api/leads").json() if lead["partner_id"]]
        )


def test_missing_model_keeps_demo_working(tmp_path):
    scorer = ConversionScorer(tmp_path / "missing.joblib", tmp_path / "missing-card.json")
    with TestClient(create_app(tmp_path / "demo.db", scorer=scorer)) as client:
        assert client.get("/api/meta").json()["model"]["available"] is False
        seeded = client.get("/api/leads").json()
        assert len(seeded) == 12
        assert all(lead["ml_score"] is None and lead["model_version"] is None for lead in seeded)
        response = client.post("/api/leads", json={
            "area": "Ang Mo Kio", "property_type": "HDB 4 room", "ac_type": "split",
            "ac_units": 2, "daily_hours": 6, "contact_name": "Test Resident",
            "contact_email": "resident@example.test", "consent": True,
        })
        assert response.status_code == 201, response.text
        lead = response.json()
        assert lead["qualification_status"] == "qualified"
        assert lead["ml_score"] is None and lead["model_version"] is None
        assert lead["score_warning"] == UNAVAILABLE_MESSAGE
        assert client.get(f"/api/leads/{lead['id']}").json()["score_warning"] == UNAVAILABLE_MESSAGE


def test_prediction_failure_still_saves_enquiry(tmp_path):
    class BrokenModel:
        def predict_proba(self, _records):
            raise RuntimeError("prediction failed")

    scorer = ConversionScorer()
    assert scorer.available
    scorer.model = BrokenModel()
    with TestClient(create_app(tmp_path / "demo.db", seed=False, scorer=scorer)) as client:
        response = client.post("/api/leads", json={
            "area": "Ang Mo Kio", "property_type": "HDB 4 room", "ac_type": "split",
            "ac_units": 2, "daily_hours": 6, "contact_name": "Test Resident",
            "contact_email": "resident@example.test", "consent": True,
        })
        assert response.status_code == 201
        assert response.json()["ml_score"] is None
        assert response.json()["score_warning"] == UNAVAILABLE_MESSAGE


def test_simple_homeowner_enquiry_preserves_attribution_and_phone(tmp_path):
    with TestClient(create_app(tmp_path / "demo.db")) as client:
        partner = client.get("/api/partners").json()[0]
        response = client.post("/api/leads", json={
            "referral_code": partner["referral_code"], "property_type": "HDB",
            "ac_units": 3, "daily_hours": 6, "contact_name": "Demo Homeowner",
            "contact_email": "homeowner@example.test", "contact_phone": "+65 8123 4567",
            "consent": True,
        })
        assert response.status_code == 201, response.text
        lead = response.json()
        assert lead["id"] > 0
        assert lead["partner_id"] == partner["id"]
        assert lead["referral_code"] == partner["referral_code"]
        assert lead["contact_phone"] == "+65 8123 4567"
        assert lead["area"] == "Not provided" and lead["ac_type"] == "unknown"
        assert lead["qualification_status"] == "needs_review"
        assert client.get(f"/api/leads/{lead['id']}").json()["id"] == lead["id"]
        assert client.patch(f"/api/leads/{lead['id']}/stage", json={"stage": "qualified"}).status_code == 422
        assert client.post(f"/api/leads/{lead['id']}/review", json={
            "area": "Ang Mo Kio", "ac_type": "window",
            "reason": "System needs a manual compatibility check",
        }).status_code == 422
        assert client.post(f"/api/leads/{lead['id']}/review", json={
            "area": "Ang Mo Kio", "ac_type": "split",
            "reason": "Confirmed compatible AC setup by phone",
        }).status_code == 200
        assert client.patch(f"/api/leads/{lead['id']}/stage", json={"stage": "qualified"}).status_code == 200


def test_complete_form_screening_and_stage_evidence(tmp_path):
    with TestClient(create_app(tmp_path / "demo.db")) as client:
        partner = client.get("/api/partners").json()[0]
        response = client.post("/api/leads", json={
            "referral_code": partner["referral_code"], "property_type": "Condo",
            "area": "Ang Mo Kio", "ac_type": "multi_split", "ac_units": 2,
            "daily_hours": 7, "enquiry_note": "Interested in an assessment.",
            "contact_name": "Demo Homeowner", "contact_email": "homeowner@example.com",
            "consent": True,
        })
        assert response.status_code == 201, response.text
        lead = response.json()
        assert lead["qualification_status"] == "qualified"
        assert lead["company_name"] == partner["company_name"]
        assert lead["enquiry_note"] == "Interested in an assessment."
        assert client.patch(f"/api/leads/{lead['id']}/stage", json={"stage": "qualified"}).status_code == 200
        assert client.patch(f"/api/leads/{lead['id']}/stage", json={"stage": "assessment_booked"}).status_code == 422
        booked = client.patch(f"/api/leads/{lead['id']}/stage", json={
            "stage": "assessment_booked", "reason": "Customer agreed to a demo appointment on 20 Oct.",
        })
        assert booked.status_code == 200
        detail = client.get(f"/api/leads/{lead['id']}").json()
        assert detail["stage_events"][-1]["reason"] == "Customer agreed to a demo appointment on 20 Oct."


def test_any_workspace_company_can_have_an_attributed_demo_referral(tmp_path):
    with TestClient(create_app(tmp_path / "demo.db")) as client:
        company = next(item for item in client.get("/api/workspace").json()["companies"] if item["id"] == "81aircon")
        assert company["stage"] == "Discovered"
        created = client.post(f"/api/workspace/companies/{company['id']}/demo-referral")
        assert created.status_code == 200, created.text
        referral = created.json()
        assert referral["company_id"] == company["id"]
        assert client.post(f"/api/workspace/companies/{company['id']}/demo-referral").json() == referral
        lead = client.post("/api/leads", json={
            "referral_code": referral["referral_code"], "property_type": "HDB",
            "area": "Ang Mo Kio", "ac_type": "split", "ac_units": 2,
            "daily_hours": 6, "contact_name": "Demo Customer",
            "contact_email": "customer@example.com", "consent": True,
        }).json()
        assert lead["partner_id"] == referral["partner_id"]
        assert lead["company_id"] == company["id"]
        assert lead["company_name"] == company["name"]
        assert client.get("/api/dashboard").json()["company_breakdown"][company["id"]]["submitted_enquiries"] == 1
        assert client.get(f"/api/workspace/companies/{company['id']}").json()["stage"] == "Discovered"


def test_followup_requires_manual_sent_confirmation(tmp_path):
    with TestClient(create_app(tmp_path / "demo.db")) as client:
        lead_id = client.get("/api/leads").json()[0]["id"]
        draft = client.post(f"/api/leads/{lead_id}/draft").json()
        assert draft["status"] == "draft"
        assert client.post(f"/api/drafts/{draft['id']}/mark-sent", json={"confirmed": False}).status_code == 422
        sent = client.post(f"/api/drafts/{draft['id']}/mark-sent", json={"confirmed": True})
        assert sent.status_code == 200
        assert sent.json()["status"] == "sent"
        assert sent.json()["sent_at"]
        assert client.patch(f"/api/drafts/{draft['id']}", json={"message": "Change already sent text."}).status_code == 422


def test_public_mode_hides_internal_customer_records(tmp_path, monkeypatch):
    monkeypatch.setenv("BIZSU_PUBLIC_MODE", "1")
    with TestClient(create_app(tmp_path / "demo.db")) as client:
        assert client.get("/api/leads").status_code == 403
        assert client.get("/api/leads/1").status_code == 403
        assert client.get("/api/dashboard").status_code == 403
        assert client.get("/api/workspace").status_code == 403
        assert client.get("/api/candidates").status_code == 403
        assert client.post("/api/leads", json={
            "property_type": "Condo", "ac_units": 2, "daily_hours": 5,
            "contact_name": "Demo Homeowner", "contact_email": "homeowner@example.test",
            "consent": True,
        }).status_code == 201
