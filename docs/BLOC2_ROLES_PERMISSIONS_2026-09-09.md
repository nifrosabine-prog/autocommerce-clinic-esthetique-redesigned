# Bloc 2 — Rôles et permissions (livraison corrigée)

Date : 2026-09-09
Base : `AutoCommerce-Clinic-BLOC1-EPISODE-CORE-v4-corrige.zip`

## Périmètre (extrait du cahier des charges)

- Rôles minimum : admin technique, direction, assistante, médecin, esthéticienne, masseuse / prestataire.
- **Un rôle technique ne possède pas automatiquement l'accès aux données médicales.**
- Permissions vérifiées **côté backend** ; le frontend n'est qu'une aide d'interface.
- Le médecin peut **afficher/masquer** les prix mais ne peut pas les modifier ; l'assistante gère la validation financière et le paiement selon ses droits ; l'esthéticienne et la masseuse ne voient que les données nécessaires à leur intervention.
- Actions interdites → erreur backend explicite ; accès dépendant de la clinique et, si nécessaire, de l'intervention affectée ; tests de permissions par rôle.

## Défauts corrigés par rapport à la livraison v4 (bloc 1)

1. **Accès médical de l'admin technique non restreint** : la matrice v4 donnait `admin → dossiers_medicaux : read/write/delete` et `photos : read/write/delete`. Corrigé : `photos` et `notes_privees` refusés par défaut, `dossiers_medicaux` en **lecture technique auditée uniquement** (les contenus sont chiffrés Fernet : l'admin lit des lignes chiffrées, jamais le contenu déchiffré).
2. **Rôle prestataire présent mais inutilisable** : l'enum `PRESTATAIRE` existait (masseuse, drainage, épilation…) mais n'était pas assignable depuis une clinique (`CLINIC_ASSIGNABLE_ROLES` l'ignorait) et n'avait aucune entrée dans la matrice (refus partout). Corrigé : assignable via `/users`, matrice complète, tests.
3. **Pas de couche de permissions resource+action pour les routes** : seule `require_role` existait. Ajout de `require_permission(resource, action)`, du mapping `BLOC2_ACTIONS` et du service `services/rbac_service.py` (portée clinique, portée d'intervention, filtrage des notes privées, politique prix).
4. **Politique des prix non distincte** : ajout de `can_view_prices` / `can_edit_prices` / `price_policy` (le médecin affiche, ne modifie jamais).
5. **Aucune API de permissions pour l'interface** : ajout de `/rbac/me`, `/rbac/matrix`, `/rbac/check` (à but d'interface uniquement — la sécurité reste backend).
6. **Aucune migration d'alignement** : ajout de `alembic/versions/bloc2_prestataire_role.py` (comptes hérités `masseuse` → `prestataire`, rollback documenté).

## Fichiers livrés (Bloc 2)

| Fichier | Rôle |
|---|---|
| `api-server/middleware/clinic_rbac.py` | Matrice stricte (8 rôles × 17 ressources), `require_role` (compat), `require_permission`, `check_bloc2_action`, helpers prix / notes |
| `api-server/services/rbac_service.py` | Règles métier : contexte clinique obligatoire, intervention affectée, filtrage notes privées, politique prix, résumé de permissions |
| `api-server/api/v1/rbac.py` | Routes `/rbac/me`, `/rbac/matrix`, `/rbac/check` |
| `api-server/api/v1/__init__.py` | Montage du routeur `rbac` (privé + rétrocompat `/api/v1`) |
| `api-server/api/v1/users.py` | `PRESTATAIRE` ajouté aux rôles assignables en clinique |
| `api-server/alembic/versions/bloc2_prestataire_role.py` | Migration d'alignement `masseuse` → `prestataire` (up/down) |
| `api-server/tests/test_bloc2_rbac.py` | Nouveaux tests Bloc 2 (~25 tests, rôles × actions exhaustifs) |
| `api-server/tests/test_clinic_rbac.py` | Mise à jour du test admin (suppression médicale interdite) |
| `docs/BLOC2_ROLES_PERMISSIONS_2026-09-09.md` | Ce document |

## Matrice (rôle → droits marquants)

| Ressource | Directrice | Médecin | Esthéticienne | Assistante | Commercial | Admin (tech) | Prestataire |
|---|---|---|---|---|---|---|---|
| patients | R/W/D | R/W | R/W | R/W | R | R/W/D | R |
| dossiers_medicaux | R | R/W | R/W (pas antécédents) | — | — | R (audité, chiffré) | — |
| photos | — | R/W/D | R/W | — | — | — | — |
| notes_privees | R | R/W | R/W (ses notes) | — | — | — | R/W (ses notes) |
| notes_partagees | R/W | R/W | R/W | R | — | R | R/W |
| interventions | R/create/validate | R/create/start/validate | idem (siennes) | R | — | R | idem (siennes) |
| prix (affichage) | R/W | **R** (jamais W) | — | R/W | — | R/W | — |
| remise | apply | — | — | apply | — | apply | — |
| devis / validation financière | validate/convertir | R | R | **validate/convertir** | — | R/W | — |
| paiements | enregistrer | — | — | enregistrer | — | enregistrer | — |
| actes | R/W | proposer | proposer (habilitations) | R | — | R/W | proposer (habilitations) |
| épisodes / clôture | cloturer | cloturer | R | R | — | R | R |
| lots | utiliser | utiliser | utiliser | R | — | utiliser | utiliser |
| simulation IA | run | run | R | — | — | run | — |

## Routes ajoutées

```
GET /api/v1/rbac/me        → résumé des permissions du rôle connecté (interface)
GET /api/v1/rbac/matrix    → matrice complète (directrice / admin / super_admin)
GET /api/v1/rbac/check     → vérification unitaire ?resource=&action=
```

## Tests

```bash
cd api-server && pytest tests/test_bloc2_rbac.py tests/test_clinic_rbac.py -q
```

Le fichier `test_bloc2_rbac.py` énumère **exhaustivement** les rôles attendus
pour chacune des 19 actions nommées du Bloc 2 (échec si un seul rôle diverge),
et couvre : admin sans accès médical automatique, notes privées jamais exposées
aux rôles non autorisés, médecin affiche-sans-modifier, prestataire limité à
son intervention, erreurs backend explicites (403), contexte clinique
multi-clinique.

## Migration et rollback

```bash
alembic upgrade head        # applique bloc2_prestataire_role
alembic downgrade bloc2_prestataire_role   # rollback : prestataires → assistante
```

## Hypothèses actées

- L'admin technique garde la **lecture technique auditée** des dossiers
  médicaux **chiffrés** (support technique sans exposition de données
  déchiffrées) ; photos et notes privées lui sont refusées.
- « Prestataire » couvre la masseuse et toute profession non dédiée ; le
  libellé métier reste porté par `Utilisateur.specialite` (aucune nouvelle
  table — principe déjà acté en Bloc 1).
- La direction reste un rôle métier encadré (lecture médicale seule, pas de
  modification des données médicales), distinct de l'admin technique.
- Aucun contrat d'API existant n'est rompu : `require_role` est conservé à
  l'identique pour les routes historiques ; les nouvelles vérifications sont
  additives (`require_permission`, service). Les contrôles frontend restent
  une aide d'interface — la décision de sécurité est toujours backend.
