from pathlib import Path
import json, html

PAGE = Path('eksik-veriler.html')
DATA = Path('data/unresolved-review-1453.json')

reasons = {
    'published_zero_or_dash': ('0 / - yayımlanmış','MEB sayfasındaki öğrenci alanında kullanılabilir pozitif sayı yok.'),
    'student_field_not_found': ('Öğrenci alanı bulunamadı','Ayrıntılı MEB taramasında öğrenci sayısı alanı bulunamadı.'),
    'site_unreachable': ('Site erişilemedi','MEB okul sitesi tarama sırasında erişilebilir yanıt vermedi.'),
    'site_unreachable_or_blocked': ('Site erişilemedi / engelledi','Site erişim hatası veya istek engellemesi kaydı var.'),
    'no_usable_url': ('Kullanılabilir URL yok','Kullanılabilir MEB okul sitesi adresi bulunamadı.'),
    'student_field_not_found_or_unpublished': ('Alan bulunamadı / yayımlanmamış','Mevcut kayıtlarda pozitif öğrenci sayısı yok ve yayımlanmış doğrulanabilir alan bulunamadı.'),
}

def e(v):
    return html.escape(str(v or ''), quote=True)

def row(x):
    label, detail = reasons.get(x.get('neden'), (x.get('neden') or '', ''))
    links = [f'<a class="primary" href="{e(x.get("meb_url"))}" target="_blank" rel="noopener">MEB sitesi ↗</a>']
    if x.get('kaynak_url') and x.get('kaynak_url') != x.get('meb_url'):
        links.append(f'<a href="{e(x.get("kaynak_url"))}" target="_blank" rel="noopener">Kayıtlı kaynak ↗</a>')
    links.append(f'<a href="{e(x.get("google_search"))}" target="_blank" rel="noopener">Google\'da ara ↗</a>')
    return (
        '<tr class="static-review-row">'
        f'<td class="school">{e(x.get("okul_adi"))}<span class="code">Kurum kodu: {e(x.get("kurum_kodu"))}</span></td>'
        f'<td>{e(x.get("il"))}<br><span class="code">{e(x.get("ilce"))}</span></td>'
        f'<td><span class="pill">{e(x.get("kademe"))}</span></td>'
        f'<td>{e(x.get("okul_turu"))}</td>'
        f'<td class="reason"><b>{e(label)}</b>{e(detail)}</td>'
        f'<td><div class="links">{"".join(links)}</div></td>'
        '</tr>'
    )

data = json.loads(DATA.read_text(encoding='utf-8'))
records = data.get('records') or []
assert data.get('total') == 1453, data.get('total')
assert len(records) == 1453, len(records)

text = PAGE.read_text(encoding='utf-8')
start = '<tbody id="rows">'
end = '</tbody>'
pos = text.find(start)
if pos < 0:
    raise SystemExit('tbody start not found')
close = text.find(end, pos)
if close < 0:
    raise SystemExit('tbody end not found')
rows_html = ''.join(row(x) for x in records)
text = text[:pos+len(start)] + rows_html + text[close:]
# Static summary values are visible even before JavaScript runs.
text = text.replace('<strong id="sTotal">—</strong>', '<strong id="sTotal">1.453</strong>')
text = text.replace('<strong id="sPrimary">—</strong>', '<strong id="sPrimary">579</strong>')
text = text.replace('<strong id="sMiddle">—</strong>', '<strong id="sMiddle">385</strong>')
text = text.replace('<strong id="sKg">—</strong>', '<strong id="sKg">225</strong>')
text = text.replace('<strong id="shown">—</strong>', '<strong id="shown">1.453</strong>')
PAGE.write_text(text, encoding='utf-8')

check = PAGE.read_text(encoding='utf-8')
assert check.count('class="static-review-row"') == 1453
assert 'Beyaz Fidan Anaokulu' in check
print('rendered 1453 static rows into eksik-veriler.html')
