#!/bin/sh
# App Platform PRE_DEPLOY job'ı: her deploy'dan önce çalışır, hata verirse yeni sürüm yayına alınmaz.
# createcachetable, migrate ile çalışmaz (throttle sayaçları için DatabaseCache tablosu); idempotenttir.
set -e

python manage.py migrate --noinput
python manage.py createcachetable
