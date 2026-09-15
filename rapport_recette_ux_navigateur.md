# Recette UX navigateur — AutoCommerce Clinic

**Date :** 13 septembre 2026  
**Méthode :** utilisation de l’application par navigateur public, sans appels backend directs pour valider les écrans et actions utilisateur.  
**URL testée :** https://8080-i32ictd6s1mm82rah1zu0-e86cdfc7.us4.manus.computer/

## Résultat global

**Résultat : PARTIELLEMENT CONFORME — NO-GO pour le parcours public de prise de rendez-vous.**

Les pages principales, les connexions par rôle, la navigation et l’affichage des données fonctionnent. Toutefois, le parcours patient demandé ne peut pas être terminé par un utilisateur réel, car aucun créneau de réservation n’est disponible.

## Scénarios exécutés dans le navigateur

### Utilisateur public non connecté

La page d’accueil publique se charge correctement. Les sections suivantes sont visibles et navigables : présentation de la clinique, actes, contact, formulaire de rappel et bouton de réservation.

Le formulaire de rappel présente les champs nom, téléphone, email facultatif, besoin et consentement de recontact. La page affiche toutefois que les disponibilités de réservation seront ouvertes après le paramétrage des médecins et prestations.

### Directrice / administratrice

Connexion réussie avec le compte de recette. Les pages suivantes ont été ouvertes avec succès : tableau de bord, gestion d’équipe, actes médicaux, patients, dossier patient et agenda.

La page équipe affiche bien une directrice, une assistante, un médecin et une esthéticienne. La page des actes affiche `Botox front - recette` à `250.000 DT`.

La page patients affiche Ines Gharbi. La recherche par nom fonctionne. Le dossier patient s’ouvre et affiche les onglets dossiers, consentements, photos, faits médicaux et prescriptions.

Le formulaire de nouveau rendez-vous permet de rechercher Ines Gharbi, de sélectionner Nadia Ben Salem et l’acte Botox front - recette. Après ces sélections, le champ créneau affiche **« Aucun créneau disponible »**. La création du rendez-vous ne peut donc pas être finalisée.

### Médecin

Connexion réussie avec le compte médecin. Le tableau de bord, l’agenda, la liste patients et le dossier d’Ines Gharbi sont accessibles.

Le dossier affiche les onglets cliniques et la fonction d’attribution d’un injectable avec le lot de recette. Aucun dossier, consentement ou photo n’existe encore dans les données de recette, ce qui est cohérent avec l’absence de rendez-vous créé.

### Assistante

Connexion réussie avec le compte assistante. Le tableau de bord et l’agenda sont accessibles. L’agenda affiche la zone « Demandes publiques à traiter », actuellement vide, ainsi que la mention expliquant qu’une demande devient un patient et un rendez-vous interne après approbation.

### Esthéticienne

Connexion réussie avec le compte esthéticienne. Le tableau de bord et le dossier patient sont accessibles. Le dossier affiche les onglets dossiers, consentements, photos, faits médicaux et prescriptions. Aucun contenu clinique n’est disponible puisque le rendez-vous n’a pas pu être créé.

## Points conformes

| Fonction | Résultat |
|---|---|
| Chargement de la landing page publique | PASS |
| Navigation publique | PASS |
| Connexion directrice | PASS |
| Connexion médecin | PASS |
| Connexion assistante | PASS |
| Connexion esthéticienne | PASS |
| Gestion équipe visible par directrice | PASS |
| Acte et prix visibles | PASS |
| Recherche patient | PASS |
| Ouverture du dossier patient | PASS |
| Visibilité des onglets médicaux | PASS |
| Zone demandes publiques assistante | PASS |
| Formulaire de rendez-vous interne | PASS partiel |

## Blocage critique observé

Le catalogue affiche l’acte et les praticiens, mais aucune disponibilité horaire n’est paramétrée. Le formulaire de rendez-vous affiche :

> Aucun créneau disponible

La landing page publique affiche également que les disponibilités seront ouvertes après le paramétrage des médecins et prestations.

Ce blocage empêche de tester par navigateur les étapes suivantes : demande publique, validation assistante, affectation, consentement, photographie avant, facturation, reprise médecin et revue par esthéticienne.

## Corrections nécessaires

1. Configurer les horaires de travail et les disponibilités de Nadia Ben Salem et Salma Esthéticienne.
2. Vérifier l’association entre acte, durée, praticien et agenda.
3. Créer au moins un créneau futur de recette visible publiquement.
4. Rejouer la réservation publique depuis un navigateur sans session authentifiée.
5. Valider la demande côté assistante.
6. Exécuter les transitions du dossier jusqu’à la facture et la clôture de l’acte.
7. Vérifier le même dossier avec le médecin et l’esthéticienne.

## Verdict UX

L’application est navigable et les rôles principaux s’authentifient correctement. La structure des écrans est cohérente et les données de recette sont visibles.

Cependant, **le parcours critique “patient prend rendez-vous en ligne” est bloqué par l’absence de créneaux**, ce qui justifie le maintien du **NO-GO pour production** tant qu’un créneau public réel n’a pas été configuré et que le parcours complet n’a pas été rejoué par navigateur.
