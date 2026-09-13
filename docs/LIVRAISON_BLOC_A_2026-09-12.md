# Bloc A — Consultations médicales structurées : livraison exécutée et validée

**Date :** 12 septembre 2026
**Base :** `AC-CLINIC-FINAL-2026-09-12-CORRIGE` (archive complète, tous les blocs conservés)
**Périmètre exécuté :** Bloc A uniquement — consultation médicale structurée, rattachée au patient, à l'épisode (Bloc 1) et au rendez-vous, avec chiffrement des champs cliniques, journal d'audit médical et RBAC strict.

## 1. Contenu du Bloc A (fichiers livrés)

| Fichier | Rôle |
|---|---|
| `api-server/alembic/versions/20260910_consultations_medicales.py` | Migration Alembic `20260910_consultations_medicales` (table `consultations_medicales` : 21 champs cliniques chiffrés `_enc`, FK patient/episode/rdv/auteur, 8 index) |
| `api-server/models/database.py` | Modèle `ConsultationMedicale` (champs `*_enc` chiffrés Fernet) |
| `api-server/services/consultations_medicales.py` | Services CRUD : création, lecture, liste, mise à jour ; auteur authentifié non falsifiable ; isolation multi-cliniques ; chiffrement/déchiffrement ; journal `audit_medical` (CREATE/READ/READS/UPDATE) |
| `api-server/api/v1/consultations_medicales.py` | Router FastAPI : `POST/GET/PATCH /api/v1/patients/{patient_id}/consultations` — payload `extra="forbid"` (l'identité de l'auteur ne peut pas être injectée par le client) |
| `api-server/api/v1/__init__.py` | Router enregistré : `target.include_router(consultations_medicales.router)` |
| `api-server/tests/test_bloc_a_consultations.py` | 4 tests Bloc A (critères d'acceptation) |

Chaîne de migrations vérifiée : `20260910_devis_dossier_link` → **`20260910_consultations_medicales`** → `20260910_patient_medical_facts` → `20260910_prescriptions_medicales` → `20260910_documents_medicaux_patients` (head unique).

## 2. Garanties implémentées

1. **RBAC médical** : seule la rôle `medecin` peut créer, lire, lister et modifier une consultation. Toute autre route renvoie `403`.
2. **Auteur authentifié** : `auteur_id` est toujours celui de l'utilisateur connecté (rôle médecin vérifié actif de la clinique) ; le payload interdit le champ auteur (`extra="forbid"` — testé).
3. **Confidentialité multi-cliniques** : patient, épisode et rendez-vous hors clinique refusés (`ValueError` → 400) ; test d'isolation cross-tenant inclus.
4. **Chiffrement au repos** : les 21 champs cliniques (motif, diagnostic, plan thérapeutique, risques, etc.) sont stockés chiffrés (`*_enc`) via la même clé Fernet que le dossier médical.
5. **Audit médical** : chaque création, lecture et modification écrit dans `AuditLogMedical` (action, utilisateur, patient, IP, user-agent, épisode).
6. **Statuts contrôlés** : `brouillon | validee | archivee` (validation Pydantic `pattern`).

## 3. Exécution de validation (réelle, ce build)

| Vérification | Résultat |
|---|---:|
| Compilation Python complète (`compileall`) | PASS, 0 erreur |
| Graphe Alembic : head unique `20260910_documents_medicaux_patients` | PASS |
| Tests Bloc A (`pytest tests/test_bloc_a_consultations.py -q`) | PASS, 4/4 |
| Suite backend complète (`pytest -q`) | **PASS, 742 réussis, 1 ignoré** |
| Correctif facturation `acte_id` (section 16 de l'audit) présent backend + frontend (`InvoicesPage.tsx`, `dossiers_medicaux.py`) | PASS |

Commandes de reproduction :

```bash
cd api-server
pytest tests/test_bloc_a_consultations.py -q   # 4 passed
pytest -q                                       # 742 passed, 1 skipped
alembic upgrade head                            # applique 20260910_consultations_medicales
alembic downgrade 20260910_devis_dossier_link   # rollback : table + index retirés
```

## 4. État des autres blocs

Aucun fichier d'un autre bloc n'a été modifié : Bloc 1 (épisode patient), Bloc 2 (RBAC), Bloc 3 (agenda/accueil), Bloc 8b, Bloc 9/10 (Lina), correctif facturation `acte_id` (section 16 de l'audit du 12/09) et toutes les migrations existantes sont conservés à l'identique. L'archive reste un livrable complet.

## 5. Réserves inchangées

Le verdict de l'audit interne du 12/09/2026 reste applicable : GO pour recette métier contrôlée ; NO-GO pour des données patients réelles tant que le déploiement permanent, la qualification PostgreSQL de staging complète, la conformité RGPD/santé et la gouvernance clinique ne sont pas formellement validés.
