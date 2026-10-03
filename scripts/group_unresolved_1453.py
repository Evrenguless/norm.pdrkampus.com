from __future__ import annotations

import csv, json, re, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

DATA=Path('data')
HEADERS=['il','ilce','okul_adi','kurum_kodu','okul_turu','web_sitesi','adres','telefon','harita','cekim_tarihi','ogrenci_sayisi','ogrenci_sayilari','durum','kaynak_url','kontrol_tarihi','egitim_yili','kanit']
EXCLUDE=['rehberlik ve arastirma','rehberlik arastirma','halk egitim','halk egitimi','ogretmenevi','aksam sanat','milli egitim mudurlugu','bilim ve sanat merkezi','olgunlasma enstitusu','hizmet ici egitim','bakanlik merkez','yurt disi','yurtdisi','mesleki egitim merkezi','meslek egitim merkezi']

def norm(s):
    s=(s or '').strip().lower().replace('ı','i')
    s=unicodedata.normalize('NFKD',s)
    s=''.join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r'[^a-z0-9]+',' ',s).strip()

def nums(v):
    if v is None:return []
    out=[]
    for x in re.findall(r'\d+',str(v).replace('.','')):
        n=int(x)
        if 0<=n<=10000:out.append(n)
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

def raw_values(r):
    return [v for v in nums(r.get('ogrenci_sayisi'))+nums(r.get('ogrenci_sayilari')) if v>0]

def override_values(code,schools):
    o=schools.get(code) or {}; vals=nums(o.get('value'))
    for v in o.get('observed_values') or []: vals+=nums(v)
    return [v for v in vals if v>0]

def eligible(r):
    blob=norm((r.get('okul_turu') or '')+' '+(r.get('okul_adi') or ''))
    if any(x in blob for x in EXCLUDE): return False
    return bool((r.get('kurum_kodu') or '').strip() and (r.get('okul_adi') or '').strip())

def level(r):
    b=norm((r.get('okul_turu') or '')+' '+(r.get('okul_adi') or ''))
    if 'anaokulu' in b or 'ana okulu' in b: return 'Anaokulu'
    if 'ilkokul' in b: return 'İlkokul'
    if 'ortaokul' in b: return 'Ortaokul'
    if 'ozel egitim' in b: return 'Özel Eğitim'
    if 'lise' in b or 'anadolu' in b or 'fen lisesi' in b or 'sosyal bilimler' in b: return 'Lise'
    return 'Diğer norm kapsamı'

def inferred_reason(r, known):
    code=(r.get('kurum_kodu') or '').strip()
    if code in known: return known[code]
    ev=' '.join([r.get('ogrenci_sayisi') or '',r.get('ogrenci_sayilari') or '',r.get('kanit') or ''])
    evn=norm(ev); durum=norm(r.get('durum')); url=(r.get('web_sitesi') or '').strip()
    # Explicit published zero/dash evidence.
    if re.search(r'ogrenci\s+sayisi\s*[:\-]?\s*0(?:\D|$)', evn) or (str(r.get('ogrenci_sayisi') or '').strip() in {'0','-'}):
        return 'published_zero_or_dash'
    if not url: return 'no_usable_url'
    if any(x in durum for x in ['timeout','erisim','ulas','hata','403','429']): return 'site_unreachable_or_blocked'
    return 'student_field_not_found_or_unpublished'

def main():
    overrides=json.loads((DATA/'student-overrides.json').read_text(encoding='utf-8'))
    schools=overrides.get('schools',{})
    scan=json.loads((DATA/'student-scan-summary.json').read_text(encoding='utf-8'))
    known={str(k):v.get('reason') for k,v in (scan.get('unresolved') or {}).items() if v.get('reason')}
    rows=load_rows(); scoped=[r for r in rows if eligible(r)]
    targets=[]
    for r in scoped:
        code=(r.get('kurum_kodu') or '').strip()
        if not(raw_values(r)+override_values(code,schools)): targets.append(r)
    by_level=Counter(); by_type=Counter(); by_reason=Counter(); cross=defaultdict(Counter)
    for r in targets:
        lv=level(r); typ=(r.get('okul_turu') or 'Belirsiz').strip() or 'Belirsiz'; rs=inferred_reason(r,known)
        by_level[lv]+=1; by_type[typ]+=1; by_reason[rs]+=1; cross[lv][rs]+=1
    out={
      'all_rows':len(rows),'school_scope_rows':len(scoped),'targets':len(targets),
      'by_level':dict(by_level.most_common()),
      'by_school_type':dict(by_type.most_common()),
      'by_reason':dict(by_reason.most_common()),
      'level_x_reason':{k:dict(v) for k,v in sorted(cross.items())},
      'reason_method_note':'student-scan-summary reason is used where preserved; otherwise reason is conservatively inferred from current CSV fields (published 0/dash, missing URL, explicit access/block status, or student field not found/unpublished).',
    }
    (DATA/'unresolved-1453-breakdown.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
