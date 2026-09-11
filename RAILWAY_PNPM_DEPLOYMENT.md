# Déploiement Railway — AutoCommerce Clinic Esthétique (PNPM, sans Docker)

Cette version est validée localement avec **PNPM**, un backend FastAPI et un frontend Vite. Pour Railway, il est recommandé de créer deux services dans le même projet : un service API et un service frontend. Les deux services utilisent le même dépôt mais des répertoires racines distincts.

## Service API

Le répertoire racine Railway doit être `api-server`.

| Paramètre | Valeur |
|---|---|
| Build command | `python -m pip install -r requirements.txt` |
| Start command | `bash start.sh` |
| Port | Railway fournit automatiquement `PORT`; le script l'utilise désormais avec repli sur `8000`. |

Variables minimales : `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `FERNET_KEY`, `PHOTO_ENCRYPTION_KEY`, `CORS_ORIGINS`, `ENV=production`, `DEPLOYMENT_MODE=enterprise`, `PUBLIC_ROUTES_ENABLED=true` si la landing utilise les routes publiques, et `PUBLIC_CLINIC_ID` si nécessaire. Les clés IA, WhatsApp, e-mail et stockage ne sont ajoutées que lorsque l'intégration correspondante est réellement activée.

Le compte administrateur initial doit être injecté hors dépôt par `BOOTSTRAP_ADMIN_EMAIL` et `BOOTSTRAP_ADMIN_PASSWORD`. Le script `start.sh` exécute les migrations avant de démarrer Uvicorn et n'effectue le bootstrap que si les variables sont présentes.

## Service frontend

Le répertoire racine Railway doit rester la racine du dépôt afin d'utiliser le lockfile PNPM et le workspace.

| Paramètre | Valeur |
|---|---|
| Install / build command | `pnpm install --frozen-lockfile && pnpm build:frontend` |
| Start command | `pnpm --dir autocommerce-app preview --host 0.0.0.0 --port $PORT` |
| Variable API | `VITE_API_URL=https://<domaine-api-railway>/api/v1` avant le build. |

Le frontend doit être reconstruit après chaque changement de `VITE_API_URL`, car Vite injecte cette valeur au moment du build. Le domaine final du frontend doit être ajouté à `CORS_ORIGINS` côté API.

## Ordre conseillé

Créer d'abord PostgreSQL et Redis dans le projet Railway, puis le service API. Vérifier `/health`, exécuter les migrations et créer l'administrateur initial. Créer ensuite le service frontend, définir `VITE_API_URL`, lancer le build PNPM et vérifier la landing page, la connexion, le dashboard et une route métier protégée.

## Points de contrôle avant production

Les secrets ne doivent pas être déposés dans GitHub. Il faut utiliser les variables Railway et régénérer les clés pour cette installation. Le compte de validation local `admin@clinic.local` et son mot de passe de test ne sont pas des identifiants de production et ne doivent pas être réutilisés. La base locale SQLite et le script `local_validation_setup.py` servent exclusivement à la validation sandbox et ne font pas partie de la configuration Railway.
