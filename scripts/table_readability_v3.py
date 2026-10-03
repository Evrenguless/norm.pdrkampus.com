from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
text = INDEX.read_text(encoding="utf-8")

STYLE = r'''
  <style id="table-readability-v3">
    /* Referans PDRnormcalismasi yaklaşımı: dikey kaydırma sayfaya ait. */
    .results{
      overflow:visible!important;
      border-radius:14px!important;
    }

    .table-wrap{
      max-height:none!important;
      min-height:0!important;
      height:auto!important;
      overflow-x:auto!important;
      overflow-y:visible!important;
      background:#fff!important;
      scrollbar-gutter:stable;
    }

    .results table{
      width:100%!important;
      min-width:1120px!important;
      table-layout:auto!important;
      border-collapse:separate!important;
      border-spacing:0!important;
      font-size:11.5px!important;
      color:#30443c!important;
    }

    .results thead th{
      position:sticky!important;
      top:58px!important;
      z-index:20!important;
      padding:10px 11px!important;
      background:#f3f6f4!important;
      color:#596a63!important;
      border-bottom:1px solid #cfd9d3!important;
      box-shadow:0 1px 0 rgba(20,50,40,.04)!important;
      font-size:9.5px!important;
      line-height:1.15!important;
      letter-spacing:.055em!important;
      text-transform:uppercase!important;
      font-weight:800!important;
      white-space:nowrap!important;
    }

    .results tbody td{
      padding:9px 11px!important;
      border-bottom:1px solid #e6ece8!important;
      vertical-align:top!important;
      line-height:1.35!important;
      color:#344940!important;
      background:transparent!important;
    }

    .results tbody tr:nth-child(even){background:#fafcfa!important}
    .results tbody tr:hover{background:#f0f6f2!important}

    .results th:nth-child(1),.results td:nth-child(1){width:76px;min-width:76px}
    .results th:nth-child(2),.results td:nth-child(2){width:105px;min-width:105px}
    .results th:nth-child(3),.results td:nth-child(3){width:29%;min-width:270px}
    .results th:nth-child(4),.results td:nth-child(4){width:19%;min-width:190px}
    .results th:nth-child(5),.results td:nth-child(5){width:88px;min-width:88px}
    .results th:nth-child(6),.results td:nth-child(6){width:118px;min-width:118px}
    .results th:nth-child(7),.results td:nth-child(7){width:27%;min-width:260px}

    .school-name{
      min-width:270px!important;
      max-width:none!important;
      color:#193a2d!important;
      font-size:11.8px!important;
      line-height:1.3!important;
      font-weight:750!important;
    }
    .school-code{
      display:block!important;
      margin:3px 0 0!important;
      color:#8b9892!important;
      font-size:9px!important;
      line-height:1.2!important;
      font-weight:550!important;
      white-space:nowrap!important;
    }

    .type-pill{
      display:inline-flex!important;
      padding:3px 7px!important;
      border-radius:7px!important;
      font-size:9.5px!important;
      font-weight:750!important;
      line-height:1.2!important;
    }

    .status-pill{
      display:inline-flex!important;
      padding:3px 7px!important;
      border-radius:7px!important;
      font-size:9.5px!important;
      font-weight:750!important;
      line-height:1.2!important;
    }

    .reason{
      display:-webkit-box!important;
      -webkit-line-clamp:2!important;
      -webkit-box-orient:vertical!important;
      white-space:normal!important;
      overflow:hidden!important;
      text-overflow:ellipsis!important;
      max-width:none!important;
      margin-top:4px!important;
      color:#74837d!important;
      font-size:9.5px!important;
      line-height:1.35!important;
    }

    .norm-badge{
      min-width:30px!important;
      padding:5px 8px!important;
      border-radius:8px!important;
      font-size:11px!important;
      font-weight:800!important;
    }

    .student-unavailable{font-size:10px!important;font-weight:700!important}
    .numeric{font-variant-numeric:tabular-nums!important;font-weight:650!important}

    .pagination{
      position:static!important;
      bottom:auto!important;
      min-height:46px!important;
      padding:8px 12px!important;
      background:#f8faf8!important;
      border-top:1px solid #dfe6e1!important;
    }
    .pagination button{
      height:30px!important;
      padding:0 11px!important;
      font-size:10px!important;
      border-radius:8px!important;
    }
    #pageInfo{font-size:10px!important}

    /* Filtreler de sayfaya ait; tabloyu ekran içine hapsetme. */
    .filters{position:relative!important;top:auto!important}

    @media(max-width:680px){
      .results thead th{top:54px!important}
      .results table{min-width:1020px!important;font-size:11px!important}
      .results tbody td{padding:8px 9px!important}
      .school-name{font-size:11.3px!important}
    }
  </style>
'''

if 'id="table-readability-v3"' not in text:
    text = text.replace('</head>', STYLE + '\n</head>', 1)

# Long page scrolling is more useful with a larger page size.
text = text.replace('const PAGE_SIZE = 50;', 'const PAGE_SIZE = 100;')

INDEX.write_text(text, encoding="utf-8")
print('table readability v3 applied: page scrolling, clearer rows, 100 records/page')
