# Build, exposition et validation multi-rôles — Clinic Esthétique

## Résultat

L’application a été reconstruite dans l’environnement de validation avec PostgreSQL 16, Redis 7, les dépendances Python, les dépendances frontend et `esbuild 0.25.12`. La base PostgreSQL `clinic_e2e` a été recréée puis migrée depuis zéro jusqu’à la révision unique `20260904_team_audit`.

Le frontend de production a été généré avec Vite et l’entrée `client/src/main.tsx` a également été bundlée directement avec esbuild en activant la condition CSS `style`. Le build Vite final contient l’URL publique de l’API de validation.

## Tests exécutés

| Domaine | Résultat |
|---|---|
| PostgreSQL | Disponible sur 127.0.0.1:5432, migrations complètes appliquées. |
| Redis | Disponible sur 127.0.0.1:6379, `/ready` confirme `redis: ok`. |
| API `/health` | OK. |
| API `/ready` | OK avec PostgreSQL et Redis. |
| TypeScript | `pnpm check` réussi. |
| esbuild | Bundle direct réussi, fichier JS généré de 3,9 Mo et CSS de 43,3 Ko. |
| Vite production | Build réussi, artefacts dans `dist/public`. |
| Comptes de recette | Directrice, médecin, assistante, commercial et esthéticienne actifs et connectables. |
| RBAC | Directrice autorisée sur `/api/v1/users`; les quatre rôles métier reçoivent correctement `403`; métriques protégées contrôlées. |
| Validation en ligne | Connexions des cinq rôles réussies via le proxy public. |
| Navigateur | Le build de production charge `/login`; la directrice se connecte et arrive sur `/dashboard`. |

## Comptes de recette

Les comptes utilisés sont `admin@clinic.local`, `medecin@clinic.local`, `assistante@clinic.local`, `commercial@clinic.local` et `estheticienne@clinic.local`. Leurs mots de passe de recette sont présents uniquement dans l’environnement de validation et ne sont pas inclus dans l’archive livrée.

## Accès temporaires

Le build frontend de production est exposé à l’adresse suivante :

<https://3002-iy8oy7whdeuec1nysdxnd-bf1f158d.us4.manus.computer/>

La page de connexion est disponible sur `/login`. L’API de validation est également exposée séparément sur :

<https://18000-iy8oy7whdeuec1nysdxnd-bf1f158d.us4.manus.computer/health>

Ces URLs sont temporaires et dépendent du maintien de l’environnement de validation actif. Elles ne constituent pas un déploiement permanent ni un environnement de production durci.

## Correctif CORS appliqué à la validation

Une première connexion depuis le build de production a échoué car le domaine frontend temporaire n’était pas présent dans `CORS_ORIGINS`. L’API a été redémarrée avec le domaine public de validation autorisé. La seconde tentative a réussi et a redirigé vers le tableau de bord directrice.

Pour un vrai déploiement, renseigner le domaine final dans `CORS_ORIGINS`, activer les cookies sécurisés, utiliser des clés distinctes générées aléatoirement et ne jamais reprendre les secrets de recette.

## Limites

La composition Docker de production est présente dans `docker-compose.production.yml`, mais le moteur Docker n’est pas disponible dans l’environnement de travail. Les services PostgreSQL et Redis ont néanmoins été installés et exécutés directement, les migrations ont été appliquées sur une base propre, les builds ont été générés et les parcours HTTP ont été vérifiés en ligne.
