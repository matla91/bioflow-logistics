import json

import httpx

from baselhack.storage import ROOT


def fetch(url, filename):
    response = httpx.get(url, timeout=60, follow_redirects=True)
    response.raise_for_status()
    target = ROOT / "data" / "raw" / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(response.content)
    return response


def cache(name, payload):
    target = ROOT / "data" / "cache" / name
    target.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    )
