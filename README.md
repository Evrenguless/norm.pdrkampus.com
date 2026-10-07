# PDR Norm Haritası

Türkiye'deki okul verisini, **Rehberlik Alan Öğretmeni Norm Kadrosu – Madde 21** eşikleriyle tarayan statik web uygulaması.

## Hesaplama özeti

- İlkokul: 300+ öğrenci → 1 norm; 500 ve katlarında her defasında +1.
- Ortaokul / İmam Hatip Ortaokulu: 150+ → 1; 500 ve katlarında +1.
- Ortaöğretim: 150+ → 1; 500 ve katlarında +1.
- Özel eğitim (özel eğitim anaokulu hariç): 25+ → 1; 100 ve katlarında +1.
- Meslekî eğitim merkezi: 200+ çırak/kursiyer → 1; CSV'deki öğrenci sayısı vekil veri olarak kullanılır.
- Yatılı/pansiyonlu: okul adı/türünde açık işaret varsa en az 1 norm.
- RAM: nüfus verisi olmadığı için otomatik hesaplanmaz.
- Madde 21/2-d: ilçe merkezi bilgisi veri setinde olmadığından otomatik eklenmez.
- Madde 21/4: norm sayısı değil atama sırası kuralı olduğundan hesaplanan normu değiştirmez.

## Veri

`data/chunk-001.csv` … `data/chunk-056.csv` dosyaları kaynak CSV'nin sıralı parçalarıdır. Tarayıcı bunları birleştirip CSV'yi parse eder ve norm sütununu istemci tarafında hesaplar. Böylece kaynak veri aynen korunur.

## Yayın

Repo kökünden GitHub Pages ile çalışacak şekilde hazırlanmıştır. `CNAME` dosyası `norm.pdrkampus.com` alan adını içerir.

## Arayüz ve veri güncellemesi

Okul normu ve RAM mevcut personel sayısı ayrı gösterilir. Okul tablolarında kaynak adresleri, CSV kontrol tarihi ve manuel düzeltme tarihi bulunur; tarihsiz kayıtlar belirtilir. Filtreler URL parametreleri (`il`, `ilce`, `q`, `kademe`, `norm`, `ogrenci`) ile paylaşılır. CSV ve Excel ile açılabilen XML çalışma kitabı dışa aktarımı tüm filtrelenmiş kayıtları içerir.

Modern tarayıcılar `data/schools-v1.json.gz` ve `data/overrides-v1.json.gz` dosyalarını yükler; DecompressionStream olmayan tarayıcılar kaynak CSV/JSON dosyalarını kullanır. Kaynak veri veya manuel düzeltmeler güncellenince `python3 tools/build-data.py` çalıştırılıp iki sıkıştırılmış dosya da aynı committe yayımlanmalıdır. Bu işlem sayı seçimi ve norm formüllerini değiştirmez.

## İstanbul kurum profilleri

`Publish PDR Norm and Istanbul School Profiles` GitHub Actions iş akışı, ana uygulama ve İstanbul'daki kaynak kurum kayıtlarını aynı Pages sürümünde yayınlar. `scripts/build_school_profiles.py --output /absolute/output/outside/checkout` komutu, mevcut uygulamadan norm modelini okuyarak statik profiller, ilçe dizinleri ve sitemap üretir. Node.js ve Python gereklidir. Kaynak veri dosyaları değiştirilmez; kişisel kullanım için üretilmiş öğrenci senaryoları kamuya açık kaynak profillerinden hariç tutulur. Eksik öğrenci ve personel kaydı sıfır sayılmaz.

Görsel sistem `assets/school-profile.css` dosyasıyla ve mevcut `assets/logo.png` logosuyla ortaktır. Her profilde iki adet `Tüm istatistikleri için` butonu ana norm haritasına yönlendirir. Okul profilleri ana sayfada tanıtım alanı olarak gösterilmez. `scripts/test_school_profiles.py <output>` tüm üretilen sayfaların canonical, sitemap, logo, yönlendirme ve yerel bağlantılarını denetler. GitHub Pages yayın kaynağı GitHub Actions olarak ayarlanmalıdır.
