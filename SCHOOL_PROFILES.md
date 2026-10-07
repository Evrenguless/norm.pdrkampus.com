# Türkiye okul ve kurum profilleri

Publish PDR Norm and School Profiles iş akışı, mevcut norm haritası ile 81 ildeki kurum profillerini aynı GitHub Pages sürümünde yayınlar.

- /okullar/: şehir dizini
- /okullar/<il>/: ilçe/bölge dizini
- /okullar/<il>/<ilce>/: okul/kurum listesi
- /okullar/<il>/<ilce>/<okul-adi-kurum-kodu>/: kurum profili

Kaynak veri setindeki Bakanlık merkez ve yurt dışı kayıtları şehir kapsamına dahil edilmez. İlçe/bölge başlıkları veri setinden aynen alınır; resmî ilçe sayımı olarak sunulmaz. İstanbul'da daha önce yayınlanan /okul/ bağlantıları çalışmaya devam eder ve yeni profilin canonical adresini taşır. İl ve ilçe bağlantıları korunur.

Python ve Node.js ile scripts/build_school_profiles.py --output /absolute/output/outside/checkout komutu kullanılır. Veri dosyaları ve ana uygulamanın hesaplama kodu değiştirilmez. Üretilmiş kişisel öğrenci senaryoları resmî kaynak verisi olarak gösterilmez. Eksik öğrenci ve personel verisi sıfır sayılmaz.

Her profil güncel logo ve assets/school-profile.css temasını kullanır, Tüm istatistikleri için butonuyla ana norm haritasına yönlendirir. Ana sayfada okul tanıtımı bulunmaz. Şehir/ilçe/okul dizinlerinde Türkçe karakterleri destekleyen arama, assets/school-directory.js ile çalışır.

sitemap.xml bir sitemap index dosyasıdır; ana sayfalar ve 81 il için ayrı sitemap dosyaları sitemaps/ altında üretilir. scripts/test_school_profiles.py <output>, bütün sayfaların metadata, canonical, zorunlu CTA, yerel bağlantılar, kaynak il/ilçe/kurum eşleşmesi, eski İstanbul bağlantıları ve sitemap kapsamını doğrular.
