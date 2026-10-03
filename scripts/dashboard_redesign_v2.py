from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
text = INDEX.read_text(encoding="utf-8")

STYLE = r'''
  <style id="dashboard-redesign-v2">
    :root{
      --dash-bg:#f4f6f3;
      --dash-paper:#ffffff;
      --dash-ink:#173229;
      --dash-muted:#6f7d77;
      --dash-line:#dfe6e1;
      --dash-green:#123c31;
      --dash-soft:#eaf1ed;
      --dash-warn:#9a6b1f;
      --dash-warn-bg:#fbf5e8;
    }

    body{
      background:var(--dash-bg)!important;
      color:var(--dash-ink)!important;
    }

    .topbar{
      height:58px!important;
      min-height:58px!important;
      padding:0 18px!important;
      background:var(--dash-green)!important;
      border:0!important;
      box-shadow:0 1px 0 rgba(0,0,0,.08)!important;
      backdrop-filter:none!important;
    }
    .topbar .brand{color:#fff!important;font-size:14px!important;font-weight:800!important;gap:8px!important}
    .topbar .brand-mark{
      width:32px!important;height:32px!important;border-radius:9px!important;
      display:inline-flex!important;align-items:center!important;justify-content:center!important;
      background:#fff!important;color:var(--dash-green)!important;font-size:11px!important;
    }
    #methodBtn{
      height:34px!important;padding:0 11px!important;border:1px solid rgba(255,255,255,.24)!important;
      background:rgba(255,255,255,.08)!important;color:#fff!important;border-radius:9px!important;font-size:11px!important;
    }

    main{padding:14px 16px 18px!important;max-width:1700px!important;margin:0 auto!important}

    .filters{
      position:relative!important;top:auto!important;z-index:1!important;
      margin:0 0 12px!important;padding:12px!important;
      background:var(--dash-paper)!important;border:1px solid var(--dash-line)!important;
      border-radius:14px!important;box-shadow:0 3px 12px rgba(20,50,40,.035)!important;
    }
    .filters .panel-head{display:flex!important;align-items:center!important;justify-content:space-between!important;margin:0 0 9px!important;padding:0!important}
    .filters .panel-head .section-kicker{display:none!important}
    .filters .panel-head h2{font-family:Manrope,system-ui,sans-serif!important;font-size:13px!important;line-height:1!important;margin:0!important;font-weight:800!important;color:var(--dash-ink)!important}
    #resetBtn{font-size:10.5px!important;color:#66766f!important}
    .filter-grid{
      display:grid!important;grid-template-columns:minmax(230px,1.7fr) repeat(5,minmax(120px,1fr))!important;
      gap:8px!important;margin:0!important;
    }
    .field{gap:4px!important}
    .field>span{font-size:9px!important;letter-spacing:.04em!important;text-transform:uppercase!important;color:#7d8984!important;font-weight:800!important}
    .field input,.field select{
      height:36px!important;min-height:36px!important;padding:0 10px!important;border:1px solid #dce4df!important;
      background:#fbfcfb!important;border-radius:8px!important;font-size:11px!important;color:#263b33!important;
      box-shadow:none!important;
    }
    .field input:focus,.field select:focus{outline:2px solid rgba(18,60,49,.12)!important;border-color:#8da89d!important}

    .results{
      background:var(--dash-paper)!important;border:1px solid var(--dash-line)!important;border-radius:14px!important;
      overflow:hidden!important;box-shadow:0 3px 14px rgba(20,50,40,.035)!important;
    }
    .results-head{
      min-height:46px!important;padding:10px 14px!important;border-bottom:1px solid var(--dash-line)!important;
      background:#fff!important;display:flex!important;align-items:center!important;
    }
    .results-head .section-kicker{display:none!important}
    .results-head h2{
      font-family:Manrope,system-ui,sans-serif!important;font-size:13px!important;font-weight:800!important;margin:0!important;color:var(--dash-ink)!important;
    }
    .results-head h2::before{content:"Okul sonuçları · ";color:#6c7a74;font-weight:700}
    #downloadBtn{
      height:32px!important;padding:0 10px!important;border-radius:8px!important;font-size:10.5px!important;
      background:#fff!important;border:1px solid #dce4df!important;color:#365248!important;
    }

    .results-summary{
      display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:0!important;padding:0!important;
      background:#fff!important;border-bottom:1px solid var(--dash-line)!important;
    }
    .results-summary-card{
      position:relative!important;border:0!important;border-right:1px solid var(--dash-line)!important;border-radius:0!important;
      padding:13px 15px 12px!important;background:#fff!important;min-height:84px!important;
    }
    .results-summary-card:last-child{border-right:0!important}
    .results-summary-card::before{
      content:"";position:absolute;left:15px;right:15px;top:0;height:2px;border-radius:99px;background:#b8c9c1;
    }
    .results-summary-card:nth-child(2)::before{background:#7fa492}
    .results-summary-card:nth-child(3)::before{background:#3f725f}
    .results-summary-card:nth-child(4)::before{background:#c79543}
    .results-summary-card span{
      margin:0 0 6px!important;font-size:9px!important;letter-spacing:.065em!important;text-transform:uppercase!important;
      color:#7a8781!important;font-weight:800!important;
    }
    .results-summary-card strong{
      font-family:Manrope,system-ui,sans-serif!important;font-size:23px!important;line-height:1!important;font-weight:800!important;color:var(--dash-ink)!important;
    }
    .results-summary-card small{margin-top:5px!important;font-size:9.5px!important;line-height:1.3!important;color:#89958f!important}

    .coverage-note{
      min-height:38px!important;padding:8px 14px!important;display:flex!important;align-items:center!important;gap:10px!important;
      background:var(--dash-soft)!important;border-bottom:1px solid #d9e5df!important;color:#51675e!important;font-size:10px!important;line-height:1.35!important;
    }
    .coverage-note b{color:#27483b!important}
    .coverage-rate{
      margin-left:auto!important;flex:0 0 auto!important;padding:4px 8px!important;border-radius:999px!important;
      background:#fff!important;border:1px solid #cfddd6!important;color:#315d4c!important;font-weight:800!important;font-size:9.5px!important;
    }

    .zero-norm-breakdown{
      min-height:42px!important;padding:7px 14px!important;gap:8px!important;background:var(--dash-warn-bg)!important;
      border-bottom:1px solid #eadfca!important;color:#665b48!important;font-size:9.5px!important;
    }
    .zero-norm-title{font-size:9px!important;letter-spacing:.04em!important;text-transform:uppercase!important;color:#8a682c!important}
    .zero-norm-total{padding:4px 7px!important;background:#f1e3c7!important;color:#76531d!important;font-size:10px!important}
    .zero-norm-chip{padding:3px 6px!important;border-color:#e4d8c1!important;background:rgba(255,255,255,.72)!important;font-size:9px!important}
    .zero-norm-note{font-size:8.5px!important;color:#9b8f7d!important}

    .table-wrap{
      max-height:calc(100vh - 324px)!important;min-height:410px!important;overflow:auto!important;background:#fff!important;
    }
    .results table{width:100%!important;min-width:980px!important;border-collapse:separate!important;border-spacing:0!important;font-size:10.5px!important}
    .results thead th{
      position:sticky!important;top:0!important;z-index:4!important;background:#f6f8f6!important;color:#66766f!important;
      padding:7px 8px!important;border-bottom:1px solid #dbe3de!important;font-size:8.5px!important;letter-spacing:.055em!important;
      text-transform:uppercase!important;font-weight:800!important;white-space:nowrap!important;
    }
    .results tbody tr:nth-child(even){background:#fbfcfb!important}
    .results tbody tr:hover{background:#f2f7f4!important}
    .results tbody td{
      padding:6px 8px!important;border-bottom:1px solid #edf1ee!important;vertical-align:middle!important;line-height:1.18!important;color:#31453d!important;
    }
    .school-name{min-width:210px!important;max-width:330px!important;font-weight:700!important;color:#203c31!important}
    .school-code{font-size:8px!important;color:#9aa5a0!important;font-weight:500!important}
    .type-pill,.status-pill{padding:2px 5px!important;border-radius:6px!important;font-size:8.5px!important;font-weight:700!important}
    .reason{font-size:8.5px!important;line-height:1.2!important;color:#89958f!important;margin-top:2px!important;max-width:330px!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}
    .norm-badge{min-width:26px!important;padding:3px 6px!important;border-radius:7px!important;font-size:10px!important}
    .numeric{white-space:nowrap!important}

    .pagination{
      min-height:40px!important;padding:6px 12px!important;background:#fbfcfb!important;border-top:1px solid var(--dash-line)!important;
    }
    .pagination button{height:28px!important;padding:0 9px!important;border-radius:7px!important;font-size:9.5px!important}
    #pageInfo{font-size:9.5px!important;color:#75827c!important}

    @media(max-width:1150px){
      main{padding:10px!important}
      .filter-grid{grid-template-columns:repeat(3,minmax(0,1fr))!important}
      .field-search{grid-column:span 2!important}
      .results-summary{grid-template-columns:repeat(2,minmax(0,1fr))!important}
      .results-summary-card:nth-child(2){border-right:0!important}
      .results-summary-card:nth-child(-n+2){border-bottom:1px solid var(--dash-line)!important}
      .table-wrap{max-height:calc(100vh - 400px)!important}
    }
    @media(max-width:680px){
      .topbar{height:54px!important;min-height:54px!important;padding:0 10px!important}
      main{padding:8px!important}
      .filters{padding:9px!important;margin-bottom:8px!important}
      .filter-grid{grid-template-columns:1fr 1fr!important;gap:6px!important}
      .field-search{grid-column:1/-1!important}
      .field input,.field select{height:34px!important;min-height:34px!important}
      .results-summary{grid-template-columns:1fr 1fr!important}
      .results-summary-card{min-height:76px!important;padding:11px 12px!important}
      .results-summary-card strong{font-size:20px!important}
      .coverage-note{align-items:flex-start!important;flex-direction:column!important;gap:5px!important}
      .coverage-rate{margin-left:0!important}
      .zero-norm-note{display:none!important}
      .table-wrap{max-height:calc(100vh - 430px)!important;min-height:330px!important}
      .results table{min-width:900px!important}
    }
  </style>
'''

if 'id="dashboard-redesign-v2"' not in text:
    text = text.replace('</head>', STYLE + '\n</head>', 1)

# Clearer filter title.
text = text.replace('<span class="section-kicker">FİLTRELER</span><h2>Okul verisini daralt</h2>', '<span class="section-kicker">FİLTRELER</span><h2>Filtreler</h2>')

# Add a fourth KPI card for schools whose verified student count stays below the threshold.
needle = '<article class="results-summary-card"><span>Hesaplanan norm + RAM</span><strong id="resultNorm">—</strong><small id="resultNormNote">hesaplanabilen norm toplamı</small></article>'
replacement = needle + '\n        <article class="results-summary-card"><span>Eşik altında / 0 norm</span><strong id="resultZeroNorm">—</strong><small>öğrenci sayısı norm eşiğine ulaşmayan okul</small></article>'
if 'id="resultZeroNorm"' not in text:
    if needle not in text:
        raise RuntimeError('resultNorm KPI anchor not found')
    text = text.replace(needle, replacement, 1)

# Mirror the existing zero-norm total into the KPI card.
old = 'if(totalEl) totalEl.textContent=fmt(rows.length);'
new = 'if(totalEl) totalEl.textContent=fmt(rows.length);const resultZeroNorm=$("resultZeroNorm");if(resultZeroNorm)resultZeroNorm.textContent=fmt(rows.length);'
if 'resultZeroNorm.textContent' not in text:
    if old not in text:
        raise RuntimeError('zero norm update anchor not found')
    text = text.replace(old, new, 1)

INDEX.write_text(text, encoding="utf-8")
print('dashboard redesign v2 applied')
