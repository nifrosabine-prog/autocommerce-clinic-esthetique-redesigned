# AutoCommerce Clinic — Livraison des blocs 1 et 2

**Date :** 12 septembre 2026
**Statut :** implanté, compilé et vérifié.

## Périmètre livré

### Bloc 1 — Fonctionnalités simples

Le dialogue **Modifier / Replanifier** de l’agenda propose désormais un sélecteur de praticien alimenté par les praticiens actifs de la clinique. Le nouvel identifiant `praticien_id` est transmis au backend existant, qui conserve les contrôles de conflit d’agenda et la règle de self-scoping pour les médecins.

Le contenu arabe de la landing publique était déjà disponible et a été contrôlé comme fonctionnel. La direction RTL est maintenant appliquée de façon globale lors du changement de langue, et non plus uniquement depuis la landing.

L’écran **Recrutement → Gestion des postes** propose désormais une génération d’annonce assistée par IA. Le texte est affiché dans une zone éditable afin que le personnel puisse le relire et le copier manuellement. Aucune publication automatique ni aucun connecteur social n’est déclenché.

Le champ technique **Expression de planification** a été supprimé de l’éditeur de workflows. Le payload frontend ne transmet plus `cron_expression`, afin de ne pas présenter comme active une automatisation planifiée qui n’est pas exécutée par le système.

### Bloc 2 — Fonctionnalités d’effort moyen

Une page publique `/candidature` permet à un candidat de sélectionner un poste ouvert, de renseigner ses coordonnées et de déposer un CV PDF, DOC ou DOCX. La candidature est créée dans le pipeline interne de recrutement sans authentification clinique.

La route publique refuse les postes fermés, limite les fichiers à 10 Mo, vérifie les extensions et les types MIME, stocke le CV dans l’espace de la clinique et conserve le lien protégé vers le document.

L’extraction automatique est disponible pour les formats PDF et DOCX grâce à `pypdf` et `python-docx`. Le bouton d’analyse CV peut maintenant analyser automatiquement le fichier déposé lorsqu’aucun texte n’est fourni manuellement. En cas de document scanné ou d’extraction impossible, le système conserve le parcours manuel sans bloquer le recrutement.

Les traductions arabes MSA ont été complétées pour les libellés communs, l’authentification, la navigation, les rôles, le tableau de bord, les patients, l’agenda, le stock et la facturation. Les contenus métier écrits en dur dans certaines pages ne sont pas automatiquement traduits par le simple fichier de ressources ; ils restent à migrer écran par écran dans une phase i18n ultérieure si une couverture arabe exhaustive de chaque phrase est requise.

## Vérifications exécutées

| Contrôle | Résultat |
|---|---:|
| Compilation Python | PASS |
| Suite backend complète | PASS — 742 réussis, 1 ignoré |
| Contrôle TypeScript `pnpm check` | PASS |
| Tests frontend `pnpm test --run` | PASS — 73 réussis |
| Build frontend `pnpm build` | PASS |
| Tête Alembic | Inchangée — `20260910_documents_medicaux_patients` |

## Fichiers principaux modifiés

- `autocommerce-app/client/src/pages/agenda/AgendaView.tsx`
- `autocommerce-app/client/src/pages/workflow/WorkflowEngine.tsx`
- `autocommerce-app/client/src/pages/recruitment/RecruitmentPage.tsx`
- `autocommerce-app/client/src/pages/public/PublicApplication.tsx`
- `autocommerce-app/client/src/components/LanguageSwitcher.tsx`
- `autocommerce-app/client/src/App.tsx`
- `autocommerce-app/client/public/locales/ar/common.json`
- `api-server/api/v1/recrutement.py`
- `api-server/api/v1/public_recruitment.py`
- `api-server/api/v1/__init__.py`
- `api-server/services/recrutement.py`
- `api-server/requirements.txt`

## Réserves de mise en production

La génération IA dépend de la configuration et du quota IA de la clinique. Elle ne doit jamais être interprétée comme une décision de recrutement et ne publie aucun contenu automatiquement.

La candidature publique doit être testée sur l’environnement de staging avec le stockage réel, les règles de conservation des CV et les mécanismes de suppression ou d’export applicables aux données personnelles.

La validation réalisée ici confirme l’absence de régression automatisée dans le build fourni. Elle ne remplace pas une recette navigateur complète avec les rôles assistante, directrice, médecin et administrateur.
