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
 ap=argparse.ArgumentParser(); ap.add_argument('--dry-run',action='store_true'); ap.add_argument('--execute',action='store_true'); ap.add_argument('--verify',action='store_true'); ap.add_argument('--preflight',action='store_true'); ap.add_argument('--approve-write',action='store_true'); ap.add_argument('--fresh-cloud-mirror',action='store_true'); a=ap.parse_args()
 if sum((a.dry_run,a.execute,a.verify,a.preflight))!=1: ap.error('choose exactly one mode')
 if a.execute and not a.approve_write:
  print('Execute blocked: add --approve-write to confirm migration writes.'); return 2
 if a.fresh_cloud_mirror and not (a.execute and a.approve_write):
  print('Fresh cloud mirror requires --execute --approve-write.'); return 2
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
  if a.preflight:
   dc={t:e.connect().execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar() for t in sc if t!='google_connection'}
   print('Destination counts:',dc); print('Tables that would be cleared:', ['queue_item','email_activity','calendar_event','external_action','crm_state','upload','run','prospect','app_setting','campaign']); print('Sequence handling:', ['campaign','prospect','run','crm_state','external_action','calendar_event','email_activity','queue_item']); print('Preflight PASS'); return 0
  pre={t:e.connect().execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar() for t in sc if t!='google_connection'}
  print('Destination pre-migration counts:',pre)
  order=['campaign','prospect','run','crm_state','upload','external_action','calendar_event','email_activity','app_setting']
  if sc.get('queue_item',0): order.append('queue_item')
  insp=inspect(e)
  destination_columns={t:{c['name'] for c in insp.get_columns(t)} for t in order}
  primary_keys={t:(insp.get_pk_constraint(t).get('constrained_columns') or []) for t in order}
  for table in order:
   pks=inspect(e).get_pk_constraint(table).get('constrained_columns') or []
   if not pks: raise RuntimeError(f"No primary key found for {table}")
   print(f"{table} primary key: {','.join(pks)}")
  with e.begin() as conn:
   if a.fresh_cloud_mirror:
    for t in ['queue_item','email_activity','calendar_event','external_action','crm_state','upload','run','prospect','app_setting','campaign']:
     conn.execute(text(f'DELETE FROM "{t}"'))
   # Upsert campaigns first, then resolve every legacy identifier on this same transaction connection.
   for raw in s.execute('SELECT * FROM "campaign"').fetchall():
    cur=s.execute('SELECT * FROM "campaign"'); cols=[d[0] for d in cur.description]; row=dict(zip(cols,raw))
    conn.execute(text('UPDATE "campaign" SET "name"=:name,"market"=:market,"active"=:active,"config_ref"=:config_ref,"city"=:city,"state"=:state,"category"=:category,"description"=:description,"daily_queue_limit"=:daily_queue_limit,"status"=:status WHERE "slug"=:slug'),row)
    if not conn.execute(text('SELECT 1 FROM "campaign" WHERE "slug"=:slug'),row).first(): conn.execute(text('INSERT INTO "campaign" ("id","slug","name") VALUES (:id,:slug,:name)'),row)
   campaign_map={}; src_campaigns=s.execute('SELECT id, slug, name FROM campaign').fetchall()
   for sid,slug,name in src_campaigns:
    dest=conn.execute(text('SELECT id,slug,name FROM "campaign" WHERE slug=:slug OR name=:name'),{'slug':slug,'name':name}).first()
    if not dest: raise RuntimeError(f'No destination campaign mapping for {slug or name}')
    campaign_map[str(sid)]=dest[0]; campaign_map[str(slug)]=dest[0]; print(f'{slug or name} -> {dest[0]}')
   for table in order:
    cur=s.execute(f'SELECT * FROM "{table}"'); rows=cur.fetchall(); cols=[d[0] for d in cur.description]
    pks=primary_keys[table]
    if not pks: raise RuntimeError(f"No primary key found for {table}")
    for raw in rows:
      row=dict(zip(cols,raw)); row={k:v for k,v in row.items() if k in destination_columns[table]}
      if table in ('prospect','run') and 'campaign_id' in row:
       key=str(row['campaign_id'])
       if key not in campaign_map: raise RuntimeError(f'No campaign mapping for {key}')
       row['campaign_id']=campaign_map[key]
     where=' AND '.join(f'"{k}"=:pk_{k}' for k in pks); params={f'pk_{k}':row[k] for k in pks}
     sets=', '.join(f'"{k}"=:v_{k}' for k in row if k not in pks)
     if conn.execute(text(f'SELECT 1 FROM "{table}" WHERE {where}'),params).first():
      if sets: conn.execute(text(f'UPDATE "{table}" SET {sets} WHERE {where}'),{**params,**{f'v_{k}':v for k,v in row.items() if k not in pks}})
     else:
      names=', '.join(f'"{k}"' for k in row); binds=', '.join(f':{k}' for k in row)
      conn.execute(text(f'INSERT INTO "{table}" ({names}) VALUES ({binds})'),row)
   # Synchronize identity sequences after preserving source IDs.
   for table in order:
    pks=primary_keys[table]
    if len(pks)!=1 or table=='app_setting': continue
    pk=pks[0]
    seq=conn.execute(text('SELECT pg_get_serial_sequence(:table_name,:column_name)'),{'table_name':table,'column_name':pk}).scalar()
    if seq:
     max_id=conn.execute(text(f'SELECT MAX("{pk}") FROM "{table}"')).scalar()
     if max_id is not None: conn.execute(text('SELECT setval(CAST(:seq AS regclass), :value, true)'),{'seq':seq,'value':max_id})
  post={t:e.connect().execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar() for t in pre}
  print('Destination post-migration counts:',post); print('Execute PASS'); return 0
if __name__=='__main__': sys.exit(main())
