"""Join Census 2020 aggregate tables without manufacturing household-level records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

FEATURE_LABELS = {
    "hdb_share": "HDB household share",
    "large_hdb_share": "4/5-room HDB household share",
    "condo_share": "Condo/apartment household share",
    "large_household_share": "4+ person household share",
    "high_income_share": "$10k+ work-income household share",
}


def number(value: object) -> int | None:
    if value is None or str(value).strip().lower() in {"-", "na", "", "null"}:
        return None
    return int(float(str(value).replace(",", "")))


def fraction(numerator: int | None, denominator: int) -> float | None:
    return None if numerator is None or denominator <= 0 else numerator / denominator


def sum_present(row: dict, keys: list[str]) -> int | None:
    values = [number(row.get(key)) for key in keys]
    return None if any(value is None for value in values) else sum(values)


def checked_snapshot(source: dict) -> dict:
    path = DATA / source["file"]
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != source["sha256"]:
        raise ValueError(f"Source checksum mismatch: {path}")
    return json.loads(content)


def keyed_rows(records: list[dict]) -> dict[str, dict]:
    return {str(row["Number"]).strip(): row for row in records if row["Number"] != "Total"}


def build() -> dict:
    manifest = json.loads((DATA / "sources.json").read_text())
    sources = {source["key"]: source for source in manifest["sources"]}
    dwelling = keyed_rows(checked_snapshot(sources["dwelling"])["records"])
    size = keyed_rows(checked_snapshot(sources["household_size"])["records"])
    income = keyed_rows(checked_snapshot(sources["income"])["records"])
    if set(dwelling) != set(size) or set(dwelling) != set(income):
        raise ValueError("Census planning-area keys differ; refusing an incomplete join")
    ema = checked_snapshot(sources["ema_2013"])
    ema_by_name = {row["PLN_AREA_N"].strip().title(): row for row in ema["areas"]}
    ac_rows = checked_snapshot(sources["ac_ownership"])["records"]
    ac_ownership = next(float(row["2023"]) for row in ac_rows if row["DataSeries"] == "Air Conditioner")

    areas = []
    for name in sorted(dwelling):
        d, s, i = dwelling[name], size[name], income[name]
        totals = (number(d["Total"]), number(s["Total"]), number(i["Total"]))
        if len(set(totals)) != 1 or totals[0] is None:
            raise ValueError(f"Census totals disagree for {name}: {totals}")
        total = totals[0]
        housing = {
            "hdb_1_2": number(d["HDBDwellings_1_and2_RoomFlats1"]),
            "hdb_3": number(d["HDBDwellings_3_RoomFlats"]),
            "hdb_4": number(d["HDBDwellings_4_RoomFlats"]),
            "hdb_5_exec": number(d["HDBDwellings_5_RoomandExecutiveFlats"]),
            "condo": number(d["CondominiumsandOtherApartments"]),
            "landed": number(d["LandedProperties"]),
            "other": number(d["Others"]),
        }
        household_size_counts = {str(n): number(s[f"{n}Person" if n == 1 else f"{n}Persons"]) for n in range(1, 8)}
        household_size_counts["8+"] = number(s["8orMorePersons"])
        income_keys = [key for key in i if key.startswith(("10_000", "11_000", "12_000", "13_000", "14_000", "15_000", "17_500", "20_000"))]
        features = {
            "hdb_share": fraction(number(d["HDBDwellings_Total"]), total),
            "large_hdb_share": fraction(sum_present(d, ["HDBDwellings_4_RoomFlats", "HDBDwellings_5_RoomandExecutiveFlats"]), total),
            "condo_share": fraction(housing["condo"], total),
            "large_household_share": fraction(sum_present(s, ["4Persons", "5Persons", "6Persons", "7Persons", "8orMorePersons"]), total),
            "high_income_share": fraction(sum_present(i, income_keys), total),
        }
        e = ema_by_name.get(name)
        electricity = None if e is None else {
            "year": 2013,
            "average_monthly_kwh": e.get("TOTAL"),
            "hdb_4room_monthly_kwh": e.get("FOUR_RM"),
            "source_key": "ema_2013",
            "note": "Historical whole-home average; not AC use or current demand",
        }
        reasons = []
        if name == "Others":
            reasons.append("Non-geographic aggregate category")
        reasons += [f"Missing {FEATURE_LABELS[key]}" for key, value in features.items() if value is None]
        areas.append({
            "name": name,
            "observation_year": 2020,
            "households": total,
            "housing_counts": housing,
            "household_size_counts": household_size_counts,
            "features": features,
            "cluster_eligible": not reasons,
            "cluster_exclusion_reasons": reasons,
            "electricity_context": electricity,
        })
    return {
        "unit": "planning area; every figure is an aggregate, never an individual household",
        "observation_year": 2020,
        "feature_labels": FEATURE_LABELS,
        "national_ac_ownership_2023_percent": ac_ownership,
        "areas": areas,
        "provenance_file": "data/sources.json",
    }


def main() -> None:
    result = build()
    path = DATA / "processed" / "areas.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    eligible = sum(area["cluster_eligible"] for area in result["areas"])
    print(f"Saved {len(result['areas'])} aggregate rows; {eligible} geographic areas eligible for clustering")


if __name__ == "__main__":
    main()
