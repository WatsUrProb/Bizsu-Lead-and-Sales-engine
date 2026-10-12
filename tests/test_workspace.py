from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import create_app


def test_company_specific_drafts_and_controls(tmp_path: Path):
    with TestClient(create_app(db_path=tmp_path / "workspace.db", seed=False)) as client:
        companies = client.get("/api/workspace").json()["companies"]
        assert len(companies) == 20
        by_name = {item["name"]: item for item in companies}
        settings = {"purpose": "Initial proposal", "tone": "Professional", "angle": "Customer value"}
        a = client.post(f"/api/workspace/companies/{by_name['81Aircon']['id']}/generate", json=settings).json()
        b = client.post(f"/api/workspace/companies/{by_name['JetStyle Aircon']['id']}/generate", json=settings).json()
        assert a["body"] != b["body"]
        assert "hdb, condo and landed" in a["body"].lower()
        assert "yearly contract" in a["body"].lower()
        assert "yearly contract" not in b["body"].lower()
        variant = client.post(f"/api/workspace/companies/{by_name['81Aircon']['id']}/generate",
                              json={"purpose": "Meeting request", "tone": "Concise", "angle": "Installation collaboration"}).json()
        assert variant["body"] != a["body"]
        assert "technical approval" in variant["body"]


def test_save_and_stage_persist_without_implied_contact(tmp_path: Path):
    db = tmp_path / "workspace.db"
    with TestClient(create_app(db_path=db, seed=False)) as client:
        company_id = client.get("/api/workspace").json()["companies"][0]["id"]
        draft = {"purpose": "Initial proposal", "tone": "Professional", "angle": "Customer value",
                 "instructions": "", "subject": "Hello", "body": "An editable partnership proposal."}
        assert client.post(f"/api/workspace/companies/{company_id}/drafts", json=draft).status_code == 201
        assert client.get(f"/api/workspace/companies/{company_id}").json()["stage"] == "Discovered"
        assert client.post(f"/api/workspace/companies/{company_id}/stage", json={"stage": "Contacted"}).status_code == 422
        assert client.post(f"/api/workspace/companies/{company_id}/stage", json={"stage": "Shortlisted"}).status_code == 200
    with TestClient(create_app(db_path=db, seed=False)) as client:
        company = client.get(f"/api/workspace/companies/{company_id}").json()
        assert company["stage"] == "Shortlisted"
        assert len(company["drafts"]) == 1


def test_staff_can_add_and_edit_company(tmp_path: Path):
    db = tmp_path / "workspace.db"
    payload = {"name": "Example Aircon", "website": "https://example.test/", "residential_evidence": "Home servicing listed",
               "maintenance": "Unverified", "installation": "unverified", "coverage": "Unverified",
               "contact": "Website form", "source": "https://example.test/services", "retrieved_on": "2026-10-12",
               "unknowns": "Maintenance plan and coverage"}
    with TestClient(create_app(db_path=db, seed=False)) as client:
        response = client.post("/api/workspace/companies", json=payload)
        assert response.status_code == 201
        company_id = response.json()["id"]
        payload["maintenance"] = "Quarterly package"
        assert client.put(f"/api/workspace/companies/{company_id}", json=payload).status_code == 200
    with TestClient(create_app(db_path=db, seed=False)) as client:
        company = client.get(f"/api/workspace/companies/{company_id}").json()
        assert company["maintenance"] == "Quarterly package"
        assert company["origin"] == "User-entered"
