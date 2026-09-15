"""Matching-only normalization; never modify V1.1 fields."""
import re
from urllib.parse import urlsplit
from normalize import key, phone, url, host_matches

def unprotect(value):
    value = str(value or "").strip()
    return value[1:] if value.startswith(("'+", "'=", "'-", "'@")) else value

def identity(data, cfg, record_id="", archived=False):
    ncfg = cfg["normalization"]
    name = key(data.get("name", ""))
    alias = name
    for suffix in sorted(ncfg["legal_suffixes"], key=len, reverse=True):
        if alias.endswith(" " + suffix):
            alias = alias[:-(len(suffix) + 1)]
    state = str(data.get("state") or "").strip()
    state = ncfg["state_aliases"].get(key(state), state.upper())
    raw_address = " ".join(str(data.get(f) or "").strip() for f in ("address", "address2")).strip()
    suite_match = re.search(ncfg["suite_pattern"], raw_address.casefold())
    suite = key(suite_match.group(1)) if suite_match else ""
    street = raw_address[:suite_match.start()] if suite_match else raw_address
    # Venue prose is secondary to street identity; raw data is retained below.
    number = re.search(r"\b\d+\b", street)
    street = street[number.start():] if number else street
    street = " ".join(ncfg["street_aliases"].get(t, t) for t in key(street).split())
    city = key(data.get("city", ""))
    domains, urls = set(), set()
    for field in ("domain", "hs_additional_domains", "website", "social", "other_contact"):
        for value in str(data.get(field) or "").split(";"):
            normalized = url(unprotect(value))
            if normalized:
                parsed = urlsplit(normalized)
                host = parsed.hostname or ""
                domains.add(host)
                # Fold known corporate subdomains, never arbitrary tenant subdomains.
                for brand in cfg["brand_domains"]:
                    if host_matches(host, [brand]):
                        domains.add(brand)
                urls.add(normalized)
    platforms = []
    for p in cfg["platforms"]:
        if any(host_matches(d, [p["domain"]]) for d in domains):
            operator = any(re.search(pattern, name) for pattern in p["operator_name_patterns"])
            platforms.append((p["domain"], "operator" if operator else "tenant"))
    return {"id": record_id, "archived": archived, "name": name, "name_alias": alias,
            "distinctive": bool(set(alias.split()) - set(ncfg["generic_name_tokens"])),
            "phone": phone(unprotect(data.get("phone", ""))).split(" ext ")[0],
            "domains": domains, "urls": urls, "street": street, "suite": suite,
            "city": city, "state": state, "country": ncfg["country_aliases"].get(key(data.get("country", "")), key(data.get("country", ""))),
            "full_address": bool(number and street and city and state),
            "platforms": dict(platforms), "raw": dict(data)}

def is_shared_host(domain, cfg):
    return host_matches(domain, cfg["shared_domains"] + cfg["brand_domains"])
