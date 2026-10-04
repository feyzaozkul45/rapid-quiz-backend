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
# collectstatic DB'ye bağlanmaz; build için geçici secret yeterli (prod ayarları anahtar gücünü
# denetler: en az 50 karakter). Bu değer imaja ENV olarak girmez, yalnızca bu komuta verilir.
RUN DJANGO_SECRET_KEY=build-time-only-key-never-used-at-runtime-0123456789abcdef0123456789 \
    python manage.py collectstatic --noinput
USER appuser
EXPOSE 8080
CMD gunicorn config.wsgi:application --bind 0.0.0.0:${PORT} --workers 3 --timeout 30 --access-logfile -
