"""Failure-tolerant access to the optional synthetic conversion model."""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LOGGER = logging.getLogger(__name__)
UNAVAILABLE_MESSAGE = "Synthetic scoring is unavailable. Rule-based screening was still completed."


class LinearModel:
    """Evaluate the exported DictVectorizer + logistic regression model in pure Python."""

    def __init__(self, artifact: dict):
        if artifact.get("format") != "dictvectorizer-logistic-regression-v1" or artifact.get("classes") != [0, 1]:
            raise ValueError("Unsupported conversion model format")
        names = artifact.get("feature_names")
        weights = artifact.get("coefficients")
        if not isinstance(names, list) or not isinstance(weights, list) or len(names) != len(weights) or not names:
            raise ValueError("Invalid conversion model coefficients")
        self.terms = [(name.split("=", 1), float(weight)) for name, weight in zip(names, weights)]
        self.intercept = float(artifact["intercept"])
        if not math.isfinite(self.intercept) or any(not math.isfinite(weight) for _, weight in self.terms):
            raise ValueError("Conversion model contains non-finite coefficients")

    def predict_proba(self, records: list[dict]) -> list[list[float]]:
        output = []
        for record in records:
            linear = self.intercept
            for parts, weight in self.terms:
                if len(parts) == 2:
                    linear += weight * (record.get(parts[0]) == parts[1])
                else:
                    linear += weight * float(record.get(parts[0], 0))
            if linear >= 0:
                probability = 1 / (1 + math.exp(-linear))
            else:
                exponent = math.exp(linear)
                probability = exponent / (1 + exponent)
            output.append([1 - probability, probability])
        return output


class ConversionScorer:
    """Load and call the demo model without making it a runtime requirement."""

    def __init__(self, model_path: Path | None = None, card_path: Path | None = None):
        model_dir = ROOT / "data" / "models"
        self.model_path = Path(model_path or model_dir / "conversion_model.json")
        self.card_path = Path(card_path or model_dir / "conversion_card.json")
        self.model = None
        self.model_card: dict = {}
        self.available = False
        self.unavailable_reason: str | None = "Synthetic scoring model is unavailable."
        self._load()

    def _load(self) -> None:
        try:
            card = json.loads(self.card_path.read_text())
            feature_keys = card.get("feature_keys")
            if not isinstance(feature_keys, list) or not feature_keys or not all(isinstance(key, str) for key in feature_keys):
                raise ValueError("Model card has no valid feature list")
            model = LinearModel(json.loads(self.model_path.read_text()))
        except Exception as error:
            LOGGER.warning("Synthetic conversion scoring disabled (%s)", type(error).__name__)
            return
        self.model_card = card
        self.model = model
        self.available = True
        self.unavailable_reason = None

    @property
    def model_version(self) -> str | None:
        return self.model_card.get("version") if self.available else None

    def score(self, lead: dict) -> float | None:
        if not self.available or self.model is None:
            return None
        try:
            prediction = {key: lead[key] for key in self.model_card["feature_keys"]}
            return round(float(self.model.predict_proba([prediction])[0][1]) * 100, 1)
        except Exception as error:
            LOGGER.warning("Synthetic conversion prediction skipped (%s)", type(error).__name__)
            return None

    def warning(self, score: float | None) -> str:
        if score is None:
            return UNAVAILABLE_MESSAGE
        return self.model_card.get(
            "warning",
            "Predictions are unvalidated synthetic demonstration scores, not purchase probabilities.",
        )

    def metadata(self) -> dict:
        if not self.available:
            return {
                "available": False,
                "version": None,
                "unavailable_reason": self.unavailable_reason,
            }
        return {
            **self.model_card,
            "available": True,
            "unavailable_reason": None,
        }
