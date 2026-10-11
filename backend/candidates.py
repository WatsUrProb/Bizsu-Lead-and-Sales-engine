"""Evidence-backed candidate catalog, separate from fictional referral partners."""

import json
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[1] / "data" / "company_candidates.json"
WEIGHTS = {"residential": 40, "servicing_and_installation": 30, "maintenance_plan": 20, "coverage": 10}


def load_catalog() -> dict:
    catalog = json.loads(CATALOG.read_text())
    for candidate in catalog["candidates"]:
        candidate["evidence_score"] = sum(
            weight for signal, weight in WEIGHTS.items() if candidate["signals"][signal]
        )
    return catalog


def outreach_template(candidate: dict) -> str:
    return (
        f"Subject: Exploring a possible residential collaboration with Bizsu\n\n"
        f"Hello {candidate['name']} team,\n\n"
        "Bizsu is exploring whether an air-conditioning service partnership could help homeowners "
        "understand their options. Your publicly listed services prompted us to learn more. "
        "Would you be open to a short conversation about your residential work and service coverage?\n\n"
        "This is an editable research draft. Please verify the company details and Bizsu's proposal "
        "before any outreach.\n"
    )
