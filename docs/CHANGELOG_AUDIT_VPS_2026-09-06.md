# Changelog — corrections suite audit "GO conditionnel" (VPS mono-serveur)

Date : 2026-09-06
Rapport source : audit archive `AutoCommerce-Clinic-recette-final-CORRIGE (2).zip`
(3 bloquants identifiés avant mise en ligne).

## Bloquants corrigés dans cette archive

### 1. `poppler-utils` manquant (scan de factures PDF cassé en prod)
`api-server/services/facture_scanner.py` utilise `pdf2image.convert_from_bytes`,
qui appelle le binaire système `pdftoppm`. Il n'était installé dans aucune
étape du `Dockerfile` de l'API.

**Corrigé** : `api-server/Dockerfile`, étape finale (runtime) —
`poppler-utils` ajouté à côté de `libpq-dev`/`curl`.
Vérification après build : `docker compose exec api pdftoppm -v`.

### 2. `deploy/production.env` — génération sécurisée au lieu d'un fichier pré-rempli
Le rapport proposait de livrer un `production.env` avec DOMAIN + clés en
dur. **Choix fait ici : ne jamais mettre de secrets réels dans une
archive livrée** (même générés aléatoirement) — un fichier zip peut être
recopié, archivé, envoyé par erreur.

**Ajouté** : `deploy/generate_production_env.sh` — script exécuté
**sur le VPS**, jamais en local ni committé :
- demande interactivement le `DOMAIN` (DNS déjà pointé) ;
- génère avec `openssl rand` : `POSTGRES_PASSWORD`, `SECRET_KEY` (88
  caractères, > 64 requis par `config.py`), `FERNET_KEY`,
  `PHOTO_ENCRYPTION_KEY`, `MFA_ENCRYPTION_KEY` (3 clés Fernet distinctes,
  valides — vérifié avec `cryptography.Fernet`) ;
- écrit `deploy/production.env` en `chmod 600` ;
- refuse d'écraser un fichier existant (évite de perdre des secrets en
  usage par erreur de relance).

Usage :
```bash
cd deploy && ./generate_production_env.sh
# puis vérifier/adapter POSTGRES_DB, POSTGRES_USER, WEB_PORT si besoin
```

### 3. Pare-feu + comptes de recette (action opérationnelle, pas de code à livrer)
Vérifié dans le code : aucun seed QA (`qa.admin@clinic.local`,
`qa.medecin@clinic.local`...) n'est déclenché automatiquement par
`api-server/start.sh` ni par `docker-compose.production.yml` — c'est une
commande manuelle documentée à part dans `docs/RECETTE_LOCALE.md`. Le
risque n'est donc pas un bug de code mais un rappel opérationnel :

- **À faire sur le VPS, pas dans l'archive** : `ufw allow 80,443/tcp`
  puis `ufw enable` (le service `web` n'expose déjà rien en direct,
  tout passe par `caddy` — confirmé dans `docker-compose.production.yml`).
- **Ne pas lancer le script de seed QA en production.** Utiliser
  `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` dans
  `deploy/production.env` pour créer le compte direction initial, puis
  retirer ces deux lignes du fichier une fois le compte créé (rappel
  ajouté dans la sortie de `generate_production_env.sh`).

## Vigilance non bloquante corrigée

### Fenêtre de démarrage `api` (`start_period`) trop courte pour 44 migrations
`docker-compose.production.yml` : le healthcheck de `api` avait
`start_period: 30s`. Sur un VPS d'entrée de gamme, les 44 migrations
Alembic exécutées au boot (`start.sh` → `alembic upgrade head`) peuvent
dépasser cette fenêtre, ce qui marquerait `api` `unhealthy` et bloquerait
`worker`/`beat`/`web`/`caddy` (`depends_on: condition: service_healthy`).

**Corrigé** : `start_period` passé à `120s` pour le service `api`.

## Non traité ici (actions humaines hors du dépôt, pas du code)

- **Révoquer l'ancienne clé OpenAI** qui a circulé dans les archives
  précédentes (« V5 », « recette-final-CORRIGE ») — à faire directement
  sur la console OpenAI, indépendamment de cette archive.
- **Smoke test du premier boot**, non exécuté ici (pas de PostgreSQL/
  Redis dans le bac à sable de correction) :
  ```bash
  docker compose --env-file deploy/production.env \
    -f docker-compose.production.yml up -d --build
  docker compose -f docker-compose.production.yml ps   # tous "healthy"
  curl -fsS https://votre-domaine.tld/api/v1/ready
  curl -fsS https://votre-domaine.tld/
  # + upload d'une facture PDF pour valider le correctif poppler-utils
  ```
- Les 619 tests backend / 73 tests frontend documentés dans
  `docs/RELEASE_VALIDATION_2026-09-05.md` restent une déclaration du
  projet, non re-exécutés dans cet environnement (pas d'accès réseau
  pour installer les dépendances).

## Fichiers modifiés / ajoutés dans ce lot

- `api-server/Dockerfile` (édité — `poppler-utils`)
- `docker-compose.production.yml` (édité — `start_period: 120s` sur `api`)
- `deploy/generate_production_env.sh` (nouveau, exécutable)
- `docs/CHANGELOG_AUDIT_VPS_2026-09-06.md` (ce fichier)

Voir aussi `docs/CHANGELOG_LINA_MULTILANG_BLOC9_10.md` pour le lot
précédent (Lina patient/multilingue + Bloc 10 social).
