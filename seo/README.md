# Çevrimdışı SEO denetimi ve pilot

Bu araç bağımsız çalışır; Supabase bağlantısı, ortak uygulama çalışma zamanı veya canlı yayın komutu içermez. `protected-files.json` bütün özgün dosyaların başlangıç SHA-256 kaydını tutar. Kayıt değiştiğinde pilot üretimi durur. Başlangıç kaydı her çalıştırmada yeniden oluşturulmaz.

Python 3.9+ ile proje kökünde:

```sh
python3 scripts/seo_engine.py audit --output /tmp/pdr-audit-yeni
python3 scripts/seo_engine.py validate --sources /mutlak/yol/pilot-sources --output /tmp/pdr-validate-yeni
python3 scripts/seo_engine.py generate --dry-run --sources /mutlak/yol/pilot-sources --output /tmp/pdr-preview-yeni
```

Her komut yeni, proje dışındaki bir çıktı dizini ister. `generate` yalnız `--dry-run` ile önizleme üretir; özgün HTML, sitemap, veri, formül ve auth dosyalarını değiştirmez. Aynı çıktı dizini tekrar kullanılamaz. Kaynak PDF’ler `pilot.json` içindeki kimlikle adlandırılmalı ve kayıtlı SHA-256 ile eşleşmelidir. PDF’ler uygulamaya kopyalanmaz.

Puanlama: kaynak kimliği 20, kapsam 20, kısa cevap 15, kaynak/yöntem/tarih 10, görünür sorular 10, metadata 10, şema eşleşmesi 10, iç keşif 5. 70 puan alt sınırdır; her denetim ayrıca zorunlu geçiş koşuludur. Bu yapısal editoryal kontrol listesi; anlam doğruluğu, Google sıralaması veya indeksleme garantisi değildir. Kaynağa dayanma ve özgünlük insan incelemesi gerektirir. JSON-LD doğrulaması yerel sözdizimi ve belirli görünür alanların eşleşmesiyle sınırlıdır.

Durumlar: `created`, `updated`, `skipped`, `duplicate`, `invalid`, `noindex`, `error`. Mevcut pilot yalnız var olan kaynak sayfalarının önerilen `updated` durumunu kullanır; canlı güncelleme anlamına gelmez. Yeni sayfa yaratma ve yayın işlemi uygulanmamıştır. Legacy sayfalar otomatik noindex yapılmaz. Yinelenen dosyalar ID’leri korunarak raporlanır, kataloglar değiştirilmez. Norm öğrenci sayıları ve bütün hesaplama verileri kalite puanlamasının dışında korunur.

Kaynaklar: https://schema.org/LearningResource ve https://developers.google.com/search/docs/appearance/structured-data/sd-policies

Koruma testleri: `python3 scripts/test_seo_engine.py`. PDF gerektiren pilot testleri için `PDR_SEO_SOURCES=/mutlak/yol/pilot-sources python3 scripts/test_seo_engine.py` kullanılır. PDF bulunmadığında bu testler açıkça atlanır.

## İncelenmiş SEO düzeltmeleri

Başlangıç hash kaydı korunur. Kullanıcının devam/düzeltme talebiyle yapılan sınırlı SEO değişikliklerinin başlangıç ve incelenmiş hash’leri `approved-edits.json` dosyasında ayrıca tutulur. Veri/CSV/JSON, SQL, auth ve hesaplama dosyaları bu izin listesine alınamaz. HTML içindeki JSON-LD dışındaki scriptler başlangıçla aynı kalmalıdır. İncelenmiş sürümün üzerine yapılan yeni değişiklik ayrıca değerlendirilmeden geçmez.

Ana sitenin aynı resmî dosyaya işaret eden katalog kayıtları kaynak verisi değiştirilmeden tek görünür kartta gruplanır. Kayıt kimlikleri ve diğer başlıklar korunur. `catalogue-aliases.json` yalnız denetlenmiş ortak dosya gruplarını tanımlar; yeni ve denetlenmemiş tekrarlar katalog oluşturma/test aşamasında hata verir. Özel üye dosyaları gruplanmaz.

İsteğe bağlı komut adları `seo/package.json` içinde tanımlıdır; `seo/` dizininde `npm run seo:audit -- --output /tmp/yeni-cikti` kullanılabilir. Üretim komutu yine `--dry-run` gerektirir.
