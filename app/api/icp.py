"""User-owned Ideal Customer Profiles and explainable lead qualification."""
from __future__ import annotations

import re
from typing import Any

DEFAULT_WEIGHTS = {"fit": 30, "need": 20, "authority": 15, "value": 15, "friction": 10, "timing": 10}
STATE_NAMES = dict(zip("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split(), "Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming|District of Columbia".split("|")))

EMPTY_PROFILE = {
    "offer": "", "typical_buyer": "", "market_type": "B2B", "offer_value_min": 0,
    "offer_value_max": 0, "offer_model": "project-based", "target_industries": [],
    "business_types": [], "company_size": "", "locations_min": 1, "locations_max": 5,
    "geography": [], "revenue_range": "", "ownership_preferences": [], "growth_stages": [],
    "buyer_roles": [], "problems_solved": [], "need_signals": [], "urgency_signals": [],
    "minimum_budget": 0, "ideal_customer_value": 0, "accepts_trade": False,
    "excluded_industries": [], "excluded_company_sizes": [], "excluded_geographies": [],
    "red_flags": [], "positive_signals": [], "preferred_opportunity_type": "",
}

def normalize_profile(value: dict[str, Any] | None) -> dict[str, Any]:
    profile = dict(EMPTY_PROFILE)
    for key, default in EMPTY_PROFILE.items():
        incoming = (value or {}).get(key, default)
        if isinstance(default, list):
            if isinstance(incoming, str):
                incoming = [x.strip() for x in incoming.split(",") if x.strip()]
            incoming = [str(x).strip() for x in (incoming or []) if str(x).strip()]
        profile[key] = incoming
    return profile

def validate_weights(value: dict[str, Any] | None) -> dict[str, float]:
    weights = {key: float((value or {}).get(key, amount)) for key, amount in DEFAULT_WEIGHTS.items()}
    if any(amount < 0 for amount in weights.values()) or not sum(weights.values()):
        raise ValueError("ICP weights must be non-negative and total more than zero")
    total = sum(weights.values())
    return {key: round(amount * 100 / total, 4) for key, amount in weights.items()}

def profile_complete(profile: dict[str, Any]) -> bool:
    return bool(profile.get("offer") and (profile.get("target_industries") or profile.get("business_types")) and profile.get("geography") and profile.get("buyer_roles") and profile.get("problems_solved"))

def _text(*values: Any) -> str:
    return " ".join(str(v or "") for v in values).casefold()

def _matches(text: str, values: list[str]) -> list[str]:
    normalized_text = re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()
    return [value for value in values if re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip() in normalized_text]

def _geography_matches(lead: dict[str, Any], values: list[str]) -> list[str]:
    city=str(lead.get("city") or "").casefold().strip(); state=str(lead.get("state") or "").upper().strip()
    state_name=STATE_NAMES.get(state,"").casefold()
    matched=[]
    for value in values:
        normalized=re.sub(r"[^a-z0-9]+"," ",value.casefold()).strip()
        if (city and city in normalized) or (state and re.search(rf"\b{re.escape(state.casefold())}\b",normalized)) or (state_name and state_name in normalized):matched.append(value)
    return matched

def _priority(score: float, disqualified: bool) -> str:
    if disqualified or score < 50:return "LOW_PRIORITY"
    if score < 65:return "REVIEW"
    if score < 80:return "GOOD_FIT"
    return "HIGH_PRIORITY"

def score_lead(lead: dict[str, Any], profile: dict[str, Any], weights: dict[str, float] | None = None) -> dict[str, Any]:
    profile = normalize_profile(profile); weights = validate_weights(weights)
    company_text = _text(lead.get("category"), lead.get("normalized_category"), lead.get("name"), lead.get("business"))
    evidence_text = _text(lead.get("description"), lead.get("research"), lead.get("visual_evidence"), lead.get("ownership_evidence"), lead.get("category"), lead.get("name"))
    location_text = _text(lead.get("city"), lead.get("state"), lead.get("address"))
    contact = bool(lead.get("phone") or lead.get("email") or lead.get("website") or lead.get("social"))
    named = bool(lead.get("owner") or lead.get("decision_maker") or lead.get("contact_name"))
    industry_matches = _matches(company_text, profile["target_industries"] + profile["business_types"])
    geography_matches = _geography_matches(lead, profile["geography"])
    positive_matches = _matches(evidence_text, profile["positive_signals"] + profile["need_signals"] + profile["urgency_signals"])
    excluded_industry = _matches(company_text, profile["excluded_industries"])
    excluded_geography = _geography_matches(lead, profile["excluded_geographies"])
    outside_geo = bool(profile["geography"] and location_text.strip() and not geography_matches)
    disqualifiers = []
    if excluded_industry: disqualifiers.append("Excluded industry: " + ", ".join(excluded_industry))
    if excluded_geography: disqualifiers.append("Excluded geography: " + ", ".join(excluded_geography))
    if outside_geo: disqualifiers.append("Outside the service geography in your ICP")
    closed = str(lead.get("status") or "").casefold() in {"closed", "permanently_closed"} or bool(lead.get("permanently_closed"))
    if closed: disqualifiers.append("Business appears permanently closed")

    dimensions = {
        "fit": (0.45 if industry_matches else 0.1) + (0.35 if geography_matches else 0) + (0.2 if profile["ownership_preferences"] and _matches(evidence_text, profile["ownership_preferences"]) else 0),
        "need": min(1.0, 0.45 + 0.3 * len(positive_matches)) if profile["problems_solved"] else 0.25,
        "authority": 1.0 if named else 0.65 if contact else 0.15,
        "value": 0.8 if (profile.get("ideal_customer_value") or profile.get("offer_value_max")) else 0.55,
        "friction": 0.8 if contact and not disqualifiers else 0.25 if disqualifiers else 0.5,
        "timing": min(1.0, 0.3 + 0.35 * len(positive_matches)),
    }
    score = round(sum(weights[key] * max(0, min(1, dimensions[key])) for key in weights))
    if disqualifiers: score = min(score, 49)
    matches = []
    if industry_matches: matches.append("Matches target industry: " + ", ".join(industry_matches))
    if geography_matches: matches.append("Within target geography: " + ", ".join(geography_matches))
    if contact: matches.append("Has a reachable contact path")
    if named: matches.append("Decision-maker information is available")
    signals = [f"Detected signal: {value}" for value in positive_matches]
    missing = []
    if not industry_matches: missing.append("Target industry match is not confirmed")
    if not location_text.strip(): missing.append("Location is missing")
    if not named: missing.append("Decision-maker is not identified")
    if not positive_matches: missing.append("No current buying or urgency signal is confirmed")
    risks = list(disqualifiers)
    if not contact: risks.append("No usable contact path")
    action = "Skip or verify the disqualifier before spending time on outreach." if disqualifiers else ("Contact the likely decision-maker and lead with " + (profile["problems_solved"][0] if profile["problems_solved"] else "the clearest problem your offer solves") + ".")
    return {"score": score, "priority": _priority(score, bool(disqualifiers)), "dimensions": {k: round(v * weights[k]) for k, v in dimensions.items()}, "matches": matches, "signals": signals, "missing_information": missing, "risks": risks, "disqualifiers": disqualifiers, "recommended_action": action}

def discovery_defaults(profile: dict[str, Any]) -> dict[str, Any]:
    profile = normalize_profile(profile)
    place = profile["geography"][0] if profile["geography"] else ""
    state_match = re.search(r"\b([A-Z]{2})\b", place.upper())
    city = place.split(",", 1)[0].strip() if "," in place else ""
    return {"business_types": profile["business_types"] or profile["target_industries"], "geography": profile["geography"], "suggested_business_type": (profile["business_types"] or profile["target_industries"] or [""])[0], "suggested_city": city, "suggested_state": state_match.group(1) if state_match else ""}
