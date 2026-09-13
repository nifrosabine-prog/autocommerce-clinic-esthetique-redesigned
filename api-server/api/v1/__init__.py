"""
AutoCommerce Clinic — composition des frontières API.

La séparation est logique et déployée dans un seul service FastAPI :
- /api/public : passerelle publique sans privilèges cliniques ;
- /api/private : cœur clinique privé ;
- /api/v1 : compatibilité descendante pour les clients déjà déployés.

La passerelle publique ne reçoit que le routeur public explicitement autorisé.
"""

from fastapi import APIRouter

from api.v1 import (
    agenda_clinic, assistant, auth, booking_requests, business_intelligence, commissions, copilote_crm, dashboard_ia,
    depenses_clinic, dossiers_medicaux, consultations_medicales, patient_medical_facts, prescriptions_medicales, documents_medicaux, timeline_patient_global, exports_patient, audit_medical, equipe, factures, fidelite, mfa, omnicanal, patients, recrutement,
    settings as settings_router, public_chat, public_recruitment, recruitment_inbound, absences_praticiens, remplacements_rdv, social, stock_injectable, stock_alerts, workflow_engine, consommables, taches_internes,
    teleconsultation, parrainage, simulation_ia,
            assistant_ia, bi_insights, workflow_extra, qms, scribe_ia, delegues, users,
            salles, pointage, super_admin, clinical_operations, rbac, accueil, workspace, episodes, devis, paiements_episode, notes_episode,

)


def _include_private_routers(target: APIRouter) -> None:
    """Monter uniquement les routes du cœur privé sur un routeur donné."""
    target.include_router(auth.router)
    target.include_router(booking_requests.router)
    target.include_router(assistant.router)
    target.include_router(patients.router)
    target.include_router(factures.router)
    target.include_router(commissions.router)
    target.include_router(fidelite.router)
    target.include_router(recrutement.router)
    target.include_router(absences_praticiens.router)
    target.include_router(taches_internes.router)
    target.include_router(remplacements_rdv.router)
    target.include_router(social.router)
    target.include_router(settings_router.router)
    target.include_router(agenda_clinic.router)
    target.include_router(depenses_clinic.router)
    target.include_router(dossiers_medicaux.router)
    target.include_router(consultations_medicales.router)
    target.include_router(patient_medical_facts.router)
    target.include_router(prescriptions_medicales.router)
    target.include_router(documents_medicaux.router)
    target.include_router(timeline_patient_global.router)
    target.include_router(exports_patient.router)
    target.include_router(audit_medical.router)
    target.include_router(stock_injectable.router)
    target.include_router(stock_alerts.router)
    target.include_router(consommables.router)
    target.include_router(teleconsultation.router)
    target.include_router(parrainage.router)
    target.include_router(mfa.router)
    target.include_router(omnicanal.router)
    target.include_router(dashboard_ia.router)
    target.include_router(workflow_engine.router)
    target.include_router(copilote_crm.router)
    target.include_router(business_intelligence.router)
    target.include_router(equipe.router)
    target.include_router(simulation_ia.router)
    target.include_router(assistant_ia.router)
    target.include_router(bi_insights.router)
    target.include_router(workflow_extra.router)
    target.include_router(qms.router)
    target.include_router(scribe_ia.router)
    target.include_router(delegues.router)
    target.include_router(users.router)
    target.include_router(salles.router)
    target.include_router(pointage.router)
    target.include_router(super_admin.router)
    target.include_router(clinical_operations.router)
    target.include_router(rbac.router)
    target.include_router(accueil.router)
    target.include_router(workspace.router)
    target.include_router(episodes.router)
    target.include_router(devis.router)
    target.include_router(paiements_episode.router)
    target.include_router(notes_episode.router)


# Cœur privé canonique et contrat historique de compatibilité.
private_router = APIRouter(prefix="/api/private")
_include_private_routers(private_router)

api_router = APIRouter(prefix="/api/v1")
_include_private_routers(api_router)

# Public Gateway : seul le sous-routeur explicitement public est monté.
public_gateway_router = APIRouter(prefix="/api/public")
public_gateway_router.include_router(settings_router.public_router)
public_gateway_router.include_router(public_chat.router)
public_gateway_router.include_router(public_recruitment.router)
public_gateway_router.include_router(recruitment_inbound.router)

# Compatibilité descendante pour les landing pages déjà configurées.
legacy_public_gateway_router = APIRouter(prefix="/api/v1/public")
legacy_public_gateway_router.include_router(settings_router.public_router)
legacy_public_gateway_router.include_router(public_chat.router)
legacy_public_gateway_router.include_router(public_recruitment.router)
legacy_public_gateway_router.include_router(recruitment_inbound.router)

# L’application monte ces trois arbres séparément ; public et privé ne partagent
# aucun routeur métier sensible.
root_router = APIRouter()
root_router.include_router(public_gateway_router)
root_router.include_router(private_router)
root_router.include_router(api_router)
root_router.include_router(legacy_public_gateway_router)

# Nom historique conservé pour main.py et les intégrations existantes.
api_router = root_router
