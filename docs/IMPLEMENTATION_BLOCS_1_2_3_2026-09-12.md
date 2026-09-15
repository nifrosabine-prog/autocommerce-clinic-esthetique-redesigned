# AutoCommerce Clinic — Livraison des blocs 1, 2 et 3

**Date :** 12 septembre 2026  
**Statut :** implanté, compilé, testé et archivé.

## Bloc 3 livré

### Réception des candidatures en ligne

Le parcours public `/candidature` du bloc 2 est conservé et renforcé comme point de réception en ligne. Il accepte les candidatures pour les postes ouverts, vérifie le poste côté serveur, limite le CV à 10 Mo, autorise uniquement PDF/DOC/DOCX et conserve l’isolement par clinique. Le pipeline RH interne reçoit la candidature sans créer de compte clinique pour le candidat.

### Absence d’un praticien et réaffectation

Une déclaration d’absence est disponible depuis l’accueil des patients et via l’API `/api/private/agenda/absences-praticiens`. Le système recherche les rendez-vous impactés, ignore les rendez-vous annulés ou no-show, vérifie les conflits des autres praticiens actifs et crée des propositions traçables. La réaffectation ne modifie jamais silencieusement un rendez-vous : l’assistante, la directrice ou l’administrateur doit valider la proposition via `/agenda/absences-praticiens/{absence_id}/reaffectations/{reaffectation_id}/valider`.

### Cascade après annulation

Après une annulation confirmée, le système recherche jusqu’à trois créneaux futurs compatibles, à la même heure sur les semaines suivantes, après contrôle de disponibilité du praticien. Les propositions sont stockées dans `suggestions_remplacement_rdv` et restent en attente de validation. La validation crée un nouveau rendez-vous avec `source=remplacement` et `remplace_rdv_id` pointant vers le rendez-vous annulé ; l’ancien rendez-vous et son historique sont conservés.

### Publication sociale planifiée

La publication sociale planifiée conserve la validation humaine existante : un post n’est publié automatiquement que lorsqu’il est enregistré avec le statut `planifie` et une date future. Une tâche Celery vérifie toutes les cinq minutes les posts arrivés à échéance, tente la publication via le connecteur configuré et marque honnêtement les plateformes non connectées en échec. Aucun faux succès n’est produit pour Instagram, Facebook ou TikTok sans connecteur réel.

## Modifications principales

| Domaine | Fichiers principaux |
|---|---|
| Absences et réaffectations | `models/database.py`, `api/v1/absences_praticiens.py`, `services/remplacement_rdv.py` |
| Cascade d’annulation | `api/v1/agenda_clinic.py`, `api/v1/remplacements_rdv.py` |
| Publication planifiée | `services/celery_app.py` |
| Interface | `client/src/pages/accueil/AccueilPatients.tsx` |
| Schéma | `alembic/versions/20260912_bloc3_absences_praticiens.py` |

## Vérifications

| Contrôle | Résultat |
|---|---:|
| Compilation Python | PASS |
| Import des nouveaux modèles et routeurs | PASS |
| Suite backend complète | **742 réussis, 1 ignoré** |
| Contrôle TypeScript `pnpm check` | PASS |
| Tests frontend `pnpm test --run` | PASS |
| Build frontend | PASS |
| Migration Alembic ajoutée | PASS — nouvelle tête `20260912_bloc3_absences_praticiens` |
| Archive ZIP | PASS — testée avec `unzip -tq` |

## Réserves de production

Les connexions Instagram, Facebook et TikTok restent dépendantes de leurs clés et autorisations développeur respectives. La tâche Celery doit être active en production pour exécuter les publications planifiées. Les créneaux proposés après annulation sont des suggestions déterministes contrôlées par disponibilité ; ils ne constituent pas une décision médicale et ne sont jamais envoyés au patient sans validation de l’équipe.
