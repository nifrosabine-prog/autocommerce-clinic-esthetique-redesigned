# AutoCommerce Clinic — Guide de recette locale

## Installation classique sans Docker

Le projet a été validé avec PostgreSQL et Redis installés comme services système.

```bash
sudo systemctl enable --now postgresql redis-server
cd api-server
python -m venv ../.venv
source ../.venv/bin/activate
python -m pip install -r requirements.txt
alembic upgrade head
```

Dans un second terminal :

```bash
cd autocommerce-app
pnpm install --frozen-lockfile
pnpm check
pnpm test
pnpm build
```

## Démarrage

API :

```bash
cd api-server
source ../.venv/bin/activate
set -a
source .env
set +a
../.venv/bin/alembic upgrade head
../.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
```

Frontend :

```bash
cd autocommerce-app
pnpm dev --host 0.0.0.0 --port 3000
```

Le frontend Vite proxyfie les appels `/api` vers `http://localhost:8000`.

## Vérifications de santé

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

La réponse attendue de `/ready` confirme PostgreSQL et Redis :

```json
{"status":"ready","postgres":"ok","redis":"ok"}
```

## Données mock de recette

Le seed crée ou met à jour :

- un compte administrateur QA ;
- un compte médecin QA ;
- une patiente de test ;
- un acte médical de recette ;
- un produit injectable ;
- un lot injectable ;
- un numéro autorisé pour les tests assistant.

Pour relancer le seed :

```bash
cd api-server
set -a
source .env
set +a
QA_ADMIN_EMAIL='qa.admin@clinic.local' \
QA_ADMIN_PASSWORD='QA-Admin-2026!local' \
QA_MEDECIN_EMAIL='qa.medecin@clinic.local' \
QA_MEDECIN_PASSWORD='QA-Medecin-2026!local' \
ENV=test ../.venv/bin/python seed_production.py
```

Ces comptes et mots de passe sont réservés à la recette locale et doivent être remplacés avant la production.

## Périmètre des assistants

Le **chat public** fournit uniquement des informations générales sur la clinique, les actes publiés, les horaires, l’adresse, les contacts et les rendez-vous. Il ne doit pas exposer les KPI, le stock, le chiffre d’affaires ou les données patient internes.

L’**assistant WhatsApp privé de la direction** peut consulter les statistiques internes, le stock, les alertes, les rendez-vous et les informations de facturation selon le rôle et les permissions. Les actions sensibles doivent rester soumises à confirmation.

Pour les demandes médicales personnalisées, l’assistant répond explicitement qu’il n’est pas médecin et oriente vers un médecin ou l’équipe de la clinique.

## Validation finale

La suite backend a été validée avec :

```text
620 passed, 1 skipped
```

Le frontend a été validé avec :

```text
pnpm check
pnpm test
pnpm build
```

## Sécurité avant mise en ligne

Cette archive ne contient **aucun fichier `.env` ni secret**. Les secrets de production sont générés **sur le VPS** par `deploy/generate_production_env.sh` (clés aléatoires `openssl rand`, écriture en `chmod 600`, refus d'écraser un fichier existant) - voir `docs/CHANGELOG_AUDIT_VPS_2026-09-06.md`. Toute clé OpenAI/Meta ayant circulé dans des archives précédentes (« V5 », « recette-final-CORRIGE ») doit être révoquée puis régénérée avant mise en production.

Ne jamais committer ni livrer `deploy/production.env` ni `api-server/.env`. Utiliser un gestionnaire de secrets (Docker secrets, variables du fournisseur d'hébergement).
