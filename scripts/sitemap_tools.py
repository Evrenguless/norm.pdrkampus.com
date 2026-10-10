"""Canonical-only, bounded sitemap serialization shared by all publishers."""
from pathlib import Path
from urllib.parse import urlsplit, unquote
import xml.etree.ElementTree as ET
from collections import defaultdict
import re

NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'
TAG = '{' + NS + '}'
MAX_URLS = 50000
MAX_BYTES = 50 * 1024 * 1024
ET.register_namespace('', NS)


def local_file(root, base, url):
    u = urlsplit(url)
    if u.scheme != 'https' or u.netloc != urlsplit(base).netloc or u.query or u.fragment:
        raise ValueError('Noncanonical sitemap URL: ' + url)
    rel = unquote(u.path).lstrip('/')
    path = root / (rel + 'index.html' if not rel or rel.endswith('/') else rel)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Sitemap path escapes site')
    return path


def read_urlset(root):
    """Read either a legacy urlset or a same-host local sitemap index."""
    root = Path(root)
    start = ET.parse(root / 'sitemap.xml').getroot()
    if start.tag == TAG + 'urlset':
        return ET.ElementTree(start)
    if start.tag != TAG + 'sitemapindex':
        raise ValueError('Invalid sitemap root')
    base = 'https://' + (root / 'CNAME').read_text().strip()
    flat = ET.Element(TAG + 'urlset')
    for entry in start.findall(TAG + 'sitemap'):
        url = entry.findtext(TAG + 'loc')
        file = local_file(root, base, url)
        shard = ET.parse(file).getroot()
        if shard.tag != TAG + 'urlset':
            raise ValueError('Nested or invalid sitemap index')
        flat.extend(list(shard))
    return ET.ElementTree(flat)


def xml(node):
    ET.indent(node, space='  ')
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(node, encoding='unicode') + '\n'


def render_sitemaps(urls, base, max_urls=MAX_URLS, max_bytes=MAX_BYTES, group_for_url=None):
    """Split deterministically by URL count AND encoded size; never invent lastmod."""
    if not 1 <= max_urls <= MAX_URLS or not 200 <= max_bytes <= MAX_BYTES:
        raise ValueError('Unsafe sitemap limits')
    groups = defaultdict(list)
    for url in sorted(set(urls)):
        local_file(Path('/tmp/sitemap-validation'), base, url)
        parts = urlsplit(url).path.strip('/').split('/')
        group = group_for_url(url) if group_for_url else 'kaynaklar' if parts[0] in {'kutuphane', 'kaynak', 'kaynak-detay'} else 'konular' if parts[0] == 'konu' else 'sayfalar'
        groups[group].append(url)
    outputs = {}; index = ET.Element(TAG + 'sitemapindex')
    for group, values in sorted(groups.items()):
        chunks = []; nodes = []; size = len(xml(ET.Element(TAG+'urlset')).encode())
        for url in values:
            node = ET.Element(TAG+'url'); ET.SubElement(node,TAG+'loc').text=url
            weight = len(ET.tostring(node,encoding='utf-8')) + 20
            if nodes and (len(nodes) == max_urls or size + weight > max_bytes):
                chunks.append(nodes); nodes=[]; size=len(xml(ET.Element(TAG+'urlset')).encode())
            nodes.append(node); size+=weight
        if nodes: chunks.append(nodes)
        for number, chunk in enumerate(chunks,1):
            tree=ET.Element(TAG+'urlset'); tree.extend(chunk); content=xml(tree)
            if len(content.encode()) > max_bytes: raise ValueError('Sitemap byte limit exceeded')
            filename=f'sitemaps/{group}-{number}.xml'; outputs[filename]=content
            entry=ET.SubElement(index,TAG+'sitemap'); ET.SubElement(entry,TAG+'loc').text=base+'/'+filename
    if len(outputs)>MAX_URLS: raise ValueError('Too many sitemap shards')
    outputs['sitemap.xml']=xml(index)
    if len(outputs['sitemap.xml'].encode())>MAX_BYTES: raise ValueError('Sitemap index byte limit exceeded')
    return outputs


def eligible_outputs(root, tree, overrides=None):
    """Existing reviewed inventory plus publisher outputs; no parameter expansion."""
    from seo_engine import Page
    root=Path(root); base='https://'+(root/'CNAME').read_text().strip(); overrides=overrides or {}
    pages={}; excluded={}
    for url in {n.text for n in tree.iter(TAG+'loc') if n.text}:
        try: file=local_file(root,base,url)
        except ValueError: excluded[url]='noncanonical_url'; continue
        key=file.relative_to(root).as_posix()
        source=overrides.get(key)
        if source is None and file.is_file(): source=file.read_text()
        if source is None: excluded[url]='missing_file'; continue
        page=Page(source)
        if page.noindex: excluded[url]='noindex'; continue
        if page.canonicals != [url]: excluded[url]='canonical_mismatch'; continue
        if not page.title or not page.description or len(page.primary_h1)!=1 or len(page.main_text.strip())<150:
            excluded[url]='incomplete_static_content'; continue
        if re.match(r'^(PDF|DOCX?|PPTX?|XLSX?)\s+[^ ]*\.(gov|k12)\.tr',page.title,re.I):
            excluded[url]='filename_title_needs_editorial_review'; continue
        pages[url]=page
    # Same title is not proof of the same document. Keep both routes; hold sitemap
    # promotion until a source-backed title/summary distinguishes the editions.
    # Check the whole canonical inventory, including previously held pages,
    # so a partial publisher cannot silently promote one ambiguous edition.
    titles=defaultdict(set)
    for file in root.rglob('*.html'):
        key=file.relative_to(root).as_posix()
        if set(file.relative_to(root).parts) & {'.git','node_modules','seo','_staging','work'}: continue
        source=overrides.get(key)
        page=Page(source if source is not None else file.read_text())
        if page.noindex or len(page.canonicals)!=1: continue
        url=page.canonicals[0]
        try:
            if local_file(root,base,url).resolve()!=file.resolve(): continue
        except ValueError: continue
        titles[page.title].add(url)
    for url,page in pages.items(): titles[page.title].add(url)
    for members in titles.values():
        if len(members)>1:
            for url in members:
                if url in pages: excluded[url]='ambiguous_title_needs_editorial_review'; pages.pop(url)
    return render_sitemaps(pages,base), excluded
