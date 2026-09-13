# Bloc C — Prescriptions médicales sécurisées : livraison exécutée et validée

**Date :** 12 septembre 2026
**Base :** `AC-CLINIC-FINAL-2026-09-12-BLOC-A-B-FINI` (archive livrée avec Blocs A + B validés, conservés à l'identique)
**Périmètre exécuté :** Bloc C uniquement — prescriptions médicales sécurisées, créées exclusivement par un médecin authentifié, rattachées au patient, à l'épisode, à la consultation (Bloc A), à l'intervention et à l'acte, avec détails chiffrés au repos, journal d'audit médical et intégration timeline/export.

## 1. Contenu du Bloc C (fichiers livrés)

| Fichier | Rôle |
|---|---|
| `api-server/alembic/versions/20260910_prescriptions_medicales.py` | Migration Alembic `20260910_prescriptions_medicales` — table `prescriptions_medicales` : FK patient/episode/consultation/intervention/acte/prescripteur, `details_enc` chiffré, `statut` (`ACTIVE`/`CANCELLED`/`COMPLETED`), `classification` (`MEDICAL_SENSITIVE`), 9 index, rollback complet |
| `api-server/models/database.py` | Modèle `PrescriptionMedicale` — « Prescription médicale créée exclusivement par un médecin authentifié » |
| `api-server/services/prescriptions_medicales.py` | Services `create_prescription` / `list_prescriptions` : garde `require_real_role` (rôle réel en base, pas seulement le JWT), validation d'intégrité épisode↔intervention (l'intervention doit appartenir à l'épisode fourni), chiffrement Fernet des détails, prescripteur déduit de l'utilisateur authentifié, journal `audit_medical` (`CREATE_PRESCRIPTION`, `READ_PRESCRIPTIONS`) |
| `api-server/api/v1/prescriptions_medicales.py` | Router : `POST / GET /api/v1/patients/{patient_id}/prescriptions` — payload `extra="forbid"` (identité de prescripteur non injectable par le client), statut contrôlé par pattern |
| `api-server/api/v1/__init__.py` | Router enregistré : `target.include_router(prescriptions_medicales.router)` |
| `api-server/tests/test_bloc_c_prescriptions.py` | 3 tests Bloc C (critères d'acceptation) |
| `services/timeline_patient_global.py` | Intégration : chaque prescription apparaît dans la chronologie clinique globale (`type: PRESCRIPTION`, médecin uniquement) et donc dans l'export structuré/PDF (Bloc F) |
| `autocommerce-app/client/src/lib/api.ts` | **Ajouté (interface)** : `prescriptionsApi` (`list`, `create`) + type `PrescriptionItem` |
| `autocommerce-app/client/src/pages/patients/MedicalFile.tsx` | **Ajouté (interface)** : onglet « Prescriptions » (liste avec statut, dosage/fréquence/durée, date de prescription), dialog de saisie (médicament, dosage, fréquence, durée, instructions — médecin uniquement) |

Chaîne de migrations vérifiée : `20260910_patient_medical_facts` (Bloc B) → **`20260910_prescriptions_medicales`** → `20260910_documents_medicaux_patients` (head unique).

## 2. Garanties implémentées

1. **RBAC médical strict** : création et lecture réservées au rôle `medecin` ; `require_real_role` revérifie le rôle réel en base — un rôle dégradé ou falsifié est refusé (testé).
2. **Prescripteur authentifié** : `prescripteur_id` est toujours déduit de l'utilisateur connecté (vérifié médecin actif de la clinique) ; le payload interdit tout champ d'identité client (`extra="forbid"` — testé avec `prescripteur_id` injecté).
3. **Chiffrement au repos** : `details_enc` (médicament, dosage, fréquence, durée, instructions) chiffré via la même clé Fernet que le dossier médical.
4. **Isolation multi-cliniques** : patient, épisode, intervention ou acte hors clinique refusé ; une intervention doit appartenir à l'épisode déclaré (test cross-tenant inclus).
5. **Traçabilité** : chaque création et lecture écrit dans `AuditLogMedical` (action, patient, IP).
6. **Cohérence clinique** : rattachements optionnels validés (`consultation_id` Bloc A, `intervention_id`, `acte_id`) — jamais de référence orpheline hors clinique.
7. **Frontend** : prescriptions chargées uniquement si `user.role === 'medecin'` ; la saisie est refusée visuellement pour les autres rôles et refusée côté serveur de toute façon (défense en profondeur).

## 3. Exécution de validation (réelle, ce build)

| Vérification | Résultat |
|---|---:|
| Tests Bloc C (`pytest tests/test_bloc_c_prescriptions.py -v`) | PASS, 3/3 |
| Tests Blocs A + B + C combinés (`-q`) | **PASS, 11/11** (3 Bloc C + 4 Bloc B + 4 Bloc A) |
| Suite backend complète (`pytest -q`) | **PASS, 742 réussis, 1 ignoré** |
| Vérification TypeScript (`pnpm check`) | PASS, 0 erreur |
| Tests frontend (`pnpm test`) | **PASS, 13 fichiers, 73/73 réussis** |
| Build frontend production (`pnpm build`) | PASS — bundle `MedicalFile-DQOhyCEr.js` 85,35 kB (16,94 kB gzip) |

Commandes de reproduction :

```bash
cd api-server
pytest tests/test_bloc_c_prescriptions.py -v    # 3 passed
pytest tests/test_bloc_c_prescriptions.py tests/test_bloc_b_medical_facts.py tests/test_bloc_a_consultations.py -q   # 11 passed
pytest -q                                        # 742 passed, 1 skipped
alembic upgrade head                             # applique 20260910_prescriptions_medicales
alembic downgrade 20260910_patient_medical_facts # rollback : table + index retirés

# Frontend (à la racine autocommerce-app/)
pnpm check   # tsc --noEmit : 0 erreur
pnpm test    # 73 passed
pnpm build   # ✓ built
```

## 4. État des autres blocs

Aucun fichier d'un autre bloc n'a été modifié : Bloc A (consultations structurées), Bloc B (faits médicaux), Bloc 1 (épisode patient), Bloc 2 (RBAC), Bloc 3 (agenda/accueil), Bloc 9/10 (Lina), correctif facturation `acte_id` et toutes les migrations existantes sont conservés à l'identique. L'archive reste un livrable complet : **Blocs A + B + C réalisés et validés**.

## 5. Réserves inchangées

Le verdict de l'audit interne du 12/09/2026 reste applicable : GO pour recette métier contrôlée ; NO-GO pour des données patients réelles tant que le déploiement permanent, la qualification PostgreSQL de staging complète, la conformité RGPD/santé et la gouvernance clinique ne sont pas formellement validés.
