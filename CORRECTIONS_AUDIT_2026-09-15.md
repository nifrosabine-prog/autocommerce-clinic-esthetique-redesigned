# Corrections intégrées — AutoCommerce Clinic

## Export médical

L’export PDF et l’export JSON reprennent les rubriques cliniques structurées : consultations, demande du patient, objectifs, histoire, évolution, traitements précédents, mesures, diagnostic, analyse professionnelle, indication, plan thérapeutique, contre-indications, facteurs de risque, bénéfices, risques, alternatives, recommandations et suivi. Les prescriptions, faits médicaux structurés, analyses, radios et documents importés sont également référencés avec description, type, taille et empreinte d’intégrité.

Les photos cliniques ne sont volontairement pas incluses dans l’export partageable. Elles restent dans l’espace médical sécurisé, avec accès contrôlé aux rôles médicaux autorisés, conformément au RGPD.

## Parcours assistante / médecin

L’assistante peut créer le brouillon d’accueil et valider l’arrivée du patient. Le médecin ou l’esthéticienne signe le consentement et complète le dossier clinique.

## Paiement

Le paiement d’une facture payante crée maintenant une écriture dans le ledger `paiements`, avec le montant total, le mode de paiement et l’utilisateur encaissant. La lecture des factures calcule ainsi correctement `montant_paye` et `solde`. Les factures gratuites ne créent pas d’écriture de paiement à zéro.

## Validation

Tests ciblés exécutés : **20 passed** pour l’export médical, la sécurité de l’export et la facturation.

La réservation publique reste conditionnée à la configuration de l’équipe, des actes et des créneaux dans l’administration.
