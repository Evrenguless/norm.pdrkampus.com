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
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; PDRKampusNormBot/6.1; +https://norm.pdrkampus.com)'}
TIMEOUT = 12
WORKERS = int(os.getenv('WORKERS', '24'))

TRUSTED_EXTERNAL = {
    'anaokullar.com.tr':'C_ANAOKULLAR', 'www.anaokullar.com.tr':'C_ANAOKULLAR',
    'ilkokullar.com':'C_ILKOKULLAR', 'www.ilkokullar.com':'C_ILKOKULLAR',
    'liseler.com.tr':'C_LISELER', 'www.liseler.com.tr':'C_LISELER',
    'okullarhakkinda.com':'C_OKULLARHAKKINDA', 'www.okullarhakkinda.com':'C_OKULLARHAKKINDA',
    'okulailem.com':'C_OKULAILEM', 'www.okulailem.com':'C_OKULAILEM',
}

EXCLUDE = [
    'rehberlik ve arastirma', 'rehberlik arastirma', 'halk egitim', 'halk egitimi',
    'ogretmenevi', 'aksam sanat', 'milli egitim mudurlugu', 'bilim ve sanat merkezi',
    'olgunlasma enstitusu', 'hizmet ici egitim', 'bakanlik merkez', 'yurt disi', 'yurtdisi',
    'mesleki egitim merkezi', 'meslek egitim merkezi'
]
INCLUDE = ['anaokulu','ana okulu','ilkokul','ortaokul','imam hatip ortaokulu','yatili bolge ortaokulu','lise','ozel egitim']


def norm(s):
    s=(s or '').strip().lower().replace('ı','i')
    s=unicodedata.normalize('NFKD', s)
    s=''.join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r'[^a-z0-9]+',' ',s).strip()


def nums(v):
    if v is None: return []
    out=[]
    for x in re.findall(r'\d+', str(v).replace('.','')):
        n=int(x)
        if 0 <= n <= 10000: out.append(n)
    return out


def raw_values(row):
    vals=nums(row.get('ogrenci_sayisi'))+nums(row.get('ogrenci_sayilari'))
    return [v for v in vals if v>0]


def override_values(code, schools):
    o=schools.get(code) or {}
    vals=nums(o.get('value'))
    for v in o.get('observed_values') or []: vals += nums(v)
    return [v for v in vals if v>0]


def school_scope(row):
    blob=norm((row.get('okul_turu') or '')+' '+(row.get('okul_adi') or ''))
    if any(x in blob for x in EXCLUDE): return False
    return any(x in blob for x in INCLUDE)


def load_rows():
    rows=[]
    for p in sorted(DATA_DIR.glob('chunk-*.csv')):
        with p.open(encoding='utf-8-sig', newline='') as f:
            rows.extend(csv.DictReader(f))
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
        if r.status_code != 200: return {'ok':False,'status':r.status_code,'url':r.url}
        ct=(r.headers.get('content-type') or '').lower()
        if 'pdf' in ct or r.url.lower().endswith('.pdf'):
            try:
                reader=PdfReader(io.BytesIO(r.content))
                text=' '.join((p.extract_text() or '') for p in reader.pages[:80])
                return {'ok':True,'status':200,'url':r.url,'text':text,'pdf':True}
            except Exception:
                return {'ok':False,'status':200,'url':r.url,'pdf_error':True}
        return {'ok':True,'status':200,'url':r.url,'text':BeautifulSoup(r.text,'html.parser').get_text(' ',strip=True),'pdf':False}
    except Exception as e:
        return {'ok':False,'error':type(e).__name__,'url':url}


def strong_match(text,row):
    nt=norm(text); name=norm(row.get('okul_adi')); il=norm(row.get('il')); ilce=norm(row.get('ilce')); code=str(row.get('kurum_kodu') or '')
    if not name or name not in nt: return False
    return bool((il and il in nt and ilce and ilce in nt) or (code and code in text))


def bing(q):
    try:
        r=requests.get('https://www.bing.com/search?q='+quote_plus(q)+'&count=15',headers=HEADERS,timeout=TIMEOUT)
        if r.status_code != 200: return []
        soup=BeautifulSoup(r.text,'html.parser'); out=[]
        for li in soup.select('li.b_algo'):
            a=li.select_one('h2 a'); p=li.select_one('.b_caption p')
            if a: out.append({'url':a.get('href') or '', 'title':a.get_text(' ',strip=True), 'snippet':p.get_text(' ',strip=True) if p else ''})
        return out
    except Exception: return []


def step1(row):
    code=str(row.get('kurum_kodu') or '').strip(); base=(row.get('web_sitesi') or '').strip(); urls=[]
    if base:
        b=base.rstrip('/'); urls += [b+'/',b+'/tema/',b+'/tema/okulumuz_hakkinda.php',b+'/okulumuz_hakkinda.html']
    if code:
        b=f'https://{code}.meb.k12.tr'; urls += [b+'/',b+'/tema/',b+'/tema/okulumuz_hakkinda.php',b+'/okulumuz_hakkinda.html']
    attempts=[]; seen=set()
    for u in urls:
        if u in seen: continue
        seen.add(u); r=fetch(u); attempts.append({'url':u,'ok':r.get('ok',False),'status':r.get('status')})
        if r.get('ok'):
            c=extract_count(r.get('text',''))
            if c: return {'found':True,'value':c,'source_url':r['url'],'source_type':'A_MEB_SITE','confidence':'A','attempts':attempts}
    return {'found':False,'attempts':attempts}


def step2(row):
    name=row.get('okul_adi') or ''; code=str(row.get('kurum_kodu') or ''); il=row.get('il') or ''; ilce=row.get('ilce') or ''
    qs=[f'"{name}" "Öğrenci Sayısı" site:meb.k12.tr',f'"{code}" "Öğrenci Sayısı" site:meb.k12.tr',f'"{name}" "{ilce}" "{il}" filetype:pdf MEB']
    checked=[]
    for q in qs:
        hits=bing(q); checked.append({'query':q,'hits':len(hits)})
        for h in hits:
            host=urlparse(h['url']).netloc.lower(); blob=h['title']+' '+h['snippet']
            if 'meb' not in host or not (strong_match(blob,row) or code in blob): continue
            r=fetch(h['url']); text=r.get('text','') if r.get('ok') else blob
            if strong_match(text or blob,row) or code in (text or blob):
                c=extract_count(text) or extract_count(blob)
                if c: return {'found':True,'value':c,'source_url':r.get('url') or h['url'],'source_type':'B_MEB_SEARCH_OR_PDF','confidence':'B','queries':checked}
        time.sleep(.08)
    return {'found':False,'queries':checked}


def step3(row):
    name=row.get('okul_adi') or ''; il=row.get('il') or ''; ilce=row.get('ilce') or ''; checked=[]
    for domain in sorted(set(d for d in TRUSTED_EXTERNAL if not d.startswith('www.'))):
        q=f'"{name}" "{ilce}" "{il}" site:{domain}'; hits=bing(q); checked.append({'domain':domain,'hits':len(hits)})
        for h in hits:
            host=urlparse(h['url']).netloc.lower()
            if host not in TRUSTED_EXTERNAL: continue
            r=fetch(h['url']); text=r.get('text','') if r.get('ok') else ''
            if text and strong_match(text,row):
                c=extract_count(text)
                if c: return {'found':True,'value':c,'source_url':r['url'],'source_type':TRUSTED_EXTERNAL[host],'confidence':'C','checked':checked}
        time.sleep(.06)
    return {'found':False,'checked':checked}


def step4(row):
    name=row.get('okul_adi') or ''; il=row.get('il') or ''; ilce=row.get('ilce') or ''; code=str(row.get('kurum_kodu') or '')
    qs=[f'"{name}" "{ilce}" "{il}" öğrenci',f'"{name}" "öğrenci sayısı"',f'"{code}" okul öğrenci']; checked=[]; candidates=[]
    for q in qs:
        hits=bing(q); checked.append({'query':q,'hits':len(hits)})
        for h in hits:
            blob=h['title']+' '+h['snippet']; c=extract_count(blob)
            if not c or not (strong_match(blob,row) or code in blob): continue
            host=urlparse(h['url']).netloc.lower(); r=fetch(h['url']); text=r.get('text','') if r.get('ok') else ''
            if text and strong_match(text,row):
                cc=extract_count(text) or c
                if cc: candidates.append({'value':cc,'source_url':r.get('url') or h['url'],'domain':host,'confidence':'D'})
            else: candidates.append({'value':c,'source_url':h['url'],'domain':host,'confidence':'D-snippet'})
        time.sleep(.06)
    return {'found':False,'checked':checked,'candidates':candidates[:10]}


def scan_one(row):
    trace={'institution_code':str(row.get('kurum_kodu') or '').strip(),'school':row.get('okul_adi'),'province':row.get('il'),'district':row.get('ilce'),'school_type':row.get('okul_turu'),'steps':{}}
    for key,fn in [('1_meb_direct',step1),('2_official_search_pdf',step2),('3_trusted_external',step3)]:
        s=fn(row); trace['steps'][key]=s
        if s.get('found'): trace['result']='found'; trace['accepted']=s; return trace
    s4=step4(row); trace['steps']['4_broad_web']=s4
    trace['result']='4_adim_tamamlandi_dusuk_guvenli_aday_var' if s4.get('candidates') else '4_adim_tamamlandi_bulunamadi'
    return trace


def main():
    rows=load_rows(); payload=load_json(OVERRIDES,{'schools':{}}); schools=payload.setdefault('schools',{})
    scoped=[r for r in rows if school_scope(r)]
    targets=[]
    for r in scoped:
        code=str(r.get('kurum_kodu') or '').strip()
        if not (raw_values(r)+override_values(code,schools)): targets.append(r)
    print(json.dumps({'all_rows':len(rows),'school_scope_rows':len(scoped),'targets':len(targets)},ensure_ascii=False),flush=True)
    if len(rows) < 50000: raise RuntimeError(f'Safety check failed: expected >50k rows, got {len(rows)}')
    if len(scoped) < 30000: raise RuntimeError(f'Safety check failed: expected >30k school-scope rows, got {len(scoped)}')
    if not (1000 <= len(targets) <= 5000): raise RuntimeError(f'Safety check failed: expected 1000-5000 unresolved school targets, got {len(targets)}')

    results={}; accepted=0; candidates=0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs={ex.submit(scan_one,r):r for r in targets}
        for i,f in enumerate(as_completed(futs),1):
            res=f.result(); code=res['institution_code']; results[code]=res; hit=res.get('accepted')
            if hit:
                old=schools.get(code) or {}; obs=[]
                for v in old.get('observed_values') or []: obs += nums(v)
                obs += nums(old.get('value')); obs.append(hit['value']); obs=[v for v in obs if v>0]; final=max(obs)
                schools[code]={**old,'value':final,'verified':True,'observed_values':sorted(set(obs)),'source':hit['source_type'],'source_url':hit['source_url'],'confidence':hit['confidence'],'school':res['school'],'province':res['province'],'district':res['district'],'school_type':res['school_type'],'note':'Dört adımlı eksik veri taramasında doğrulandı; doğrulanabilir değerler içinden en yüksek değer kullanıldı.'}
                accepted += 1
            if res['result'].endswith('aday_var'): candidates += 1
            if i%100==0 or i==len(targets): print(f'scanned {i}/{len(targets)} accepted={accepted} low_conf_candidates={candidates}',flush=True)
    unresolved=sum(1 for x in results.values() if x['result'].startswith('4_adim_tamamlandi'))
    payload.setdefault('meta',{})['four_pass_all_missing_updated_at']=datetime.now(timezone.utc).isoformat()
    OVERRIDES.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    summary={'updated_at':datetime.now(timezone.utc).isoformat(),'all_rows':len(rows),'school_scope_rows':len(scoped),'targets':len(targets),'accepted':accepted,'low_confidence_candidate_schools':candidates,'four_steps_completed_unresolved':unresolved,'status_label':'4_adim_tamamlandi_bulunamadi','results':results}
    OUT.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ['all_rows','school_scope_rows','targets','accepted','low_confidence_candidate_schools','four_steps_completed_unresolved']},ensure_ascii=False),flush=True)

if __name__=='__main__': main()
