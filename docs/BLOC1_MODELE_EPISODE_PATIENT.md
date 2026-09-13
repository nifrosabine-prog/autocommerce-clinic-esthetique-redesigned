# Bloc 1 — Modèle de données cible : cœur "Épisode patient"

Décision validée : **refonte du cœur** (`EpisodePatient` comme pivot dès le
départ), pas une extension incrémentale.

## Schéma relationnel (nouvelles tables)

```text
Patient 1───N Prospect (conversion, patient_id renseigné une fois)

Patient 1───N EpisodePatient
EpisodePatient N───1 RendezVous (rdv_origine_id, optionnel)
EpisodePatient 1───N Intervention          (1 par professionnel)
Intervention   N───1 Utilisateur (professionnel_id)
Intervention   1───N InterventionActe      (1 par acte proposé/réalisé)
InterventionActe N───1 ActeMedical (acte_id)         ← catalogue existant réutilisé

EpisodePatient 1───N Devis
Devis          1───N DevisLigne
DevisLigne     N───1 InterventionActe

Facture (existant) 1───N FactureLigne (nouveau)
FactureLigne   N───1 InterventionActe (optionnel, SET NULL)
Facture        1───N Paiement (nouveau — plusieurs paiements partiels)

EpisodePatient 1───N NotePrivee   (episode_id + intervention_id optionnel, auteur_id)
EpisodePatient 1───N NotePartagee (episode_id, auteur_id)

AgendaEvent    N───1 Utilisateur (professionnel_id, optionnel)
AgendaEvent    N───1 RendezVous  (rdv_id, optionnel — miroir)

AuditEvent     N───1 EpisodePatient (optionnel)
AuditEvent     N───1 Utilisateur (acteur_id, optionnel)
```

## La chaîne d'états d'un acte (le point central du Bloc 1)

```text
Acte proposé
  │  InterventionActe créé, accepte_medical=false, accepte_financier=false
  ▼
Accepté médicalement (accepte_medical=true, horodaté, auteur=médecin/pro)
  │
  ▼ (peut se produire avant ou après, indépendamment)
Accepté financièrement (accepte_financier=true, horodaté, auteur=assistante/patient)
  │
  ▼
Payé (paye=true, horodaté — via un ou plusieurs Paiement rattachés à la Facture)
  │
  ▼
Réalisé (realise=true, horodaté, auteur=professionnel)
  garde-fou base de données : impossible si accepte_medical=false
```

Chaque étape est un couple **booléen + horodatage + auteur** sur la même
ligne `InterventionActe`, pas un enum linéaire unique — parce que l'ordre
réel (accepté financièrement avant ou après la validation médicale finale)
dépend du protocole de chaque clinique, et qu'un acte payé en acompte peut
rester non réalisé pendant que d'autres actes du même épisode avancent
indépendamment.

## Statuts et transitions autorisées (résumé — code source dans `models/episode_core.py`)

| Entité | Statuts | Transitions |
|---|---|---|
| `Prospect` | nouveau, contacte, qualifie, converti, perdu | nouveau→contacte→qualifie→converti ; perdu relançable→nouveau |
| `EpisodePatient` | ouvert, en_cours, en_attente_paiement, cloture, annule | ouvert→en_cours→(en_attente_paiement⇄en_cours)→cloture ; annulable à tout moment sauf depuis cloture |
| `Intervention` | planifiee, en_cours, terminee, annulee | planifiee→en_cours→terminee ; annulable avant terminee |
| `Devis` | brouillon, envoye, accepte, refuse, expire | brouillon→envoye→(accepte\|refuse\|expire) ; refuse/expire→brouillon (nouvelle version) |
| `Paiement` | enregistre, annule, rembourse | pas de machine à états complexe — un paiement annulé/remboursé reste tracé, jamais supprimé |

Ces transitions sont définies comme données (`transitions_autorisees()` sur
chaque enum) pour que le service applicatif (Bloc 4) et un futur audit
puissent les vérifier programmatiquement, plutôt que rejouées en dur dans
chaque endpoint.

## Contraintes multi-clinique et suppressions logiques

- Toutes les nouvelles tables portent `clinic_id` (cohérent avec le reste
  du schéma).
- Aucun `DELETE` métier : `EpisodePatient`/`Intervention`/`InterventionActe`
  utilisent des statuts (`annule`, `refuse`) plutôt que la suppression —
  la facturation et l'historique médical doivent rester intègres même sur
  un épisode annulé.
- `ondelete="RESTRICT"` sur les FK vers `Patient`/`Utilisateur`/`ActeMedical`
  depuis les tables pivots (on ne doit jamais pouvoir supprimer un patient
  ou un praticien qui a un épisode/une intervention associée) ; `SET NULL`
  ou `CASCADE` réservés aux FK réellement secondaires (ex. `rdv_id` sur
  `AgendaEvent`).

## Ce qui n'est PAS dans ce lot (volontairement)

- **Migration des données existantes** (`DossierMedical`/`Facture` déjà en
  base vers des épisodes rétroactifs) : Bloc 13, avec son propre script
  réversible et son plan de validation — mélanger création de schéma et
  migration de données dans une seule opération aurait rendu un rollback
  partiel dangereux.
- **RoleEnum** (ajout masseuse/prestataire générique) : Bloc 2.
- **Services et endpoints** exploitant ces tables (transitions contrôlées,
  visibilité notes privées, masquage prix médecin) : Blocs 2 à 10.
- **Consolidation de l'audit** (3 tables existantes + `AuditEvent`) : Bloc 12.

## Fichiers de ce lot

- `api-server/models/episode_core.py` (nouveau) — 22 entités/enums cibles
  du Bloc 1, y compris `TypeIntervention`, `StatutProspect`,
  `StatutEpisode`, `StatutIntervention`, `StatutInterventionActe`,
  `StatutDevis`, `StatutPaiement`.
- `api-server/models/database.py` (édité) — `type_intervention` ajouté à
  `ActeMedical` ; relations `lignes`/`paiements` ajoutées à `Facture` pour
  le `back_populates` du nouveau module.
- `api-server/alembic/versions/20260907_episode_core.py` (nouveau) —
  migration additive (12 nouvelles tables + 1 colonne), 100% réversible,
  aucune donnée existante touchée.
- `api-server/alembic/env.py`, `api-server/local_validation_setup.py`
  (édités) — enregistrement du nouveau module pour qu'Alembic autogenerate
  et les tests locaux voient les nouvelles tables.

## Validation à faire côté toi (pas d'accès DB dans ce bac à sable)

```bash
alembic upgrade head        # doit s'arrêter sur 20260907_episode_core sans erreur
alembic downgrade -1        # doit revenir proprement à 20260904_team_audit
alembic upgrade head        # ré-applique sans erreur
```

Je n'ai pas pu exécuter ces commandes ici (pas de PostgreSQL ni de
`sqlalchemy` installables dans ce bac à sable) — la migration a été
relue ligne par ligne (FK, index, contraintes cohérents avec les modèles)
et le code Python vérifié par `py_compile`, mais pas exécuté contre une
vraie base.

---

## Ajustements post-revue (2026-09-08)

Revue reçue et appliquée intégralement avant d'attaquer le Bloc 2 :

1. **`Intervention.rdv_id`/`salle_id`** (+ `date_debut_prevue`/`date_fin_prevue`)
   ajoutés — un épisode peut regrouper plusieurs rendez-vous/salles
   (médecin en salle de consultation, esthéticienne en salle esthétique...).
   `EpisodePatient.rdv_origine_id` reste le rendez-vous d'accueil ; chaque
   intervention peut avoir le sien.

2. **`PaiementAffectation`** (nouvelle table) — répartit chaque `Paiement`
   sur une ou plusieurs `FactureLigne` précises (`montant_affecte`). Résout
   l'ambiguïté d'un paiement partiel sur une facture multi-actes : on sait
   désormais exactement quelle ligne (donc quel `InterventionActe`) est
   soldée. `InterventionActe.paye` reste un indicateur rapide, documenté
   comme dérivé des affectations, jamais comme source de vérité seule.

3. **Versionnage des devis** — `Devis.version`, `devis_parent_id` (racine
   commune), `remplace_devis_id` (version précédente). `StatutDevis.
   transitions_autorisees()` corrigé : `refuse`/`expire` sont désormais
   **terminaux** pour une ligne donnée — une nouvelle proposition crée une
   nouvelle ligne `Devis`, jamais un retour à `brouillon` sur la même ligne
   (qui aurait détruit la trace de ce que le patient a vu et refusé).

4. **`StatutEpisode.EN_ATTENTE_CONSENTEMENT`** ajouté, transitions
   élargies (`OUVERT` peut aller directement vers `EN_ATTENTE_PAIEMENT` ou
   `EN_ATTENTE_CONSENTEMENT`). La transition vers `CLOTURE` reste dans
   l'enum mais **n'est licite que si le service de clôture (Bloc 4)
   vérifie** : interventions obligatoires terminées, actes requis validés,
   consentements présents, facturation conforme, paiement conforme,
   documents/photos obligatoires complétés, événements indésirables
   traités, suivi post-séance créé si nécessaire. L'enum documente la
   transition possible, jamais sa légalité à elle seule.

5. **`StatutIntervention.A_VALIDER`** ajouté entre `EN_COURS` et
   `TERMINEE` : l'acte est fait mais compte-rendu/photos/produits restent
   à compléter avant clôture définitive. Retour `A_VALIDER → EN_COURS`
   autorisé si un complément est nécessaire.

6. **Notes protégées** — `NotePrivee`/`NotePartagee` : FK `episode_id`/
   `intervention_id` passées de `CASCADE` à `RESTRICT` (une suppression
   forcée d'épisode ne peut plus emporter silencieusement les notes), et
   `archived_at`/`archived_by_id` ajoutés pour un retrait sans suppression
   physique, cohérent avec la règle d'historisation du reste du schéma.

7. **Rôle générique `PRESTATAIRE`** ajouté à `RoleEnum` (`models/
   database.py`) plutôt qu'un rôle rigide `MASSEUSE`. Aucune nouvelle table
   nécessaire : `Utilisateur.specialite` (déjà existant, texte libre) porte
   le métier réel, et `Utilisateur.actes_pratiques` (déjà existant, table
   d'association `utilisateurs_actes`) porte les actes autorisés. Le
   libellé affiché ("Masseuse", "Prestataire"...) se dérive de
   `specialite` côté frontend, jamais en dur sur le rôle backend.

### Fichiers ajoutés/modifiés dans ce lot d'ajustements

- `api-server/models/episode_core.py` (édité — points 1 à 6)
- `api-server/models/database.py` (édité — `RoleEnum.PRESTATAIRE`)
- `api-server/alembic/versions/20260908_episode_core_adjustments.py`
  (nouveau — migration additive chaînée sur `20260907_episode_core`)

### Point d'attention pour l'exécution réelle

La migration 2 suppose que Postgres a nommé les FK `CASCADE` créées par la
migration 1 selon sa convention par défaut (`notes_privees_episode_id_fkey`,
etc.). À vérifier avant exécution en prod si l'environnement diffère :
```sql
SELECT conname FROM pg_constraint WHERE conrelid = 'notes_privees'::regclass;
```

---

## Réponse à la revue v2 (2026-09-09)

### 1. Correction bloquante — import runtime de `episode_core`

`models/__init__.py` était vide : les modèles `episode_core` n'étaient
chargés que via `alembic/env.py` ou `local_validation_setup.py`, jamais
garantis au démarrage réel de l'API. **Corrigé** : `models/__init__.py`
importe maintenant explicitement `database` (en premier, les autres en
dépendent) puis `omnicanal`, `security`, `workflow_engine`, `episode_core`.
Tout `from models.database import ...` ou `import models` déclenche
désormais l'enregistrement complet des mappers (comportement standard
d'exécution d'un `__init__.py` de package Python).

### 7. Portée `clinic_id` des tables enfants — Option A retenue

`DevisLigne`, `FactureLigne`, `PaiementAffectation` n'ont volontairement
pas leur propre `clinic_id` — la portée se lit via leur parent
(`.devis.clinic_id`, `.facture.clinic_id`, `.paiement.clinic_id`).
Documenté explicitement dans le docstring de chacune des 3 classes et
dans l'en-tête du module (qui affirmait à tort que "toutes" les tables
étaient scopées). **Obligation pour le Bloc 4** : tout service qui
interroge ces tables doit filtrer par jointure sur le parent, jamais par
un scan isolé.

### 9. Tests ajoutés

`tests/test_episode_core_bloc1.py` — 10 tests couvrant : enregistrement
runtime des tables, épisode multi-intervention multi-professionnel
(ajustement 1), garde-fou DB `realise ⇒ accepte_medical`, répartition
d'un paiement sur plusieurs lignes + contrainte d'unicité
(ajustement 2), versionnage de devis avec transitions terminales
(ajustement 3), transitions `EN_ATTENTE_CONSENTEMENT` et `A_VALIDER`
(ajustements 4-5), archivage de note sans suppression physique
(ajustement 6), rôle `PRESTATAIRE` + `specialite` (ajustement 7),
conversion Prospect→Patient avec contrainte de cohérence.

### 2, 3, 4, 5, 6, 8 — accusé de réception, pas d'action ce lot

Points 2 à 6 : la structure est validée telle quelle par la revue, les
recommandations concernent l'implémentation du **service** (Bloc 4), pas
le modèle — notées pour ne pas être oubliées à ce moment-là (résumé
repris ci-dessus dans les docstrings pertinents : `InterventionActe.paye`,
`Paiement`/`PaiementAffectation`).

Point 8 (exécution réelle sur PostgreSQL, y compris la vérification des
noms de contraintes générés) : **toujours non faite** — aucun accès
PostgreSQL dans ce bac à sable. Reste à exécuter côté toi avant mise en
recette :
```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

### Fichiers ajoutés/modifiés dans ce lot

- `api-server/models/__init__.py` (corrigé — était vide)
- `api-server/models/episode_core.py` (édité — docstrings clinic_id)
- `api-server/tests/test_episode_core_bloc1.py` (nouveau)


## Corrections finales appliquées le 2026-09-09

La migration `20260909_episode_clinical_links` complète les rattachements du
Bloc 1 sans modifier les données historiques existantes. Les colonnes sont
nullable pour permettre une migration de données progressive ; les nouveaux
services doivent renseigner la portée dès la création.

Les entités suivantes portent désormais `episode_id` et `intervention_id`
(lorsque l’intervention est connue) :

- `PhotoClinic` ;
- `Consentement` ;
- `SimulationIA` ;
- `UtilisationLot` ;
- `SuiviPostActe`, qui constitue l’implémentation persistante de
  `SuiviPostSeance`.

`ActeMedical` est officiellement l’implémentation du catalogue partagé cible
`ActeCatalogue` ; l’alias Python `ActeCatalogue` est exposé sans créer une
seconde table ni casser les clés étrangères existantes.

La validation PostgreSQL à effectuer depuis un environnement disposant des
dépendances et d’une base de test est désormais :

```bash
alembic upgrade head
alembic downgrade -1   # revient à 20260908_episode_core_adjustments
alembic upgrade head
alembic downgrade -4   # revient à 20260904_team_audit
alembic upgrade head
pytest -q tests/test_episode_core_bloc1.py
```

La migration finale est réversible et utilise des noms explicites pour toutes
les nouvelles contraintes étrangères.
