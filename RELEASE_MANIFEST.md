# Manifeste de livraison — Clinic Esthétique

**Release :** 26 août 2026  
**Racine de livraison :** ce dossier `source/`  
**Architecture :** frontend React/Vite (`autocommerce-app/`) et API FastAPI (`api-server/`).

## Contenu livré

La livraison regroupe l’application clinique, les migrations Alembic, la documentation d’exploitation, les scripts de démarrage et le `Dockerfile` de cette racine. Le frontend est reconstruit lors de la construction de l’image et est ensuite servi par FastAPI.

| Composant | Emplacement | Rôle |
| --- | --- | --- |
| API clinique | `api-server/` | API FastAPI, règles métier, consentements, migrations et tests backend. |
| Interface clinique | `autocommerce-app/` | Interface React, landing publique et tests frontend. |
| Déploiement | `Dockerfile`, `start.sh`, fichiers Compose | Démarrage de l’application depuis cette racine. |
| Documentation | `README.md`, `INSTALLATION.md`, `OPERATIONS.md`, `SECURITY.md` | Installation, exploitation et sécurité. |

## Validations effectuées

| Contrôle | Résultat |
| --- | --- |
| Tests backend | 569 réussis, 1 ignoré. |
| Contrôle TypeScript | Réussi. |
| Tests frontend | 13 fichiers, 87 tests réussis. |
| Build frontend | Réussi ; `index.html` de 1 093 octets, sans runtime de diagnostic. |
| Migration Alembic | Tête unique `20260826_consentement_contrat_snapshot`. |
| Recette isolée | Réservation publique, branding PDF, double signature et refus e-mail sans BYOK actif vérifiés avec données synthétiques. |

## E-mail BYOK du contrat signé

La clinique configure uniquement son domaine d’envoi et son adresse expéditrice dans **Paramètres**. La clé Resend est un secret de déploiement : elle ne doit jamais être saisie dans l’interface, ajoutée à la base de données ou déposée dans le code. L’envoi est volontairement bloqué tant que le déploiement ne contient pas la clé Resend, que le domaine n’est pas vérifié et que le canal e-mail n’est pas explicitement autorisé.

## Exclusions de l’archive

L’archive de remise exclut volontairement les dépendances installées, les builds locaux, les caches Python et JavaScript, les données SQLite temporaires, les journaux, les fichiers d’environnement et les outils de recette. Elle ne contient pas le scaffold parent au-dessus de `source/`.

> Le contrat de consentement est un modèle logiciel. Sa formulation doit être validée par le praticien responsable et un conseil juridique compétent avant son utilisation auprès de patients réels.
