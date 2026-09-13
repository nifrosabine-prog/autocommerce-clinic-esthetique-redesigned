
## Incident détecté

La page `/login` du build de production est rendue correctement. Une première soumission a affiché `Erreur de connexion`, causée par l’absence du domaine frontend temporaire dans `CORS_ORIGINS`. Après redémarrage de l’API avec `CORS_ORIGINS=https://3002-iy8oy7whdeuec1nysdxnd-bf1f158d.us4.manus.computer`, la connexion directrice a réussi et a redirigé vers `/dashboard`. Le tableau de bord, la navigation métier et le rôle `Directrice` sont visibles.
