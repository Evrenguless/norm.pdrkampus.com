#!/usr/bin/env python3
"""Validate generated coverage, source preservation and public navigation."""
import hashlib,json,sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit,unquote
from xml.etree import ElementTree as ET
class Page(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.canonicals=[];self.h1=0;self.cta=False;self.schema=[];self.in_schema=False;self.buf='';self.noindex=False
 def handle_starttag(self,t,attrs):
  a=dict(attrs)
  if t=='a':self.links.append(a.get('href',''))
  if t=='h1':self.h1+=1
  if t=='link' and a.get('rel')=='canonical':self.canonicals.append(a.get('href'))
  if t=='meta' and a.get('name')=='robots' and 'noindex' in a.get('content',''):self.noindex=True
  if t=='script' and a.get('type')=='application/ld+json':self.in_schema=True;self.buf=''
 def handle_data(self,data):
  if 'Tüm istatistikleri için' in data:self.cta=True
  if self.in_schema:self.buf+=data
 def handle_endtag(self,t):
  if t=='script' and self.in_schema:self.schema.append(json.loads(self.buf));self.in_schema=False
site=Path(sys.argv[1]).resolve();report=json.loads((site/'school-profile-build.json').read_text());base='https://norm.pdrkampus.com';errors=[]
assert report['profiles']==3512 and report['districts']==39
assert hashlib.sha256((site/'data/schools-v1.json.gz').read_bytes()).hexdigest()==report['source_sha256']
ns={'s':'http://www.sitemaps.org/schemas/sitemap/0.9'};urls=[e.text for e in ET.parse(site/'sitemap.xml').findall('s:url/s:loc',ns)];assert len(urls)==len(set(urls))
for path in report['paths']:
 file=site/path.strip('/')/'index.html';p=Page();p.feed(file.read_text())
 if p.h1!=1 or p.noindex or p.canonicals!=[base+path] or not p.cta or not p.schema or '/' not in p.links or base+path not in urls:errors.append(path+' metadata/CTA')
 for link in p.links:
  u=urlsplit(link)
  if u.scheme or u.netloc or not u.path.startswith('/'):continue
  target=site/unquote(u.path).lstrip('/')
  if not target.is_file() and not (target/'index.html').is_file():errors.append(path+' broken link '+link)
 assert '/assets/logo.png' in file.read_text() and '/assets/school-profile.css' in file.read_text()
assert 'schoolProfileTitle' not in (site/'index.html').read_text()
assert '2.445' in (site/'okul/esenyurt-sezai-karakoc-anadolu-lisesi/index.html').read_text()
assert not errors, '\n'.join(errors[:30])
print(json.dumps({'checked_pages':len(report['paths']),'sitemap_urls':len(urls),'broken_links':0,'duplicate_urls':0,'mandatory_cta':True,'source_data_preserved':True}))
