"""Resolve the global ICP into a campaign-aware scoring configuration."""
import copy
import json
from pathlib import Path


def load(root, campaign):
    root = Path(root)

    profile = json.loads(
        (root / "config" / "ideal_client_profile.json")
        .read_text(encoding="utf-8")
    )

    cfg = copy.deepcopy(profile)

    campaign_path = root / "config" / "campaigns" / f"{campaign}.json"

    if not campaign_path.exists():
        raise FileNotFoundError(f"Unknown campaign configuration: {campaign}")

    campaign_cfg = json.loads(
        campaign_path.read_text(encoding="utf-8")
    )

    market_cfg = campaign_cfg.get("market") or {}
    active_market = market_cfg.get("active")

    if not active_market:
        raise ValueError(f"Campaign {campaign} has no active market")

    if active_market not in cfg.get("markets", {}):
        raise ValueError(
            f"Campaign {campaign} references unknown market: {active_market}"
        )

    # Exactly one campaign market is active during qualification.
    for market_name, market in cfg["markets"].items():
        market["enabled"] = market_name == active_market

    return cfg
