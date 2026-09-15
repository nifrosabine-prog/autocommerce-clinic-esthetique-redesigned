# Audit utilisateur AutoCommerce Clinic

**Date :** 15 septembre 2026  
**Archive auditée :** `autocommerce-clinic-pass4-i18n-light.zip`  
**Environnement :** Ubuntu 24.04, PostgreSQL 16, Redis 7, Python 3.11, Node.js 22, pnpm 11  
**URL de recette :** https://8000-ivezsdrj1zq39s41t7vdw-f1cd7e0f.us1.manus.computer/

## Verdict exécutif

Le projet est **fonctionnel sur son socle principal**, mais je ne recommande pas un **GO production sans réserve**. Le démarrage complet a réussi, les migrations ont été appliquées, PostgreSQL et Redis sont opérationnels, le frontend se compile et le parcours public ainsi que les principaux dashboards sont accessibles.

Le verdict reste **GO conditionnel**, mais la réservation publique ne doit pas être classée comme un blocage produit autonome. Elle devient fonctionnelle après configuration de l’équipe, des actes et des créneaux dans l’administration. La suite backend présente encore **3 échecs sur 746 tests exécutés**. Le parcours médical est correctement protégé par le consentement, mais aucun consentement signé n’est préconfiguré pour permettre la validation clinique et la photo de recette. La réservation doit donc être contrôlée après configuration complète, mais elle n’est pas en elle-même un défaut bloquant confirmé.

## Build et démarrage complet

La stack locale a été installée puis démarrée sans Docker, conformément à la documentation du projet. PostgreSQL 16 et Redis 7 ont été installés comme services système. Les dépendances Python et JavaScript ont été installées avec succès.

Les migrations Alembic ont atteint la tête `20260913_replanification_concurrency` sans erreur. Les endpoints de santé ont retourné les résultats suivants :

```json
{"status":"ok"}
{"status":"ready","postgres":"ok","redis":"ok"}
```

Le frontend a passé le contrôle TypeScript et le build Vite. Le build produit notamment les bundles des dashboards, de l’agenda, des patients, du dossier médical, du stock, des factures et du recrutement.

La suite frontend exécutée par `pnpm test` et le build sont passés. La suite backend a produit **742 tests passés, 1 test ignoré et 3 tests en échec**.

## Rôles et dashboards

Les comptes suivants ont été testés :

| Rôle | Connexion | API principale | Dashboard UI | Résultat observé |
|---|---:|---:|---:|---|
| Directrice / administratrice QA | PASS | PASS | PASS | Dashboard complet avec pilotage, agenda, stock, factures, recrutement et administration |
| Médecin QA | PASS | PASS | PASS | Dashboard médical avec patients, agenda, dossier médical, factures et suivi |
| Esthéticienne QA | PASS | PASS | Non rejoué intégralement dans le navigateur | Connexion, profil, agenda, patients, factures et dossiers autorisés par API |
| Assistante QA | PASS | PASS | Non rejoué intégralement dans le navigateur | Connexion, profil, agenda, patients, factures et dossiers autorisés par API |

Le dashboard de la directrice expose 21 entrées de navigation, dont les modules IA, agenda, patients, dossier médical, stock, facturation, commissions, fidélité, recrutement, social CRM, équipe, salles, reporting RH, actes et paramètres. Le dashboard médecin expose un sous-ensemble cohérent, sans les fonctions de gestion réservées à la direction.

Le contrôle RBAC vérifié directement confirme notamment que la directrice ne peut pas créer un dossier clinique et reçoit `403 Accès refusé`. Cette opération est réservée aux rôles médicaux autorisés par le backend.

Les rôles `super_admin`, `commercial` et `prestataire` existent dans le code, mais aucun compte de recette n’a été fourni ou provisionné pour eux dans cette archive. Ils ne peuvent donc pas être déclarés validés par cet audit utilisateur.

## Internationalisation et RTL

Le sélecteur de langue fonctionne dans le dashboard. Les locales français, anglais, italien, allemand et arabe sont proposées. Le passage en arabe a correctement modifié le texte, `document.documentElement.lang` et la direction visuelle RTL. Le dashboard directrice, le dashboard médecin, l’agenda, le stock, la facturation, le recrutement, le dossier médical et la landing publique ont été observés en arabe.

Le rendu RTL est exploitable, mais l’audit confirme que plusieurs écrans métier restent plus fragiles que le dashboard. Le rapport existant du projet signalait déjà que de nombreuses pages utilisent encore des chaînes françaises codées en dur au lieu de consommer `useTranslation`. Ce point reste à traiter avant de considérer l’i18n comme complète.

## Parcours public

La landing publique charge correctement son branding MBA Clinic, les praticiens et l’acte Botox de recette. Le formulaire de rappel a été soumis avec succès et a retourné `201` ainsi qu’un identifiant de lead.

La réservation publique a été testée au niveau API. Une requête valide avec `date_heure` a créé une demande en attente avec `202` et `booking_request_id=1`. La demande n’est pas transformée directement en patient ou rendez-vous interne, ce qui respecte la séparation attendue entre le public et le cœur clinique privé. Le fonctionnement dépend toutefois de la configuration préalable des praticiens, des actes et des créneaux dans l’administration. Le propriétaire du projet confirme que le parcours fonctionne après cette configuration ; la réservation doit donc être classée comme une **précondition de recette**, et non comme un défaut confirmé du produit.

Lors de la première recette, l’interface présentait les périodes matin et après-midi comme « indisponibles ». Cette observation s’explique désormais par une configuration de recette incomplète ou non synchronisée avec les créneaux disponibles. Le contrat API exige `date_heure`, tandis que l’interface sélectionne une période ; ce point doit être vérifié après configuration complète, mais il ne doit pas être déclaré bloquant sans reproduire l’échec dans cette configuration.

## Dossier médical et fichiers

Le dossier médical de la patiente de recette s’ouvre correctement. Les onglets suivants sont présents : dossiers, consentements, photos, données médicales et prescriptions. L’interface distingue correctement la fiche administrative de la création du dossier clinique.

Le médecin a réussi à téléverser un document médical texte. Le backend a retourné `201`, a persisté le document avec son hash SHA-256 et a permis son téléchargement avec `200`. Le contenu téléchargé correspondait exactement au contenu envoyé. Les exports structurés et PDF du patient ont également répondu avec succès.

La séparation métier a été vérifiée. L’assistante peut créer un **brouillon d’accueil** avec les coordonnées et l’arrivée du patient ; le brouillon est créé avec succès et reste à ouvrir par le médecin. Le médecin et l’esthéticienne sont les rôles autorisés pour la création clinique, mais leur tentative a été refusée avec `400 Consentement non signé ou expiré pour cet acte`, ce qui est attendu sans consentement valide. Le téléversement de photo a été refusé avec `400 Consentement photo non signé ou expiré`. Le parcours métier complet n’est donc pas validable avec les seules données QA actuelles : il faut d’abord créer et signer les consentements prévus par le produit, puis rejouer l’ouverture clinique, la photo, les faits médicaux, la prescription et la suppression logique.

## Modules métier visualisés

Les écrans suivants ont été ouverts avec le compte directrice et ont rendu leur contenu sans erreur bloquante :

- **Dashboard :** KPI à zéro cohérents avec la base fraîche et bouton de pointage présent.
- **Agenda :** vue jour/semaine, nouveau rendez-vous, demandes publiques en attente et recherche patient.
- **Stock :** lot Botox de recette visible avec quantité 100, seuil 10 et statut correct ; ajout de lot et scan QR présents.
- **Facturation :** factures clients, services à facturer, dépenses et audit financier accessibles ; état initial vide.
- **Recrutement :** postes, nouvelle candidature, filtres et compteurs de workflow accessibles ; état initial vide.
- **Dossier médical :** patient Ines Gharbi visible, onglets cliniques présents, création restreinte au médecin.

Les modules secondaires sont présents dans le menu, mais ne peuvent pas tous être déclarés fonctionnellement validés par simple ouverture : les données de test ne couvrent pas les cas nécessaires pour les workflows d’absences, facturation d’un acte, commission, prescription, consentement, suivi post-acte, messages, recrutement avec CV et validation assistante.

## Échecs automatisés

Les trois échecs backend sont concentrés dans `tests/test_config_security.py` et `tests/test_dual_mode_enterprise.py`. Ils apparaissent lors de tests qui chargent une configuration de production ou de mode entreprise sans `REFRESH_COOKIE_SECURE=true`. L’application refuse alors la configuration avec :

```text
Configuration de production invalide:
REFRESH_COOKIE_SECURE doit être true en production
```

Le refus est raisonnable en production. Le défaut concerne le contrat de test : les fixtures de configuration de ces trois tests ne fournissent pas la valeur exigée par la validation actuelle. Il faut soit mettre à jour les fixtures, soit clarifier la règle de sécurité attendue pour le mode entreprise. Tant que ces trois tests échouent, la release ne doit pas être considérée comme verte.

## Anomalies et priorités de correction

| Priorité | Constat | Impact | Correction recommandée |
|---|---|---|---|
| P0 | 3 tests backend en échec sur la configuration sécurisée | Pipeline de release rouge | Corriger les fixtures et ajouter un test de démarrage production réel |
| P1 | Réservation publique dépendante de la configuration équipe, actes et créneaux | Un environnement non configuré affiche des disponibilités indisponibles | Documenter cette précondition et rejouer la réservation après configuration complète |
| P1 | Aucun consentement de recette pour ouverture clinique et photo | Le workflow clinique complet reste non démontré, tandis que le brouillon d’accueil est validé | Ajouter un seed QA de consentement signé et rejouer tout le parcours médical |
| P1 | Facture marquée `payee` mais `montant_paye=0` et `solde=320` après paiement de 320 TND | Les indicateurs financiers ne reflètent pas le statut de paiement | Réconcilier le paiement, le montant payé et le solde dans la transaction et dans les lectures facture |
| P2 | Export structuré JSON enrichi, mais les photos restent volontairement exclues et les originaux sensibles sont séparés | Le destinataire doit disposer d’un accès médical autorisé pour consulter les photos ou télécharger un document original | Conserver le contrôle RGPD et documenter le téléchargement séparé des originaux |
| P1 | Tous les rôles du code ne sont pas provisionnés | `super_admin`, `commercial` et `prestataire` non validés | Ajouter des comptes et une matrice de tests par rôle |
| P1 | i18n incomplète dans les pages métier | Risque de chaînes françaises résiduelles en arabe/RTL | Brancher les pages métier à `useTranslation` et vérifier les libellés dynamiques |
| P2 | Les données de recette sont presque vides | KPI, factures, demandes et workflows complexes non exercés | Ajouter une fixture réaliste couvrant un cycle clinique complet |

## Recommandation finale

## Recette clinique multi-rôles exécutée

### Évolution de l’export médical après clarification RGPD

L’export médical a été renforcé pour transmettre à un autre médecin les informations cliniques utiles et vérifiables : toutes les rubriques de consultation, demande du patient, objectifs, histoire, évolution, traitements précédents, mesures et résultats, diagnostic ou analyse professionnelle, indication, plan thérapeutique, contre-indications, facteurs de risque, bénéfices, risques, alternatives, recommandations et suivi. Les prescriptions, faits médicaux structurés, analyses importées, radios et documents médicaux sont listés avec leur description, type, taille et empreinte d’intégrité ; les documents texte et images importés peuvent également être prévisualisés dans le PDF lorsque leur format le permet.

Les photos cliniques ne sont volontairement pas intégrées dans l’export partageable. Le PDF et l’export JSON indiquent explicitement qu’elles restent dans l’espace médical sécurisé, conformément au RGPD. Elles restent consultables uniquement par les rôles médicaux autorisés dans l’application. Les documents originaux sensibles restent eux aussi stockés dans leur espace sécurisé et sont récupérables séparément avec contrôle d’accès et journalisation.

Les tests d’export ciblés sont au vert : **5 tests passés**. Le PDF réel régénéré contient les sections « Consultations », « Prescriptions », « Faits médicaux structurés » et « Analyses, radios et documents médicaux », ainsi que l’avertissement explicite d’exclusion des photos cliniques.

Le scénario demandé a été exécuté sur une base réelle avec les comptes authentifiés de la directrice, de l’assistante et du médecin. L’équipe contenait bien un médecin, une esthéticienne et une assistante. Un acte `Audit Botox Clinique` a été créé avec un prix de 320 TND, ainsi qu’un produit injectable `Botox Audit Clinique` et le lot `AUDIT-2026-09`.

L’assistante a créé un rendez-vous pour Ines Gharbi avec le médecin, puis a validé l’arrivée du patient. Le backend a créé l’épisode et le brouillon de dossier. Le médecin a signé le consentement médical, ouvert le dossier clinique, renseigné les zones traitées, les observations, les effets secondaires et la satisfaction, puis téléversé une photo médicale. La photo a été relue avec succès en JPEG déchiffré. L’utilisation de deux unités du lot injectable a été enregistrée avec succès et la traçabilité du lot a retourné le praticien, la quantité et le dossier.

L’export PDF du dossier a été téléchargé et converti en texte pour vérification. Il contient le patient, le praticien, l’observation clinique, le consentement signé et le document médical. L’export structuré JSON a bien répondu, mais il ne contenait que les documents dans la liste `entries` et ne reprenait pas le dossier clinique créé. Ce comportement doit être vérifié selon le contrat attendu de l’export structuré.

L’assistante a ensuite créé la facture `F-2026-0001` de 320 TND. Le paiement par carte a retourné `statut: payee` et a produit 32 points de fidélité. Le PDF de facture a été téléchargé avec succès et contient le patient, la prestation, le prix de 320 TND et le total TTC. Une incohérence est toutefois visible dans la lecture de la facture après paiement : la facture est marquée `payee`, mais l’API retourne encore `montant_paye: 0` et `solde: 320`. Le statut de paiement et les montants financiers doivent être corrigés ou réconciliés.

| Étape | Résultat |
|---|---|
| Configuration équipe | PASS |
| Création acte tarifé | PASS |
| Création produit et lot injectable | PASS |
| Rendez-vous par l’assistante | PASS |
| Validation arrivée patient | PASS |
| Consentement médecin | PASS |
| Ouverture dossier clinique | PASS |
| Téléversement et relecture photo | PASS |
| Traçabilité utilisation injectable | PASS |
| Export PDF dossier et vérification texte | PASS |
| Export structuré JSON | PASS technique, contenu à vérifier |
| Création facture | PASS |
| Paiement | PASS technique, incohérence solde |
| Téléchargement facture | PASS |

Le projet peut poursuivre une recette corrective. Le socle technique, l’authentification, le RBAC de base, le chargement des dashboards, le stockage de documents et les protections du dossier médical sont encourageants. La mise en production doit rester conditionnée à la remise au vert des trois tests backend, à une recette clinique avec consentements signés et à une dernière vérification de réservation après configuration de l’équipe, des actes et des créneaux. La réservation publique n’est pas, à ce stade, un défaut bloquant confirmé.

Après ces corrections, il faudra rejouer le scénario complet suivant : réservation publique, validation accueil, création patient, rendez-vous interne, consentement, dossier clinique, photo avant/après, acte médical, prescription, suivi, facturation, export PDF et contrôle d’audit.

## Références

[1]: https://8000-ivezsdrj1zq39s41t7vdw-f1cd7e0f.us1.manus.computer/ "Instance de recette AutoCommerce Clinic auditée"
