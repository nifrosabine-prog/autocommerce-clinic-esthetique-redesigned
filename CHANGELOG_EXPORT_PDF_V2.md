# CHANGELOG — Export PDF enrichi (v2)

## Fichiers modifiés
- `api-server/services/dossier_medical.py` : remplacement complet de `export_dossier_pdf`
- `api-server/api/v1/dossiers_medicaux.py` : point d'appel `/patients/{id}/export-pdf` mis à jour (transmission de l'identité de l'exportateur)

## Nouveautés
- **Consultations** structurées : date, praticien, type, statut, motif, observations cliniques, diagnostic, plan thérapeutique, contre-indications, recommandation (champs déchiffrés).
- **Prescriptions** : date, prescripteur, statut, classification, détails (médicament / dosage / fréquence / durée) déchiffrés.
- **Faits médicaux structurés** : type, statut de vérification, source, auteur, données déchiffrées (actifs uniquement).
- **Documents médicaux / analyses importées** : nom, type MIME, taille (formatée), description, empreinte d'intégrité SHA-256, date d'import.
- **Identité patient complétée** : genre, groupe sanguin, adresse/ville, contre-indications (en plus des allergies/antécédents existants).
- **En-tête d'export professionnel** : référence unique (`DOS-{clinic}-{patient}-{horodatage}`), date/heure UTC, identité de l'exportateur, classification MEDICAL_SENSITIVE.
- **Pagination réelle** « Page X / Y » + rappel d'émission UTC en pied de page, en-tête répété sur toutes les pages.
- **Sécurité** : échappement XML de toute donnée libre déchiffrée avant insertion (champs contenant `<`, `&`, etc. ne cassent plus la mise en page).
- **Confidentialité conservée** : les 4 sections cliniques et les champs sensibles du patient restent réservés au médecin ; la directrice voit une mention « ACCÈS MÉDICAL RÉSERVÉ ».

## Contrat préservé
- Route : `GET /patients/{patient_id}/export-pdf` (inchangée)
- Réponse : PDF en `application/pdf` avec `Content-Disposition` attachment (inchangée)
- Comportements existants conservés : timeline des actes, produits injectés avec lots, photos (visibles selon le rôle), consentements, footer RGPD, masquage directrice.
- Signature interne de `export_dossier_pdf` : `(patient_id, db, user=None, clinic_id=None)` — `user_role` remplacé par le dict `user` complet (id, role, prenom, nom, email, clinic_id). Aucun autre appelant dans le dépôt.

## Vérifications
- Tests exécutés : voir le rapport pytest de la session (blocs A, B, C, D, F exports + dossier médical).
- Rendu PDF réel vérifié pour les branches médecin / directrice, pagination, échappement XML et sections vides.
