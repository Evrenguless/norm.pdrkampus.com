#!/usr/bin/env python3
"""Scan tracked files without ever printing credential values. No dependencies."""
import argparse,base64,hashlib,json,re,subprocess,sys
from pathlib import Path
PATTERNS = [
    ('supabase-secret', r'sb_secret_[A-Za-z0-9_-]{20,}'),
    ('github-token', r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})'),
    ('provider-secret', r'(?<![A-Za-z0-9_-])sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{35,}'),
    ('aws-access-key', r'AKIA[0-9A-Z]{16}'),
    ('private-key', r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
]
JWT = re.compile(r'eyJ[A-Za-z0-9_-]+\.([A-Za-z0-9_-]+)\.[A-Za-z0-9_-]{20,}')
def findings(body):
    found=[]
    for kind,pattern in PATTERNS:
        for m in re.finditer(pattern,body):found.append((kind,m.start(),m.group()))
    for m in JWT.finditer(body):
        try:payload=json.loads(base64.urlsafe_b64decode(m.group(1)+'='*(-len(m.group(1))%4)))
        except (ValueError,UnicodeDecodeError):continue
        if isinstance(payload,dict) and payload.get('role')=='service_role':found.append(('service-role-jwt',m.start(),m.group()))
    return [{'kind':kind,'line':body.count('\n',0,pos)+1,'fingerprint':hashlib.sha256(value.encode()).hexdigest()[:12]} for kind,pos,value in found]
def scan(root):
    names=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode().split('\0')
    results=[];scanned=0
    for name in filter(None,names):
        p=root/name
        if not p.is_file() or p.is_symlink():continue
        # Tracked .env files are forbidden even if a token pattern is unknown.
        if (p.name=='.env' or p.name.startswith('.env.')) and p.name not in {'.env.example','.env.sample','.env.template'}:
            results.append({'file':name,'kind':'tracked-env','line':1});continue
        raw=p.read_bytes()
        if b'\0' in raw:continue
        scanned+=1
        for result in findings(raw.decode('utf-8',errors='replace')):results.append({'file':name,**result})
    return {'tracked_text_files':scanned,'findings':results}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);a=ap.parse_args()
    result=scan(a.root);print(json.dumps(result,ensure_ascii=False,indent=2));return bool(result['findings'])
if __name__=='__main__':sys.exit(main())
