#!/usr/bin/env python3
"""Offline audit and proposal renderer. Never writes into an application checkout."""
import argparse
import hashlib
import html
import json
import re
import sys
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote
import xml.etree.ElementTree as ET

STATUSES = ('created', 'updated', 'skipped', 'duplicate', 'invalid', 'noindex', 'error')

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def runtime_digest(source):
    scripts = [m.group(0) for m in re.finditer(r'<script\b[^>]*>.*?</script>', source, re.S | re.I)
               if 'application/ld+json' not in m.group(0).split('>')[0]]
    return hashlib.sha256('\n'.join(scripts).encode()).hexdigest()

def protected(root):
    baseline = read(root / 'seo/protected-files.json')
    approval_path = root / 'seo/approved-edits.json'
    approvals = read(approval_path).get('edits', {}) if approval_path.exists() else {}
    changes, approved = [], []
    for name, expected in baseline['files'].items():
        path = root / name
        if path.is_file() and not path.is_symlink() and digest(path) == expected:
            continue
        edit = approvals.get(name, {})
        permitted = name.endswith('.html') or name == 'sitemap.xml' or name in {'scripts/build_library_catalog.py', 'src/library.js', 'tests/catalog.mjs', 'scripts/check_links.py'}
        valid = (permitted and path.is_file() and not path.is_symlink()
                 and edit.get('baseline_sha256') == expected and edit.get('reviewed_sha256') == digest(path))
        if valid and name.endswith('.html'):
            valid = edit.get('runtime_sha256') == runtime_digest(path.read_text(encoding='utf-8'))
        (approved if valid else changes).append(name)
    return {'baseline_commit': baseline['baseline_commit'], 'checked': len(baseline['files']),
            'changed': changes, 'approved_seo_edits': approved, 'pass': not changes}

class Page(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.links, self.canonicals, self.schemas, self.errors = [], [], [], []
        self.title, self.description, self.h1, self.main_text = '', '', [], ''
        self.noindex = False
        self.primary_h1 = []
        self._stack = []
        self._heading_visible = False
        self._title = self._h1 = self._main = self._script = self._style = False
        self._ld = False
        self._buffer = ''
        self.feed(source)
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        suppressed = any(frame[1] for frame in self._stack) or 'hidden' in a or a.get('role') == 'dialog' or a.get('aria-hidden') == 'true'
        if tag not in {'meta','link','img','br','hr','input','source','area','base','embed','param','track','wbr'}:
            self._stack.append((tag, suppressed))
        if tag == 'title': self._title = True
        if tag == 'h1':
            self._h1 = True; self.h1.append(''); self._heading_visible = not suppressed
            if self._heading_visible: self.primary_h1.append('')
        if tag == 'main': self._main = True
        if tag == 'script':
            self._script = True; self._ld = a.get('type') == 'application/ld+json'; self._buffer = ''
        if tag == 'style': self._style = True
        if tag == 'a' and a.get('href'): self.links.append(a['href'])
        if tag == 'link' and 'canonical' in a.get('rel', '').split(): self.canonicals.append(a.get('href', ''))
        if tag == 'meta':
            if a.get('name') == 'description': self.description = a.get('content', '')
            if a.get('name', '').lower() in ('robots','googlebot'):
                self.noindex |= 'noindex' in a.get('content','').lower()
    def handle_data(self, data):
        if self._ld: self._buffer += data
        if self._script or self._style: return
        if self._title: self.title += data
        if self._h1:
            self.h1[-1] += data
            if self._heading_visible: self.primary_h1[-1] += data
        if self._main: self.main_text += data + ' '
    def handle_endtag(self, tag):
        for i in range(len(self._stack)-1, -1, -1):
            if self._stack[i][0] == tag:
                del self._stack[i:]
                break
        if tag == 'title': self._title = False
        if tag == 'h1': self._h1 = False
        if tag == 'main': self._main = False
        if tag == 'style': self._style = False
        if tag == 'script':
            if self._ld:
                try: self.schemas.append(json.loads(self._buffer))
                except ValueError as e: self.errors.append(str(e))
            self._ld = self._script = False

def page_url(base, relative):
    name = relative.as_posix()
    if name == 'index.html': name = ''
    elif name.endswith('/index.html'): name = name[:-10]
    return urljoin(base + '/', name)

def pages(root, config):
    return {page_url(config['base_url'], p.relative_to(root)): (p, Page(p.read_text(encoding='utf-8')))
            for p in sorted(root.rglob('*.html')) if not set(p.relative_to(root).parts) & {'.git','node_modules','seo'}}

def audit(root, config):
    inventory = pages(root, config)
    inbound = defaultdict(set)
    for origin, (_, page) in inventory.items():
        for link in page.links:
            target = urljoin(origin, link).split('#')[0].split('?')[0]
            if target in inventory and target != origin: inbound[target].add(origin)
    sitepath = root / 'sitemap.xml'
    sitemap, sitemap_error = set(), None
    if sitepath.exists():
        try: sitemap = {n.text for n in ET.parse(sitepath).iter() if n.tag.split('}')[-1] == 'loc'}
        except ET.ParseError as e: sitemap_error = str(e)
    titles = Counter(p.title for _, p in inventory.values() if p.title and not p.noindex)
    descriptions = Counter(p.description for _, p in inventory.values() if p.description and not p.noindex)
    rows = []
    for url, (path, page) in inventory.items():
        issues = []
        if not page.noindex and page.canonicals != [url]: issues.append('canonical_missing_multiple_or_mismatch')
        if not page.noindex and not page.title: issues.append('missing_title')
        elif not page.noindex and titles[page.title] > 1: issues.append('duplicate_title')
        if not page.noindex and not page.description: issues.append('missing_description')
        elif not page.noindex and descriptions[page.description] > 1: issues.append('duplicate_description')
        if not page.noindex and len(page.primary_h1) != 1: issues.append('primary_h1_count_' + str(len(page.primary_h1)))
        if page.errors: issues.append('jsonld_syntax_error')
        if page.noindex and url in sitemap: issues.append('noindex_in_sitemap')
        if not page.noindex and not inbound[url] and url != config['base_url']+'/': issues.append('static_inbound_not_observed')
        rows.append({'url':url, 'file':path.relative_to(root).as_posix(), 'issues':issues,
                     'noindex':page.noindex, 'sitemap':url in sitemap, 'inbound_count':len(inbound[url])})
    groups = defaultdict(list)
    for name in config.get('catalogues', []):
        for entry in read(root / name):
            if entry.get('file'): groups[entry['file']].append({'id':entry['id'],'catalogue':name})
    return {'mode':'offline_static', 'protection':protected(root), 'pages':rows,
            'robots_exists':(root/'robots.txt').exists(), 'sitemap_exists':sitepath.exists(),
            'sitemap_error':sitemap_error, 'sitemap_unresolved':sorted(sitemap-set(inventory)),
            'duplicate_file_groups':[{'file':url,'members':v} for url,v in groups.items() if len(v)>1],
            'limits':['No live HTTP, Search Console, browser execution or external schema validation.',
                      'Static inbound absence is a review candidate; no automatic noindex or route removal.']}

def render(root, config, proposal, source=None):
    route = proposal['route']
    if not re.fullmatch(r'/kaynak-detay/[a-z0-9-]+/', route): raise ValueError('unsupported route')
    original = root / route.strip('/') / 'index.html'
    source = original.read_text(encoding='utf-8') if source is None else source
    h = html.escape
    desc = h(proposal['description'], quote=True)
    source, n = re.subn(r'(<meta (?:name="description"|property="og:description") content=")[^"]*(">)',
                       lambda m:m[1]+desc+m[2], source)
    if n != 2: raise ValueError('description template changed')
    source, n = re.subn(r'<p class="catalog-lead">.*?</p>',
                       '<p class="catalog-lead">'+h(proposal['answer'])+'</p>', source, count=1, flags=re.S)
    if n != 1: raise ValueError('lead template changed')
    section = '<section class="catalog-card"><h2>Belgenin kapsamı ve kullanımı</h2>'
    for title, body in proposal['sections']:
        section += '<h3>'+h(title)+'</h3><p>'+h(body)+'</p>'
    section += '</section><section class="catalog-card"><h2>Sık sorulan sorular</h2>'
    for q,a in proposal['faq']:
        section += '<h3>'+h(q)+'</h3><p>'+h(a)+'</p>'
    section += '</section><section class="catalog-card"><h2>Kaynak ve kontrol bilgisi</h2>'
    section += '<p>'+h(proposal['methodology'])+'</p>'
    section += '<p>Kaynak erişimi ve içerik kontrolü: <time datetime="'+h(proposal['checked_on'])+'">'+h(proposal['checked_on'])+'</time>. Bu tarih belgenin yayın tarihi değildir.</p>'
    section += '<p><a href="'+h(proposal['source_url'])+'#page='+str(proposal['source_pdf_page'])+'" target="_blank" rel="noopener">Açıklamanın dayandığı belge bölümü (PDF sayfası '+str(proposal['source_pdf_page'])+')</a></p>'
    section += '<p><a href="/konu/akran-zorbaligi/">Akran zorbalığı konu rehberi</a></p></section>'
    source, n = re.subn(r'<section class="catalog-card"><h2>(?:Hangi çalışma için kullanılabilir\?|Belgenin kapsamı ve kullanımı)</h2>.*?(?=<h2>İlgili kaynaklar</h2>)',
                       lambda _:section, source, count=1, flags=re.S)
    if n != 1: raise ValueError('body template changed')
    canonical = config['base_url'] + route
    catalogue = {x['id']:x for x in read(root/'data/library.json')}
    item = catalogue[proposal['id']]
    schema = {'@context':'https://schema.org','@graph':[
        {'@type':['CreativeWork','LearningResource'],'name':item['title'],'url':canonical,
         'description':proposal['answer'],'inLanguage':'tr','learningResourceType':item['type'],
         'educationalLevel':item['level'],'isAccessibleForFree':True,
         'publisher':{'@type':'Organization','name':item['source']},
         'encoding':{'@type':'MediaObject','contentUrl':item['file'],'encodingFormat':'application/pdf'},
         'citation':item['sourcePage']},
        {'@type':'BreadcrumbList','itemListElement':[
            {'@type':'ListItem','position':1,'name':'Kütüphane','item':config['base_url']+'/kutuphane.html'},
            {'@type':'ListItem','position':2,'name':'Resmî kaynaklar','item':config['base_url']+'/kutuphane/katalog/'},
            {'@type':'ListItem','position':3,'name':item['title'],'item':canonical}]}]}
    encoded = json.dumps(schema,ensure_ascii=False).replace('<','\\u003c')
    source, n = re.subn(r'<script type="application/ld\+json">.*?</script>',
                       lambda _:'<script type="application/ld+json">'+encoded+'</script>',source,count=1,flags=re.S)
    if n != 1: raise ValueError('schema template changed')
    return source

def validate(root, config, manifest, source_dir):
    guard = protected(root)
    existing = pages(root,config)
    results, seen = [], set()
    proposals = manifest.get('proposals', [])
    routes = Counter(p.get('route') for p in proposals)
    library = {x['id']:x for x in read(root/'data/library.json')} if proposals else {}
    for p in proposals:
        issues, source = [], None
        try:
            for key in ('id','route','answer','description','sections','faq','methodology','checked_on','source_url','source_sha256','source_pdf_page'):
                if not p.get(key): raise ValueError('missing '+key)
            if not re.fullmatch(r'[a-z0-9-]+', p['id']): raise ValueError('invalid resource id')
            route = p['route']; url = config['base_url'] + route
            if routes[route] > 1: issues.append('duplicate_route')
            if p['source_url'] in seen: issues.append('duplicate_source')
            seen.add(p['source_url'])
            item = library.get(p['id'])
            if not item or item['file'] != p['source_url']: issues.append('catalogue_source_mismatch')
            if source_dir is None: issues.append('source_evidence_directory_required')
            else:
                pdf = source_dir / (p['id']+'.pdf')
                if not pdf.is_file() or digest(pdf) != p['source_sha256']: issues.append('source_hash_mismatch')
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',p['checked_on']): issues.append('invalid_check_date')
            if url not in existing: issues.append('existing_route_required')
            source = render(root,config,p)
            page = Page(source)
            inbound = any(urljoin(u,l).split('#')[0] == url for u,(_,pg) in existing.items() if u != url for l in pg.links)
            nodes = page.schemas[0].get('@graph',[]) if page.schemas else []
            resource = next((x for x in nodes if 'LearningResource' in x.get('@type',[])),{})
            checks = {
                'source_evidence':('source_hash_mismatch' not in issues and source_dir is not None,20),
                'specific_scope':(len(p['sections'])>=2 and len({b for _,b in p['sections']})==len(p['sections']),20),
                'concise_answer':(25<=len(p['answer'].split())<=90,15),
                'source_method_date':(len(p['methodology'])>=80 and p['checked_on'] in page.main_text,10),
                'visible_questions':(len(p['faq'])>=2 and all(q in page.main_text and a in page.main_text for q,a in p['faq']),10),
                'metadata':(bool(page.title) and 80<=len(page.description)<=180 and page.canonicals==[url] and len(page.h1)==1,10),
                'schema_visible_match':(not page.errors and resource.get('name') in page.h1 and resource.get('description')==p['answer'] and resource.get('url')==url and item is not None and resource.get('publisher',{}).get('name')==item['source'],10),
                'internal_discovery':(inbound and '/konu/akran-zorbaligi/' in page.links,5)}
            score = sum(w for ok,w in checks.values() if ok)
            for name,(ok,_) in checks.items():
                if not ok: issues.append(name)
            if page.noindex: issues.append('existing_noindex')
            if not guard['pass']: issues.append('protected_file_changed')
            if score < config['minimum_score']: issues.append('below_quality_threshold')
            hard_ok = not issues
            status = 'duplicate' if any(i.startswith('duplicate_') for i in issues) else 'noindex' if page.noindex else 'invalid' if not hard_ok else 'updated'
            results.append({'id':p['id'],'route':route,'status':status,'score':score,'checks':{k:ok for k,(ok,_) in checks.items()},'issues':issues,
                            'eligible_for_staging':hard_ok,'render_sha256':hashlib.sha256(source.encode()).hexdigest()})
        except (KeyError,ValueError,OSError,TypeError) as e:
            results.append({'id':p.get('id'),'status':'error','issues':[str(e)],'eligible_for_staging':False})
    return {'mode':'offline_proposal_validation','protection':guard,'results':results,
            'status_counts':{s:sum(r['status']==s for r in results) for s in STATUSES},
            'score_note':'Editorial checklist, not a search ranking score. Every check is also a required gate.',
            'limits':['Source hash establishes document identity, not independent factual review.',
                      'No live publication, indexability guarantee or rich-result eligibility claim.']}

def safe_output(root, output):
    output = output.resolve()
    root = root.resolve()
    if output == root or root in output.parents or output in root.parents:
        raise ValueError('Output must be outside the application checkout and its ancestors')
    return output

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command',choices=['audit','validate','generate'])
    ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument('--sources',type=Path)
    ap.add_argument('--output',type=Path,required=True,help='New output directory, outside checkout')
    ap.add_argument('--dry-run',action='store_true',help='Required for generate: write previews only')
    args = ap.parse_args()
    root = args.root.resolve()
    config = read(root/'seo/config.json')
    output = safe_output(root,args.output)
    if output.exists(): raise ValueError('Output directory already exists; choose a new directory')
    if args.command=='generate' and not args.dry_run: raise ValueError('Only generate --dry-run is supported; deployment is not implemented')
    manifest = read(root/'seo/pilot.json')
    result = audit(root,config) if args.command=='audit' else validate(root,config,manifest,args.sources)
    if args.command=='generate' and not result['protection']['pass']: raise ValueError('Protected original files changed; refusing previews')
    output.mkdir(parents=True)
    if args.command=='generate':
        for p,r in zip(manifest['proposals'],result['results']):
            if r['eligible_for_staging']:
                target = output/'preview'/p['route'].strip('/')/'index.html'
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text(render(root,config,p),encoding='utf-8')
                r['preview_file'] = target.relative_to(output).as_posix()
        result['dry_run']=True
        result['application_writes']=0
    (output/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'report':str(output/'report.json'),'protection':result['protection'],'status_counts':result.get('status_counts')},ensure_ascii=False))
    return 0 if result['protection']['pass'] and all(r['eligible_for_staging'] for r in result.get('results',[])) else 1

if __name__=='__main__':
    try: sys.exit(main())
    except (ValueError,OSError,KeyError) as e:
        print('ERROR: '+str(e),file=sys.stderr); sys.exit(2)
