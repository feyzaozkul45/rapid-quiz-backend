# rapid-quiz-backend

Rapid Quiz için Django REST API. Gereksinimler: [docs/PROJECT.md](docs/PROJECT.md).

## Yerel geliştirme

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements/dev.txt
cp .env.example .env
docker compose up -d db        # PostgreSQL (Docker yoksa DATABASE_URL'siz SQLite kullanılır)
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py seed_questions
.venv/Scripts/python manage.py runserver
```

Test: `.venv/Scripts/python -m pytest` — Lint: `ruff check . && ruff format .`
