# Bloc 3 — Agenda, réservations, CRM (prospects) et accueil patient

Date : 2026-09-09
Base : `AutoCommerce-Clinic-BLOC2-RBAC-v4-corrige.zip` (Bloc 2 livré)

## Périmètre (extrait du cahier des charges)

- Réservation **Internet**, **WhatsApp**, **téléphone**, **manuel** — un modèle unique de rendez-vous (seule la `source` diffère).
- Patient existant vs **nouveau prospect** ; **détection de doublons** (téléphone, nom+prénom, email).
- Parcours d'arrivée : **patient arrivé → présence confirmée → accord pour être reçu/examiné** (l'accord ouvre l'épisode patient).
- **Absence** (historique conservé), **report**, **annulation**, **remplacement par un nouveau patient**.
- **Ne jamais supprimer un ancien rendez-vous** : toute modification importante crée un événement d'agenda avec ancienne valeur, nouvelle valeur, auteur, date et motif.
- À chaque création/modification : mise à jour du **CRM**, de la **timeline patient**, de l'**épisode patient**, des espaces des professionnels et des **tâches de l'assistante**.
- **Page « Accueil des patients »** : recherche par nom, téléphone, référence, rendez-vous et source.

## Défauts d'écart constatés sur la base (et traités ici)

1. **Pas de notion de source ni de référence sur un rendez-vous** : colonnes `rendez_vous.source`, `rendez_vous.reference`, `rendez_vous.remplace_rdv_id` ajoutées (migration `bloc3_rdv_parcours_arrivee`).
2. **Pas de statuts d'arrivée** (`arrive`, `accord`) : ajoutés à `StatutRDV` (l'absence restant `no_show`, conformément au modèle existant).
3. **Pas de journal d'agenda** : table `rdv_evenements` (ancienne valeur / nouvelle valeur / auteur / motif / date) + modèle `RdvEvenement`.
4. **Aucune API d'accueil unique** : nouveau routeur `accueil` (`/accueil/*`) qui orchestre réservation, CRM, épisode et tâches.
5. **CRM prospect (Bloc 1) non branché sur l'arrivée** : `upsert_prospect_crm` relie désormais tout nouveau RDV au prospect (statut `qualifie` quand le patient existe, `nouveau` sinon) + endpoint de détection de doublons.

## Fichiers livrés

| Fichier | Rôle |
|---|---|
| `api-server/models/database.py` | `StatutRDV.ARRIVE/ACCORD` ; colonnes `RendezVous.source/reference/remplace_rdv_id` |
| `api-server/models/episode_core.py` | Modèle `RdvEvenement` (journal d'agenda) |
| `api-server/alembic/versions/bloc3_rdv_parcours_arrivee.py` | Migration additif (colonnes + table + index), enchaînée sur `bloc2_prestataire_role` |
| `api-server/services/parcours_arrivee.py` | Orchestration : réservation unifiée (4 sources), doublons, flux d'arrivée, absence, remplacement, journal, tâches, prospect CRM, listing accueil |
| `api-server/api/v1/accueil.py` | Routeur `/accueil` (page Accueil des patients + actions d'arrivée) |
| `api-server/api/v1/__init__.py` | Montage du routeur `accueil` (privé + rétrocompat `/api/v1`) |
| `api-server/tests/test_bloc3_accueil.py` | Tests Bloc 3 (10 tests, critères d'acceptation) |
| `docs/BLOC3_AGENDA_ACCUEIL_2026-09-09.md` | Ce document |

## Routes ajoutées

```
GET  /api/v1/accueil?q=&source=&date_debut=&date_fin=   → liste accueil (nom, tél., référence, id RDV, source)
POST /api/v1/accueil/reservations                       → réservation unifiée (internet|whatsapp|telephone|manuel)
GET  /api/v1/accueil/doublons?telephone=&nom=&prenom=&email=
POST /api/v1/accueil/rdv/{id}/arrivee                   → patient arrivé (statut arrive)
POST /api/v1/accueil/rdv/{id}/presence                  → présence confirmée (statut confirme)
POST /api/v1/accueil/rdv/{id}/accord                    → accord d'examen + ouverture épisode (statut accord)
POST /api/v1/accueil/rdv/{id}/absence                   → no_show (motif obligatoire, historique conservé)
POST /api/v1/accueil/rdv/{id}/remplacement              → nouveau RDV (l'ancien n'est jamais écrasé)
GET  /api/v1/accueil/rdv/{id}/evenements                → journal complet (ancienne/nouvelle valeur, auteur, date, motif)
```

## Règles métier implémentées

- **Modèle unique pour toutes les sources** : Internet, WhatsApp, téléphone et manuel passent par `creer_rdv_complet` ; seule `RendezVous.source` diffère (les critères d'acceptation « RDV Internet visible agenda+CRM » et « WhatsApp même modèle que manuel » sont testés).
- **Absence** : statut `no_show` (jamais de DELETE), motif conservé dans `notes_post_acte` et journalisé.
- **Remplacement** : possible uniquement après `no_show` ; crée un rendez-vous avec `remplace_rdv_id → ancien` ; même créneau/praticien/acte ; l'ancien reste `no_show` avec son historique complet.
- **Épisode patient** : l'accord d'examen réutilise l'épisode non clos du patient ou en ouvre un nouveau avec `rdv_origine_id` (l'épisode naît de l'accueil).
- **CRM** : le prospect est retrouvé/créé par téléphone (doublon) puis relié au patient ; la recherche de doublons couvre patients et prospects.
- **Tâches assistante** : création systématique d'une `TacheInterneAssistant` « Accueil patient … » avec créneau, salle et source.
- **Journal** : `creation`, `arrivee`, `presence_confirmee`, `accord_examen`, `absence`, `remplacement`, `annulation`, `report`, `modification_statut` — chaque événement enregistre ancienne valeur, nouvelle valeur, auteur, date et motif.

## Tests

```bash
cd api-server && pytest tests/test_bloc3_accueil.py -q
```

Les 10 tests couvrent : RDV Internet visible agenda+CRM (prospect + tâche), RDV WhatsApp = même modèle que manuel, flux arrivée→présence→accord→épisode (et précondition de la présence), absence avec historique conservé, remplacement sans écrasement (et précondition), journalisation avec ancienne/nouvelle valeur, détection de doublons (téléphone, nom+prénom), référence stable.

## Migration et rollback

```bash
alembic upgrade head        # applique bloc3_rdv_parcours_arrivee
alembic downgrade bloc3_rdv_parcours_arrivee   # rollback : colonnes + table retirées, RDV inchangés
```

## Hypothèses actées

- Le statut « report » est matérialisé par une modification (replanification existante `PATCH /agenda/rdv/{id}/replanifier`) ; un événement `report` sera journalisé lors du Bloc 8 qui fiabilisera les transitions. Les transitions d'arrivée sont déjà contrôlées côté backend (préconditions explicites → 409).
- La timeline patient complète sera agrégée au Bloc 10 (notes) ; l'accueil alimente déjà la source primaire (événements d'agenda).
- Les espaces de travail des professionnels (workspace) sont du ressort du Bloc 4 ; l'agenda liste déjà les RDV par praticien (périmètre auto pour médecin/estéticienne).
- WhatsApp reste un canal d'entrée (source `whatsapp`) typé par l'existant `BookingRequest.source` ; l'expédition de messages continue via `services/whatsapp_service.py`.
