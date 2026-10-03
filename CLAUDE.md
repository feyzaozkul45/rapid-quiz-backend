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
- İsim: Unicode harf/rakam/boşluk/tire, trim + art arda boşluklar teke, 2–20 karakter; bir kez kaydedilir (2. deneme 409); yalnız completed oturuma
- Skor tablosu: yalnız status=completed ve player_name dolu oturumlar
- Throttle (IP başına): quiz başlatma 10/dk, isim kaydetme 10/dk, cevap 120/dk; gerçek IP için NUM_PROXIES
- Seed: `python manage.py seed_questions` (kategori başına YAML, idempotent)

## Komutlar
- docker compose up -d
- pytest
- ruff check . && ruff format .
- Yerel (Docker yok): .venv\Scripts\python manage.py ... ; DATABASE_URL yoksa SQLite kullanılır
