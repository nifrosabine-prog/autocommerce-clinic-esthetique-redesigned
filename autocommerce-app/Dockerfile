# Build autonome du frontend Clinique Esthétique.
# Le contexte Docker attendu est ./autocommerce-app.
FROM node:22-alpine AS builder

ARG PNPM_VERSION=10.15.1
RUN npm install --global pnpm@${PNPM_VERSION}

WORKDIR /app

ARG VITE_API_URL=/api/v1
ARG VITE_PUBLIC_API_URL=/api/public
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_PUBLIC_API_URL=${VITE_PUBLIC_API_URL}

COPY package.json pnpm-lock.yaml ./
COPY patches ./patches
RUN pnpm install --frozen-lockfile --ignore-workspace

COPY . .
RUN pnpm check && pnpm build

FROM nginx:1.27-alpine AS runtime

COPY --from=builder /app/dist/public /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Exécution non-root : Nginx écoute sur le port utilisateur 8080.
RUN addgroup -S clinicweb && adduser -S -G clinicweb clinicweb && \
    chown -R clinicweb:clinicweb /usr/share/nginx/html /var/cache/nginx /var/log/nginx /etc/nginx /run
USER clinicweb
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://127.0.0.1:8080/index.html || exit 1

CMD ["nginx", "-g", "daemon off;"]
