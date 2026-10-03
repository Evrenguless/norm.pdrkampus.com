from pathlib import Path
import json

html_path = Path('eksik-veriler.html')
data_path = Path('data/unresolved-review-1453.json')
html = html_path.read_text(encoding='utf-8')
data = json.loads(data_path.read_text(encoding='utf-8'))
assert data.get('total') == 1453
assert len(data.get('records', [])) == 1453

start = "fetch('data/unresolved-review-1453.json').then(r=>r.json()).then(d=>{"
end = ").catch(e=>{$('rows').innerHTML='<tr><td colspan=\"6\">Veri dosyası yüklenemedi.</td></tr>';console.error(e)});"
if start not in html or end not in html:
    raise SystemExit('Expected fetch block not found')

payload = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
replacement = f"const d={payload};{{"
html = html.replace(start, replacement, 1)
html = html.replace(end, "}", 1)
html_path.write_text(html, encoding='utf-8')
print('embedded', len(data['records']), 'records into', html_path)
