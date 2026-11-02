# Despliegue de SIGAP

SIGAP es una aplicación Django monolítica que renderiza el panel administrativo
desde el servidor. No requiere un frontend separado ni un servicio de API
independiente.

## Preparación

1. Copia `.env.example` como `.env` y reemplaza los valores de Django,
   PostgreSQL y correo.
2. Coloca la credencial de la cuenta de servicio de Google en
   `credentials/google-sheets.json`. No la agregues al repositorio.
3. Comparte con el correo de la cuenta de servicio únicamente las hojas que
   deben ser leídas por los importadores.

La cuenta de servicio se monta como un secreto Docker en
`/app/credentials/google-sheets.json`. Esta es la única ruta que utiliza la
aplicación, tanto localmente como dentro del contenedor.

## Arranque

```text
docker compose up -d --build
```

El contenedor web ejecuta las migraciones, recolecta los archivos estáticos y
arranca Gunicorn. El sitio queda disponible en `http://localhost:8000/admin/`.

Los importadores de Google Sheets se ejecutan como comandos Django dentro del
contenedor, por ejemplo:

```text
docker compose exec web python manage.py importar_forms
```

## Producción

Coloca un proxy TLS (por ejemplo, Nginx, Caddy o el balanceador del proveedor)
delante del puerto 8000 y configura `DJANGO_ALLOWED_HOSTS` y
`DJANGO_CSRF_TRUSTED_ORIGINS` con el dominio real. Cuando el proxy fuerce
HTTPS, puedes activar `DJANGO_SECURE_SSL_REDIRECT=True` y configurar HSTS
después de verificar que todo el dominio funciona exclusivamente por HTTPS.
Mantén PostgreSQL en un volumen persistente y realiza respaldos.

La clave privada de Google que haya sido expuesta o compartida previamente debe
revocarse y reemplazarse en Google Cloud antes de usar este despliegue.
