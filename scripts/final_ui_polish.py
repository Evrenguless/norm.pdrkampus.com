from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
INDEX=ROOT/'index.html'

text=INDEX.read_text(encoding='utf-8')

css='''
/* final publication polish */
.data-note{max-width:1180px;margin:0 auto 22px;padding:0 34px}.data-note-inner{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;padding:16px 18px;border:1px solid #d7e0da;border-radius:16px;background:rgba(255,253,248,.82);box-shadow:0 10px 30px rgba(18,60,49,.035)}.data-note-title{font-size:12px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:#3e6256;margin-bottom:5px}.data-note-copy{font-size:12px;line-height:1.6;color:#6b7974;max-width:850px}.data-note-copy b{color:#173c32}.data-note-badge{flex:none;display:inline-flex;align-items:center;border-radius:999px;background:#e8efe9;border:1px solid #d4e0d7;color:#35594d;padding:8px 11px;font-size:10.5px;font-weight:800;white-space:nowrap}.status-pill{font-weight:700}.status-pill.missing{background:#f7ead3;color:#81561d;border:1px solid #efd7ad}.status-pill.moved{background:#f7ead3;color:#84531b;border:1px solid #e9c997}.student-unavailable{display:inline-flex;align-items:center;border-radius:999px;padding:5px 8px;background:#f7ead3;color:#84531b;font-weight:800;font-size:11px}.table-wrap{scrollbar-color:#bdc9c1 transparent;scrollbar-width:thin}tbody tr{transition:background .15s ease}tbody tr:hover{background:#f4f8f4}.school-name{line-height:1.35}.reason{max-width:260px}.stat{transition:transform .15s ease,box-shadow .15s ease}.stat:hover{transform:translateY(-1px);box-shadow:0 12px 34px rgba(18,60,49,.06)}.ghost-btn{transition:background .15s ease,border-color .15s ease}.ghost-btn:hover{background:#edf3ee;border-color:#b8c9bf}.secondary-btn{transition:transform .15s ease,box-shadow .15s ease}.secondary-btn:hover{transform:translateY(-1px);box-shadow:0 8px 22px rgba(18,60,49,.16)}
@media(max-width:680px){.data-note{padding:0 18px;margin-bottom:16px}.data-note-inner{flex-direction:column;padding:14px}.data-note-badge{white-space:normal}.hero{padding-top:42px}.hero h1{font-size:42px;line-height:1.02}.stats{grid-template-columns:1fr 1fr}.stat small{font-size:10px}.table-wrap{max-height:none}.status-pill{white-space:normal;line-height:1.3}.student-unavailable{white-space:normal}}
'''
if '/* final publication polish */' not in text:
    text=text.replace('</style>',css+'</style>',1)

banner='''\n    <section class="data-note" aria-label="Veri kapsamı notu">\n      <div class="data-note-inner">\n        <div>\n          <div class="data-note-title">Veri kapsamı</div>\n          <div class="data-note-copy"><b>Bulunabilen güncel öğrenci sayıları işlendi.</b> Manuel kontrolde öğrenci sayısına ulaşılamayan bazı liseler <b>“Veri yok · Taşınmış / isim değişmiş”</b> olarak işaretlenir ve bu kayıtlar için kesin norm üretilmez.</div>\n        </div>\n        <span class="data-note-badge">Yayın öncesi manuel kontrol tamamlandı</span>\n      </div>\n    </section>\n'''
if 'aria-label="Veri kapsamı notu"' not in text:
    marker='    <section class="stats" aria-label="Özet istatistikler">'
    if marker not in text:
        raise RuntimeError('stats marker not found')
    text=text.replace(marker,banner+'\n'+marker,1)

text=text.replace('55 binden fazla okulun öğrenci sayısını Madde 21 kurallarıyla eşleştir; il, ilçe, eğitim kademesi ve hesaplanan rehberlik normuna göre filtrele.','55 binden fazla okulun öğrenci sayısını Madde 21 kurallarıyla eşleştir; il, ilçe, eğitim kademesi ve hesaplanan rehberlik normuna göre filtrele. Güncel verisine ulaşılamayan kurumlar ayrıca işaretlenir.')

# Add semantic CSS class for moved/renamed status and unavailable student display at render time.
text=text.replace('class="status-pill ${isMissingForNorm(r)?\"missing\":\"\"}"','class="status-pill ${r.status===\"Taşınmış / isim değişmiş\"?\"moved\":(isMissingForNorm(r)?\"missing\":\"\")}"')
text=text.replace('${esc(r.ogrenci_sayisi_gosterim||(r.ogrenci_sayisi_etkin===null?"—":fmt(r.ogrenci_sayisi_etkin)))}','${r.ogrenci_veri_yok?`<span class="student-unavailable">Veri yok</span>`:esc(r.ogrenci_sayisi_gosterim||(r.ogrenci_sayisi_etkin===null?"—":fmt(r.ogrenci_sayisi_etkin)))}')

INDEX.write_text(text,encoding='utf-8')
print('Final UI polish applied')
