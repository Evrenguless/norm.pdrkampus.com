"""Shared PDR Kampüs navigation; ordinary links, no application state changes."""
from html import escape as E
PLATFORMS = [
 ('platform','https://pdrkampus.com/','Ana platform','Kaynaklar, rehberler ve meslektaş paylaşımı.'),
 ('questions','https://cikmissorular.pdrkampus.com/','Çıkmış sorular','Yıllara ve konulara göre PDR ÖABT sorularını çöz.'),
 ('analysis','https://analiz.pdrkampus.com/','Sınav analizi','AGS / PDR puan ve sıralama tahminlerini incele.'),
 ('norm','https://norm.pdrkampus.com/','Norm hesaplama','Okul verilerini ve rehber öğretmen normunu incele.')
]
def links(current, descriptions=False):
 return ''.join('<a href="'+url+'"'+(' aria-current="true"' if key==current else '')+'><strong>'+title+'</strong>'+('<span>'+desc+'</span>' if descriptions else '')+'</a>' for key,url,title,desc in PLATFORMS)
def navigation(current):
 title=next(p[2] for p in PLATFORMS if p[0]==current)
 return '<div class="pk-network" data-campus-platform="'+current+'"><span class="pk-network-label">PDR Kampüs araçları</span><nav class="pk-network-desktop pk-network-links" aria-label="PDR Kampüs platformları">'+links(current)+'</nav><details class="pk-network-mobile"><summary>Platformlar <span>'+title+' ▾</span></summary><nav class="pk-network-links" aria-label="PDR Kampüs platformları (mobil)">'+links(current)+'</nav></details></div>'
def footer(current):
 return '<section class="pk-network-footer" aria-label="Diğer PDR Kampüs çalışma alanları"><h2>Tek kampüs, farklı çalışma alanları.</h2><p>İhtiyacına uygun kaynak veya araçla devam et.</p><nav class="pk-network-footer-links" aria-label="PDR Kampüs çalışma alanları">'+links(current,True)+'</nav></section>'
def context(title,text,items):
 return '<section class="pk-context"><h2>'+E(title)+'</h2><p>'+E(text)+'</p><nav aria-label="İlgili çalışma araçları">'+''.join('<a href="'+E(url,quote=True)+'">'+E(label)+' →</a>' for url,label in items)+'</nav></section>'
