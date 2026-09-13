# Test de concurrence — double tentative de replanification

**Date :** 13 septembre 2026
**Scénario :** deux confirmations simultanées pour le même rendez-vous initial absent

## Défaut initial reproduit

Avant correction, deux transactions concurrentes réussissaient simultanément et créaient les rendez-vous `#9` et `#10` sur le même créneau, tous deux reliés au même rendez-vous initial. Il s’agissait d’une condition de course réelle.

## Correction

Le rendez-vous initial est maintenant verrouillé avec `SELECT ... FOR UPDATE` pendant la confirmation. Une contrainte d’unicité PostgreSQL `uq_rendez_vous_remplace_rdv_id` garantit également qu’un rendez-vous initial ne peut avoir qu’un seul remplacement actif. La contrainte ne porte pas sur la date, le patient ou le praticien : plusieurs patients peuvent continuer à avoir des rendez-vous le même jour et à la même heure lorsque les ressources sont disponibles.

La migration `20260913_replanification_concurrency` neutralise les éventuels doublons historiques sans supprimer les lignes : elle conserve le remplacement le plus ancien et détache les doublons plus récents.

## Résultat après correction

| Tentative | Résultat |
|---|---|
| Session A | Succès, nouveau rendez-vous `#11` créé le 21/09/2026 à 09:00 |
| Session B | Rejet propre : `Une replanification existe déjà (RDV #11)` |
| Remplacements actifs du RDV initial | Un seul : `#11` |

Le nouveau rendez-vous reste soumis à la validation finale de l’assistante et à la confirmation téléphonique du patient. Aucun envoi WhatsApp réel n’a été effectué pendant le test.
