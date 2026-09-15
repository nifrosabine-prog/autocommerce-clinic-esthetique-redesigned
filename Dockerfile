FROM node:22-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv build-essential libpq-dev libgomp1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . ./
RUN pip3 install --no-cache-dir --break-system-packages -r api-server/requirements.txt \
    && npm install --global --force pnpm@10.15.1 \
    && pnpm install --frozen-lockfile \
    && pnpm build:frontend \
    && rm -rf api-server/web-dist \
    && mkdir -p api-server/web-dist \
    && cp -R autocommerce-app/dist/public/. api-server/web-dist/ \
    && test -s api-server/web-dist/index.html
ENV PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["bash", "/app/start-railway.sh"]
