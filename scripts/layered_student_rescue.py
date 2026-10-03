from __future__ import annotations

import csv, json, os, re, time, unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup

DATA_DIR = Path('data')
OVERRIDES = DATA_DIR / 'student-overrides.json'
OUT = DATA_DIR / 'layered-rescue-summary.json'
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; PDRKampusNormBot/5.0; +https://norm.pdrkampus.com)'}
TIMEOUT = 10
WORKERS = 16
TARGET_GROUP = os.getenv('TARGET_GROUP', 'kindergarten').strip().lower()


def norm(s):
    s = (s or '').strip().lower().replace('ı','i')
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r'[^a-z0-9]+',' ',s).strip()


def load_rows():
    rows=[]
    for p in sorted(DATA_DIR.glob('chunk-*.csv')):
        with p.open(encoding='utf-8-sig', newline='') as f:
            rows.extend(csv.DictReader(f))
    return rows


def load_json(path, default):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except Exception: return default


def nums(v):
    if v is None: return []
    return [int(x) for x in re.findall(r'\d+', str(v).replace('.','')) if 0 <= int(x) <= 10000]


def row_current(row, overrides):
    vals=[]
    vals += nums(row.get('ogrenci_sayisi'))
    vals += nums(row.get('ogrenci_sayilari'))
    o=overrides.get(str(row.get('kurum_kodu') or '').strip()) or {}
    vals += nums(o.get('value'))
    for v in o.get('observed_values') or []: vals += nums(v)
    vals=[v for v in vals if v>0]
    return max(vals) if vals else None


def is_target(row):
    t=(row.get('okul_turu') or '').strip()
    if TARGET_GROUP=='kindergarten': return t=='Anaokulu'
    if TARGET_GROUP=='primary': return t=='İlkokul'
    if TARGET_GROUP=='middle': return t in {'Ortaokul','İmam Hatip Ortaokulu','Yatılı Bölge Ortaokulu'}
    if TARGET_GROUP=='special': return t=='Özel Eğitim Kurumu'
    return False


def extract_count(text):
    pats=[
      r'Öğrenci\s+Sayısı\s*[:\-]?\s*(?:Kız\s*\d+\s*Erkek\s*\d+\s*)?(?:Toplam\s*)?(\d{1,5})',
      r'Öğrenci\s+Sayısı\s*[:\-]?\s*(\d{1,5})',
      r'Toplam\s+Öğrenci\s+Sayısı\s*[:\-]?\s*(\d{1,5})',
      r'(\d{1,5})\s+öğrenci\s+(?:ile\s+)?eğitim',
    ]
    vals=[]
    for p in pats:
        vals += [int(x) for x in re.findall(p, text, flags=re.I|re.S)]
    vals=[x for x in vals if 0<x<=10000]
    return max(vals) if vals else None


def fetch_text(url):
    try:
        r=requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code!=200: return None
        ct=(r.headers.get('content-type') or '').lower()
        if 'pdf' in ct or url.lower().endswith('.pdf'):
            return None  # PDF discovery is recorded as candidate; parsing requires separate extractor.
        return BeautifulSoup(r.text,'html.parser').get_text(' ', strip=True)
    except Exception:
        return None


def meb_direct(row):
    code=str(row.get('kurum_kodu') or '').strip()
    for url in [f'https://{code}.meb.k12.tr/', f'https://{code}.meb.k12.tr/tema/']:
        text=fetch_text(url)
        if not text: continue
        c=extract_count(text)
        if c: return {'value':c,'source_url':url,'source_type':'A_MEB_SITE','confidence':'A'}
    return None


def search_bing(row):
    name=row.get('okul_adi') or ''; il=row.get('il') or ''; ilce=row.get('ilce') or ''; code=str(row.get('kurum_kodu') or '').strip()
    queries=[
      f'"{name}" "Öğrenci Sayısı" site:meb.k12.tr',
      f'"{code}" "Öğrenci Sayısı" site:meb.k12.tr',
      f'"{name}" {ilce} {il} "Öğrenci Sayısı"',
    ]
    candidates=[]
    for q in queries:
        url='https://www.bing.com/search?q='+quote_plus(q)+'&count=10'
        try:
            r=requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code!=200: continue
            soup=BeautifulSoup(r.text,'html.parser')
            for li in soup.select('li.b_algo'):
                a=li.select_one('h2 a'); p=li.select_one('.b_caption p')
                if not a: continue
                href=a.get('href') or ''; snippet=p.get_text(' ',strip=True) if p else ''
                blob=' '.join([a.get_text(' ',strip=True), snippet])
                nb=norm(blob)
                if norm(name) not in nb and code not in blob: continue
                if norm(il) not in nb and norm(ilce) not in nb: continue
                c=extract_count(blob)
                host=urlparse(href).netloc.lower()
                if 'meb.k12.tr' in host:
                    if href.lower().endswith('.pdf') or 'meb_iys_dosyalar' in href:
                        candidates.append({'value':c,'source_url':href,'source_type':'B_MEB_PDF_CANDIDATE','confidence':'B-candidate','snippet':blob[:500]})
                    else:
                        text=fetch_text(href)
                        cc=extract_count(text or '') or c
                        if cc: return {'value':cc,'source_url':href,'source_type':'A_MEB_SEARCH_HIT','confidence':'A'}
                elif c:
                    candidates.append({'value':c,'source_url':href,'source_type':'D_SEARCH_SNIPPET','confidence':'D','snippet':blob[:500]})
        except Exception:
            pass
        time.sleep(.2)
    return {'candidates':candidates} if candidates else None


def scan(row, overrides):
    code=str(row.get('kurum_kodu') or '').strip()
    if row_current(row, overrides): return code, None
    hit=meb_direct(row)
    if hit: return code, {'accepted':hit,'row':row}
    other=search_bing(row)
    return code, {'accepted':None,'candidates':(other or {}).get('candidates',[]),'row':row}


def main():
    rows=load_rows(); payload=load_json(OVERRIDES, {'schools':{}}); schools=payload.setdefault('schools',{})
    targets=[r for r in rows if is_target(r) and not row_current(r, schools)]
    expected={'kindergarten':410}.get(TARGET_GROUP)
    if expected is not None and len(targets)>expected:
        raise RuntimeError(f'safety check: expected at most {expected} unresolved {TARGET_GROUP}, got {len(targets)}')
    accepted={}; candidates={}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs=[ex.submit(scan,r,schools) for r in targets]
        for i,f in enumerate(as_completed(futs),1):
            code,res=f.result()
            if not res: continue
            if res.get('accepted'):
                h=res['accepted']; old=schools.get(code) or {}; observed=[]
                for v in old.get('observed_values') or []: observed += nums(v)
                observed += nums(old.get('value')); observed.append(h['value'])
                value=max([v for v in observed if v>0])
                schools[code]={**old,'value':value,'verified':True,'observed_values':sorted(set(observed)),'source':h['source_type'],'source_url':h['source_url'],'confidence':h['confidence'],'note':f"Katmanlı taramada {h['source_type']} kaynağında {h['value']} öğrenci bulundu; mevcut doğrulanmış değerlerle karşılaştırılıp en yüksek {value} kullanıldı."}
                accepted[code]={'school':res['row'].get('okul_adi'),'province':res['row'].get('il'),'district':res['row'].get('ilce'),**h,'final_value':value}
            elif res.get('candidates'):
                candidates[code]={'school':res['row'].get('okul_adi'),'province':res['row'].get('il'),'district':res['row'].get('ilce'),'items':res['candidates']}
            if i%50==0: print('scanned',i,'/',len(targets),'accepted',len(accepted),'candidates',len(candidates), flush=True)
    payload['meta']=payload.get('meta') or {}; payload['meta']['layered_rescue_updated_at']=datetime.now(timezone.utc).isoformat()
    OVERRIDES.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    out={'target_group':TARGET_GROUP,'targets':len(targets),'accepted':len(accepted),'candidate_only':len(candidates),'remaining_without_accepted':len(targets)-len(accepted),'accepted_schools':accepted,'candidate_schools':candidates}
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:out[k] for k in ['target_group','targets','accepted','candidate_only','remaining_without_accepted']},ensure_ascii=False))

if __name__=='__main__': main()
