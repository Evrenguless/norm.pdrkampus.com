from __future__ import annotations
import csv,json,re,unicodedata,urllib.parse
from pathlib import Path
DATA=Path('data')
HEADERS=['il','ilce','okul_adi','kurum_kodu','okul_turu','web_sitesi','adres','telefon','harita','cekim_tarihi','ogrenci_sayisi','ogrenci_sayilari','durum','kaynak_url','kontrol_tarihi','egitim_yili','kanit']
EXCLUDE=['rehberlik ve arastirma','rehberlik arastirma','halk egitim','halk egitimi','ogretmenevi','aksam sanat','milli egitim mudurlugu','bilim ve sanat merkezi','olgunlasma enstitusu','hizmet ici egitim','bakanlik merkez','yurt disi','yurtdisi','mesleki egitim merkezi','meslek egitim merkezi']
def norm(s):
 s=(s or '').strip().lower().replace('ı','i'); s=unicodedata.normalize('NFKD',s); s=''.join(ch for ch in s if not unicodedata.combining(ch)); return re.sub(r'[^a-z0-9]+',' ',s).strip()
def nums(v):
 out=[]
 for x in re.findall(r'\d+',str(v or '').replace('.','')):
  n=int(x)
  if 0<=n<=10000: out.append(n)
 return out
def load_rows():
 rows=[]
 for p in sorted(DATA.glob('chunk-*.csv')):
  with p.open(encoding='utf-8-sig',newline='') as f:
   for i,vals in enumerate(csv.reader(f)):
    if not vals: continue
    if i==0 and vals[0].strip().lower()=='il': continue
    if len(vals)<len(HEADERS): vals += ['']*(len(HEADERS)-len(vals))
    elif len(vals)>len(HEADERS): vals=vals[:len(HEADERS)-1]+[','.join(vals[len(HEADERS)-1:])]
    rows.append(dict(zip(HEADERS,vals)))
 return rows
def raw_values(r): return [v for v in nums(r.get('ogrenci_sayisi'))+nums(r.get('ogrenci_sayilari')) if v>0]
def override_values(code,schools):
 o=schools.get(code) or {}; vals=nums(o.get('value'))
 for v in o.get('observed_values') or []: vals += nums(v)
 return [v for v in vals if v>0]
def eligible(r):
 b=norm((r.get('okul_turu') or '')+' '+(r.get('okul_adi') or ''))
 return not any(x in b for x in EXCLUDE) and bool((r.get('kurum_kodu') or '').strip() and (r.get('okul_adi') or '').strip())
def level(r):
 b=norm((r.get('okul_turu') or '')+' '+(r.get('okul_adi') or ''))
 if 'anaokulu' in b or 'ana okulu' in b:return 'Anaokulu'
 if 'ilkokul' in b:return 'İlkokul'
 if 'ortaokul' in b:return 'Ortaokul'
 if 'ozel egitim' in b:return 'Özel Eğitim'
 if 'lise' in b or 'anadolu' in b or 'fen lisesi' in b or 'sosyal bilimler' in b:return 'Lise'
 return 'Diğer norm kapsamı'
def reason(r,known):
 code=(r.get('kurum_kodu') or '').strip()
 if code in known:return known[code]
 ev=' '.join([r.get('ogrenci_sayisi') or '',r.get('ogrenci_sayilari') or '',r.get('kanit') or '']); evn=norm(ev); durum=norm(r.get('durum')); url=(r.get('web_sitesi') or '').strip()
 if re.search(r'ogrenci\s+sayisi\s*[:\-]?\s*0(?:\D|$)',evn) or str(r.get('ogrenci_sayisi') or '').strip() in {'0','-'}: return 'published_zero_or_dash'
 if not url:return 'no_usable_url'
 if any(x in durum for x in ['timeout','erisim','ulas','hata','403','429']):return 'site_unreachable_or_blocked'
 return 'student_field_not_found_or_unpublished'
def main():
 schools=json.loads((DATA/'student-overrides.json').read_text(encoding='utf-8')).get('schools',{})
 scan=json.loads((DATA/'student-scan-summary.json').read_text(encoding='utf-8'))
 known={str(k):v.get('reason') for k,v in (scan.get('unresolved') or {}).items() if v.get('reason')}
 out=[]
 for r in load_rows():
  if not eligible(r): continue
  code=(r.get('kurum_kodu') or '').strip()
  if raw_values(r)+override_values(code,schools): continue
  name=(r.get('okul_adi') or '').strip(); il=(r.get('il') or '').strip(); ilce=(r.get('ilce') or '').strip(); web=(r.get('web_sitesi') or '').strip()
  search_q=f'"{name}" "{ilce}" "{il}" öğrenci sayısı'
  out.append({
   'kurum_kodu':code,'okul_adi':name,'il':il,'ilce':ilce,
   'kademe':level(r),'okul_turu':(r.get('okul_turu') or 'Belirsiz').strip() or 'Belirsiz',
   'neden':reason(r,known),'meb_url':web or f'https://{code}.meb.k12.tr/',
   'kaynak_url':(r.get('kaynak_url') or '').strip(),
   'google_search':'https://www.google.com/search?q='+urllib.parse.quote_plus(search_q)
  })
 out.sort(key=lambda x:(x['kademe'],x['il'],x['ilce'],x['okul_adi']))
 payload={'snapshot_run_id':37121325865,'total':len(out),'records':out}
 (DATA/'unresolved-review-1453.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'total':len(out)},ensure_ascii=False))
 if len(out)!=1453: raise SystemExit(f'Expected 1453, got {len(out)}')
if __name__=='__main__': main()
