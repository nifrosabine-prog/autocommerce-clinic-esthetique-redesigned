"""
AutoCommerce Clinic — Gestion stock injectables
Scan, traçabilité, alertes, utilisation, réceptions, registre de mouvements
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from models.database import (
    LotInjectable,
    ProduitInjectable,
    UtilisationLot,
    StatutLot,
    Utilisateur,
    Patient,
    DossierMedical,
    MouvementLotInjectable,
    TypeMouvementLot,
)
from services.qr_injectable import decode_scan
from services.tenant_scope import resolve_clinic_id
from services.stock_alerts import sync_stock_alert
from models.episode_core import Intervention


def _resolve_usage_datetime(date_injection: Optional[datetime]) -> datetime:
    """Garantit une date d'utilisation non nulle pour la traçabilité.

    Correctif Bug #3 (audit): quand le front n'envoie pas de
    ``date_injection`` explicite, l'enregistrement doit prendre la date
    UTC courante afin de satisfaire la contrainte NOT NULL sur
    ``utilisations_lot.date_utilisation`` et préserver la traçabilité
    temporelle.
    """
    return date_injection if date_injection is not None else datetime.utcnow()


# ── Dataclasses ────────────────────────────────────────────

@dataclass
class LotDetail:
    lot_id: int
    produit_nom: str
    fabricant: Optional[str]
    numero_lot: str
    quantite_restante: Decimal
    unite: str
    date_expiration: date
    statut: str
    jours_avant_expiration: int

    stock_minimum: Decimal
    stock_alerte: Decimal


@dataclass
class StockAlert:
    niveau: str  # "rouge" | "orange" | "vert"
    produit_nom: str
    numero_lot: str
    message: str
    lot_id: int


# ── Scan & recherche lot ─────────────────────────────────

async def get_lot_by_scan(
    code_str: str,
    db: AsyncSession,
    clinic_id: Optional[int] = None,
) -> LotDetail:
    """Recherche un lot par scan (QR JSON ou Code 128)."""
    clinic_id = resolve_clinic_id(clinic_id)
    decoded = decode_scan(code_str)

    if decoded["type"] == "qr_json":
        lot_id = decoded["data"].get("lot_id")
        if not lot_id:
            raise ValueError("QR code sans lot_id")
        result = await db.execute(
            select(LotInjectable, ProduitInjectable)
            .join(ProduitInjectable, LotInjectable.produit_id == ProduitInjectable.id)
            .where(
                LotInjectable.id == lot_id,
                LotInjectable.clinic_id == clinic_id,
                ProduitInjectable.clinic_id == clinic_id,
            )
        )
    elif decoded["type"] == "barcode":
        numero_lot = decoded["numero_lot"]
        result = await db.execute(
            select(LotInjectable, ProduitInjectable)
            .join(ProduitInjectable, LotInjectable.produit_id == ProduitInjectable.id)
            .where(
                LotInjectable.numero_lot == numero_lot,
                LotInjectable.clinic_id == clinic_id,
                ProduitInjectable.clinic_id == clinic_id,
            )
        )
    else:
        raise ValueError(f"Format de scan non reconnu : {decoded.get('raw', code_str)}")

    row = result.first()
    if not row:
        raise ValueError("Lot non trouvé")

    lot, produit = row
    jours = (lot.date_expiration - date.today()).days

    return LotDetail(
        lot_id=lot.id,
        produit_nom=produit.nom,
        fabricant=produit.fabricant,
        numero_lot=lot.numero_lot,
        quantite_restante=lot.quantite_restante,
        unite=produit.unite,
        date_expiration=lot.date_expiration,
        statut=lot.statut,
        jours_avant_expiration=jours,
        stock_minimum=produit.stock_minimum,
        stock_alerte=produit.stock_alerte,
    )


# ── Enregistrement utilisation ────────────────────────────

async def register_usage(
    lot_id: int,
    dossier_id: Optional[int],
    patient_id: int,
    praticien_id: int,
    quantite: Decimal,
    unite: str,
    db: AsyncSession,
    type_injection: Optional[str] = None,
    date_injection: Optional[datetime] = None,
    notes: Optional[str] = None,
    clinic_id: Optional[int] = None,
    episode_id: Optional[int] = None,
    intervention_id: Optional[int] = None,
) -> UtilisationLot:
    """Débite le stock d'un lot et crée une utilisation.

    Vérifie :
    - Lot existe et disponible
    - Quantité suffisante (avec verrou pessimiste anti race-condition)
    - Lot non expiré
    - Quant strictement positive

    Correctif Bug #1 (audit) :
    - Cast strict Decimal(str(quantite)) pour éviter la propagation d'un
      float depuis Pydantic (perte de précision arithmétique).
    - Verrou pessimiste ``SELECT ... FOR UPDATE`` sur la ligne du lot
      pour sérialiser les décrémentations concurrentes.
    - Décrémentation via nouvelle valeur ``Decimal`` recalculée (pas
      d'opérateur ``-=`` sur un attribut ORM potentiellement partagé).
    - Ordre transactionnel sûr : mutation du lot -> flush -> ajout de
      l'UtilisationLot -> flush -> refresh, avec rollback implicite
      via l'exception si le flush échoue (rien n'est persisté à moitié).
    - Vérification post-décrémentation que ``quantite_restante >= 0``.
    """
    clinic_id = resolve_clinic_id(clinic_id)

    # ── 1. Validation stricte des entrées ─────────────────────
    try:
        quantite = Decimal(str(quantite))
    except (ArithmeticError, ValueError, TypeError) as exc:
        raise ValueError(f"Quantité invalide : {quantite!r}") from exc

    if quantite <= 0:
        raise ValueError(
            f"Quantité doit être strictement positive (reçu : {quantite})"
        )

    # ── 2. Chargement du lot avec verrou pessimiste ───────────
    result = await db.execute(
        select(LotInjectable, ProduitInjectable)
        .join(ProduitInjectable, LotInjectable.produit_id == ProduitInjectable.id)
        .where(
            LotInjectable.id == lot_id,
            LotInjectable.clinic_id == clinic_id,
            ProduitInjectable.clinic_id == clinic_id,
        )
        .with_for_update(of=LotInjectable)
    )
    row = result.first()
    if not row:
        raise ValueError(f"Lot {lot_id} non trouvé")

    lot, produit = row

    patient = await db.scalar(select(Patient).where(
        Patient.id == patient_id,
        Patient.clinic_id == clinic_id,
    ))
    praticien = await db.scalar(select(Utilisateur).where(
        Utilisateur.id == praticien_id,
        Utilisateur.clinic_id == clinic_id,
    ))
    if not patient or not praticien:
        raise ValueError("Patient ou praticien hors clinique")
    if dossier_id is not None:
        dossier = await db.scalar(select(DossierMedical).where(
            DossierMedical.id == dossier_id,
            DossierMedical.clinic_id == clinic_id,
            DossierMedical.patient_id == patient_id,
        ))
        if not dossier:
            raise ValueError("Dossier hors clinique ou patient incohérent")
        if episode_id is None:
            episode_id = dossier.episode_id
        elif dossier.episode_id is not None and dossier.episode_id != episode_id:
            raise ValueError("Le dossier et l'épisode ne correspondent pas")

    if intervention_id is not None:
        intervention = await db.scalar(select(Intervention).where(
            Intervention.id == intervention_id,
            Intervention.clinic_id == clinic_id,
            Intervention.episode_id == episode_id,
            Intervention.professionnel_id == praticien_id,
        ))
        if not intervention:
            raise ValueError("Intervention hors épisode, clinique ou praticien")

    # ── 3. Vérifications métier ───────────────────────────────
    if lot.statut in (StatutLot.EPUISE.value, StatutLot.EXPIRE.value, StatutLot.RETIRE.value):
        raise ValueError(f"Lot indisponible (statut: {lot.statut})")

    if lot.date_expiration < date.today():
        lot.statut = StatutLot.EXPIRE.value
        await db.flush()
        raise ValueError("Lot expiré — utilisation impossible")

    stock_actuel = Decimal(str(lot.quantite_restante))

    if stock_actuel < quantite:
        raise ValueError(
            f"Stock insuffisant : {stock_actuel} {produit.unite} disponible, "
            f"{quantite} {unite} demandé"
        )

    # ── 4. Débit atomique ─────────────────────────────────────
    nouveau_stock = stock_actuel - quantite

    if nouveau_stock < 0:
        raise ValueError(
            f"Stock insuffisant après vérification concurrente : "
            f"{stock_actuel} - {quantite} = {nouveau_stock}"
        )

    lot.quantite_restante = nouveau_stock

    if nouveau_stock == 0:
        lot.quantite_restante = Decimal("0.00")
        lot.statut = StatutLot.EPUISE.value
    elif nouveau_stock <= Decimal(str(produit.stock_minimum)):
        lot.statut = StatutLot.QUARANTAINE.value

    await db.flush()

    # ── 5. Création de l'utilisation ──────────────────────────
    usage_datetime = _resolve_usage_datetime(date_injection)

    prochaine_date = None
    if produit.duree_effet_jours and produit.duree_effet_jours > 0:
        prochaine_date = (usage_datetime + timedelta(days=produit.duree_effet_jours)).date()

    utilisation = UtilisationLot(
        clinic_id=lot.clinic_id,
        lot_id=lot_id,
        dossier_id=dossier_id,
        patient_id=patient_id,
        episode_id=episode_id,
        intervention_id=intervention_id,
        praticien_id=praticien_id,
        date_utilisation=usage_datetime,
        quantite_utilisee=quantite,
        unite=unite,
        type_injection=type_injection,
        notes=notes,
        prochaine_injection_date=prochaine_date,
        prochaine_injection_envoyee=False,
    )
    db.add(utilisation)
    await db.flush()
    await db.refresh(utilisation)

    # ── 6. Journalisation du mouvement (registre d'audit) ─────
    mouvement = MouvementLotInjectable(
        clinic_id=lot.clinic_id,
        lot_id=lot_id,
        type_mouvement=TypeMouvementLot.INJECTION.value,
        quantite=-quantite,
        date_mouvement=usage_datetime,
        utilisateur_id=praticien_id,
        motif=type_injection or "Injection",
    )
    db.add(mouvement)
    await db.flush()
    await db.refresh(mouvement)

    # ── 7. Alertes post-utilisation ───────────────────────────
    await _check_single_lot_alert(lot, produit, db)

    return utilisation


async def _check_single_lot_alert(lot: LotInjectable, produit: ProduitInjectable, db: AsyncSession):
    """Vérifie si une alerte doit être déclenchée après utilisation."""
    return await sync_stock_alert(
        db, clinic_id=lot.clinic_id, type_article="injectable",
        article_nom=produit.nom, stock_actuel=lot.quantite_restante,
        seuil_alerte=produit.stock_alerte, stock_minimum=produit.stock_minimum,
        produit_id=produit.id, lot_id=lot.id,
    )


# ── Réception / réapprovisionnement ───────────────────────

async def _recompute_lot_statut(lot: LotInjectable, produit: ProduitInjectable) -> None:
    """Recalcule le statut du lot après un mouvement de stock.

    - stock ≤ 0 → épuisé
    - stock ≤ stock_minimum → quarantaine
    - sinon → disponible (sauf expiration déjà passée)
    """
    if lot.date_expiration < date.today():
        lot.statut = StatutLot.EXPIRE.value
        return
    stock = Decimal(str(lot.quantite_restante))
    if stock <= 0:
        lot.statut = StatutLot.EPUISE.value
    elif stock <= Decimal(str(produit.stock_minimum)):
        lot.statut = StatutLot.QUARANTAINE.value
    else:
        lot.statut = StatutLot.DISPONIBLE.value


async def register_reception(
    lot_id: int,
    quantite: Decimal,
    db: AsyncSession,
    utilisateur_id: Optional[int] = None,
    motif: Optional[str] = None,
    reference: Optional[str] = None,
    document_url: Optional[str] = None,
    date_expiration: Optional[date] = None,
    fournisseur: Optional[str] = None,
    prix_achat_lot: Optional[Decimal] = None,
    clinic_id: Optional[int] = None,
) -> MouvementLotInjectable:
    """Crédite le stock d'un lot existant et journalise une réception.

    Évolution « Ajouter du stock / Réception » au scan :
    - verrou pessimiste ``FOR UPDATE`` pour sérialiser le crédit ;
    - recalcul du statut (réactivation d'un lot épuisé, quarantaine sous le seuil) ;
    - un lot ``retiré`` (rappel) ne peut jamais être réapprovisionné ;
    - un lot ``expiré`` n'est réactivé que si une nouvelle date d'expiration
      valide est fournie.
    """
    clinic_id = resolve_clinic_id(clinic_id)
    try:
        quantite = Decimal(str(quantite))
    except (ArithmeticError, ValueError, TypeError) as exc:
        raise ValueError(f"Quantité invalide : {quantite!r}") from exc

    if quantite <= 0:
        raise ValueError("La quantité reçue doit être strictement positive")

    result = await db.execute(
        select(LotInjectable, ProduitInjectable)
        .join(ProduitInjectable, LotInjectable.produit_id == ProduitInjectable.id)
        .where(
            LotInjectable.id == lot_id,
            LotInjectable.clinic_id == clinic_id,
            ProduitInjectable.clinic_id == clinic_id,
        )
        .with_for_update(of=LotInjectable)
    )
    row = result.first()
    if not row:
        raise ValueError(f"Lot {lot_id} non trouvé")

    lot, produit = row

    if lot.statut == StatutLot.RETIRE.value:
        raise ValueError("Lot retiré (rappel) — réapprovisionnement impossible")

    nouvelle_expiration = lot.date_expiration
    if date_expiration is not None:
        nouvelle_expiration = date_expiration
        if nouvelle_expiration < date.today():
            raise ValueError("La date d'expiration doit être dans le futur")

    if lot.date_expiration < date.today() and date_expiration is None:
        raise ValueError(
            "Lot expiré — fournir une nouvelle date d'expiration pour la réception"
        )

    if fournisseur is not None:
        lot.fournisseur = fournisseur
    if prix_achat_lot is not None:
        try:
            lot.prix_achat_lot = Decimal(str(prix_achat_lot))
        except (ArithmeticError, ValueError, TypeError):
            raise ValueError("Prix d'achat invalide")
    if nouvelle_expiration != lot.date_expiration:
        lot.date_expiration = nouvelle_expiration

    stock_actuel = Decimal(str(lot.quantite_restante))
    lot.quantite_restante = stock_actuel + quantite
    await _recompute_lot_statut(lot, produit)
    await db.flush()

    mouvement = MouvementLotInjectable(
        clinic_id=clinic_id,
        lot_id=lot_id,
        type_mouvement=TypeMouvementLot.RECEPTION.value,
        quantite=quantite,
        date_mouvement=datetime.utcnow(),
        utilisateur_id=utilisateur_id,
        motif=motif,
        reference=reference,
        document_url=document_url,
    )
    db.add(mouvement)
    await db.flush()
    await db.refresh(mouvement)
    await _check_single_lot_alert(lot, produit, db)
    return mouvement


# ── Registre des mouvements ────────────────────────────────

def _mouvement_to_dict(mvt: MouvementLotInjectable, lot: LotInjectable, produit: ProduitInjectable) -> dict:
    return {
        "mouvement_id": mvt.id,
        "lot_id": mvt.lot_id,
        "produit_nom": produit.nom,
        "numero_lot": lot.numero_lot,
        "type_mouvement": mvt.type_mouvement,
        "quantite": float(mvt.quantite),
        "date_mouvement": mvt.date_mouvement.isoformat(),
        "utilisateur_id": mvt.utilisateur_id,
        "motif": mvt.motif,
        "reference": mvt.reference,
    }


async def get_lot_mouvements(
    lot_id: int,
    db: AsyncSession,
    clinic_id: Optional[int] = None,
    limit: int = 50,
) -> List[dict]:
    """Retourne l'historique des mouvements d'un lot donné (plus récent d'abord)."""
    clinic_id = resolve_clinic_id(clinic_id)
    result = await db.execute(
        select(MouvementLotInjectable, LotInjectable, ProduitInjectable)
        .join(LotInjectable, MouvementLotInjectable.lot_id == LotInjectable.id)
        .join(ProduitInjectable, LotInjectable.produit_id == ProduitInjectable.id)
        .where(
            MouvementLotInjectable.clinic_id == clinic_id,
            MouvementLotInjectable.lot_id == lot_id,
        )
        .order_by(MouvementLotInjectable.date_mouvement.desc())
        .limit(limit)
    )
    return [_mouvement_to_dict(m, lot, prod) for m, lot, prod in result.all()]


async def get_recent_mouvements(
    db: AsyncSession,
    clinic_id: Optional[int] = None,
    limit: int = 12,
) -> List[dict]:
    """Retourne les derniers mouvements de stock de la clinique (registre d'audit)."""
    clinic_id = resolve_clinic_id(clinic_id)
    result = await db.execute(
        select(MouvementLotInjectable, LotInjectable, ProduitInjectable)
        .join(LotInjectable, MouvementLotInjectable.lot_id == LotInjectable.id)
        .join(ProduitInjectable, LotInjectable.produit_id == ProduitInjectable.id)
        .where(MouvementLotInjectable.clinic_id == clinic_id)
        .order_by(MouvementLotInjectable.date_mouvement.desc())
        .limit(limit)
    )
    return [_mouvement_to_dict(m, lot, prod) for m, lot, prod in result.all()]


async def get_mouvements_filtered(
    db: AsyncSession,
    clinic_id: Optional[int] = None,
    date_debut: Optional[date] = None,
    date_fin: Optional[date] = None,
    lot_id: Optional[int] = None,
    type_mouvement: Optional[str] = None,
    limit: int = 500,
) -> List[dict]:
    """Registre des mouvements filtré — alimente l'export PDF d'audit (V2.3).

    Filtres optionnels : plage de dates, lot précis, type de mouvement.
    Tri du plus récent au plus ancien.
    """
    clinic_id = resolve_clinic_id(clinic_id)
    stmt = (
        select(MouvementLotInjectable, LotInjectable, ProduitInjectable)
        .join(LotInjectable, MouvementLotInjectable.lot_id == LotInjectable.id)
        .join(ProduitInjectable, LotInjectable.produit_id == ProduitInjectable.id)
        .where(MouvementLotInjectable.clinic_id == clinic_id)
    )
    if date_debut is not None:
        stmt = stmt.where(
            MouvementLotInjectable.date_mouvement >= datetime.combine(date_debut, datetime.min.time())
        )
    if date_fin is not None:
        stmt = stmt.where(
            MouvementLotInjectable.date_mouvement <= datetime.combine(date_fin, datetime.max.time())
        )
    if lot_id is not None:
        stmt = stmt.where(MouvementLotInjectable.lot_id == lot_id)
    if type_mouvement is not None:
        stmt = stmt.where(MouvementLotInjectable.type_mouvement == type_mouvement)
    stmt = stmt.order_by(MouvementLotInjectable.date_mouvement.desc()).limit(limit)
    result = await db.execute(stmt)
    return [_mouvement_to_dict(m, lot, prod) for m, lot, prod in result.all()]


# ── Alertes stock ──────────────────────────────────────────

async def check_stock_alerts(db: AsyncSession, clinic_id: Optional[int] = None) -> List[StockAlert]:
    """Retourne toutes les alertes stock.

    ROUGE : stock = 0 OU lot expiré
    ORANGE : stock < minimum OU expire dans < 30j
    VERT : expire dans < 60j (info)
    """
    clinic_id = resolve_clinic_id(clinic_id)
    alerts: List[StockAlert] = []
    today = date.today()

    result = await db.execute(
        select(LotInjectable, ProduitInjectable)
        .join(ProduitInjectable, LotInjectable.produit_id == ProduitInjectable.id)
        .where(LotInjectable.clinic_id == clinic_id)
        .where(ProduitInjectable.clinic_id == clinic_id)
        .where(LotInjectable.statut.in_([
            StatutLot.DISPONIBLE.value,
            StatutLot.QUARANTAINE.value,
        ]))
    )

    for lot, produit in result.all():
        jours = (lot.date_expiration - today).days

        # ROUGE
        if lot.quantite_restante <= 0 or jours < 0:
            alerts.append(StockAlert(
                niveau="rouge",
                produit_nom=produit.nom,
                numero_lot=lot.numero_lot,
                message=f"RUPTURE — {lot.quantite_restante} {produit.unite} restant" if lot.quantite_restante <= 0 else f"EXPIRÉ depuis {abs(jours)} jours",
                lot_id=lot.id,
            ))
        # ORANGE
        elif lot.quantite_restante <= produit.stock_alerte or jours <= 30:
            alerts.append(StockAlert(
                niveau="orange",
                produit_nom=produit.nom,
                numero_lot=lot.numero_lot,
                message=f"{lot.quantite_restante} {produit.unite} restant — expire dans {jours}j" if jours <= 30 else f"Stock sous le seuil : {lot.quantite_restante} {produit.unite}",
                lot_id=lot.id,
            ))
        # VERT (info)
        elif jours <= 60:
            alerts.append(StockAlert(
                niveau="vert",
                produit_nom=produit.nom,
                numero_lot=lot.numero_lot,
                message=f"Expire dans {jours} jours",
                lot_id=lot.id,
            ))

    return alerts


# ── Traçabilité patient ───────────────────────────────────

async def get_tracabilite_patient(
    patient_id: int,
    db: AsyncSession,
    clinic_id: Optional[int] = None,
) -> List[dict]:
    """Retourne l'historique complet des injectables utilisés sur une patiente."""
    clinic_id = resolve_clinic_id(clinic_id)
    result = await db.execute(
        select(
            UtilisationLot,
            LotInjectable,
            ProduitInjectable,
            Utilisateur,
        )
        .join(LotInjectable, UtilisationLot.lot_id == LotInjectable.id)
        .join(ProduitInjectable, LotInjectable.produit_id == ProduitInjectable.id)
        .join(Utilisateur, UtilisationLot.praticien_id == Utilisateur.id)
        .where(
            UtilisationLot.patient_id == patient_id,
            UtilisationLot.clinic_id == clinic_id,
            LotInjectable.clinic_id == clinic_id,
            ProduitInjectable.clinic_id == clinic_id,
            Utilisateur.clinic_id == clinic_id,
        )
        .order_by(UtilisationLot.date_utilisation.desc())
    )

    history = []
    for util, lot, prod, prat in result.all():
        history.append({
            "date": util.date_utilisation.isoformat(),
            "produit": prod.nom,
            "fabricant": prod.fabricant,
            "numero_lot": lot.numero_lot,
            "quantite": float(util.quantite_utilisee),
            "unite": util.unite,
            "praticien": f"{prat.prenom} {prat.nom}",
            "notes": util.notes,
        })

    return history


# ── Dashboard stock ────────────────────────────────────────

async def get_stock_dashboard(
    db: AsyncSession,
    clinic_id: Optional[int] = None,
) -> dict:
    """Retourne le tableau de bord stock complet."""
    clinic_id = resolve_clinic_id(clinic_id)
    # Total par produit
    result = await db.execute(
        select(
            ProduitInjectable.id,
            ProduitInjectable.nom,
            ProduitInjectable.categorie,
            ProduitInjectable.unite,
            ProduitInjectable.stock_minimum,
            func.coalesce(func.sum(LotInjectable.quantite_restante), Decimal("0.00")).label("total_restant"),
            func.count(LotInjectable.id).label("nb_lots"),
        )
        .outerjoin(LotInjectable, and_(
            LotInjectable.produit_id == ProduitInjectable.id,
            LotInjectable.clinic_id == clinic_id,
            LotInjectable.statut.in_([StatutLot.DISPONIBLE.value, StatutLot.QUARANTAINE.value]),
        ))
        .where(
            ProduitInjectable.is_active,
            ProduitInjectable.clinic_id == clinic_id,
        )
        .group_by(ProduitInjectable.id)
    )

    produits = []
    for row in result.all():
        total = row.total_restant or Decimal("0.00")
        statut = "ok"
        if total <= 0:
            statut = "rupture"
        elif total <= row.stock_minimum:
            statut = "alerte"

        produits.append({
            "produit_id": row.id,
            "nom": row.nom,
            "categorie": row.categorie,
            "unite": row.unite,
            "stock_total": float(total),
            "stock_minimum": float(row.stock_minimum),
            "nb_lots_actifs": row.nb_lots,
            "statut": statut,
        })

    # Alertes
    alerts = await check_stock_alerts(db, clinic_id=clinic_id)

    return {
        "produits": produits,
        "alertes": {
            "rouge": [a for a in alerts if a.niveau == "rouge"],
            "orange": [a for a in alerts if a.niveau == "orange"],
            "vert": [a for a in alerts if a.niveau == "vert"],
        },
        "total_alertes": len(alerts),
    }
