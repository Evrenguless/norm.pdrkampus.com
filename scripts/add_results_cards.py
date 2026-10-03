from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
text = INDEX.read_text(encoding="utf-8")

css = r'''
  <style>
    .results-summary{
      display:grid;
      grid-template-columns:repeat(3,minmax(0,1fr));
      gap:10px;
      padding:12px 18px;
      background:var(--bg);
      border-bottom:1px solid var(--line);
    }
    .results-summary-card{
      background:var(--paper);
      border:1px solid var(--line);
      border-radius:14px;
      padding:12px 14px;
      min-width:0;
    }
    .results-summary-card span{
      display:block;
      font-size:10px;
      font-weight:800;
      letter-spacing:.07em;
      text-transform:uppercase;
      color:#78857f;
      margin-bottom:6px;
    }
    .results-summary-card strong{
      display:block;
      font-family:"Source Serif 4",Georgia,serif;
      font-size:28px;
      line-height:1;
      color:var(--ink);
    }
    .results-summary-card small{
      display:block;
      margin-top:5px;
      color:#89928e;
      font-size:10px;
    }
    @media(max-width:680px){
      .results-summary{grid-template-columns:1fr 1fr;padding:10px 12px;gap:8px}
      .results-summary-card:first-child{grid-column:1/-1}
      .results-summary-card{padding:10px 12px}
      .results-summary-card strong{font-size:24px}
    }
  </style>
'''
if 'class="results-summary"' not in text:
    text = text.replace('</head>', css + '\n</head>', 1)

old = '''    <section class="panel results">
      <div class="results-head"><div><span class="section-kicker">SONUÇLAR</span><h2><span id="resultCount">—</span> okul</h2></div><div class="actions"><button id="downloadBtn" class="secondary-btn" type="button" disabled>Filtrelenmiş CSV'yi indir</button></div></div>'''
new = '''    <section class="panel results">
      <div class="results-head"><div><span class="section-kicker">SONUÇLAR</span><h2><span id="resultCount">—</span> okul</h2></div><div class="actions"><button id="downloadBtn" class="secondary-btn" type="button" disabled>Filtrelenmiş CSV'yi indir</button></div></div>
      <div class="results-summary" aria-label="Filtrelenmiş sonuç özeti">
        <article class="results-summary-card"><span>Toplam okul</span><strong id="resultSchools">—</strong><small>filtreyle eşleşen kayıt</small></article>
        <article class="results-summary-card"><span>Toplam öğrenci</span><strong id="resultStudents">—</strong><small>öğrenci sayısı bulunan kayıtlar</small></article>
        <article class="results-summary-card"><span>Hesaplanan norm</span><strong id="resultNorm">—</strong><small>hesaplanabilen norm toplamı</small></article>
      </div>'''
if 'id="resultStudents"' not in text:
    if old not in text:
        raise RuntimeError('results section anchor not found')
    text = text.replace(old, new, 1)

old_stats = 'function updateStats(){const known=filtered.filter(r=>r.norm!==null),total=known.reduce((s,r)=>s+r.norm,0),eligible=known.filter(r=>r.norm>=1).length,miss=filtered.filter(isMissingForNorm).length;$("statSchools").textContent=fmt(filtered.length);$("statNorm").textContent=fmt(total);$("statEligible").textContent=fmt(eligible);$("statMissing").textContent=fmt(miss);}'
new_stats = 'function updateStats(){const known=filtered.filter(r=>r.norm!==null),total=known.reduce((s,r)=>s+r.norm,0),eligible=known.filter(r=>r.norm>=1).length,miss=filtered.filter(isMissingForNorm).length,studentTotal=filtered.reduce((s,r)=>s+(Number.isFinite(Number(r.ogrenci_sayisi_etkin))?Number(r.ogrenci_sayisi_etkin):0),0);const statSchools=$("statSchools"),statNorm=$("statNorm"),statEligible=$("statEligible"),statMissing=$("statMissing");if(statSchools)statSchools.textContent=fmt(filtered.length);if(statNorm)statNorm.textContent=fmt(total);if(statEligible)statEligible.textContent=fmt(eligible);if(statMissing)statMissing.textContent=fmt(miss);$("resultSchools").textContent=fmt(filtered.length);$("resultStudents").textContent=fmt(studentTotal);$("resultNorm").textContent=fmt(total);}'
if 'studentTotal=filtered.reduce' not in text:
    if old_stats not in text:
        raise RuntimeError('updateStats anchor not found')
    text = text.replace(old_stats, new_stats, 1)

# Account for the new summary strip in the full-screen table height.
text = text.replace('max-height: calc(100vh - 236px) !important;', 'max-height: calc(100vh - 330px) !important;')
text = text.replace('max-height: calc(100vh - 280px) !important;', 'max-height: calc(100vh - 374px) !important;')
text = text.replace('max-height: calc(100vh - 286px) !important;', 'max-height: calc(100vh - 390px) !important;')

INDEX.write_text(text, encoding="utf-8")
print('results summary cards applied')
