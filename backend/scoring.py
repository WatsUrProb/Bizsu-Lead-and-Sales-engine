"""Failure-tolerant access to the optional synthetic conversion model."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parents[1]

LOGGER = logging.getLogger(__name__)
UNAVAILABLE_MESSAGE = "Synthetic scoring is unavailable. Rule-based screening was still completed."


class ConversionScorer:
    """Load and call the demo model without making it a runtime requirement."""

    def __init__(self, model_path: Path | None = None, card_path: Path | None = None):
        model_dir = ROOT / "data" / "models"
        self.model_path = Path(model_path or model_dir / "conversion.joblib")
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
            model = joblib.load(self.model_path)
            if not callable(getattr(model, "predict_proba", None)):
                raise TypeError("Model does not provide predict_proba")
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
            return round(float(self.model.predict_proba([prediction])[0, 1]) * 100, 1)
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
