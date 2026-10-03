from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
text = INDEX.read_text(encoding="utf-8")

STYLE = r'''
  <style id="table-layout-v3">
    /* Referans tablo yaklaşımı: merkezlenmiş içerik, sayfa scroll'u, doğal tablo başlığı. */
    body{background:#f5f7f8!important;}

    main{
      width:min(1240px, calc(100% - 40px))!important;
      max-width:1240px!important;
      margin:22px auto 44px!important;
      padding:0!important;
    }

    .filters,
    .results{
      width:100%!important;
      max-width:none!important;
      margin-left:0!important;
      margin-right:0!important;
    }

    .filters{
      margin-bottom:16px!important;
      border-radius:10px!important;
      box-shadow:none!important;
      border:1px solid #dfe5e8!important;
    }

    .results{
      border-radius:10px!important;
      overflow:visible!important;
      box-shadow:none!important;
      border:1px solid #dfe5e8!important;
    }

    .results-head{
      border-radius:10px 10px 0 0!important;
      padding:14px 16px!important;
    }

    .table-wrap{
      max-height:none!important;
      min-height:0!important;
      height:auto!important;
      overflow-x:auto!important;
      overflow-y:visible!important;
      background:#fff!important;
      scrollbar-width:thin;
    }

    .results table{
      width:100%!important;
      min-width:1080px!important;
      table-layout:fixed!important;
      border-collapse:collapse!important;
      font-size:12px!important;
      background:#fff!important;
    }

    .results thead,
    .results thead tr{
      display:table-header-group!important;
      position:static!important;
    }

    .results thead th{
      position:static!important;
      top:auto!important;
      z-index:auto!important;
      padding:11px 12px!important;
      background:#f1f4f3!important;
      border-bottom:1px solid #cfd8d4!important;
      color:#51655d!important;
      font-size:10px!important;
      line-height:1.25!important;
      letter-spacing:.045em!important;
      font-weight:800!important;
      text-transform:uppercase!important;
      vertical-align:bottom!important;
      white-space:normal!important;
    }

    .results tbody td{
      padding:10px 12px!important;
      border-bottom:1px solid #e9eeeb!important;
      vertical-align:top!important;
      line-height:1.35!important;
      color:#2d4039!important;
      font-size:12px!important;
    }

    .results tbody tr:nth-child(even){background:#fafcfb!important;}
    .results tbody tr:hover{background:#f3f7f5!important;}

    .results th:nth-child(1),.results td:nth-child(1){width:8%!important;}
    .results th:nth-child(2),.results td:nth-child(2){width:10%!important;}
    .results th:nth-child(3),.results td:nth-child(3){width:26%!important;}
    .results th:nth-child(4),.results td:nth-child(4){width:17%!important;}
    .results th:nth-child(5),.results td:nth-child(5){width:9%!important;}
    .results th:nth-child(6),.results td:nth-child(6){width:13%!important;}
    .results th:nth-child(7),.results td:nth-child(7){width:17%!important;}

    .school-name{
      min-width:0!important;
      max-width:none!important;
      font-size:12.5px!important;
      font-weight:750!important;
      color:#183d30!important;
    }
    .school-code{
      display:block!important;
      margin:3px 0 0!important;
      font-size:9.5px!important;
      color:#8c9993!important;
      font-weight:500!important;
      white-space:normal!important;
    }
    .type-pill,.status-pill{
      display:inline-flex!important;
      align-items:center!important;
      padding:3px 7px!important;
      border-radius:999px!important;
      font-size:9.5px!important;
      line-height:1.2!important;
      font-weight:750!important;
    }
    .reason{
      display:-webkit-box!important;
      margin-top:4px!important;
      max-width:none!important;
      overflow:hidden!important;
      -webkit-box-orient:vertical!important;
      -webkit-line-clamp:2!important;
      white-space:normal!important;
      text-overflow:clip!important;
      color:#77857f!important;
      font-size:9.5px!important;
      line-height:1.35!important;
    }
    .norm-badge{
      min-width:30px!important;
      padding:4px 8px!important;
      font-size:11.5px!important;
      font-weight:800!important;
      border-radius:8px!important;
    }

    .results-summary-card strong{font-size:25px!important;}
    .coverage-note,.zero-norm-breakdown{font-size:10.5px!important;}

    .pagination{
      position:static!important;
      bottom:auto!important;
      padding:10px 14px!important;
      border-radius:0 0 10px 10px!important;
    }

    @media(max-width:1300px){
      main{width:calc(100% - 32px)!important;margin:16px auto 36px!important;}
    }
    @media(max-width:760px){
      main{width:calc(100% - 16px)!important;margin:10px auto 24px!important;}
      .results table{min-width:980px!important;}
      .results tbody td{padding:9px 10px!important;}
    }
  </style>
'''

if 'id="table-layout-v3"' not in text:
    text = text.replace('</head>', STYLE + '\n</head>', 1)

INDEX.write_text(text, encoding="utf-8")
print('table layout v3 applied')
