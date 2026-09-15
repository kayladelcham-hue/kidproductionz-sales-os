"""Only allowlisted company/property GET requests, with redacted diagnostics."""
import json
import os
import re
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, quote, quote_plus
from urllib.request import Request, build_opener, HTTPRedirectHandler

class ReadError(RuntimeError):
    def __init__(self, message, diagnostic=None):
        self.diagnostic = diagnostic
        super().__init__(message if diagnostic is None else
                         message + "\n" + json.dumps(diagnostic, ensure_ascii=True, indent=2))

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def redact(value, token):
    """Sanitize before display/storage; never output arbitrary response headers."""
    secret_keys = {"authorization", "proxyauthorization", "accesstoken", "refreshtoken",
                   "clientsecret", "token", "hapikey", "apikey", "password", "cookie", "setcookie"}
    if isinstance(value, dict):
        return {redact(str(k), token): "[REDACTED]" if re.sub(r"[^a-z]", "", str(k).lower()) in secret_keys
                else redact(v, token) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, token) for v in value]
    if not isinstance(value, str):
        return value
    if token:
        variants = {token, quote(token, safe=""), quote_plus(token), json.dumps(token)[1:-1]}
        for secret in sorted(variants, key=len, reverse=True):
            value = value.replace(secret, "[REDACTED]")
    value = re.sub(r"(?i)\bBearer\s+[^\s\"'<>,;]+", "Bearer [REDACTED]", value)
    value = re.sub(r'''(?ix)
        ((?:authorization|access[_-]?token|refresh[_-]?token|client[_-]?secret|
        hapikey|api[_-]?key|password|cookie)\s*["']?\s*[:=]\s*)
        (?:"[^"]*"|'[^']*'|[^\s&,;<]+)
        ''', r"\1[REDACTED]", value)
    return value

class HubSpotReader:
    PATHS = {"/crm/v3/properties/companies", "/crm/v3/objects/companies"}

    @classmethod
    def from_environment(cls, cfg):
        env_name = cfg.get("token_env")
        if not isinstance(env_name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", env_name):
            raise ReadError("Invalid credential environment-variable configuration")
        token = os.environ.get(env_name)
        if not token or not token.strip():
            raise ReadError("Read-only credential environment variable is missing or blank: " + env_name)
        return cls(token, cfg)

    def __init__(self, token, cfg):
        if cfg["api_base"] != "https://api.hubapi.com":
            raise ReadError("Only the official HubSpot API host is allowed")
        if not isinstance(token, str) or not token.strip():
            raise ReadError("A read-only Service Key is required")
        # Copy/paste outer whitespace is harmless; never accept a whole header,
        # quotes, line breaks, or other invalid Bearer credential characters.
        token = token.strip()
        if not re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", token):
            raise ReadError("Malformed Service Key: supply only the key, without quotes, a Bearer prefix, or embedded whitespace")
        self._token = token
        self.cfg = cfg
        self.opener = build_opener(NoRedirect())
        self.diagnostics = []
        self.property_validation = None

    def report_property_validation(self, report):
        self.property_validation = redact(report, self._token)
        print("HubSpot property validation: " + json.dumps(self.property_validation, ensure_ascii=True),
              file=sys.stderr)

    def _failure(self, path, params, target, code, body, correlation_id, attempt, authorization_header_present=False):
        params = params or {}
        requested = params.get("properties", "")
        properties = requested.split(",") if isinstance(requested, str) else list(requested)
        diagnostic = redact({
            "method": "GET", "endpoint": self.cfg["api_base"] + path,
            "request_url": target, "query_parameters": params,
            "requested_properties": properties if requested else [],
            "http_status": code, "attempt": attempt + 1,
            "authorization_header_present": authorization_header_present,
            "response_body": body,
            "message": body.get("message") if isinstance(body, dict) else body,
            "correlation_id": (body.get("correlationId") if isinstance(body, dict) else None) or correlation_id,
            "property_validation": self.property_validation
        }, self._token)
        self.diagnostics.append(diagnostic)
        print("HubSpot GET diagnostic: " + json.dumps(diagnostic, ensure_ascii=True), file=sys.stderr)
        return diagnostic

    def get(self, path, params=None):
        if path not in self.PATHS:
            raise ReadError("Endpoint is not on the read-only allowlist")
        target = self.cfg["api_base"] + path
        if params:
            target += "?" + urlencode(params)
        settings = self.cfg["retrieval"]
        for attempt in range(settings["max_retries"] + 1):
            request = Request(target, headers={"Authorization": "Bearer " + self._token,
                                               "Accept": "application/json"}, method="GET")
            authorization_present = bool(request.get_header("Authorization"))
            if not authorization_present:
                raise ReadError("Authorization header missing locally; no HTTP request sent")
            print("HubSpot request authentication: " + json.dumps({
                "authorization_header_present": authorization_present}), file=sys.stderr)
            try:
                with self.opener.open(request, timeout=settings["timeout_seconds"]) as response:
                    return json.load(response)
            except HTTPError as exc:
                code = exc.code
                retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
                correlation = exc.headers.get("X-HubSpot-Correlation-Id") if exc.headers else None
                try:
                    raw = exc.read().decode("utf-8", errors="replace")
                    try:
                        body = json.loads(raw)
                    except ValueError:
                        body = raw
                except Exception:
                    body = "[Response body could not be read]"
                finally:
                    exc.close()
                diagnostic = self._failure(path, params, target, code, body, correlation, attempt, authorization_present)
                if code not in (429, 500, 502, 503, 504) or attempt == settings["max_retries"]:
                    raise ReadError(f"HubSpot read failed: HTTP {code}", diagnostic) from None
                try:
                    delay = min(60, max(0, float(retry_after)))
                except ValueError:
                    delay = min(30, 2 ** attempt)
                time.sleep(delay)
            except Exception:
                diagnostic = self._failure(path, params, target, None,
                    "[Network, timeout, or invalid JSON response; no HTTP error body available]", None, attempt, authorization_present)
                raise ReadError("HubSpot GET failed", diagnostic) from None
