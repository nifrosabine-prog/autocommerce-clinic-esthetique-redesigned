# Audit réel — points 7 et 8 AutoCommerce Clinic

## Périmètre vérifié

L’audit a été effectué sur l’archive `AC-CLINIC-BLOC-1-2-3-CORRIGE-FINAL.zip`, extraite dans `/home/ubuntu/work_autocommerce`, après lecture du code réel et non à partir du seul prompt.

## Point 7 — Traduction arabe MSA et RTL

L’état effectivement constaté est le suivant : le frontend contient **34 fichiers `.tsx` sous `client/src/pages/`**, mais seuls **2 fichiers** utilisent actuellement `useTranslation` : `public/LandingPage.tsx` et `dashboard/Dashboard.tsx`. Les 32 autres pages suivantes ne le consomment pas :

| Zone | Fichiers non câblés constatés |
|---|---|
| Racine / auth | `Home.tsx`, `NotFound.tsx`, `auth/Login.tsx`, `auth/MfaVerification.tsx` |
| Agenda / accueil | `agenda/AgendaView.tsx`, `accueil/AccueilPatients.tsx` |
| Patients / médical | `patients/MedicalFile.tsx`, `patients/PatientsList.tsx`, `clinical/ClinicalOperationsPage.tsx`, `teleconsultation/TeleconsultationPage.tsx` |
| Finance / stock | `invoices/InvoicesPage.tsx`, `stock/StockPage.tsx`, `commissions/CommissionsPage.tsx`, `loyalty/LoyaltyPage.tsx`, `loyalty/ParrainageSection.tsx` |
| Recrutement / équipe / social | `recruitment/RecruitmentPage.tsx`, `admin/ReportingRH.tsx`, `equipe/EquipeMessages.tsx`, `social/SocialPage.tsx`, `delegues/DeleguesPage.tsx` |
| Administration / paramètres | `admin/RoomsPage.tsx`, `admin/TeamPage.tsx`, `settings/ActesPage.tsx`, `settings/MfaSettings.tsx`, `settings/SettingsPage.tsx`, `super-admin/SuperAdminDashboard.tsx` |
| IA / opérations / workspace | `analytics/BusinessIntelligence.tsx`, `crm/CopiloteCRM.tsx`, `dashboard/DashboardIA.tsx`, `workflow/WorkflowEngine.tsx`, `workspace/WorkspacePage.tsx` |

Les namespaces `nav`, `roles`, `patients`, `agenda`, `stock`, `invoices` et `dashboard` existent bien dans les deux fichiers `client/public/locales/fr/common.json` et `client/public/locales/ar/common.json`. Leur présence ne signifie toutefois pas que les écrans les consomment : l’audit a relevé **315 lignes contenant des caractères français accentués** dans les cinq zones prioritaires agenda, patients, factures, stock et recrutement.

Le composant `LanguageSwitcher.tsx` est présent et monté dans `DashboardLayout`. Il met bien à jour `document.documentElement.lang` et `document.documentElement.dir`, avec `rtl` pour l’arabe. Le fallback `fallbackLng: 'fr'` est présent dans `client/src/i18n/config.ts`. Le câblage global est donc correct, mais **il ne suffit pas** : les pages métier restent majoritairement en chaînes françaises codées en dur. Le point 7 n’est pas considéré terminé.

## Point 8 — Réception automatique des candidatures

### Vérifications préalables

Le service existant `services/omnicanal/email_connector.py` ne faisait que l’envoi Resend. Le middleware `middleware/webhook_omnicanal.py` confirme l’existence d’un pattern webhook multi-canal, mais le flux générique existant ne sait pas traiter les pièces jointes de Resend Inbound.

La documentation Resend actuelle confirme que l’événement `email.received` existe, mais que le webhook contient uniquement les métadonnées. Le corps est récupéré par `GET /emails/receiving/:email_id`, puis une pièce jointe par `GET /emails/receiving/:email_id/attachments/:attachment_id`, qui renvoie une URL de téléchargement temporaire. Resend documente aussi les headers `svix-id`, `svix-timestamp` et `svix-signature`, ainsi que la nécessité d’absorber les livraisons au moins une fois.

Le flux public existant `api/v1/public_recruitment.py` possède déjà la whitelist PDF/DOC/DOCX, la limite de 10 Mo, le stockage UUID sous `uploads/recrutement/<clinic>/<candidature>` et l’extraction vers `cv_texte_extrait`. `RecruitmentPage.tsx` consomme déjà la route de liste privée et affiche les candidatures. `notes_rh` reste réservé aux notes manuelles RH ; le nouveau flux n’y écrit pas.

### Implémentation réalisée

Les fichiers suivants ont été ajoutés ou modifiés :

- `api-server/services/recrutement_inbound.py` : récupération Resend, vérification Svix, résolution de clinique, validation des pièces jointes, téléchargement, stockage UUID, extraction CV, idempotence et absorption des erreurs.
- `api-server/api/v1/recruitment_inbound.py` : endpoint `POST /api/public/recrutement/inbound/resend`, monté aussi sur le chemin legacy `/api/v1/public/recrutement/inbound/resend`.
- `api-server/api/v1/__init__.py` : enregistrement du routeur sur les deux passerelles publiques.
- `api-server/config.py` : ajout de `recruitment_inbound_email`, `recruitment_inbound_clinic_id` et `resend_webhook_signing_secret`.
- `api-server/models/database.py` : ajout de `Candidature.source_email_id` pour absorber les retries Resend/Svix.
- `api-server/alembic/versions/20260913_add_recruitment_inbound_source.py` : migration du champ source avec contrainte unique.

Un e-mail sans pièce jointe CV supportée, un expéditeur sans adresse exploitable, un destinataire ne permettant pas de résoudre une clinique ou une erreur de téléchargement sont ignorés et journalisés sans faire échouer l’accusé de réception HTTP. Une candidature créée utilise le statut existant `RECU`, son texte extrait est stocké dans `cv_texte_extrait`, et elle apparaît dans l’écran Recrutement via le mécanisme frontend déjà présent.

## Points de vigilance et décisions de configuration

Le déploiement doit renseigner `RESEND_API_KEY`, `RESEND_WEBHOOK_SIGNING_SECRET`, `RECRUITMENT_INBOUND_EMAIL`, `RECRUITMENT_INBOUND_CLINIC_ID` et activer `WEBHOOKS_ENABLED`. Le mapping de clinique est volontairement explicite ; il n’est pas déduit de l’adresse de l’expéditeur. En environnement mono-clinique, `PUBLIC_CLINIC_ID` peut servir de repli si `RECRUITMENT_INBOUND_CLINIC_ID` n’est pas défini.

La chaîne Alembic contient déjà plusieurs branches dans l’archive d’après les `down_revision` divergentes constatées dans les fichiers. La migration ajoutée suit explicitement `20260912_add_cv_texte_extrait`, migration cohérente avec la modification de `Candidature`; elle ne tente pas de réparer les autres têtes.

## Validation effectuée

La compilation syntaxique Python des nouveaux fichiers et des fichiers modifiés a réussi avec `python3 -m py_compile`. Les contrôles TypeScript n’ont pas pu être lancés car `autocommerce-app/node_modules` n’est pas présent dans l’archive. Le chargement complet de l’application n’a pas pu être exécuté dans cette sandbox, car les dépendances Python du backend, notamment SQLAlchemy, ne sont pas installées. La migration et l’endpoint doivent donc encore être testés dans l’environnement de déploiement avec les dépendances et une base réelle ou de test.

## Consigne de travail à conserver

**Toujours vérifier le code réel avant de coder.** Pour chaque point, commencer par `grep`/`rg`, lire les routes, modèles, services, migrations et composants d’affichage concernés, puis vérifier le trajet complet écriture base → route de lecture → rendu frontend. Ne jamais remplir uniquement les traductions sans câbler `useTranslation`, ne jamais confondre `cv_texte_extrait` et `notes_rh`, et ne jamais considérer une écriture base comme terminée tant que la donnée n’est pas lisible et visible par le staff.
