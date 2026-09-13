"""
AutoCommerce Clinic — Service Gestion Stock Consommables
CRUD, mouvements de stock (entrée / sortie / ajustement) et alertes.

Améliorations V2.2 :
- verrou pessimiste ``FOR UPDATE`` sur le consommable avant chaque mouvement
  (sérialise les opérations concurrentes) ;
- quantités en ``Decimal`` stricts, refus des quantités non positives ;
- nouveau type ``ajustement`` : remplace le stock par la quantité constatée
  (motif obligatoire) pour les inventaires ;
- historique consultable par consommable et flux récent global.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Consommable, MouvementConsommable, Utilisateur
from services.stock_alerts import sync_stock_alert


def _decimal(value) -> Decimal:
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError, TypeError) as exc:
        raise ValueError(f"Valeur numérique invalide : {value!r}") from exc


class ConsommableService:
    @staticmethod
    async def get_all(db: AsyncSession, clinic_id: int = 1) -> List[Consommable]:
        stmt = select(Consommable).where(
            Consommable.clinic_id == clinic_id,
            Consommable.is_active
        ).order_by(Consommable.nom)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, consommable_id: int, clinic_id: int = 1) -> Optional[Consommable]:
        stmt = select(Consommable).where(
            Consommable.id == consommable_id,
            Consommable.clinic_id == clinic_id
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def _get_by_id_locked(db: AsyncSession, consommable_id: int, clinic_id: int = 1) -> Optional[Consommable]:
        """Charge le consommable avec verrou pessimiste (anti course critique)."""
        stmt = (
            select(Consommable)
            .where(
                Consommable.id == consommable_id,
                Consommable.clinic_id == clinic_id,
            )
            .with_for_update(of=Consommable)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, data: dict, clinic_id: int = 1) -> Consommable:
        consommable = Consommable(
            clinic_id=clinic_id,
            nom=data["nom"],
            categorie=data["categorie"],
            unite=data["unite"],
            stock_actuel=_decimal(data.get("stock_actuel", 0)),
            seuil_alerte=_decimal(data.get("seuil_alerte", 0)),
            stock_minimum=_decimal(data.get("stock_minimum", 0)),
            prix_unitaire=_decimal(data.get("prix_unitaire", 0)),
            fournisseur_id=data.get("fournisseur_id"),
            is_active=True
        )
        db.add(consommable)
        await db.commit()
        await db.refresh(consommable)
        return consommable

    @staticmethod
    async def update(db: AsyncSession, consommable_id: int, data: dict, clinic_id: int = 1) -> Optional[Consommable]:
        consommable = await ConsommableService.get_by_id(db, consommable_id, clinic_id)
        if not consommable:
            return None

        for key, value in data.items():
            if hasattr(consommable, key):
                if key in ["stock_actuel", "seuil_alerte", "stock_minimum", "prix_unitaire"]:
                    setattr(consommable, key, _decimal(value))
                else:
                    setattr(consommable, key, value)

        await db.commit()
        await db.refresh(consommable)
        return consommable

    @staticmethod
    async def delete(db: AsyncSession, consommable_id: int, clinic_id: int = 1) -> bool:
        consommable = await ConsommableService.get_by_id(db, consommable_id, clinic_id)
        if not consommable:
            return False

        consommable.is_active = False
        await db.commit()
        return True

    @staticmethod
    async def add_mouvement(
        db: AsyncSession,
        consommable_id: int,
        type_mvt: str,
        quantite: float,
        utilisateur_id: int,
        motif: str = None,
        reference: str = None,
        clinic_id: int = 1
    ) -> Optional[MouvementConsommable]:
        consommable = await ConsommableService._get_by_id_locked(db, consommable_id, clinic_id)
        if not consommable:
            return None

        qte = _decimal(quantite)
        if qte <= 0:
            raise ValueError("La quantité doit être strictement positive")

        if type_mvt not in ("entree", "sortie", "ajustement"):
            raise ValueError(f"Type de mouvement inconnu : {type_mvt}")

        # Un ajustement (inventaire) remplace le stock : motif obligatoire
        # pour que la trace d'audit reste exploitable.
        if type_mvt == "ajustement" and not motif:
            raise ValueError("Un motif est obligatoire pour un ajustement d'inventaire")

        if type_mvt == "sortie" and consommable.stock_actuel < qte:
            raise ValueError(
                f"Stock insuffisant : {consommable.stock_actuel} {consommable.unite} disponible(s), "
                f"{qte} demandé(s)"
            )

        mouvement = MouvementConsommable(
            clinic_id=clinic_id,
            consommable_id=consommable_id,
            type=type_mvt,
            quantite=qte,
            utilisateur_id=utilisateur_id,
            motif=motif,
            reference=reference
        )
        db.add(mouvement)

        if type_mvt == "entree":
            consommable.stock_actuel += qte
        elif type_mvt == "sortie":
            consommable.stock_actuel -= qte
        elif type_mvt == "ajustement":
            consommable.stock_actuel = qte

        await sync_stock_alert(
            db, clinic_id=clinic_id, type_article="consommable",
            article_nom=consommable.nom, stock_actuel=consommable.stock_actuel,
            seuil_alerte=consommable.seuil_alerte,
            stock_minimum=consommable.stock_minimum,
            consommable_id=consommable.id,
        )
        await db.commit()
        await db.refresh(mouvement)
        return mouvement

    @staticmethod
    async def get_mouvements(
        db: AsyncSession, consommable_id: int, clinic_id: int = 1, limit: int = 100
    ) -> List[Dict]:
        """Historique des mouvements d'un consommable (plus récent d'abord)."""
        stmt = (
            select(MouvementConsommable, Utilisateur)
            .outerjoin(Utilisateur, MouvementConsommable.utilisateur_id == Utilisateur.id)
            .where(
                MouvementConsommable.clinic_id == clinic_id,
                MouvementConsommable.consommable_id == consommable_id,
            )
            .order_by(MouvementConsommable.date_mouvement.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = []
        for m, u in result.all():
            rows.append({
                "mouvement_id": m.id,
                "consommable_id": m.consommable_id,
                "type": m.type,
                "quantite": float(m.quantite),
                "date_mouvement": m.date_mouvement.isoformat(),
                "utilisateur": f"{u.prenom} {u.nom}" if u else None,
                "motif": m.motif,
                "reference": m.reference,
            })
        return rows

    @staticmethod
    async def get_recent_mouvements(
        db: AsyncSession, clinic_id: int = 1, limit: int = 12
    ) -> List[Dict]:
        """Derniers mouvements consommables de la clinique (registre d'audit)."""
        stmt = (
            select(MouvementConsommable, Consommable, Utilisateur)
            .join(Consommable, MouvementConsommable.consommable_id == Consommable.id)
            .outerjoin(Utilisateur, MouvementConsommable.utilisateur_id == Utilisateur.id)
            .where(MouvementConsommable.clinic_id == clinic_id)
            .order_by(MouvementConsommable.date_mouvement.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = []
        for m, c, u in result.all():
            rows.append({
                "mouvement_id": m.id,
                "consommable_id": c.id,
                "consommable_nom": c.nom,
                "unite": c.unite,
                "type": m.type,
                "quantite": float(m.quantite),
                "date_mouvement": m.date_mouvement.isoformat(),
                "utilisateur": f"{u.prenom} {u.nom}" if u else None,
                "motif": m.motif,
                "reference": m.reference,
            })
        return rows

    @staticmethod
    async def get_mouvements_filtered(
        db: AsyncSession,
        clinic_id: int = 1,
        date_debut: Optional[date] = None,
        date_fin: Optional[date] = None,
        consommable_id: Optional[int] = None,
        type_mvt: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict]:
        """Registre des mouvements consommables filtré — export PDF d'audit (V2.3)."""
        stmt = (
            select(MouvementConsommable, Consommable, Utilisateur)
            .join(Consommable, MouvementConsommable.consommable_id == Consommable.id)
            .outerjoin(Utilisateur, MouvementConsommable.utilisateur_id == Utilisateur.id)
            .where(MouvementConsommable.clinic_id == clinic_id)
        )
        if date_debut is not None:
            stmt = stmt.where(
                MouvementConsommable.date_mouvement >= datetime.combine(date_debut, datetime.min.time())
            )
        if date_fin is not None:
            stmt = stmt.where(
                MouvementConsommable.date_mouvement <= datetime.combine(date_fin, datetime.max.time())
            )
        if consommable_id is not None:
            stmt = stmt.where(MouvementConsommable.consommable_id == consommable_id)
        if type_mvt is not None:
            stmt = stmt.where(MouvementConsommable.type == type_mvt)
        stmt = stmt.order_by(MouvementConsommable.date_mouvement.desc()).limit(limit)
        result = await db.execute(stmt)
        rows = []
        for m, c, u in result.all():
            rows.append({
                "mouvement_id": m.id,
                "consommable_id": c.id,
                "consommable_nom": c.nom,
                "unite": c.unite,
                "type": m.type,
                "quantite": float(m.quantite),
                "date_mouvement": m.date_mouvement.isoformat(),
                "utilisateur": f"{u.prenom} {u.nom}" if u else None,
                "motif": m.motif,
                "reference": m.reference,
            })
        return rows

    @staticmethod
    async def get_alertes(db: AsyncSession, clinic_id: int = 1) -> List[Dict]:
        stmt = select(Consommable).where(
            Consommable.clinic_id == clinic_id,
            Consommable.is_active,
            Consommable.stock_actuel <= Consommable.seuil_alerte
        ).order_by(Consommable.stock_actuel)

        result = await db.execute(stmt)
        alertes = []
        for c in result.scalars().all():
            niveau = "critique" if c.stock_actuel <= c.stock_minimum else "alerte"
            alertes.append({
                "id": c.id,
                "nom": c.nom,
                "stock_actuel": float(c.stock_actuel),
                "seuil_alerte": float(c.seuil_alerte),
                "stock_minimum": float(c.stock_minimum),
                "niveau": niveau
            })
        return alertes
