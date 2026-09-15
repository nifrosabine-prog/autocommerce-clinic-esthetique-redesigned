# Bilan de build complet — AutoCommerce Clinic

## Résultat

Le projet a été construit et démarré dans un environnement local de recette avec PostgreSQL, Redis, les dépendances Python, les dépendances pnpm et les outils de compilation frontend.

## Infrastructure

| Élément | Résultat |
|---|---|
| PostgreSQL | PASS — PostgreSQL 16 actif |
| Redis | PASS — Redis 7 actif, `PONG` |
| Base | `clinic_test` |
| Migration Alembic | PASS — tête unique `20260913_replanification_concurrency` |
| Tables après migration | 91 |
| Dépendances Python | PASS — environnement virtuel `.venv` |
| Dépendances frontend | PASS — `pnpm install --frozen-lockfile` |
| TypeScript | PASS — `pnpm check` |
| Build Vite | PASS — `dist/public/index.html` généré |
| API FastAPI | PASS — port local 8000 |
| Nginx | PASS — reverse-proxy sur le port 8080 |

## Vérification publique

URL temporaire de recette :

<https://8080-i35ghrp3iujk6876edc61-fc375964.us1.manus.computer>

Contrôles effectués via cette URL :

| Route | Résultat |
|---|---:|
| `/` — interface React complète | HTTP 200 |
| `/api/public/content` | HTTP 200 |
| `/api/public/praticiens` | HTTP 200 |
| `/api/public/actes` | HTTP 200 |
| `/ready` en local | PostgreSQL et Redis OK |

L’acte de recette `Botox front - recette` est visible dans la réponse publique, avec une durée de 30 minutes et un prix de 250 TND.

## Comptes fictifs de recette

| Rôle | Identifiant | Mot de passe |
|---|---|---|
| Directrice | `admin.qa@autoclinique.test` | `AdminQA-2026-Secure!` |
| Médecin | `medecin.qa@autoclinique.test` | `MedecinQA-2026-Secure!` |
| Esthéticienne | `estheticienne.qa@autoclinique.test` | `RoleQA-2026-Secure!` |
| Assistante | `assistante.qa@autoclinique.test` | `RoleQA-2026-Secure!` |

Patient fictif de recette : Ines Gharbi, téléphone `+21620000001`.

## Important

Cette URL est une exposition temporaire du sandbox, destinée uniquement à la démonstration et à la recette technique. Elle ne constitue pas un déploiement de production durable. Ne pas y saisir de données de santé réelles. Les secrets utilisés pour cette instance sont locaux et ne sont pas inclus dans l’archive livrée.
