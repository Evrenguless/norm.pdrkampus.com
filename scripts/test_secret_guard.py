import base64,json,subprocess,tempfile,unittest
from pathlib import Path
from secret_guard import findings,scan
class SecretGuardTests(unittest.TestCase):
 def test_privileged_tokens_redacted(self):
  token='sb_'+'secret_'+'a'*40
  result=findings('first\n'+token)
  self.assertEqual(result[0]['line'],2);self.assertNotIn(token,json.dumps(result))
 def test_jwt_roles(self):
  def jwt(role):
   enc=lambda x:base64.urlsafe_b64encode(json.dumps(x).encode()).decode().rstrip('=')
   return enc({'alg':'HS256'})+'.'+enc({'role':role})+'.'+'a'*43
  self.assertEqual(findings(jwt('anon')),[])
  self.assertEqual(findings(jwt('service_role'))[0]['kind'],'service-role-jwt')
 def test_public_keys_and_turkish_risk_slugs(self):
  self.assertEqual(findings('sb_'+'publishable_'+'a'*40+' /kriz-risk-'+'a'*70),[])
 def test_unicode_paths_and_env(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);subprocess.run(['git','init','-q',folder],check=True)
   (root/'özel.env.txt').write_text('sb_'+'secret_'+'b'*40)
   (root/'.env.production').write_text('UNKNOWN_SECRET=x')
   (root/'.env.example').write_text('SUPABASE_SECRET_KEY=')
   subprocess.run(['git','add','-f','.'],cwd=root,check=True)
   result=scan(root)['findings']
   self.assertEqual({r['file'] for r in result},{'özel.env.txt','.env.production'})
if __name__=='__main__':unittest.main()
