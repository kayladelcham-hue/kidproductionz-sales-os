from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
from normalize import url
SOCIAL={'instagram.com':'INSTAGRAM','facebook.com':'FACEBOOK','tiktok.com':'TIKTOK'}
BOOKING={'salonlofts.com','booksy.com','vagaro.com','styleseat.com','fresha.com'}
def canonical(value):
    value=url(value)
    if not value:return ''
    p=urlsplit(value);host=(p.hostname or '').removeprefix('www.')
    return urlunsplit((p.scheme,host,p.path.rstrip('/'),urlencode([(k,v) for k,v in parse_qsl(p.query) if not k.startswith('utm_') and k not in ('fbclid','gclid')]),''))
def kind(value):
    p=urlsplit(value);host=p.hostname
    if host in SOCIAL:return SOCIAL[host]
    if host in BOOKING:return 'BOOKING_PLATFORM'
    if host in ('yelp.com','yellowpages.com'):return 'BUSINESS_DIRECTORY'
    return 'OTHER_PUBLIC_SOURCE'
