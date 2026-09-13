# Livraison — workflow complet d’absence et replanification

**Date :** 13 septembre 2026
**Projet :** AutoClinique
**Statut :** implémenté, testé et disponible dans le build local

## Chaîne livrée

Le parcours complet est désormais disponible depuis l’espace assistante. Après un rendez-vous marqué `no_show`, l’assistante peut déclencher une proposition de replanification. Le backend recherche des créneaux libres pour le même praticien, la même durée et la même clinique, puis génère un brouillon WhatsApp contextualisé. Le brouillon reste soumis à validation et aucun message réel n’est envoyé sans connecteur WhatsApp configuré.

Après confirmation explicite du patient, l’assistante sélectionne le créneau confirmé dans l’interface. Le backend vérifie une nouvelle fois la disponibilité, crée un nouveau rendez-vous atomiquement, conserve l’ancien rendez-vous en `no_show`, relie le nouveau rendez-vous avec `remplace_rdv_id`, conserve la source `whatsapp`, journalise l’événement et crée une tâche interne pour l’assistante.

Une protection contre les doublons empêche de confirmer une seconde replanification active pour le même rendez-vous absent.

## Endpoints ajoutés

| Endpoint | Fonction |
|---|---|
| `POST /accueil/rdv/{id}/replanification/proposer` | Recherche jusqu’à trois créneaux et crée le brouillon WhatsApp ainsi qu’une tâche de suivi |
| `POST /accueil/rdv/{id}/replanification/confirmer` | Vérifie le créneau choisi et crée le nouveau rendez-vous confirmé |

Les deux endpoints sont protégés par les rôles accueil autorisés : directrice, assistante et administrateur.

## Vérification d’intégration

Le scénario QA a produit le résultat suivant :

| Élément | Résultat |
|---|---|
| Rendez-vous initial | `#3`, conservé en `no_show` le 14/09/2026 à 14:00 |
| Créneaux proposés | 15/09/2026 à 09:00, 09:30 et 10:00 |
| Brouillon WhatsApp | Généré, avec validation requise |
| Confirmation simulée | Reçue via `whatsapp_simulation` |
| Nouveau rendez-vous | `#8`, le 15/09/2026 à 09:00 |
| Lien historique | `remplace_rdv_id=3` |
| Source | `whatsapp_simulation` |
| Tâche assistante | Créée, tâche `#2` |
| Envoi WhatsApp réel | Non effectué, connecteur non configuré |

## Validations

Le type-check frontend, les tests frontend et le build frontend ont réussi. La suite backend complète a réussi avec la configuration de recette sécurisée : **742 tests réussis et 1 test ignoré**. Le premier lancement sans le paramètre de recette `REFRESH_COOKIE_SECURE=true` a échoué sur le contrôle de configuration de production ; aucun échec fonctionnel n’a persisté après correction de l’environnement de test.

Le serveur a été redémarré et les contrôles runtime suivants sont passés : endpoint `/health` disponible et nouvelle route `replanification/proposer` présente dans OpenAPI.

Aucune migration SQL n’est nécessaire pour cette évolution : elle réutilise les tables existantes `rendez_vous`, `taches_internes_assistant` et `rdv_evenements`.
