# Rapport d’audit et de recette — AutoCommerce Clinic

**Date :** 13 septembre 2026  
**Environnement :** recette locale exposée temporairement par sandbox public  
**Verdict :** **GO technique pour recette contrôlée ; NO-GO pour production clinique réelle sans corrections et durcissement complémentaires.**

## Déploiement réalisé

PostgreSQL et Redis ont été installés et démarrés. La base `clinic_production` a été créée avec un compte applicatif dédié. L’environnement Python isolé a été construit, les dépendances backend installées et les dépendances frontend installées depuis le lockfile pnpm. Les migrations Alembic ont été appliquées jusqu’au head `20260913_add_recruitment_inbound_source`.

Le frontend React/Vite a été vérifié avec TypeScript puis compilé en production. Un défaut TypeScript bloquant a été corrigé dans `AgendaView.tsx` : comparaison de l’identifiant du praticien avec `user?.id` au lieu de `user.id` lorsque l’utilisateur peut être nul.

L’API FastAPI/Uvicorn écoute sur le port 8000 et le frontend compilé est servi par Nginx sur le port 8080 avec reverse-proxy des routes `/api/` vers l’API.

## Lien public de recette

[Ouvrir AutoCommerce Clinic — environnement de recette](https://8080-i32ictd6s1mm82rah1zu0-e86cdfc7.us4.manus.computer/)

Ce lien est temporaire et destiné exclusivement à la recette. Il ne constitue pas un déploiement de production durable et ne doit pas recevoir de données patient réelles.

## Comptes de test

| Rôle | Identifiant | Mot de passe |
|---|---|---|
| Directrice / admin | `admin.qa@autoclinique.test` | `AdminQA-2026-Secure!` |
| Médecin | `medecin.qa@autoclinique.test` | `MedecinQA-2026-Secure!` |
| Esthéticienne | `estheticienne.qa@autoclinique.test` | `RoleQA-2026-Secure!` |
| Assistante | `assistante.qa@autoclinique.test` | `RoleQA-2026-Secure!` |

Ces comptes sont fictifs et réservés à la recette.

## Configuration métier de recette

Le seed a créé et vérifié :

| Élément | Résultat |
|---|---|
| Équipe | 1 directrice, 1 médecin, 1 esthéticienne, 1 assistante |
| Acte | `Botox front - recette` |
| Prix de test | `250.000` TND |
| Patient de recette | Ines Gharbi, téléphone fictif `+21620000001` |
| Produit / lot | Produit Botox de recette, lot `QA-LOT-2026-001` |

## Tests exécutés

| Contrôle | Résultat |
|---|---|
| PostgreSQL disponible | PASS |
| Redis disponible | PASS — `PONG` |
| Migrations Alembic | PASS — head atteint |
| Contrôle pré-déploiement sécurité | PASS avec avertissement TLS local |
| TypeScript frontend | PASS |
| Build frontend production | PASS |
| Tests backend ciblés réservation, accueil, consentement, photos, factures, rôles | **64 passed** |
| Smoke local API/frontend | PASS |
| Smoke via lien public API/frontend | PASS |
| Connexion des 4 rôles via lien public | PASS |
| Tests frontend Vitest complets | **68 passed / 5 failed** |

Les cinq échecs frontend concernent le test `patients-list.test.tsx`, autour du bouton d’anonymisation et de son libellé accessible. Ils ne bloquent pas la compilation ni le smoke test, mais doivent être corrigés avant une validation de release complète.

## Parcours demandé — état de preuve

Les briques backend correspondant à la réservation, à la revue assistante, au consentement, aux photos cliniques, au dossier patient, aux factures et aux rôles ont été couvertes par 64 tests backend ciblés réussis. La disponibilité publique, les quatre authentifications et les routes protégées ont aussi été vérifiées.

En revanche, la session n’a pas produit une preuve E2E navigateur complète de chaque transition métier demandée avec données persistées de bout en bout : réservation publique réelle, validation assistante, affectation, signature consentement, photo avant, validation facture, reprise médecin puis revue par esthéticienne. Le verdict ne doit donc pas présenter ce parcours complet comme entièrement démontré par navigateur ; il est **couvert par les tests backend et la validation smoke**, mais reste à exécuter en recette fonctionnelle navigateur avec captures et identifiants de dossier.

## Réserves bloquantes avant production clinique

La publication actuelle est un lien temporaire de sandbox sans domaine métier ni certificat TLS configuré par le projet. Il faut déployer derrière un domaine contrôlé, TLS, sauvegardes PostgreSQL testées, stockage persistant des photos, rotation des secrets, supervision et restauration vérifiée.

Les données de recette sont fictives. Il est interdit d’utiliser ce lien ou ces comptes avec des données de santé réelles. La correction des cinq tests UI frontend et l’exécution d’un parcours navigateur complet avec audit des journaux doivent précéder un go-live.

## Verdict final

**GO pour démonstration et recette technique contrôlée.**  
**NO-GO pour mise en production clinique réelle à ce stade**, en raison du caractère temporaire/non-TLS de l’exposition, de la validation navigateur métier encore incomplète et des cinq tests frontend en échec.
