# Bloc 1 — Correction finale du modèle épisode patient

## Statut

Le cœur du Bloc 1 a été corrigé afin que les objets cliniques existants puissent être rattachés explicitement à l’épisode patient et, lorsque nécessaire, à l’intervention professionnelle.

## Corrections livrées

La migration `20260909_episode_clinical_links` ajoute des colonnes nullable et des contraintes nommées à :

- `photos_clinic` : `episode_id`, `intervention_id` ;
- `consentements` : `episode_id`, `intervention_id` ;
- `utilisations_lot` : `episode_id`, `intervention_id` ;
- `simulations_ia` : `episode_id`, `intervention_id` ;
- `suivis_post_acte` : `episode_id`, `intervention_id`.

Les champs sont nullable pour préserver les données historiques. Les nouveaux enregistrements doivent toutefois être créés avec leur portée épisode/intervention dès que celle-ci est connue.

`ActeMedical` est exposé sous l’alias `ActeCatalogue`, car il constitue déjà le catalogue partagé référencé par les rendez-vous, dossiers et consentements existants. Aucune seconde table catalogue n’est créée.

Les relations SQLAlchemy correspondantes ont été ajoutées sur `EpisodePatient` et `Intervention`. Un test de régression vérifie la présence des colonnes et l’enregistrement du catalogue.

## Migration et rollback

La chaîne finale est :

```text
20260904_team_audit
→ 20260907_episode_core
→ 20260908_episode_core_adjustments
→ 20260909_episode_clinical_links
```

La migration finale utilise uniquement des noms de contraintes explicites et son `downgrade()` supprime les index, contraintes et colonnes dans l’ordre inverse.

Validation PostgreSQL recommandée :

```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head
alembic downgrade -4
alembic upgrade head
pytest -q tests/test_episode_core_bloc1.py
```

Le premier `downgrade -1` revient à `20260908_episode_core_adjustments`. Depuis la tête finale, quatre révisions sont nécessaires pour revenir à `20260904_team_audit`.
