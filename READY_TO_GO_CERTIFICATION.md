# AutoCommerce Clinic — Certificat de release candidate

**Date de vérification :** 19 août 2026  
**Périmètre :** API FastAPI, services métier, modèle de données, tâches Celery, intégrations WhatsApp/LLM, frontend React/Vite, scripts de déploiement et contrôles de sécurité.  
**Niveau visé :** qualité opérationnelle 8–9/10.

## Verdict

> **VERDICT : GO CONDITIONNEL POUR DÉPLOIEMENT CONTRÔLÉ — NO-GO POUR UN DÉPLOIEMENT AVEUGLE OU INSTANTANÉ SANS VALIDATION DU VPS CIBLE.**

Le projet a été remédié sur les risques bloquants identifiés par l’audit initial. Les vecteurs de franchissement inter-tenant testés sont désormais bloqués, le backend passe sa suite complète, le frontend est typé, testé et compilé, le lint est propre et les dépendances ne présentent pas de vulnérabilité connue dans les contrôles exécutés.

La mention « instantanée » ne peut pas être certifiée depuis l’environnement d’audit, car le runtime Docker, le PostgreSQL, le Redis, les secrets de production, les fournisseurs externes et le VPS cible ne sont pas disponibles ici. La release est donc **prête à entrer dans la procédure de go-live**, mais le dernier feu vert doit être donné après exécution du smoke test sur le VPS cible.

## Preuves de validation

| Contrôle | Résultat | Preuve |
|---|---:|---|
| Tests backend complets | **539 réussis, 1 ignoré, 0 échec** | `backend_final.log` |
| Tests frontend | **67 réussis dans 12 fichiers** | `frontend_final.log` |
| TypeScript | **PASS** | `frontend_final.log` |
| Build frontend Vite | **PASS** | `frontend_final.log` |
| Ruff backend | **PASS** | gate final |
| Audit dépendances Python | **Aucune vulnérabilité connue** | `pip-audit` |
| Audit dépendances JavaScript | **Aucune vulnérabilité connue** | `pnpm audit --prod` |
| Probe fidélité inter-tenant | **Bloqué** | `audit_cross_tenant_probe_after.py` |
| Probe commissions inter-tenant | **Bloqué** | `audit_cross_tenant_probe_after.py` |
| Probe stock/scan inter-tenant | **Bloqué** | `audit_cross_tenant_probe_after.py` |
| Probe dashboard stock inter-tenant | **Bloqué** | `audit_cross_tenant_probe_after.py` |
| Probe copilote CRM inter-tenant | **Bloqué** | `audit_cross_tenant_probe_after.py` |
| Pré-déploiement production avec configuration temporaire | **PASS** | `release_gates_after.log` |
| Syntaxe des scripts shell | **PASS** | `bash -n` |

## Corrections principales réalisées

### Isolation multitenant

Les services fidélité, commissions, stock injectable, QR/étiquettes et copilote CRM imposent désormais le contexte clinique sur les lectures, mutations, agrégats et chargements de relations. Les routes propaguent le tenant authentifié au lieu de faire confiance à une valeur fournie par le navigateur. Les jobs asynchrones et planifiés sont exécutés par clinique, avec commit explicite et filtrage des relations associées.

Des tests permanents de non-régression ont été ajoutés dans `api-server/tests/test_multitenant_remediation.py`. Ils couvrent la fidélité, les commissions, le scan stock, le dashboard stock et le chargement du copilote CRM.

### RBAC médical

La matrice RBAC a été alignée avec la politique médicale : la directrice conserve une lecture administrative masquée des dossiers, mais ne peut ni écrire le contenu médical ni accéder aux photos médicales. Les routes HTTP de photos ont été alignées sur cette règle ; les opérations de dossier et de consentement restent séparées des opérations photo.

### Workflows et traitements asynchrones

Les tâches Celery d’anniversaire, d’inactivité, d’expiration des points, de rappels agenda, de rappels d’injection et de commissions sont maintenant tenant-scoped. Les tâches qui modifient des données effectuent un commit explicite. Le calcul mensuel de commissions, référencé par Celery mais absent du service, a été ajouté avec prévention de double création par facture.

### Intégrations externes

Le connecteur WhatsApp est désormais fail-closed lorsque le canal est désactivé ou absent de l’allowlist. Le mode dev reste disponible uniquement lorsque les credentials ne sont pas configurés, ce qui maintient les tests locaux sans permettre un envoi silencieux en production. Les rappels fidélité et post-injection respectent l’opt-out.

### Frontend et session

La réhydratation frontend utilise le cookie refresh HttpOnly lorsque l’access token en mémoire est absent après un rechargement. Aucun token n’est persisté dans le stockage navigateur. Le proxy Nginx frontend transmet désormais `X-Forwarded-For`, ce qui permet une traçabilité et un rate limiting cohérents derrière le reverse proxy.

### Sauvegarde et exploitation

Les scripts de backup et de restauration vérifient désormais un HMAC sidecar avant déchiffrement, en complément du chiffrement existant. Les scripts shell ont été vérifiés par `bash -n`. Le rate limiting utilise Redis hors test et n’accepte pas de fallback mémoire en production ; le stockage mémoire est limité à l’environnement de test.

## Conditions de go-live obligatoires

Avant le déploiement réel, l’équipe d’exploitation doit injecter des secrets générés par le gestionnaire de secrets, et non ceux utilisés dans les exemples ou dans les tests. Il faut notamment définir `SECRET_KEY`, `FERNET_KEY`, `PHOTO_ENCRYPTION_KEY`, `DATABASE_URL`, `REDIS_URL`, `CORS_ORIGINS` et les paramètres de cookies sécurisés.

Le mode de déploiement doit être déclaré explicitement. Pour une installation mono-clinique interne, utiliser `DEPLOYMENT_MODE=internal_single_clinic` avec un `CLINIC_ID` explicite. Pour une installation entreprise multitenant, utiliser `DEPLOYMENT_MODE=enterprise`, configurer PostgreSQL et Redis réellement disponibles, désactiver tout défaut implicite et valider les politiques de tenant sur la base cible.

Les intégrations WhatsApp, e-mail, SMS, LLM, stockage objet et monitoring doivent rester désactivées tant que leurs credentials, leurs allowlists, leurs contrats de traitement et leurs tests de bout en bout ne sont pas validés. Le contrôle de pré-déploiement doit être exécuté avec `ENV=production` sur le VPS cible.

## Smoke test VPS à exécuter avant ouverture aux utilisateurs

| Étape | Critère d’acceptation |
|---|---|
| Migration | Une seule tête de migration, migration appliquée sur une base vide de staging puis sur la base cible contrôlée |
| Démarrage | API, frontend, PostgreSQL, Redis et workers healthy |
| Authentification | Login, MFA, refresh cookie, expiration et logout validés |
| RBAC | Chaque rôle reçoit exactement les permissions prévues |
| Multitenant | Deux cliniques de test ne peuvent lire, modifier, rechercher, exporter ou télécharger les ressources de l’autre |
| Jobs | Un job par clinique ne modifie aucune donnée d’une autre clinique |
| Sauvegarde | Backup chiffré, HMAC vérifié, restauration sur instance isolée, comptages cohérents |
| Observabilité | Logs, correlation ID, erreurs, latence et alertes visibles |
| Rollback | Retour arrière testé pour l’image et la migration selon la procédure approuvée |
| Externe | WhatsApp/LLM/e-mail ne sortent que si allowlist, feature flag et credentials sont valides |

## Limites restantes

Le runtime Docker n’était pas disponible dans l’environnement d’audit ; aucun conteneur n’a donc été lancé ici. La restaurabilité réelle d’un backup n’a pas pu être prouvée contre un PostgreSQL isolé vivant. Les tests de charge, la rotation effective des secrets, les certificats TLS, les DNS, le firewall, le reverse proxy public et les appels réels aux fournisseurs externes restent à valider sur l’infrastructure cible.

En conséquence, le statut recommandé est **release candidate prête pour déploiement contrôlé**, avec **ouverture production autorisée uniquement après le smoke test VPS et la restauration de backup réussie**. Après ces deux preuves, le projet peut être classé **ready to go entreprise 8–9/10**.
