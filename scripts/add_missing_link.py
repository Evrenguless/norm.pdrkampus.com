from pathlib import Path
p=Path('index.html')
s=p.read_text(encoding='utf-8')
old='''  <header class="topbar">\n    <a class="brand" href="./"><span class="brand-mark">PDR</span><span>Norm Haritası</span></a>\n    <button id="methodBtn" class="ghost-btn" type="button">Hesaplama yöntemi</button>\n  </header>'''
new='''  <header class="topbar">\n    <a class="brand" href="./"><span class="brand-mark">PDR</span><span>Norm Haritası</span></a>\n    <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">\n      <a class="ghost-btn" href="eksik-veriler.html" style="text-decoration:none;display:inline-flex;align-items:center">Eksik Veriler · 1.453</a>\n      <button id="methodBtn" class="ghost-btn" type="button">Hesaplama yöntemi</button>\n    </div>\n  </header>'''
if 'Eksik Veriler · 1.453' not in s:
    if old not in s:
        raise SystemExit('topbar target not found')
    s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('patched')
