"""All business thresholds, awards, penalties, and vocabulary come from JSON."""
from normalize import key, phrase
from chains import classify
from location_normalization import normalize_state

def evaluate(lead, cfg):
    w, p, t = cfg["weights"], cfg["penalties"], cfg["thresholds"]
    additions, flags, hard, review = [], [], [], []
    score = 0
    def add(rule, applies, points, detail):
        nonlocal score
        delta = points if applies else 0
        score += delta
        additions.append(f"{rule}: {delta:+g} ({detail})")
    def reject(rule, condition, reason):
        if condition and cfg["exclusions"][rule]:
            hard.append(reason)
    true = {key(v) for v in cfg["true_values"]}
    status = key(lead["status"])
    permanent = (key(lead["permanently_closed"]) in true or
                 status in {key(v) for v in cfg["status_values"]["permanently_closed"]})
    temporary = (key(lead["temporarily_closed"]) in true or
                 status in {key(v) for v in cfg["status_values"]["temporarily_closed"]})
    reject("permanently_closed", permanent, "PERMANENTLY_CLOSED")
    reject("temporarily_closed", temporary, "TEMPORARILY_CLOSED")
    matched = []

    normalized_state = normalize_state(lead.get("state"))

    for name, market in cfg["markets"].items():
        market_state = normalize_state(market.get("state"))

        if (
            market.get("enabled")
            and normalized_state == market_state
            and key(lead["city"]) in {key(c) for c in market.get("cities", [])}
        ):
            matched.append(name)

    area_known = bool(lead["city"] and lead["state"])
    in_area = bool(matched)
    lead["market"] = "; ".join(matched)
    if not area_known:
        review.append("UNKNOWN_SERVICE_AREA")
    add("active_area", in_area, w["active_area"], lead["city"] + ", " + lead["state"] if area_known else "city/state missing; ZIP alone does not qualify")
    add("outside_area", area_known and not in_area, p["outside_area"], "city/state outside active markets" if area_known and not in_area else "not applied")
    reject("outside_area", area_known and not in_area, "OUTSIDE_ACTIVE_SERVICE_AREA")
    visual = key(lead["visual"]) in true and bool(lead["visual_evidence"])
    primary = [c for c, terms in cfg["categories"]["primary"].items() if any(phrase(lead["category"], a) for a in terms)]
    secondary = [c for c, terms in cfg["categories"]["secondary"].items() if any(phrase(lead["category"], a) for a in terms)]
    excluded = [term for term in cfg["categories"]["excluded"] if phrase(lead["category"], term)]
    reject("excluded_category", bool(excluded), "EXCLUDED_CATEGORY: " + ", ".join(excluded))
    eligible_secondary = [c for c in secondary if c not in cfg["categories"]["secondary_requires_visual_evidence"] or visual]
    lead["category_tier"] = "primary" if primary else "secondary" if eligible_secondary else "unclassified"
    lead["normalized_category"] = "; ".join(primary or secondary) or "unclassified"
    add("primary_category", bool(primary), w["primary_category"], ", ".join(primary) or "no match")
    add("secondary_category", not primary and bool(eligible_secondary), w["secondary_category"], ", ".join(eligible_secondary) if not primary else "primary already awarded")
    if not primary and not eligible_secondary and not excluded:
        if cfg["categories"]["unknown_action"] == "review":
            review.append("CATEGORY_NEEDS_REVIEW")
        else:
            hard.append("UNCLASSIFIED_CATEGORY")
    independent = (any(phrase(lead["ownership"], v) for v in cfg["ownership"]["independent_values"]) and
                   (bool(lead["ownership_evidence"]) or not cfg["ownership"]["evidence_required"]))
    add("independent", independent, w["independent"], lead["ownership_evidence"] if independent else "no supported ownership signal")
    chain_reasons, platform_flags = classify(lead, cfg)
    flags.extend(platform_flags)
    lead["chain_evidence"] = "; ".join(chain_reasons)
    chain = bool(chain_reasons)
    if chain:
        flags.append("LIKELY_CHAIN")
        if not independent and cfg["chains"]["ambiguous_action"] == "review":
            review.append("LIKELY_CHAIN")
    penalize_chain = chain and not (independent and cfg["chains"]["independent_evidence_waives_penalty"])
    add("likely_chain", penalize_chain, p["likely_chain"], ", ".join(chain_reasons) if chain else "no configured chain match; this is not ownership evidence")
    for field in ("website", "social"):
        add(field, bool(lead[field]), w[field], "available" if lead[field] else "missing or unusable")
    contact = any(lead[f] for f in ("phone", "website", "social", "email", "other_contact"))
    lead["contact_paths"] = "; ".join(f for f in ("phone", "website", "social", "email", "other_contact") if lead[f])
    add("usable_contact", contact, w["usable_contact"], lead["contact_paths"] or "no usable contact path")
    add("no_contact", not contact, p["no_contact"], "no usable contact path" if not contact else "usable contact path exists")
    reject("no_contact", not contact, "NO_USABLE_CONTACT")
    add("rating", lead["rating"] is not None and lead["rating"] >= t["rating"], w["rating"], str(lead["rating"]) if lead["rating"] is not None else "missing or invalid")
    add("reviews", lead["reviews"] is not None and lead["reviews"] >= t["reviews"], w["reviews"], str(lead["reviews"]) if lead["reviews"] is not None else "missing or invalid")
    add("visual", visual, w["visual"], lead["visual_evidence"] if visual else "needs affirmative signal and evidence")
    add("named_contact", bool(lead["owner"]), w["named_contact"], lead["owner"] or "missing")
    if not lead["name"]:
        hard.append("MISSING_BUSINESS_NAME")
    final = max(0, min(100, score))
    if final != score:
        additions.append(f"Clamp to 0–100: {score:g} -> {final:g}")
    # Primary auto-qualification has evidence gates in addition to the score.
    # Low scores keep their existing review/hold routing.
    if primary and final >= t["qualified"]:
        gate = cfg["primary_qualification"]
        checks = [
            (gate["require_active_area"] and not in_area, "PRIMARY_SERVICE_AREA_UNCONFIRMED"),
            (gate["require_contact"] and not contact, "PRIMARY_NO_USABLE_CONTACT"),
            (gate["require_rating"] and (lead["rating"] is None or lead["rating"] < t["rating"]), "PRIMARY_RATING_REQUIREMENT_NOT_MET"),
            (gate["require_reviews"] and (lead["reviews"] is None or lead["reviews"] < t["reviews"]), "PRIMARY_REVIEW_COUNT_REQUIREMENT_NOT_MET"),
            (gate["block_closed"] and (permanent or temporary), "PRIMARY_BUSINESS_CLOSED"),
            (gate["block_excluded_category"] and bool(excluded), "PRIMARY_EXCLUDED_CATEGORY"),
        ]
        review.extend(reason for applies, reason in checks if applies)
    lead.update(score=final, raw_score=score,
                grade="A / Hot" if final >= t["hot"] else "B / Qualified" if final >= t["qualified"] else "C / Review" if final >= t["review"] else "Reject/Hold",
                score_explanation=" | ".join(additions), flags=flags,
                rejection_reasons=hard, review_reasons=review)
    return lead
