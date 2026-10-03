#!/bin/sh
# Veritabanı hazırlığı: migrate + createcachetable. Render'da scripts/start.sh her başlangıçta
# çağırır (ücretsiz planda pre-deploy komutu yok). Hata verirse (set -e) sunucu başlamaz.
# createcachetable, migrate ile çalışmaz (throttle sayaçları için DatabaseCache tablosu); idempotenttir.
set -e

python manage.py migrate --noinput
python manage.py createcachetable
