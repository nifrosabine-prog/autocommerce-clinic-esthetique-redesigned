# Branding des documents et design des factures

## Logo par clinique

Chaque clinique peut configurer son propre logo depuis les paramètres de branding. Le logo est envoyé par un administrateur ou une directrice via `POST /api/v1/settings/branding/logo`, stocké dans un répertoire isolé `clinic-{clinic_id}` et enregistré dans la configuration branding de cette clinique.

Les formats PNG, JPEG et WEBP sont acceptés, avec une taille maximale de 2 Mo. L’image est validée par son contenu réel, redimensionnée à 600×300 maximum et optimisée avant stockage. Les exports PDF ne lisent que les fichiers générés dans le répertoire branding interne ; les URLs externes et les chemins arbitraires sont refusés.

## Documents concernés

Le logo clinique est injecté dans l’en-tête des factures/devis et des exports PDF du dossier médical. Le nom, les couleurs primaire/secondaire, l’adresse et le téléphone de la clinique sont également repris lorsque configurés.

## Facture améliorée

La facture utilise désormais un bandeau de marque, une carte émetteur/client, un tableau alterné lisible, des totaux mis en évidence, le statut et le mode de paiement, un pied de page paginé et une référence visuelle cohérente.

## Vérification en ligne

Avec le logo configuré pour la clinique de recette, les deux documents ont été générés et vérifiés :

- facture brandée : 238 Ko, logo raster détecté dans le PDF ;
- dossier médical brandé : 241 Ko, logo raster détecté dans le PDF ;
- facture `F-2026-0004` : 320 TND, payée, solde zéro ;
- nom de clinique visible : `AutoCommerce Clinic Demo`.

Tests PDF ciblés : **10 passed**.
