from pathlib import Path
import csv, json, gzip, io
root = Path(__file__).resolve().parents[1]
columns = ["il","ilce","okul_adi","kurum_kodu","okul_turu","web_sitesi","cekim_tarihi","ogrenci_sayisi","ogrenci_sayilari","durum","kaynak_url","kontrol_tarihi","egitim_yili","kanit"]
text = '\n'.join(p.read_text(encoding='utf-8-sig') for p in sorted((root/'data').glob('chunk-*.csv')))
rows = [[r.get(k,'') for k in columns] for r in csv.DictReader(io.StringIO(text)) if any(r.values())]
keys = {'value','verified','note','observed_values','student_count_status','student_count_label','updated_at','manual_reviewed_at','source_url','source','sources'}
payload = json.loads((root/'data/student-overrides.json').read_text())
schools = {code:{k:v for k,v in r.items() if k in keys} for code,r in payload['schools'].items()}
for r in schools.values():
    if 'sources' in r: r['sources'] = [{k:v for k,v in s.items() if k in {'url','values','updated_at','checked_at'}} for s in r['sources']]
for name,data in [('schools-v1',{'version':1,'columns':columns,'rows':rows}),('overrides-v1',{'meta':payload['meta'],'schools':schools})]:
    raw = json.dumps(data,ensure_ascii=False,separators=(',',':')).encode()
    (root/'data'/f'{name}.json.gz').write_bytes(gzip.compress(raw,compresslevel=9,mtime=0))
print(f'{len(rows)} schools; {len(schools)} overrides')
