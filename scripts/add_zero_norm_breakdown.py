from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
text = INDEX.read_text(encoding="utf-8")

css = r'''
  <style id="zero-norm-breakdown-style">
    .zero-norm-breakdown{
      display:flex;
      align-items:center;
      gap:12px;
      padding:9px 18px;
      border-bottom:1px solid var(--line);
      background:#f7f3e9;
      color:#5e675f;
      font-size:10.5px;
      overflow-x:auto;
      scrollbar-width:thin;
    }
    .zero-norm-title{
      flex:0 0 auto;
      font-weight:800;
      color:#5d4c2b;
      white-space:nowrap;
    }
    .zero-norm-total{
      display:inline-flex;
      align-items:center;
      gap:5px;
      padding:4px 8px;
      border-radius:999px;
      background:#efe2c5;
      color:#6b4c18;
      font-weight:800;
      white-space:nowrap;
    }
    .zero-norm-levels{
      display:flex;
      align-items:center;
      gap:6px;
      flex-wrap:nowrap;
    }
    .zero-norm-chip{
      display:inline-flex;
      align-items:center;
      gap:4px;
      padding:4px 7px;
      border:1px solid #ddd4c3;
      border-radius:999px;
      background:#fffdf8;
      color:#56625c;
      white-space:nowrap;
    }
    .zero-norm-chip b{color:#3f4b45}
    .zero-norm-note{
      margin-left:auto;
      color:#8a867d;
      white-space:nowrap;
      font-size:9.5px;
    }
    @media(max-width:680px){
      .zero-norm-breakdown{padding:8px 12px;gap:8px}
      .zero-norm-note{display:none}
    }
  </style>
'''
if 'id="zero-norm-breakdown-style"' not in text:
    text = text.replace('</head>', css + '\n</head>', 1)

anchor = '      <div id="loadingBox" class="loading-box">'
block = '''      <div class="zero-norm-breakdown" aria-label="Öğrenci sayısı eşiği nedeniyle norm oluşmayan okullar">
        <span class="zero-norm-title">Öğrenci eşiği nedeniyle 0 norm</span>
        <span class="zero-norm-total">Toplam <b id="zeroNormTotal">—</b></span>
        <div class="zero-norm-levels" id="zeroNormLevels"></div>
        <span class="zero-norm-note">Eksik veri, RAM ve kapsam dışı kurumlar dahil değildir.</span>
      </div>
'''
if 'id="zeroNormTotal"' not in text:
    if anchor not in text:
        raise RuntimeError('loading anchor not found')
    text = text.replace(anchor, block + anchor, 1)

# Add threshold helper before updateStats.
helper = r'''function isZeroNormByStudentThreshold(r){
  if(r.norm!==0) return false;
  const n=r.ogrenci_sayisi_etkin;
  if(r.kademe==="Anaokulu") return !!r.ogrenci_sayisi_alt_100||(n!==null&&n<150);
  if(r.kademe==="İlkokul") return n!==null&&n<300;
  if(r.kademe==="Ortaokul"||r.kademe==="Lise") return n!==null&&n<150;
  if(r.kademe==="Özel Eğitim") return n!==null&&n<25;
  if(r.kademe==="Meslekî Eğitim Merkezi") return n!==null&&n<200;
  return false;
}
function updateZeroNormBreakdown(){
  const levels=["Anaokulu","İlkokul","Ortaokul","Lise","Özel Eğitim","Meslekî Eğitim Merkezi"];
  const labels={"Anaokulu":"Anaokulu","İlkokul":"İlkokul","Ortaokul":"Ortaokul","Lise":"Lise","Özel Eğitim":"Özel eğitim","Meslekî Eğitim Merkezi":"Meslekî eğitim*"};
  const rows=filtered.filter(isZeroNormByStudentThreshold);
  const counts=Object.fromEntries(levels.map(k=>[k,0]));
  for(const r of rows) if(Object.prototype.hasOwnProperty.call(counts,r.kademe)) counts[r.kademe]++;
  const totalEl=$("zeroNormTotal"),levelsEl=$("zeroNormLevels");
  if(totalEl) totalEl.textContent=fmt(rows.length);
  if(levelsEl) levelsEl.innerHTML=levels.map(k=>`<span class="zero-norm-chip">${labels[k]} <b>${fmt(counts[k])}</b></span>`).join("");
}
'''
if 'function isZeroNormByStudentThreshold' not in text:
    marker = 'function updateStats(){'
    pos = text.find(marker)
    if pos < 0:
        raise RuntimeError('updateStats marker not found')
    text = text[:pos] + helper + text[pos:]

# Ensure every filter refresh updates the new breakdown.
old_apply = 'page=1;sortRows();render();updateStats();renderNormSummary();}'
new_apply = 'page=1;sortRows();render();updateStats();updateZeroNormBreakdown();renderNormSummary();}'
if old_apply in text:
    text = text.replace(old_apply, new_apply, 1)
elif 'updateZeroNormBreakdown();renderNormSummary();' not in text:
    raise RuntimeError('applyFilters anchor not found')

# Slightly reduce table viewport to account for compact breakdown row.
text = text.replace('max-height: calc(100vh - 300px) !important;', 'max-height: calc(100vh - 336px) !important;')
text = text.replace('max-height: calc(100vh - 344px) !important;', 'max-height: calc(100vh - 380px) !important;')
text = text.replace('max-height: calc(100vh - 356px) !important;', 'max-height: calc(100vh - 392px) !important;')

INDEX.write_text(text, encoding="utf-8")
print('zero-norm threshold breakdown added')
