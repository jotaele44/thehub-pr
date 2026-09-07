#!/usr/bin/env python3
"""Certify the same-origin GIS proxy against the live PR WFS source.

The upstream URL is fixed here and must also be allowed by server/backend/gis_proxy.py.
This proves the mounted FastAPI route, allowlist, HTTP upstream bridge, and exact
78-feature WFS manifestation as one bounded runtime path.
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SOURCE_ID = "pr-geodata-municipios-2015"
UPSTREAM = (
    "http://geoserver2.pr.gov/geoserver/pr_geodata/ows?"
    + urllib.parse.urlencode(
        {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": "pr_geodata:g03_legales_municipios_2015",
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
        }
    )
)


def main() -> int:
    url = "http://127.0.0.1:8000/api/gis/proxy?" + urllib.parse.urlencode(
        {"source_id": SOURCE_ID, "target": UPSTREAM}
    )
    try:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            headers = dict(response.headers.items())
        payload = json.loads(raw)
        features = payload.get("features")
        if payload.get("type") != "FeatureCollection" or not isinstance(features, list):
            raise AssertionError("proxy response is not a GeoJSON FeatureCollection")
        if len(features) != 78:
            raise AssertionError(f"proxy WFS denominator expected 78, observed {len(features)}")
        if headers.get("X-GIS-Source-Id") != SOURCE_ID:
            raise AssertionError("proxy source-id response binding missing")
        receipt = {
            "status": "PASS",
            "source_id": SOURCE_ID,
            "upstream": UPSTREAM,
            "count": 78,
            "snapshot_sha256": hashlib.sha256(raw).hexdigest(),
            "transport": headers.get("X-GIS-Transport"),
            "retrieval_utc": datetime.now(timezone.utc).isoformat(),
            "identity_policy": "CANDIDATE_NOT_IDENTITY",
        }
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "source_id": SOURCE_ID,
                    "error": f"{type(exc).__name__}: {exc}",
                    "retrieval_utc": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
