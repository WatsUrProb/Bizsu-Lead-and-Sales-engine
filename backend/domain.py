"""Deterministic partner ranking, qualification and pipeline rules."""

from __future__ import annotations

from backend.product_copy import CUSTOMER_FEATURES

STAGES = ["new", "qualified", "assessment_booked", "assessed", "quoted", "won", "lost"]
NEXT_STAGE = {
    "new": {"qualified", "lost"},
    "qualified": {"assessment_booked", "lost"},
    "assessment_booked": {"assessed", "lost"},
    "assessed": {"quoted", "lost"},
    "quoted": {"won", "lost"},
    "won": set(),
    "lost": set(),
}
RANKING_WEIGHTS = {"residential_relevance": 0.4, "service_complementarity": 0.3, "geographic_coverage": 0.2, "engagement_fit": 0.1}
SUPPORTED_AC_TYPES = {"split", "multi_split"}


def rank_partner(partner: dict) -> dict:
    focus = partner["customer_focus"]
    residential = {"residential": 1.0, "mixed": 0.65, "commercial": 0.1}[focus]
    services = set(partner["services"])
    complementary = 1.0 if "aircon_servicing" in services else (0.6 if "hvac" in services else 0.2)
    coverage = min(len(partner["service_areas"]) / 5, 1.0)
    components = {
        "residential_relevance": residential,
        "service_complementarity": complementary,
        "geographic_coverage": coverage,
        "engagement_fit": float(partner["engagement_fit"]),
    }
    score = round(100 * sum(components[key] * weight for key, weight in RANKING_WEIGHTS.items()), 1)
    return {"score": score, "components": components, "weights": RANKING_WEIGHTS}


def qualify(lead: dict, known_areas: set[str]) -> dict:
    reasons = []
    if lead["area"] == "Not provided":
        reasons.append("Planning area needs to be confirmed")
    elif lead["area"] not in known_areas:
        reasons.append("Area is outside the assumed Singapore demo coverage")
    if lead["ac_type"] == "unknown":
        reasons.append("AC system type needs to be confirmed")
    elif lead["ac_type"] not in SUPPORTED_AC_TYPES:
        reasons.append("AC configuration needs a manual compatibility assessment")
    if lead["ac_units"] < 1:
        reasons.append("At least one AC unit is required")
    if lead["daily_hours"] <= 0:
        reasons.append("Estimated daily usage is required")
    qualified = not reasons
    if qualified:
        reasons.append("Area, AC configuration and enquiry details meet the demo screening rules")
    return {"status": "qualified" if qualified else "needs_review", "reasons": reasons}


def stage_allowed(current: str, next_stage: str, qualification_status: str) -> bool:
    if next_stage not in NEXT_STAGE.get(current, set()):
        return False
    if next_stage == "qualified" and qualification_status != "qualified":
        return False
    return True


def draft_message(lead: dict) -> str:
    name = lead["contact_name"]
    location = f" in {lead['area']}" if lead.get("area") and lead["area"] != "Not provided" else ""
    opening = f"Dear {name},\n\nThank you for your interest in Bizsu and for sharing details of your air-conditioning system{location}."
    if lead["stage"] == "new" and lead["qualification_status"] == "needs_review":
        next_step = ("We would be pleased to discuss arranging a physical assessment of your air-conditioning "
                     "setup. Could you please share a convenient date and time and, if possible, confirm the type "
                     "of system installed? Our team will review these details before confirming an appointment.")
    elif lead["stage"] in {"new", "qualified"}:
        next_step = ("We would be pleased to discuss a physical assessment of your air-conditioning setup. "
                     "Please let us know a convenient time to speak so that we can explain the next steps.")
    else:
        next_step = ("I am following up on your enquiry. Please let us know if you have any questions or would "
                     "like to discuss the next steps with our team.")
    return (f"{opening}\n\n{CUSTOMER_FEATURES}\n\n"
            f"{next_step}\n\n"
            "Kind regards,\nBizsu Team")
