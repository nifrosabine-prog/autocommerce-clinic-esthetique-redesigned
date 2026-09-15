# Validation dossier médical avec données QA fictives

**Patient de recette :** Ines Gharbi  
**Rôle vérifié :** Esthéticienne  
**URL :** https://8080-i32ictd6s1mm82rah1zu0-e86cdfc7.us4.manus.computer/

## Données fictives enregistrées

Deux éléments explicitement marqués QA ont été ajoutés dans l’environnement de recette :

| Élément | Résultat | Détail |
|---|---|---|
| Consentement fake | ENREGISTRÉ | Consentement `acte_medical`, valide, méthode `qa_fake`, ID 2 |
| Photo fake | ENREGISTRÉE | Photo `avant`, zone `visage — QA FAKE`, ID 1 |

La photo est une image fictive générée pour la recette et contient une mention visuelle **QA / FAKE — ne pas utiliser en production**. Aucun fichier patient réel n’a été utilisé.

## Vérification dans l’interface esthéticienne

Après rechargement du dossier patient, l’interface affiche :

- **Consentements (1)**
- **Photos (1)**
- Le consentement apparaît comme **Valide** avec la méthode `qa_fake`.
- La photo apparaît dans l’onglet Photos avec le type **Avant** et la date du 13/09/2026.
- La vignette de la photo est chargée et visible dans le navigateur.

## Dossier complet ou non ?

Le dossier médical n’est **pas complet** à ce stade.

La présence d’un consentement valide et d’une photo Avant confirme que les pièces préalables sont bien enregistrées, mais l’interface affiche encore :

- **Dossiers (0)**
- aucune intervention clinique réalisée ;
- aucun rendez-vous créé ;
- aucune facture liée ;
- aucun acte terminé ;
- aucune photo Après ;
- aucune note clinique ou prescription.

## Verdict

**Les données fake sont bien persistées et consultables.** Elles permettent de valider le fonctionnement technique de l’accès esthéticienne, de la signature et de la photo Avant.

**Le dossier médical est partiellement renseigné, mais non complet.** Pour le considérer complet dans le parcours métier, il faut encore créer un rendez-vous, ouvrir ou créer le dossier clinique, enregistrer l’acte et les observations, valider la facturation, puis ajouter une photo Après et clôturer l’intervention.

Les données `qa_fake` peuvent être supprimées après la recette sans impact sur les données réelles.
