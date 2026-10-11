"""Refresh frozen public-data snapshots. The demo itself never calls an external API."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MANIFEST = DATA / "sources.json"


def get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Bizsu student demo data research/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def save_snapshot(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    contents = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(contents)
    return hashlib.sha256(contents.encode()).hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for source in manifest["sources"]:
        dataset_id = source["dataset_id"]
        if source["key"] == "ema_2013":
            endpoint = f"https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"
            signed_url = get_json(endpoint)["data"]["url"]
            # curl succeeds with the signed public blob URL where urllib is sometimes rejected.
            result = subprocess.run(["curl", "-fLsS", signed_url], capture_output=True, check=True)
            geojson = json.loads(result.stdout)
            payload = {
                "observation_year": 2013,
                "unit": "average monthly household kWh, not AC-specific",
                "areas": [feature["properties"] for feature in geojson["features"]],
            }
        else:
            endpoint = f"https://data.gov.sg/api/action/datastore_search?resource_id={dataset_id}&limit=10000"
            response = get_json(endpoint)
            if not response.get("success"):
                raise RuntimeError(f"Dataset request failed: {dataset_id}")
            result = response["result"]
            if len(result["records"]) != result["total"]:
                raise RuntimeError(f"Incomplete dataset: {dataset_id}")
            payload = {"fields": result["fields"], "records": result["records"], "total": result["total"]}
            time.sleep(2.7)  # Respect public unauthenticated rate limits.
        source["retrieved_at_utc"] = retrieved_at
        source["sha256"] = save_snapshot(DATA / source["file"], payload)
        print(f"Saved {source['key']}: {source['file']}")
    manifest["retrieved_at_utc"] = retrieved_at
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
