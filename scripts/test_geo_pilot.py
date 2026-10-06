import unittest,json,gzip,tempfile
from pathlib import Path
from build_geo_pilot import plans,load_rows,official_url,render,slug
CONFIG={'provinces':{'Adana':['Aladağ']},'minimum_score':70,'require_education_period':True}
def row(year=''):
 return {'il':'Adana','ilce':'Aladağ','okul_turu':'İlkokul','okul_adi':'Test Kurumu','kaynak_url':'https://test.meb.k12.tr/','egitim_yili':year}
class Tests(unittest.TestCase):
 def test_unknown_period_is_not_publishable_even_if_score_passes(self):
  p=plans([row()],CONFIG)[0];self.assertGreaterEqual(p['score'],70);self.assertFalse(p['eligible_for_publication']);self.assertEqual(p['status'],'noindex')
 def test_mixed_and_partial_period_block_publication(self):
  for values in [['2025-2026','2026-2027'],['2026-2027','']]:
   p=plans([row(v) for v in values],CONFIG)[0];self.assertFalse(p['eligible_for_publication'])
 def test_user_declaration_supplies_period_without_mutating_rows(self):
  rows=[row(),row('2026-2027')];before=json.dumps(rows)
  c={**CONFIG,'education_period_declaration':{'period':'2026-2027','basis':'user_confirmation','confirmed_on':'2026-10-06','scope':'current_norm_institution_records'}}
  p=plans(rows,c)[0];self.assertTrue(p['eligible_for_publication']);self.assertEqual(p['effective_period'],'2026-2027');self.assertEqual(json.dumps(rows),before)
  page=render(p,[p],'test','2026-10-06');self.assertIn('2026-2027',page);self.assertNotIn('kullanıcı teyidi',page);self.assertNotIn('veri sahibinin',page);self.assertIn('noindex,follow',page)
 def test_declared_period_cannot_override_conflicting_source_year(self):
  c={**CONFIG,'education_period_declaration':{'period':'2026-2027','basis':'user_confirmation','confirmed_on':'2026-10-06','scope':'current_norm_institution_records'}}
  p=plans([row('2025-2026')],c)[0];self.assertFalse(p['eligible_for_publication']);self.assertIn('education_period_conflicts_with_declaration',p['issues'])
 def test_invalid_declaration_rejected(self):
  with self.assertRaises(ValueError):plans([row()],{**CONFIG,'education_period_declaration':{'period':'2026-2028','basis':'user_confirmation'}})
 def test_out_of_scope_and_personal_fields_are_not_exported(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'data').mkdir();columns=list(row())+['ogrenci_sayisi','telefon','person_name'];data=list(row().values())+['123','555','PRIVATE']
   (root/'data/schools-v1.json.gz').write_bytes(gzip.compress(json.dumps({'version':1,'columns':columns,'rows':[data]}).encode()))
   rows,_=load_rows(root);self.assertEqual(set(rows[0]),set(row()));self.assertNotIn('PRIVATE',json.dumps(rows))
 def test_region_limit_enforced(self):
  config={**CONFIG,'provinces':{str(i):[] for i in range(6)}}
  with self.assertRaises(ValueError):plans([],config)
 def test_official_host_boundary(self):
  self.assertTrue(official_url('https://a.meb.k12.tr/'));self.assertFalse(official_url('https://meb.k12.tr.evil.example/'));self.assertFalse(official_url('https://name:secret@a.meb.k12.tr/'))
 def test_noindex_preview_has_encoded_filter_link_and_escaped_names(self):
  r=row();r['okul_adi']='<script>alert(1)</script>';p=plans([r],CONFIG);page=render(p[0],p,'test','2026-10-06')
  self.assertIn('noindex,follow',page);self.assertIn('il=Adana',page);self.assertIn('&lt;script&gt;',page);self.assertNotIn('<script>alert',page)
 def test_local_editorial_sections(self):
  c={**CONFIG,'education_period_declaration':{'period':'2026-2027','basis':'user_confirmation','confirmed_on':'2026-10-06','scope':'current_norm_institution_records'}}
  ps=plans([row(),row()],c)
  district=ps[1];page=render(district,ps,'test','2026-10-06');self.assertIn('İlkokul: 2 kayıt',page);self.assertIn('Aladağ için filtreyi',page);self.assertNotIn('doğrulanmamıştır',page)
 def test_turkish_slug(self):self.assertEqual(slug('Adıyaman'),'adiyaman');self.assertEqual(slug('Ağaçören'),'agacoren')
if __name__=='__main__':unittest.main(verbosity=2)
