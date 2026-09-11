# Clinic Esthétique — Racine de livraison

Ce répertoire est la **racine applicative de livraison**. Il contient le frontend React sous `autocommerce-app/` et l’API FastAPI sous `api-server/`. Les fichiers de template présents un niveau plus haut ne font pas partie du livrable clinique.

## Vérification locale

```bash
corepack pnpm install --frozen-lockfile
corepack pnpm build:frontend
cd api-server && pytest -q
```

## Conteneur

Construire depuis ce répertoire avec le `Dockerfile` joint. Les paramètres d’environnement de production, dont `DATABASE_URL`, `SECRET_KEY`, les clés de chiffrement, le domaine public et les secrets d’intégration, doivent être fournis hors dépôt. Aucun jeu de données de validation n’est démarré par défaut.
