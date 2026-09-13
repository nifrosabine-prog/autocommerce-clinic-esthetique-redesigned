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

interface WorkflowFormValue {
  nom: string;
  description: string;
  trigger_type: string;
  trigger_config_text: string;
  conditions_text: string;
  actions: ActionDraft[];
  simple_delay: string;
  simple_delay_unit: 'heures' | 'jours';
  simple_message: string;
  require_approval: boolean;
  advanced_mode: boolean;
}

interface ActionDraft {
  type: string;
  config_text: string;
}

const TRIGGER_TYPES = [
  { value: 'manual', label: 'Manuel' },
  { value: 'event_based', label: 'Événement clinique' },
  { value: 'condition_based', label: 'Condition patient' },
  { value: 'scheduled', label: 'Planifié' },
];

const ACTION_TYPES = [
  { value: 'send_whatsapp', label: 'Préparer un WhatsApp' },
  { value: 'send_sms', label: 'Préparer un SMS' },
  { value: 'send_email', label: 'Préparer un e-mail' },
  { value: 'create_task', label: 'Créer une tâche interne' },
  { value: 'create_appointment', label: 'Créer un rendez-vous' },
  { value: 'add_fidelite_points', label: 'Ajouter des points fidélité' },
  { value: 'launch_campaign', label: 'Lancer une campagne' },
];

const DEFAULT_ACTION: ActionDraft = {
  type: 'send_whatsapp',
  config_text: '{\n  "template": "Message de suivi"\n}',
};

const EMPTY_FORM: WorkflowFormValue = {
  nom: '',
  description: '',
  trigger_type: 'manual',
  trigger_config_text: '',
  conditions_text: '',
  actions: [{ ...DEFAULT_ACTION }],
  simple_delay: '24',
  simple_delay_unit: 'heures',
  simple_message: 'Bonjour {{prénom}}, nous espérons que votre soin s’est bien passé. Souhaitez-vous être rappelé par notre équipe ?',
  require_approval: true,
  advanced_mode: false,
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

const stringifyJson = (value?: JsonObject | null) =>
  value && Object.keys(value).length > 0 ? JSON.stringify(value, null, 2) : '';

type WorkflowFormSource = Partial<Omit<Workflow, 'id'>>;

const workflowToForm = (workflow: WorkflowFormSource): WorkflowFormValue => ({
  nom: workflow.nom || '',
  description: workflow.description || '',
  trigger_type: workflow.trigger_type || 'manual',
  trigger_config_text: stringifyJson(workflow.trigger_config),
  conditions_text: stringifyJson(workflow.conditions),
  actions: workflow.actions?.length
    ? workflow.actions.map((action) => ({
        type: action.type,
        config_text: stringifyJson(action.config),
      }))
    : [{ ...DEFAULT_ACTION }],
  simple_delay: String((workflow.trigger_config?.delay_hours as number) || 24),
  simple_delay_unit: 'heures',
  simple_message: String((workflow.actions?.[0]?.config?.template as string) || 'Bonjour {{prénom}}, nous espérons que votre soin s’est bien passé. Souhaitez-vous être rappelé par notre équipe ?'),
  require_approval: true,
  advanced_mode: false,
});

const parseJsonObject = (value: string, fieldLabel: string): JsonObject | undefined => {
  if (!value.trim()) return undefined;
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch {
    throw new Error(`${fieldLabel} doit contenir un JSON valide`);
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(`${fieldLabel} doit être un objet JSON`);
  }
  return parsed as JsonObject;
};

export default function WorkflowEngine() {
  const [isLoading, setIsLoading] = useState(true);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [stats, setStats] = useState<WorkflowStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorMode, setEditorMode] = useState<'create' | 'edit'>('create');
  const [editingWorkflowId, setEditingWorkflowId] = useState<number | null>(null);
  const [editorInitialValue, setEditorInitialValue] = useState<WorkflowFormValue>(EMPTY_FORM);
  const [executionTarget, setExecutionTarget] = useState<Workflow | null>(null);
  const [historyTarget, setHistoryTarget] = useState<Workflow | null>(null);

  const loadData = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const [workflowsRes, statsRes, templatesRes] = await Promise.all([
        api.get('/workflows/'),
        api.get('/workflows/statistics/summary'),
        api.get('/workflows/templates'),
      ]);
      setWorkflows(Array.isArray(workflowsRes.data?.data) ? workflowsRes.data.data : []);
      setStats(statsRes.data?.data || null);
      setTemplates(Array.isArray(templatesRes.data?.data) ? templatesRes.data.data : []);
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
    setEditorInitialValue(template ? workflowToForm(template) : { ...EMPTY_FORM, actions: [{ ...DEFAULT_ACTION }] });
    setEditorOpen(true);
  };

  const openEdit = async (workflow: Workflow) => {
    try {
      const response = await api.get(`/workflows/${workflow.id}`);
      setEditorMode('edit');
      setEditingWorkflowId(workflow.id);
      setEditorInitialValue(workflowToForm(response.data?.data || workflow));
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

  const handleToggleWorkflow = async (workflow: Workflow) => {
    try {
      await api.put(`/workflows/${workflow.id}`, {
        enabled: !workflow.enabled,
      });
      toast.success(workflow.enabled ? 'Workflow mis en pause' : 'Workflow activé');
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
      const actions = value.actions.map((action) => ({
        type: action.type,
        config: parseJsonObject(action.config_text, `Configuration de l’action ${action.type}`) || {},
      }));
      const payload = {
        nom: value.nom.trim(),
        description: value.description.trim() || undefined,
        trigger_type: value.trigger_type,
        trigger_config: parseJsonObject(value.trigger_config_text, 'Configuration du déclencheur'),
        conditions: parseJsonObject(value.conditions_text, 'Conditions'),
        actions,
      };
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
            <h1 className="text-3xl font-bold text-gray-900">Moteur de Workflows</h1>
            <p className="text-gray-600 mt-2">Automatisez les processus cliniques avec validation et traçabilité.</p>
          </div>
          <Button onClick={() => openCreate()} className="gap-2">
            <Plus className="w-5 h-5" /> Nouveau Workflow
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
            <Card className="lg:col-span-2"><CardContent className="pt-12 pb-12 text-center text-gray-500">Aucun workflow créé. Commencez par en créer un ou utilisez un modèle.</CardContent></Card>
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
                  <div><p className="text-xs text-gray-600">Déclencheur</p><p className="text-sm font-medium">{TRIGGER_TYPES.find((item) => item.value === workflow.trigger_type)?.label || workflow.trigger_type}</p></div>
                  <div><p className="text-xs text-gray-600">Créé le</p><p className="text-sm font-medium">{new Date(workflow.created_at).toLocaleDateString('fr-FR')}</p></div>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mt-4 pt-4 border-t">
                  <Button size="sm" variant="outline" onClick={() => void handleExecuteWorkflow(workflow)} className="gap-1"><Play className="w-3.5 h-3.5" /> Exécuter</Button>
                  <Button size="sm" variant="outline" onClick={() => openEdit(workflow)} className="gap-1"><Edit2 className="w-3.5 h-3.5" /> Éditer</Button>
                  <Button size="sm" variant="outline" onClick={() => handleToggleWorkflow(workflow)} className="gap-1"><Pause className="w-3.5 h-3.5" /> {workflow.enabled ? 'Pause' : 'Activer'}</Button>
                  <Button size="sm" variant="outline" onClick={() => setHistoryTarget(workflow)} className="gap-1"><History className="w-3.5 h-3.5" /> Historique</Button>
                  <Button size="sm" variant="outline" onClick={() => handleDeleteWorkflow(workflow)} className="gap-1 text-red-600 hover:text-red-700"><Trash2 className="w-3.5 h-3.5" /> Supprimer</Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><BarChart3 className="w-5 h-5" /> Modèles prédéfinis</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {templates.map((template) => (
                <button key={template.id} type="button" onClick={() => openCreate(template)} className="p-4 rounded-lg border bg-gray-50 text-left hover:bg-blue-50 hover:border-blue-300 transition">
                  <p className="font-medium text-sm">{template.nom}</p>
                  <p className="text-xs text-gray-600 mt-1">{template.description}</p>
                  <p className="text-xs text-blue-700 mt-3">Utiliser ce modèle</p>
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
    </DashboardLayout>
  );
}

function StatCard({ title, value, detail, tone }: { title: string; value: string | number; detail: string; tone?: 'green' | 'red' | 'yellow' }) {
  const toneClass = tone === 'green' ? 'border-green-200 bg-green-50 text-green-700' : tone === 'red' ? 'border-red-200 bg-red-50 text-red-700' : tone === 'yellow' ? 'border-yellow-200 bg-yellow-50 text-yellow-700' : '';
  return <Card className={toneClass}><CardHeader className="pb-2"><CardTitle className="text-sm font-medium">{title}</CardTitle></CardHeader><CardContent><div className="text-3xl font-bold">{value}</div><p className="text-xs mt-2">{detail}</p></CardContent></Card>;
}

function WorkflowEditorDialog({ open, mode, initialValue, onOpenChange, onSave }: { open: boolean; mode: 'create' | 'edit'; initialValue: WorkflowFormValue; onOpenChange: (open: boolean) => void; onSave: (value: WorkflowFormValue) => Promise<void>; }) {
  const [form, setForm] = useState<WorkflowFormValue>(initialValue);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => { if (open) setForm(initialValue); }, [open, initialValue]);

  const updateField = (field: keyof WorkflowFormValue, value: string) => setForm((current) => ({ ...current, [field]: value }));
  const updateAction = (index: number, field: keyof ActionDraft, value: string) => setForm((current) => ({ ...current, actions: current.actions.map((action, actionIndex) => actionIndex === index ? { ...action, [field]: value } : action) }));
  const addAction = () => setForm((current) => ({ ...current, actions: [...current.actions, { ...DEFAULT_ACTION }] }));
  const removeAction = (index: number) => setForm((current) => ({ ...current, actions: current.actions.filter((_, actionIndex) => actionIndex !== index) }));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (form.actions.length === 0) { toast.error('Ajoutez au moins une action'); return; }
    const delay = Math.max(1, Number(form.simple_delay) || 24);
    const firstAction = form.actions[0];
    const guidedTrigger = form.trigger_type === 'event_based'
      ? { type: 'appointment_completed', delay_hours: form.simple_delay_unit === 'jours' ? delay * 24 : delay }
      : form.trigger_type === 'condition_based'
        ? { inactive_days: form.simple_delay_unit === 'jours' ? delay : delay / 24 }
        : form.trigger_type === 'scheduled'
          ? { reminder_delay: `${delay} ${form.simple_delay_unit}` }
          : {};
    const guidedActionConfig = firstAction.type.startsWith('send_')
      ? { template: form.simple_message.trim(), personalization: true, require_approval: form.require_approval }
      : firstAction.type === 'create_task'
        ? { title: form.simple_message.trim() || form.nom.trim(), priority: 'medium', require_approval: form.require_approval }
        : { require_approval: form.require_approval };
    const guidedForm = form.advanced_mode ? form : {
      ...form,
      trigger_config_text: JSON.stringify(guidedTrigger),
      conditions_text: JSON.stringify({ opted_out: false }),
      actions: [{ ...firstAction, config_text: JSON.stringify(guidedActionConfig) }, ...form.actions.slice(1)],
    };
    setIsSaving(true);
    try { await onSave(guidedForm); } catch { /* Le parent affiche l’erreur. */ } finally { setIsSaving(false); }
  };

  return <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
      <DialogHeader><DialogTitle>{mode === 'edit' ? 'Modifier le workflow' : 'Nouveau workflow'}</DialogTitle><DialogDescription>Définissez le déclencheur et les actions à exécuter.</DialogDescription></DialogHeader>
      <form onSubmit={submit} className="space-y-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div><Label htmlFor="workflow-nom">Nom *</Label><Input id="workflow-nom" value={form.nom} onChange={(event) => updateField('nom', event.target.value)} required maxLength={200} /></div>
          <div><Label htmlFor="workflow-trigger">Déclencheur *</Label><select id="workflow-trigger" value={form.trigger_type} onChange={(event) => updateField('trigger_type', event.target.value)} className="w-full h-9 px-3 border rounded-md text-sm">{TRIGGER_TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></div>
        </div>
        <div><Label htmlFor="workflow-description">Description</Label><Textarea id="workflow-description" value={form.description} onChange={(event) => updateField('description', event.target.value)} rows={2} maxLength={5000} /></div>
        {!form.advanced_mode && <Card className="border-blue-100 bg-blue-50"><CardContent className="pt-4 space-y-4"><p className="text-sm font-medium text-blue-900">Configuration guidée</p><p className="text-xs text-blue-800">Répondez simplement aux questions suivantes. L’application prépare automatiquement la configuration technique.</p><div className="grid grid-cols-1 md:grid-cols-2 gap-4"><div><Label htmlFor="workflow-delay">Délai</Label><div className="flex gap-2"><Input id="workflow-delay" type="number" min="1" value={form.simple_delay} onChange={(event) => updateField('simple_delay', event.target.value)} /><select value={form.simple_delay_unit} onChange={(event) => updateField('simple_delay_unit', event.target.value as WorkflowFormValue['simple_delay_unit'])} className="h-9 px-3 border rounded-md text-sm"><option value="heures">heures</option><option value="jours">jours</option></select></div></div><div><Label htmlFor="workflow-approval">Validation</Label><select id="workflow-approval" value={form.require_approval ? 'required' : 'automatic'} onChange={(event) => setForm((current) => ({ ...current, require_approval: event.target.value === 'required' }))} className="w-full h-9 px-3 border rounded-md text-sm"><option value="required">Validation humaine obligatoire</option><option value="automatic">Exécution automatique</option></select></div></div><div><Label htmlFor="workflow-message">Message ou consigne</Label><Textarea id="workflow-message" value={form.simple_message} onChange={(event) => updateField('simple_message', event.target.value)} rows={3} placeholder="Écrivez le message ou la consigne" /></div></CardContent></Card>}
        {form.advanced_mode && <div><Label htmlFor="workflow-trigger-config">Configuration avancée du déclencheur (JSON)</Label><Textarea id="workflow-trigger-config" value={form.trigger_config_text} onChange={(event) => updateField('trigger_config_text', event.target.value)} rows={3} placeholder={'Exemple : {"type":"appointment_completed","delay_hours":24}'} className="font-mono text-xs" /></div>}
        {form.advanced_mode && <div><Label htmlFor="workflow-conditions">Conditions avancées (JSON)</Label><Textarea id="workflow-conditions" value={form.conditions_text} onChange={(event) => updateField('conditions_text', event.target.value)} rows={3} placeholder={'Exemple : {"opted_out":false}'} className="font-mono text-xs" /></div>}
        <div className="space-y-3"><div className="flex items-center justify-between"><Label>Actions *</Label><Button type="button" variant="outline" size="sm" onClick={addAction}><Plus className="w-4 h-4 mr-1" /> Ajouter une action</Button></div>
          {form.actions.map((action, index) => <div key={`${index}-${action.type}`} className="border rounded-md p-3 space-y-3">
            <div className="flex items-center gap-2"><select value={action.type} onChange={(event) => updateAction(index, 'type', event.target.value)} className="flex-1 h-9 px-3 border rounded-md text-sm">{ACTION_TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select><Button type="button" variant="ghost" size="sm" onClick={() => removeAction(index)} disabled={form.actions.length === 1} className="text-red-600"><Trash2 className="w-4 h-4" /></Button></div>
            {form.advanced_mode ? <Textarea value={action.config_text} onChange={(event) => updateAction(index, 'config_text', event.target.value)} rows={4} className="font-mono text-xs" placeholder={'Exemple : {"template":"Votre message"}'} /> : <p className="text-xs text-muted-foreground">Cette action sera configurée automatiquement à partir des choix guidés.</p>}
          </div>)}
        </div>
        <div className="flex items-center justify-between gap-3"><Button type="button" variant="ghost" size="sm" onClick={() => setForm((current) => ({ ...current, advanced_mode: !current.advanced_mode }))}>{form.advanced_mode ? 'Revenir au mode simple' : 'Options avancées'}</Button><DialogFooter><Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button><Button type="submit" disabled={isSaving}>{isSaving ? <Spinner className="w-4 h-4" /> : mode === 'edit' ? 'Enregistrer' : 'Créer le brouillon'}</Button></DialogFooter></div>
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
