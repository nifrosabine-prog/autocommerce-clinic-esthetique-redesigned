# Rapport de validation runtime — dernière version Clinique Esthétique

## Version testée

La version sélectionnée est `/home/ubuntu/autocommerce_ready_to_go`, plus récente que `/home/ubuntu/audit_autocommerce`. La copie de recette utilisée est `/home/ubuntu/aesthetic_runtime_audit`. Une base PostgreSQL dédiée `autocommerce_clinic_runtime` et Redis DB 1 ont été utilisés afin d’isoler la campagne du runtime garage.

## Build et gates

Le backend passe **539 tests**, avec 1 test ignoré. Ruff est propre, la compilation Python est propre, Alembic atteint la tête unique `d7e8f9a0b1c2`, `pip-audit` ne signale aucune vulnérabilité connue et `pip check` est propre après alignement de boto3/botocore sur 1.42.24 et ReportLab sur 4.4.3.

Le frontend a été reconstruit depuis le lockfile avec `pnpm install --frozen-lockfile`. Le typecheck passe, les tests Vitest passent avec **67 tests dans 12 fichiers**, et le build Vite de production passe. Le build génère le frontend sous `dist/public`.

## Runtime

PostgreSQL, Redis, FastAPI sur le port 8100, Vite preview sur le port 5175, Celery worker et Celery beat ont démarré. `celery inspect ping` répond `pong`. La tâche `reminder_j1_task` a été exécutée avec succès et sans erreur d’import.

Le premier lancement Celery a utilisé par erreur `celery_app.celery`, alors que le module réel est `services.celery_app.celery`. Le lancement conforme a été corrigé et validé. Les fichiers Compose esthétiques utilisent déjà le chemin correct `services.celery_app.celery`.

## Parcours par rôle

| Rôle | Scénario | Résultat |
|---|---|---|
| Directrice | Connexion, `/auth/me`, utilisateurs, création des actes et audit financier | PASS |
| Assistante | Création patient, prise de rendez-vous, agenda, création et paiement facture | PASS |
| Médecin | Confirmation du rendez-vous, signature consentement, création dossier médical, lecture timeline | PASS |
| Esthéticienne | Lecture de la timeline et du dossier du patient | PASS |
| Commercial | Lecture patients autorisée, création patient refusée | PASS RBAC : 403 sur écriture |
| Admin | Compte créé par la directrice et connexion valide | PASS |

Le scénario complet a créé un acte esthétique, un patient, un rendez-vous avec médecin, un consentement valide, un dossier médical, une facture de 214,20 et un paiement. Le paiement a généré 21 points de fidélité. La directrice a ensuite retrouvé les traces de paiement dans l’audit financier.

## Anomalies et interprétation

| Observation | Diagnostic | Statut |
|---|---|---|
| `Fernet key must be 32 url-safe base64-encoded bytes` lors du premier dossier | La clé de l’environnement de recette générée manuellement n’était pas une clé Fernet valide. | Corrigé dans l’environnement de recette avec deux clés base64 valides; le dossier a ensuite été créé en 200. |
| `pip check` signalait boto3/botocore et ReportLab | Conflits avec les paquets présents dans l’environnement de contrôle, non défaut métier de l’application. | Corrigé dans la copie de validation par mise à niveau des contraintes; pip check est propre. |
| Premier lancement Celery : `No module named celery_app` | Mauvais chemin de module dans la commande de test. | Corrigé en utilisant `services.celery_app.celery`; Compose source est déjà conforme. |
| Rate limiting login `5/minute` pendant la matrice rapide | Le compteur est conservé dans Redis DB 1, y compris après redémarrage API. | Comportement de sécurité attendu; Redis de recette a été réinitialisé avant le rejeu commercial. |
| Landing page : réservation publique temporairement indisponible | Configuration de recette avec réservation publique désactivée; les rendez-vous internes sont disponibles et fonctionnent. | Décision de configuration, pas bug bloquant. Activer `PUBLIC_ROUTES_ENABLED`/workflow public et fournir contenu clinique si réservation publique attendue. |

## URLs publiques temporaires

Frontend direct : https://5175-ivbbqzym6kuuj86p5z6xk-e0c9d40c.us3.manus.computer/

API directe : https://8100-ivbbqzym6kuuj86p5z6xk-e0c9d40c.us3.manus.computer

Proxy mono-origine frontend + API : https://8180-ivbbqzym6kuuj86p5z6xk-e0c9d40c.us3.manus.computer/

Le frontend direct et le proxy mono-origine répondent HTTP 200. L’API `/health` répond HTTP 200. Le login directrice répond HTTP 200 sur l’API et via le proxy.

## Verdict

La dernière version esthétique est **fonctionnelle en recette contrôlée**, avec une communication cohérente entre directrice, assistante, médecin, esthéticienne, commercial et admin. Les contrôles RBAC observés sont conformes au scénario. La seule décision métier à confirmer est l’activation de la réservation publique; elle est actuellement désactivée par configuration. Les URLs sont temporaires et l’environnement doit être reproduit sur un hôte persistant avec secrets rotés, TLS/Nginx, sauvegardes et supervision avant production.
