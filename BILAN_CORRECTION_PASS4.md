# Bilan de correction — AutoCommerce Clinic Pass 4

## Verdict

La régression signalée est confirmée comme une **régression d’export/packaging frontend**, et non une régression backend. L’archive pass4 initiale omettait des manifestes nécessaires au build (`package.json`, `pnpm-lock.yaml`, `tsconfig.json`, `nginx.conf`) et ne contenait pas `dist/public/index.html`.

## Corrections appliquées

Les manifestes frontend et la configuration Nginx ont été réintégrés. La configuration TypeScript a été restaurée. Cinq erreurs TypeScript de pass4 ont été corrigées : masquage de la fonction de traduction par une variable de tâche, deux contextes i18n manquants pour le formatage des dates photo et remplacement d’une constante de statut obsolète par le helper traduit. Le setup Vitest initialise i18n en français et isole le stockage navigateur entre les tests. Le contrat de test multipart Scribe est aligné sur le comportement correct d’Axios, qui laisse le navigateur générer la boundary. Le test Dashboard IA attend désormais le libellé français traduit « Élevée ».

## Validation

| Contrôle | Résultat |
|---|---:|
| Compilation Python | PASS |
| Tête Alembic unique | PASS — `20260913_replanification_concurrency` |
| `pnpm check` | PASS |
| Tests frontend | PASS — 13 fichiers, 73 tests |
| `pnpm build` | PASS |
| `dist/public/index.html` | PRESENT |
| Manifestes frontend | PRESENTS |
| Intégrité ZIP | PASS |

L’archive corrigée inclut les sources frontend, les locales complètes, les manifestes de dépendances, les configurations Vite/TypeScript/Nginx et le build `dist/public` généré.

## Réserves

La validation backend complète et le smoke navigateur du parcours métier restent ceux documentés dans le bilan fourni. Les données de recette demeurent fictives et l’exposition sandbox ne doit pas recevoir de données patient réelles.
