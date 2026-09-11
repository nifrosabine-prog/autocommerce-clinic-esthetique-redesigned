FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
COPY . /app

# Les valeurs par défaut du code historique pointent vers /home/ubuntu.
# En conteneur, les fichiers persistants restent sous /app.
ENV DATA_DIR=/app/data \
    PHOTOS_DIR=/app/data/photos \
    UPLOADS_DIR=/app/data/uploads \
    BRANDING_DIR=/app/data/branding \
    BACKUPS_DIR=/app/backups
RUN mkdir -p /app/data/photos /app/data/uploads /app/data/branding /app/backups \
    && useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
