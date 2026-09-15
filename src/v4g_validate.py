import json
from pathlib import Path
from unittest.mock import patch
import v4f_validate
from v4g_redirects import RedirectFetcher

def main():
 root=Path(__file__).resolve().parents[1];base=root/'discovery_outputs/bf5212e7dee74a9fb70a751afd08a0b3'
 holders=[]
 def factory(*a,**kw):
  f=RedirectFetcher(*a,**kw);holders.append(f);return f
 with patch.object(v4f_validate,'FragmentFetcher',factory):report=v4f_validate.run(base,root)
 f=holders[0];folder=Path(report['output']);target=folder.with_name(folder.name.replace('v4f_','v4g_',1));folder.rename(target)
 report['output']=str(target)
 report.update(redirect_encounters=len(f.redirects),redirects_followed=sum(r['followed'] for r in f.redirects),redirects_blocked=sum(not r['followed'] for r in f.redirects),redirect_loops_errors=sum(r['blocking_reason'] in ('REDIRECT_LOOP','REDIRECT_HOP_LIMIT') for r in f.redirects),redirect_chains=f.redirects,final_urls=f.final_urls)
 (target/'summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()
