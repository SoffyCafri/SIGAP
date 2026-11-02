FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN mkdir -p /app/staticfiles \
    && chmod +x /app/entrypoint.sh \
    && useradd --create-home --shell /usr/sbin/nologin sigap \
    && chown -R sigap:sigap /app

USER sigap

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
