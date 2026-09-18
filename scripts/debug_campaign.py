import uuid
import traceback
from app.api import database_v2 as db

db.init_db()
slug = "debug_" + uuid.uuid4().hex[:8]

print("slug:", slug)

try:
    c = db.create_campaign({
        "slug": slug,
        "name": "debug_campaign",
        "city": "Render",
        "state": "TS",
        "category": "Validation",
    })
    print("CREATED:", c)
    print("GET:", db.get_campaign(slug))
    print("LIST MATCH:", [x for x in db.list_campaigns() if x.get("slug") == slug])
except Exception:
    traceback.print_exc()
