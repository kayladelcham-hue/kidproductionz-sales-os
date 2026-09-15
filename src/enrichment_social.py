"""Social profile links explicitly published on corroborated official pages."""
from urllib.parse import urlsplit
from normalize import url

def socials(links,cfg):
    result={}
    for link in links:
        value=url(link)
        if not value:continue
        p=urlsplit(value);host=(p.hostname or '').removeprefix('www.')
        parts=p.path.strip('/').split('/')
        if host not in cfg['social_domains'] or not parts[0] or parts[0] in ('p','reel','reels','share','sharer.php','login','explore','watch','stories'):continue
        if len(parts)!=1:continue
        clean=p.scheme+'://'+host+'/'+parts[0]
        result[clean]={'platform':cfg['social_domains'][host],'handle':parts[0]}
    return result
