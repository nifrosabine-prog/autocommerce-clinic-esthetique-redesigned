FROM node:22-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . ./

RUN npm install -g corepack@latest \
    && corepack pnpm install --frozen-lockfile \
    && corepack pnpm build:frontend \
    && rm -rf api-server/web-dist \
    && cp -R autocommerce-app/dist/public api-server/web-dist \
    && pip3 install --no-cache-dir --break-system-packages -r api-server/requirements.txt

WORKDIR /app/api-server
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port \"${PORT:-8000}\""]
