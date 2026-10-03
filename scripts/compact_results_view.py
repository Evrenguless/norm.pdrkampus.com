from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"

STYLE = r'''
  <style id="compact-results-view">
    /* Yayın görünümü: sonuçları merkeze al, bilgilendirme/özet bloklarını gizle. */
    .hero,
    .data-note,
    .stats,
    .summary-panel,
    .method-summary,
    .loading-box,
    .topbar a[href="eksik-veriler.html"] {
      display: none !important;
    }

    body { min-height: 100vh; }

    .topbar {
      position: sticky;
      top: 0;
      z-index: 50;
      max-width: none !important;
      width: 100%;
      margin: 0 !important;
      padding: 0 24px !important;
      background: rgba(244,241,233,.96);
      backdrop-filter: blur(10px);
    }

    main { width: 100%; }

    .panel {
      max-width: none !important;
      width: 100% !important;
      margin: 0 !important;
      border-left: 0 !important;
      border-right: 0 !important;
      border-radius: 0 !important;
      box-shadow: none !important;
    }

    .filters {
      position: sticky;
      top: 72px;
      z-index: 40;
      padding: 16px 24px 18px !important;
      background: var(--paper);
      border-top: 0 !important;
      border-bottom: 1px solid var(--line) !important;
    }

    .filter-grid { margin-top: 14px !important; }
    .results { overflow: hidden; }
    .results-head { padding: 14px 24px !important; }

    .table-wrap {
      max-height: calc(100vh - 236px) !important;
      min-height: 420px;
      overflow: auto !important;
    }

    .results table { min-width: 1180px; }

    .pagination {
      position: sticky;
      bottom: 0;
      z-index: 5;
      padding: 10px 18px !important;
      background: var(--paper);
    }

    footer { display: none !important; }

    @media (max-width: 1100px) {
      .filters { top: 72px; }
      .table-wrap { max-height: calc(100vh - 280px) !important; }
    }

    @media (max-width: 680px) {
      .topbar { height: 64px !important; padding: 0 14px !important; }
      .filters { top: 64px; padding: 12px 14px 14px !important; }
      .panel-head h2 { font-size: 24px !important; }
      .filter-grid { margin-top: 10px !important; gap: 8px !important; }
      .field input, .field select { height: 42px !important; }
      .results-head { padding: 12px 14px !important; }
      .table-wrap { max-height: calc(100vh - 286px) !important; min-height: 360px; }
      .pagination { padding: 9px 12px !important; }
    }
  </style>
'''

text = INDEX.read_text(encoding="utf-8")
if 'id="compact-results-view"' not in text:
    if "</head>" not in text:
        raise RuntimeError("index.html içinde </head> bulunamadı")
    text = text.replace("</head>", STYLE + "\n</head>", 1)
    INDEX.write_text(text, encoding="utf-8")
    print("compact results view applied")
else:
    print("compact results view already present")
