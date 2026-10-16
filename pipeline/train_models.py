"""Reproducible area clustering and explicitly synthetic lead-model training."""

from __future__ import annotations

import json
import math
import random
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, adjusted_rand_score, roc_auc_score, silhouette_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SEED = 42
FEATURE_KEYS = ["hdb_share", "large_hdb_share", "condo_share", "large_household_share", "high_income_share"]
HOUSING_NAMES = {
    "hdb_1_2": "HDB 1–2 room",
    "hdb_3": "HDB 3 room",
    "hdb_4": "HDB 4 room",
    "hdb_5_exec": "HDB 5 room/executive",
    "condo": "Condo/apartment",
    "landed": "Landed",
}


def weighted_choice(rng: random.Random, counts: dict) -> str:
    pairs = [(key, value) for key, value in counts.items() if value is not None and value > 0]
    return rng.choices([key for key, _ in pairs], weights=[value for _, value in pairs], k=1)[0]


def cluster_areas(areas: list[dict]) -> dict:
    eligible = [area for area in areas if area["cluster_eligible"]]
    x = np.array([[area["features"][key] for key in FEATURE_KEYS] for area in eligible], dtype=float)
    scaler = StandardScaler().fit(x)
    scaled = scaler.transform(x)
    candidates = []
    for k in range(2, 5):
        reference = KMeans(n_clusters=k, random_state=SEED, n_init=20).fit(scaled)
        reference_labels = reference.labels_
        stability = []
        for repeat in range(12):
            indices = np.random.default_rng(SEED + repeat).choice(len(x), size=round(len(x) * 0.8), replace=False)
            trial = KMeans(n_clusters=k, random_state=SEED + repeat, n_init=10).fit(scaled[indices])
            stability.append(adjusted_rand_score(reference_labels, trial.predict(scaled)))
        silhouette = float(silhouette_score(scaled, reference_labels))
        minimum_size = min(Counter(reference_labels).values())
        candidates.append({
            "k": k,
            "silhouette": round(silhouette, 3),
            "stability_ari": round(float(np.mean(stability)), 3),
            "minimum_cluster_size": int(minimum_size),
            "selection_score": round(silhouette + 0.35 * float(np.mean(stability)) - (0.25 if minimum_size < 3 else 0), 3),
        })
    chosen = max(candidates, key=lambda item: item["selection_score"])
    model = KMeans(n_clusters=chosen["k"], random_state=SEED, n_init=20).fit(scaled)
    labels = {}
    feature_names = json.loads((DATA / "processed" / "areas.json").read_text())["feature_labels"]
    for cluster_id, centroid in enumerate(model.cluster_centers_):
        top = np.argsort(np.abs(centroid))[::-1][:2]
        labels[str(cluster_id)] = "; ".join(
            f"{'Higher' if centroid[index] >= 0 else 'Lower'} {feature_names[FEATURE_KEYS[index]]}"
            for index in top
        )
    assignments = {
        area["name"]: {"cluster_id": int(cluster_id), "cluster_label": labels[str(cluster_id)]}
        for area, cluster_id in zip(eligible, model.labels_)
    }
    return {
        "unit": "planning areas, not households",
        "observation_year": 2020,
        "feature_keys": FEATURE_KEYS,
        "standardisation": "StandardScaler fitted on 28 eligible planning areas",
        "candidate_metrics": candidates,
        "chosen_k": chosen["k"],
        "cluster_labels": labels,
        "assignments": assignments,
        "excluded": {area["name"]: area["cluster_exclusion_reasons"] for area in areas if not area["cluster_eligible"]},
        "limitations": "Descriptive clusters of 2020 aggregate area profiles; no household-level AC, interest or commercial outcomes.",
    }


def generate_synthetic_leads(areas: list[dict], count: int = 1200) -> list[dict]:
    rng = random.Random(SEED)
    eligible = [area for area in areas if area["cluster_eligible"]]
    weights = [area["households"] for area in eligible]
    records = []
    while len(records) < count:
        area = rng.choices(eligible, weights=weights, k=1)[0]
        # National 2023 ownership prevalence is applied uniformly as a scenario assumption.
        if rng.random() >= 0.819:
            continue
        housing_key = weighted_choice(rng, area["housing_counts"])
        if housing_key == "other":
            continue
        household_size = weighted_choice(rng, area["household_size_counts"])
        min_units, max_units = {
            "hdb_1_2": (1, 2), "hdb_3": (1, 3), "hdb_4": (1, 4),
            "hdb_5_exec": (2, 5), "condo": (1, 5), "landed": (2, 6),
        }[housing_key]
        ac_units = rng.randint(min_units, max_units)
        daily_hours = round(rng.uniform(3, 12), 1)
        ac_type = rng.choices(["split", "multi_split", "window", "central"], weights=[0.62, 0.16, 0.14, 0.08])[0]
        # This is an invented response mechanism, not a Bizsu conversion rate.
        linear = -2.25 + 0.33 * ac_units + 0.10 * (daily_hours - 6)
        linear += 0.22 if ac_type in {"split", "multi_split"} else -0.25
        linear += rng.gauss(0, 0.65)
        simulated_chance = 1 / (1 + math.exp(-linear))
        outcome = int(rng.random() < simulated_chance)
        records.append({
            "area": area["name"], "property_type": HOUSING_NAMES[housing_key],
            "household_size": household_size, "ac_type": ac_type,
            "ac_units": ac_units, "daily_hours": daily_hours,
            "simulated_conversion": outcome,
            "data_kind": "synthetic enquiry and synthetic outcome",
        })
    return records


def train_conversion(records: list[dict]) -> tuple[Pipeline, dict]:
    feature_keys = ["property_type", "ac_type", "ac_units", "daily_hours"]
    x = [{key: row[key] for key in feature_keys} for row in records]
    y = [row["simulated_conversion"] for row in records]
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.25, stratify=y, random_state=SEED)
    model = Pipeline([("transform", DictVectorizer()), ("classifier", LogisticRegression(max_iter=1000))])
    model.fit(x_train, y_train)
    probabilities = model.predict_proba(x_test)[:, 1]
    metrics = {
        "training_rows": len(x_train), "held_out_rows": len(x_test),
        "synthetic_accuracy": round(float(accuracy_score(y_test, probabilities >= 0.5)), 3),
        "synthetic_roc_auc": round(float(roc_auc_score(y_test, probabilities)), 3),
        "synthetic_positive_rate": round(sum(y) / len(y), 3),
    }
    card = {
        "model": "Logistic regression, demonstration only",
        "version": "synthetic-v1-seed42",
        "feature_keys": feature_keys,
        "metrics": metrics,
        "assumptions": [
            "Area and dwelling-type frequencies come from aggregate Census 2020 counts.",
            "Household size is sampled separately within area; its joint distribution with dwelling type is unknown.",
            "The 81.9% national 2023 AC ownership figure is applied uniformly as a scenario assumption.",
            "AC unit ranges, type shares, daily usage and enquiry selection are simulated assumptions.",
            "Conversion outcomes come from an invented noisy formula using AC units, usage and type.",
            "Held-out metrics measure consistency with that invented formula, not real-world accuracy.",
        ],
        "warning": "Predictions are unvalidated synthetic demonstration scores, not purchase probabilities.",
    }
    return model, card


def main() -> None:
    areas = json.loads((DATA / "processed" / "areas.json").read_text())["areas"]
    clusters = cluster_areas(areas)
    (DATA / "processed" / "clusters.json").write_text(json.dumps(clusters, indent=2) + "\n")
    records = generate_synthetic_leads(areas)
    (DATA / "processed" / "synthetic_training.json").write_text(json.dumps(records, indent=2) + "\n")
    model, card = train_conversion(records)
    (DATA / "models").mkdir(exist_ok=True)
    joblib.dump(model, DATA / "models" / "conversion.joblib")
    vectorizer = model.named_steps["transform"]
    classifier = model.named_steps["classifier"]
    artifact = {
        "format": "dictvectorizer-logistic-regression-v1",
        "feature_names": vectorizer.get_feature_names_out().tolist(),
        "coefficients": classifier.coef_[0].tolist(),
        "intercept": float(classifier.intercept_[0]),
        "classes": classifier.classes_.tolist(),
    }
    (DATA / "models" / "conversion_model.json").write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n")
    (DATA / "models" / "conversion_card.json").write_text(json.dumps(card, indent=2) + "\n")
    print(f"K-Means chose k={clusters['chosen_k']}; candidate metrics: {clusters['candidate_metrics']}")
    print(f"Trained synthetic classifier: {card['metrics']}")


if __name__ == "__main__":
    main()
