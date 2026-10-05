"""Resumeable public MEB roster crawl. Absence is unknown, never zero."""
import os, argparse, concurrent.futures, datetime, gzip, hashlib, json, re, sqlite3, time, unicodedata
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlsplit, urlunsplit
from urllib.error import HTTPError
from lxml import html

ROOT=Path(os.environ.get('STAFF_WORK_DIR','work/staff')); ROOT.mkdir(parents=True,exist_ok=True)
def fold(s):
    return ''.join(c for c in unicodedata.normalize('NFD',s.lower().replace('ı','i')) if not unicodedata.combining(c))
def is_counselor(role):
    t=fold(role)
    if re.search(r'sinif|sube|ogrenci rehber|mudur|yonetici',t): return False
    return bool(re.search(r'rehber(?:lik)?\s+(?:ogretmen|alan)|psikolojik\s+danisman|^rehberlik$|\bpdr\b',t))
def parse_roster(text, code, url):
    doc=html.fromstring(text)
    codes=set(re.findall(r'/meb_iys_dosyalar/\d+/\d+/(\d+)/',text))
    if codes and str(code) not in codes:
        return {'status':'institution_mismatch','listed_count':None}
    title=' '.join(doc.xpath('//title/text()'))
    if not any(k in fold(title) for k in ['teskilat','kadromuz','ogretmen','personel']):
        return {'status':'unexpected_page','listed_count':None}
    anchors=doc.xpath('//a[contains(@href,"idari_personel/")]')
    seen={}; permanent=assigned=unspecified=0
    for a in anchors:
        role=a.get('title') or ' '.join(a.xpath('.//span//text()'))
        if not is_counselor(role): continue
        key=re.search(r'_(\d+)\.html',a.get('href',''))
        key=key.group(1) if key else a.get('href')
        if key in seen: continue
        seen[key]=role
        t=fold(role)
        if 'gorevlendir' in t: assigned+=1
        elif 'kadrolu' in t: permanent+=1
        else: unspecified+=1
    # A roster lacking a counselor may be incomplete or outdated.
    n=len(seen)
    return {'status':'listed' if n else 'not_listed','listed_count':n if n else None,
        'permanent_listed':permanent if permanent else None,
        'assigned_listed':assigned if assigned else None,
        'unspecified_listed':unspecified if n else None,
        'employment_complete':bool(n and not unspecified),
        'roster_profiles':len(anchors),'source_url':url,'as_of':None,
        'source_sha256':hashlib.sha256(text.encode()).hexdigest()}
def crawl(row):
    code=str(row['kurum_kodu']).strip()
    base=row.get('web_sitesi','').strip()
    if base and not base.startswith(('https://','http://')): base='https://'+base
    parts=urlsplit(base)
    if not (parts.hostname or '').endswith('.meb.k12.tr'):
        return code,{'status':'no_official_website','listed_count':None}
    url=urlunsplit((parts.scheme,parts.netloc,'/tema/teskilat.php','',''))
    stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        req=Request(url,headers={'User-Agent':'PDRKampus-public-roster-research/1.0 (+https://pdrkampus.com/)'})
        with urlopen(req,timeout=10) as response:
            final=response.url
            if not (urlsplit(final).hostname or '').endswith('.meb.k12.tr'):
                raise ValueError('external_redirect')
            raw=response.read(1500001)
            if len(raw)>1500000: raise ValueError('oversized_page')
            charset=response.headers.get_content_charset() or 'utf-8'
            text=raw.decode(charset,errors='replace')
        result=parse_roster(text,code,final)
    except HTTPError as e:
        result={'status':'http_'+str(e.code),'listed_count':None,'source_url':url}
        if e.code==429: time.sleep(30)
    except Exception as e:
        result={'status':'access_error','listed_count':None,'source_url':url,'error_type':type(e).__name__}
    result['checked_at']=stamp
    time.sleep(.15)
    return code,result
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int,default=0);ap.add_argument('--workers',type=int,default=12)
    args=ap.parse_args()
    p=json.loads(gzip.decompress(Path('data/schools-v1.json.gz').read_bytes()))
    rows=[dict(zip(p['columns'],r)) for r in p['rows']]
    db=sqlite3.connect(ROOT/'staff-crawl.sqlite')
    db.execute('create table if not exists results(code text primary key, payload text not null)')
    seed=Path('data/staff-scan-seed.json.gz')
    if seed.exists():
        for code,payload in json.loads(gzip.decompress(seed.read_bytes())).items():
            db.execute('insert or ignore into results values (?,?)',(code,json.dumps(payload,ensure_ascii=False)))
        db.commit()
    done={x[0] for x in db.execute('select code from results')}
    todo=[r for r in rows if str(r['kurum_kodu']).strip() not in done]
    if args.limit:todo=todo[:args.limit]
    print(json.dumps({'start':len(done),'queued':len(todo),'target':len(rows)},ensure_ascii=False),flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(crawl,r):r for r in todo}
        for i,f in enumerate(concurrent.futures.as_completed(futures),1):
            code,result=f.result()
            db.execute('insert or replace into results values (?,?)',(code,json.dumps(result,ensure_ascii=False)))
            if i%100==0:
                db.commit()
                print(json.dumps({'finished_this_run':i,'scanned':len(done)+i,'listed':db.execute("select count(*) from results where json_extract(payload,'$.status')='listed'").fetchone()[0]},ensure_ascii=False),flush=True)
        db.commit()
    print('COMPLETE',flush=True)
if __name__=='__main__':main()
