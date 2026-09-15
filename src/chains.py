"""Config-driven brand detection with shared-platform tenant separation."""
import re
from urllib.parse import unquote, urlsplit
from normalize import key, phrase, host_matches

def classify(lead, cfg):
    reasons = [f"brand name: {n}" for n in cfg["chains"]["names"] if phrase(lead["name"], n)]
    if lead["domain"] and host_matches(lead["domain"], cfg["chains"]["domains"]):
        reasons.append(f"brand domain: {lead['domain']}")
    flags = []
    for platform in cfg["chains"]["shared_platforms"]:
        on_platform = host_matches(lead["domain"], platform["domains"])
        named_platform = any(phrase(lead["name"], n) for n in platform["names"])
        if not (on_platform or named_platform):
            continue
        path = unquote(urlsplit(lead["website"]).path)
        operator_name = any(re.search(p, key(lead["name"])) for p in platform["operator_name_patterns"])
        if operator_name:
            reasons.append(f"platform operator name: {lead['name']}")
        else:
            # A tenant may link to an operator's location page; the domain/path
            # must never, by itself, turn the tenant into the operator.
            flags.append("SHARED_PLATFORM_TENANT")
        lead.setdefault("platform_evidence", []).append({
            "platform": platform["names"][0], "url_path": path,
            "classification": "operator" if operator_name else "tenant_or_non_operator",
            "evidence": "configured operator-name pattern" if operator_name else "distinct business name; shared platform is not ownership evidence"
        })
    return reasons, flags
