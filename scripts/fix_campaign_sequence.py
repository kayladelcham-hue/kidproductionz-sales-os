from app.api import database_v2 as db
from sqlalchemy import text

with db.engine.begin() as conn:
    conn.execute(text("""
        SELECT setval(
            pg_get_serial_sequence('campaign', 'id'),
            COALESCE((SELECT MAX(id) FROM campaign), 1),
            true
        )
    """))

print("campaign sequence repaired")
