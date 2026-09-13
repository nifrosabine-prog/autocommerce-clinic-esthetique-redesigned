# Validation de recette — AutoCommerce Clinic

Date : 5 septembre 2026

## Environnement exécuté

L’application a été installée en mode classique, sans Docker, avec PostgreSQL 16, Redis 7, un environnement virtuel Python, le backend FastAPI et le frontend Vite lancé avec pnpm. La base `clinic_production` et l’utilisateur PostgreSQL de recette ont été créés, puis toutes les migrations Alembic ont été appliquées. Les données mock de recette ont été injectées avec `seed_production.py`.

Le backend répond sur `http://127.0.0.1:18000` et le frontend sur `http://127.0.0.1:18080`. Les endpoints `/health` et `/ready` répondent correctement, avec PostgreSQL et Redis indiqués comme opérationnels.

## Vérifications automatisées

Les tests ciblés du client LLM sont passés : **7 tests réussis**. Les tests frontend Vitest sont passés : **13 fichiers et 73 tests réussis**. Le contrôle TypeScript et le build frontend pnpm sont également passés.

## Vérification navigateur

Le parcours réel suivant a été exécuté dans le navigateur : ouverture de `/login`, saisie du compte mock directrice, soumission du formulaire et redirection vers `/dashboard`. La page affiche « Connecté avec succès », le rôle « Directrice » et les modules applicatifs.

Le frontend a d’abord été lancé avec `vite preview`, ce qui ne proxyfiait pas `/api` et provoquait une erreur de connexion dans le navigateur. Il a été relancé avec `pnpm dev` et `AESTHETIC_API_PROXY_TARGET=http://127.0.0.1:18000`, après quoi la connexion navigateur a fonctionné.

## Vérification IA

L’endpoint assistant a été testé avec une demande de réponse à un message patient et a produit une réponse professionnelle en français. Une demande d’analyse d’un message de report de rendez-vous a également produit une analyse structurée avec les actions administratives recommandées et les informations manquantes à demander.

Le garde-fou médical a correctement refusé une demande de diagnostic précis et a orienté vers un professionnel de santé ou les urgences si nécessaire.

Le modèle réellement utilisé dans cette recette est `openai / gpt-5-mini`, car c’est le modèle autorisé par le proxy d’exécution disponible. Le client a été corrigé pour utiliser `max_completion_tokens` et la température par défaut avec les modèles GPT-5, tout en conservant `max_tokens` et la température applicative pour `gpt-4o` et `gpt-4o-mini`.

## Corrections appliquées

Le client LLM distingue désormais les paramètres compatibles GPT-5 des paramètres historiques GPT-4o. Le budget de sortie de l’endpoint `/api/v1/assistant-ia/ask` a été augmenté afin de laisser suffisamment de place au raisonnement des modèles GPT-5 et d’éviter les réponses vides.

## Limites constatées

Le fichier de test fourni `scripts/test_online_roles.py` utilise une URL publique historique et un préfixe qui ne correspondent pas au lancement local ; il ne constitue donc pas un test valide tel quel pour cette recette. Les parcours équivalents ont été exécutés directement contre l’API locale et dans le navigateur avec le proxy Vite correct.

L’environnement Docker n’a pas pu être utilisé, non pas à cause du projet, mais parce que le noyau de la sandbox bloque les règles `iptables raw` nécessaires aux réseaux Docker. L’installation classique PostgreSQL, Redis, Python et pnpm a été utilisée avec succès.
