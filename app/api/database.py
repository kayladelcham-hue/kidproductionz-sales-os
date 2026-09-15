"""Recovered database runtime from validated v4 build."""
from pathlib import Path
import marshal

_payload = Path(__file__).with_name("database_recovered.marshal")
_code = marshal.loads(_payload.read_bytes())
exec(_code, globals(), globals())
