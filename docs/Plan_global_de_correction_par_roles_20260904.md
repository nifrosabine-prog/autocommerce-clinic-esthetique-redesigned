# Plan global de correction par rôles — AutoCommerce Clinic

**Version 2026-09-04 — revue et corrections appliquées**

Ce document remplace le relevé d'audit précédent et distingue les défauts
reproduits dans le code des décisions métier restant à confirmer.

## Synthèse par priorité

| Priorité | Sujet | État |
| --- | --- | --- |
| P0 | Réactivation : timeout client, anti-double-clic, remontée des erreurs et test de parcours | Corrigé |
| P1 | Masquage des données médicales pour l'esthéticienne | Corrigé |
| P1 | Protection du dernier compte dirigeant actif | Corrigé |
| P1 | Audit des actions de gestion d'équipe | Corrigé |
| P1 | Suppression logique et anonymisation des comptes | Corrigé |
| P1 | Consentements signés | Revue : aucune route de modification exposée |
| P2 | Terminologie Commercial / Commissions | Corrigé dans l'interface et la documentation |
| P2 | Cohérence devise et libellés | Corrigé |
| P3 | Tests par rôle, isolation et révocation | Tests ciblés ajoutés ; suite complète à exécuter en CI |

## Constats et corrections

### 1. Comptes et activation

Le client Axios utilise désormais un délai maximal de 15 secondes. L'interface
verrouille l'action d'activation ou de désactivation pendant le PATCH et affiche
un message explicite en cas de dépassement de délai. Le serveur continue de
retourner le conflit `409` pour un email déjà utilisé.

Le délai observé d'environ 45 secondes n'est pas reproductible dans le code de
l'endpoint. Il est donc classé **origine infrastructure** (proxy, pool de
connexions ou base de données). Le P0 porte sur le timeout client,
l'anti-double-clic et les tests, avec mesure de la durée du PATCH dans les logs
d'exécution.

### 2. Sécurité médicale et rôles

- Une esthéticienne peut conserver les champs esthétiques utiles
  (`zones_traitees`, `produits_utilises`, `satisfaction`) mais voit
  `observations` et `effets_secondaires` masqués.
- Une directrice conserve la lecture administrative masquée. Le médecin et
  l'administrateur technique conservent l'accès complet prévu par la matrice.
- Une clinique ne peut plus créer un compte `ADMIN` depuis la gestion d'équipe.
- Une clinique ne peut pas désactiver, changer de rôle ou supprimer le dernier
  compte actif d'un rôle dirigeant (`directrice` ou `admin`).

### 3. Équipe, audit et suppression

Les créations, modifications, activations/désactivations et suppressions
logiques écrivent dans `audit_logs_team`. Chaque entrée porte la clinique,
l'utilisateur concerné, l'acteur, l'action, les valeurs avant/après et la date.
`GET /api/v1/users/audit-logs` est réservé à la direction et à l'administrateur.

La suppression d'un membre est logique : les relations cliniques et la
traçabilité sont conservées, les identifiants sont anonymisés et le compte est
désactivé. Le mot de passe n'est jamais placé dans le journal.

La revue des routes de consentement confirme qu'aucune opération de modification
après signature n'est exposée ; les routes de consultation et de liste restent
disponibles aux rôles prévus.

### 4. Commercial et Commissions

**Commercial** désigne le rôle utilisateur. **Commissions** désigne le module
de suivi financier. Les deux niveaux de validation sont exposés par l'API et
l'interface distingue désormais « Validée », « Double-validée » et « Payée ».

Le comportement des demandes de réservation reste inchangé et documenté :
elles restent accessibles à la direction, à l'assistante et à
l'administrateur ; le Commercial n'est pas ajouté sans décision métier signée.

### 5. Routes, devises et libellés

- La route `/team` n'existe pas dans l'application. Le menu pointe déjà vers
  `/admin/equipe`; aucune redirection artificielle n'est ajoutée.
- Le formatage des montants des factures, commissions et données multi-devises
  passe par `formatMoney`, avec symbole et trois décimales. Le défaut des
  valeurs concaténées est marqué comme **déjà résolu** par
  `client/src/lib/currency.ts` et la migration
  `api-server/alembic/versions/20260902_facture_currency.py`.
- L'affichage français emploie « Médecin » pour le rôle concerné. Les noms
  techniques des endpoints et champs API restent inchangés pour préserver le
  contrat existant.
- La gestion d'équipe continue d'utiliser `GET /users`, qui inclut les comptes
  inactifs afin de permettre leur réactivation.

## Vérifications attendues avant livraison

```text
pytest api-server/tests/ -q
pnpm --dir autocommerce-app check
pnpm --dir autocommerce-app test
pnpm --dir autocommerce-app build
```

Le contrat `current_user` reste `{id, role, clinic_id, email, is_active}` et
la règle de livraison demeure : rien ne se teste avec un compte inactif, rien ne
se livre sans test.

## Mise à jour P0-1 — appliquée (2026-09-04)

- `middleware/request_timing.py` (nouveau) : chaque requête HTTP est
  chronométrée ; durée >= 5 s ou statut >= 400 journalisés en WARNING
  (logger `api.timing`), sinon DEBUG. Objectif : objectiver la cause racine
  des ~45 s observés lors de l'audit.
- `models/database.py` : pool SQLAlchemy durci pour PostgreSQL
  (`pool_pre_ping`, `DB_POOL_SIZE=5`, `DB_MAX_OVERFLOW=10`,
  `DB_POOL_TIMEOUT=5 s`, `DB_POOL_RECYCLE=1800 s`, timeouts asyncpg
  15 s / 30 s). Les moteurs non-PostgreSQL (sqlite) sont inchangés.
- `api/v1/users.py` : le `PATCH /users/{id}` journalise `duration_ms` en
  succès (déjà présent), sur `IntegrityError` (déjà présent) et sur toute
  erreur inattendue (nouveau, avec `exc_info`).
- `scripts/activate_recipe_accounts.py` (nouveau) : active un compte de
  recette EXISTANT par rôle via `UPDATE utilisateurs SET is_active = true`
  (idempotent, aucun doublon), réinitialise le mot de passe si
  `ACTIVATE_RECIPE_PASSWORD` est défini, et signale les comptes encore
  manquants.
- `tests/test_team_activation_timing.py` (nouveau) : seuil de lenteur,
  normalisation asyncpg, durcissement du pool, liste des comptes de recette,
  bascule de driver du script.

Reste opérationnel (hors archive) : exécuter le script sur l'environnement
 déployé pour chaque rôle, vérifier la réactivation < 5 s (écriture
 `audit_logs_team` action `activation`), puis lancer la suite complète en CI
 (`pytest`, `pnpm check/test/build`).

## Mise à jour livraison finale (2026-09-04) — statut P0-1, P1-1, P1-2, P2-1

| Point | Résultat | Statut |
| --- | --- | --- |
| P0-1 — Instrumentation durée du PATCH | `duration_ms` journalisé en succès (`team_user_update`) et sur `IntegrityError` comme sur toute erreur inattendue ; middleware `request_timing.py` branché dans `main.py` (`add_middleware(RequestTimingMiddleware)`) | Code fait — mesure < 5 s sur l'environnement déployé : opérationnel, hors archive |
| P0-1 — Pool SQLAlchemy | Durci (`pool_pre_ping`, taille/overflow/timeout/recycle bornés, timeouts asyncpg 15 s / 30 s) | Fait |
| P0-1 — Réactivation par rôle | Script `scripts/activate_recipe_accounts.py` livré (idempotent, sans doublon) ; exécution requise sur l'environnement déployé pour les 4 rôles | Opérationnel — non vérifiable ici (pas d'accès à l'environnement déployé) |
| P1-1 — Erreur + « Réessayer » | Ajouté sur les 3 pages : `StockPage.tsx`, `InvoicesPage.tsx`, `CommissionsPage.tsx` (état d'erreur visible + bouton relançant la requête, plus d'UI bloquée en chargement) ; validé par `pnpm check` et `pnpm build` | Fait |
| P1-2 — Rôle Commercial vs réservations | Décision métier **non signée** : périmètre actuel verrouillé — le Commercial reste exclu des demandes de réservation (GET/approve/reject limités à directrice/assistante/admin) ; RBAC inchangé ; `test_booking_requests.py` et `test_clinic_rbac.py` verts | Décision ouverte (doit être écrite et signée avant tout élargissement) |
| P2-1 — Suite complète | `pytest`: 619 passed / 1 skipped ; `pnpm check`: 0 erreur ; `pnpm test`: 73 passed ; `pnpm build`: OK ; workflow CI `.github/workflows/ci.yml` ajouté (jobs backend + frontend) | Fait |

Corrections de tests au passage (l'archive d'origine contenait deux tests
incohérents avec le code de référence livré) :

- `tests/test_security_regressions.py::test_clinic_roles_remain_assignable` :
  incluait `ADMIN` parmi les rôles attribuables depuis une clinique, alors que
  le périmètre interdit la création d'un compte admin — aligné sur la règle
  (« une clinique ne peut pas créer un compte ADMIN ») et ajout d'un test
  dédié `test_clinic_cannot_assign_admin_role` (403 attendu).
- `tests/test_team_activation_timing.py::test_pool_hardening_applied_on_postgres_engine` :
  assertion trop stricte sur la taille interne de la file SQLAlchemy, qui
  varie selon la version — rendue tolérante (`pool_size` ou `pool_size + overflow`).