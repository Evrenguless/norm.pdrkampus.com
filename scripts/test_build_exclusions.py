import shutil,tempfile,unittest
from pathlib import Path
from build_school_profiles import PUBLIC_BUILD_IGNORE
class PublicArtifactTests(unittest.TestCase):
 def test_private_files_excluded_and_public_assets_preserved(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);source=root/'source';source.mkdir()
   for name in ['.env','.env.production','key.pem','key.p12','.DS_Store','index.html','robots.txt']:(source/name).write_text('fixture')
   for name in ['.git','.github','scripts','tests','seo','node_modules','assets','data']:
    (source/name).mkdir();(source/name/'file.txt').write_text('fixture')
   shutil.copytree(source,root/'public',ignore=PUBLIC_BUILD_IGNORE)
   self.assertEqual({p.name for p in (root/'public').iterdir()},{'index.html','robots.txt','assets','data'})
if __name__=='__main__':unittest.main()
