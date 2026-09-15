from __future__ import annotations
import argparse, os, sqlite3, sys
from pathlib import Path
from sqlalchemy import create_engine, inspect, text

SOURCE=Path(r"C:\Users\CJ\AppData\Local\KidProductionz Sales OS\kidproductionz.db")
TABLES=['campaign','prospect','run','crm_state','upload','external_action','calendar_event','email_activity','app_setting']
SENSITIVE='google_connection'

def pg_url():
 u=os.getenv('DATABASE_URL','')
 if not u or u.startswith('sqlite:') or not (u.startswith('postgresql://') or u.startswith('postgresql+psycopg://')):
  raise SystemExit('DATABASE_URL must be a PostgreSQL URL supplied by the environment')
 return 'postgresql+psycopg://'+u[len('postgresql://'):] if u.startswith('postgresql://') else u

def source_conn():
 if not SOURCE.exists(): raise SystemExit('Source database does not exist')
 return sqlite3.connect(f'file:{SOURCE.as_posix()}?mode=ro',uri=True)

def counts(c):
 return {t:c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in TABLES+['google_connection','queue_item'] if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(t,)).fetchone()}

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--dry-run',action='store_true'); ap.add_argument('--execute',action='store_true'); ap.add_argument('--verify',action='store_true'); ap.add_argument('--approve-write',action='store_true'); a=ap.parse_args()
 if sum((a.dry_run,a.execute,a.verify))!=1: ap.error('choose exactly one mode')
 if a.execute and not a.approve_write:
  print('Execute blocked: add --approve-write to confirm migration writes.'); return 2
 with source_conn() as s:
  sc=counts(s); print('Source counts:',sc); print('Sensitive tables skipped:',SENSITIVE)
  if sc.get('queue_item',0): print('Queue rows present; migration enabled for existing rows only')
  if a.dry_run:
   try:
    e=create_engine(pg_url()); dc={t:e.connect().execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar() for t in sc if t!='google_connection'}
    print('Destination counts:',dc); print('Dry-run PASS')
   except Exception as ex: print('Dry-run FAIL:',type(ex).__name__,str(ex)[:200]); return 1
   return 0
  e=create_engine(pg_url()); insp=inspect(e)
  missing=[t for t in TABLES if not insp.has_table(t)]
  if missing: raise SystemExit('Destination schema missing tables: '+','.join(missing))
  if a.verify:
   dc={t:e.connect().execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar() for t in sc if t!='google_connection'}
   print('Destination counts:',dc); print('Verify PASS' if all(sc.get(t)==dc.get(t) for t in dc) else 'Verify FAIL'); return 0
  pre={t:e.connect().execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar() for t in sc if t!='google_connection'}
  print('Destination pre-migration counts:',pre)
  order=['campaign','prospect','run','crm_state','upload','external_action','calendar_event','email_activity','app_setting']
  if sc.get('queue_item',0): order.append('queue_item')
  for table in order:
   pks=inspect(e).get_pk_constraint(table).get('constrained_columns') or []
   if not pks: raise RuntimeError(f"No primary key found for {table}")
   print(f"{table} primary key: {','.join(pks)}")
  with e.begin() as conn:
   for table in order:
    cur=s.execute(f'SELECT * FROM "{table}"'); rows=cur.fetchall(); cols=[d[0] for d in cur.description]
    pks=inspect(e).get_pk_constraint(table).get('constrained_columns') or []
    if not pks: raise RuntimeError(f"No primary key found for {table}")
    for raw in rows:
     row=dict(zip(cols,raw)); row={k:v for k,v in row.items() if k in [x['name'] for x in inspect(e).get_columns(table)]}
     where=' AND '.join(f'"{k}"=:pk_{k}' for k in pks); params={f'pk_{k}':row[k] for k in pks}
     sets=', '.join(f'"{k}"=:v_{k}' for k in row if k not in pks)
     if conn.execute(text(f'SELECT 1 FROM "{table}" WHERE {where}'),params).first():
      if sets: conn.execute(text(f'UPDATE "{table}" SET {sets} WHERE {where}'),{**params,**{f'v_{k}':v for k,v in row.items() if k not in pks}})
     else:
      names=', '.join(f'"{k}"' for k in row); binds=', '.join(f':{k}' for k in row)
      conn.execute(text(f'INSERT INTO "{table}" ({names}) VALUES ({binds})'),row)
  post={t:e.connect().execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar() for t in pre}
  print('Destination post-migration counts:',post); print('Execute PASS'); return 0
if __name__=='__main__': sys.exit(main())
