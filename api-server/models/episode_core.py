"""
AutoCommerce Clinic — Cœur "Épisode patient" (Bloc 1 de la refonte multi-pro)

Ce module introduit le pivot central de la refonte : un patient peut être vu
par plusieurs professionnels (médecin, esthéticienne, masseuse...) au cours
d'une même prise en charge, sans que cela crée plusieurs parcours séparés.

Décisions de conception (voir rapport d'audit Bloc 0 pour le détail des
écarts avec le schéma existant) :

- `EpisodePatient` est le nouveau pivot : 1 épisode peut regrouper plusieurs
  `Intervention` (1 par professionnel), chacune portant plusieurs
  `InterventionActe` (1 par acte proposé/réalisé).
- `ActeMedical` (models/database.py) devient le catalogue d'actes partagé
  entre professions — réutilisé tel quel plutôt que dupliqué en
  `ActeCatalogue`, pour ne pas casser les FK existantes (RendezVous,
  DossierMedical, Consentement, BookingRequest en dépendent déjà). Un champ
  `type_intervention` lui est ajouté par migration pour distinguer
  medical/esthetique/massage/autre.
- La chaîne « Acte proposé ≠ accepté médicalement ≠ accepté financièrement
  ≠ payé ≠ réalisé » est portée par `InterventionActe` : chaque étape a son
  propre champ (booléen + horodatage + auteur), car ce sont des décisions
  indépendantes qui peuvent survenir dans des ordres différents selon le
  protocole de la clinique (ex. acceptation financière avant validation
  médicale finale). Un `statut` dérivé reste disponible pour le filtrage
  rapide côté API, recalculé par le service applicatif — jamais source de
  vérité à lui seul.
- `Devis`/`DevisLigne` sont strictement séparés de `Facture`/`FactureLigne` :
  un devis peut être refusé ou partiellement accepté sans jamais toucher à
  la facturation.
- `NotePrivee` (visible uniquement par son auteur + direction/admin) est
  séparée de `NotePartagee` (visible par tous les intervenants de
  l'épisode) — ce sont deux tables, pas un flag sur une table commune, pour
  qu'une erreur d'application ne puisse pas faire fuiter une note privée
  vers le résumé partagé.
- `Paiement` est un nouveau ledger (aucun équivalent n'existait) : plusieurs
  paiements partiels peuvent s'accumuler sur une même facture globale.
- `AuditEvent` est un journal unifié pour les actions liées à l'épisode ;
  les 3 tables d'audit existantes (`AuditLogMedical/Financial/Team`) restent
  en place pour leurs domaines actuels — la consolidation complète est
  prévue au Bloc 12, pas ici, pour limiter le risque de cette migration.
- `Prospect` est un pivot léger vers lequel `CallbackLead` et
  `BookingRequest` peuvent converger (champ `prospect_id` optionnel ajouté
  aux deux par migration) ; il se transforme en `Patient` via
  `patient_id` renseigné, jamais supprimé (traçabilité).

Les tables racines sont scopées `clinic_id` (cohérent avec le reste du
schéma). Les tables enfants strictement dépendantes d'un parent déjà scopé
(`DevisLigne`, `FactureLigne`, `PaiementAffectation`) n'ont volontairement
pas leur propre `clinic_id` — Option A actée en revue Bloc 1 v2 : éviter
une colonne redondante plutôt qu'une isolation en profondeur, à condition
que le service applicatif filtre toujours via le parent (jamais de scan
isolé de ces tables enfants sans jointure). Voir le docstring de chacune
pour le détail. Par ailleurs, toutes utilisent des suppressions logiques
(`annule`/`statut`) plutôt que des `DELETE`, pour préserver l'historique
facturable/médical.
"""
from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.database import Base


# ═══════════════════════════════════════════════════════════
# ENUMS — statuts et transitions
# ═══════════════════════════════════════════════════════════

class TypeIntervention(str, enum.Enum):
    """Ajouté à ActeMedical.type_intervention par migration (Bloc 1)."""
    MEDICAL = "medical"
    ESTHETIQUE = "esthetique"
    MASSAGE = "massage"
    AUTRE = "autre"


class StatutProspect(str, enum.Enum):
    NOUVEAU = "nouveau"
    CONTACTE = "contacte"
    QUALIFIE = "qualifie"
    CONVERTI = "converti"          # patient_id renseigné
    PERDU = "perdu"

    @classmethod
    def transitions_autorisees(cls) -> dict[str, set[str]]:
        return {
            cls.NOUVEAU.value: {cls.CONTACTE.value, cls.PERDU.value},
            cls.CONTACTE.value: {cls.QUALIFIE.value, cls.PERDU.value},
            cls.QUALIFIE.value: {cls.CONVERTI.value, cls.PERDU.value},
            cls.CONVERTI.value: set(),   # état terminal
            cls.PERDU.value: {cls.NOUVEAU.value},  # relance possible
        }


class StatutEpisode(str, enum.Enum):
    OUVERT = "ouvert"                        # accueil fait, aucune intervention close
    EN_ATTENTE_CONSENTEMENT = "en_attente_consentement"
    EN_ATTENTE_PAIEMENT = "en_attente_paiement"
    EN_COURS = "en_cours"                    # au moins une intervention démarrée
    CLOTURE = "cloture"                      # cf. garde-fou obligatoire dans le service de clôture
    ANNULE = "annule"

    @classmethod
    def transitions_autorisees(cls) -> dict[str, set[str]]:
        return {
            cls.OUVERT.value: {
                cls.EN_ATTENTE_CONSENTEMENT.value,
                cls.EN_ATTENTE_PAIEMENT.value,
                cls.EN_COURS.value,
                cls.ANNULE.value,
            },
            cls.EN_ATTENTE_CONSENTEMENT.value: {cls.EN_ATTENTE_PAIEMENT.value, cls.EN_COURS.value, cls.ANNULE.value},
            cls.EN_ATTENTE_PAIEMENT.value: {cls.EN_ATTENTE_CONSENTEMENT.value, cls.EN_COURS.value, cls.ANNULE.value},
            cls.EN_COURS.value: {cls.EN_ATTENTE_PAIEMENT.value, cls.CLOTURE.value, cls.ANNULE.value},
            # CLOTURE n'est atteignable QUE via le service de clôture, qui
            # vérifie interventions/consentements/facturation/paiement/
            # photos obligatoires/EI traités/suivi post-séance AVANT
            # d'autoriser cette transition — l'enum liste la transition
            # possible, mais ne garantit jamais à elle seule qu'elle est
            # licite (voir services/episode.py, Bloc 4).
            cls.CLOTURE.value: set(),
            cls.ANNULE.value: set(),
        }


class StatutIntervention(str, enum.Enum):
    PLANIFIEE = "planifiee"
    EN_COURS = "en_cours"
    A_VALIDER = "a_valider"    # acte fait, mais compte-rendu/photos/produits à compléter avant clôture
    TERMINEE = "terminee"      # entièrement documentée et signée
    ANNULEE = "annulee"

    @classmethod
    def transitions_autorisees(cls) -> dict[str, set[str]]:
        return {
            cls.PLANIFIEE.value: {cls.EN_COURS.value, cls.ANNULEE.value},
            cls.EN_COURS.value: {cls.A_VALIDER.value, cls.ANNULEE.value},
            cls.A_VALIDER.value: {cls.TERMINEE.value, cls.EN_COURS.value},  # retour possible si complément nécessaire
            cls.TERMINEE.value: set(),
            cls.ANNULEE.value: set(),
        }


class StatutInterventionActe(str, enum.Enum):
    """Statut dérivé (lecture rapide) — recalculé par le service à partir
    des horodatages ci-dessous, jamais écrit directement sans passer par
    la fonction de transition (voir services/episode.py, Bloc 4)."""
    PROPOSE = "propose"
    ACCEPTE_MEDICAL = "accepte_medical"
    ACCEPTE_FINANCIER = "accepte_financier"
    PAYE = "paye"
    REALISE = "realise"
    REFUSE = "refuse"
    ANNULE = "annule"


class StatutDevis(str, enum.Enum):
    BROUILLON = "brouillon"
    ENVOYE = "envoye"
    ACCEPTE = "accepte"            # peut être partiel — voir DevisLigne.acceptee
    REFUSE = "refuse"
    EXPIRE = "expire"

    @classmethod
    def transitions_autorisees(cls) -> dict[str, set[str]]:
        # Un devis envoyé ne se modifie plus directement (voir `Devis.
        # version`/`devis_parent_id`/`remplace_devis_id`) : refuse/expire
        # sont désormais des états terminaux pour LA LIGNE — une nouvelle
        # proposition crée une nouvelle ligne `Devis` (version+1), jamais
        # un retour à brouillon sur la même ligne (ça détruirait la trace
        # de ce que le patient a réellement vu et refusé).
        return {
            cls.BROUILLON.value: {cls.ENVOYE.value},
            cls.ENVOYE.value: {cls.ACCEPTE.value, cls.REFUSE.value, cls.EXPIRE.value},
            cls.ACCEPTE.value: set(),
            cls.REFUSE.value: set(),
            cls.EXPIRE.value: set(),
        }


class StatutPaiement(str, enum.Enum):
    ENREGISTRE = "enregistre"
    ANNULE = "annule"
    REMBOURSE = "rembourse"


class StatutSuivi(str, enum.Enum):
    PLANIFIE = "planifie"
    FAIT = "fait"
    SANS_REPONSE = "sans_reponse"
    ANNULE = "annule"


class TypeAgendaEvent(str, enum.Enum):
    RDV = "rdv"                    # miroir d'un RendezVous (rdv_id renseigné)
    BLOCAGE = "blocage"            # indisponibilité praticien/salle
    TACHE = "tache"                # rappel interne, sans patient


# ═══════════════════════════════════════════════════════════
# PROSPECT — pré-patient unifié
# ═══════════════════════════════════════════════════════════

class Prospect(Base):
    __tablename__ = "prospects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    prenom: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    telephone: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="inconnue")
    statut: Mapped[str] = mapped_column(String(20), nullable=False, default=StatutProspect.NOUVEAU.value, index=True)
    # Renseigné uniquement à la conversion — jamais réécrit ni supprimé après.
    patient_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assigned_to_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    converti_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_prospects_clinic_statut", "clinic_id", "statut"),
        CheckConstraint(
            "(statut != 'converti') OR (patient_id IS NOT NULL)",
            name="ck_prospect_converti_a_patient_id",
        ),
    )


# ═══════════════════════════════════════════════════════════
# EPISODE — pivot central
# ═══════════════════════════════════════════════════════════

class EpisodePatient(Base):
    """Une prise en charge du patient, potentiellement multi-professionnelle.

    Un épisode nait généralement d'un accueil (rdv_origine_id) mais reste
    indépendant du rendez-vous une fois ouvert : des interventions
    supplémentaires (orientation vers un autre professionnel le jour même)
    peuvent s'y ajouter sans nouveau rendez-vous.
    """
    __tablename__ = "episodes_patient"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    rdv_origine_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("rendez_vous.id", ondelete="SET NULL"), nullable=True
    )
    statut: Mapped[str] = mapped_column(String(30), nullable=False, default=StatutEpisode.OUVERT.value, index=True)
    ouvert_par_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False
    )
    ouvert_le: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    cloture_le: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cloture_par_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        Index("ix_episode_clinic_patient", "clinic_id", "patient_id"),
        Index("ix_episode_clinic_statut", "clinic_id", "statut"),
        CheckConstraint(
            "(statut != 'cloture') OR (cloture_le IS NOT NULL AND cloture_par_id IS NOT NULL)",
            name="ck_episode_cloture_complete",
        ),
    )

    patient: Mapped["Patient"] = relationship("Patient")  # type: ignore[name-defined]
    interventions: Mapped[List["Intervention"]] = relationship(
        "Intervention", back_populates="episode", order_by="Intervention.id"
    )
    devis: Mapped[List["Devis"]] = relationship("Devis", back_populates="episode")
    notes_privees: Mapped[List["NotePrivee"]] = relationship("NotePrivee", back_populates="episode")
    notes_partagees: Mapped[List["NotePartagee"]] = relationship("NotePartagee", back_populates="episode")
    photos: Mapped[List["PhotoClinic"]] = relationship("PhotoClinic", back_populates="episode")
    consentements: Mapped[List["Consentement"]] = relationship("Consentement", back_populates="episode")
    simulations_ia: Mapped[List["SimulationIA"]] = relationship("SimulationIA", back_populates="episode")
    utilisations_lot: Mapped[List["UtilisationLot"]] = relationship("UtilisationLot", back_populates="episode")
    suivis_post_acte: Mapped[List["SuiviPostActe"]] = relationship("SuiviPostActe", back_populates="episode")


class Intervention(Base):
    """Un professionnel, dans un épisode. Porte 1..N InterventionActe.

    `rdv_id`/`salle_id` sont indépendants de `EpisodePatient.rdv_origine_id` :
    un épisode peut regrouper plusieurs rendez-vous (médecin à 10h en salle
    de consultation, esthéticienne à 11h30 en salle esthétique...). Pour une
    séance commune au même horaire, plusieurs interventions peuvent pointer
    vers le même `rdv_id`.
    """
    __tablename__ = "interventions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    episode_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("episodes_patient.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    professionnel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    rdv_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("rendez_vous.id", ondelete="SET NULL"), nullable=True, index=True
    )
    salle_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("salles.id", ondelete="SET NULL"), nullable=True
    )
    type_intervention: Mapped[str] = mapped_column(String(20), nullable=False)  # TypeIntervention
    statut: Mapped[str] = mapped_column(String(20), nullable=False, default=StatutIntervention.PLANIFIEE.value)
    # Planification indépendante d'un RDV classique (ex. intervention
    # ajoutée le jour même sans créneau réservé au préalable).
    date_debut_prevue: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    date_fin_prevue: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    demarree_le: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    terminee_le: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_intervention_episode", "episode_id"),
        Index("ix_intervention_professionnel_statut", "professionnel_id", "statut"),
        Index("ix_intervention_rdv", "rdv_id"),
    )

    episode: Mapped["EpisodePatient"] = relationship("EpisodePatient", back_populates="interventions")
    actes: Mapped[List["InterventionActe"]] = relationship(
        "InterventionActe", back_populates="intervention", order_by="InterventionActe.id"
    )
    notes_privees: Mapped[List["NotePrivee"]] = relationship("NotePrivee", back_populates="intervention")
    photos: Mapped[List["PhotoClinic"]] = relationship("PhotoClinic", back_populates="intervention")
    consentements: Mapped[List["Consentement"]] = relationship("Consentement", back_populates="intervention")
    simulations_ia: Mapped[List["SimulationIA"]] = relationship("SimulationIA", back_populates="intervention")
    utilisations_lot: Mapped[List["UtilisationLot"]] = relationship("UtilisationLot", back_populates="intervention")
    suivis_post_acte: Mapped[List["SuiviPostActe"]] = relationship("SuiviPostActe", back_populates="intervention")


class InterventionActe(Base):
    """Un acte au sein d'une intervention — porte la chaîne d'états
    proposé → accepté médical → accepté financier → payé → réalisé.

    Chaque étape est indépendante (booléen + horodatage + auteur) : un acte
    peut être accepté financièrement puis médicalement refusé au dernier
    moment, ou payé avant d'être totalement réalisé (acompte). `statut` est
    une lecture rapide recalculée par le service, jamais la seule vérité.
    """
    __tablename__ = "interventions_actes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    intervention_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("interventions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    acte_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("actes_medicaux.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    statut: Mapped[str] = mapped_column(
        String(20), nullable=False, default=StatutInterventionActe.PROPOSE.value, index=True
    )
    prix_convenu: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False, default=Decimal("0.000"))

    propose_par_id: Mapped[int] = mapped_column(Integer, ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False)
    propose_le: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    accepte_medical: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    accepte_medical_par_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True)
    accepte_medical_le: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    accepte_financier: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    accepte_financier_par_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True)
    accepte_financier_le: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    paye: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # indicateur rapide — voir Paiement/PaiementAffectation pour la répartition réelle
    paye_le: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    realise: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    realise_par_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True)
    realise_le: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    refuse_motif: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_intervention_acte_intervention", "intervention_id"),
        Index("ix_intervention_acte_statut", "clinic_id", "statut"),
        CheckConstraint("prix_convenu >= 0", name="ck_intervention_acte_prix_non_negatif"),
        # Un acte ne peut pas être marqué réalisé sans avoir été accepté
        # médicalement au préalable — contrôlé aussi côté service (Bloc 4),
        # doublé ici en garde-fou base de données.
        CheckConstraint(
            "(realise = false) OR (accepte_medical = true)",
            name="ck_intervention_acte_realise_implique_accepte_medical",
        ),
    )

    intervention: Mapped["Intervention"] = relationship("Intervention", back_populates="actes")
    acte: Mapped["ActeMedical"] = relationship("ActeMedical")  # type: ignore[name-defined]
    devis_lignes: Mapped[List["DevisLigne"]] = relationship("DevisLigne", back_populates="intervention_acte")
    facture_lignes: Mapped[List["FactureLigne"]] = relationship("FactureLigne", back_populates="intervention_acte")


# ═══════════════════════════════════════════════════════════
# DEVIS — séparé de la facture
# ═══════════════════════════════════════════════════════════

class Devis(Base):
    """Un devis envoyé ne se modifie plus directement : toute modification
    après envoi crée une nouvelle version (nouvelle ligne `Devis`), pour ne
    jamais perdre la trace de ce que le patient a réellement vu et refusé.
    """
    __tablename__ = "devis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    episode_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("episodes_patient.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # L'offre financière est liée à l'épisode et au dossier médical présenté.
    dossier_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("dossiers_medicaux.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    numero_devis: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Racine commune à toutes les versions d'un même devis logique (auto-FK
    # vers la version 1) — permet de retrouver tout l'historique en une
    # requête sans remonter la chaîne remplace_devis_id à la main.
    devis_parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("devis.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Pointe vers la version immédiatement précédente que ce devis remplace
    # (rempli seulement à partir de la version 2).
    remplace_devis_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("devis.id", ondelete="SET NULL"), nullable=True
    )
    statut: Mapped[str] = mapped_column(String(20), nullable=False, default=StatutDevis.BROUILLON.value, index=True)
    cree_par_id: Mapped[int] = mapped_column(Integer, ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    envoye_le: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reponse_le: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    validite_jours: Mapped[int] = mapped_column(Integer, default=30, nullable=False)

    __table_args__ = (
        Index("ix_devis_clinic_statut", "clinic_id", "statut"),
        Index("ix_devis_parent", "devis_parent_id"),
    )

    episode: Mapped["EpisodePatient"] = relationship("EpisodePatient", back_populates="devis")
    lignes: Mapped[List["DevisLigne"]] = relationship("DevisLigne", back_populates="devis", order_by="DevisLigne.id")


class DevisLigne(Base):
    """Pas de `clinic_id` propre (Option A, revue Bloc 1 v2) : la portée
    clinique se lit via `DevisLigne.devis.clinic_id`. Choix délibéré —
    éviter une colonne redondante qui pourrait diverger de son parent est
    jugé préférable à une isolation "en profondeur" pour une table qui
    n'est jamais interrogée sans jointure sur `devis`. **Obligation côté
    service (Bloc 4)** : toute requête sur `DevisLigne` doit filtrer via
    son `Devis` parent (jamais un scan `DevisLigne` isolé sans jointure
    `clinic_id`)."""
    __tablename__ = "devis_lignes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    devis_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("devis.id", ondelete="CASCADE"), nullable=False, index=True
    )
    intervention_acte_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("interventions_actes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    quantite: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    prix_unitaire: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    remise_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"))
    # Acceptation par ligne : un devis "accepté" peut ne l'être que
    # partiellement — chaque ligne porte sa propre décision patient.
    acceptee: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)  # None = pas encore répondu

    __table_args__ = (
        CheckConstraint("quantite > 0", name="ck_devis_ligne_quantite_positive"),
        CheckConstraint("prix_unitaire >= 0", name="ck_devis_ligne_prix_non_negatif"),
    )

    devis: Mapped["Devis"] = relationship("Devis", back_populates="lignes")
    intervention_acte: Mapped["InterventionActe"] = relationship("InterventionActe", back_populates="devis_lignes")


# ═══════════════════════════════════════════════════════════
# FACTURE — extension (FactureLigne + rattachement épisode)
# ═══════════════════════════════════════════════════════════

class FactureLigne(Base):
    """Remplace les champs JSON dénormalisés `Facture.actes`/`produits` pour
    les nouvelles factures issues d'un épisode. Les factures existantes
    conservent leur JSON (lu en compatibilité) — voir Bloc 13.

    Pas de `clinic_id` propre (Option A, revue Bloc 1 v2) — portée via
    `FactureLigne.facture.clinic_id`, même obligation de filtrage par
    jointure côté service que `DevisLigne`."""
    __tablename__ = "facture_lignes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facture_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("factures.id", ondelete="CASCADE"), nullable=False, index=True
    )
    intervention_acte_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("interventions_actes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    quantite: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    prix_unitaire: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    remise_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"))
    montant_ligne: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)

    __table_args__ = (
        CheckConstraint("quantite > 0", name="ck_facture_ligne_quantite_positive"),
        CheckConstraint("prix_unitaire >= 0", name="ck_facture_ligne_prix_non_negatif"),
    )

    facture: Mapped["Facture"] = relationship("Facture", back_populates="lignes")  # type: ignore[name-defined]
    intervention_acte: Mapped[Optional["InterventionActe"]] = relationship(
        "InterventionActe", back_populates="facture_lignes"
    )
    affectations: Mapped[List["PaiementAffectation"]] = relationship(
        "PaiementAffectation", back_populates="facture_ligne"
    )


class Paiement(Base):
    """Ledger de paiements — plusieurs paiements partiels par facture.

    Un `Paiement` seul ne dit pas QUEL acte/ligne il couvre sur une facture
    globale multi-actes : voir `PaiementAffectation` ci-dessous, qui porte
    la répartition réelle. `InterventionActe.paye` reste un indicateur
    rapide (filtrage/liste), mais la vérité de "cet acte peut démarrer"
    doit se lire via les affectations, pas via ce seul booléen — il est
    maintenu par le service de paiement (Bloc 4/8), jamais écrit à la main
    par un endpoint qui ignorerait la répartition.
    """
    __tablename__ = "paiements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    facture_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("factures.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    montant: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    mode: Mapped[str] = mapped_column(String(50), nullable=False)  # especes/carte/virement/cheque...
    statut: Mapped[str] = mapped_column(String(20), nullable=False, default=StatutPaiement.ENREGISTRE.value)
    encaisse_par_id: Mapped[int] = mapped_column(Integer, ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False)
    encaisse_le: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_paiement_facture", "facture_id"),
        CheckConstraint("montant > 0", name="ck_paiement_montant_positif"),
    )

    facture: Mapped["Facture"] = relationship("Facture", back_populates="paiements")  # type: ignore[name-defined]
    affectations: Mapped[List["PaiementAffectation"]] = relationship(
        "PaiementAffectation", back_populates="paiement", cascade="all, delete-orphan"
    )


class PaiementAffectation(Base):
    """Répartit un `Paiement` sur une ou plusieurs `FactureLigne`.

    Exemple : un paiement de 200 € sur une facture Botox(300)+Massage(100)
    peut être affecté 100 € à la ligne Massage (soldée) et 100 € à la ligne
    Botox (encore partiellement due) — ce qui détermine précisément quel
    `InterventionActe` peut démarrer et lequel doit rester bloqué.

    La somme des `montant_affecte` d'un paiement ne doit jamais dépasser
    son `montant` (contrôlé côté service, pas en contrainte SQL portable
    car cela nécessite une agrégation inter-lignes).

    Pas de `clinic_id` propre (Option A, revue Bloc 1 v2) — portée via
    `PaiementAffectation.paiement.clinic_id`, même obligation de filtrage
    par jointure côté service que `DevisLigne`/`FactureLigne`.
    """
    __tablename__ = "paiements_affectations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paiement_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("paiements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    facture_ligne_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("facture_lignes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    montant_affecte: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)

    __table_args__ = (
        Index("ix_paiement_affectation_paiement", "paiement_id"),
        Index("ix_paiement_affectation_ligne", "facture_ligne_id"),
        UniqueConstraint("paiement_id", "facture_ligne_id", name="uq_paiement_affectation_paiement_ligne"),
        CheckConstraint("montant_affecte > 0", name="ck_paiement_affectation_montant_positif"),
    )

    paiement: Mapped["Paiement"] = relationship("Paiement", back_populates="affectations")
    facture_ligne: Mapped["FactureLigne"] = relationship("FactureLigne", back_populates="affectations")


# ═══════════════════════════════════════════════════════════
# NOTES — privées vs partagées (2 tables distinctes)
# ═══════════════════════════════════════════════════════════

class NotePrivee(Base):
    """Visible uniquement par son auteur + rôles direction/admin (contrôlé
    côté API, jamais par un simple filtre frontend).

    Pas de suppression physique : `archived_at`/`archived_by_id` marquent
    une note comme retirée sans effacer l'historique. FK en `RESTRICT` (pas
    `CASCADE`) — une suppression forcée d'épisode ne doit jamais pouvoir
    emporter silencieusement les notes qui y sont rattachées.
    """
    __tablename__ = "notes_privees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    episode_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("episodes_patient.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    intervention_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("interventions.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    auteur_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    contenu_enc: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    archived_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )

    episode: Mapped["EpisodePatient"] = relationship("EpisodePatient", back_populates="notes_privees")
    intervention: Mapped[Optional["Intervention"]] = relationship("Intervention", back_populates="notes_privees")


class NotePartagee(Base):
    """Résumé partagé, visible par tous les intervenants de l'épisode —
    jamais de données médicales détaillées, seulement les consignes utiles
    aux autres professionnels (contrôlé côté service, pas ici).

    Mêmes règles d'historisation que `NotePrivee` : archivage, pas de
    suppression physique, FK `RESTRICT`.
    """
    __tablename__ = "notes_partagees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    episode_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("episodes_patient.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    auteur_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    contenu: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    archived_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )

    episode: Mapped["EpisodePatient"] = relationship("EpisodePatient", back_populates="notes_partagees")


# ═══════════════════════════════════════════════════════════
# SUIVI POST-SÉANCE (rattachement épisode)
# ═══════════════════════════════════════════════════════════
# SuiviPostActe existe déjà dans models/database.py (rattaché à un acte de
# dossier). Un champ episode_id (nullable, ajouté par migration) le relie
# au nouveau pivot sans dupliquer la table — voir Bloc 13 pour le detail
# de compatibilité ascendante.


# ═══════════════════════════════════════════════════════════
# AGENDA EVENT — générique (blocages, tâches), au-delà du RDV patient
# ═══════════════════════════════════════════════════════════

class AgendaEvent(Base):
    __tablename__ = "agenda_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    type_event: Mapped[str] = mapped_column(String(20), nullable=False, default=TypeAgendaEvent.TACHE.value)
    titre: Mapped[str] = mapped_column(String(200), nullable=False)
    professionnel_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    rdv_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("rendez_vous.id", ondelete="CASCADE"), nullable=True
    )
    date_debut: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    date_fin: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_agenda_event_clinic_date", "clinic_id", "date_debut"),
        CheckConstraint("date_fin > date_debut", name="ck_agenda_event_periode_valide"),
    )


# ═══════════════════════════════════════════════════════════
# AUDIT EVENT — journal unifié (scope épisode, Bloc 12 pour le reste)
# ═══════════════════════════════════════════════════════════

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    episode_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("episodes_patient.id", ondelete="SET NULL"), nullable=True, index=True
    )
    domaine: Mapped[str] = mapped_column(String(30), nullable=False)   # episode/devis/facture/paiement/note/photo...
    action: Mapped[str] = mapped_column(String(50), nullable=False)    # ex. "transition_statut", "creation"
    acteur_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    cible_type: Mapped[str] = mapped_column(String(50), nullable=False)  # ex. "InterventionActe"
    cible_id: Mapped[int] = mapped_column(Integer, nullable=False)
    detail: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # jamais de contenu médical brut ici
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_audit_event_clinic_date", "clinic_id", "created_at"),
        Index("ix_audit_event_cible", "cible_type", "cible_id"),
    )


# ═══════════════════════════════════════════════════════════
# BLOC 3 — Journal d'agenda (parcours d'arrivée patient)
# ═══════════════════════════════════════════════════════════

class RdvEvenement(Base):
    """Bloc 3 — journal d'événements d'un rendez-vous.

    Aucun rendez-vous n'est supprimé : toute modification importante crée un
    événement d'agenda avec ancienne valeur, nouvelle valeur, auteur, date et
    motif (table `rdv_evenements`).
    """

    __tablename__ = "rdv_evenements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    rdv_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rendez_vous.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="SET NULL"), nullable=True
    )
    type_evenement: Mapped[str] = mapped_column(String(30), nullable=False)
    ancienne_valeur: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    nouvelle_valeur: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auteur_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    motif: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cree_le: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
    )
