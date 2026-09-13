# Bloc B — Faits médicaux structurés du patient : livraison exécutée et validée

**Date :** 12 septembre 2026
**Base :** `AC-CLINIC-FINAL-2026-09-12-BLOC-A-FINI` (archive livrée avec Bloc A validé, conservée à l'identique)
**Périmètre exécuté :** Bloc B uniquement — antécédents (médicaux, chirurgicaux, anesthésiques, familiaux), allergies, traitements et contre-indications du patient, en données structurées chiffrées, vérifiables, journalisées dans l'audit médical et réservées au rôle médecin.

## 1. Contenu du Bloc B (fichiers livrés)

| Fichier | Rôle |
|---|---|
| `api-server/alembic/versions/20260910_patient_medical_facts.py` | Migration Alembic `20260910_patient_medical_facts` — table `patients_faits_medicaux` (FK patient/episode/auteur, `type_fait`, `classification`, `donnees_enc` chiffré, `source`, `verification_status`, `actif`, 7 index) |
| `api-server/models/database.py` | Modèle `PatientMedicalFact` (classification `MEDICAL_SENSITIVE`, suppression logique `actif`) |
| `api-server/services/patient_medical_facts.py` | Services : `create_fact`, `list_facts`, `soft_delete_fact` — 7 types autorisés (`antecedent_medical`, `antecedent_chirurgical`, `antecedent_anesthesique`, `antecedent_familial`, `allergie`, `traitement`, `contre_indication`), chiffrement Fernet, garde `require_real_role`, journal `audit_medical` (`CREATE_MEDICAL_FACT`, `READ_MEDICAL_FACTS`, `SOFT_DELETE_MEDICAL_FACT`) |
| `api-server/api/v1/patient_medical_facts.py` | Router FastAPI : `POST/GET/DELETE /api/v1/patients/{patient_id}/medical-facts` — payload `extra="forbid"` (identité d'auteur non injectable par le client) |
| `api-server/api/v1/__init__.py` | Router enregistré : `target.include_router(patient_medical_facts.router)` |
| `api-server/tests/test_bloc_b_medical_facts.py` | 4 tests Bloc A (critères d'acceptation) |
| `services/timeline_patient_global.py` | Intégration : chaque fait actif apparaît dans la chronologie clinique globale (médecin uniquement) |
| `autocommerce-app/client/src/lib/api.ts` | **Ajouté (interface)** : `medicalFactsApi` (`list`, `create`, `delete`) + type `MedicalFactItem` |
| `autocommerce-app/client/src/pages/patients/MedicalFile.tsx` | **Ajouté (interface)** : onglet « Faits médicaux » (liste, désactivation logique avec confirmation), dialog de saisie adaptatif par type de fait (médecin uniquement) |

Chaîne de migrations vérifiée : `20260910_consultations_medicales` (Bloc A) → **`20260910_patient_medical_facts`** → `20260910_prescriptions_medicales` → `20260910_documents_medicaux_patients` (head unique).

## 2. Garanties implémentées

1. **RBAC médical strict** : création, lecture et désactivation réservées au rôle `medecin` ; le garde `require_real_role` revérifie le rôle **réel en base** (pas seulement le JWT) — un rôle dégradé ou falsifié est refusé.
2. **Auteur authentifié** : `auteur_id` est toujours déduit de l'utilisateur connecté ; le payload interdit tout champ d'identité fourni par le client (`extra="forbid"` — testé).
3. **Chiffrement au repos** : `donnees_enc` chiffré via la même clé Fernet que le dossier médical ; déchiffré uniquement à la lecture pour un médecin autorisé.
4. **Suppression logique** : la désactivation masque la donnée sans effacement physique ; l'historique clinique et le journal d'audit médical sont conservés (testé).
5. **Isolation multi-cliniques** : patient ou épisode hors clinique refusé (`ValueError` → 400) ; test cross-tenant inclus.
6. **Traçabilité** : chaque création, lecture et désactivation écrit dans `AuditLogMedical` (IP, user-agent, type de fait).
7. **Frontend** : les faits ne sont chargés que si `user.role === 'medecin'` ; la saisie est refusée visuellement pour les autres rôles et refusée côté serveur de toute façon (défense en profondeur).

## 3. Exécution de validation (réelle, ce build)

| Vérification | Résultat |
|---|---:|
| Tests Bloc B (`pytest tests/test_bloc_b_medical_facts.py -q`) | PASS, 4/4 |
| Tests Bloc B + Bloc A combinés (`-v`) | PASS, 8/8 |
| Suite backend complète (`pytest -q`) | **PASS, 742 réussis, 1 ignoré** |
| Vérification TypeScript (`pnpm check`) | PASS, 0 erreur |
| Tests frontend (`pnpm test`) | **PASS, 13 fichiers, 73/73 réussis** |
| Build frontend production (`pnpm build`) | PASS — bundle `MedicalFile-D7W_J3Xn.js` 78,34 kB généré |

Commandes de reproduction :

```bash
cd api-server
pytest tests/test_bloc_b_medical_facts.py -q   # 4 passed
pytest -q                                       # 742 passed, 1 skipped
alembic upgrade head                            # applique 20260910_patient_medical_facts
alembic downgrade 20260910_consultations_medicales   # rollback : table + index retirés

# Frontend (à la racine autocommerce-app/)
pnpm check   # tsc --noEmit : 0 erreur
pnpm test    # 73 passed
pnpm build   # ✓ built
```

## 4. État des autres blocs

Aucun fichier d'un autre bloc n'a été modifié : Bloc A (consultations structurées), Bloc 1 (épisode patient), Bloc 2 (RBAC), Bloc 3 (agenda/accueil), Bloc 9/10 (Lina), correctif facturation `acte_id` et toutes les migrations existantes sont conservés à l'identique. L'archive reste un livrable complet : **Blocs A + B réalisés et validés**.

## 5. Réserves inchangées

Le verdict de l'audit interne du 12/09/2026 reste applicable : GO pour recette métier contrôlée ; NO-GO pour des données patients réelles tant que le déploiement permanent, la qualification PostgreSQL de staging complète, la conformité RGPD/santé et la gouvernance clinique ne sont pas formellement validés.
