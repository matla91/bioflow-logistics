"""Small, fail-closed helpers for bounded public observation downloads."""

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from ..interfaces import ObservationSource

BASEL_API = "https://data.bs.ch/api/explore/v2.1/catalog/datasets"
PAGE_SIZE = 100
ODS_RECORD_LIMIT = 10000


class IngestionError(ValueError):
    """A download or provider record is incomplete, unavailable or invalid."""


def timestamp(value: Any, field: str) -> datetime:
    """Parse an explicit provider offset and keep one UTC time basis."""
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise IngestionError(f"Invalid {field} timestamp: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise IngestionError(f"{field} timestamp needs an explicit UTC offset")
    return parsed.astimezone(timezone.utc)


def window(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    start, end = timestamp(start, "start"), timestamp(end, "end")
    if end <= start:
        raise IngestionError("Download end must be later than start")
    return start, end


def number(value: Any, field: str, *, optional: bool = False) -> float | None:
    if isinstance(value, str):
        value = value.strip()
    if value is None or value == "":
        if optional:
            return None
        raise IngestionError(f"Missing {field}")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise IngestionError(f"Invalid numeric {field}: {value!r}") from exc
    if isinstance(value, bool) or not math.isfinite(parsed):
        raise IngestionError(f"{field} must be a finite number")
    return parsed


def get(client: httpx.Client, url: str, params: dict | None = None) -> httpx.Response:
    try:
        response = client.get(url, params=params)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise IngestionError(f"Observation download failed for {url}: {exc}") from exc
    return response


def basel_records(
    dataset: str,
    where: str,
    order_by: str,
    *,
    client: httpx.Client | None = None,
) -> tuple[list[dict], str]:
    """Read every page in a bounded query, or return no partial result.

    Explore API queries are limited to 10,000 records. Larger requests fail with
    an instruction to narrow the window rather than quietly truncating history.
    A caller-supplied client remains open, allowing MockTransport in tests.
    """
    if client is None:
        with httpx.Client(timeout=30) as owned_client:
            return basel_records(dataset, where, order_by, client=owned_client)
    url = f"{BASEL_API}/{dataset}/records"
    params = {"where": where, "order_by": order_by, "limit": PAGE_SIZE, "offset": 0}
    source_url = f"{url}?{urlencode(params)}"
    rows: list[dict] = []
    expected_count: int | None = None
    seen_pages: set[str] = set()
    while True:
        response = get(client, url, params)
        try:
            payload = response.json()
            count, page = payload["total_count"], payload["results"]
        except (ValueError, TypeError, KeyError) as exc:
            raise IngestionError("Invalid Basel API records response") from exc
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise IngestionError("Basel API returned an invalid total_count")
        if not isinstance(page, list) or not all(isinstance(row, dict) for row in page):
            raise IngestionError("Basel API results must be a list of records")
        page_signature = hashlib.sha256(
            json.dumps(page, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if page and page_signature in seen_pages:
            raise IngestionError(
                "Basel API repeated an earlier page; history is incomplete"
            )
        seen_pages.add(page_signature)
        if count > ODS_RECORD_LIMIT:
            raise IngestionError(
                "Basel API query exceeds 10,000 records; narrow the date window "
                "or station selection"
            )
        if expected_count is None:
            expected_count = count
        elif count != expected_count:
            raise IngestionError(
                "Basel dataset changed during pagination; retry download"
            )
        if len(page) > PAGE_SIZE or len(rows) + len(page) > count:
            raise IngestionError("Basel API page exceeds its advertised record count")
        if not page and len(rows) < count:
            raise IngestionError("Basel API returned an incomplete page sequence")
        rows.extend(page)
        if len(rows) == count:
            return rows, source_url
        params["offset"] = len(rows)


def provenance(
    provider: str, dataset: str, url: str, licence: str, content: bytes | list[dict]
) -> ObservationSource:
    """Hash CSV bytes, or canonical raw records combined across API pages."""
    if isinstance(content, list):
        content = json.dumps(
            content, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
    return ObservationSource(
        provider=provider,
        dataset=dataset,
        url=url,
        retrieved_at=datetime.now(timezone.utc),
        licence=licence,
        sha256=hashlib.sha256(content).hexdigest(),
    )
