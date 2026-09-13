# Rapport de validation de release — Clinic Esthétique

## Périmètre

Cette release prépare le projet pour un déploiement conteneurisé avec PostgreSQL 16, Redis 7, l’API FastAPI, un worker et un beat Celery, un reverse-proxy TLS Caddy, un service de sauvegarde automatisée, et le frontend React/Vite servi par Nginx.

**Correctif de sécurité (post-audit)** : les archives précédentes (« V5 » et « recette-final-CORRIGE ») livraient bien des secrets réels — `deploy/production.env`, `api-server/.env` et `api-server/.env.backup` contenaient une clé OpenAI live et des mots de passe en clair, malgré cette affirmation. Ces trois fichiers ont été supprimés de l'archive et ne sont plus livrés ; seul `deploy/production.env.example` (placeholders uniquement) est inclus. La clé OpenAI exposée doit être révoquée sur la console OpenAI si ce n'est pas déjà fait — voir README pour la procédure de configuration.

## Corrections et ajouts

| Élément | Résultat |
|---|---|
| PostgreSQL | Service de production avec volume persistant et healthcheck `pg_isready`. |
| Redis | Service de production avec persistance AOF et healthcheck `redis-cli ping`. |
| API | Attente des dépendances saines, exécution automatique de `alembic upgrade head`, healthcheck `/ready`. |
| Frontend | Build autonome Nginx, reverse-proxy `/api/` vers le service API interne. |
| Sécurité | Modèle `deploy/production.env.example` sans secrets ; fichier réel ignoré par Git **et retiré de l'archive livrée** (voir correctif ci-dessus). |
| Vérification | Script `scripts/verify_release.sh` pour compilation, migrations, tests, TypeScript et build. |
| Audit équipe | Les corrections P0 déjà présentes dans l’archive ont été vérifiées par les tests de réactivation, persistance et audit. |

## Vérifications exécutées

La base PostgreSQL `clinic_validation` et Redis locaux ont été démarrés, puis les migrations ont été appliquées jusqu’à la révision unique `20260904_team_audit`. Le contrôle Alembic confirme une seule tête de migration.

La suite backend a produit **619 tests réussis et 1 test ignoré**. La suite frontend a produit **73 tests réussis dans 13 fichiers**. Le contrôle TypeScript et le build Vite de production ont également réussi. Le smoke test HTTP a confirmé :

```json
{"status":"ok"}
{"status":"ready","postgres":"ok","redis":"ok"}
```

## Démarrage de production

```bash
cp deploy/production.env.example deploy/production.env
# Remplacer toutes les valeurs indiquées comme obligatoires.
docker compose --env-file deploy/production.env -f docker-compose.production.yml up -d --build
```

Le fichier `deploy/production.env` doit être conservé hors du dépôt et les clés de chiffrement doivent être distinctes. Le modèle fourni ne doit jamais être utilisé sans remplacement des placeholders.

## Limite de validation

L’environnement de travail ne disposait pas du moteur Docker ; la composition a donc été validée syntaxiquement et ses dépendances ont été réellement testées directement avec PostgreSQL et Redis locaux. La construction et le démarrage des quatre conteneurs doivent être effectués sur l’hôte de production disposant de Docker Compose.
