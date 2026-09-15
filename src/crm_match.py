"""Rule-strength matching, candidate indexing, and conservative classification."""
from collections import defaultdict
from difflib import SequenceMatcher
from urllib.parse import urlsplit
from crm_normalize import identity, is_shared_host

class CompanyIndex:
    def __init__(self, records, cfg):
        self.cfg = cfg
        self.companies = {r["id"]: identity(r["properties"], cfg, r["id"], r["archived"]) for r in records}
        self.domains, self.phones, self.addresses, self.names = (defaultdict(set) for _ in range(4))
        for cid, c in self.companies.items():
            for domain in c["domains"]:
                self.domains[domain].add(cid)
            if c["phone"]:
                self.phones[c["phone"]].add(cid)
            if c["street"] and c["city"]:
                self.addresses[(c["street"], c["city"], c["state"])].add(cid)
            if c["name_alias"]:
                self.names[c["name_alias"]].add(cid)

    def candidates(self, lead):
        ids = set()
        for domain in lead["domains"]:
            ids.update(self.domains.get(domain, ()))
        if lead["phone"]:
            ids.update(self.phones.get(lead["phone"], ()))
        ids.update(self.addresses.get((lead["street"], lead["city"], lead["state"]), ()))
        ids.update(self.names.get(lead["name_alias"], ()))
        # Scan distinct name keys, not a city-restricted subset: CRM locations may be stale.
        if lead["distinctive"]:
            cutoff = self.cfg["thresholds"]["name_similarity"]
            for name, candidates in self.names.items():
                matcher = SequenceMatcher(None, lead["name_alias"], name)
                if matcher.real_quick_ratio() >= cutoff and matcher.quick_ratio() >= cutoff and matcher.ratio() >= cutoff:
                    ids.update(candidates)
        return [self.companies[cid] for cid in sorted(ids)]

    def compare(self, lead, company):
        cfg, weights = self.cfg, self.cfg["confidence"]
        signals, conflicts, rules = [], [], []
        def signal(code, field, a, b):
            signals.append({"code": code, "field": field, "prospect": a, "hubspot": b})
        def rule(name, applies):
            if applies:
                rules.append((weights[name], name))
        exact_name = bool(lead["name_alias"] and lead["name_alias"] == company["name_alias"])
        ratio = SequenceMatcher(None, lead["name_alias"], company["name_alias"]).ratio() if lead["name_alias"] and company["name_alias"] else 0
        fuzzy = lead["distinctive"] and company["distinctive"] and ratio >= cfg["thresholds"]["name_similarity"]
        same_city = bool(lead["city"] and lead["state"] and lead["city"] == company["city"] and lead["state"] == company["state"])
        phone_match = bool(lead["phone"] and lead["phone"] == company["phone"])
        common = lead["domains"] & company["domains"]
        shared_domain = bool(common) and any(is_shared_host(d, cfg) or len(self.domains[d]) > 1 for d in common)
        shared_phone = phone_match and len(self.phones[lead["phone"]]) > 1
        own_domain = bool(common) and not shared_domain
        same_street = bool(lead["full_address"] and company["full_address"] and same_city and lead["street"] == company["street"])
        suite_conflict = bool(same_street and lead["suite"] and company["suite"] and lead["suite"] != company["suite"])
        suite_missing = bool(same_street and bool(lead["suite"]) != bool(company["suite"]))
        address_match = bool(same_street and lead["suite"] == company["suite"])
        location_conflict = bool(
            (lead["state"] and company["state"] and lead["state"] != company["state"]) or
            (lead["city"] and company["city"] and lead["city"] != company["city"]) or
            (lead["full_address"] and company["full_address"] and lead["street"] != company["street"]) or suite_conflict)
        country_conflict = bool(lead["country"] and company["country"] and lead["country"] != company["country"])
        if exact_name or fuzzy:
            signal("EXACT_NAME" if exact_name else "FUZZY_NAME", "name", lead["name_alias"], company["name_alias"])
        if common:
            signal("SHARED_DOMAIN" if shared_domain else "EXACT_BUSINESS_DOMAIN", "domain", sorted(lead["domains"]), sorted(company["domains"]))
        if phone_match:
            signal("SHARED_PHONE" if shared_phone else "EXACT_PHONE", "phone", lead["phone"], company["phone"])
        if same_city:
            signal("CITY_STATE_MATCH", "city_state", [lead["city"], lead["state"]], [company["city"], company["state"]])
        if same_street:
            signal("FULL_ADDRESS_MATCH" if address_match else "STREET_WITH_SUITE_UNCERTAINTY",
                   "address", [lead["street"], lead["suite"]], [company["street"], company["suite"]])
        common_urls = lead["urls"] & company["urls"]
        specific_url = any(urlsplit(u).path.strip("/") for u in common_urls)
        if specific_url:
            signal("SAME_URL_PATH", "website", sorted(common_urls), sorted(common_urls))
        if location_conflict or country_conflict:
            conflicts.append("POSSIBLE_RELATED_LOCATION" if (common or phone_match or exact_name) else "LOCATION_CONFLICT")
        if suite_missing:
            conflicts.append("SUITE_INFORMATION_INCOMPLETE")
        for domain in lead["platforms"].keys() & company["platforms"].keys():
            if lead["platforms"][domain] != company["platforms"][domain]:
                conflicts.append("PLATFORM_TENANT_OPERATOR_CONFLICT")
        if lead["phone"] and company["phone"] and not phone_match:
            signal("PHONE_DIFFERS", "phone", lead["phone"], company["phone"])
        if lead["domains"] and company["domains"] and not common:
            signal("DOMAIN_DIFFERS", "domain", sorted(lead["domains"]), sorted(company["domains"]))
        rule("name_address", exact_name and lead["distinctive"] and address_match)
        rule("domain_phone_name", own_domain and phone_match and not shared_phone and fuzzy)
        rule("domain_name_city", own_domain and exact_name and lead["distinctive"] and same_city)
        rule("fuzzy_phone_address", fuzzy and phone_match and address_match)
        rule("domain_only", own_domain)
        rule("name_city", exact_name and same_city)
        rule("phone_only", phone_match)
        rule("address_only", address_match)
        rule("fuzzy_only", fuzzy)
        # A platform domain alone is a relationship, not a credible tenant match.
        rule("shared_identifier", bool(common) and shared_domain and
             (not all(is_shared_host(d, cfg) and d in cfg["shared_domains"] for d in common) or
              fuzzy or phone_match or same_street or specific_url))
        strength, match_rule = max(rules, default=(0, "NO_CREDIBLE_MATCH"))
        return {"hubspot_id": company["id"], "hubspot_name": company["raw"].get("name", ""),
                "archived": company["archived"], "confidence": strength, "rule": match_rule,
                "name_similarity": round(ratio, 4), "evidence": signals,
                "conflicts": sorted(set(conflicts)), "hubspot_values": company["raw"]}

def classify(lead, index, cfg):
    candidates = sorted((index.compare(lead, c) for c in index.candidates(lead)),
                        key=lambda c: (-c["confidence"], c["hubspot_id"]))
    credible = [c for c in candidates if c["confidence"] >= cfg["thresholds"]["review"]]
    # Identity sufficiency excludes generic/shared homepages and generic business names.
    specific_platform_page = any(urlsplit(u).path.strip("/") and
        not any(urlsplit(u).path.startswith(prefix) for p in cfg["platforms"]
                for prefix in p["operator_path_prefixes"]) for u in lead["urls"])
    usable = bool(lead["phone"] or lead["full_address"] or
                  any(not is_shared_host(d, cfg) for d in lead["domains"]) or specific_platform_page)
    reasons = []
    if not lead["name_alias"] or not lead["distinctive"] or not usable:
        reasons.append("INSUFFICIENT_IDENTIFIERS")
    if any(c["archived"] for c in credible):
        reasons.append("ARCHIVED_MATCH")
    if credible:
        top = credible[0]
        reasons.extend(top["conflicts"])
        if len([c for c in credible if c["confidence"] >= cfg["thresholds"]["competing"]]) > 1:
            reasons.append("MULTIPLE_CREDIBLE_COMPANIES")
        if top["confidence"] < cfg["thresholds"]["existing"]:
            reasons.append("POSSIBLE_MATCH")
        status = "REVIEW" if reasons else "EXISTING"
    else:
        top = None
        status = "REVIEW" if reasons else "NEW"
    return {"crm_status": status, "match_confidence": top["confidence"] if top else 0,
            "matched_hubspot_id": top["hubspot_id"] if top and status == "EXISTING" else "",
            "candidate_hubspot_ids": "; ".join(c["hubspot_id"] for c in credible),
            "matched_company_name": top["hubspot_name"] if top and status == "EXISTING" else "",
            "match_rule": top["rule"] if top else "NO_CREDIBLE_MATCH",
            "review_reason_crm": "; ".join(dict.fromkeys(reasons)),
            "match_evidence": top["evidence"] if top else [],
            "conflicting_evidence": sorted({v for c in credible for v in c["conflicts"]}),
            "candidates": candidates}
