import os,sqlite3,json,datetime,collections,gzip
from pathlib import Path
root=Path(os.environ.get('STAFF_WORK_DIR','work/staff'))
db=sqlite3.connect(root/'staff-crawl.sqlite')
results={code:json.loads(p) for code,p in db.execute('select code,payload from results')}
if (root/'staff-seed.json').exists():
    for code,r in json.loads((root/'staff-seed.json').read_text()).items(): results.setdefault(code,r)
keys=['listed_count','permanent_listed','assigned_listed','unspecified_listed','source_url','checked_at','as_of']
schools={code:{k:r.get(k) for k in keys} for code,r in results.items() if r.get('status')=='listed' and r.get('listed_count',0)>0}
meta={'scanned_schools':len(results),'total_schools':55216,'complete':len(results)==55216,'exported_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'statuses':dict(collections.Counter(r['status'] for r in results.values())),'listed_schools':len(schools),'listed_counselors':sum(s['listed_count'] for s in schools.values()),'method':'Public official MEB roster listings; not confirmed staffing. No listing is unknown, never zero.'}
data=json.dumps({'version':1,'meta':meta,'columns':['code']+keys,'rows':[[code]+[s[k] for k in keys] for code,s in schools.items()]},ensure_ascii=False,separators=(',',':')).encode()
Path('data/staff-v1.json').write_bytes(data)
Path('data/staff-v1.json.gz').write_bytes(gzip.compress(data,mtime=0))
print(json.dumps(meta,ensure_ascii=False))
