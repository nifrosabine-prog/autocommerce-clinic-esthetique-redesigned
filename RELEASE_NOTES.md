# Release Notes — AutoCommerce Clinic Enterprise

## Commercial Production Release — 2026-08-17

### Verdict

**GO — COMMERCIAL PRODUCTION RELEASE**.

Cette release correspond à la version finale réconciliée du package AutoCommerce Clinic Enterprise. La passe de reconciliation n’a ajouté aucune fonctionnalité et n’a pas modifié l’architecture validée; elle a consolidé la source de vérité, les documents et les preuves finales.

### État validé

Le backend compte **515 tests passés et 1 test skipped**. La campagne IA compte **14 tests passés**. Le full-stack, TypeScript, Vitest, le build frontend, Docker, PostgreSQL, Redis, Celery, beat, les audits de dépendances, l’authentification/MFA, les cookies de refresh, la rotation/reuse, l’isolation tenant, le booking public, la Public Gateway, le Private Clinical Core, Nginx, la frontière réseau et le backup/restore sont PASS.

Le release gate final a produit `EXIT 0` et :

```text
GO: tous les contrôles critiques exécutés avec succès.
```

### Version et migrations

La tête Alembic réellement exécutée est `c9d0e1f2a3b4`. Cette valeur est la seule tête référencée dans les documents finaux et dans le manifeste.

### Architecture réseau

La surface publique est `app.autocommerce-clinic.com` et `pub.api.autocommerce-clinic.com`, avec `/api/public`, booking, landing et webhooks nécessaires. La surface privée est `clinic.autocommerce-clinic.local` et `api.autocommerce-clinic.com`, avec `/api/private`, `/api/v1` legacy, patients, dossiers, facturation, stock, agenda, IA et audit. PostgreSQL et Redis restent internes.

Le contrôle runtime final a confirmé : public gateway `200`, public vers private `404`, listener privé bloqué depuis l’interface publique et private authentifié `200`.

### Preuves et packaging

La source de vérité est `FINAL_RELEASE_GATE.log`. Les commandes, dates, exit codes et fichiers de preuve sont détaillés dans `RELEASE_EVIDENCE_FINAL.md`. Le package final est `AutoCommerce-Clinic-Enterprise-Commercial-Production-Ready-FINAL-2026-08-17.zip` et son empreinte est dans `SHA256SUMS.txt`.

### Limites de déploiement

Le package est techniquement validé en staging. Avant l’ouverture production chez une clinique, il faut configurer et tester le DNS réel, le TLS réel, le firewall réel, le VPN/réseau clinique réel, le backup externe et les credentials des fournisseurs externes. Ces éléments ne sont pas présentés comme déjà validés.

## Revalidation du package livré — 2026-08-19

Cette section complète l'historique précédent avec les vérifications effectuées sur la version actuellement préparée pour le test interne.

| Vérification | Résultat |
|---|---|
| Import complet de l'application FastAPI | Réussi avec `ENV=test` |
| Suite backend complète | 534 tests réussis, 1 test ignoré |
| Tests Agenda et Workflows | Réussis |
| Contrôle TypeScript | Réussi |
| Suite frontend Vitest | 67 tests réussis |
| Build frontend de production | Réussi |
| Synchronisation du build unifié | `autocommerce-app/dist` copié vers `api-server/web-dist` |
| Route API inconnue | Retourne désormais 404 JSON au lieu de servir le SPA |

Le package inclut le code source backend FastAPI, le frontend React/Vite, les migrations, les tests, les fichiers de configuration d'exemple et les builds frontend synchronisés dans `api-server/web-dist`. Les dépendances installées et les secrets réels ne sont pas inclus ; les fichiers de verrouillage permettent une installation reproductible avec pnpm.

Pour la validation locale du backend :

```bash
cd api-server
ENV=test pytest -q
```

Pour la validation du frontend :

```bash
pnpm --dir autocommerce-app check
pnpm --dir autocommerce-app test -- --run
pnpm --dir autocommerce-app build
```

Les secrets réels, notamment `api-server/.env.clinic`, sont volontairement exclus du ZIP. Seuls les fichiers `.example` sont livrés. Une migration de base de données et une configuration PostgreSQL/Redis sont nécessaires avant un démarrage sur une base vide.

Le déploiement interne de production et le test manuel complet par l'utilisateur restent l'étape suivante. Aucun déploiement Railway n'est inclus ou déclenché par ce package.
