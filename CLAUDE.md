# rapid-quiz-backend
Proje gereksinimleri: docs/PROJECT.md
Frontend reposu: ../RapidQuizFrontend

## Kurallar
- Django 6 + DRF, tüm uç noktalar /api/v1/ altında
- Doğru cevap hiçbir soru yanıtında istemciye gönderilmez
- Puan ve süre hesabı yalnızca apps/quiz_sessions/services.py içinde
- `apps/sessions` yerine `apps/quiz_sessions` kullanılır (django.contrib.sessions ile çakışmasın)
- Her yeni özellik pytest testiyle gelir

## Karar notları (docs/PROJECT.md'ye ek)
- Süre toleransı: geçen süre <= 6 sn kabul
- İsim: Unicode harf/rakam/boşluk/tire, trim + art arda boşluklar teke, 2–20 karakter; bir kez kaydedilir (2. deneme 409); yalnız completed oturuma, bitişten sonra 30 dk içinde (aksi 410 name_window_closed)
- Skor tablosu: yalnız status=completed ve player_name dolu oturumlar
- Throttle (IP başına): quiz başlatma 10/dk, isim kaydetme 10/dk, cevap 120/dk, soru 240/dk, okuma (categories/result/leaderboard) 300/dk; gerçek IP için NUM_PROXIES; sayaçlar DatabaseCache'te (`createcachetable` şart)
- Throttle (oturum başına, `config/throttles.py`): cevap 40/dk, soru 60/dk; IP başlığından bağımsızdır. Yeni uç nokta eklerken throttle kapsamı da eklenir (health hariç)
- Seed: `python manage.py seed_questions` (kategori başına YAML, idempotent; soru kimliği kategori+metin olduğundan metin değişince eski soru aktif kalır: `--deactivate-missing` (varsayılan kapalı) YAML dışı soruları pasifleştirir, silmez); havuz kategori başına 40 soru, doğru şık konumu dengeli, doğru şık uzunluğu ipucu vermemeli (test_seed bunu denetler)
- Tekrar önleme: istemci `recent_question_ids` (≤40 pozitif tam sayı, eskiden yeniye) gönderir; sunucu önce bunların dışından seçer, yetmezse en eski oynananlardan tamamlar (`services.choose_questions`)
- Seçenek sırası oturum+soru başına deterministik karıştırılır (`services.shuffled_choices`); 300 ms'den hızlı seçenekli cevap puansız (`too_fast`)

- PostgreSQL'e özgü testler tests/test_postgres.py'de (yerelde atlanır, CI'da REQUIRE_POSTGRES=1)
- Ayrıntılı API/kural dokümanı docs/PROJECT.md'dedir ve kodla aynı tutulur

## Komutlar
- docker compose up -d
- pytest
- ruff check . && ruff format .
- Yerel (Docker yok): .venv\Scripts\python manage.py ... ; DATABASE_URL yoksa SQLite kullanılır

## Deployment (ücretsiz)
- Render ücretsiz web servisi (`render.yaml`, Docker) + Neon PostgreSQL + DO statik site (frontend repo)
- Ücretsiz Render'da pre-deploy yok: `scripts/start.sh` her başlangıçta migrate + createcachetable çalıştırır, ardından `purge_sessions` (7 günden eski bitmemiş/isimsiz oturumlar; skor tablosu satırlarına dokunmaz)
- DatabaseCache `MAX_ENTRIES=100000` (varsayılan 300 throttle sayaçlarını siler); değiştirme
- Admin adresi `ADMIN_URL` ortam değişkeninden okunur (varsayılan `admin/`); Render panelinde tahmin edilmesi zor bir değer girilir
- Prod veritabanı komutları yerelden, `DATABASE_URL` ortam değişkeniyle çalıştırılır (adres repoya/komut geçmişine yazılmaz): README
