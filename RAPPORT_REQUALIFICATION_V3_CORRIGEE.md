# Rapport de requalification — AutoCommerce Clinic v3 corrigée

**Auteur :** Manus AI  
**Nature :** audit externe, remédiation suivie et requalification technique  
**Objet initial :** `aesthetic_release_v2_final.zip`  
**Copie corrigée :** `aesthetic_release_v3_fixed`  
**SHA-256 de l’archive v2 originale :** `c6b5da3b948f22f21ae3f7b9542409a71b05e221a7e008cecfda935a542d8ce3`  
**Date de requalification :** 22 août 2026

## 1. Décision finale

> **VERDICT : GO TECHNIQUE DE RECETTE — score 94,0/100.**
>
> La release v3 corrigée passe le gate complet de livraison, le build Docker production-like, les migrations PostgreSQL, les services PostgreSQL/Redis/API/worker/beat/web, les scénarios de sécurité, les E2E HTTP/HTTPS, le smoke full-stack, le smoke frontend par routes et la restauration PostgreSQL chiffrée et authentifiée.

Les deux défauts P0 de la v2 — élévation vers `super_admin` depuis une clinique et association WhatsApp inter-tenant — sont corrigés et leurs probes de régression sont bloquées comme attendu. L’archive v2 n’a pas été modifiée.

Ce verdict est un **GO technique pour un déploiement contrôlé**, et non une certification réglementaire ou une garantie de disponibilité de fournisseurs externes. Avant une mise en production publique, l’exploitant doit encore injecter ses propres secrets via un gestionnaire de secrets, configurer ses domaines et certificats, vérifier les webhooks de ses fournisseurs réels et faire signer la revue conformité/retention par le responsable compétent.

## 2. Score de requalification

Le score mesure la qualité observée dans les contrôles exécutés. Il ne transforme pas les validations de recette en certification légale, médicale ou contractuelle.

| Domaine | Poids | Score | Contribution |
|---|---:|---:|---:|
| Sécurité, authentification et RBAC | 20 % | 95/100 | 19,0 |
| Isolation multi-clinique et ownership | 15 % | 96/100 | 14,4 |
| Backend et API | 15 % | 94/100 | 14,1 |
| Données médicales et confidentialité | 15 % | 92/100 | 13,8 |
| Frontend, UX et accessibilité | 10 % | 90/100 | 9,0 |
| Tests et qualité de code | 10 % | 96/100 | 9,6 |
| Déploiement et exploitabilité | 10 % | 95/100 | 9,5 |
| Intégrations et traitements asynchrones | 5 % | 90/100 | 4,5 |
| **Total pondéré** | **100 %** |  | **94,0/100** |

La légère décote restante correspond principalement à l’absence de validation contre les comptes réels de chaque fournisseur de webhook, à la nécessité d’une revue humaine de conformité et au fait que le smoke frontend vérifie les routes et les parcours critiques, mais ne constitue pas une exécution manuelle exhaustive de chaque bouton de chaque écran.

## 3. Défauts corrigés

### 3.1 Sécurité, RBAC et isolation

La création ou la promotion d’un compte `super_admin` depuis une clinique est refusée côté serveur avec HTTP 403. Le matching patient WhatsApp et les mutateurs omnicanaux vérifient désormais le tenant de la conversation, du patient et des utilisateurs concernés. Le probe inter-tenant confirme qu’aucun patient de Clinic B n’est associé à une conversation de Clinic A.

Les routes d’opérations cliniques et de pointage utilisent un utilisateur actif et vérifient l’ownership de la séance, de la cure et du patient. Les paramètres de clinique transmis par le client ne permettent pas de contourner le tenant authentifié. Les E2E Clinic A/Clinic B confirment l’absence d’IDOR patient et le refus d’accès aux données de l’autre clinique.

### 3.2 MFA, sessions et secrets

Les challenges MFA sont persistés avec `jti`, expiration et date de consommation. Ils sont mono-usage et protégés contre le rejeu. Les secrets TOTP sont chiffrés au repos avec `MFA_ENCRYPTION_KEY`, séparée des autres clés de chiffrement. La migration `20260822_mfa_secret_text` corrige aussi la longueur de colonne PostgreSQL : un secret Fernet ne peut plus être tronqué par `VARCHAR(100)`.

Le refresh token reste dans un cookie `HttpOnly`, `Secure` et soumis aux règles SameSite configurées. La rotation, la détection de réutilisation et la révocation au logout sont passées dans l’E2E HTTPS. Le code frontend de production ne stocke pas de token d’authentification dans `localStorage`.

### 3.3 Données patients, photos et dossiers médicaux

L’écriture des champs médicaux chiffrés est réservée aux rôles cliniques autorisés. Le `commercial_id` est validé dans le même tenant et doit correspondre à un utilisateur actif. Les photos médicales contrôlent le patient, le dossier et la clinique avant upload ou lecture ; les lectures déchiffrées sont journalisées et la lecture HTTP est bornée.

Les dossiers, séances, suivis et utilisations de lots vérifient les liens patient/clinique. Le stock injectable applique un scoping tenant sur les produits, lots, QR, codes-barres, usages et traçabilité.

### 3.4 IA et OpenAI-compatible

Les messages effectivement transmis au fournisseur LLM sont pseudonymisés, y compris dans les structures imbriquées. Les modèles et providers sont contrôlés par allowlist, le budget est gouverné par Redis et le mode fail-closed refuse l’appel lorsque le compteur central est indisponible en production. Les assistant tools sont tenant-scopés et les opérations sensibles restent protégées.

L’URL du fournisseur est maintenant configurable par `OPENAI_BASE_URL`. Un appel applicatif réel a été exécuté avec un texte synthétique non médical : HTTP 200, provider `openai`, modèle `gpt-5-nano`, réponse reçue. Il s’agit d’une **intégration OpenAI-compatible de test fournie par l’environnement de recette**, pas d’une clé gratuite ou d’un crédit de production permanent. Aucun secret n’est livré dans l’archive.

### 3.5 Nginx, webhooks et infrastructure

Nginx expose les chemins webhook publics canoniques et bloque publiquement les anciennes routes `/api/v1` ainsi que le cœur privé. Le problème de démarrage du conteneur web causé par le tmpfs non-root a été corrigé avec les permissions adaptées à l’utilisateur Nginx.

Le runtime staging réel comprend PostgreSQL 16, Redis 7, API FastAPI, Celery worker, Celery beat et frontend Nginx. Les six services sont restés `running healthy`. Les migrations PostgreSQL atteignent une tête unique Alembic : `20260822_mfa_secret_text`.

### 3.6 Frontend, UX et parcours utilisateur

Le consentement de confidentialité est obligatoire avant réservation ou demande de rappel. Le cockpit clinique utilise une autocomplétion patient au lieu d’une saisie libre d’identifiant. Les sélecteurs MFA et les filtres E2E ont été rendus cohérents avec l’interface et le proxy `/api/v1`.

Le smoke Playwright parcourt les routes landing, login, dashboard, dashboard IA, workflows, copilote CRM, analytics, agenda, opérations cliniques, patients et détail, stock, factures, commissions, délégués, fidélité, téléconsultation, recrutement, social, équipe, paramètres, actes, salles, RH et 404. Il vérifie l’absence de réponse 5xx et d’erreur JavaScript de page. Les parcours enterprise couvrent en outre l’authentification/refresh/logout, MFA, IDOR Clinic A/B et IA médicale fail-closed.

## 4. Validation exécutée

Le gate final `scripts/release_gate.sh` a terminé par `GO: tous les contrôles critiques exécutés avec succès`.

| Contrôle | Résultat observé |
|---|---|
| Secret scan de la release | **PASS** — aucune clé ou credential détecté |
| Compilation Python et syntaxe shell | **PASS** |
| Backend pytest | **550 passed, 1 skipped** |
| Ruff | **PASS** |
| Typecheck TypeScript | **PASS** |
| Vitest frontend | **12 fichiers, 68 tests passés** |
| Build Vite | **PASS** — 2040 modules transformés |
| `pip-audit` | **PASS** — aucune vulnérabilité connue |
| `pnpm audit --prod` | **PASS** — aucune vulnérabilité connue |
| Compose config et build Docker | **PASS** |
| PostgreSQL/Redis/API/worker/beat/web | **PASS** — tous healthy |
| Alembic PostgreSQL | **PASS** — `20260822_mfa_secret_text (head)` |
| E2E HTTP/HTTPS staging | **PASS** — cookie Secure, rotation, rejeu, booking, isolation, logout |
| Smoke full-stack | **PASS** — login, MFA, patients, dossiers, agenda, facturation, stock, IA, logout |
| Probe escalade `super_admin` | **BLOCKED** — HTTP 403 |
| Probe matching WhatsApp inter-tenant | **BLOCKED** — aucun patient cross-tenant associé |
| Nginx exposure policy | **PASS** |
| Network boundary | **PASS** — gateway public 200, accès privé public bloqué, listener privé bloqué, accès authentifié autorisé |
| Backup/restore PostgreSQL | **PASS** — `patients=3 users=3 booking_requests=2` après restauration |
| Playwright enterprise + route smoke | **5 passed** |
| Intégration OpenAI-compatible applicative | **PASS** — prompt synthétique non médical, HTTP 200 |

## 5. Périmètre frontend réellement couvert

La qualification frontend n’est pas présentée comme un test manuel exhaustif écran par écran. Elle combine un smoke de toutes les routes identifiées, des tests Vitest et cinq parcours Playwright ciblés. Les interactions métier les plus critiques ont été exercées : authentification, rotation et révocation de session, MFA, isolation inter-clinique, fail-closed IA, réservation publique, consentement, approbation de booking, stock injectable, facturation et déconnexion.

| Couverture | Portée |
|---|---|
| Routes | Toutes les routes publiques et privées listées dans `e2e/route-smoke.spec.ts`, plus 404 |
| Authentification | Login, refresh cookie, logout, stockage mémoire du token |
| Sécurité métier | MFA, Clinic A/B IDOR, IA médicale fail-closed |
| Public gateway | Praticiens, actes, réservation, consentement et anti-réflexion d’injection |
| Cockpit métier | Patients, dossiers, agenda, facturation, stock, outils IA |
| Qualité d’affichage | Absence de 5xx et d’erreur JavaScript lors du parcours des routes |
| Limite déclarée | Pas de certification manuelle de chaque bouton et de chaque combinaison de formulaire |

## 6. Limites et actions avant production publique

Le fournisseur OpenAI-compatible validé est un endpoint de test configuré dans l’environnement d’audit. La production doit fournir sa propre clé, son propre endpoint si nécessaire, ses limites de budget et ses règles de conservation ; aucune clé de recette ne doit être réutilisée.

Les webhooks ont été vérifiés au niveau du proxy, des signatures, des limites et des chemins canoniques. Les appels contre les comptes réels de chaque fournisseur social ou omnicanal n’ont pas été revendiqués dans cette requalification. Ils doivent être exécutés en sandbox fournisseur avant ouverture publique.

Enfin, une revue humaine doit confirmer les rôles cliniques, le consentement, les durées de conservation, les sous-traitants IA, les procédures de rotation de secrets, la supervision et les objectifs de restauration. Ces points ne constituent pas un défaut reproductible de code découvert lors du gate, mais relèvent de la gouvernance de production.

## 7. Fichiers de preuve principaux

Les preuves nettoyées sont incluses dans le dossier `evidence/` de l’archive finale. Les journaux runtime canoniques sont également conservés à la racine de la copie de travail pour audit local.

| Fichier | Objet |
|---|---|
| `evidence/release_gate_final.txt` | Gate complet terminé par GO |
| `evidence/playwright_final_runtime.txt` | 5 tests Playwright passés |
| `evidence/full_stack_final.txt` | Smoke full-stack passé |
| `evidence/staging_e2e_https_final.txt` | E2E cookie Secure et isolation passés |
| `evidence/network_boundary_final.txt` | Boundary réseau passé |
| `evidence/nginx_exposure_final.txt` | Politique Nginx passée |
| `evidence/backup_restore_validation.log` | Preuve RESTORE PASS sanitizée |
| `evidence/ai_security_final.log` | Preuve IA synthétique sans secret |
| `evidence/security_probes_fixed.txt` | Probes P0 bloquées |
| `evidence/backend_full.txt` | Suite backend |
| `evidence/frontend_vitest.txt` | Suite Vitest |
| `evidence/frontend_typecheck.txt` | TypeScript |
| `evidence/frontend_build.txt` | Build Vite |
| `evidence/manifest.sha256` | Empreintes des fichiers livrés |

## 8. Conclusion

La v3 corrigée est **prête pour un déploiement contrôlé** avec un score de requalification de **94,0/100** et un gate technique entièrement vert. Les défauts P0 de la v2 sont fermés, le runtime production-like est opérationnel, la chaîne PostgreSQL/Redis/Celery/FastAPI/Nginx est validée et la sauvegarde-restauration a été démontrée.

Le propriétaire du projet peut donc passer à la préparation de production avec ses propres secrets, domaines, comptes fournisseurs et validations conformité. La release v2 originale demeure intacte et est fournie uniquement comme référence historique, jamais comme artefact modifié.

## Références de preuve

[1]: evidence/release_gate_final.txt "Gate de release final"
[2]: evidence/playwright_final_runtime.txt "Playwright enterprise et route smoke"
[3]: evidence/full_stack_final.txt "Smoke full-stack"
[4]: evidence/backup_restore_validation.log "Validation backup/restore"
[5]: evidence/network_boundary_final.txt "Test de frontière réseau"
[6]: evidence/nginx_exposure_final.txt "Contrôle d’exposition Nginx"
[7]: evidence/ai_security_final.log "Validation IA synthétique"
[8]: evidence/security_probes_fixed.txt "Probes de sécurité P0"
