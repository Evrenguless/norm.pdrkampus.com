# Gizli yapılandırma ve yayın güvenliği

Tarayıcıya gönderilen JavaScript ve HTML herkese açıktır. Supabase publishable/anon anahtarları tarayıcı istemcisinde kullanılabilir; güvenlik RLS, oturum ve fonksiyon izinleriyle sağlanır. service_role, sb_secret, özel imza anahtarları ve sağlayıcı erişim tokenları tarayıcıya eklenmez.

`.env` bir şifreleme yöntemi değildir. Yerel sunucu araçları için dosya yalnızca çalışma makinesinde tutulur; üretimde sunucu/Edge ortam değişkenleri veya GitHub Actions Secrets kullanılır. Bu statik siteler `.env` dosyasını otomatik okumaz. Tarayıcı anahtarını `.env` içine taşımak onu gizlemez ve mevcut istemciyi bozabilir.

Credential Guard, takip edilen dosyalarda bilinen özel anahtar biçimlerini, service_role JWT ve gerçek .env dosyalarını reddeder. Çıktıda yalnızca dosya, satır ve parmak izi bulunur. Testler public anahtarların çalışmasını ve Türkçe risk başlıklarının yanlış alarm üretmemesini de denetler. Bu kontrol bütün olası sır türlerini veya GitHub'daki erişilemeyen eski nesneleri kapsadığı garantisini vermez.

Bir özel anahtar geçmişte paylaşılmışsa önce sağlayıcıdan iptal edilir/yenilenir. Dosyadan silmek veya geçmişi yeniden yazmak tek başına yeterli değildir. Mevcut kullanıcı oturumlarına ve veri erişimine etkisi incelenmeden anahtar değiştirilmez.

Yayın öncesinde güvenlik kontrolü, mevcut koruma/hesaplama testleri ve site haritası kontrolleri çalıştırılır. Canlı adresler korunur; yalnızca kullanılmadığı doğrulanan dosyalar Git geçmişinden geri alınabilecek şekilde silinir.
