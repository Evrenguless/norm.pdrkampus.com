#!/usr/bin/env python3
# coding: utf-8
"""Build source-backed Istanbul profiles with the application's unchanged model."""
import argparse,collections,gzip,hashlib,html,json,os,re,shutil,subprocess,unicodedata
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
BASE='https://norm.pdrkampus.com'
E=html.escape
SPECIAL='769335'
DATE='2026-10-07'
def slug(s):
 return re.sub('[^a-z0-9]+','-',unicodedata.normalize('NFKD',s.replace('ı','i').replace('İ','I')).encode('ascii','ignore').decode().lower()).strip('-')
def route(r):
 return '/okul/'+('esenyurt-sezai-karakoc-anadolu-lisesi' if str(r['kurum_kodu'])==SPECIAL else slug(r['okul_adi'])+'-'+str(r['kurum_kodu']))+'/'
def official(value):
 try:
  p=urlsplit(value or '')
  return value if p.scheme in ('http','https') and not p.username and not p.password and re.search(r'(^|\.)meb\.(gov|k12)\.tr$',p.hostname or '') else ''
 except ValueError:return ''
def date_label(value):
 return (value or '')[:10] or 'Kayıtta tarih belirtilmemiş'
def fmt(v):
 return f'{v:,}'.replace(',','.') if isinstance(v,(int,float)) else str(v)
def load():
 payload=json.loads(gzip.decompress((ROOT/'data/schools-v1.json.gz').read_bytes()))
 rows=[dict(zip(payload['columns'],r)) for r in payload['rows'] if r[0]=='İstanbul']
 staff=json.loads((ROOT/'data/staff-v1.json').read_text())
 staff={str(r[0]):dict(zip(staff['columns'],r)) for r in staff['rows']}
 source=(ROOT/'index.html').read_text()
 functions=[]
 for prefix in ['function trLower','function num','let STUDENT_OVERRIDES','function studentInfo','const secondaryTypes','function isSpecialEducation','function schoolLevel','function institutionPolicy','function normFor','const numberFormatter']:
  line=next(l for l in source.splitlines() if l.startswith(prefix))
  functions.append(line)
 # Public profiles do not present personal, generated scenario values as MEB records.
 overrides=json.loads((ROOT/'data/student-overrides.json').read_text())['schools']
 public_overrides={k:v for k,v in overrides.items() if not v.get('generated_for_personal_use')}
 js='\n'.join(functions)+'\nSTUDENT_OVERRIDES={...STUDENT_OVERRIDES,...input.overrides};\nconsole.log(JSON.stringify(input.rows.map(r=>{const si=studentInfo(r);return {...r,student:si,calculation:normFor(r,si),level:schoolLevel(r)}})));'
 script='const fs=require("fs");const input=JSON.parse(fs.readFileSync(0,"utf8"));\n'+js
 process=subprocess.run([os.environ.get('NODE_BIN','node'),'-e',script],input=json.dumps({'rows':rows,'overrides':public_overrides}),text=True,capture_output=True,check=True)
 rows=json.loads(process.stdout)
 for r in rows:
  code=str(r['kurum_kodu']);r['staff']=staff.get(code);r['route']=route(r)
  r['scenario_excluded']=bool(overrides.get(code,{}).get('generated_for_personal_use'))
  r['override']=public_overrides.get(code,{})
 return rows

def header():
 return '<header class="site-header"><div class="shell header-inner"><a class="brand" href="/"><img src="/assets/logo.png" alt="" width="44" height="44"><div><strong>PDR<span>Kampüs</span></strong><small>Okul Psikolojik Danışmanlığı · Norm Analizi</small></div></a><a class="header-link" href="https://pdrkampus.com/">Ana platform ↗</a></div></header>'
def footer():
 return '<footer class="site-footer"><span>© 2026 PDR Kampüs · Bağımsız okul ve kurum verisi incelemesi</span><div><a href="/">Norm haritası</a> · <a href="https://pdrkampus.com/iletisim.html">İletişim</a></div></footer>'
def conversion():
 return '<section class="conversion"><div><h2>Verileri birlikte değerlendirin.</h2><p>İl, ilçe ve okul türüne göre karşılaştırın; öğrenci, hesaplanan norm ve web listesindeki PDR verilerini norm haritasında inceleyin.</p></div><a class="button" href="/">Tüm istatistikleri için <span aria-hidden="true">↗</span></a></section>'
def document(title,desc,path,body,schema):
 return '<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+E(title)+'</title><meta name="description" content="'+E(desc,quote=True)+'"><meta name="robots" content="index,follow"><link rel="canonical" href="'+BASE+path+'"><link rel="icon" href="/assets/logo.png" type="image/png"><meta name="theme-color" content="#f3f6f8"><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet"><link rel="stylesheet" href="/assets/school-profile.css"><meta property="og:type" content="website"><meta property="og:title" content="'+E(title,quote=True)+'"><meta property="og:description" content="'+E(desc,quote=True)+'"><meta property="og:url" content="'+BASE+path+'"><meta property="og:image" content="'+BASE+'/assets/logo.png"><meta name="twitter:card" content="summary"><script type="application/ld+json">'+json.dumps(schema,ensure_ascii=False).replace('<','\\u003c')+'</script></head><body>'+header()+'<main class="shell">'+body+conversion()+footer()+'</main></body></html>'
def metric(label,value,note):
 v=E(str(value));long=' long' if len(str(value))>8 else ''
 return '<article class="metric"><span class="metric-label">'+E(label)+'</span><strong class="'+long.strip()+'">'+v+'</strong><small>'+E(note)+'</small></article>'
def source_item(label,url,date):
 return '<div class="source"><strong>'+E(label)+'</strong>'+(('<a href="'+E(url,quote=True)+'" target="_blank" rel="noopener">'+E(urlsplit(url).hostname or url)+' ↗</a>') if url else '<small>Resmî kaynak bağlantısı kayıtta bulunmuyor.</small>')+'<small>Kayıt kontrolü: '+E(date_label(date))+'</small></div>'
def render(r,peers):
 name=r['okul_adi'];district=r['ilce'];code=str(r['kurum_kodu']);si=r['student'];calc=r['calculation'];st=r['staff'];url=official(r['web_sitesi']);source=official(r['kaynak_url']) or url
 droute='/okullar/istanbul/'+slug(district)+'/'
 title=name+' | Öğrenci ve Rehber Öğretmen Sayısı · PDR Kampüs'
 desc=f"{name}: İstanbul {district} öğrenci sayısı, web listesindeki rehber öğretmen sayısı, rehberlik norm analizi ve tarihli kaynaklar. Kurum kodu {code}."
 crumbs='<nav class="crumbs" aria-label="İçerik yolu"><a href="/">Norm haritası</a><span>/</span><a href="/okullar/istanbul/">İstanbul</a><span>/</span><a href="'+droute+'">'+E(district)+'</a><span>/</span><span>Kurum profili</span></nav>'
 tool='/?'+urlencode({'il':'İstanbul','ilce':district,'q':code})+'#schools'
 student_value=si.get('label') or (fmt(si['value']) if si['value'] is not None else 'Veri yok')
 norm_value=calc.get('normRange') or (fmt(calc['norm']) if calc['norm'] is not None else 'Hesaplanmadı')
 count=st.get('listed_count') if st else None
 staff_value=fmt(count) if count is not None else 'Listede yok'
 staff_note='Web listesindeki kayıt; görevdeki personelin tamamını doğrulamaz.' if count is not None else 'Liste kaydı bulunmaması, PDR sayısının sıfır olduğu anlamına gelmez.'
 body=crumbs+'<section class="hero"><div><p class="kicker">İstanbul / '+E(district)+' <span>'+E(r['level'])+'</span></p><h1>'+E(name)+'</h1><p class="lead">'+E(district)+' ilçesindeki '+E(r['okul_turu'])+' kaydını; öğrenci bilgisi, rehberlik norm analizi ve okulun web listesindeki PDR verileriyle birlikte inceleyin.</p><div class="actions"><a class="button primary" href="/">Tüm istatistikleri için <span aria-hidden="true">↗</span></a><a class="button secondary" href="'+E(tool,quote=True)+'">Bu kurumu haritada incele</a></div></div><aside class="hero-aside"><div><small>Kurum kodu</small><strong>'+E(code)+'</strong></div><div><small>Öğrenci kaydı kontrolü</small><strong>'+E(date_label(r['kontrol_tarihi'] or r['cekim_tarihi']))+'</strong></div></aside></section>'
 body+='<section class="metrics" aria-label="Kurum verileri">'+metric('Öğrenci sayısı',student_value,'Tarihli platform kaydı · Güncel resmî toplam değildir.')+metric('Hesaplanan rehberlik normu',norm_value,calc['status'])+metric('Web listesinde rehber öğretmen',staff_value,staff_note)+'</section>'
 body+='<aside class="data-note">Hesaplanan norm ve web listesindeki PDR sayısı farklı verilerdir. Bu sayfa kesin boş kadro ya da personel açığı tespiti değildir. Kaynak tarihleriyle değerlendirin.</aside><div class="content-grid"><div><section class="panel"><div class="section-label">KURUM BİLGİLERİ</div><h2>'+E(name)+' hangi ilçede?</h2><dl>'
 facts=[('İl / ilçe','İstanbul / '+district),('Kurum türü',r['okul_turu']),('Kademe',r['level']),('Kurum kodu',code)]
 if code==SPECIAL:facts.extend([('Adres','Barbaros Hayrettin Paşa Mahallesi, 2266. Sokak No: 2, Esenyurt / İstanbul'),('Telefon','0212 813 72 73')])
 body+=''.join('<div><dt>'+E(k)+'</dt><dd>'+E(v)+'</dd></div>' for k,v in facts)
 body+='<div><dt>Resmî web sitesi</dt><dd>'+('<a href="'+E(url,quote=True)+'" target="_blank" rel="noopener">'+E(urlsplit(url).hostname)+' ↗</a>' if url else 'Kayıtta belirtilmemiş')+'</dd></div></dl></section><section class="panel"><div class="section-label">REHBERLİK NORM ANALİZİ</div><h2>Norm hesabı nasıl yorumlanmalı?</h2><span class="status'+(' missing' if calc['status']!='Hesaplandı' else '')+'">'+E(calc['status'])+'</span><div class="method">'+E(calc['reason'])+'</div><p>Hesap, PDR Norm Haritası’nın mevcut modeliyle oluşturulur. Web listesindeki personel sayısı norm hesabının girdisi değildir. Kesin kurum normu ve güncel görevlendirmeler resmî kurum kayıtlarından doğrulanmalıdır.</p><a href="'+E(tool,quote=True)+'">Kurumun ayrıntılı istatistiklerini aç →</a></section><section class="panel"><div class="section-label">VERİ KAPSAMI</div><h2>Öğrenci ve PDR verisinin kaynağı</h2><p>'+E((si.get('note') or 'Öğrenci sayısı, platformdaki tarihli kurum kaydına dayanır.').replace('CSV ve MEB doğrulamalarındaki','Kaynak kaydı ve MEB doğrulamalarındaki').replace("CSV'deki",'Kaynak kaydındaki').replace("CSV'de",'Kaynak kaydında'))+'</p><p>'+E(staff_note)+'</p>'
 if r['scenario_excluded']:body+='<p>Kişisel çalışma için üretilmiş senaryo değerleri bu kamuya açık kurum profilinde kullanılmaz; kaynak kurum verisi esas alınır. Haritadaki kişisel senaryo ile bu kaynak profili farklı değerler gösterebilir.</p>'
 if code==SPECIAL:body+='<p>7 Ekim 2026 kontrolünde okulun MEB ana sayfasında 2.445, “Okulumuz Hakkında” sayfasında 2.447 öğrenci görülmüştür. Platform kaydı 2.445’tir; iki değer de mevcut modelde 5 norm sonucunu verir.</p>'
 body+='</section><section class="panel"><div class="section-label">SIK SORULANLAR</div><h2>'+E(name)+' hakkında</h2><h3>'+E(name)+' öğrenci sayısı kaç?</h3><p>'+('Platformdaki kaynak kaydı '+E(student_value)+' olarak gösterilir.' if si['value'] is not None or si.get('label') else 'Kaynak veri setinde doğrulanabilir öğrenci sayısı bulunmuyor; sayı uydurulmadan “Veri yok” olarak gösterilir.')+'</p><h3>'+E(name)+' rehber öğretmen sayısı kaç?</h3><p>'+((str(count)+' rehber öğretmen / psikolojik danışman kaydı okulun web listesinde bulunur.') if count is not None else 'Bu kurum için web listesinde PDR kaydı bulunmamıştır.')+' Bu bilgi güncel resmî personel sayımı değildir.</p><h3>Diğer kurumlarla nasıl karşılaştırabilirim?</h3><p>“Tüm istatistikleri için” butonuyla norm haritasını açın; il, ilçe ve kurum türüne göre filtreleyin.</p></section></div><aside><section class="panel"><div class="section-label">TARİHLİ KAYNAKLAR</div><h2>Veri izini takip edin</h2>'+source_item('Öğrenci kaydı',source,r['kontrol_tarihi'] or r['cekim_tarihi'])
 override_urls=[official(u) for u in r['override'].get('source_urls',[]) if official(u)]
 for u in override_urls[:3]:body+=source_item('Öğrenci düzeltme kaynağı',u,r['override'].get('checked_at') or r['override'].get('verified_at'))
 body+=source_item('PDR web listesi',official(st.get('source_url')) if st else '',st.get('checked_at') if st else '')
 if code==SPECIAL:body+=source_item('Okulumuz Hakkında','https://eskal.meb.k12.tr/34/39/769335/okulumuz_hakkinda.html',DATE)+source_item('İletişim','https://eskal.meb.k12.tr/tema/iletisim.php',DATE)
 body+='</section><section class="panel"><div class="section-label">AYNI İLÇEDEN</div><h2>'+E(district)+' kurumları</h2><ul class="related">'+''.join('<li><a href="'+p['route']+'">'+E(p['okul_adi'])+'</a><small>'+E(p['okul_turu'])+'</small></li>' for p in peers)+'</ul><p style="margin-top:16px"><a href="'+droute+'">İlçedeki tüm kurum kayıtları →</a></p></section><section class="panel"><h2>Bu sayfa hakkında</h2><p>PDR Kampüs’ün bağımsız kurum verisi profilidir. Kurumun resmî web sitesi değildir.</p><p>Sayfa oluşturma tarihi: '+DATE+'. Bu tarih kaynak kurum verisinin kontrol tarihi değildir.</p></section></aside></div>'
 entity={'@type':'School' if r['level'] not in ('Diğer','RAM') else 'EducationalOrganization','@id':BASE+r['route']+'#institution','name':name,'identifier':code,'address':{'@type':'PostalAddress','addressLocality':district,'addressRegion':'İstanbul','addressCountry':'TR'}}
 if url:entity['sameAs']=url
 schema={'@context':'https://schema.org','@graph':[entity,{'@type':'WebPage','url':BASE+r['route'],'name':title,'inLanguage':'tr-TR','about':{'@id':entity['@id']},'publisher':{'@type':'Organization','name':'PDR Kampüs','url':'https://pdrkampus.com/'}},{'@type':'BreadcrumbList','itemListElement':[{'@type':'ListItem','position':1,'name':'İstanbul','item':BASE+'/okullar/istanbul/'},{'@type':'ListItem','position':2,'name':district,'item':BASE+droute},{'@type':'ListItem','position':3,'name':name,'item':BASE+r['route']}]}]}
 return document(title,desc,r['route'],body,schema)
def directory(rows,district=None):
 path='/okullar/istanbul/'+(slug(district)+'/' if district else '')
 place='İstanbul'+(' / '+district if district else '')
 title=place+' Okul ve Kurum Kayıtları | PDR Kampüs'
 body='<nav class="crumbs" aria-label="İçerik yolu"><a href="/">Norm haritası</a><span>/</span><a href="/okullar/istanbul/">İstanbul kurumları</a>'+('<span>/</span><span>'+E(district)+'</span>' if district else '')+'</nav><section class="hero"><div><p class="kicker">Kurum profilleri</p><h1>'+E(place)+' okul ve kurum kayıtları</h1><p class="lead directory-intro">Mevcut platform veri setindeki '+fmt(len(rows))+' kurum kaydını inceleyin. Her profil öğrenci, norm analizi ve tarihli kaynak bilgisine ayrı bir bağlantı sunar. Kapsam veri setine dayanır; İstanbul’daki tüm resmî ve özel kurumların eksiksiz sayımı değildir.</p><div class="actions"><a class="button primary" href="/">Tüm istatistikleri için ↗</a></div></div></section>'
 if not district:
  counts=collections.Counter(r['ilce'] for r in rows)
  body+='<div class="district-grid">'+''.join('<a class="district-card" href="/okullar/istanbul/'+slug(d)+'/">'+E(d)+'<span>'+fmt(n)+' kayıt →</span></a>' for d,n in sorted(counts.items()))+'</div>'
 else:
  body+='<section class="panel"><h2>'+E(district)+' kurum profilleri</h2><ul class="institution-list">'+''.join('<li><a href="'+r['route']+'">'+E(r['okul_adi'])+'</a><small>'+E(r['okul_turu'])+' · Kurum kodu '+E(str(r['kurum_kodu']))+'</small></li>' for r in rows)+'</ul></section>'
 return path,document(title,place+' kurumlarının öğrenci ve rehberlik norm analizlerine, okul profillerine ve kaynak kayıtlarına erişin.',path,body,{'@context':'https://schema.org','@type':'CollectionPage','url':BASE+path,'name':title,'inLanguage':'tr-TR'})
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();out=args.output.resolve()
 if out==ROOT or ROOT in out.parents:raise ValueError('Output must be outside source checkout')
 if out.exists():raise ValueError('Output already exists')
 rows=load();assert len(rows)==len({r['kurum_kodu'] for r in rows});assert len(rows)==len({r['route'] for r in rows})
 shutil.copytree(ROOT,out,ignore=shutil.ignore_patterns('.git','__pycache__','.DS_Store'))
 groups={d:sorted([r for r in rows if r['ilce']==d],key=lambda r:r['okul_adi']) for d in set(r['ilce'] for r in rows)}
 paths=[]
 for r in rows:
  peers=groups[r['ilce']];pos=next(i for i,p in enumerate(peers) if p['kurum_kodu']==r['kurum_kodu']);near=[peers[(pos+i)%len(peers)] for i in range(1,min(5,len(peers)))]
  target=out/r['route'].strip('/')/'index.html';target.parent.mkdir(parents=True,exist_ok=True);target.write_text(render(r,near));paths.append(r['route'])
 for d,rs in [(None,rows)]+list(sorted(groups.items())):
  path,content=directory(rs,d);target=out/path.strip('/')/'index.html';target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content);paths.append(path)
 ns='http://www.sitemaps.org/schemas/sitemap/0.9';ET.register_namespace('',ns);tree=ET.parse(ROOT/'sitemap.xml');root=tree.getroot();known={u.find('{'+ns+'}loc').text for u in root}
 for path in paths:
  if BASE+path not in known:
   node=ET.SubElement(root,'{'+ns+'}url');ET.SubElement(node,'{'+ns+'}loc').text=BASE+path;ET.SubElement(node,'{'+ns+'}lastmod').text=DATE
  else:
   for node in root:
    if node.find('{'+ns+'}loc').text==BASE+path:
     lm=node.find('{'+ns+'}lastmod')
     if lm is None:lm=ET.SubElement(node,'{'+ns+'}lastmod')
     lm.text=DATE
 tree.write(out/'sitemap.xml',encoding='utf-8',xml_declaration=True)
 report={'profiles':len(rows),'districts':len(groups),'directory_pages':len(groups)+1,'sitemap_urls':len(root),'scenario_values_excluded':sum(r['scenario_excluded'] for r in rows),'missing_students':sum(r['student']['value'] is None for r in rows),'missing_rosters':sum(r['staff'] is None for r in rows),'source_sha256':hashlib.sha256((ROOT/'data/schools-v1.json.gz').read_bytes()).hexdigest(),'paths':paths}
 (out/'school-profile-build.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='paths'},ensure_ascii=False))
if __name__=='__main__':main()
