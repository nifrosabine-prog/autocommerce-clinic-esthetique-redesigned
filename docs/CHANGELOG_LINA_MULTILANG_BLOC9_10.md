# Changelog — Lina multilingue, réponse patient réelle, Bloc 9/10

Date : 2026-09-06
Base auditée : `AutoCommerce-Clinic-recette-STABILISE-v2.zip`

## 1. Correctif critique — Lina ne répondait à AUCUN patient réel

`services/assistant_ia.py` (Bloc 1-3 : darija, garde médical, escalade)
n'était joignable que par une route interne authentifiée
(`POST /assistant/ask`). Le webhook WhatsApp réel
(`middleware/webhook_omnicanal.py`) ne routait vers un agent que les
numéros whitelistés (staff/direction, Bloc 9) : un vrai patient qui
écrivait sur le WhatsApp de la clinique était seulement enregistré dans
l'inbox, sans aucune réponse automatique.

**Corrigé** :
- Nouveau `services/lina_patient_reply.py` — chemin patient dédié,
  léger (ne dépend pas des tables `sessions_assistant` /
  `commandes_assistant`, réservées aux numéros staff whitelistés via
  contrainte FK `whitelist_id`).
- Câblé dans `middleware/webhook_omnicanal.py` : après persistance du
  message entrant patient, Lina répond automatiquement via
  `omnicanal_service.send_reply` (le connecteur réel du canal).
- Respecte toutes les règles dures du Bloc 0 : jamais de diagnostic,
  jamais d'action exécutée automatiquement (annulation/RDV → transmis à
  l'équipe), anti prompt-injection, anti-hallucination (le seul fait
  cité — le prochain RDV — vient d'une requête SQL réelle, jamais
  inventé), échec silencieux et sans casser le webhook (fail-safe).

## 2. Différenciation patient vs directeur/admin (confirmée + corrigée)

Le routage existait déjà côté staff : un numéro whitelisté déclenche
`clinic_agent.handle_agent_message` (Bloc 9 — rapports, RDV, stock, CA,
tâches). Il manquait la moitié patient (§1) — désormais les deux
chemins sont réellement actifs et distincts :

| Expéditeur            | Chemin                                | Comportement |
|------------------------|----------------------------------------|--------------|
| Numéro staff whitelisté | `clinic_agent.py` (Bloc 9)             | Lecture directe (RDV du jour, CA, stock...) + actions proposées avec confirmation HMAC |
| Numéro patient          | `lina_patient_reply.py` (Bloc 1, neuf) | Lecture seule de ses propres données (prochain RDV), toute demande d'action transmise à l'équipe, escalade médicale immédiate |

## 3. Multilingue élargi (fr / darija / en / it / de)

Nouveau `services/lina_i18n.py` : table de traduction centrale avec
test de complétude (`tests/test_lina_patient_reply.py`) qui échoue si
une clé est ajoutée sans ses 5 traductions. `services/medical_guard.py`
couvrait déjà ces 5 langues pour l'escalade médicale ; le chemin patient
généraliste (accueil, prochain RDV, transmission à l'équipe, refus
d'injection) est désormais lui aussi couvert dans les 5 langues.

**Non traité dans ce lot** (à budgétiser séparément si besoin) :
localisation complète des réponses opérationnelles du Bloc 9
(`clinic_agent._humanize` — CA, stock, tâches...), qui restent fr/darija
uniquement ; la direction utilisant l'agent est un usage interne, jugé
moins prioritaire que la réponse patient.

## 4. Bloc 10 — publications réseaux sociaux « compatibles algorithmes »

`services/lina_tools.py::create_social_post_draft` renvoie désormais un
bloc `recommandations_format` par brouillon : longueur du texte, nombre
de hashtags détectés, et repères de bonnes pratiques publiques par
plateforme (TikTok : vidéo courte + 3-5 hashtags ; Instagram : accroche
dans les 125 premiers caractères + 5-15 hashtags ; Facebook : peu de
hashtags + CTA pour les commentaires). Ce sont des repères déclaratifs,
jamais un score de portée mesuré ni une garantie — et la publication
reste 100 % manuelle (`publier_post` n'est toujours pas exposé à
l'agent).

**WhatsApp n'a pas été ajouté comme plateforme de publication** :
WhatsApp est un canal de messagerie, pas un flux public avec un
algorithme de recommandation — l'ajouter aurait été une fonctionnalité
inventée. Les relances/rappels WhatsApp existent déjà via le Bloc 3
(`draft_whatsapp`, brouillon + validation humaine).

## Fichiers modifiés / ajoutés

- `api-server/services/lina_i18n.py` (nouveau)
- `api-server/services/lina_patient_reply.py` (nouveau)
- `api-server/middleware/webhook_omnicanal.py` (édité — appel du
  nouveau chemin patient après `receive_message`)
- `api-server/services/lina_tools.py` (édité — `recommandations_format`
  dans `create_social_post_draft`)
- `api-server/tests/test_lina_patient_reply.py` (nouveau)

## Non exécuté dans cet environnement

Les tests ci-dessus n'ont pas pu être lancés avec `pytest` faute d'accès
réseau pour installer les dépendances (`sqlalchemy`, `pytest-asyncio`)
dans le bac à sable de correction. Le code a été vérifié par
compilation (`py_compile`) sur tous les fichiers touchés — à exécuter
avec la suite de tests complète avant mise en recette.
