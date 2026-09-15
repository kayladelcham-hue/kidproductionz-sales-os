"""Explicit read-only Brave discovery pilot; no CRM or outreach operations."""
import argparse,csv,json
from pathlib import Path
from discovery_brave import BraveProvider
from discovery_providers import CachedProvider
from discovery_pipeline import discover
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--limit',type=int,default=10);p.add_argument('--live-read-only',action='store_true');args=p.parse_args()
    if not args.live_read_only:p.error('Explicit --live-read-only is required')
    if not 1<=args.limit<=10:p.error('Limit must be 1–10')
    cfg=json.loads((ROOT/'config/discovery_brave_config.json').read_text())
    with args.input.open(encoding='utf-8-sig',newline='') as f:rows=[r for r in csv.DictReader(f) if r.get('queue')=='qualified'][:args.limit]
    adapter=BraveProvider(cfg,ROOT/'discovery_cache'/'public')
    provider=CachedProvider(adapter,cfg,ROOT/'discovery_cache'/'search')
    print(json.dumps(discover(rows,provider,cfg,ROOT/'discovery_outputs'),indent=2))
if __name__=='__main__':main()
