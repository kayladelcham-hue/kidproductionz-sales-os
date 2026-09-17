from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


OUTSCRAPER_URL = "https://api.outscraper.cloud/google-maps-search"


def _flatten_places(payload: Any) -> list[dict]:
    """
    Outscraper may return:
      - [ [place, place, ...] ]
      - [place, place, ...]
      - {"data": [...]}
    Normalize all of those into one flat list.
    """

    if isinstance(payload, dict):
        payload = payload.get("data", payload.get("results", []))

    if not isinstance(payload, list):
        return []

    flattened: list[dict] = []

    for item in payload:
        if isinstance(item, list):
            for child in item:
                if isinstance(child, dict):
                    flattened.append(child)

        elif isinstance(item, dict):
            flattened.append(item)

    return flattened


def _first(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, list):
        for item in value:
            if item:
                return str(item).strip()
        return ""

    return str(value).strip()


def normalize_place(place: dict, fallback_category: str = "") -> dict:
    """
    Map Outscraper Google Maps fields into fields already understood
    by the KidProductionz qualification pipeline.
    """

    website = _first(
        place.get("site")
        or place.get("website")
        or place.get("domain")
    )

    phone = _first(
        place.get("phone")
        or place.get("phone_number")
    )

    category = _first(
        place.get("category")
        or place.get("type")
        or place.get("subtypes")
        or fallback_category
    )

    city = _first(
        place.get("city")
        or place.get("borough")
    )

    state = _first(
        place.get("state")
        or place.get("state_code")
    )

    address = _first(
        place.get("full_address")
        or place.get("address")
    )

    return {
        "name": _first(
            place.get("name")
            or place.get("title")
            or place.get("business_name")
        ),
        "business": _first(
            place.get("name")
            or place.get("title")
            or place.get("business_name")
        ),
        "category": category,
        "city": city,
        "state": state,
        "address": address,
        "zip": _first(
            place.get("postal_code")
            or place.get("zip")
        ),
        "phone": phone,
        "website": website,
        "domain": website,
        "email": _first(
            place.get("email")
            or place.get("emails")
        ),
        "instagram": _first(
            place.get("instagram")
            or place.get("social")
        ),
        "social": _first(
            place.get("instagram")
            or place.get("social")
        ),
        "rating": place.get("rating"),
        "reviews": (
            place.get("reviews")
            if place.get("reviews") is not None
            else place.get("reviews_count")
        ),
        "place_id": _first(place.get("place_id")),
        "google_id": _first(
            place.get("google_id")
            or place.get("google_mid")
        ),
        "latitude": place.get("latitude"),
        "longitude": place.get("longitude"),
        "source": "OUTSCRAPER_GOOGLE_MAPS",
    }


def search_google_maps(
    query: str,
    limit: int = 10,
    category: str = "",
) -> dict:

    api_key = os.getenv("OUTSCRAPER_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError("OUTSCRAPER_API_KEY_NOT_CONFIGURED")

    query = str(query or "").strip()

    if not query:
        raise ValueError("OUTSCRAPER_QUERY_REQUIRED")

    limit = max(1, min(int(limit or 10), 500))

    params = urlencode({
        "query": query,
        "limit": limit,
        "async": "false",
    })

    request = Request(
        f"{OUTSCRAPER_URL}?{params}",
        headers={
            "X-API-KEY": api_key,
            "Accept": "application/json",
            "User-Agent": "KidProductionz-Sales-OS/1.0",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=90) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw)

    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"OUTSCRAPER_HTTP_{exc.code}: {detail[:300]}"
        ) from exc

    except URLError as exc:
        raise RuntimeError(
            f"OUTSCRAPER_CONNECTION_ERROR: {exc.reason}"
        ) from exc

    except TimeoutError as exc:
        raise RuntimeError("OUTSCRAPER_TIMEOUT") from exc

    places = _flatten_places(payload)

    normalized = [
        normalize_place(place, fallback_category=category)
        for place in places
    ]

    # Drop rows with no usable business identity.
    normalized = [
        row for row in normalized
        if row.get("name")
    ]

    # Local dedupe before anything reaches qualification.
    seen: set[str] = set()
    unique: list[dict] = []

    for row in normalized:
        key = (
            row.get("place_id")
            or row.get("google_id")
            or "|".join([
                str(row.get("name") or "").casefold(),
                str(row.get("address") or "").casefold(),
                str(row.get("phone") or "").casefold(),
            ])
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(row)

    return {
        "query": query,
        "requested_limit": limit,
        "received_count": len(places),
        "normalized_count": len(normalized),
        "unique_count": len(unique),
        "duplicates_removed": len(normalized) - len(unique),
        "leads": unique,
    }
