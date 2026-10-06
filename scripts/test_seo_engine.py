import copy
import os
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT=Path(os.environ.get('PDR_SEO_ROOT', Path(__file__).resolve().parents[1])).resolve()
spec=importlib.util.spec_from_file_location('engine',ROOT/'scripts/seo_engine.py')
engine=importlib.util.module_from_spec(spec); spec.loader.exec_module(engine)
CONFIG=engine.read(ROOT/'seo/config.json')
MANIFEST=engine.read(ROOT/'seo/pilot.json')
SOURCES=Path(os.environ['PDR_SEO_SOURCES']).resolve() if os.environ.get('PDR_SEO_SOURCES') else None

class SafetyTests(unittest.TestCase):
 def validate(self, manifest): return engine.validate(ROOT,CONFIG,manifest,SOURCES)
 def test_original_files_unchanged(self):
  self.assertTrue(engine.protected(ROOT)['pass'])
 def test_data_file_cannot_be_exempted_by_review_record(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp); (root/'seo').mkdir(); p=root/'data.csv';p.write_text('original');before=engine.digest(p);p.write_text('changed')
   (root/'seo/protected-files.json').write_text(json.dumps({'baseline_commit':'test','files':{'data.csv':before}}))
   (root/'seo/approved-edits.json').write_text(json.dumps({'edits':{'data.csv':{'baseline_sha256':before,'reviewed_sha256':engine.digest(p)}}}))
   self.assertFalse(engine.protected(root)['pass'])
 def test_hidden_and_dialog_headings_do_not_raise_primary_h1_count(self):
  page=engine.Page('<main><h1>Overview</h1><section hidden><h1>Scenario</h1></section></main><section role="dialog"><h1>Welcome</h1></section>')
  self.assertEqual(page.primary_h1,['Overview']);self.assertEqual(len(page.h1),3)
 def test_protected_change_detected_without_touching_real_data(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp); (root/'seo').mkdir(); (root/'data.csv').write_text('original')
   (root/'seo/protected-files.json').write_text(json.dumps({'baseline_commit':'test','files':{'data.csv':engine.digest(root/'data.csv')}}))
   (root/'data.csv').write_text('changed')
   self.assertEqual(engine.protected(root)['changed'],['data.csv'])
 def test_output_inside_checkout_and_ancestors_rejected(self):
  for p in [ROOT,ROOT/'new-preview',ROOT.parent]:
   with self.assertRaises(ValueError): engine.safe_output(ROOT,p)
 def test_symlink_output_into_checkout_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   link=Path(tmp)/'alias'; link.symlink_to(ROOT,target_is_directory=True)
   with self.assertRaises(ValueError): engine.safe_output(ROOT,link/'preview')
 @unittest.skipUnless(SOURCES is not None and MANIFEST['proposals'], 'Pilot PDF source directory required')
 def test_source_hash_mismatch_blocks_preview(self):
  manifest=copy.deepcopy(MANIFEST); manifest['proposals'][0]['source_sha256']='0'*64
  row=self.validate(manifest)['results'][0]
  self.assertFalse(row['eligible_for_staging']); self.assertIn('source_hash_mismatch',row['issues'])
 @unittest.skipUnless(SOURCES is not None and MANIFEST['proposals'], 'Pilot PDF source directory required')
 def test_duplicate_route_blocked(self):
  manifest=copy.deepcopy(MANIFEST); manifest['proposals'].append(copy.deepcopy(manifest['proposals'][0]))
  rows=self.validate(manifest)['results']
  self.assertEqual(rows[0]['status'],'duplicate'); self.assertEqual(rows[-1]['status'],'duplicate')
 @unittest.skipUnless(SOURCES is not None and MANIFEST['proposals'], 'Pilot PDF source directory required')
 def test_directory_traversal_id_rejected(self):
  manifest=copy.deepcopy(MANIFEST); manifest['proposals'][0]['id']='../../other'
  self.assertEqual(self.validate(manifest)['results'][0]['status'],'error')
 @unittest.skipUnless(SOURCES is not None and MANIFEST['proposals'], 'Pilot PDF source directory required')
 def test_visible_schema_and_canonical_match(self):
  for p in MANIFEST['proposals']:
   page=engine.Page(engine.render(ROOT,CONFIG,p))
   self.assertEqual(page.canonicals,[CONFIG['base_url']+p['route']]); self.assertFalse(page.errors)
   self.assertEqual(page.schemas[0]['@graph'][0]['description'],p['answer'])
   self.assertIn(p['answer'],page.main_text)
 @unittest.skipUnless((ROOT/'data/library.json').exists(), 'No library catalogue in this app')
 def test_duplicates_reported_without_catalogue_mutation(self):
  before=engine.digest(ROOT/'data/library.json'); report=engine.audit(ROOT,CONFIG)
  self.assertEqual(len(report['duplicate_file_groups']),4)
  self.assertTrue(all(len(g['members'])==2 for g in report['duplicate_file_groups']))
  self.assertEqual(before,engine.digest(ROOT/'data/library.json'))

if __name__=='__main__': unittest.main(verbosity=2)
