"""Deterministic per-route daily selection."""
from outreach_routing import ROUTES
from outreach_priority import number

def queue(rows,cfg):
    order={'P1':0,'P2':1,'P3':2,'RESEARCH':3}
    selected=[]
    for route in ROUTES:
        limit=cfg['daily_limits'][route]
        if type(limit) is not int or limit<0: raise ValueError('Daily limits must be nonnegative integers')
        candidates=[r for r in rows if r['outreach_route']==route]
        candidates.sort(key=lambda r:(order[r['outreach_priority']],-number(r['lead_score']),r['company_name'].casefold(),r['lead_id']))
        selected.extend(candidates[:limit])
    return selected
