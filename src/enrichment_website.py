"""Extract visible page text and links without executing JavaScript."""
from html.parser import HTMLParser
from urllib.parse import urljoin,urlsplit

class Page(HTMLParser):
    def __init__(self,html):
        super().__init__();self.links=[];self.text=[];self.hidden=0;self.feed(html)
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.hidden+=1
        if tag=='a':
            href=dict(attrs).get('href')
            if href:self.links.append(href)
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.hidden=max(0,self.hidden-1)
    def handle_data(self,data):
        if not self.hidden:self.text.append(data)

def contact_page(base,links):
    for link in links:
        value=urljoin(base,link)
        p=urlsplit(value)
        if p.netloc==urlsplit(base).netloc and p.path.rstrip('/').lower() in ('/contact','/contact-us') and not p.query:return value
    return None
