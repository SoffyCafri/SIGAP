#!/bin/sh
set -eu

python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Crear superusuario automático si no existe
python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'pruebasigapqfb@gmail.com', '123456789');
    print('Superusuario creado exitosamente.')
"

exec gunicorn SIGAP.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-120}" \
    --access-logfile -
