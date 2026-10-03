from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
text = INDEX.read_text(encoding="utf-8")

STYLE = r'''
  <style id="table-alignment-v4">
    /* Tabloyu panel genişliğine tam oturt; başlık ve satırlar aynı grid'i kullansın. */
    .results,
    .table-wrap{
      width:100%!important;
      max-width:100%!important;
      box-sizing:border-box!important;
    }

    .table-wrap{
      overflow-x:auto!important;
      overflow-y:visible!important;
    }

    .results table{
      width:100%!important;
      min-width:0!important;
      max-width:100%!important;
      table-layout:fixed!important;
      border-collapse:collapse!important;
    }

    .results thead th{
      position:static!important;
      top:auto!important;
      z-index:auto!important;
      box-sizing:border-box!important;
      vertical-align:bottom!important;
      white-space:normal!important;
      overflow-wrap:normal!important;
      word-break:normal!important;
      line-height:1.25!important;
      padding:10px 10px!important;
      background:#f3f6f4!important;
    }

    .results tbody td{
      box-sizing:border-box!important;
      padding:9px 10px!important;
    }

    /* Toplam tam %100. */
    .results th:nth-child(1),.results td:nth-child(1){width:7%!important;min-width:0!important}
    .results th:nth-child(2),.results td:nth-child(2){width:9%!important;min-width:0!important}
    .results th:nth-child(3),.results td:nth-child(3){width:27%!important;min-width:0!important}
    .results th:nth-child(4),.results td:nth-child(4){width:19%!important;min-width:0!important}
    .results th:nth-child(5),.results td:nth-child(5){width:9%!important;min-width:0!important}
    .results th:nth-child(6),.results td:nth-child(6){width:14%!important;min-width:0!important}
    .results th:nth-child(7),.results td:nth-child(7){width:15%!important;min-width:0!important}

    .school-name{
      min-width:0!important;
      max-width:100%!important;
      overflow-wrap:anywhere!important;
    }
    .school-code{white-space:normal!important}
    .reason{max-width:100%!important}

    /* Üst özet şeridi de tablo/panel ile aynı sınırları kullansın. */
    .zero-norm-breakdown,
    .coverage-note,
    .results-summary,
    .results-head{
      width:100%!important;
      box-sizing:border-box!important;
    }

    @media(max-width:900px){
      .results table{
        min-width:1040px!important;
        table-layout:fixed!important;
      }
      .results th:nth-child(1),.results td:nth-child(1){width:72px!important}
      .results th:nth-child(2),.results td:nth-child(2){width:92px!important}
      .results th:nth-child(3),.results td:nth-child(3){width:280px!important}
      .results th:nth-child(4),.results td:nth-child(4){width:190px!important}
      .results th:nth-child(5),.results td:nth-child(5){width:90px!important}
      .results th:nth-child(6),.results td:nth-child(6){width:140px!important}
      .results th:nth-child(7),.results td:nth-child(7){width:176px!important}
    }
  </style>
'''

if 'id="table-alignment-v4"' not in text:
    text = text.replace('</head>', STYLE + '\n</head>', 1)

INDEX.write_text(text, encoding="utf-8")
print('table alignment v4 applied: fixed 100% column grid, non-sticky header')
