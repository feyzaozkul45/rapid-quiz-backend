#!/bin/sh
# Render (ücretsiz plan) başlangıç komutu. Ücretsiz planda pre-deploy komutu yoktur; bu yüzden
# migrate ve createcachetable her başlangıçta çalışır (ikisi de tekrar çalıştırılabilir).
# Servis uykudan her uyandığında da çalıştığı için uyanma süresini birkaç saniye uzatır.
# Başarısız olursa (set -e) gunicorn başlamaz ve Render sürümü yayına almaz.
set -e

sh scripts/predeploy.sh

# Render PORT'u kendisi verir (varsayılan 10000). Ücretsiz plan 512 MB RAM / 0.1 CPU olduğundan
# worker sayısı düşük tutulur; WEB_CONCURRENCY ile değiştirilebilir.
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8080}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout 30 \
  --access-logfile -
