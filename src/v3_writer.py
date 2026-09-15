"""V3-only company CREATE transport. No updates, associations or retry loop."""
import json
import os
import re
from urllib.error import HTTPError
from urllib.request import Request, build_opener
from hubspot_client import NoRedirect, redact

class CreateError(RuntimeError):
    pass

class CompanyCreator:
    def __init__(self, cfg):
        if cfg.get("enabled") is not True:
            raise CreateError("V3 writes are disabled")
        token = os.environ.get(cfg["write_token_env"], "").strip()
        if not token or not re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", token):
            raise CreateError("Missing or malformed V3 create credential")
        self._token = token
        self.opener = build_opener(NoRedirect())

    def create_company(self, payload):
        if set(payload) != {"properties"} or not isinstance(payload["properties"], dict) or not payload["properties"].get("name"):
            raise CreateError("Only a company properties payload with a name is allowed")
        request = Request("https://api.hubapi.com/crm/v3/objects/companies",
                          data=json.dumps(payload).encode("utf-8"),
                          headers={"Authorization":"Bearer " + self._token, "Content-Type":"application/json"},
                          method="POST")
        try:
            with self.opener.open(request, timeout=30) as response:
                result = json.load(response)
            if not isinstance(result.get("id"), str) or not result["id"].isdigit():
                raise ValueError()
            return result["id"]
        except HTTPError as exc:
            code = exc.code
            try:
                body = redact(exc.read().decode("utf-8", errors="replace"), self._token)
            except Exception:
                body = "[Body unavailable]"
            finally:
                exc.close()
            raise CreateError("Company create HTTP " + str(code) + ": " + body) from None
        except Exception:
            raise CreateError("Create outcome unknown: transport or response failure; do not retry automatically") from None
