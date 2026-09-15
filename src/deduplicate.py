"""V1.1 identity conflicts are separate from nonblocking relationships."""
import json
import re
from difflib import SequenceMatcher
from urllib.parse import urlsplit
from normalize import key

def address_parts(value, cfg):
    raw = value.casefold()
    suite_match = re.search(cfg["duplicates"]["suite_pattern"], raw)
    suite = key(suite_match.group(1)) if suite_match else ""
    base = raw[:suite_match.start()] if suite_match else raw
    # Remove venue prose preceding a street number; keep original address intact.
    number = re.search(r"\b\d+\b", base)
    base = key(base[number.start():]) if number else key(base)
    return base, suite

def compare(a, b, cfg):
    if a["place_id"] and a["place_id"] == b["place_id"]:
        return "exact", ["SAME_PLACE_ID"], []
    same_city = bool(a["city"] and a["state"] and key(a["city"]) == key(b["city"]) and a["state"] == b["state"])
    full_address = same_city and bool(a["address"]) and key(a["address"]) == key(b["address"])
    abase, asuite = address_parts(a["address"], cfg)
    bbase, bsuite = address_parts(b["address"], cfg)
    compatible_address = bool(same_city and abase and abase == bbase and not (asuite and bsuite and asuite != bsuite))
    distinct_location = bool(a["address"] and b["address"] and (
        (a["city"] and b["city"] and not same_city) or
        (same_city and (abase != bbase or (asuite and bsuite and asuite != bsuite)))))
    same_name = bool(a["name_key"]) and a["name_key"] == b["name_key"]
    similar = bool(a["name_key"] and b["name_key"] and
                   SequenceMatcher(None, a["name_key"], b["name_key"]).ratio() >= cfg["duplicates"]["fuzzy_name_ratio"])
    same_phone = bool(a["phone"]) and a["phone"].split(" ext ")[0] == b["phone"].split(" ext ")[0]
    same_domain = bool(a["domain"]) and a["domain"] == b["domain"]
    same_page = bool(same_domain and urlsplit(a["website"]).path.strip("/") and a["website"] == b["website"])
    different_ids = bool(a["place_id"] and b["place_id"] and a["place_id"] != b["place_id"])
    relationships = []
    if same_domain:
        relationships.append("SHARED_DOMAIN")
    if same_phone:
        relationships.append("SHARED_PHONE")
    if similar and distinct_location:
        relationships.append("POSSIBLE_MULTI_LOCATION")
    if same_name and full_address and not different_ids:
        return "exact", ["SAME_NORMALIZED_NAME", "SAME_FULL_ADDRESS_CITY_STATE"], relationships
    evidence = []
    if same_phone and full_address:
        evidence = ["SAME_PHONE", "SAME_FULL_ADDRESS_CITY_STATE"]
    elif similar and compatible_address:
        evidence = ["SIMILAR_NAME", "COMPATIBLE_STREET_ADDRESS_CITY_STATE"]
    elif similar and not distinct_location and (same_phone or (same_page and same_city)):
        evidence = ["SIMILAR_NAME"] + (["SAME_PHONE"] if same_phone else ["SAME_BUSINESS_URL", "SAME_CITY_STATE"])
    if evidence:
        if different_ids:
            evidence.append("DIFFERENT_PLACE_IDS_REQUIRES_REVIEW")
        return "uncertain", evidence, relationships
    return "", [], relationships

def counterpart(other, evidence):
    return {"lead_id": other["lead_id"], "name": other["name"],
            "place_id": other["place_id"], "address": other["address"],
            "city": other["city"], "website": other["website"],
            "source_file": other["source_file"], "source_row": other["source_row"],
            "evidence": evidence}

def annotate(leads, cfg):
    for lead in leads:
        lead["duplicate_matches"] = []
        lead["relationship_matches"] = []
        lead["duplicate_of"] = []
    ranked = sorted(leads, key=lambda x: (bool(x["rejection_reasons"]), bool(x["review_reasons"]), -x["score"], x["lead_id"]))
    previous = []
    for lead in ranked:
        matches = [(other, *compare(lead, other, cfg)) for other in previous]
        exact = [(other, evidence) for other, kind, evidence, _ in matches if kind == "exact"]
        for other, kind, evidence, relations in matches:
            if relations:
                for a, b in ((lead, other), (other, lead)):
                    a["relationship_matches"].append(counterpart(b, relations))
                    a["flags"].extend(relations)
            if kind == "exact" or (kind == "uncertain" and not exact):
                for a, b in ((lead, other), (other, lead)):
                    a["duplicate_matches"].append({"kind": kind, **counterpart(b, evidence)})
                if kind == "uncertain":
                    for a, b in ((lead, other), (other, lead)):
                        a["review_reasons"].append("UNCERTAIN_DUPLICATE")
                        a["duplicate_of"].append(b["lead_id"])
        if exact:
            lead["rejection_reasons"].append("EXACT_DUPLICATE")
            lead["duplicate_of"].extend(other["lead_id"] for other, _ in exact)
        else:
            previous.append(lead)
    for lead in leads:
        lead["duplicate_of"] = "; ".join(dict.fromkeys(lead["duplicate_of"]))
        for field in ("duplicate_matches", "relationship_matches"):
            lead[field] = json.dumps(lead[field], ensure_ascii=False)
