from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
text = INDEX.read_text(encoding="utf-8")

old = '''      <div class="coverage-note" aria-label="Veri kapsamı">
        <span><b>Türkiye geneli veri kapsamı:</b> Platformdaki 14.936.079 öğrenci, MEB 2025-2026 resmî okul öğrenci toplamı olan 15.167.794 öğrencinin yaklaşık <b>%98,5</b>'ine karşılık gelir.</span>
        <span class="coverage-rate">%98,5 kapsama</span>
      </div>'''
new = '''      <div class="coverage-note" aria-label="Veri kapsamı">
        <span><b>Türkiye geneli veri kapsamı:</b> Platformdaki 14.936.079 öğrenci, MEB 2025-2026 resmî okul öğrenci toplamı olan 15.167.794 öğrencinin yaklaşık <b>%98,5</b>'ine karşılık gelir. <b>Özel okul verileri bu analize dahil edilmemiştir.</b></span>
        <span class="coverage-rate">%98,5 kapsama</span>
      </div>'''

if old in text:
    text = text.replace(old, new, 1)
elif "Özel okul verileri bu analize dahil edilmemiştir." not in text:
    anchor = "<span class=\"coverage-rate\">%98,5 kapsama</span>"
    if anchor not in text:
        raise RuntimeError("coverage note anchor not found")
    text = text.replace(anchor, '<span class="private-school-note">Özel okul verileri dahil değildir.</span>' + anchor, 1)

INDEX.write_text(text, encoding="utf-8")
print("private school scope note applied")
