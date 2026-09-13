"""Paiements structurés et autorisation de démarrage d'intervention."""
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from api.deps import get_db
from middleware.auth import get_current_active_user
from models.database import Facture
from models.episode_core import Paiement, Intervention, InterventionActe, Devis
from services.access_control import clinic_id_for
from services.rbac_service import assert_intervention_scope, role_of

router = APIRouter(tags=["paiements-episode"])
CASH_ROLES = {"assistante", "directrice", "admin"}

class PaymentCreate(BaseModel):
    montant: Decimal = Field(gt=0)
    mode: str = Field(min_length=2, max_length=50)
    reference: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=500)

@router.post("/factures/{facture_id}/paiements", status_code=201)
async def record_payment(facture_id: int, data: PaymentCreate, current_user=Depends(get_current_active_user), db: AsyncSession=Depends(get_db)):
    if role_of(current_user) not in CASH_ROLES: raise HTTPException(403, "Enregistrement des paiements réservé à l'accueil ou la direction")
    clinic_id = clinic_id_for(current_user)
    invoice = await db.scalar(select(Facture).where(Facture.id == facture_id, Facture.clinic_id == clinic_id))
    if not invoice: raise HTTPException(404, "Facture introuvable")
    if invoice.statut in {"annulee", "remboursee"}: raise HTTPException(409, "Cette facture ne peut plus recevoir de paiement")
    paid = await db.scalar(select(func.coalesce(func.sum(Paiement.montant), 0)).where(Paiement.facture_id == invoice.id, Paiement.clinic_id == clinic_id, Paiement.statut == "enregistre"))
    due = Decimal(str(invoice.total_ttc or 0)) - Decimal(str(paid or 0))
    if data.montant > due: raise HTTPException(400, "Le paiement dépasse le solde dû")
    payment = Paiement(clinic_id=clinic_id, facture_id=invoice.id, montant=data.montant, mode=data.mode, reference=data.reference, notes=data.notes, encaisse_par_id=int(current_user["id"]))
    db.add(payment)
    new_paid = Decimal(str(paid or 0)) + data.montant
    invoice.statut = "payee" if new_paid >= Decimal(str(invoice.total_ttc or 0)) else "partiellement_payee"
    invoice.mode_paiement = data.mode
    await db.commit()
    return {"id": payment.id, "facture_id": invoice.id, "montant": str(data.montant), "solde": str(max(Decimal('0'), due - data.montant)), "statut_facture": invoice.statut}

@router.post("/interventions/{intervention_id}/demarrer")
async def start_intervention(intervention_id: int, current_user=Depends(get_current_active_user), db: AsyncSession=Depends(get_db)):
    intervention = await assert_intervention_scope(db, current_user, intervention_id)
    if intervention.statut == "en_cours": return {"id": intervention.id, "statut": intervention.statut, "idempotent": True}
    if intervention.statut != "planifiee": raise HTTPException(409, "L'intervention n'est pas planifiée")
    acts = (await db.execute(select(InterventionActe).where(InterventionActe.intervention_id == intervention.id))).scalars().all()
    if not acts: raise HTTPException(409, "Aucun acte n'est affecté à cette intervention")
    if any(not act.accepte_medical for act in acts): raise HTTPException(409, "Accord médical manquant pour un acte")
    if any(not act.accepte_financier for act in acts): raise HTTPException(409, "Validation financière manquante pour un acte")
    quote = await db.scalar(select(Devis).where(Devis.episode_id == intervention.episode_id, Devis.statut == "accepte", Devis.clinic_id == intervention.clinic_id))
    if quote:
        invoice = await db.scalar(select(Facture).where(Facture.devis_id == quote.id, Facture.clinic_id == intervention.clinic_id))
        if not invoice or invoice.statut != "payee": raise HTTPException(409, "Paiement requis avant le démarrage")
    intervention.statut = "en_cours"; intervention.demarree_le = datetime.utcnow()
    await db.commit()
    return {"id": intervention.id, "statut": intervention.statut, "demarree_le": intervention.demarree_le.isoformat()}

@router.post("/interventions/{intervention_id}/valider")
async def validate_intervention(intervention_id: int, current_user=Depends(get_current_active_user), db: AsyncSession=Depends(get_db)):
    intervention = await assert_intervention_scope(db, current_user, intervention_id)
    if intervention.statut == "a_valider": return {"id": intervention.id, "statut": intervention.statut, "idempotent": True}
    if intervention.statut != "en_cours": raise HTTPException(409, "Seule une intervention en cours peut être validée")
    intervention.statut = "a_valider"; await db.commit(); return {"id": intervention.id, "statut": intervention.statut}

@router.post("/interventions/{intervention_id}/cloturer")
async def close_intervention(intervention_id: int, current_user=Depends(get_current_active_user), db: AsyncSession=Depends(get_db)):
    intervention = await assert_intervention_scope(db, current_user, intervention_id)
    if intervention.statut == "terminee": return {"id": intervention.id, "statut": intervention.statut, "idempotent": True}
    if intervention.statut != "a_valider": raise HTTPException(409, "L’intervention doit être validée avant sa clôture")
    acts = (await db.execute(select(InterventionActe).where(InterventionActe.intervention_id == intervention.id))).scalars().all()
    if any(not act.realise for act in acts): raise HTTPException(409, "Tous les actes ne sont pas marqués comme réalisés")
    intervention.statut = "terminee"; intervention.terminee_le = datetime.utcnow(); await db.commit()
    return {"id": intervention.id, "statut": intervention.statut, "terminee_le": intervention.terminee_le.isoformat()}
