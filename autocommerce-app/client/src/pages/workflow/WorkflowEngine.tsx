import { useEffect, useState } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { toast } from 'sonner';
import {
  Plus,
  Edit2,
  Trash2,
  Play,
  BarChart3,
  AlertCircle,
  CheckCircle,
  Clock,
  XCircle,
  Pause,
  History,
} from 'lucide-react';

interface JsonObject {
  [key: string]: unknown;
}

interface WorkflowActionDefinition {
  type: string;
  config?: JsonObject;
}

interface Workflow {
  id: number;
  nom: string;
  description?: string | null;
  trigger_type: string;
  trigger_config?: JsonObject | null;
  conditions?: JsonObject | null;
  actions?: WorkflowActionDefinition[];
  cron_expression?: string | null;
  enabled: boolean;
  status: string;
  created_at: string;
}

interface WorkflowTemplate extends Omit<Workflow, 'id' | 'enabled' | 'status' | 'created_at'> {
  id: string;
  categorie?: string;
}

interface WorkflowStats {
  total_executions: number;
  completed: number;
  failed: number;
  drafts_awaiting_approval: number;
  success_rate: number;
}

interface WorkflowTriggerPreset {
  key: string;
  triggerType: string;
  eventType: string;
  label: string;
  description: string;
}

interface WorkflowActionType {
  value: string;
  label: string;
  description: string;
  tone: string;
}

interface WorkflowCatalog {
  triggers: WorkflowTriggerPreset[];
  actions: WorkflowActionType[];
  patient_segments?: { value: string; label: string }[];
  appointment_scopes?: { value: string; label: string }[];
}

interface WorkflowExecution {
  id: number;
  status: string;
  trigger_reason: string;
  result?: JsonObject | null;
  created_at: string;
}

interface WorkflowActionLog {
  id: number;
  action_type: string;
  action_config?: JsonObject | null;
  status: string;
  result?: JsonObject | null;
  error_message?: string | null;
  executed_at?: string | null;
}

interface TeamMember {
  id: number;
  nom: string;
  prenom: string;
  role: string;
  is_active: boolean;
}

interface WorkflowFormValue {
  nom: string;
  description: string;
  trigger_key: string;
  delay_days: number;
  only_active_patients: boolean;
  exclude_opted_out: boolean;
  patient_segment: 'all' | 'new' | 'returning' | 'vip';
  appointment_scope: 'any' | 'confirmed' | 'completed';
  actions: VisualActionDraft[];
}

interface VisualActionDraft {
  type: string;
  recipient: 'patient' | 'equipe';
  assignee_id: number | null;
  assignee_role: string | null;
  message: string;
  task_title: string;
  priority: 'low' | 'medium' | 'high';
  delay_days: number;
  points: number;
  reason: string;
}

const TRIGGER_PRESETS = [
  { key: 'manual', triggerType: 'manual', eventType: 'manual', label: 'À la demande', description: 'Le membre de l’équipe lance le scénario lorsqu’il le décide.' },
  { key: 'after_act', triggerType: 'event_based', eventType: 'appointment_completed', label: 'Après un acte', description: 'À la fin d’un rendez-vous ou d’un acte enregistré.' },
  { key: 'after_injection', triggerType: 'event_based', eventType: 'injection_completed', label: 'Après une injection', description: 'Pour organiser un contrôle ou un suivi spécifique.' },
  { key: 'after_treatment', triggerType: 'event_based', eventType: 'aesthetic_treatment_completed', label: 'Après un traitement esthétique', description: 'Pour préparer un suivi à distance.' },
  { key: 'callback_request', triggerType: 'event_based', eventType: 'callback_requested', label: 'Quand un rappel est demandé', description: 'Pour ne laisser aucune demande de rappel sans suite.' },
  { key: 'pending_consent', triggerType: 'event_based', eventType: 'consent_pending', label: 'Quand un consentement manque', description: 'Pour préparer le rappel de signature avant un acte.' },
  { key: 'inactive_patient', triggerType: 'condition_based', eventType: 'patient_inactive', label: 'Patient inactif', description: 'Après une période sans visite, définie ci-dessous.' },
  { key: 'unaccepted_quote', triggerType: 'condition_based', eventType: 'quote_not_accepted', label: 'Devis non accepté', description: 'Après un délai de relance défini ci-dessous.' },
  { key: 'monthly', triggerType: 'scheduled', eventType: 'monthly', label: 'Chaque mois', description: 'Pour une revue ou une campagne planifiée.' },
  { key: 'birthday', triggerType: 'scheduled', eventType: 'birthday', label: 'Anniversaire patient', description: 'Le jour de l’anniversaire du patient.' },
];

const ACTION_TYPES = [
  { value: 'create_task', label: 'Créer une tâche interne', description: 'Visible dans la file de l’équipe.', tone: 'teal' },
  { value: 'send_whatsapp', label: 'Préparer un WhatsApp', description: 'Toujours soumis à validation humaine avant envoi.', tone: 'amber' },
  { value: 'send_sms', label: 'Préparer un SMS', description: 'Toujours soumis à validation humaine avant envoi.', tone: 'amber' },
  { value: 'send_email', label: 'Préparer un e-mail', description: 'Toujours soumis à validation humaine avant envoi.', tone: 'amber' },
  { value: 'add_fidelite_points', label: 'Ajouter des points fidélité', description: 'Valorise un suivi ou une campagne définie.', tone: 'violet' },
  { value: 'launch_campaign', label: 'Préparer une campagne', description: 'Prépare une campagne à vérifier avant diffusion.', tone: 'violet' },
];

const ASSIGNMENT_ROLE_OPTIONS = [
  { value: 'assistante', label: 'Équipe d’assistance' },
  { value: 'medecin', label: 'Praticien médecin' },
  { value: 'estheticienne', label: 'Praticien esthétique' },
  { value: 'directrice', label: 'Direction clinique' },
];

const PATIENT_SEGMENT_OPTIONS = [
  { value: 'all', label: 'Tous les patients éligibles' },
  { value: 'new', label: 'Nouveaux patients' },
  { value: 'returning', label: 'Patients déjà suivis' },
  { value: 'vip', label: 'Patients VIP / fidélité élevée' },
] as const;

const APPOINTMENT_SCOPE_OPTIONS = [
  { value: 'any', label: 'Tout contexte de rendez-vous' },
  { value: 'confirmed', label: 'Rendez-vous confirmé' },
  { value: 'completed', label: 'Acte ou rendez-vous réalisé' },
] as const;

const DEFAULT_WORKFLOW_CATALOG: WorkflowCatalog = {
  triggers: TRIGGER_PRESETS,
  actions: ACTION_TYPES,
  patient_segments: [...PATIENT_SEGMENT_OPTIONS],
  appointment_scopes: [...APPOINTMENT_SCOPE_OPTIONS],
};

const DEFAULT_ACTION: VisualActionDraft = {
  type: 'create_task',
  recipient: 'equipe',
  assignee_id: null,
  assignee_role: null,
  message: '',
  task_title: 'Contacter le patient',
  priority: 'medium',
  delay_days: 0,
  points: 0,
  reason: '',
};

const EMPTY_FORM: WorkflowFormValue = {
  nom: '',
  description: '',
  trigger_key: 'after_act',
  delay_days: 1,
  only_active_patients: true,
  exclude_opted_out: true,
  patient_segment: 'all',
  appointment_scope: 'any',
  actions: [{ ...DEFAULT_ACTION }],
};

const STATUS_LABELS: Record<string, string> = {
  draft: 'Brouillon',
  active: 'Actif',
  paused: 'En pause',
  archived: 'Archivé',
  pending: 'En attente',
  running: 'En cours',
  completed: 'Terminé',
  failed: 'Échoué',
  awaiting_approval: 'À approuver',
};

const getErrorMessage = (error: any, fallback: string) =>
  error?.response?.data?.detail || error?.message || fallback;

type WorkflowFormSource = Partial<Omit<Workflow, 'id'>>;

const inferTriggerKey = (workflow: WorkflowFormSource) => {
  const eventType = workflow.trigger_config?.type;
  return TRIGGER_PRESETS.find((preset) => preset.eventType === eventType)?.key
    || TRIGGER_PRESETS.find((preset) => preset.triggerType === workflow.trigger_type)?.key
    || 'after_act';
};

const workflowToForm = (workflow: WorkflowFormSource, triggerPresets = TRIGGER_PRESETS): WorkflowFormValue => {
  const config = workflow.trigger_config || {};
  const conditions = workflow.conditions || {};
  return {
    nom: workflow.nom || '',
    description: workflow.description || '',
    trigger_key: triggerPresets.find((preset) => preset.eventType === config.type)?.key
      || triggerPresets.find((preset) => preset.triggerType === workflow.trigger_type)?.key
      || inferTriggerKey(workflow),
    delay_days: Number(config.delay_days ?? config.days ?? (Math.ceil(Number(config.delay_hours || 0) / 24) || 0)),
    only_active_patients: conditions.patient_status !== 'inactive',
    exclude_opted_out: conditions.opted_out !== false,
    patient_segment: ['new', 'returning', 'vip'].includes(String(conditions.patient_segment)) ? String(conditions.patient_segment) as WorkflowFormValue['patient_segment'] : 'all',
    appointment_scope: ['confirmed', 'completed'].includes(String(conditions.appointment_status)) ? String(conditions.appointment_status) as WorkflowFormValue['appointment_scope'] : 'any',
    actions: workflow.actions?.length ? workflow.actions.map((action) => {
      const actionConfig = action.config || {};
      return {
        type: action.type,
        recipient: actionConfig.recipient === 'equipe' ? 'equipe' : ['send_whatsapp', 'send_sms', 'send_email', 'add_fidelite_points'].includes(action.type) ? 'patient' : 'equipe',
        assignee_id: typeof actionConfig.assignee_id === 'number' ? actionConfig.assignee_id : null,
        assignee_role: typeof actionConfig.assignee_role === 'string' ? actionConfig.assignee_role : null,
        message: String(actionConfig.message || actionConfig.template || ''),
        task_title: String(actionConfig.title || 'Contacter le patient'),
        priority: ['low', 'medium', 'high'].includes(String(actionConfig.priority)) ? String(actionConfig.priority) as VisualActionDraft['priority'] : 'medium',
        delay_days: Number(actionConfig.days_from_now || 0),
        points: Number(actionConfig.points || 0),
        reason: String(actionConfig.reason || ''),
      };
    }) : [{ ...DEFAULT_ACTION }],
  };
};

const visualFormToPayload = (value: WorkflowFormValue, triggerPresets = TRIGGER_PRESETS) => {
  const preset = triggerPresets.find((item) => item.key === value.trigger_key) || triggerPresets[0] || TRIGGER_PRESETS[0];
  const triggerConfig: JsonObject = { type: preset.eventType };
  if (['after_act', 'after_injection', 'after_treatment', 'callback_request', 'pending_consent'].includes(preset.key)) triggerConfig.delay_days = Math.max(0, value.delay_days);
  if (['inactive_patient', 'unaccepted_quote'].includes(preset.key)) triggerConfig.days = Math.max(0, value.delay_days);
  const conditions: JsonObject = {};
  if (value.only_active_patients) conditions.patient_status = 'active';
  if (value.exclude_opted_out) conditions.opted_out = false;
  if (value.patient_segment !== 'all') conditions.patient_segment = value.patient_segment;
  if (value.appointment_scope !== 'any') conditions.appointment_status = value.appointment_scope;
  const actions = value.actions.map((action) => {
    if (action.type === 'create_task') return { type: action.type, config: { title: action.task_title.trim() || 'Tâche clinique', priority: action.priority, days_from_now: Math.max(0, action.delay_days), recipient: action.recipient, assignee_id: action.assignee_id || undefined, assignee_role: action.assignee_role || undefined } };
    if (['send_whatsapp', 'send_sms', 'send_email'].includes(action.type)) return { type: action.type, config: { template: action.message.trim() || 'message_clinique_a_valider', message: action.message.trim(), recipient: action.recipient } };
    if (action.type === 'add_fidelite_points') return { type: action.type, config: { points: Math.max(0, action.points), reason: action.reason.trim() || 'Programme fidélité clinique', recipient: action.recipient } };
    return { type: action.type, config: { nom: action.task_title.trim() || 'Campagne clinique', template: action.message.trim(), recipient: action.recipient } };
  });
  return { nom: value.nom.trim(), description: value.description.trim() || undefined, trigger_type: preset.triggerType, trigger_config: triggerConfig, conditions: Object.keys(conditions).length ? conditions : undefined, actions };
};

export default function WorkflowEngine() {
  const [isLoading, setIsLoading] = useState(true);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [stats, setStats] = useState<WorkflowStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorMode, setEditorMode] = useState<'create' | 'edit'>('create');
  const [editingWorkflowId, setEditingWorkflowId] = useState<number | null>(null);
  const [editorInitialValue, setEditorInitialValue] = useState<WorkflowFormValue>(EMPTY_FORM);
  const [executionTarget, setExecutionTarget] = useState<Workflow | null>(null);
  const [historyTarget, setHistoryTarget] = useState<Workflow | null>(null);
  const [activationTarget, setActivationTarget] = useState<Workflow | null>(null);
  const [workflowCatalog, setWorkflowCatalog] = useState<WorkflowCatalog>(DEFAULT_WORKFLOW_CATALOG);

  const loadData = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const [workflowsRes, statsRes, templatesRes, usersRes, catalogRes] = await Promise.all([
        api.get('/workflows/'),
        api.get('/workflows/statistics/summary'),
        api.get('/workflows/templates'),
        api.get('/users'),
        api.get('/workflows/catalog'),
      ]);
      setWorkflows(Array.isArray(workflowsRes.data?.data) ? workflowsRes.data.data : []);
      setStats(statsRes.data?.data || null);
      setTemplates(Array.isArray(templatesRes.data?.data) ? templatesRes.data.data : []);
      setTeamMembers(Array.isArray(usersRes.data) ? usersRes.data.filter((member: TeamMember) => member.is_active) : []);
      const remoteCatalog = catalogRes.data?.data;
      if (Array.isArray(remoteCatalog?.triggers) && Array.isArray(remoteCatalog?.actions)) {
        setWorkflowCatalog({
          triggers: remoteCatalog.triggers.map((item: any) => ({ key: item.key, triggerType: item.trigger_type, eventType: item.event_type, label: item.label, description: item.description })),
          actions: remoteCatalog.actions,
          patient_segments: remoteCatalog.patient_segments,
          appointment_scopes: remoteCatalog.appointment_scopes,
        });
      }
    } catch (err: any) {
      const message = getErrorMessage(err, 'Erreur lors du chargement des workflows');
      setError(message);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  const openCreate = (template?: WorkflowTemplate) => {
    setEditorMode('create');
    setEditingWorkflowId(null);
    setEditorInitialValue(template ? workflowToForm(template, workflowCatalog.triggers) : { ...EMPTY_FORM, actions: [{ ...DEFAULT_ACTION }] });
    setEditorOpen(true);
  };

  const openEdit = async (workflow: Workflow) => {
    try {
      const response = await api.get(`/workflows/${workflow.id}`);
      setEditorMode('edit');
      setEditingWorkflowId(workflow.id);
      setEditorInitialValue(workflowToForm(response.data?.data || workflow, workflowCatalog.triggers));
      setEditorOpen(true);
    } catch (err: any) {
      toast.error(getErrorMessage(err, 'Impossible de charger le workflow'));
    }
  };

  const handleDeleteWorkflow = async (workflow: Workflow) => {
    if (!window.confirm(`Supprimer le workflow « ${workflow.nom} » ?`)) return;
    try {
      await api.delete(`/workflows/${workflow.id}`);
      toast.success('Workflow supprimé');
      await loadData();
    } catch (err: any) {
      toast.error(getErrorMessage(err, 'Erreur lors de la suppression du workflow'));
    }
  };

  const handleToggleWorkflow = async (workflow: Workflow, enabled = !workflow.enabled) => {
    try {
      await api.put(`/workflows/${workflow.id}`, {
        enabled,
      });
      toast.success(enabled ? 'Scénario activé' : 'Scénario mis en pause');
      await loadData();
    } catch (err: any) {
      toast.error(getErrorMessage(err, 'Erreur lors du changement de statut'));
    }
  };

  const handleExecuteWorkflow = async (workflow: Workflow, patientId?: number) => {
    try {
      const response = patientId
        ? await api.post(`/workflows/${workflow.id}/execute`, undefined, { params: { patient_id: patientId } })
        : await api.post(`/workflows/${workflow.id}/execute`);
      const executionStatus = response.data?.data?.status;
      if (executionStatus === 'awaiting_approval') {
        toast.success('Workflow exécuté : une validation humaine est requise');
      } else if (executionStatus === 'failed') {
        toast.error('Le workflow a échoué. Consultez son historique.');
      } else {
        toast.success('Workflow exécuté');
      }
      setExecutionTarget(null);
      await loadData();
      setHistoryTarget(workflow);
    } catch (err: any) {
      toast.error(getErrorMessage(err, "Erreur lors de l'exécution du workflow"));
    }
  };

  const handleSaveWorkflow = async (value: WorkflowFormValue) => {
    try {
      const payload = visualFormToPayload(value, workflowCatalog.triggers);
      if (!payload.nom) throw new Error('Le nom du workflow est obligatoire');

      if (editorMode === 'edit') {
        if (!editingWorkflowId) throw new Error('Workflow à modifier introuvable');
        await api.put(`/workflows/${editingWorkflowId}`, payload);
        toast.success('Workflow mis à jour');
      } else {
        await api.post('/workflows/', payload);
        toast.success('Workflow créé en brouillon');
      }
      setEditorOpen(false);
      await loadData();
    } catch (err: any) {
      toast.error(getErrorMessage(err, 'Impossible d’enregistrer le workflow'));
      throw err;
    }
  };

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-screen"><Spinner /></div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-slate-950">Scénarios et rappels cliniques</h1>
            <p className="mt-2 text-slate-600">Composez des rappels et actions d’équipe en langage métier, avec validation et traçabilité.</p>
          </div>
          <Button onClick={() => openCreate()} className="gap-2">
            <Plus className="w-5 h-5" /> Nouveau scénario
          </Button>
        </div>

        {error && (
          <Card className="border-red-200 bg-red-50">
            <CardContent className="pt-6 flex items-center gap-2 text-red-700">
              <AlertCircle className="w-5 h-5" /> <span>{error}</span>
            </CardContent>
          </Card>
        )}

        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            <StatCard title="Total" value={stats.total_executions} detail="Exécutions (30 j)" />
            <StatCard title="Réussies" value={stats.completed} detail="Complétées" tone="green" />
            <StatCard title="Échouées" value={stats.failed} detail="Erreurs" tone="red" />
            <StatCard title="À valider" value={stats.drafts_awaiting_approval} detail="Approbations humaines" tone="yellow" />
            <StatCard title="Taux de réussite" value={`${(stats.success_rate || 0).toFixed(1)}%`} detail="Succès" />
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {workflows.length === 0 ? (
            <Card className="lg:col-span-2"><CardContent className="pt-12 pb-12 text-center text-gray-500">Aucun scénario créé. Commencez à partir d’un modèle clinique ou composez votre propre scénario.</CardContent></Card>
          ) : workflows.map((workflow) => (
            <Card key={workflow.id} className={workflow.enabled ? '' : 'opacity-70'}>
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <CardTitle className="text-lg">{workflow.nom}</CardTitle>
                    {workflow.description && <p className="text-sm text-gray-600 mt-1">{workflow.description}</p>}
                  </div>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${workflow.status === 'active' ? 'bg-green-100 text-green-700' : workflow.status === 'paused' ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-700'}`}>
                    <span className="sr-only">{workflow.status}</span>
                    {STATUS_LABELS[workflow.status] || workflow.status}
                  </span>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div><p className="text-xs text-gray-600">Déclencheur</p><p className="text-sm font-medium">{workflowCatalog.triggers.find((item) => item.triggerType === workflow.trigger_type)?.label || workflow.trigger_type}</p></div>
                  <div><p className="text-xs text-gray-600">Créé le</p><p className="text-sm font-medium">{new Date(workflow.created_at).toLocaleDateString('fr-FR')}</p></div>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mt-4 pt-4 border-t">
                  <Button size="sm" variant="outline" onClick={() => void handleExecuteWorkflow(workflow)} className="gap-1"><Play className="w-3.5 h-3.5" /> Exécuter</Button>
                  <Button size="sm" variant="outline" onClick={() => openEdit(workflow)} className="gap-1"><Edit2 className="w-3.5 h-3.5" /> Éditer</Button>
                  <Button size="sm" variant="outline" onClick={() => workflow.enabled ? void handleToggleWorkflow(workflow, false) : setActivationTarget(workflow)} className="gap-1"><Pause className="w-3.5 h-3.5" /> {workflow.enabled ? 'Pause' : 'Revoir puis activer'}</Button>
                  <Button size="sm" variant="outline" onClick={() => setHistoryTarget(workflow)} className="gap-1"><History className="w-3.5 h-3.5" /> Historique</Button>
                  <Button size="sm" variant="outline" onClick={() => handleDeleteWorkflow(workflow)} className="gap-1 text-red-600 hover:text-red-700"><Trash2 className="w-3.5 h-3.5" /> Supprimer</Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><BarChart3 className="w-5 h-5" /> Modèles cliniques prêts à adapter</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {templates.map((template) => (
                <button key={template.id} type="button" onClick={() => openCreate(template)} className="p-4 rounded-lg border bg-gray-50 text-left hover:bg-blue-50 hover:border-blue-300 transition">
                  <p className="font-medium text-sm">{template.nom}</p>
                  <p className="text-xs text-gray-600 mt-1">{template.description}</p>
                  <p className="mt-3 text-xs text-teal-700">Adapter ce modèle</p>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <WorkflowEditorDialog
        open={editorOpen}
        mode={editorMode}
        initialValue={editorInitialValue}
        teamMembers={teamMembers}
        workflowCatalog={workflowCatalog}
        onOpenChange={setEditorOpen}
        onSave={handleSaveWorkflow}
      />
      <ExecuteWorkflowDialog
        workflow={executionTarget}
        onOpenChange={(open) => { if (!open) setExecutionTarget(null); }}
        onExecute={handleExecuteWorkflow}
      />
      <WorkflowHistoryDialog
        workflow={historyTarget}
        onOpenChange={(open) => { if (!open) setHistoryTarget(null); }}
      />
      <WorkflowActivationDialog
        workflow={activationTarget}
        onOpenChange={(open) => { if (!open) setActivationTarget(null); }}
        onActivate={async (workflow) => { await handleToggleWorkflow(workflow, true); setActivationTarget(null); }}
      />
    </DashboardLayout>
  );
}

function StatCard({ title, value, detail, tone }: { title: string; value: string | number; detail: string; tone?: 'green' | 'red' | 'yellow' }) {
  const toneClass = tone === 'green' ? 'border-green-200 bg-green-50 text-green-700' : tone === 'red' ? 'border-red-200 bg-red-50 text-red-700' : tone === 'yellow' ? 'border-yellow-200 bg-yellow-50 text-yellow-700' : '';
  return <Card className={toneClass}><CardHeader className="pb-2"><CardTitle className="text-sm font-medium">{title}</CardTitle></CardHeader><CardContent><div className="text-3xl font-bold">{value}</div><p className="text-xs mt-2">{detail}</p></CardContent></Card>;
}

function WorkflowActivationDialog({ workflow, onOpenChange, onActivate }: { workflow: Workflow | null; onOpenChange: (open: boolean) => void; onActivate: (workflow: Workflow) => Promise<void>; }) {
  const [reviewed, setReviewed] = useState(false);
  const [isActivating, setIsActivating] = useState(false);
  useEffect(() => { if (workflow) { setReviewed(false); setIsActivating(false); } }, [workflow]);
  const trigger = workflow ? TRIGGER_PRESETS.find((item) => item.triggerType === workflow.trigger_type) : undefined;
  return <Dialog open={!!workflow} onOpenChange={onOpenChange}><DialogContent className="max-w-xl"><DialogHeader><DialogTitle>Revoir avant activation</DialogTitle><DialogDescription>Le scénario reste en brouillon tant que cette revue n’est pas confirmée.</DialogDescription></DialogHeader>{workflow && <div className="space-y-4"><div className="rounded-xl border border-slate-200 bg-slate-50 p-4"><p className="text-xs font-semibold uppercase tracking-[0.14em] text-teal-700">Scénario</p><p className="mt-1 font-semibold text-slate-950">{workflow.nom}</p>{workflow.description && <p className="mt-1 text-sm text-slate-600">{workflow.description}</p>}<p className="mt-3 text-sm text-slate-700"><strong>Déclencheur :</strong> {trigger?.label || workflow.trigger_type}</p></div><div className="rounded-xl border border-slate-200 p-4"><p className="text-sm font-semibold text-slate-900">Actions prévues</p><ul className="mt-2 space-y-2 text-sm text-slate-600">{workflow.actions?.map((action, index) => <li key={`${action.type}-${index}`} className="flex gap-2"><span className="font-semibold text-teal-700">{index + 1}.</span>{ACTION_TYPES.find((item) => item.value === action.type)?.label || action.type}</li>) || <li>Aucune action détectée.</li>}</ul></div><label className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950"><input type="checkbox" checked={reviewed} onChange={(event) => setReviewed(event.target.checked)} className="mt-0.5 accent-teal-700" /><span>J’ai vérifié le déclencheur, les actions et les destinataires. Les messages externes restent à approuver avant envoi.</span></label></div>}<DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)}>Retour</Button><Button disabled={!reviewed || isActivating || !workflow} onClick={async () => { if (!workflow) return; setIsActivating(true); try { await onActivate(workflow); } finally { setIsActivating(false); } }} className="bg-teal-700 text-white hover:bg-teal-800">{isActivating ? <Spinner className="h-4 w-4" /> : 'Activer le scénario'}</Button></DialogFooter></DialogContent></Dialog>;
}

function WorkflowEditorDialog({ open, mode, initialValue, teamMembers, workflowCatalog, onOpenChange, onSave }: { open: boolean; mode: 'create' | 'edit'; initialValue: WorkflowFormValue; teamMembers: TeamMember[]; workflowCatalog: WorkflowCatalog; onOpenChange: (open: boolean) => void; onSave: (value: WorkflowFormValue) => Promise<void>; }) {
  const [form, setForm] = useState<WorkflowFormValue>(initialValue);
  const [isSaving, setIsSaving] = useState(false);
  const [brief, setBrief] = useState('');

  useEffect(() => { if (open) { setForm(initialValue); setBrief(''); } }, [open, initialValue]);

  const updateField = <K extends keyof WorkflowFormValue>(field: K, value: WorkflowFormValue[K]) => setForm((current) => ({ ...current, [field]: value }));
  const updateAction = <K extends keyof VisualActionDraft>(index: number, field: K, value: VisualActionDraft[K]) => setForm((current) => ({ ...current, actions: current.actions.map((action, actionIndex) => actionIndex === index ? { ...action, [field]: value } : action) }));
  const addAction = () => setForm((current) => ({ ...current, actions: [...current.actions, { ...DEFAULT_ACTION }] }));
  const removeAction = (index: number) => setForm((current) => ({ ...current, actions: current.actions.filter((_, actionIndex) => actionIndex !== index) }));
  const trigger = workflowCatalog.triggers.find((item) => item.key === form.trigger_key) || workflowCatalog.triggers[0] || TRIGGER_PRESETS[0];
  const proposeFromBrief = () => {
    const normalized = brief.trim().toLocaleLowerCase('fr-FR');
    if (!normalized) { toast.error('Décrivez le besoin clinique à couvrir.'); return; }
    const proposedTrigger = normalized.includes('consent') ? 'pending_consent'
      : normalized.includes('rappel') || normalized.includes('appeler') ? 'callback_request'
      : normalized.includes('injection') ? 'after_injection'
      : normalized.includes('devis') ? 'unaccepted_quote'
      : normalized.includes('inactif') ? 'inactive_patient'
      : normalized.includes('post') || normalized.includes('suivi') ? 'after_act'
      : 'manual';
    const daysMatch = normalized.match(/(\d+)\s*jour/);
    const hoursMatch = normalized.match(/(\d+)\s*(?:h|heure)/);
    const delay = daysMatch ? Math.min(365, Math.max(0, Number(daysMatch[1])))
      : hoursMatch ? Math.max(1, Math.ceil(Number(hoursMatch[1]) / 24))
      : normalized.includes('demain') ? 1
      : normalized.includes('semaine') ? 7
      : 1;
    const actionType = normalized.includes('sms') ? 'send_sms'
      : normalized.includes('email') || normalized.includes('e-mail') ? 'send_email'
      : normalized.includes('whatsapp') || normalized.includes('message') ? 'send_whatsapp'
      : 'create_task';
    const assigneeRole = normalized.includes('assistante') || normalized.includes('secrétaire') ? 'assistante'
      : normalized.includes('esthéticienne') ? 'estheticienne'
      : normalized.includes('médecin') || normalized.includes('docteur') ? 'medecin'
      : null;
    setForm((current) => ({
      ...current,
      nom: current.nom || `Scénario — ${brief.trim().slice(0, 70)}`,
      description: current.description || brief.trim(),
      trigger_key: proposedTrigger,
      delay_days: delay,
      actions: [{ ...DEFAULT_ACTION, type: actionType, recipient: actionType === 'create_task' ? 'equipe' : 'patient', assignee_role: actionType === 'create_task' ? assigneeRole : null, message: actionType === 'create_task' ? '' : brief.trim(), task_title: normalized.includes('consent') ? 'Relancer la signature du consentement' : normalized.includes('rappel') ? 'Rappeler le patient' : 'Vérifier le suivi patient', delay_days: 0 }],
    }));
    toast.success('Proposition créée : relisez-la puis adaptez-la avant enregistrement.');
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (form.actions.length === 0) { toast.error('Ajoutez au moins une action'); return; }
    setIsSaving(true);
    try { await onSave(form); } catch { /* Le parent affiche l’erreur. */ } finally { setIsSaving(false); }
  };

  return <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
      <DialogHeader><DialogTitle>{mode === 'edit' ? 'Modifier le scénario' : 'Nouveau scénario clinique'}</DialogTitle><DialogDescription>Construisez le scénario avec des mots métier. Les messages restent toujours à valider humainement avant envoi.</DialogDescription></DialogHeader>
      <form onSubmit={submit} className="space-y-6">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2"><div><Label htmlFor="workflow-nom">Nom du scénario *</Label><Input id="workflow-nom" value={form.nom} onChange={(event) => updateField('nom', event.target.value)} placeholder="Ex. Rappel de contrôle après injection" required maxLength={200} /></div><div><Label htmlFor="workflow-description">Objectif clinique</Label><Input id="workflow-description" value={form.description} onChange={(event) => updateField('description', event.target.value)} placeholder="Ex. Ne pas oublier le contrôle à J+14" maxLength={5000} /></div></div>
        <section className="rounded-2xl border border-violet-100 bg-violet-50/70 p-4"><div className="flex flex-col gap-3 sm:flex-row sm:items-end"><div className="flex-1"><Label htmlFor="workflow-brief" className="text-violet-950">Génération guidée par modèles métier</Label><Input id="workflow-brief" value={brief} onChange={(event) => setBrief(event.target.value)} placeholder="Ex. Rappeler les patients trois jours après une injection" className="mt-1 bg-white" /><p className="mt-1 text-xs text-violet-800">Une proposition modifiable sera créée ; aucune règle n’est activée automatiquement.</p></div><Button type="button" onClick={proposeFromBrief} className="bg-violet-700 text-white hover:bg-violet-800">Proposer une base</Button></div></section>
        <section className="rounded-2xl border border-slate-200 bg-slate-50 p-4"><div className="flex items-center justify-between"><div><p className="text-sm font-semibold text-slate-900">1. Quand faut-il agir ?</p><p className="text-xs text-slate-500">Choisissez un déclencheur clinique ou opérationnel.</p></div><span className="rounded-full bg-teal-100 px-2.5 py-1 text-xs font-semibold text-teal-800">Déclencheur</span></div><div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">{workflowCatalog.triggers.map((preset) => <button type="button" key={preset.key} onClick={() => updateField('trigger_key', preset.key)} className={`rounded-xl border p-3 text-left transition-colors ${form.trigger_key === preset.key ? 'border-teal-400 bg-teal-50 ring-2 ring-teal-100' : 'border-slate-200 bg-white hover:border-teal-200'}`}><span className="block text-sm font-semibold text-slate-900">{preset.label}</span><span className="mt-1 block text-xs leading-5 text-slate-500">{preset.description}</span></button>)}</div>{trigger.key !== 'manual' && trigger.key !== 'birthday' && trigger.key !== 'monthly' && <div className="mt-4 max-w-xs"><Label htmlFor="workflow-delay">Délai avant action (jours)</Label><Input id="workflow-delay" type="number" min="0" max="365" value={form.delay_days} onChange={(event) => updateField('delay_days', Number(event.target.value) || 0)} /></div>}</section>
        <section className="rounded-2xl border border-slate-200 bg-white p-4"><div><p className="text-sm font-semibold text-slate-900">2. Pour quels patients ?</p><p className="text-xs text-slate-500">Ces règles protègent les préférences de contact du patient.</p></div><div className="mt-4 grid gap-3 sm:grid-cols-2"><label className="flex items-start gap-3 rounded-xl border border-slate-200 p-3 text-sm text-slate-700"><input type="checkbox" checked={form.only_active_patients} onChange={(event) => updateField('only_active_patients', event.target.checked)} className="mt-0.5 accent-teal-700" /><span><strong className="font-medium text-slate-900">Patients actifs uniquement</strong><br />Ne pas inclure les dossiers inactifs.</span></label><label className="flex items-start gap-3 rounded-xl border border-slate-200 p-3 text-sm text-slate-700"><input type="checkbox" checked={form.exclude_opted_out} onChange={(event) => updateField('exclude_opted_out', event.target.checked)} className="mt-0.5 accent-teal-700" /><span><strong className="font-medium text-slate-900">Respecter le refus de contact</strong><br />Exclure les patients opposés aux communications.</span></label></div></section>
        <section className="rounded-2xl border border-slate-200 bg-white p-4"><div><p className="text-sm font-semibold text-slate-900">2 bis. Affiner le contexte clinique</p><p className="text-xs text-slate-500">Choisissez des paramètres métier supplémentaires sans manipuler de données techniques.</p></div><div className="mt-4 grid gap-3 sm:grid-cols-2"><div><Label htmlFor="workflow-patient-segment">Segment clinique</Label><select id="workflow-patient-segment" aria-label="Segment clinique" value={form.patient_segment} onChange={(event) => updateField('patient_segment', event.target.value as WorkflowFormValue['patient_segment'])} className="mt-1 h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm">{(workflowCatalog.patient_segments || PATIENT_SEGMENT_OPTIONS).map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></div><div><Label htmlFor="workflow-appointment-scope">Contexte du rendez-vous</Label><select id="workflow-appointment-scope" aria-label="Contexte du rendez-vous" value={form.appointment_scope} onChange={(event) => updateField('appointment_scope', event.target.value as WorkflowFormValue['appointment_scope'])} className="mt-1 h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm">{(workflowCatalog.appointment_scopes || APPOINTMENT_SCOPE_OPTIONS).map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></div></div></section>
        <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4"><div className="flex items-center justify-between"><div><p className="text-sm font-semibold text-slate-900">3. Que doit faire l’équipe ?</p><p className="text-xs text-slate-500">Ajoutez une ou plusieurs actions dans l’ordre.</p></div><Button type="button" variant="outline" size="sm" onClick={addAction}><Plus className="mr-1 h-4 w-4" /> Ajouter</Button></div>{form.actions.map((action, index) => { const actionDefinition = workflowCatalog.actions.find((item) => item.value === action.type); return <div key={`${index}-${action.type}`} className="rounded-xl border border-slate-200 bg-slate-50 p-3"><div className="flex flex-wrap items-center gap-2"><select aria-label={`Action ${index + 1}`} value={action.type} onChange={(event) => updateAction(index, 'type', event.target.value)} className="h-10 min-w-52 flex-1 rounded-lg border border-slate-300 bg-white px-3 text-sm">{workflowCatalog.actions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select><select aria-label={`Destinataire de l’action ${index + 1}`} value={action.recipient} onChange={(event) => updateAction(index, 'recipient', event.target.value as VisualActionDraft['recipient'])} className="h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm"><option value="patient">Pour le patient</option><option value="equipe">Pour l’équipe</option></select><Button type="button" variant="ghost" size="sm" onClick={() => removeAction(index)} disabled={form.actions.length === 1} className="text-red-600"><Trash2 className="h-4 w-4" /></Button></div><p className="mt-2 text-xs text-slate-500">{actionDefinition?.description}</p>{action.type === 'create_task' && <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_140px_110px]"><Input value={action.task_title} onChange={(event) => updateAction(index, 'task_title', event.target.value)} placeholder="Ex. Appeler le patient" /><select value={action.priority} onChange={(event) => updateAction(index, 'priority', event.target.value as VisualActionDraft['priority'])} className="rounded-lg border border-slate-300 bg-white px-3 text-sm"><option value="low">Priorité basse</option><option value="medium">Priorité normale</option><option value="high">Priorité élevée</option></select><Input type="number" min="0" value={action.delay_days} onChange={(event) => updateAction(index, 'delay_days', Number(event.target.value) || 0)} aria-label="Délai de tâche en jours" /></div>}{['send_whatsapp', 'send_sms', 'send_email'].includes(action.type) && <div className="mt-3"><Label>Consigne ou modèle de message</Label><Textarea value={action.message} onChange={(event) => updateAction(index, 'message', event.target.value)} rows={2} placeholder="Ex. Prendre des nouvelles du patient et proposer un créneau de contrôle." /><p className="mt-1 text-[11px] text-amber-700">Le message est préparé comme brouillon et demande une approbation humaine.</p></div>}{action.type === 'add_fidelite_points' && <div className="mt-3 grid gap-3 sm:grid-cols-[120px_1fr]"><Input type="number" min="0" value={action.points} onChange={(event) => updateAction(index, 'points', Number(event.target.value) || 0)} aria-label="Nombre de points" /><Input value={action.reason} onChange={(event) => updateAction(index, 'reason', event.target.value)} placeholder="Motif des points" /></div>}{action.type === 'launch_campaign' && <div className="mt-3 grid gap-3"><Input value={action.task_title} onChange={(event) => updateAction(index, 'task_title', event.target.value)} placeholder="Nom de la campagne" /><Textarea value={action.message} onChange={(event) => updateAction(index, 'message', event.target.value)} rows={2} placeholder="Objectif ou contenu à faire valider" /></div>}</div>; })}</section>
        {form.actions.some((action) => action.type === 'create_task') && <section className="rounded-2xl border border-slate-200 bg-white p-4"><p className="text-sm font-semibold text-slate-900">4. À qui attribuer les tâches ?</p><p className="mt-1 text-xs text-slate-500">Laissez la tâche dans la file commune, assignez-la à un rôle, ou désignez un membre actif précis.</p><div className="mt-3 space-y-3">{form.actions.map((action, index) => action.type === 'create_task' ? <div key={`assignee-${index}`} className="rounded-xl bg-slate-50 p-3"><p className="mb-2 text-sm text-slate-700">{action.task_title || `Tâche ${index + 1}`}</p><div className="grid gap-2 sm:grid-cols-2"><select aria-label={`Rôle responsable de la tâche ${index + 1}`} value={action.assignee_role ?? ''} onChange={(event) => { const role = event.target.value || null; updateAction(index, 'assignee_role', role); if (role) updateAction(index, 'assignee_id', null); }} className="h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm"><option value="">File d’équipe non attribuée</option>{ASSIGNMENT_ROLE_OPTIONS.map((role) => <option key={role.value} value={role.value}>{role.label}</option>)}</select><select aria-label={`Responsable nommé de la tâche ${index + 1}`} value={action.assignee_id ?? ''} onChange={(event) => { const assigneeId = event.target.value ? Number(event.target.value) : null; updateAction(index, 'assignee_id', assigneeId); if (assigneeId) updateAction(index, 'assignee_role', null); }} className="h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm"><option value="">Choisir un membre précis</option>{teamMembers.map((member) => <option key={member.id} value={member.id}>{member.prenom} {member.nom} · {member.role}</option>)}</select></div></div> : null)}</div></section>}
        <section className="rounded-2xl border border-teal-200 bg-teal-50 p-4"><p className="text-xs font-semibold uppercase tracking-[0.14em] text-teal-700">Prévisualisation avant enregistrement</p><p className="mt-2 text-sm leading-6 text-teal-950">Quand <strong>{trigger.label.toLocaleLowerCase('fr-FR')}</strong>{form.delay_days > 0 ? `, après ${form.delay_days} jour${form.delay_days > 1 ? 's' : ''}` : ''}, le scénario appliquera {form.actions.length} action{form.actions.length > 1 ? 's' : ''} pour les patients correspondant aux règles choisies.</p></section>
        <DialogFooter><Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button><Button type="submit" disabled={isSaving} className="bg-teal-700 text-white hover:bg-teal-800">{isSaving ? <Spinner className="w-4 h-4" /> : mode === 'edit' ? 'Enregistrer la version' : 'Créer le brouillon à valider'}</Button></DialogFooter>
      </form>
    </DialogContent>
  </Dialog>;
}

function ExecuteWorkflowDialog({ workflow, onOpenChange, onExecute }: { workflow: Workflow | null; onOpenChange: (open: boolean) => void; onExecute: (workflow: Workflow, patientId?: number) => Promise<void>; }) {
  const [patientId, setPatientId] = useState('');
  useEffect(() => { if (workflow) setPatientId(''); }, [workflow]);
  const submit = async (event: React.FormEvent) => { event.preventDefault(); const parsed = patientId.trim() ? Number(patientId) : undefined; if (patientId.trim() && (!Number.isInteger(parsed) || (parsed || 0) <= 0)) { toast.error('L’identifiant patient doit être un entier positif'); return; } if (workflow) await onExecute(workflow, parsed); };
  return <Dialog open={!!workflow} onOpenChange={onOpenChange}><DialogContent><DialogHeader><DialogTitle>Exécuter « {workflow?.nom} »</DialogTitle><DialogDescription>Pour les actions destinées à un patient, indiquez son identifiant interne. Les messages sortants restent soumis à approbation humaine.</DialogDescription></DialogHeader><form onSubmit={submit} className="space-y-4"><div><Label htmlFor="workflow-patient-id">Patient ID (optionnel)</Label><Input id="workflow-patient-id" type="number" min="1" value={patientId} onChange={(event) => setPatientId(event.target.value)} placeholder="Ex. 42" /></div><DialogFooter><Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button><Button type="submit"><Play className="w-4 h-4 mr-2" /> Exécuter</Button></DialogFooter></form></DialogContent></Dialog>;
}

function WorkflowHistoryDialog({ workflow, onOpenChange }: { workflow: Workflow | null; onOpenChange: (open: boolean) => void; }) {
  const [executions, setExecutions] = useState<WorkflowExecution[]>([]);
  const [selectedExecutionId, setSelectedExecutionId] = useState<number | null>(null);
  const [actions, setActions] = useState<WorkflowActionLog[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingActions, setIsLoadingActions] = useState(false);

  useEffect(() => {
    if (!workflow) return;
    let cancelled = false;
    setIsLoading(true);
    api.get(`/workflows/${workflow.id}/executions`)
      .then((response) => { if (!cancelled) { const data = Array.isArray(response.data?.data) ? response.data.data : []; setExecutions(data); setSelectedExecutionId(data[0]?.id || null); } })
      .catch((error) => { if (!cancelled) toast.error(getErrorMessage(error, 'Impossible de charger l’historique')); })
      .finally(() => { if (!cancelled) setIsLoading(false); });
    return () => { cancelled = true; };
  }, [workflow]);

  useEffect(() => {
    if (!selectedExecutionId) { setActions([]); return; }
    let cancelled = false;
    setIsLoadingActions(true);
    api.get(`/workflows/executions/${selectedExecutionId}/actions`)
      .then((response) => { if (!cancelled) setActions(Array.isArray(response.data?.data) ? response.data.data : []); })
      .catch((error) => { if (!cancelled) toast.error(getErrorMessage(error, 'Impossible de charger les actions')); })
      .finally(() => { if (!cancelled) setIsLoadingActions(false); });
    return () => { cancelled = true; };
  }, [selectedExecutionId]);

  const approve = async (action: WorkflowActionLog, executionId: number) => {
    if (!workflow) return;
    try {
      await api.post(`/workflows/executions/${executionId}/approve-action`, { action_id: action.id, workflow_id: workflow.id });
      toast.success('Action approuvée et exécutée');
      const response = await api.get(`/workflows/executions/${executionId}/actions`);
      setActions(Array.isArray(response.data?.data) ? response.data.data : []);
    } catch (error: any) { toast.error(getErrorMessage(error, 'Impossible d’approuver cette action')); }
  };

  return <Dialog open={!!workflow} onOpenChange={onOpenChange}><DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto"><DialogHeader><DialogTitle>Historique — {workflow?.nom}</DialogTitle><DialogDescription>Consultez les exécutions et validez les actions qui nécessitent une intervention humaine.</DialogDescription></DialogHeader>{isLoading ? <div className="flex justify-center py-8"><Spinner /></div> : executions.length === 0 ? <p className="text-sm text-muted-foreground py-6">Aucune exécution enregistrée.</p> : <div className="grid grid-cols-1 md:grid-cols-2 gap-4"><div className="space-y-2">{executions.map((execution) => <button type="button" key={execution.id} onClick={() => setSelectedExecutionId(execution.id)} className={`w-full text-left border rounded-md p-3 ${selectedExecutionId === execution.id ? 'border-blue-500 bg-blue-50' : 'hover:bg-gray-50'}`}><div className="flex items-center justify-between gap-2"><span className="font-medium">#{execution.id}</span><ExecutionStatus status={execution.status} /></div><p className="text-xs text-gray-600 mt-1">{execution.trigger_reason}</p><p className="text-xs text-gray-500 mt-1">{new Date(execution.created_at).toLocaleString('fr-FR')}</p></button>)}</div><div className="border rounded-md p-4">{isLoadingActions ? <div className="flex justify-center py-8"><Spinner /></div> : actions.length === 0 ? <p className="text-sm text-muted-foreground">Aucune action pour cette exécution.</p> : <div className="space-y-3">{actions.map((action) => <div key={action.id} className="border-b last:border-b-0 pb-3 last:pb-0"><div className="flex items-center justify-between gap-2"><span className="text-sm font-medium">{action.action_type}</span><ExecutionStatus status={action.status} /></div>{action.error_message && <p className="text-xs text-red-600 mt-1">{action.error_message}</p>}{action.status === 'awaiting_approval' && <Button size="sm" className="mt-2" onClick={() => selectedExecutionId && approve(action, selectedExecutionId)}><CheckCircle className="w-4 h-4 mr-1" /> Approuver</Button>}</div>)}</div>}</div></div>}<DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)}>Fermer</Button></DialogFooter></DialogContent></Dialog>;
}

function ExecutionStatus({ status }: { status: string }) {
  const label = STATUS_LABELS[status] || status;
  if (status === 'completed') return <span className="inline-flex items-center gap-1 text-xs text-green-700"><CheckCircle className="w-3.5 h-3.5" />{label}</span>;
  if (status === 'failed') return <span className="inline-flex items-center gap-1 text-xs text-red-700"><XCircle className="w-3.5 h-3.5" />{label}</span>;
  if (status === 'awaiting_approval') return <span className="inline-flex items-center gap-1 text-xs text-yellow-700"><Clock className="w-3.5 h-3.5" />{label}</span>;
  return <span className="inline-flex items-center gap-1 text-xs text-gray-600"><Clock className="w-3.5 h-3.5" />{label}</span>;
}
