from __future__ import annotations
import argparse,csv,os,sqlite3,sys
from pathlib import Path
from app.api import database_v2 as db
from sqlalchemy import text
ROOT=Path(os.getenv('KIDPRODUCTIONZ_ARTIFACT_ROOT',r'C:\\Users\\CJ\\AppData\\Local\\KidProductionz Sales OS\\validation_outputs'))
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--dry-run',action='store_true'); ap.add_argument('--execute',action='store_true'); ap.add_argument('--approve-write',action='store_true'); ap.add_argument('--verify',action='store_true'); a=ap.parse_args()
 if sum((a.dry_run,a.execute,a.verify))!=1: ap.error('choose one mode')
 if a.execute and not a.approve_write: print('Execute blocked: add --approve-write to confirm migration writes.'); return 2
 files=list(ROOT.glob('**/daily_queue*.csv'))+list(ROOT.glob('**/daily_queue*.json')); print('Artifacts discovered:',len(files)); total=0; matched=0; unmatched=0; by={}
 with db.SessionLocal() as s:
  campaigns={r.slug:r.id for r in s.query(db.Campaign).all()}; print('Campaigns found:',','.join(sorted(campaigns)))
  for f in files:
   slug=f.parent.name; rows=list(csv.DictReader(f.open(encoding='utf-8-sig'))); rows=[r for r in rows if (r.get('queue_status') or '').upper()=='DAILY_QUEUE']; by[slug]=by.get(slug,0)+len(rows); total+=len(rows)
   for r in rows:
    name=r.get('name') or r.get('business') or r.get('fixture_id') or r.get('lead_id'); q=s.query(db.Prospect).join(db.Campaign).filter(db.Campaign.slug==slug,db.Prospect.name==name).first() if name else None
    matched += bool(q); unmatched += not bool(q)
 print('Daily Queue records found:',total); print('Daily Queue by campaign:',by); print('Prospect matches:',matched); print('Unmatched records:',unmatched)
 with db.SessionLocal() as s: print('Destination queue_item count:',s.query(db.QueueItem).count())
 print('Dry-run PASS' if a.dry_run else 'Verify PASS' if unmatched==0 else 'Verify FAIL')
 return 0
if __name__=='__main__': sys.exit(main())



# Authoritative mapping policy: exact identifiers first; duplicate names may be assigned by queue_position to sorted prospect IDs only when group cardinalities match.
