from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
text = INDEX.read_text(encoding="utf-8")

STYLE = r'''
  <style id="final-table-density">
    .coverage-note{
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:14px;
      padding:8px 18px 9px;
      border-bottom:1px solid var(--line);
      background:#f7faf7;
      color:#60716a;
      font-size:10.5px;
      line-height:1.35;
    }
    .coverage-note b{color:var(--ink)}
    .coverage-note .coverage-rate{
      flex:0 0 auto;
      display:inline-flex;
      align-items:center;
      border:1px solid #cddbd2;
      background:#e8f0ea;
      color:#315a4c;
      border-radius:999px;
      padding:4px 8px;
      font-weight:800;
      white-space:nowrap;
    }

    .results-summary{
      gap:8px !important;
      padding:9px 18px !important;
    }
    .results-summary-card{
      padding:9px 12px !important;
      border-radius:11px !important;
    }
    .results-summary-card span{margin-bottom:4px !important;font-size:9px !important}
    .results-summary-card strong{font-size:24px !important}
    .results-summary-card small{margin-top:3px !important;font-size:9px !important}

    .results-head{padding:10px 18px !important}
    .results-head h2{font-size:24px !important;margin-top:2px !important}
    .secondary-btn{padding:8px 11px !important;font-size:11px !important;border-radius:9px !important}

    .table-wrap{
      max-height:calc(100vh - 285px) !important;
      min-height:440px !important;
    }
    .results table{
      width:100% !important;
      min-width:900px !important;
      table-layout:auto;
      font-size:11px !important;
    }
    .results thead th{
      padding:8px 9px !important;
      font-size:9px !important;
      letter-spacing:.035em !important;
    }
    .results tbody td{
      padding:7px 9px !important;
      line-height:1.2 !important;
    }
    .school-name{
      min-width:190px !important;
      max-width:330px;
      line-height:1.2 !important;
    }
    .school-code{
      display:inline !important;
      margin-left:6px !important;
      margin-top:0 !important;
      font-size:8.5px !important;
      color:#98a19d !important;
      white-space:nowrap;
    }
    .type-pill,.status-pill{
      padding:3px 6px !important;
      font-size:9.5px !important;
    }
    .norm-badge{
      min-width:28px !important;
      padding:4px 7px !important;
      font-size:11px !important;
    }
    .reason{
      margin-top:3px !important;
      font-size:8.5px !important;
      line-height:1.2 !important;
      max-width:190px !important;
      display:-webkit-box;
      -webkit-line-clamp:1;
      -webkit-box-orient:vertical;
      overflow:hidden;
    }
    .student-unavailable{padding:3px 6px !important;font-size:9px !important}
    .pagination{padding:7px 12px !important}
    .pagination button{padding:6px 10px !important;font-size:10px !important}
    .pagination span{font-size:10px !important}

    @media(max-width:1100px){
      .table-wrap{max-height:calc(100vh - 330px) !important}
      .results table{min-width:860px !important}
    }
    @media(max-width:680px){
      .coverage-note{padding:7px 12px;font-size:9.5px;align-items:flex-start}
      .coverage-note .coverage-rate{font-size:9px;padding:3px 6px}
      .results-summary{padding:8px 12px !important}
      .results-head{padding:9px 12px !important}
      .table-wrap{max-height:calc(100vh - 355px) !important;min-height:380px !important}
      .results table{min-width:820px !important;font-size:10.5px !important}
      .results tbody td{padding:6px 8px !important}
    }
  </style>
'''

if 'id="final-table-density"' not in text:
    text = text.replace('</head>', STYLE + '\n</head>', 1)

coverage = '''      <div class="coverage-note" aria-label="Veri kapsamı">
        <span><b>Türkiye geneli veri kapsamı:</b> Platformdaki 14.936.079 öğrenci, MEB 2025-2026 resmî okul öğrenci toplamı olan 15.167.794 öğrencinin yaklaşık <b>%98,5</b>'ine karşılık gelir.</span>
        <span class="coverage-rate">%98,5 kapsama</span>
      </div>'''
if 'class="coverage-note"' not in text:
    anchor = '''      </div>
      <div id="loadingBox" class="loading-box">'''
    if anchor not in text:
        raise RuntimeError('coverage insertion anchor not found')
    text = text.replace(anchor, '      </div>\n' + coverage + '\n      <div id="loadingBox" class="loading-box">', 1)

# Remove the source column from the visible table.
text = text.replace('<th>Hesap</th><th>Kaynak</th>', '<th>Hesap</th>')
text = text.replace('const statusClass=r.status==="Hesaplandı"?"":"missing";const src=r.kaynak_url||r.web_sitesi;return', 'const statusClass=r.status==="Hesaplandı"?"":"missing";return')
source_cell = '<td><span class="status-pill ${statusClass}">${esc(r.status)}</span><span class="reason">${esc(r.reason)}</span></td><td>${src?`<a class="source-link" href="${esc(src)}" target="_blank" rel="noopener">MEB ↗</a>`:"—"}</td></tr>'
no_source_cell = '<td><span class="status-pill ${statusClass}">${esc(r.status)}</span><span class="reason">${esc(r.reason)}</span></td></tr>'
text = text.replace(source_cell, no_source_cell)

# Remove source URL from downloaded CSV as requested.
old_csv = 'const cols=["il","ilce","okul_adi","kurum_kodu","kademe","okul_turu","ogrenci_sayisi","ogrenci_sayilari","ogrenci_sayisi_etkin","ogrenci_dogrulama","norm","status","reason","kaynak_url"],labels=["il","ilce","okul_adi","kurum_kodu","kademe","okul_turu","ogrenci_sayisi_csv","ogrenci_sayilari_csv","kullanilan_ogrenci_sayisi","ogrenci_dogrulama","rehber_ogretmen_normu","norm_hesap_durumu","norm_gerekce","kaynak_url"]'
new_csv = 'const cols=["il","ilce","okul_adi","kurum_kodu","kademe","okul_turu","ogrenci_sayisi","ogrenci_sayilari","ogrenci_sayisi_etkin","ogrenci_dogrulama","norm","status","reason"],labels=["il","ilce","okul_adi","kurum_kodu","kademe","okul_turu","ogrenci_sayisi_csv","ogrenci_sayilari_csv","kullanilan_ogrenci_sayisi","ogrenci_dogrulama","rehber_ogretmen_normu","norm_hesap_durumu","norm_gerekce"]'
if old_csv in text:
    text = text.replace(old_csv, new_csv, 1)
elif '"kaynak_url"],labels=' in text:
    raise RuntimeError('CSV source field still present but expected anchor changed')

INDEX.write_text(text, encoding='utf-8')
print('final dense table, coverage note and source cleanup applied')
