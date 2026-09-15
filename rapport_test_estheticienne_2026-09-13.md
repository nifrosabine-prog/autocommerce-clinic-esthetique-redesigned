# Test navigateur — rôle esthéticienne

**URL testée :** https://8080-i32ictd6s1mm82rah1zu0-e86cdfc7.us4.manus.computer/  
**Compte :** `estheticienne.qa@autoclinique.test`  
**Patient de recette :** Ines Gharbi

## Scénarios exécutés

La connexion esthéticienne fonctionne et le tableau de bord affiche correctement le rôle **Esthéticienne** ainsi que le nom de Salma Esthéticienne.

La liste des patients est accessible. Le patient Ines Gharbi est visible et son dossier s’ouvre correctement.

Le dossier expose les onglets suivants : Dossiers, Consentements, Photos, Faits médicaux et Prescriptions. L’onglet Photos est accessible sans erreur.

L’onglet Photos affiche actuellement **Photos (0)** et le message « Aucune photo trouvée », ce qui est cohérent avec les données de recette actuelles.

Le bouton **Ajouter une photo** ouvre correctement le formulaire médical. Le type de photo par défaut est **Avant**, avec les choix Après, Progression, Complication et Autre. Le champ Zone anatomique est disponible et les formats JPEG/PNG/WEBP ainsi que la limite de 20 Mo sont indiqués.

Une validation sans fichier a été effectuée. Elle est correctement refusée avec le message utilisateur : **« Sélectionnez une photo »**. Le formulaire reste ouvert et aucune donnée invalide n’est enregistrée.

## Résultats

| Fonction | Résultat |
|---|---|
| Connexion esthéticienne | PASS |
| Accès liste patients | PASS |
| Ouverture dossier Ines Gharbi | PASS |
| Accès onglet Photos | PASS |
| Affichage absence de photos | PASS |
| Ouverture ajout photo | PASS |
| Type Avant disponible | PASS |
| Validation sans fichier | PASS — rejet contrôlé |
| Affichage d’une photo Avant réelle | NON TESTÉ — aucune photo de recette disponible |

## Verdict

**Le rôle esthéticienne possède les droits attendus pour consulter le dossier patient et accéder aux photos avant intervention.** Le formulaire d’ajout d’une photo Avant est présent et sa validation minimale fonctionne.

La vérification du rendu d’une photo Avant réellement enregistrée reste à effectuer après ajout d’un fichier de test autorisé dans le dossier de recette. Aucun défaut bloquant n’a été détecté pendant cette recette.
