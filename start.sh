#!/usr/bin/env bash
set -euo pipefail
# El plan gratuito no admite preDeployCommand. Una única instancia migra al arrancar.
python manage.py migrate --noinput
python manage.py cargar_categorias
# Permite crear el primer admin sin consola remota (Render gratis no incluye Shell).
# Se ejecuta solo cuando el propietario configuró la clave en las variables secretas.
if [[ -n "${ADMIN_PASSWORD:-}" ]]; then
  python manage.py crear_admin
fi
exec gunicorn finanza_project.wsgi:application --bind "0.0.0.0:${PORT:-10000}" --workers "${WEB_CONCURRENCY:-2}" --access-logfile - --error-logfile -
