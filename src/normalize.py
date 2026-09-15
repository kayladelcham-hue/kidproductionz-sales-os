"""Conservative normalization; original cells are retained in every export."""
import json
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

def text(value):
    return "" if value is None else str(value).strip()

def key(value):
    value = unicodedata.normalize("NFKD", text(value).casefold())
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()

def phrase(value, term):
    return bool(key(term)) and (" " + key(term) + " ") in (" " + key(value) + " ")

def phone(value):
    raw = text(value)
    extension = re.search(r"(?:ext\.?|x|#)\s*(\d+)\s*$", raw, re.I)
    if extension:
        raw = raw[:extension.start()]
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        digits = "1" + digits
    if len(digits) != 11 or not digits.startswith("1"):
        return ""
    if digits[1] in "01" or digits[4] in "01" or len(set(digits[1:])) == 1:
        return ""
    return "+" + digits + (" ext " + extension.group(1) if extension else "")

def url(value):
    raw = text(value)
    if not raw or any(c.isspace() for c in raw):
        return ""
    try:
        parsed = urlsplit(raw if "://" in raw else "https://" + raw)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme not in ("http", "https") or "." not in host or parsed.username:
            return ""
        if not re.fullmatch(r"[a-z0-9.-]+", host) or ".." in host:
            return ""
        host = host.removeprefix("www.")
        netloc = host + (":" + str(parsed.port) if parsed.port else "")
        return urlunsplit((parsed.scheme, netloc, parsed.path.rstrip("/"), parsed.query, ""))
    except ValueError:
        return ""

def domain(value):
    raw = text(value)
    if not raw:
        return ""
    try:
        return (urlsplit(raw).hostname or "").removeprefix("www.")
    except (TypeError, ValueError):
        return ""

def host_matches(host, domains):
    normalized = text(host).lower().rstrip(".")
    if not normalized:
        return False
    return any(normalized == text(d).lower().rstrip(".") or normalized.endswith("." + text(d).lower().rstrip(".")) for d in domains)

def normalize(row, cfg):
    aliases = cfg["column_aliases"]
    cells = {key(k): text(v) for k, v in row.items()}
    empty = {key(v) for v in cfg["contact"]["placeholder_values"]}
    def values(field):
        return list(dict.fromkeys(cells[key(a)] for a in aliases[field]
                                 if key(a) in cells and key(cells[key(a)]) not in empty))
    def first(field):
        return next(iter(values(field)), "")
    lead = {f: first(f) for f in aliases}
    lead["name"] = re.sub(r"\s+", " ", lead["name"]).strip()
    lead["name_key"] = key(lead["name"])
    lead["city"] = re.sub(r"\s+", " ", lead["city"]).strip()
    lead["state"] = cfg["state_aliases"].get(key(lead["state"]), lead["state"].upper())
    lead["category"] = " | ".join(values("category"))
    lead["phone"] = next((p for v in values("phone") if (p := phone(v))), "")
    for field in ("rating", "reviews"):
        try:
            lead[field] = float(lead[field].replace(",", ""))
        except (ValueError, AttributeError):
            lead[field] = None
    if lead["rating"] is not None and not 0 <= lead["rating"] <= 5:
        lead["rating"] = None
    if lead["reviews"] is not None and (lead["reviews"] < 0 or not lead["reviews"].is_integer()):
        lead["reviews"] = None
    emails = []
    for v in values("email"):
        emails.extend(re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", v))
    lead["email"] = "; ".join(dict.fromkeys(e.lower() for e in emails))
    web, social, other = [], [], []
    for field in ("website", "social", "other_contact"):
        for v in values(field):
            for token in re.split(r'[;,\s|\[\]"]+', v):
                u = url(token)
                if not u:
                    continue
                host = domain(u)
                if host_matches(host, cfg["contact"]["directory_domains"]):
                    continue
                platform_host = host_matches(host, cfg["contact"]["social_domains"] + cfg["contact"]["booking_domains"])
                if platform_host and urlsplit(u).path.rstrip("/") in cfg["contact"]["generic_platform_paths"]:
                    continue
                if host_matches(host, cfg["contact"]["social_domains"]):
                    social.append(u)
                elif field == "other_contact" or host_matches(host, cfg["contact"]["booking_domains"]):
                    other.append(u)
                elif field == "website":
                    web.append(u)
    lead["website"] = next(iter(web), "")
    lead["domain"] = domain(lead["website"])
    lead["social"] = "; ".join(dict.fromkeys(social))
    lead["other_contact"] = "; ".join(dict.fromkeys(other))
    lead["original_data"] = json.dumps(row, ensure_ascii=False, default=str)
    return lead
