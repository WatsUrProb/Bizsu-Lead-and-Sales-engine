"""Vercel's FastAPI function entrypoint."""

import os

os.environ["BIZSU_SERVERLESS"] = "1"

from backend.main import app

__all__ = ["app"]
