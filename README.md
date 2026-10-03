# rapid-quiz-backend

Rapid Quiz için Django REST API. Gereksinimler: [docs/PROJECT.md](docs/PROJECT.md).

## Yerel geliştirme

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements/dev.txt
cp .env.example .env
docker compose up -d db        # PostgreSQL (Docker yoksa DATABASE_URL'siz SQLite kullanılır)
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py createcachetable   # throttle sayaçları için DatabaseCache tablosu
.venv/Scripts/python manage.py seed_questions
.venv/Scripts/python manage.py runserver
```

Test: `.venv/Scripts/python -m pytest` — Lint: `ruff check . && ruff format .`

## Deployment (ücretsiz: Render + Neon + DigitalOcean statik site)

| Bileşen | Servis | Not |
| --- | --- | --- |
| API | Render ücretsiz web servisi (Docker, Frankfurt) | `render.yaml`; 15 dk hareketsizlikte uyur, uyanması 30–60 sn sürer |
| Veritabanı | Neon ücretsiz PostgreSQL 18 (Frankfurt) | **pooler'sız doğrudan** bağlantı adresi, `sslmode=require` içerir |
| Frontend | DigitalOcean statik site | `rapid-quiz-frontend` reposundaki `.do/app.yaml` |

Ücretsiz Render planında pre-deploy komutu ve shell yoktur. Bu yüzden `scripts/start.sh` her başlangıçta `migrate` ve `createcachetable` çalıştırıp gunicorn'u başlatır (ikisi de tekrar çalıştırılabilir). Servis uykudan her uyandığında da çalıştığı için uyanma süresi birkaç saniye uzar. Render'ın verdiği `PORT` kullanılır.

### Kurulum

1. Neon'da proje oluştur (bölge Frankfurt, PostgreSQL 18). Bağlantı penceresinde **"Pooled connection" kapalıyken** görünen adresi kopyala (`ep-…` ana bilgisayar adında `-pooler` yok).
2. Render'da **New → Blueprint** ile `rapid-quiz-backend` reposunu seç; `render.yaml` okunur. İstenen değerleri panelden gir:
   - `DATABASE_URL`: Neon adresi
   - `DJANGO_SECRET_KEY`: rastgele 50+ karakter (`python -c "import secrets; print(secrets.token_urlsafe(64))"`)
   - `CORS_ALLOWED_ORIGINS`: frontend'in tam origin'i (`https://….ondigitalocean.app`, sonunda `/` olmadan)
3. İlk deploy bitince `https://<servis>.onrender.com/api/v1/health/` adresinin `{"status": "ok", "database": "up"}` döndüğünü doğrula.
4. Frontend'i DigitalOcean'da oluştururken `VITE_API_BASE_URL` değerini `https://<servis>.onrender.com/api/v1` yap.

Frontend alan adı sonradan belli olacağı için ilk deploy'da `CORS_ALLOWED_ORIGINS`'ı geçici bir değerle girip frontend yayınlanınca güncellemek gerekebilir (Render env değişikliğinde yeniden başlatır).

### Veritabanı işlemleri: kendi bilgisayarından Neon'a bağlanma

Render ücretsiz planında shell olmadığı için seed ve admin kullanıcısı yerelden, Neon'a bağlanarak yapılır. `migrate` ve `createcachetable` servis açılırken zaten çalıştığından yerelde gerek yoktur; ilk kez elle çalıştırmak istersen aynı komutlar geçerlidir.

Bağlantı adresi bir parola içerir: dosyaya yazma, komut geçmişine düşürme, repoya koyma. PowerShell'de `Read-Host` ile gir (yazdığın değer geçmişe kaydedilmez):

```powershell
cd C:\Users\THINKPAD\PycharmProjects\RapidQuizBackend
$env:DATABASE_URL = Read-Host "Neon DATABASE_URL (doğrudan bağlantı, sslmode=require)"
```

Bu oturumdaki komutlar artık Neon'a gider (`DATABASE_URL` yoksa SQLite kullanılır; yanlış veritabanına yazmamak için önce adresi yapıştırdığından emin ol). Sırayla:

```powershell
# 1) Bağlantıyı ve şema durumunu kontrol et (hata yoksa Neon'a erişiliyor)
.venv\Scripts\python manage.py showmigrations quiz

# 2) Tabloları oluştur (servis açılışında da çalışır; elle çalıştırmak zararsızdır)
.venv\Scripts\python manage.py migrate --noinput
.venv\Scripts\python manage.py createcachetable

# 3) Soruları yükle (idempotent: tekrar çalıştırmak çoğaltmaz)
.venv\Scripts\python manage.py seed_questions

# 4) Admin kullanıcısı: kullanıcı adı, e-posta ve parolayı komut sorar
.venv\Scripts\python manage.py createsuperuser
```

İşin bitince oturumdaki adresi sil:

```powershell
Remove-Item Env:DATABASE_URL
```

Doğrulama: `https://<servis>.onrender.com/api/v1/categories/` 5 kategori döndürmeli; `https://<servis>.onrender.com/admin/` adresinden giriş yapılabilmeli.

### NUM_PROXIES doğrulaması (dağıtımdan sonra bir kez)

Throttle sayaçları istemci IP'sine göre tutulur. `NUM_PROXIES`, `X-Forwarded-For` zincirinde sağdan kaç adresin güvenilir proxy olduğunu söyler; `render.yaml`'daki `2` değeri Render'ın zinciri (istemci + önündeki proxy) varsayımına dayanır ve **kanıtlanmamış tahmindir**. Yanlış değer iki şekilde zarar verir: çok küçükse tüm kullanıcılar proxy'nin IP'sini paylaşıp birbirinin limitini yer; çok büyükse istemci kendi `X-Forwarded-For` başlığıyla limiti atlatabilir.

Doğrulamak için (yukarıdaki gibi `DATABASE_URL` tanımlıyken):

```powershell
curl.exe -s https://api.ipify.org                       # kendi genel IP'n
curl.exe -s -X POST https://<servis>.onrender.com/api/v1/quiz-sessions/ -H "Content-Type: application/json" -H "X-Forwarded-For: 9.9.9.9" -d '{\"category\":\"fizik\"}'
.venv\Scripts\python manage.py shell -c "from django.db import connection; c = connection.cursor(); c.execute('select cache_key from rapidquiz_cache'); print([r[0] for r in c.fetchall()])"
```

Çıktıdaki `throttle_quiz_start_<IP>` anahtarındaki IP **kendi genel IP'n** olmalı. `9.9.9.9` görürsen değer çok büyük, başka bir (Render/Cloudflare) IP görürsen çok küçüktür; Render panelinde `NUM_PROXIES`'i ona göre değiştir ve testi tekrarla.
