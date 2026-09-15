"""Outreach priority is independent of the unchanged lead score."""
def number(value):
    try: return float(value)
    except (ValueError,TypeError): return 0

def priority(row, route, channels, cfg):
    if route=='RESEARCH': return 'RESEARCH','Channel/identity verification required.'
    score=number(row.get('score'))
    strong=number(row.get('rating'))>=cfg['priority']['rating'] and number(row.get('reviews'))>=cfg['priority']['reviews']
    count=sum(bool(channels[k]) for k in ('phone','email','social'))
    primary=str(row.get('category_tier','')).lower()=='primary'
    if score>=cfg['priority']['p1_score'] and strong and primary and count>=2:
        return 'P1','High existing score, primary category, strong rating/reviews, and multiple usable channels.'
    if score>=cfg['priority']['p2_score'] and strong:
        return 'P2','Qualified existing score, strong rating/reviews, and an actionable channel.'
    return 'P3','Routable qualified prospect; enrichment or reputation evidence is limited.'
