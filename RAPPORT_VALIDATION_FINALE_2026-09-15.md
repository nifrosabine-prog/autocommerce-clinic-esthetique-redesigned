# Validation finale — 15 septembre 2026

## Validation technique

- Backend : **745 tests passés, 1 test ignoré**.
- Frontend : `pnpm check` PASS.
- Frontend tests : PASS.
- Frontend build : PASS.
- PostgreSQL : OK.
- Redis : OK.
- Endpoint readiness : OK.

## Retest E2E en ligne

La nouvelle version a été déployée et testée en ligne sur :

https://8001-ivezsdrj1zq39s41t7vdw-f1cd7e0f.us1.manus.computer/

Le parcours suivant est PASS : configuration équipe et acte tarifé, produit et lot injectable, rendez-vous, arrivée assistante, consentement médecin, dossier clinique, photo protégée, utilisation du lot, export médical PDF/JSON, création facture, paiement et téléchargement facture.

Identifiants du dernier passage : acte 3, produit 2, lot 2, rendez-vous 3, dossier 7, photo 3, facture 3.

Le lot injectable a été consommé avec succès : 2 unités, utilisation 3, stock décrémenté.

La facture finale `F-2026-0003` est payée et doit retourner `montant_paye=320`, `solde=0`, `statut=payee`. Les anciennes factures de recette créées avant la correction peuvent conserver leurs incohérences historiques.

Les photos cliniques sont exclues de l’export partageable et restent accessibles dans l’espace médical sécurisé conformément au RGPD.
