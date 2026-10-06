#!/usr/bin/env python3
"""Read-only institution coverage pilot. Never calculates student/norm/staff figures."""
import argparse,gzip,json,hashlib,html,re,unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from datetime import date
from seo_engine import protected,safe_output
BASE='https://norm.pdrkampus.com'
ALLOWED=('il','ilce','okul_turu','okul_adi','kaynak_url','egitim_yili')
def slug(value):
 return re.sub(r'[^a-z0-9]+','-',unicodedata.normalize('NFKD',value.replace('ı','i')).encode('ascii','ignore').decode().lower()).strip('-')
def official_url(value):
 try:
  p=urlsplit(value)
  return p.scheme=='https' and not p.username and not p.password and bool(re.search(r'(^|\.)meb\.(gov|k12)\.tr$',p.hostname or ''))
 except ValueError:return False

def load_rows(root):
 path=root/'data/schools-v1.json.gz';payload=json.loads(gzip.decompress(path.read_bytes()))
 if payload.get('version')!=1 or not payload.get('rows'):raise ValueError('Unsupported or empty dataset')
 columns=payload['columns']
 if not all(key in columns for key in ALLOWED):raise ValueError('Coverage columns missing')
 positions={key:columns.index(key) for key in ALLOWED}
 # No student numbers, person names, phone/address, evidence text or model coefficients leave this function.
 return [{key:str(row[pos] or '') for key,pos in positions.items()} for row in payload['rows']],hashlib.sha256(path.read_bytes()).hexdigest()

def plans(rows,config):
 seen=set();out=[]
 declaration=config.get('education_period_declaration',{})
 declared=declaration.get('period','')
 if declared and (not re.fullmatch(r'20\d{2}-20\d{2}',declared) or int(declared[5:])!=int(declared[:4])+1 or declaration.get('basis')!='user_confirmation' or declaration.get('scope')!='current_norm_institution_records' or not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',declaration.get('confirmed_on',''))):raise ValueError('Invalid period declaration')
 if len(config['provinces'])>5 or sum(len(x) for x in config['provinces'].values())>10:raise ValueError('Pilot exceeds 5 province / 10 district limit')
 for province,districts in config['provinces'].items():
  for district in [None]+districts:
   matching=[r for r in rows if r['il']==province and (district is None or r['ilce']==district)]
   route='/il/'+slug(province)+'/'+(slug(district)+'/' if district else '')
   if route in seen:raise ValueError('Duplicate slug '+route)
   seen.add(route)
   periods=Counter(r['egitim_yili'] for r in matching if r['egitim_yili'].strip())
   sources=[r for r in matching if official_url(r['kaynak_url'])]
   types=Counter(r['okul_turu'] or 'Belirtilmemiş' for r in matching)
   issues=[]
   if not matching:issues.append('no_matching_institutions')
   if not sources:issues.append('no_official_source_links')
   if config.get('require_education_period') and len(periods)==0 and not declared:issues.append('education_period_missing')
   if len(periods)>1:issues.append('mixed_education_periods')
   if matching and sum(periods.values())!=len(matching):
    if periods and not declared:issues.append('education_period_incomplete')
   if declared and any(value!=declared for value in periods):issues.append('education_period_conflicts_with_declaration')
   effective_period=declared or (next(iter(periods)) if len(periods)==1 and sum(periods.values())==len(matching) else '')
   source_count=len(sources);count=len(matching)
   score=(20 if count else 0)+(20 if sources else 0)+(15 if len(types)>=2 else 0)+15+10+10+(10 if count and effective_period and not any('education_period' in issue for issue in issues) else 0)
   if score<config['minimum_score']:issues.append('below_quality_threshold')
   out.append({'province':province,'district':district,'route':route,'record_count':count,'types':dict(types),'district_counts':dict(Counter(r['ilce'] for r in matching)),
    'source_url_count':source_count,'missing_or_unusable_source_url_count':count-source_count,'periods':dict(periods),'effective_period':effective_period,'period_declaration':declaration if declared else None,
    'source_examples':[{'institution':r['okul_adi'],'url':r['kaynak_url']} for r in sources[:3]],'score':score,'issues':issues,
    'eligible_for_publication':not issues,'status':'noindex' if issues else 'created'})
 return out

def render(p,all_plans,source_hash,checked_on):
 e=html.escape;place=p['province']+(' / '+p['district'] if p['district'] else '')
 title=place+' · Okul Kayıtları ve Norm Analizi'
 desc=f"{place} için analiz veri kümesindeki {p['record_count']} kurum kaydının tür dağılımı, kaynak kapsamı ve filtreli norm aracına erişim."
 tool='/?'+urlencode({'il':p['province'],**({'ilce':p['district']} if p['district'] else {})})
 body=f'<h1>{e(title)}</h1><p>{e(place)} için mevcut analiz veri kümesinde {p["record_count"]} kurum kaydı bulunur. Bu sayı resmî okul sayımı, personel sayısı veya boş PDR kadrosu olarak sunulmaz. Kurum türlerini ve kayıt kapsamını aşağıda görebilir; mevcut norm aracını bu konuma göre filtreleyebilirsiniz.</p>'
 body+=f'<p><a href="{e(tool,quote=True)}">{e(place)} filtreli norm aracını aç</a></p><section><h2>Veri kapsamı</h2><dl><dt>Kurum kaydı</dt><dd>{p["record_count"]}</dd><dt>HTTPS resmî kaynak adresi bulunan kayıt</dt><dd>{p["source_url_count"]}</dd><dt>HTTPS kaynak ölçütünü karşılamayan kayıt</dt><dd>{p["missing_or_unusable_source_url_count"]}</dd><dt>Eğitim yılı</dt><dd>'+e((p['effective_period']+' (kullanıcı teyidi)' if p['period_declaration'] else p['effective_period']) or 'Kaynak veri kümesinde belirtilmemiş')+'</dd></dl></section>'
 if p['period_declaration']:body+='<p>Eğitim dönemi, veri sahibinin '+e(p['period_declaration']['confirmed_on'])+' tarihli teyidine dayanır. Kaynak kayıtların eğitim yılı alanları değiştirilmemiştir; bu teyit bağımsız resmî belge doğrulaması değildir.</p>'
 body+='<section><h2>Kurum türü dağılımı</h2><table><thead><tr><th scope="col">Kurum türü</th><th scope="col">Kayıt sayısı</th></tr></thead><tbody>'+''.join('<tr><th scope="row">'+e(k)+'</th><td>'+str(v)+'</td></tr>' for k,v in sorted(p['types'].items()))+'</tbody></table></section>'
 peers=[x for x in all_plans if x['province']==p['province'] and x['route']!=p['route']]
 body+='<section><h2>İl ve ilçe görünümleri</h2><ul>'+''.join('<li><a href="'+e(x['route'])+'">'+e(x['district'] or x['province']+' il özeti')+'</a></li>' for x in peers)+'</ul></section>'
 body+='<section><h2>Kaynak örnekleri ve yöntem</h2><ul>'+''.join('<li><a href="'+e(x['url'],quote=True)+'" target="_blank" rel="noopener">'+e(x['institution'])+' resmî kaynak adresi</a></li>' for x in p['source_examples'])+'</ul><p>Bu kapsam özeti, uygulamanın mevcut okul kayıtlarından il ve ilçe alanlarına göre hazırlanmıştır. Her satır bir kurum kaydı olarak sayılır. Kurum türü bilgisi kayıttaki etiketle gösterilir; yeni sınıflandırma veya öğrenci/norm/personel hesabı yapılmaz.</p><p>Adresin resmî alan adına ait olması içerik ve dönem doğrulamasının tamamlandığı anlamına gelmez. Bu pilotta her kurumun web sayfası yeniden doğrulanmamıştır. Eğitim yılı, varsa veri sahibinin açık dönem teyidiyle gösterilir. Teyit yoksa güncel yıl varsayılmaz; kaynak kayıtlardaki farklı dönemler yayın denetimini durdurur.</p><p>Pilot oluşturma tarihi: <time datetime="'+checked_on+'">'+checked_on+'</time>. Bu tarih kurum kaydının eğitim yılı veya resmî yayın tarihi değildir.</p></section>'
 period_answer=('Bu pilotta dönem, veri sahibinin '+p['effective_period']+' teyidiyle gösterilir; kaynak satırların boş eğitim yılı alanları doldurulmaz. ' if p['period_declaration'] else '')+'Kullanıcı teyidi bulunmayan kayıtlarda güncel yıl varsayılmaz. Resmî doğrulama için kurumun ilgili dönem belgesi ayrıca incelenmelidir.'
 body+='<section><h2>Sık sorulan sorular</h2><h3>Bu sayfa kesin boş norm sayısını gösterir mi?</h3><p>Hayır. Sayfa veri kümesinin kurum kapsamını gösterir. Hesaplanan norm, listelenen personel ve kesin boş kadro farklı kavramlardır; sonuçlar mevcut araçtaki açıklamalarıyla incelenmelidir.</p><h3>Eksik eğitim yılı nasıl yorumlanmalı?</h3><p>'+e(period_answer)+'</p></section>'
 if p['issues']:body+='<aside><strong>Dry-run önizlemesi — yayıma uygun değil.</strong><p>Eğitim dönemi veya kaynak kapsamı denetimindeki eksikler giderilmeden indekslenebilir bir sayfa olarak yayımlanmaz.</p></aside>'
 crumbs=[{'@type':'ListItem','position':1,'name':'PDR Norm Analizi','item':BASE+'/'}]
 if p['district']:crumbs.append({'@type':'ListItem','position':2,'name':p['province'],'item':BASE+'/il/'+slug(p['province'])+'/'})
 crumbs.append({'@type':'ListItem','position':len(crumbs)+1,'name':place,'item':BASE+p['route']})
 schema=json.dumps({'@context':'https://schema.org','@type':'BreadcrumbList','itemListElement':crumbs},ensure_ascii=False).replace('<','\\u003c')
 robots='noindex,follow' if p['issues'] else 'index,follow'
 return '<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+e(title)+'</title><meta name="description" content="'+e(desc,quote=True)+'"><meta name="robots" content="'+robots+'"><link rel="canonical" href="'+BASE+p['route']+'"><script type="application/ld+json">'+schema+'</script><style>body{margin:0;background:#f3f6f8;color:#152b40;font:16px system-ui;line-height:1.7}main{max-width:950px;margin:auto;padding:24px}section,aside{margin:18px 0;padding:20px;background:white;border:1px solid #dce5ed;border-radius:10px}a{color:#118999}h1{font-size:clamp(26px,4vw,38px);line-height:1.3}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:8px;border-bottom:1px solid #dce5ed}dt{font-weight:700}dd{margin:0 0 12px}aside{border-color:#976419}</style></head><body><main><nav aria-label="Gezinme"><a href="/">PDR Norm Analizi</a> · <a href="https://pdrkampus.com/">PDR Kampüs</a></nav>'+body+'</main></body></html>'

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=['audit','validate','generate']);ap.add_argument('--dry-run',action='store_true');ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
 root=args.root.resolve();out=safe_output(root,args.output)
 if out.exists():raise ValueError('Choose a new output directory')
 if args.command=='generate' and not args.dry_run:raise ValueError('Only --dry-run generation is supported')
 guard=protected(root)
 if not guard['pass']:raise ValueError('Critical preservation gate failed')
 config=json.loads((root/'seo/geo-pilot.json').read_text());rows,source_hash=load_rows(root);pilot=plans(rows,config);out.mkdir(parents=True)
 if args.command=='generate':
  for p in pilot:
   target=out/'preview'/p['route'].strip('/')/'index.html';target.parent.mkdir(parents=True);target.write_text(render(p,pilot,source_hash,date.today().isoformat()))
 report={'mode':'read_only_geographic_coverage_pilot','dry_run':args.dry_run,'application_writes':0,'protection':guard,'source_sha256':source_hash,'project_rows':len(rows),'proposals':pilot,
 'status_counts':{s:sum(p['status']==s for p in pilot) for s in ['created','updated','skipped','duplicate','invalid','noindex','error']},'limits':['No student, norm, vacancy or staff calculation.','Period declaration is user confirmation; original row periods remain unchanged. Institutional URLs have not been independently revalidated.','No sitemap or application HTML changes.']}
 (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'proposals':len(pilot),'statuses':report['status_counts'],'report':str(out/'report.json')},ensure_ascii=False))
if __name__=='__main__':main()
