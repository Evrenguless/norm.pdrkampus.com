from __future__ import annotations

import csv, io, json, os, re, time, unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

DATA_DIR = Path('data')
OVERRIDES = DATA_DIR / 'student-overrides.json'
OUT = DATA_DIR / 'four-pass-all-missing-summary.json'
HEADERS = {'User-Agent':'Mozilla/5.0 (compatible; PDRKampusNormBot/6.0; +https://norm.pdrkampus.com)'}
TIMEOUT = 12
WORKERS = int(os.getenv('WORKERS','24'))

TRUSTED_EXTERNAL = {
    'anaokullar.com.tr':'C_ANAOKULLAR', 'www.anaokullar.com.tr':'C_ANAOKULLAR',
    'ilkokullar.com':'C_ILKOKULLAR', 'www.ilkokullar.com':'C_ILKOKULLAR',
    'liseler.com.tr':'C_LISELER', 'www.liseler.com.tr':'C_LISELER',
    'okullarhakkinda.com':'C_OKULLARHAKKINDA', 'www.okullarhakkinda.com':'C_OKULLARHAKKINDA',
    'okulailem.com':'C_OKULAILEM', 'www.okulailem.com':'C_OKULAILEM',
}

EXCLUDE_TYPE_PARTS = [
    'rehberlik ve araştırma', 'rehberlik araştırma', 'halk eğitim', 'halk eğitimi',
    'öğretmenevi', 'akşam sanat', 'milli eğitim müdürlüğü', 'millî eğitim müdürlüğü',
    'bilim ve sanat merkezi', 'olgunlaşma enstitüsü', 'hizmet içi eğitim',
    'bakanlık merkez', 'yurt dışı', 'yurtdışı', 'mesleki eğitim merkezi', 'meslekî eğitim merkezi'
]


def norm(s):
    s=(s or '').strip().lower().replace('ı','i')
    s=unicodedata.normalize('NFKD',s)
    s=''.join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r'[^a-z0-9]+',' ',s).strip()


def nums(v):
    if v is None: return []
    out=[]
    for x in re.findall(r'\d+',str(v).replace('.','')):
        n=int(x)
        if 0 <= n <= 10000: out.append(n)
    return out


def raw_values(row):
    vals=[]
    vals += nums(row.get('ogrenci_sayisi'))
    vals += nums(row.get('ogrenci_sayilari'))
    return [v for v in vals if v>0]


def override_values(code, schools):
    o=schools.get(code) or {}
    vals=nums(o.get('value'))
    for v in o.get('observed_values') or []: vals += nums(v)
    return [v for v in vals if v>0]


def school_scope(row):
    t=(row.get('okul_turu') or '').lower()
    name=(row.get('okul_adi') or '').lower()
    if any(x in t for x in EXCLUDE_TYPE_PARTS): return False
    blob=t+' '+name
    keys=['anaokulu','ana okulu','ilkokul','ortaokul','lise','özel eğitim','ozel egitim']
    return any(k in blob for k in keys)


def load_rows():
    rows=[]
    for p in sorted(DATA_DIR.glob('chunk-*.csv')):
        with p.open(encoding='utf-8-sig',newline='') as f: rows.extend(csv.DictReader(f))
    return rows


def load_json(path, default):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except Exception: return default


def extract_count(text):
    if not text: return None
    pats=[
      r'Öğrenci\s+Sayısı\s*[:\-]?\s*(?:Kız\s*\d+\s*Erkek\s*\d+\s*)?(?:Toplam\s*)?(\d{1,5})',
      r'Toplam\s+Öğrenci\s+Sayısı\s*[:\-]?\s*(\d{1,5})',
      r'Öğrenci\s+Sayısı\s*[:\-]?\s*(\d{1,5})',
      r'(\d{1,5})\s+öğrenci\s+(?:ile\s+)?eğitim',
      r'öğrenci\s+mevcudu\s*[:\-]?\s*(\d{1,5})',
    ]
    vals=[]
    for p in pats: vals += [int(x) for x in re.findall(p,text,flags=re.I|re.S)]
    vals=[x for x in vals if 0 < x <= 10000]
    return max(vals) if vals else None


def fetch(url):
    try:
        r=requests.get(url,headers=HEADERS,timeout=TIMEOUT,allow_redirects=True)
        if r.status_code!=200: return {'ok':False,'status':r.status_code,'url':r.url}
        ct=(r.headers.get('content-type') or '').lower()
        if 'pdf' in ct or r.url.lower().endswith('.pdf'):
            try:
                reader=PdfReader(io.BytesIO(r.content))
                text=' '.join((p.extract_text() or '') for p in reader.pages[:80])
                return {'ok':True,'status':200,'url':r.url,'text':text,'pdf':True}
            except Exception:
                return {'ok':False,'status':200,'url':r.url,'pdf_error':True}
        text=BeautifulSoup(r.text,'html.parser').get_text(' ',strip=True)
        return {'ok':True,'status':200,'url':r.url,'text':text,'pdf':False}
    except Exception as e:
        return {'ok':False,'error':type(e).__name__,'url':url}


def strong_match(text,row):
    nt=norm(text); name=norm(row.get('okul_adi')); il=norm(row.get('il')); ilce=norm(row.get('ilce')); code=str(row.get('kurum_kodu') or '')
    if not name or name not in nt: return False
    loc=(il and il in nt) and (ilce and ilce in nt)
    return bool(loc or (code and code in text))


def bing(query):
    url='https://www.bing.com/search?q='+quote_plus(query)+'&count=15'
    try:
        r=requests.get(url,headers=HEADERS,timeout=TIMEOUT)
        if r.status_code!=200: return []
        soup=BeautifulSoup(r.text,'html.parser'); out=[]
        for li in soup.select('li.b_algo'):
            a=li.select_one('h2 a'); p=li.select_one('.b_caption p')
            if not a: continue
            out.append({'url':a.get('href') or '', 'title':a.get_text(' ',strip=True), 'snippet':p.get_text(' ',strip=True) if p else ''})
        return out
    except Exception: return []


def step1_meb_direct(row):
    code=str(row.get('kurum_kodu') or '').strip(); base=(row.get('web_sitesi') or '').strip()
    urls=[]
    if base:
        base=base.rstrip('/')
        urls += [base+'/',base+'/tema/',base+'/tema/okulumuz_hakkinda.php',base+'/okulumuz_hakkinda.html']
    if code:
        b=f'https://{code}.meb.k12.tr'
        urls += [b+'/',b+'/tema/',b+'/tema/okulumuz_hakkinda.php',b+'/okulumuz_hakkinda.html']
    seen=set(); attempts=[]
    for url in urls:
        if url in seen: continue
        seen.add(url); r=fetch(url); attempts.append({'url':url,'status':r.get('status'),'ok':r.get('ok',False)})
        if r.get('ok'):
            c=extract_count(r.get('text',''))
            if c: return {'found':True,'value':c,'source_url':r['url'],'source_type':'A_MEB_SITE','confidence':'A','attempts':attempts}
    return {'found':False,'attempts':attempts}


def step2_official_search(row):
    name=row.get('okul_adi') or ''; code=str(row.get('kurum_kodu') or ''); il=row.get('il') or ''; ilce=row.get('ilce') or ''
    qs=[f'"{name}" "Öğrenci Sayısı" site:meb.k12.tr', f'"{code}" "Öğrenci Sayısı" site:meb.k12.tr', f'"{name}" "{ilce}" "{il}" filetype:pdf MEB']
    checked=[]
    for q in qs:
        hits=bing(q); checked.append({'query':q,'hits':len(hits)})
        for h in hits:
            host=urlparse(h['url']).netloc.lower(); blob=h['title']+' '+h['snippet']
            if 'meb' not in host: continue
            if not (strong_match(blob,row) or code in blob): continue
            r=fetch(h['url'])
            text=r.get('text','') if r.get('ok') else blob
            if strong_match(text or blob,row) or code in (text or blob):
                c=extract_count(text) or extract_count(blob)
                if c: return {'found':True,'value':c,'source_url':r.get('url') or h['url'],'source_type':'B_MEB_SEARCH_OR_PDF','confidence':'B','queries':checked}
        time.sleep(.1)
    return {'found':False,'queries':checked}


def step3_trusted_external(row):
    name=row.get('okul_adi') or ''; il=row.get('il') or ''; ilce=row.get('ilce') or ''
    domains=sorted(set(TRUSTED_EXTERNAL))
    checked=[]
    for domain in domains:
        if domain.startswith('www.'): continue
        q=f'"{name}" "{ilce}" "{il}" site:{domain}'
        hits=bing(q); checked.append({'domain':domain,'hits':len(hits)})
        for h in hits:
            host=urlparse(h['url']).netloc.lower()
            if host not in TRUSTED_EXTERNAL: continue
            r=fetch(h['url']); text=r.get('text','') if r.get('ok') else ''
            if not text or not strong_match(text,row): continue
            c=extract_count(text)
            if c: return {'found':True,'value':c,'source_url':r['url'],'source_type':TRUSTED_EXTERNAL[host],'confidence':'C','checked':checked}
        time.sleep(.08)
    return {'found':False,'checked':checked}


def step4_broad_web(row):
    name=row.get('okul_adi') or ''; il=row.get('il') or ''; ilce=row.get('ilce') or ''; code=str(row.get('kurum_kodu') or '')
    qs=[f'"{name}" "{ilce}" "{il}" öğrenci', f'"{name}" "öğrenci sayısı"', f'"{code}" okul öğrenci']
    checked=[]; candidates=[]
    for q in qs:
        hits=bing(q); checked.append({'query':q,'hits':len(hits)})
        for h in hits:
            blob=h['title']+' '+h['snippet']; c=extract_count(blob)
            if not c or not (strong_match(blob,row) or code in blob): continue
            host=urlparse(h['url']).netloc.lower()
            r=fetch(h['url']); text=r.get('text','') if r.get('ok') else ''
            if text and strong_match(text,row):
                cc=extract_count(text) or c
                if cc:
                    # Broad-web matches are evidence candidates only; do not auto-write into canonical data.
                    candidates.append({'value':cc,'source_url':r.get('url') or h['url'],'domain':host,'confidence':'D','title':h['title'][:180]})
            else:
                candidates.append({'value':c,'source_url':h['url'],'domain':host,'confidence':'D-snippet','title':h['title'][:180]})
        time.sleep(.08)
    return {'found':False,'checked':checked,'candidates':candidates[:10]}


def scan_one(row):
    trace={'institution_code':str(row.get('kurum_kodu') or '').strip(),'school':row.get('okul_adi'),'province':row.get('il'),'district':row.get('ilce'),'school_type':row.get('okul_turu'),'steps':{}}
    s1=step1_meb_direct(row); trace['steps']['1_meb_direct']=s1
    if s1.get('found'): trace['result']='found'; trace['accepted']=s1; return trace
    s2=step2_official_search(row); trace['steps']['2_official_search_pdf']=s2
    if s2.get('found'): trace['result']='found'; trace['accepted']=s2; return trace
    s3=step3_trusted_external(row); trace['steps']['3_trusted_external']=s3
    if s3.get('found'): trace['result']='found'; trace['accepted']=s3; return trace
    s4=step4_broad_web(row); trace['steps']['4_broad_web']=s4
    trace['result']='4_adim_tamamlandi_bulunamadi'
    if s4.get('candidates'): trace['result']='4_adim_tamamlandi_dusuk_guvenli_aday_var'
    return trace


def main():
    rows=load_rows(); payload=load_json(OVERRIDES,{'schools':{}}); schools=payload.setdefault('schools',{})
    targets=[]
    for r in rows:
        if not school_scope(r): continue
        code=str(r.get('kurum_kodu') or '').strip()
        vals=raw_values(r)+override_values(code,schools)
        if not vals: targets.append(r)
    print(json.dumps({'school_scope_rows':sum(1 for r in rows if school_scope(r)),'targets':len(targets)},ensure_ascii=False),flush=True)
    results={}; accepted=0; candidates=0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs={ex.submit(scan_one,r):r for r in targets}
        for i,f in enumerate(as_completed(futs),1):
            res=f.result(); code=res['institution_code']; results[code]=res
            hit=res.get('accepted')
            if hit:
                old=schools.get(code) or {}; obs=[]
                for v in old.get('observed_values') or []: obs += nums(v)
                obs += nums(old.get('value')); obs.append(hit['value']); obs=[v for v in obs if v>0]
                final=max(obs)
                schools[code]={**old,'value':final,'verified':True,'observed_values':sorted(set(obs)),'source':hit['source_type'],'source_url':hit['source_url'],'confidence':hit['confidence'],'school':res['school'],'province':res['province'],'district':res['district'],'school_type':res['school_type'],'note':'Dört adımlı eksik veri taramasında doğrulandı; doğrulanabilir değerler içinden en yüksek değer kullanıldı.'}
                accepted += 1
            if res['result'].endswith('aday_var'): candidates += 1
            if i%50==0 or i==len(targets): print(f'scanned {i}/{len(targets)} accepted={accepted} low_conf_candidates={candidates}',flush=True)
    unresolved=sum(1 for r in results.values() if r['result'].startswith('4_adim_tamamlandi'))
    payload.setdefault('meta',{})['four_pass_all_missing_updated_at']=datetime.now(timezone.utc).isoformat()
    OVERRIDES.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    summary={'updated_at':datetime.now(timezone.utc).isoformat(),'scope':'Anaokulu, ilkokul, ortaokul/İHO/YBO, lise türleri ve özel eğitim okulları; RAM ve Mesleki Eğitim Merkezi farklı norm metriği nedeniyle hariç.','targets':len(targets),'accepted':accepted,'low_confidence_candidate_schools':candidates,'four_steps_completed_unresolved':unresolved,'results':results}
    OUT.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ['targets','accepted','low_confidence_candidate_schools','four_steps_completed_unresolved']},ensure_ascii=False),flush=True)

if __name__=='__main__': main()
