# AutoCommerce Clinic

Plateforme de gestion pour clinique esthétique : accueil, agenda, dossiers patients, actes, facturation, stock, rôles et permissions, exports PDF et intégrations optionnelles.

Cette branche correspond à la version issue de l’archive de validation du **15 septembre 2026**, incluant le branding des factures et les correctifs d’audit associés.

## Structure

- `api-server/` : API FastAPI, migrations Alembic, services métier et tests.
- `autocommerce-app/` : application web frontend Vite/React, servie par Nginx en production.
- `deploy/` : exemples de configuration et fichiers de déploiement.
- `docs/` : documentation fonctionnelle et rapports de validation.
- `BRANDING_FACTURES.md` : notes spécifiques au branding des factures.

## Démarrage local

### API

```bash
cd api-server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../deploy/production.env.example ../deploy/production.env
# Renseigner les valeurs locales nécessaires dans deploy/production.env
python main.py
```

### Frontend

```bash
cd autocommerce-app
corepack enable
pnpm install
pnpm dev
```

Les scripts de validation et les tests sont décrits dans `api-server/pytest.ini`, `qa_smoke.sh` et `docs/RECETTE_LOCALE.md`.

## Déploiement

Les exemples de configuration se trouvent dans `deploy/`. Ne jamais committer de fichier d’environnement réel, de clé privée, de mot de passe ou de donnée patient. Pour un déploiement conteneurisé, consulter les Dockerfiles de `api-server/` et `autocommerce-app/`, ainsi que `nginx-local.conf`.

## Sécurité et données médicales

Le projet traite des données potentiellement sensibles. Utiliser uniquement des secrets injectés par l’environnement d’exécution, des clés Fernet distinctes pour les usages prévus et une base de données protégée. Les artefacts de recette et données générées localement sont volontairement exclus du dépôt ; consulter `SECURITY.md` ou la documentation de déploiement avant toute mise en production.

## Licence

Aucune licence open source n’est déclarée dans cette archive. Tous droits réservés au propriétaire du projet, sauf accord écrit contraire.
