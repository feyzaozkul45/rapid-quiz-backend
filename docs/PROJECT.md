# Rapid Quiz – Proje Dokümanı

Oct 1, 2026 · @feyza nur

## 1. Genel Bakış

Rapid Quiz; kullanıcının bir kategori seçip 20 soruyu, her biri için yalnızca 5 saniye süresi olacak şekilde tek tek cevapladığı bir bilgi yarışması uygulamasıdır. Quiz bitince puan hesaplanır, kullanıcı adını girer ve skor tablosunda ilk 10 gösterilir.

**Kapsam (v1):**

- 5 kategori: Yapay Zeka, Bilgisayar Mühendisliği, Ülkeler, Fizik, Yazılım
- Kategori başına 20 soru, her biri ayrı ekranda, soru başına 5 saniye
- Quiz sonunda puan hesaplama, isim girişi ve top 10 skor tablosu
- Django REST API (backend) ve Vue.js web istemcisi (frontend), ayrı repolarda
- PostgreSQL veritabanı
- Daha sonra eklenecek mobil uygulamaya hazır, istemciden bağımsız bir API

**Kapsam dışı:**

- Kayıt olma, giriş yapma, kullanıcı hesabı ve profil
- Sosyal giriş, çoklu oyuncu, bildirimler
- Mobil uygulamanın kendisi (bu doküman yalnızca API'nin mobil uyumluluğunu kapsar)

## 2. Fonksiyonel Gereksinimler

| Kod | Gereksinim | Açıklama |
| --- | --- | --- |
| FR-01 | Kategori listesi | Ana ekranda 5 kategori gösterilir; liste API'den gelir, kod içine gömülü değildir. |
| FR-02 | Quiz başlatma | Kategori seçildiğinde sunucu bir quiz oturumu açar ve o kategoriden 20 soru atar. |
| FR-03 | Tek tek soru | Her soru ayrı ekranda gösterilir; mevcut soru cevaplanmadan veya süresi dolmadan sonraki görünmez. |
| FR-04 | Geri dönüş yok | Önceki soruya dönülemez, cevap değiştirilemez. |
| FR-05 | 5 saniye süre | Her soru için geri sayım 5 saniyedir; süre dolunca soru cevapsız sayılır ve sonraki soruya geçilir. |
| FR-06 | Cevap formatı | Her soru 4 seçenekli çoktan seçmelidir, tek doğru cevap vardır. |
| FR-07 | Anında geri bildirim | Cevaptan sonra kısa süre (ör. 1 sn) doğru/yanlış gösterilir; bu süre 5 saniyeye dahil değildir. |
| FR-08 | Puan hesaplama | Quiz bitince puan sunucuda hesaplanır ve sonuç ekranında gösterilir (kurallar Bölüm 7). |
| FR-09 | İsim girişi | Sonuç ekranında kullanıcıdan isim istenir; isim kaydedilince skor tabloya girer. Kurallar: Unicode harf (Türkçe dahil), rakam, boşluk ve tire; baştaki/sondaki boşluklar kırpılır, art arda boşluklar teke iner; 2–20 karakter; küfür filtresi v1'de yok. İsim bir kez kaydedilir (ikinci deneme 409) ve yalnızca `completed` oturuma, quiz bitiminden sonraki 30 dakika içinde kaydedilebilir (süre geçerse 410 `name_window_closed`). |
| FR-10 | Skor tablosu | İsim girildikten sonra seçilen kategorinin top 10 skor tablosu gösterilir; kullanıcının kendi skoru vurgulanır. Yalnızca `status=completed` ve `player_name` dolu oturumlar listelenir. |
| FR-11 | Tekrar oyna | Sonuç ekranından aynı kategoriyi tekrar başlatma veya ana ekrana dönme seçeneği bulunur. |
| FR-12 | Soru yönetimi | Sorular Django Admin üzerinden eklenir/düzenlenir (admin, soru başına tam 4 seçenek ve tam 1 doğru cevabı zorunlu kılar). İlk veri seti, kategori başına bir YAML dosyasından `python manage.py seed_questions` komutuyla yüklenir; komut idempotenttir ve her soruda 4 seçenek + 1 doğru cevap, kategori başına en az 20 soru olduğunu doğrular. |

Kategori başına havuzda 20'den fazla soru tutulursa her quiz'de rastgele 20 soru seçilir; havuz tam 20 ise sadece sıra karıştırılır.

## 3. Fonksiyonel Olmayan Gereksinimler

En kritik nokta hile önlemedir: doğru cevaplar ve süre kontrolü istemciye bırakılmaz.

- **Güvenlik / hile önleme:** Soru yanıtlarında doğru cevap istemciye gönderilmez. Puan ve süre sunucuda doğrulanır. Bir sonraki soru ancak mevcut soru cevaplandığında veya süresi dolduğunda döner.
- **Rate limiting:** DRF throttling, IP başına: quiz başlatma 10/dk, isim kaydetme 10/dk, cevap gönderme 120/dk. Okul ve mobil operatör NAT'ı arkasındaki kullanıcılar aynı IP'yi paylaşabileceği için sınırlar gevşek tutulur. Sayaçlar tüm gunicorn worker'ları arasında paylaşılsın diye `DatabaseCache`'te tutulur (Redis yok); tablo `migrate` ile oluşmadığından `python manage.py createcachetable` ayrıca çalıştırılır. Yük dengeleyici arkasında gerçek istemci IP'si için `NUM_PROXIES` ayarı kullanılır (production varsayılanı 1).
- **Performans:** Soru uç noktası sunucuda 200 ms altında yanıt vermelidir; skor tablosu sorgusu indeksle desteklenir.
- **Mobil uyumluluk:** API durumsuz (stateless) JSON REST'tir, cookie/session'a bağlı değildir; quiz oturumu UUID token ile taşınır.
- **Duyarlı arayüz:** Web arayüzü 360 px genişliğe kadar mobil tarayıcıda kullanılabilir.
- **Çoklu dil hazırlığı:** Arayüz metinleri v1'de Türkçedir; metinler i18n dosyalarında tutulur.
- **Gözlemlenebilirlik:** Backend hataları loglanır; health check uç noktası bulunur.
- **İçerik kontrolü:** Skor tablosuna girilen isimler uzunluk ve karakter kontrolünden geçer; uygunsuz kelime filtresi opsiyoneldir.

## 4. Sistem Mimarisi

Backend ve frontend ayrı repolardadır; web ve mobil istemciler veritabanına doğrudan değil, yalnızca Django REST API üzerinden erişir.

&#91;embedded content: sistem mimarisi · 2 istemci, 1 API, 1 veritabanı\]

İş kuralları (puan, süre, soru sırası) tek yerde, backend'de durur; bu sayede mobil uygulama eklendiğinde aynı kurallar otomatik geçerli olur ve hile yapılamaz.

## 5. Veritabanı Tasarımı (PostgreSQL)

Beş tablo yeterlidir; kullanıcı tablosu yoktur, oyuncu kimliği quiz oturumunun UUID'sidir.

**categories**

| Alan | Tip | Not |
| --- | --- | --- |
| id | serial PK |  |
| name | varchar(100) | ör. "Yapay Zeka" |
| slug | varchar(100), unique | ör. `yapay-zeka` |
| description | text, null |  |
| icon | varchar(50), null | arayüz ikonu adı |
| order | smallint | listeleme sırası |
| is\_active | boolean |  |

**questions**

| Alan | Tip | Not |
| --- | --- | --- |
| id | serial PK |  |
| category\_id | FK → categories | indeksli |
| text | text | soru metni |
| difficulty | smallint, null | 1–3, opsiyonel; CHECK kısıtı var |
| is\_active | boolean |  |
| created\_at | timestamptz |  |

**choices**

| Alan | Tip | Not |
| --- | --- | --- |
| id | serial PK |  |
| question\_id | FK → questions |  |
| text | varchar(255) |  |
| is\_correct | boolean | soru başına en fazla 1 doğru: `question_id` üzerinde kısmi unique indeks (`WHERE is_correct`); "tam 4 seçenek ve en az 1 doğru" admin formset'i ve seed komutuyla doğrulanır |
| order | smallint |  |

**quiz\_sessions**

| Alan | Tip | Not |
| --- | --- | --- |
| id | uuid PK | istemciye verilen oturum anahtarı |
| category\_id | FK → categories |  |
| status | varchar(20) | `in_progress`, `completed`, `expired` (`expired` tembel işaretlenir: ilgili oturuma sonraki istekte) |
| current\_index | smallint | 0–19, sıradaki soru |
| score | integer | bitişte hesaplanır |
| correct\_count | smallint |  |
| player\_name | varchar(20), null | isim girilince dolar |
| client\_type | varchar(10) | `web`, `ios`, `android` |
| started\_at / finished\_at | timestamptz |  |
| last\_activity\_at | timestamptz | son `current-question`/`answers` isteği; 10 dakika hareketsizlik kontrolü için |

**session\_answers**

| Alan | Tip | Not |
| --- | --- | --- |
| id | serial PK |  |
| session\_id | FK → quiz\_sessions |  |
| question\_id | FK → questions |  |
| position | smallint | 0–19, soru sırası |
| served\_at | timestamptz | sorunun istemciye gönderildiği an |
| answered\_at | timestamptz, null |  |
| selected\_choice\_id | FK → choices, null | null = süre doldu |
| is\_correct | boolean |  |
| points | integer |  |

İndeksler: `leaderboard_idx` = `(category_id, score DESC, finished_at)` skor tablosu için kısmi indeks (`WHERE player_name IS NOT NULL`); `(session_id, position)` unique. Her iki kısıtın PostgreSQL'de gerçekten kısmi/unique oluştuğu CI'daki PostgreSQL testleriyle doğrulanır.

## 6. API Tasarımı

Tüm uç noktalar `/api/v1/` altında, JSON tabanlı ve kimlik doğrulamasızdır; web ve mobil istemci aynı API'yi kullanır.

| Metot | Uç nokta | Amaç |
| --- | --- | --- |
| GET | `/api/v1/categories/` | Aktif kategorileri listeler (`id, name, slug, description, icon, order`) |
| POST | `/api/v1/quiz-sessions/` | Seçilen kategori için yeni quiz oturumu açar |
| GET | `/api/v1/quiz-sessions/{id}/current-question/` | Sıradaki soruyu verir (doğru cevap olmadan) |
| POST | `/api/v1/quiz-sessions/{id}/answers/` | Mevcut soruya cevap gönderir |
| GET | `/api/v1/quiz-sessions/{id}/result/` | Biten quiz'in puan özetini verir |
| PATCH | `/api/v1/quiz-sessions/{id}/player-name/` | İsmi kaydeder, skoru tabloya alır |
| GET | `/api/v1/leaderboard/?category=yapay-zeka&limit=10` | Kategori top 10 listesi |
| GET | `/api/v1/health/` | Sağlık kontrolü |

**Quiz başlatma** (`client_type` isteğe bağlıdır: yoksa `X-Client-Type` başlığı, o da yoksa `web`; geçersiz kategori 400 `validation_error`, 20'den az aktif soru 409 `category_unavailable`)

```json
POST /api/v1/quiz-sessions/
{ "category": "yapay-zeka", "client_type": "web" }

201 Created
{ "session_id": "8f1c…", "category": "yapay-zeka", "total_questions": 20, "time_limit_seconds": 5 }
```

**Sıradaki soru**

```json
GET /api/v1/quiz-sessions/8f1c…/current-question/

200 OK
{ "position": 3, "total": 20, "question_id": 142,
  "text": "Transformer mimarisini tanıtan makale hangisidir?",
  "choices": [ {"id": 561, "text": "…"}, {"id": 562, "text": "…"}, {"id": 563, "text": "…"}, {"id": 564, "text": "…"} ],
  "time_limit_seconds": 5, "served_at": "2026-10-01T10:15:03.120Z", "remaining_seconds": 5.0 }
```

`remaining_seconds` (0–5) yalnızca bilgilendirme içindir: sayfa yenilenince geri sayım kalan süreyle devam eder; aynı soru tekrar istenirse `served_at` değişmez. Doğru cevap hiçbir alanda yer almaz.

**Cevap gönderme** (süre dolduysa `choice_id: null`)

```json
POST /api/v1/quiz-sessions/8f1c…/answers/
{ "question_id": 142, "choice_id": 562 }

200 OK
{ "is_correct": true, "correct_choice_id": 562, "points": 100,
  "is_last": false, "score_so_far": 300 }
```

**Sonuç ve isim kaydı**

```json
GET /api/v1/quiz-sessions/8f1c…/result/
200 OK
{ "session_id": "8f1c…", "category": "yapay-zeka", "status": "completed", "score": 1300,
  "correct_count": 13, "total_questions": 20, "max_score": 2000, "player_name": null,
  "finished_at": "…" }

PATCH /api/v1/quiz-sessions/8f1c…/player-name/
{ "player_name": "Ayşe" }

200 OK
{ "session_id": "8f1c…", "category": "yapay-zeka", "player_name": "Ayşe", "score": 1300, "correct_count": 13 }
```

**Skor tablosu**

```json
GET /api/v1/leaderboard/?category=yapay-zeka&limit=10

200 OK
{ "category": "yapay-zeka", "entries": [ {"rank": 1, "player_name": "Ayşe", "score": 1900, "correct_count": 19, "finished_at": "…", "is_me": false} ] }
```

`limit` 1–50 arası, varsayılan 10. İsteğe bağlı `session_id` verilirse o oturumun satırında `is_me: true` olur ve yanıta `me` alanı eklenir (oturum tabloda yer alıyorsa kendi sırasıyla, top listenin dışında olsa bile; aksi halde `null`). `session_id` verilmezse yanıtta `me` bulunmaz. Bilinmeyen/pasif kategori 404 `category_not_found`.

Hata formatı sabittir: `{ "error": { "code": "session_expired", "message": "…" } }` (doğrulama hatalarında ek olarak `details` bulunur). Kodlar:

| Kod | HTTP | Anlamı |
| --- | --- | --- |
| `validation_error` | 400 | Gövde/sorgu parametresi geçersiz |
| `invalid_json` | 400 | Gövde okunamadı |
| `invalid_choice` | 400 | Seçenek, bu soruya ait değil |
| `name_invalid` | 400 | İsim kurallarına uymuyor |
| `not_found`, `session_not_found`, `category_not_found` | 404 | Kaynak yok |
| `method_not_allowed` | 405 | Metot desteklenmiyor |
| `question_mismatch` | 409 | Cevap sıradaki soruyla eşleşmiyor (aynı soruya ikinci cevap dahil) |
| `question_not_served` | 409 | Soru henüz `current-question` ile verilmedi |
| `session_completed` | 409 | Quiz zaten tamamlandı |
| `session_not_completed` | 409 | Sonuç/isim için quiz bitmeli |
| `name_already_set` | 409 | İsim zaten kaydedildi |
| `category_unavailable` | 409 | Kategoride yeterli aktif soru yok |
| `session_expired` | 410 | Oturum 10 dakika hareketsiz kaldı |
| `name_window_closed` | 410 | Quiz bitiminden sonra 30 dakika geçti |
| `rate_limited` | 429 | Throttle sınırı aşıldı |
| `server_error` | 500 | Beklenmeyen hata (loglanır) |

Web istemcisi `X-Client-Type` ve `X-Client-Version` başlıklarını gönderebilir; CORS bunlara izin verir. Yanıtlar gzip ile sıkıştırılır. API dokümantasyonu drf-spectacular ile `/api/docs/` adresinde OpenAPI olarak yayınlanır; mobil ekip bu şemadan istemci kodu üretebilir.

## 7. Puanlama ve Zamanlayıcı Kuralları

Her doğru cevap sabit 100 puandır; yanlış veya süresi dolan cevap 0 puandır. Cevabın ne kadar hızlı verildiği puanı etkilemez. Bir quiz'de en yüksek puan 20 × 100 = 2000'dir.

```latex
\text{puan} = 100 \times \text{doğru cevap sayısı}
```

Bir cevabın puan alması için hem doğru olması hem de süre içinde gelmesi gerekir. Süre, sunucunun soruyu gönderdiği an ile cevabı aldığı an arasındaki farktır.

**Sunucu tarafı kurallar:**

1. `current-question` çağrıldığında `served_at` yazılır; aynı soru tekrar istenirse yeni süre başlamaz, aynı `served_at` korunur.
2. Cevap geldiğinde geçen süre hesaplanır. Ağ gecikmesi için **1 saniye tolerans** tanınır: 6 saniyeyi aşan cevaplar süre dolmuş sayılır. Süre içinde gelen doğru cevabın 1. saniyede mi 5. saniyede mi verildiği fark etmez.
3. Cevabın `question_id` değeri oturumdaki sıradaki soruyla eşleşmezse 409 döner; aynı soruya ikinci cevap kabul edilmez.
4. 20. cevaptan sonra oturum `completed` olur, puan ve doğru sayısı yazılır.
5. İstemci cevap göndermeden kaybolursa, süresi geçmiş (6 sn) soru bir sonraki `current-question` isteğinde otomatik olarak cevapsız işaretlenir ve sıradaki soru o an sunulur; geçen soru son soruysa oturum tamamlanır. 10 dakika boyunca hareketsiz kalan `in_progress` oturumlar `expired` olur (410 `session_expired`) ve skor tablosuna giremez; `expired` durumu ilgili oturuma sonraki istekte yazılır.
6. Skor tablosunda eşitlik, bitiş zamanıyla bozulur (bu puana daha önce ulaşan üstte yer alır; o da eşitse `id`).
7. İsim yalnızca `completed` oturuma, bitişten sonraki 30 dakika içinde ve bir kez kaydedilir. Süre geçerse 410 `name_window_closed`, ikinci deneme 409 `name_already_set`.
8. Aynı oturuma eş zamanlı gelen istekler `select_for_update` ile sıraya konur: aynı soruya gelen iki cevaptan yalnızca biri sayılır, diğeri 409 `question_mismatch` alır.

**İstemci tarafı:** Geri sayım yalnızca görseldir. Süre dolunca istemci `choice_id: null` gönderir ve sonraki soruyu ister. Cevap butonları ilk tıklamada kilitlenir; sayfa yenilenirse aynı soru kalan süresiyle geri gelir.

## 8. Backend Reposu: `rapid-quiz-backend`

| Katman | Teknoloji |
| --- | --- |
| Dil / framework | Python 3.14, Django 6.x |
| API | Django REST Framework, drf-spectacular (OpenAPI) |
| Veritabanı | PostgreSQL 18, psycopg 3 (yerelde `DATABASE_URL` yoksa SQLite'a düşer) |
| CORS | django-cors-headers (web ve geliştirme ortamı originleri) |
| Ayarlar | django-environ, `.env` dosyası; seed için PyYAML |
| Test | pytest, pytest-django, factory\_boy |
| Kod kalitesi | ruff (lint + format), pre-commit; GitHub Actions: PostgreSQL 18 servisiyle Python 3.13 ve 3.14 matrisi |
| Sunucu | gunicorn, Docker (python:3.14-slim), WhiteNoise (admin statik dosyaları) |

```
rapid-quiz-backend/
├── config/
│   ├── settings/          # base.py, dev.py, prod.py
│   ├── api_errors.py      # sabit hata formatı + exception handler
│   ├── urls.py
│   ├── views.py           # health
│   └── wsgi.py
├── apps/
│   ├── quiz/              # Category, Question, Choice modelleri + admin + kategori listesi
│   │   ├── fixtures/      # kategori başına bir YAML (5 kategori, 101 soru)
│   │   ├── management/commands/seed_questions.py
│   │   └── seeding.py     # doğrulama + idempotent yükleme
│   ├── quiz_sessions/     # QuizSession, SessionAnswer (django.contrib.sessions ile çakışmasın diye bu ad)
│   │   ├── services.py    # puan/süre/isim kuralları: saf fonksiyonlar
│   │   └── workflow.py    # oturum akışı (veritabanı, select_for_update)
│   └── leaderboard/       # skor tablosu sorguları ve view'lar
├── tests/                 # pytest (+ test_postgres.py: kısmi indeks, eş zamanlılık)
├── requirements/          # base.txt, dev.txt
├── .github/workflows/ci.yml
├── scripts/predeploy.sh   # PRE_DEPLOY: migrate + createcachetable
├── .pre-commit-config.yaml
├── .do/
│   └── app.yaml           # DigitalOcean App Platform tanımı
├── Dockerfile             # production imajı (multi-stage)
├── .dockerignore
├── docker-compose.yml     # yerel geliştirme: postgres:18 + api
├── .env.example
├── README.md
└── CLAUDE.md
```

Puanlama ve süre mantığı view'larda değil, `apps/quiz_sessions/services.py` içinde saf fonksiyonlar olarak tutulur; böylece birim testleri kolaylaşır. Veritabanı gerektiren akış `workflow.py`'dedir ve kuralları `services.py`'den çağırır.

## 9. Frontend Reposu: `rapid-quiz-frontend`

| Katman | Teknoloji |
| --- | --- |
| Framework | Vue 3 (Composition API), TypeScript, Vite |
| Router / state | Vue Router, Pinia |
| HTTP | Axios, tek bir `api/` istemci katmanı |
| Stil | Tailwind CSS |
| Çoklu dil | vue-i18n (v1 yalnızca `tr`) |
| Test | Vitest + Vue Test Utils, Playwright (uçtan uca) |
| Kod kalitesi | ESLint, Prettier |

```
rapid-quiz-frontend/
├── src/
│   ├── api/            # axios istemcisi ve endpoint fonksiyonları
│   ├── stores/         # quizStore (oturum, mevcut soru, puan)
│   ├── views/          # Home, Quiz, Result, Leaderboard
│   ├── components/     # CategoryCard, QuestionCard, CountdownTimer, ChoiceButton, NameForm, LeaderboardTable
│   ├── composables/    # useCountdown
│   ├── locales/        # tr.json
│   └── router/
├── .do/app.yaml        # DigitalOcean static site tanımı
├── .env.example        # VITE_API_BASE_URL
└── CLAUDE.md
```

**Ekranlar ve kullanıcı akışı:**

1. **Ana ekran (`/`)**: 5 kategori kartı. Kart seçilince quiz oturumu açılır.
2. **Quiz ekranı (`/quiz/:sessionId`)**: Üstte "Soru 3/20" ve 5 saniyelik dairesel geri sayım, ortada soru, altında 4 seçenek. Cevap veya süre dolumu sonrası \~1 sn doğru/yanlış renklendirmesi, ardından sonraki soru. Bu adım 20 kez tekrarlanır.
3. **Sonuç ekranı (`/result/:sessionId`)**: Toplam puan, doğru sayısı ve isim formu.
4. **Skor tablosu (`/leaderboard/:category`)**: İsim kaydedildikten sonra açılır; top 10 listesi, kullanıcının satırı vurgulu. "Tekrar oyna" ve "Ana sayfa" butonları.

Quiz sırasında tarayıcı geri tuşu ana ekrana onay penceresiyle yönlendirir; önceki soruya dönüş yoktur.

## 10. Mobil Uygulama Entegrasyonu

Mobil uygulama backend'de hiçbir değişiklik gerektirmeden aynı `/api/v1/` uç noktalarını kullanacak şekilde tasarlanır.

- **Durumsuz API:** Oturum bilgisi cookie'de değil, `session_id` (UUID) olarak istemcide tutulur. Mobil uygulama bunu uygulama kapanıp açıldığında devam etmek için saklayabilir.
- **Versiyonlama:** Kırıcı değişiklikler `/api/v2/` altında yapılır; mağazadaki eski uygulama sürümleri v1 ile çalışmaya devam eder.
- **İstemci tanıma:** İsteklerde `X-Client-Type` (`web`/`ios`/`android`) ve `X-Client-Version` başlıkları gönderilir; istatistik ve zorunlu güncelleme kontrolü için kullanılır.
- **CORS sadece web için:** Native mobil uygulamalar CORS'a takılmaz; CORS listesi yalnızca web originlerini içerir.
- **Zaman:** Tüm zamanlar UTC ve ISO 8601 döner; süre hesabı sunucuda yapıldığı için cihaz saatinin yanlış olması sonucu etkilemez.
- **Sabit hata formatı:** Mobil istemci hata mesajlarını `error.code`'a göre kendi diline çevirebilir.
- **Payload boyutu:** Yanıtlar küçük tutulur ve gzip ile sıkıştırılır; zayıf mobil bağlantılarda 5 saniyelik sürenin ağda harcanmaması için sonraki soru, cevap yanıtıyla birlikte döndürülebilir (ilerideki optimizasyon).

## 11. Geliştirme Ortamı, Test ve Deployment

**Yerel geliştirme:** Backend `docker compose up` ile PostgreSQL ve API'yi başlatır, `python manage.py migrate`, `python manage.py createcachetable` ve `python manage.py seed_questions` ile veritabanı ve seed verisi hazırlanır. Frontend `npm run dev` ile çalışır ve `VITE_API_BASE_URL` ile backend'e bağlanır.

**Test hedefleri:**

- Puanlama servisi: sınır değerler (0 sn, 5 sn, 6 sn tolerans, 6+ sn) için birim testleri
- API: sıra dışı cevap, çift cevap, süresi dolmuş oturum, doğru cevabın soru yanıtında bulunmaması
- Frontend: geri sayım bileşeni ve quiz store için birim testleri; tam bir quiz turu için Playwright testi
- PostgreSQL'e özgü testler (`tests/test_postgres.py`): kısmi indeksin gerçekten kısmi olduğu ve sorgu planında kullanıldığı, tek-doğru-seçenek unique indeksi ve aynı soruya eş zamanlı cevapların yalnızca birinin sayılması. Yerelde SQLite ile atlanır; CI'da `REQUIRE_POSTGRES=1` olduğundan atlanamaz.
- Backend kod kapsamı hedefi en az %80 (CI'da `--cov-fail-under=80`)

**CI (GitHub Actions):** Her iki repoda da her PR'da lint + test çalışır. Backend: `postgres:18` servis konteyneriyle Python 3.13 ve 3.14 matrisinde `ruff check`, `ruff format --check`, `makemigrations --check` ve `pytest`; ayrıca production Dockerfile'ının (`python:3.14-slim`) derlendiği bir iş: imaj root olmayan kullanıcıyla çalışmalı, `scripts/predeploy.sh` PostgreSQL servisine karşı geçmeli, imaj `PORT=8080` ile ayağa kalkıp `/api/v1/health/` için 200 dönmeli ve throttle'lı bir uç nokta `DatabaseCache` tablosuna erişebilmelidir (duman testi).

### DigitalOcean Deployment

Her iki repo da DigitalOcean App Platform'a ayrı birer app olarak deploy edilir: backend Dockerfile'dan derlenen bir web servisi, frontend ise statik sitedir. Veritabanı DigitalOcean Managed PostgreSQL 18 kümesidir; App Platform PostgreSQL 14–18 arasını destekler ([DO PostgreSQL limitleri](https://docs.digitalocean.com/products/databases/postgresql/details/limits/)).

| Bileşen | App Platform türü | Kaynak | Örnek alan adı |
| --- | --- | --- | --- |
| `rapid-quiz-api` | Service (Dockerfile) | `rapid-quiz-backend` reposu, `main` dalı | `api.rapidquiz.example.com` |
| `migrate` | Job (PRE\_DEPLOY) | Aynı Dockerfile | — |
| `rapid-quiz-web` | Static Site | `rapid-quiz-frontend` reposu, `main` dalı | `rapidquiz.example.com` |
| `rapid-quiz-db` | Managed PostgreSQL 18 | DO Managed Databases | Yalnızca VPC içi erişim |

Bölge olarak Türkiye'ye en yakın veri merkezi olan Frankfurt (`fra`) önerilir; tüm bileşenler aynı bölgede olmalıdır. Frontend ve API farklı alt alan adlarında olduğu için backend'de CORS ayarı zorunludur.

### Backend Dockerfile

Multi-stage build ile imaj küçük tutulur, uygulama root olmayan kullanıcıyla çalışır. `psycopg[binary]` kullanıldığı için imaja libpq kurmaya gerek yoktur. App Platform'un isteği ilettiği port `PORT` değişkeninden okunur.

```dockerfile
# ---- build aşaması ----
FROM python:3.14-slim AS builder
ENV PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements/ requirements/
RUN pip wheel --wheel-dir /wheels -r requirements/base.txt

# ---- çalışma aşaması ----
FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    PORT=8080
WORKDIR /app
RUN useradd --create-home appuser
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY . .
# collectstatic DB'ye bağlanmaz; build için geçici secret yeterli
RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput
USER appuser
EXPOSE 8080
CMD gunicorn config.wsgi:application --bind 0.0.0.0:${PORT} --workers 3 --timeout 30 --access-logfile -
```

`.dockerignore` en az şunları içerir: `.git`, `.env`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `staticfiles/`, `docker-compose.yml`.

### Backend App Spec (`.do/app.yaml`)

Migration'lar ve throttle için `createcachetable` her deploy'dan önce PRE\_DEPLOY job'ı ile çalışır; başarısız olursa yeni sürüm yayına alınmaz. İki komut `scripts/predeploy.sh` betiğinde (`set -e`; `migrate --noinput`, `createcachetable`) toplanmıştır, böylece `run_command`'da kabuk operatörüne (`&&`) bağımlılık kalmaz. `createcachetable` `migrate` ile çalışmaz, ayrıca verilmelidir; komut idempotenttir. Betik `sh` ile çağrılır, çalıştırma izni gerekmez; `.gitattributes` `*.sh` dosyalarını LF'de tutar. Üst düzeydeki `envs` hem servise hem job'a uygulanır.

```yaml
name: rapid-quiz-api
region: fra
envs:
  - key: DATABASE_URL
    scope: RUN_TIME
    value: ${rapid-quiz-db.DATABASE_URL}
  - key: DJANGO_SECRET_KEY
    scope: RUN_TIME
    type: SECRET
    value: "<panelden girilir>"
  - key: DJANGO_ALLOWED_HOSTS
    scope: RUN_TIME
    value: api.rapidquiz.example.com,${APP_DOMAIN}
  - key: CORS_ALLOWED_ORIGINS
    scope: RUN_TIME
    value: https://rapidquiz.example.com
  - key: CSRF_TRUSTED_ORIGINS
    scope: RUN_TIME
    value: https://api.rapidquiz.example.com
services:
  - name: api
    github:
      repo: <github-kullanıcı>/rapid-quiz-backend
      branch: main
      deploy_on_push: true
    dockerfile_path: Dockerfile
    http_port: 8080
    instance_size_slug: apps-s-1vcpu-1gb
    instance_count: 1
    health_check:
      http_path: /api/v1/health/
jobs:
  - name: migrate
    kind: PRE_DEPLOY
    github:
      repo: <github-kullanıcı>/rapid-quiz-backend
      branch: main
    dockerfile_path: Dockerfile
    run_command: sh scripts/predeploy.sh
    instance_size_slug: apps-s-1vcpu-0.5gb
databases:
  - name: rapid-quiz-db
    engine: PG
    version: "18"
    production: true
    cluster_name: rapid-quiz-db
```

### Frontend App Spec (`.do/app.yaml`)

Vue Router history modunda çalıştığı için `catchall_document: index.html` zorunludur; aksi halde `/quiz/...` gibi adresler sayfa yenilendiğinde 404 verir. API adresi derleme anında pakete gömülür.

```yaml
name: rapid-quiz-web
region: fra
static_sites:
  - name: web
    github:
      repo: <github-kullanıcı>/rapid-quiz-frontend
      branch: main
      deploy_on_push: true
    build_command: npm ci && npm run build
    output_dir: dist
    index_document: index.html
    catchall_document: index.html
    envs:
      - key: VITE_API_BASE_URL
        scope: BUILD_TIME
        value: https://api.rapidquiz.example.com/api/v1
```

### Ortam Değişkenleri

| Değişken | Repo | Production değeri | Not |
| --- | --- | --- | --- |
| `DATABASE_URL` | backend | `${rapid-quiz-db.DATABASE_URL}` | DO otomatik doldurur, `sslmode=require` içerir |
| `DJANGO_SECRET_KEY` | backend | Rastgele 50+ karakter | SECRET tipinde, repoya girmez |
| `DJANGO_SETTINGS_MODULE` | backend | `config.settings.prod` | Dockerfile'da tanımlı |
| `DJANGO_ALLOWED_HOSTS` | backend | API alan adı + `${APP_DOMAIN}` |  |
| `CORS_ALLOWED_ORIGINS` | backend | Frontend alan adı | Mobil uygulama için gerekmez |
| `CSRF_TRUSTED_ORIGINS` | backend | API alan adı | Django Admin girişi için |
| `NUM_PROXIES` | backend | `1` (varsayılan) | Gerçek istemci IP'si için X-Forwarded-For hop sayısı; deployment'ta doğrulanır |
| `VITE_API_BASE_URL` | frontend | `https://api.…/api/v1` | BUILD\_TIME |

### Production Ayarları Kontrol Listesi (`config/settings/prod.py`)

- [ ] `DEBUG = False`, `SECRET_KEY` ve `ALLOWED_HOSTS` ortam değişkeninden okunur
- [ ] `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` (App Platform TLS'i yük dengeleyicide sonlandırır)
- [ ] `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` ve HSTS açık
- [ ] Veritabanı `DATABASE_URL`'den okunur; `CONN_MAX_AGE = 60` ve `CONN_HEALTH_CHECKS = True`
- [ ] WhiteNoise middleware'i eklenir, `STATIC_ROOT = BASE_DIR / "staticfiles"`
- [ ] Loglar stdout'a yazılır (App Platform runtime loglarında görünür)
- [ ] `/api/v1/health/` veritabanına basit bir sorgu atar ve 200 döner
- [ ] `SECURE_SSL_REDIRECT` bilerek kapalıdır: App Platform health check'i konteynere düz HTTP ile gelir ve yönlendirme bunu bozar; HTTP→HTTPS yönlendirmesini App Platform yapar (`check --deploy`'daki W008 ve HSTS preload uyarısı W021 kabul edilmiştir)
- [ ] `createcachetable` çalışmış olmalı (throttle sayaçları `DatabaseCache`'te)

### İlk Kurulum Adımları

1. Her iki repoyu GitHub'a it ve DigitalOcean hesabına GitHub erişimi ver.
2. `doctl apps create --spec .do/app.yaml` ile backend app'ini oluştur; `DJANGO_SECRET_KEY` değerini panelden gir.
3. İlk deploy bitince App Platform konsolunda `python manage.py seed_questions` ile soruları yükle ve `python manage.py createsuperuser` ile admin kullanıcısı oluştur.
4. Frontend app'ini aynı komutla oluştur.
5. Her iki app'e özel alan adlarını ekle; DNS kayıtları doğrulanınca SSL sertifikası otomatik çıkar.
6. Veritabanı kümesinde "Trusted Sources" listesine yalnızca backend app'ini ekle.

`deploy_on_push` açık olduğu için `main`'e giren her commit yayına çıkar. Bu yüzden `main` dalı korumalı olmalı ve GitHub Actions testleri geçmeden merge edilememelidir.

### Yerel Geliştirme (`docker-compose.yml`)

```yaml
services:
  db:
    image: postgres:18
    environment:
      POSTGRES_DB: rapidquiz
      POSTGRES_USER: rapidquiz
      POSTGRES_PASSWORD: rapidquiz
    ports: ["5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql   # postgres:18 imajında veri yolu bu üst dizindir
  api:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.dev
      DATABASE_URL: postgres://rapidquiz:rapidquiz@db:5432/rapidquiz
    ports: ["8000:8000"]
    volumes: [".:/app"]
    depends_on: [db]
volumes:
  pgdata:
```

## 12. Claude Code ile Geliştirme Planı

Bu dokümanı her iki reponun köküne `docs/PROJECT.md` olarak koyun ve Claude Code'a fazlar halinde, her faz sonunda testler geçecek şekilde iş verin.

**Her repoya bir `CLAUDE.md`** (Claude Code her oturumda okur). Backend için örnek:

```markdown
# rapid-quiz-backend
Proje gereksinimleri: docs/PROJECT.md

## Kurallar
- Django 6 + DRF, tüm uç noktalar /api/v1/ altında
- Doğru cevap hiçbir soru yanıtında istemciye gönderilmez
- Puan ve süre hesabı yalnızca apps/quiz_sessions/services.py içinde
- Her yeni özellik pytest testiyle gelir

## Komutlar
- docker compose up -d
- pytest
- ruff check . && ruff format .
```

**Fazlar ve örnek promptlar:**

1. **Backend iskeleti:** "docs/PROJECT.md'yi oku. Django projesini Bölüm 8'deki yapıyla, PostgreSQL ve docker-compose ile kur. Health uç noktası ve bir test ekle."
2. **Modeller ve seed:** "Bölüm 5'teki modelleri, migration'ları ve Django Admin'i oluştur. 5 kategori × 20 soruluk Türkçe YAML seti ve `seed_questions` komutunu hazırla."
3. **Quiz akışı API'si:** "Bölüm 6 ve 7'ye göre quiz-sessions uç noktalarını ve puanlama servisini yaz. Sınır durumları için testler ekle."
4. **Skor tablosu ve sıkılaştırma:** "Leaderboard uç noktasını, throttling'i, CORS'u ve drf-spectacular dokümantasyonunu ekle."
5. **Frontend iskeleti:** "Vue 3 + Vite + TS projesini Bölüm 9'daki yapıyla kur; API istemcisini /api/docs şemasına göre yaz."
6. **Ekranlar:** "Ana ekran, quiz ekranı (5 sn geri sayım), sonuç ve skor tablosu ekranlarını yap; mobil tarayıcıda da çalışsın."
7. **Test ve CI:** "Playwright ile tam bir quiz turunu test et; iki repo için GitHub Actions ekle."
8. **Deployment:** "Bölüm 11'deki DigitalOcean bölümüne göre backend için Dockerfile, .dockerignore, prod ayarları ve .do/app.yaml; frontend için .do/app.yaml oluştur. Imajı yerelde derleyip gunicorn ile çalıştığını doğrula, doctl apps spec validate ile spec'leri kontrol et ve kurulum adımlarını README'ye yaz."

Büyük fazlarda Claude Code'dan önce plan isteyin (plan mode), planı onaylayın, sonra uygulatın.
