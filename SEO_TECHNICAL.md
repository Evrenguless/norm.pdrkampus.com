# Teknik SEO — 11 Ekim 2026

Canlı robots.txt ve sitemap.xml 200, olmayan adres 404. 82 sitemap parçasının tamamı doğrudan indirildi: 56.204 URL, yinelenen URL ve sınır aşımı yok. 55.117 kurum profili, 81 il ve 989 kaynak ilçe/bölge altında yayımlanır. Canonical /okullar/ adresleri; eski İstanbul /okul/ adresleri yeni profile canonical verir ve sitemap'e eklenmez. Parametreli harita filtreleri temiz ana sayfa canonical adresini taşır.

Kurum profilleri ve dizinleri gerçek HTML'de içerik ve dahili bağlantı sunar; JavaScript arama için kullanılır. Rastgele dağıtılmış okul örnekleri 200, self-canonical ve statik içerikli bulundu. Googlebot user-agent denemesi gerçek Google taraması veya Search Console URL denetimi değildir.

İl bazında sitemap index korunur. Üretici artık bir il 50.000 URL veya açılmış UTF-8 50 MiB sınırını geçince hata vermek yerine otomatik ek parçalara böler. Bütün sitemap URL'lerinin hostu, parametresizliği, varlığı ve canonical/noindex durumu kontrol edilir; eski ana/il adresleri de test edilir. Sabit üretim tarihini bütün dosyaların güncel değişim tarihiymiş gibi gönderen lastmod alanları kaldırıldı.

Kurum verileri ve özgün norm hesaplama kodu değişmez. Eksik öğrenci/personel verisi sıfır kabul edilmez. 1.942 kişisel senaryo kamu kaynak profillerine taşınmaz. 3.255 kurumda öğrenci, 31.053 kurumda web personel listesi eksiktir; bu eksiklikler mevcut sayfalarda açıkça belirtilir. Kimlik/kaynak/kapsam bilgisi ve hesap açıklaması vardır; içerik kalitesinin Google değerlendirmesi veya tüm kaynakların insan incelemesi tamamlanmış sayılmaz.

Publish PDR Norm and School Profiles iş akışı sitemap sınır testlerini ve 56.188 üretilmiş profil/dizin sayfasının metadata, canonical, kaynak eşleşmesi ve bütün statik bağlantılarını yayın öncesinde sınar. Eski kaynak veri ve hesap kodu hash'i korunur. Başlangıç commit'indeki Google Analytics eklemesinin inceleme kaydı eksikti; mevcut dosyanın exact hash/runtime kaydı tamamlandı. Bu değişiklik index.html'yi veya analitik çalışma kodunu değiştirmez.

Doğrulama:

- python scripts/test_sitemaps.py
- python scripts/test_seo_engine.py
- python scripts/build_school_profiles.py --output /absolute/fresh/output
- python scripts/test_school_profiles.py /absolute/fresh/output

PDF pilot kaynakları ve ana site kataloğu olmadığından ilgili beş pilot test açıkça atlanır.

Search Console erişimi bu çalışmada mevcut değil. Domain mülkünde veya https://norm.pdrkampus.com/ URL-prefix mülkünde https://norm.pdrkampus.com/sitemap.xml gönderilmeli. Bir kurum, il, ilçe ve eski İstanbul alias URL'si denetlenmeli; Google'ın seçtiği canonical ile bildirilen canonical, son tarama ve indeksleme nedeni karşılaştırılmalı. Mevcut kanıt “Google siteyi görmüyor” veya tek bir indeksleme kök nedeni sonucunu desteklemiyor.
