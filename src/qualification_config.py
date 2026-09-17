"""Resolve scoring configuration for a campaign or runtime location."""

import copy
import json
from pathlib import Path

from location_normalization import normalize_state


def load(root, campaign, city=None, state=None):
    root = Path(root)

    profile = json.loads(
        (root / "config" / "ideal_client_profile.json")
        .read_text(encoding="utf-8")
    )

    cfg = copy.deepcopy(profile)

    city = str(city or "").strip()
    state = str(state or "").strip()

    # --------------------------------------------------------
    # Runtime Lead Generator market
    # --------------------------------------------------------
    if city or state:
        if not city or not state:
            raise ValueError(
                "Both city and state are required for a custom lead-generation market"
            )

        cfg["markets"] = {
            "runtime": {
                "enabled": True,
                "state": normalize_state(state),
                "cities": [city],
                "supporting_zip_codes": [],
            }
        }

        return cfg

    # --------------------------------------------------------
    # Existing campaign-configured market
    # --------------------------------------------------------
    campaign_path = (
        root
        / "config"
        / "campaigns"
        / f"{campaign}.json"
    )

    if not campaign_path.exists():
        raise FileNotFoundError(
            f"Unknown campaign configuration: {campaign}"
        )

    campaign_cfg = json.loads(
        campaign_path.read_text(encoding="utf-8")
    )

    market_cfg = campaign_cfg.get("market") or {}
    active_market = market_cfg.get("active")

    if not active_market:
        raise ValueError(
            f"Campaign {campaign} has no active market"
        )

    if active_market not in cfg.get("markets", {}):
        raise ValueError(
            f"Campaign {campaign} references unknown market: {active_market}"
        )

    for market_name, market in cfg["markets"].items():
        market["enabled"] = market_name == active_market

    return cfg
