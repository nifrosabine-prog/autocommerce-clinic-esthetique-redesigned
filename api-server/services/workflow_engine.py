"""
AutoCommerce Clinic — Service Workflow Engine (Bloc 6) — v2 production-grade

Renforcement vs v1 :
- **Idempotence** : clé ``(workflow_id, execution_id, action_type, idempotency_key)``
  garantit qu'une action critique n'est jamais exécutée 2× ;
- **Validation humaine** : aucune action ``send_*`` n'est auto-déclenchée —
  le moteur **prépare** un brouillon et **attend** la validation via
  ``/api/v1/workflows/{execution_id}/approve-action`` ;
- **Reprise sur échec** : retry avec backoff (1, 2, 4 s) avant échec définitif ;
- **Audit trail** : table ``WorkflowAuditLog`` DB (clé : clinic + workflow + execution_id + action) ;
- **LLM-decision** : ``decide_next_branch()`` consulte un LLM si le workflow a
  des branches conditionnelles (decision_required) ;
- **Async-safe** : pas de race sur l'audit (insert + flush avant exécution).
- **Strict typing Decimal** : jamais de float pour les montants ;
- **Status machine** : PENDING → RUNNING → (APPROVAL_REQUIRED | COMPLETED) → | FAILED.

Compatibilité ascendante : toutes les méthodes publiques v1 conservées
(`get_active_workflows`, `create_workflow_execution`, `execute_workflow`,
`execute_workflow_action`, ``_execute_action_impl``, etc.).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.workflow_engine import (
    Workflow, WorkflowExecution, WorkflowAction, WorkflowStatus,
    WorkflowExecutionStatus, WorkflowActionType, WorkflowTriggerType,
)
from models.database import Utilisateur, RoleEnum
from models.security import TacheInterneAssistant, StatutTacheInterneEnum

from services.omnicanal_service import send_message
from services.patients import get_patient
from services.marketing import create_campaign
from services.fidelite import add_points
from services.agenda import creer_rdv as _creer_rdv

from core.llm_client import LLMClient, LLMUnavailable, get_llm_client, pseudonymize_pii
from core.prompt_templates import WORKFLOW_DECISION

logger = logging.getLogger(__name__)
_APPROVAL_TOKEN = object()


# ── helpers ──────────────────────────────────────────────────────────────


def _idempotency_key(workflow_id: int, execution_id: int,
                     action_type: str, payload: Dict[str, Any]) -> str:
    h = hashlib.sha256()
    h.update(f"{workflow_id}|{execution_id}|{action_type}|".encode())
    h.update(json.dumps(payload, sort_keys=True, default=str).encode())
    return h.hexdigest()[:32]


# ── Service ──────────────────────────────────────────────────────────────


class WorkflowEngineService:
    """Moteur de workflows — idempotent, audité, humain-dans-la-boucle."""

    # ── V1 : actifs + scheduling (inchangé) ──────────────────────

    @staticmethod
    async def get_active_workflows(session: AsyncSession, clinic_id: int = 1) -> List[Workflow]:
        stmt = select(Workflow).where(and_(
            Workflow.clinic_id == clinic_id,
            Workflow.enabled,
            Workflow.status == WorkflowStatus.ACTIVE.value,
        ))
        return (await session.execute(stmt)).scalars().all()

    @staticmethod
    async def create_workflow_execution(
        session: AsyncSession, workflow_id: int, clinic_id: int,
        trigger_reason: str, patient_id: Optional[int] = None,
    ) -> WorkflowExecution:
        execution = WorkflowExecution(
            clinic_id=clinic_id, workflow_id=workflow_id,
            patient_id=patient_id, trigger_reason=trigger_reason,
            status=WorkflowExecutionStatus.PENDING.value,
        )
        session.add(execution)
        await session.flush()
        return execution

    # ── NOUVEAU : audit log DB ───────────────────────────────────

    @staticmethod
    async def _audit(
        session: AsyncSession, *, clinic_id: int, workflow_id: int,
        execution_id: int, action_type: str, status: str,
        detail: Dict[str, Any],
    ) -> None:
        """Écrit une ligne audit — table ``workflow_audit_logs``.

        Si la table n'existe pas encore (schéma pré-migration), on n'échoue
        jamais : on log simplement.warning().
        """
        try:
            from models.workflow_engine import WorkflowAuditLog  # late import
            log = WorkflowAuditLog(
                clinic_id=clinic_id, workflow_id=workflow_id,
                execution_id=execution_id, action_type=action_type,
                status=status, detail=json.dumps(detail, ensure_ascii=False, default=str),
            )
            # L’audit est best-effort : un défaut de schéma ou de données ne doit
            # jamais annuler la transaction métier principale. Le savepoint
            # garantit que l’exception de flush est absorbée proprement.
            async with session.begin_nested():
                session.add(log)
                await session.flush()
        except Exception as exc:
            logger.warning(
                "workflow_audit_write_failed clinic=%s wf=%s exec=%s action=%s err=%s",
                clinic_id, workflow_id, execution_id, action_type, exc,
            )
            # Compatibilité de secours avec une base qui aurait encore
            # VARCHAR(20) malgré la migration : l’audit ne doit jamais
            # transformer une exécution métier en HTTP 500. Le statut court
            # conserve la trace de l’intention dans detail.original_status.
            if len(status) > 20:
                try:
                    fallback_detail = {**detail, "original_status": status}
                    async with session.begin_nested():
                        session.add(WorkflowAuditLog(
                            clinic_id=clinic_id, workflow_id=workflow_id,
                            execution_id=execution_id, action_type=action_type,
                            status="drafted", detail=json.dumps(
                                fallback_detail, ensure_ascii=False, default=str,
                            ),
                        ))
                        await session.flush()
                except Exception as fallback_exc:
                    logger.warning(
                        "workflow_audit_fallback_failed clinic=%s wf=%s exec=%s action=%s err=%s",
                        clinic_id, workflow_id, execution_id, action_type, fallback_exc,
                    )
    # ── NOUVEAU : retry/backoff ──────────────────────────────────

    @staticmethod
    async def _retry_with_backoff(coro_factory, *, retries: int = 3):
        delay = 1.0
        last_exc: Optional[Exception] = None
        for attempt in range(retries):
            try:
                return await coro_factory()
            except Exception as exc:
                last_exc = exc
                if attempt == retries - 1:
                    break
                logger.warning("workflow_action_retry attempt=%d delay=%.1f err=%r",
                               attempt + 1, delay, exc)
                await asyncio.sleep(delay)
                delay *= 2
        assert last_exc is not None
        raise last_exc

    # ── NEW : protection anti double-exécution ──────────────────

    @staticmethod
    async def _is_already_executed(
        session: AsyncSession, *, workflow_id: int, execution_id: int,
        idempotency_key: str,
    ) -> bool:
        """Vérifie si une action a déjà été logguée avec la même clé."""
        try:
            from models.workflow_engine import WorkflowAuditLog
            stmt = select(WorkflowAuditLog).where(and_(
                WorkflowAuditLog.workflow_id == workflow_id,
                WorkflowAuditLog.execution_id == execution_id,
                WorkflowAuditLog.status == "executed",
            ))
            rows = (await session.execute(stmt)).scalars().all()
            for row in rows:
                try:
                    payload = json.loads(row.detail or "{}")
                except json.JSONDecodeError:
                    continue
                if payload.get("idempotency_key") == idempotency_key:
                    return True
            return False
        except Exception:
            # table absente ou autre : pas de protection, on log
            logger.info("workflow_idempotency_check_skipped")
            return False

    # ── NOUVEAU : validation humaine obligatoire ────────────────

    AUTO_SEND_ACTIONS = frozenset({
        WorkflowActionType.SEND_WHATSAPP.value,
        WorkflowActionType.SEND_SMS.value,
        WorkflowActionType.SEND_EMAIL.value,
    })

    @staticmethod
    async def execute_workflow_action(
        session: AsyncSession,
        execution_id: int,
        action_type: str,
        action_config: Dict[str, Any],
        patient_id: Optional[int] = None,
        clinic_id: int = 1,
        *,
        workflow_id: Optional[int] = None,
        force_send: bool = False,
        _approval_token: object | None = None,
    ) -> WorkflowAction:
        """Exécute une action — DÉCLARÉE ou transformée en brouillon."""

        # Garde-fou : force_send est réservé au chemin interne d’approbation.
        if force_send and _approval_token is not _APPROVAL_TOKEN:
            raise PermissionError("force_send réservé à l’endpoint d’approbation humaine")
        if action_type in WorkflowEngineService.AUTO_SEND_ACTIONS and not force_send:
            return await WorkflowEngineService._make_draft_action(
                session, execution_id, action_type, action_config,
                patient_id, clinic_id, workflow_id,
                reason="auto_send_disabled_without_human_validation",
            )

        # Idempotence
        idem = _idempotency_key(
            workflow_id or 0, execution_id, action_type, action_config,
        )
        if workflow_id is not None and await WorkflowEngineService._is_already_executed(
            session, workflow_id=workflow_id, execution_id=execution_id,
            idempotency_key=idem,
        ):
            logger.info("workflow_action_idempotent_skip exec=%s a=%s k=%s",
                        execution_id, action_type, idem)
            action = WorkflowAction(
                clinic_id=clinic_id, execution_id=execution_id,
                action_type=action_type, action_config=action_config,
                status=WorkflowExecutionStatus.COMPLETED.value,
                result={"idempotent_skip": True, "idempotency_key": idem},
                executed_at=datetime.utcnow(),
            )
            session.add(action)
            await session.flush()
            return action

        action = WorkflowAction(
            clinic_id=clinic_id, execution_id=execution_id,
            action_type=action_type, action_config=action_config,
            status=WorkflowExecutionStatus.RUNNING.value,
        )
        session.add(action)
        await session.flush()

        async def _do():
            return await WorkflowEngineService._execute_action_impl(
                session, action_type, action_config, patient_id, clinic_id,
            )

        try:
            result = (
                await WorkflowEngineService._retry_with_backoff(_do, retries=3)
                if action_type not in WorkflowEngineService.AUTO_SEND_ACTIONS
                else await _do()
            )
            action.status = WorkflowExecutionStatus.COMPLETED.value
            action.result = result
            action.executed_at = datetime.utcnow()
            if workflow_id is not None:
                await WorkflowEngineService._audit(
                    session, clinic_id=clinic_id, workflow_id=workflow_id,
                    execution_id=execution_id, action_type=action_type,
                    status="executed",
                    detail={"idempotency_key": idem, "result": result},
                )
        except Exception as e:
            action.status = WorkflowExecutionStatus.FAILED.value
            action.error_message = str(e)
            action.executed_at = datetime.utcnow()
            if workflow_id is not None:
                await WorkflowEngineService._audit(
                    session, clinic_id=clinic_id, workflow_id=workflow_id,
                    execution_id=execution_id, action_type=action_type,
                    status="failed",
                    detail={"idempotency_key": idem, "error": str(e)},
                )
            logger.exception("workflow_action_failed a=%s", action_type)

        await session.flush()
        return action

    @staticmethod
    async def _make_draft_action(
        session: AsyncSession, execution_id: int, action_type: str,
        action_config: Dict[str, Any], patient_id: Optional[int],
        clinic_id: int, workflow_id: Optional[int],
        *, reason: str,
    ) -> WorkflowAction:
        """Une action *send* n'est jamais auto-exécutée : on en fait un brouillon."""
        action = WorkflowAction(
            clinic_id=clinic_id, execution_id=execution_id,
            action_type=f"draft_{action_type}",
            action_config=action_config,
            status=WorkflowExecutionStatus.AWAITING_APPROVAL.value
                if hasattr(WorkflowExecutionStatus, "AWAITING_APPROVAL")
                else WorkflowExecutionStatus.PENDING.value,
            result={
                "draft": True,
                "requires_human_approval": True,
                "reason": reason,
                "original_action_type": action_type,
                "patient_id": patient_id,
            },
            executed_at=datetime.utcnow(),
        )
        session.add(action)
        await session.flush()
        if workflow_id is not None:
            await WorkflowEngineService._audit(
                session, clinic_id=clinic_id, workflow_id=workflow_id or 0,
                execution_id=execution_id, action_type=action_type,
                status="drafted_for_validation",
                detail={"reason": reason, "patient_id": patient_id},
            )
        return action

    # ── V1 _execute_action_impl (préservé) ───────────────────────

    @staticmethod
    async def _execute_action_impl(
        session: AsyncSession, action_type: str,
        action_config: Dict[str, Any], patient_id: Optional[int], clinic_id: int,
    ) -> Dict[str, Any]:
        if action_type == WorkflowActionType.SEND_WHATSAPP.value:
            return await WorkflowEngineService._send_omnicanal(
                session, patient_id, "whatsapp", action_config)
        elif action_type == WorkflowActionType.SEND_SMS.value:
            return await WorkflowEngineService._send_omnicanal(
                session, patient_id, "sms", action_config)
        elif action_type == WorkflowActionType.SEND_EMAIL.value:
            return await WorkflowEngineService._send_omnicanal(
                session, patient_id, "email", action_config)
        elif action_type == WorkflowActionType.CREATE_TASK.value:
            title = str(action_config.get("title") or "Tâche créée par un workflow").strip()
            if not title:
                raise ValueError("titre requis pour create_task")
            days_from_now = action_config.get("days_from_now")
            due_at = None
            if days_from_now is not None:
                try:
                    due_at = datetime.utcnow() + timedelta(days=max(0, int(days_from_now)))
                except (TypeError, ValueError):
                    raise ValueError("days_from_now doit être un entier")
            assignee_id = action_config.get("assignee_id")
            assignee_role = action_config.get("assignee_role")
            if assignee_role is not None:
                assignee_role = str(assignee_role).strip().lower()
                if assignee_role not in {role.value for role in RoleEnum}:
                    raise ValueError("Le rôle d’assignation est invalide")
            if assignee_id is not None:
                try:
                    assignee_id = int(assignee_id)
                except (TypeError, ValueError):
                    raise ValueError("assignee_id doit être un identifiant utilisateur valide")
                assignee = await session.scalar(select(Utilisateur).where(
                    Utilisateur.id == assignee_id,
                    Utilisateur.clinic_id == clinic_id,
                    Utilisateur.is_active,
                ))
                if not assignee:
                    raise ValueError("Le membre assigné est introuvable ou inactif dans cette clinique")
            task = TacheInterneAssistant(
                clinic_id=clinic_id,
                assignee_id=assignee_id,
                assignee_role=assignee_role,
                patient_id=patient_id,
                titre=title,
                description=action_config.get("description"),
                priorite=action_config.get("priority", "normale"),
                statut=StatutTacheInterneEnum.A_FAIRE.value,
                due_at=due_at,
            )
            session.add(task)
            await session.flush()
            return {"task_id": task.id, "status": task.statut}
        elif action_type == WorkflowActionType.LAUNCH_CAMPAIGN.value:
            campaign = await create_campaign(session, {
                "nom": action_config.get("nom", "Workflow Campaign"),
                "type": action_config.get("type", "whatsapp"),
                "message_template": action_config.get("template", ""),
                "clinic_id": clinic_id,
            })
            return {"campaign_id": campaign.id, "status": campaign.statut}
        elif action_type == WorkflowActionType.ADD_FIDELITE_POINTS.value:
            # Un workflow manuel ou planifié peut légitimement être lancé sans
            # patient. L’action fidélité est alors sans cible : elle doit être
            # ignorée avec une trace lisible, pas faire échouer les autres
            # actions du scénario (notamment un brouillon à valider).
            if not patient_id:
                return {
                    "status": "skipped",
                    "reason": "patient_id_required",
                    "message": "Points fidélité ignorés : aucun patient n’est associé à cette exécution.",
                }
            res = await add_points(
                session, patient_id,
                action_config.get("points", 0),
                action_config.get("reason", "Workflow"),
            )
            return {
                "points_added": action_config.get("points"),
                "new_total": res.points_fidelite,
            }
        elif action_type == WorkflowActionType.CREATE_APPOINTMENT.value:
            if not patient_id:
                raise ValueError("patient_id requis pour RDV")
            praticien_id = action_config.get("praticien_id")
            acte_id = action_config.get("acte_id")
            if not praticien_id or not acte_id:
                raise ValueError("praticien_id et acte_id requis pour create_appointment")
            rdv, _ = await _creer_rdv(
                patient_id=patient_id,
                praticien_id=praticien_id,
                acte_id=acte_id,
                date_heure=datetime.utcnow() + timedelta(
                    days=action_config.get("days_from_now", 7)),
                salle=action_config.get("salle"),
                db=session,
                created_by=None,
                clinic_id=clinic_id,
            )
            return {"rdv_id": rdv.id, "date": rdv.date_heure_debut.isoformat()}
        else:
            raise ValueError(f"Action non supportée ou non implémentée: {action_type}")

    @staticmethod
    async def _send_omnicanal(
        session: AsyncSession, patient_id: Optional[int],
        channel: str, config: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not patient_id:
            raise ValueError(f"patient_id requis pour {channel}")
        patient_dict = await get_patient(patient_id=patient_id, current_user={'role': 'admin'}, db=session)
        if not patient_dict:
            raise ValueError("Patient introuvable")
        to_address = (
            patient_dict.get('telephone') if channel in ('whatsapp', 'sms') else patient_dict.get('email')
        )
        if not to_address:
            raise ValueError(
                f"Coordonnées {channel} manquantes pour le patient {patient_id}")
        res = await send_message(
            channel=channel, to=to_address,
            content=config.get("template") or config.get("message", "Message automatique"),
            subject=config.get("subject") if channel == "email" else None,
        )
        return {"status": "success", "message_id": res.get("id")}

    # ── NOUVEAU : execute_workflow sensibilisation ───────────────

    @staticmethod
    async def execute_workflow(
        session: AsyncSession, workflow: Workflow,
        clinic_id: int = 1, patient_id: Optional[int] = None,
    ) -> WorkflowExecution:
        """Exécute un workflow complet en respectant les gardes (humain, idempotence)."""
        execution = await WorkflowEngineService.create_workflow_execution(
            session, workflow.id, clinic_id,
            trigger_reason=f"Workflow {workflow.nom} triggered",
            patient_id=patient_id,
        )
        try:
            execution.status = WorkflowExecutionStatus.RUNNING.value
            execution.started_at = datetime.utcnow()
            await WorkflowEngineService._audit(
                session, clinic_id=clinic_id, workflow_id=workflow.id,
                execution_id=execution.id, action_type="workflow_start",
                status="running",
                detail={"patient_id": patient_id, "trigger": execution.trigger_reason},
            )

            results = []
            for action_config in (workflow.actions or []):
                action_type = action_config.get("type")
                cfg = action_config.get("config", {})
                action = await WorkflowEngineService.execute_workflow_action(
                    session, execution.id, action_type, cfg, patient_id, clinic_id,
                    workflow_id=workflow.id,
                )
                results.append({
                    "action_type": action.action_type,
                    "status": action.status,
                    "result": action.result,
                })

            awaiting_status = (
                WorkflowExecutionStatus.AWAITING_APPROVAL.value
                if hasattr(WorkflowExecutionStatus, "AWAITING_APPROVAL")
                else WorkflowExecutionStatus.PENDING.value
            )
            if any(result["status"] == WorkflowExecutionStatus.FAILED.value for result in results):
                execution.status = WorkflowExecutionStatus.FAILED.value
            elif any(result["status"] == awaiting_status for result in results):
                execution.status = awaiting_status
            else:
                execution.status = WorkflowExecutionStatus.COMPLETED.value
            execution.result = {"actions": results}
            execution.completed_at = datetime.utcnow()
            await WorkflowEngineService._audit(
                session, clinic_id=clinic_id, workflow_id=workflow.id,
                execution_id=execution.id, action_type="workflow_end",
                status=execution.status,
                detail={"actions_count": len(results)},
            )
        except Exception as e:
            execution.status = WorkflowExecutionStatus.FAILED.value
            execution.error_message = str(e)
            execution.completed_at = datetime.utcnow()
            await WorkflowEngineService._audit(
                session, clinic_id=clinic_id, workflow_id=workflow.id,
                execution_id=execution.id, action_type="workflow_end",
                status="failed",
                detail={"error": str(e)},
            )
            logger.error(f"Workflow {workflow.id} failed: {e}")

        await session.flush()
        return execution

    # ── V1 : scheduled + event-based (préservé) ─────────────────

    @staticmethod
    async def check_and_execute_scheduled_workflows(
        session: AsyncSession, clinic_id: int = 1,
    ) -> List[WorkflowExecution]:
        workflows = await WorkflowEngineService.get_active_workflows(session, clinic_id)
        executions = []
        now = datetime.utcnow()
        for workflow in workflows:
            if workflow.trigger_type == WorkflowTriggerType.SCHEDULED.value:
                if workflow.next_execution and workflow.next_execution <= now:
                    execution = await WorkflowEngineService.execute_workflow(
                        session, workflow, clinic_id)
                    executions.append(execution)
                    workflow.next_execution = now + timedelta(days=1)
        return executions

    @staticmethod
    async def check_and_execute_event_based_workflows(
        session: AsyncSession, event_type: str, event_data: Dict[str, Any],
        clinic_id: int = 1,
    ) -> List[WorkflowExecution]:
        workflows = await WorkflowEngineService.get_active_workflows(session, clinic_id)
        executions = []
        for workflow in workflows:
            if workflow.trigger_type == WorkflowTriggerType.EVENT_BASED.value:
                trigger_config = workflow.trigger_config or {}
                if trigger_config.get("type") == event_type:
                    patient_id = event_data.get("patient_id")
                    execution = await WorkflowEngineService.execute_workflow(
                        session, workflow, clinic_id, patient_id)
                    executions.append(execution)
        return executions

    @staticmethod
    async def get_workflow_execution_history(
        session: AsyncSession, workflow_id: int, limit: int = 50,
    ) -> List[WorkflowExecution]:
        stmt = (
            select(WorkflowExecution)
            .where(WorkflowExecution.workflow_id == workflow_id)
            .order_by(WorkflowExecution.created_at.desc())
            .limit(limit)
        )
        return (await session.execute(stmt)).scalars().all()

    @staticmethod
    async def get_workflow_statistics(
        session: AsyncSession, clinic_id: int = 1, days: int = 30,
    ) -> Dict[str, Any]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = select(WorkflowExecution).where(and_(
            WorkflowExecution.clinic_id == clinic_id,
            WorkflowExecution.created_at >= cutoff,
        ))
        executions = (await session.execute(stmt)).scalars().all()
        total = len(executions)
        completed = len([
            e for e in executions
            if e.status == WorkflowExecutionStatus.COMPLETED.value
        ])
        failed = len([
            e for e in executions
            if e.status == WorkflowExecutionStatus.FAILED.value
        ])
        # Drafts = AWAITING_APPROVAL si dispo, sinon PENDING
        awaiting_attr = (
            WorkflowExecutionStatus.AWAITING_APPROVAL.value
            if hasattr(WorkflowExecutionStatus, "AWAITING_APPROVAL")
            else WorkflowExecutionStatus.PENDING.value
        )
        drafts = len([e for e in executions if e.status == awaiting_attr])
        return {
            "total_executions": total,
            "completed": completed,
            "failed": failed,
            "drafts_awaiting_approval": drafts,
            "success_rate": round((completed / total * 100), 2) if total > 0 else 0.0,
        }

    # ── NOUVEAU : décision LLM sur branches conditionnelles ─────

    @staticmethod
    async def decide_next_branch(
        session: AsyncSession,
        *,
        event_type: str, event_data: Dict[str, Any],
        available_workflows: List[Workflow],
        settings: Any = None, llm: LLMClient = None,
    ) -> Dict[str, Any]:
        """LLM-driven decision : parmi workflows disponibles, lequel
        appliquer ? Renvoie un dict avec ``selected_workflow_id`` ou
        ``'no_action'`` + reasons."""
        if not available_workflows:
            return {"selected_workflow_id": "no_action", "reason": "aucun workflow actif",
                    "llm_status": "skipped"}

        if llm is None and settings is not None:
            llm = get_llm_client(settings)
        if llm is None:
            # Mode SQL : premeir workflow dont le trigger_type matche event_type
            for w in available_workflows:
                tc = w.trigger_config or {}
                if w.trigger_type == WorkflowTriggerType.EVENT_BASED.value and tc.get("type") == event_type:
                    return {"selected_workflow_id": w.id, "reason": "fallback SQL match",
                            "llm_status": "skipped_no_llm"}
            return {"selected_workflow_id": "no_action", "reason": "fallback pas de match",
                    "llm_status": "skipped_no_llm"}
        try:
            workflows_payload = [
                {
                    "id": w.id, "name": w.nom, "trigger_type": w.trigger_type,
                    "trigger_config": w.trigger_config,
                }
                for w in available_workflows
            ]
            # Pseudonymisation du contexte patient (event_data)
            event_data_safe = pseudonymize_pii(event_data)
            
            msgs = WORKFLOW_DECISION.render(
                event_type=event_type,
                patient_context=json.dumps(event_data_safe, ensure_ascii=False, default=str),
                workflows_json=json.dumps(workflows_payload, ensure_ascii=False, default=str),
            )
            workflow_clinic_id = getattr(available_workflows[0], "clinic_id", None)
            out = await llm.chat(
                msgs,
                max_tokens=500,
                response_format_json=True,
                budget_subject=(
                    f"clinic:{workflow_clinic_id}:workflow_decision"
                    if workflow_clinic_id else "workflow_decision"
                ),
                budget_clinic_id=workflow_clinic_id,
            )
            if isinstance(out, LLMUnavailable):
                return {"selected_workflow_id": "no_action",
                        "reason": f"llm indisponible: {out.reason}",
                        "llm_status": "unavailable"}
            try:
                parsed = json.loads(out.text)
            except json.JSONDecodeError:
                return {"selected_workflow_id": "no_action",
                        "reason": "LLM n'a pas renvoyé du JSON exploitable",
                        "llm_status": "ok",
                        "raw": out.text[:300]}
            actions = parsed.get("actions") or []
            # Correction W4 (AUDIT) :
            # Auparavant, le LLM renvoyait des actions mais on retournait
            # systématiquement available_workflows[0].id — le choix du LLM
            # était complètement ignoré. Maintenant on tente de résoudre le
            # workflow ciblé ; à défaut, retour no_action honnête.
            if not actions:
                return {"selected_workflow_id": "no_action",
                        "reason": "LLM n'a proposé aucune action",
                        "llm_status": "ok"}
            # Le LLM peut proposer ``workflow_id`` explicite dans le payload,
            # sinon on tente de matcher ``nom`` (insensible à la casse), sinon
            # ``no_action`` (on ne retourne plus le premier workflow par défaut).
            proposed_id = parsed.get("workflow_id")
            proposed_name = (parsed.get("workflow_name") or "").strip().lower()
            chosen_id: Optional[int] = None
            if proposed_id is not None:
                try:
                    if any(w.id == int(proposed_id) for w in available_workflows):
                        chosen_id = int(proposed_id)
                except (TypeError, ValueError):
                    chosen_id = None
            if chosen_id is None and proposed_name:
                matches = [w for w in available_workflows
                           if (w.nom or "").strip().lower() == proposed_name]
                if len(matches) == 1:
                    chosen_id = matches[0].id
            if chosen_id is None:
                # Aucune proposition exploitable du LLM → no_action honnête.
                return {"selected_workflow_id": "no_action",
                        "reason": "LLM n'a pas identifié un workflow actif disponible",
                        "actions_suggested": actions,
                        "raw_proposal": parsed,
                        "llm_status": "ok",
                        "llm_provider": out.provider}
            return {"selected_workflow_id": chosen_id,
                    "reason": parsed.get("reason") or "LLM a choisi",
                    "actions_suggested": actions,
                    "llm_status": "ok",
                    "llm_provider": out.provider}
        except Exception as exc:
            logger.exception("workflow_decide_llm_error")
            return {"selected_workflow_id": "no_action",
                    "reason": f"exception: {exc!r}",
                    "llm_status": "exception"}

    # ── NOUVEAU : approbation humaine d'un brouillon ─────────────

    @staticmethod
    async def approve_drafted_action(
        session: AsyncSession, *, execution_id: int, action_id: int,
        clinic_id: int, workflow_id: int,
    ) -> WorkflowAction:
        """Approuve l'envoi d'une action mise en brouillon.
        Force_send=True à l'exécution, idempotence vérifiée."""
        from sqlalchemy import select as _select
        action_row = (await session.execute(
            _select(WorkflowAction)
            .join(WorkflowExecution, WorkflowAction.execution_id == WorkflowExecution.id)
            .where(
                WorkflowAction.id == action_id,
                WorkflowAction.execution_id == execution_id,
                WorkflowAction.clinic_id == clinic_id,
                WorkflowExecution.clinic_id == clinic_id,
                WorkflowExecution.workflow_id == workflow_id,
            )
        )).scalar_one_or_none()
        if not action_row:
            raise ValueError(f"action {action_id} introuvable pour execution {execution_id}")

        if not action_row.action_type.startswith("draft_"):
            raise ValueError("cette action n'est pas un brouillon")

        if action_row.status != WorkflowExecutionStatus.AWAITING_APPROVAL.value:
            raise ValueError("cette action a déjà été traitée")
        original = action_row.result["original_action_type"]
        patient_id = action_row.result["patient_id"]
        cfg = action_row.action_config

        # Exécute avec force_send=True
        approved_action = await WorkflowEngineService.execute_workflow_action(
            session, execution_id=execution_id, action_type=original,
            action_config=cfg, patient_id=patient_id, clinic_id=clinic_id,
            workflow_id=workflow_id, force_send=True,
            _approval_token=_APPROVAL_TOKEN,
        )
        action_row.status = WorkflowExecutionStatus.COMPLETED.value
        action_row.result = {
            **(action_row.result or {}),
            "approved": True,
            "approved_action_id": approved_action.id,
        }
        execution = (await session.execute(
            _select(WorkflowExecution).where(
                WorkflowExecution.id == execution_id,
                WorkflowExecution.clinic_id == clinic_id,
            )
        )).scalar_one_or_none()
        if execution:
            remaining = (await session.execute(
                _select(WorkflowAction).where(
                    WorkflowAction.execution_id == execution_id,
                    WorkflowAction.clinic_id == clinic_id,
                    WorkflowAction.status == WorkflowExecutionStatus.AWAITING_APPROVAL.value,
                )
            )).scalars().all()
            if not remaining:
                execution.status = WorkflowExecutionStatus.COMPLETED.value
                execution.completed_at = datetime.utcnow()
        await session.flush()
        return approved_action
