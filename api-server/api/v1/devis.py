"""Devis globaux d'épisode : séparés des factures et convertibles une seule fois."""
from datetime import datetime
from uuid import uuid4
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from api.deps import get_db
from middleware.auth import get_current_active_user
from models.database import DossierMedical, Facture
from models.episode_core import Devis, DevisLigne, EpisodePatient, FactureLigne, InterventionActe, StatutDevis
from services.access_control import clinic_id_for

router = APIRouter(prefix="/devis", tags=["devis"])
MANAGE = {"assistante", "directrice", "admin"}


def role(user: dict) -> str: return str(user.get("role", "")).replace("RoleEnum.", "").lower()

class QuoteLine(BaseModel):
    intervention_acte_id: int
    description: str = Field(min_length=1, max_length=300)
    quantite: int = Field(default=1, ge=1)
    prix_unitaire: Decimal = Field(ge=0)
    remise_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)

class QuoteCreate(BaseModel):
    episode_id: int
    dossier_id: int
    validite_jours: int = Field(default=30, ge=1, le=365)
    lignes: list[QuoteLine] = Field(min_length=1, max_length=100)

async def get_quote(db, quote_id, user):
    q = await db.scalar(select(Devis).where(Devis.id == quote_id, Devis.clinic_id == clinic_id_for(user)))
    if not q: raise HTTPException(404, "Devis introuvable")
    return q

def serialize(q, lines):
    return {"id": q.id, "episode_id": q.episode_id, "dossier_id": q.dossier_id, "numero_devis": q.numero_devis, "version": q.version, "statut": q.statut, "validite_jours": q.validite_jours, "created_at": q.created_at.isoformat(), "lignes": [{"id": l.id, "intervention_acte_id": l.intervention_acte_id, "description": l.description, "quantite": l.quantite, "prix_unitaire": str(l.prix_unitaire), "remise_pct": str(l.remise_pct), "total": str((l.prix_unitaire * l.quantite) * (Decimal('1') - l.remise_pct / Decimal('100'))), "acceptee": l.acceptee} for l in lines]}

@router.post("", status_code=201)
async def create_quote(data: QuoteCreate, current_user=Depends(get_current_active_user), db: AsyncSession=Depends(get_db)):
    if role(current_user) not in MANAGE: raise HTTPException(403, "Création de devis réservée à l'accueil ou la direction")
    clinic_id = clinic_id_for(current_user)
    episode = await db.scalar(select(EpisodePatient).where(EpisodePatient.id == data.episode_id, EpisodePatient.clinic_id == clinic_id))
    if not episode: raise HTTPException(404, "Épisode introuvable")
    dossier = await db.scalar(select(DossierMedical).where(
        DossierMedical.id == data.dossier_id,
        DossierMedical.patient_id == episode.patient_id,
        DossierMedical.clinic_id == clinic_id,
    ))
    if not dossier: raise HTTPException(400, "Le dossier patient doit appartenir au patient et à la clinique de l'épisode")
    # Un suffixe aléatoire court évite les collisions entre requêtes concurrentes
    # et entre cliniques, contrairement à count()+1.
    number = f"DEV-{datetime.utcnow():%Y%m%d}-{uuid4().hex[:10].upper()}"
    q = Devis(clinic_id=clinic_id, episode_id=episode.id, dossier_id=dossier.id, numero_devis=number, cree_par_id=int(current_user["id"]), validite_jours=data.validite_jours)
    db.add(q); await db.flush()
    for item in data.lignes:
        act = await db.scalar(select(InterventionActe).join(InterventionActe.intervention).where(InterventionActe.id == item.intervention_acte_id, InterventionActe.clinic_id == clinic_id, InterventionActe.intervention.has(episode_id=episode.id)))
        if not act: raise HTTPException(400, f"Acte {item.intervention_acte_id} absent de l'épisode")
        db.add(DevisLigne(devis_id=q.id, intervention_acte_id=act.id, description=item.description, quantite=item.quantite, prix_unitaire=item.prix_unitaire, remise_pct=item.remise_pct))
    await db.commit()
    lines = (await db.execute(select(DevisLigne).where(DevisLigne.devis_id == q.id))).scalars().all()
    return serialize(q, lines)

@router.get("/{quote_id}")
async def get_quote_route(quote_id: int, current_user=Depends(get_current_active_user), db: AsyncSession=Depends(get_db)):
    q = await get_quote(db, quote_id, current_user); lines = (await db.execute(select(DevisLigne).where(DevisLigne.devis_id == q.id))).scalars().all(); return serialize(q, lines)

@router.post("/{quote_id}/envoyer")
async def send_quote(quote_id: int, current_user=Depends(get_current_active_user), db: AsyncSession=Depends(get_db)):
    if role(current_user) not in MANAGE: raise HTTPException(403, "Droit insuffisant")
    q = await get_quote(db, quote_id, current_user)
    if q.statut != StatutDevis.BROUILLON.value: raise HTTPException(409, "Seul un devis brouillon peut être envoyé")
    q.statut = StatutDevis.ENVOYE.value; q.envoye_le = datetime.utcnow(); await db.commit(); return {"id": q.id, "statut": q.statut}

@router.post("/{quote_id}/accepter")
async def accept_quote(quote_id: int, current_user=Depends(get_current_active_user), db: AsyncSession=Depends(get_db)):
    if role(current_user) not in MANAGE: raise HTTPException(403, "Validation financière réservée à l'accueil ou la direction")
    q = await get_quote(db, quote_id, current_user)
    if q.statut != StatutDevis.ENVOYE.value: raise HTTPException(409, "Ce devis n'est pas envoyable à l'acceptation")
    q.statut = StatutDevis.ACCEPTE.value; q.reponse_le = datetime.utcnow()
    lines = (await db.execute(select(DevisLigne).where(DevisLigne.devis_id == q.id))).scalars().all()
    for line in lines: line.acceptee = True
    await db.commit(); return {"id": q.id, "statut": q.statut}

@router.post("/{quote_id}/refuser")
async def refuse_quote(quote_id: int, current_user=Depends(get_current_active_user), db: AsyncSession=Depends(get_db)):
    if role(current_user) not in MANAGE: raise HTTPException(403, "Validation financière réservée à l'accueil ou la direction")
    q = await get_quote(db, quote_id, current_user)
    if q.statut != StatutDevis.ENVOYE.value: raise HTTPException(409, "Seul un devis envoyé peut être refusé")
    q.statut = StatutDevis.REFUSE.value; q.reponse_le = datetime.utcnow(); await db.commit()
    return {"id": q.id, "statut": q.statut}

@router.post("/{quote_id}/version", status_code=201)
async def version_quote(quote_id: int, current_user=Depends(get_current_active_user), db: AsyncSession=Depends(get_db)):
    if role(current_user) not in MANAGE: raise HTTPException(403, "Droit insuffisant")
    source = await get_quote(db, quote_id, current_user)
    if source.statut not in {StatutDevis.REFUSE.value, StatutDevis.EXPIRE.value}:
        raise HTTPException(409, "Une nouvelle version ne peut remplacer qu'un devis refusé ou expiré")
    lines = (await db.execute(select(DevisLigne).where(DevisLigne.devis_id == source.id))).scalars().all()
    next_version = int(source.version or 1) + 1
    q = Devis(clinic_id=source.clinic_id, episode_id=source.episode_id, dossier_id=source.dossier_id, numero_devis=f"DEV-{datetime.utcnow():%Y%m%d}-{uuid4().hex[:10].upper()}", cree_par_id=int(current_user["id"]), validite_jours=source.validite_jours, version=next_version, devis_parent_id=source.id, remplace_devis_id=source.id)
    db.add(q); await db.flush()
    for line in lines:
        db.add(DevisLigne(devis_id=q.id, intervention_acte_id=line.intervention_acte_id, description=line.description, quantite=line.quantite, prix_unitaire=line.prix_unitaire, remise_pct=line.remise_pct))
    await db.commit()
    return {"id": q.id, "statut": q.statut, "version": q.version, "devis_parent_id": source.id}

@router.post("/{quote_id}/convertir-facture", status_code=201)
async def convert_quote(quote_id: int, current_user=Depends(get_current_active_user), db: AsyncSession=Depends(get_db)):
    if role(current_user) not in MANAGE: raise HTTPException(403, "Conversion réservée à l'accueil ou la direction")
    q = await get_quote(db, quote_id, current_user)
    if q.statut != StatutDevis.ACCEPTE.value: raise HTTPException(409, "Un devis refusé, expiré ou non accepté ne peut pas être converti")
    existing = await db.scalar(select(Facture).where(Facture.devis_id == q.id, Facture.clinic_id == q.clinic_id))
    if existing: return {"id": existing.id, "numero_facture": existing.numero_facture, "statut": existing.statut, "idempotent": True}
    lines = (await db.execute(select(DevisLigne).where(DevisLigne.devis_id == q.id))).scalars().all()
    subtotal = sum((line.prix_unitaire * line.quantite * (Decimal('1') - line.remise_pct / Decimal('100')) for line in lines), Decimal('0'))
    taux_tva = Decimal("0.190")
    montant_tva = (subtotal * taux_tva).quantize(Decimal("0.001"))
    total_ttc = subtotal + montant_tva
    number = f"FAC-{datetime.utcnow():%Y%m%d}-{q.id:06d}"
    invoice = Facture(clinic_id=q.clinic_id, patient_id=(await db.scalar(select(EpisodePatient.patient_id).where(EpisodePatient.id == q.episode_id))), dossier_id=q.dossier_id, devis_id=q.id, numero_facture=number, sous_total=subtotal, taux_tva=taux_tva, montant_tva=montant_tva, total_ttc=total_ttc, statut="brouillon", created_by=int(current_user["id"]))
    db.add(invoice); await db.flush()
    for line in lines: db.add(FactureLigne(facture_id=invoice.id, intervention_acte_id=line.intervention_acte_id, description=line.description, quantite=line.quantite, prix_unitaire=line.prix_unitaire, remise_pct=line.remise_pct, montant_ligne=line.prix_unitaire * line.quantite * (Decimal('1') - line.remise_pct / Decimal('100'))))
    await db.commit(); return {"id": invoice.id, "numero_facture": invoice.numero_facture, "statut": invoice.statut, "devis_id": q.id}
