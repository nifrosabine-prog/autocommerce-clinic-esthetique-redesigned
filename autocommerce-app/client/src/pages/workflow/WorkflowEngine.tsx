import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
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
  simple_delay_unit: 'hours' | 'days';
  simple_message: string;
  require_approval: boolean;
  advanced_mode: boolean;
}

interface ActionDraft {
  type: string;
  config_text: string;
}

const TRIGGER_TYPES = [
  { value: 'manual' },
  { value: 'event_based' },
  { value: 'condition_based' },
  { value: 'scheduled' },
];
const triggerLabel = (t: (k: string) => string, value: string) => t(`workflow.trigger_${value}`);

const ACTION_TYPES = [
  { value: 'send_whatsapp' },
  { value: 'send_sms' },
  { value: 'send_email' },
  { value: 'create_task' },
  { value: 'create_appointment' },
  { value: 'add_fidelite_points' },
  { value: 'launch_campaign' },
];
const actionLabel = (t: (k: string) => string, value: string) => t(`workflow.action_${value}`);

const DEFAULT_ACTION: ActionDraft = {
  type: 'send_whatsapp',
  config_text: '{\n  "template": "Message de suivi"\n}',
};

const EMPTY_MESSAGE = 'workflow.defaultMessage';
const EMPTY_FORM: WorkflowFormValue = {
  nom: '',
  description: '',
  trigger_type: 'manual',
  trigger_config_text: '',
  conditions_text: '',
  actions: [{ ...DEFAULT_ACTION }],
  simple_delay: '24',
  simple_delay_unit: 'hours',
  simple_message: EMPTY_MESSAGE,
  require_approval: true,
  advanced_mode: false,
};

const STATUS_KEYS = ['draft', 'active', 'paused', 'archived', 'pending', 'running', 'completed', 'failed', 'awaiting_approval'];
const statusLabel = (t: (k: string) => string, status: string) =>
  STATUS_KEYS.includes(status) ? t(`workflow.status_${status}`) : status;

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
  simple_delay_unit: 'hours',
  simple_message: String((workflow.actions?.[0]?.config?.template as string) || EMPTY_MESSAGE),
  require_approval: true,
  advanced_mode: false,
});

const parseJsonObject = (value: string, fieldLabel: string, t?: (k: string) => string): JsonObject | undefined => {
  if (!value.trim()) return undefined;
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch {
    throw new Error(t ? `${fieldLabel} ${t('workflow.errors.invalidJson')}` : `${fieldLabel} must contain valid JSON`);
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(t ? `${fieldLabel} ${t('workflow.errors.notObject')}` : `${fieldLabel} must be a JSON object`);
  }
  return parsed as JsonObject;
};

export default function WorkflowEngine() {
  const { t, i18n } = useTranslation();
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
      const message = getErrorMessage(err, t('workflow.errors.load'));
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
      toast.error(getErrorMessage(err, t('workflow.errors.loadOne')));
    }
  };

  const handleDeleteWorkflow = async (workflow: Workflow) => {
    if (!window.confirm(t('workflow.confirmDelete', { name: workflow.nom }))) return;
    try {
      await api.delete(`/workflows/${workflow.id}`);
      toast.success(t('workflow.deleted'));
      await loadData();
    } catch (err: any) {
      toast.error(getErrorMessage(err, t('workflow.errors.delete')));
    }
  };

  const handleToggleWorkflow = async (workflow: Workflow) => {
    try {
      await api.put(`/workflows/${workflow.id}`, {
        enabled: !workflow.enabled,
      });
      toast.success(workflow.enabled ? t('workflow.paused') : t('workflow.activated'));
      await loadData();
    } catch (err: any) {
      toast.error(getErrorMessage(err, t('workflow.errors.statusChange')));
    }
  };

  const handleExecuteWorkflow = async (workflow: Workflow, patientId?: number) => {
    try {
      const response = patientId
        ? await api.post(`/workflows/${workflow.id}/execute`, undefined, { params: { patient_id: patientId } })
        : await api.post(`/workflows/${workflow.id}/execute`);
      const executionStatus = response.data?.data?.status;
      if (executionStatus === 'awaiting_approval') {
        toast.success(t('workflow.executedApproval'));
      } else if (executionStatus === 'failed') {
        toast.error(t('workflow.executedFailed'));
      } else {
        toast.success(t('workflow.executed'));
      }
      setExecutionTarget(null);
      await loadData();
      setHistoryTarget(workflow);
    } catch (err: any) {
      toast.error(getErrorMessage(err, t('workflow.errors.execute')));
    }
  };

  const handleSaveWorkflow = async (value: WorkflowFormValue) => {
    try {
      const actions = value.actions.map((action) => ({
        type: action.type,
        config: parseJsonObject(action.config_text, t('workflow.actionConfig'), t) || {},
      }));
      const payload = {
        nom: value.nom.trim(),
        description: value.description.trim() || undefined,
        trigger_type: value.trigger_type,
        trigger_config: parseJsonObject(value.trigger_config_text, t('workflow.triggerConfig'), t),
        conditions: parseJsonObject(value.conditions_text, t('workflow.conditions'), t),
        actions,
      };
      if (!payload.nom) throw new Error(t('workflow.errors.nameRequired'));

      if (editorMode === 'edit') {
        if (!editingWorkflowId) throw new Error(t('workflow.errors.notFound'));
        await api.put(`/workflows/${editingWorkflowId}`, payload);
        toast.success(t('workflow.updated'));
      } else {
        await api.post('/workflows/', payload);
        toast.success(t('workflow.createdDraft'));
      }
      setEditorOpen(false);
      await loadData();
    } catch (err: any) {
      toast.error(getErrorMessage(err, t('workflow.errors.save')));
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
            <h1 className="text-3xl font-bold text-gray-900">{t('workflow.title')}</h1>
            <p className="text-gray-600 mt-2">{t('workflow.subtitle')}</p>
          </div>
          <Button onClick={() => openCreate()} className="gap-2">
            <Plus className="w-5 h-5" /> {t('workflow.new')}
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
            <StatCard title={t('workflow.statTotal')} value={stats.total_executions} detail={t('workflow.statTotalDetail')} />
            <StatCard title={t('workflow.statCompleted')} value={stats.completed} detail={t('workflow.statCompletedDetail')} tone="green" />
            <StatCard title={t('workflow.statFailed')} value={stats.failed} detail={t('workflow.statFailedDetail')} tone="red" />
            <StatCard title={t('workflow.statPending')} value={stats.drafts_awaiting_approval} detail={t('workflow.statPendingDetail')} tone="yellow" />
            <StatCard title={t('workflow.statRate')} value={`${(stats.success_rate || 0).toFixed(1)}%`} detail={t('workflow.statRateDetail')} />
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {workflows.length === 0 ? (
            <Card className="lg:col-span-2"><CardContent className="pt-12 pb-12 text-center text-gray-500">{t('workflow.empty')}</CardContent></Card>
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
                    {statusLabel(t, workflow.status)}
                  </span>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div><p className="text-xs text-gray-600">{t('workflow.trigger')}</p><p className="text-sm font-medium">{triggerLabel(t, workflow.trigger_type)}</p></div>
                  <div><p className="text-xs text-gray-600">{t('workflow.createdAt')}</p><p className="text-sm font-medium">{new Date(workflow.created_at).toLocaleDateString(i18n.language)}</p></div>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mt-4 pt-4 border-t">
                  <Button size="sm" variant="outline" onClick={() => void handleExecuteWorkflow(workflow)} className="gap-1"><Play className="w-3.5 h-3.5" /> {t('workflow.run')}</Button>
                  <Button size="sm" variant="outline" onClick={() => openEdit(workflow)} className="gap-1"><Edit2 className="w-3.5 h-3.5" /> {t('workflow.edit')}</Button>
                  <Button size="sm" variant="outline" onClick={() => handleToggleWorkflow(workflow)} className="gap-1"><Pause className="w-3.5 h-3.5" /> {workflow.enabled ? t('workflow.pause') : t('workflow.activate')}</Button>
                  <Button size="sm" variant="outline" onClick={() => setHistoryTarget(workflow)} className="gap-1"><History className="w-3.5 h-3.5" /> {t('workflow.history')}</Button>
                  <Button size="sm" variant="outline" onClick={() => handleDeleteWorkflow(workflow)} className="gap-1 text-red-600 hover:text-red-700"><Trash2 className="w-3.5 h-3.5" /> {t('workflow.delete')}</Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><BarChart3 className="w-5 h-5" /> {t('workflow.templates')}</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {templates.map((template) => (
                <button key={template.id} type="button" onClick={() => openCreate(template)} className="p-4 rounded-lg border bg-gray-50 text-left hover:bg-blue-50 hover:border-blue-300 transition">
                  <p className="font-medium text-sm">{template.nom}</p>
                  <p className="text-xs text-gray-600 mt-1">{template.description}</p>
                  <p className="text-xs text-blue-700 mt-3">{t('workflow.useTemplate')}</p>
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
  const { t } = useTranslation();
  const [form, setForm] = useState<WorkflowFormValue>(initialValue);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => { if (open) setForm(initialValue); }, [open, initialValue]);

  const updateField = (field: keyof WorkflowFormValue, value: string) => setForm((current) => ({ ...current, [field]: value }));
  const updateAction = (index: number, field: keyof ActionDraft, value: string) => setForm((current) => ({ ...current, actions: current.actions.map((action, actionIndex) => actionIndex === index ? { ...action, [field]: value } : action) }));
  const addAction = () => setForm((current) => ({ ...current, actions: [...current.actions, { ...DEFAULT_ACTION }] }));
  const removeAction = (index: number) => setForm((current) => ({ ...current, actions: current.actions.filter((_, actionIndex) => actionIndex !== index) }));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (form.actions.length === 0) { toast.error(t('workflow.errors.minAction')); return; }
    const delay = Math.max(1, Number(form.simple_delay) || 24);
    const firstAction = form.actions[0];
    const guidedTrigger = form.trigger_type === 'event_based'
      ? { type: 'appointment_completed', delay_hours: form.simple_delay_unit === 'days' ? delay * 24 : delay }
      : form.trigger_type === 'condition_based'
        ? { inactive_days: form.simple_delay_unit === 'days' ? delay : delay / 24 }
        : form.trigger_type === 'scheduled'
          ? { reminder_delay: `${delay} ${form.simple_delay_unit}` }
          : {};
    const messageText = (form.simple_message === EMPTY_MESSAGE ? t(EMPTY_MESSAGE) : form.simple_message).trim();
    const guidedActionConfig = firstAction.type.startsWith('send_')
      ? { template: messageText, personalization: true, require_approval: form.require_approval }
      : firstAction.type === 'create_task'
        ? { title: messageText || form.nom.trim(), priority: 'medium', require_approval: form.require_approval }
        : { require_approval: form.require_approval };
    const guidedForm = form.advanced_mode ? form : {
      ...form,
      trigger_config_text: JSON.stringify(guidedTrigger),
      conditions_text: JSON.stringify({ opted_out: false }),
      actions: [{ ...firstAction, config_text: JSON.stringify(guidedActionConfig) }, ...form.actions.slice(1)],
    };
    setIsSaving(true);
    try { await onSave(guidedForm); } catch { /* Parent component displays the error. */ } finally { setIsSaving(false); }
  };

  return <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
      <DialogHeader><DialogTitle>{mode === 'edit' ? t('workflow.editTitle') : t('workflow.newTitle')}</DialogTitle><DialogDescription>{t('workflow.editorDesc')}</DialogDescription></DialogHeader>
      <form onSubmit={submit} className="space-y-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div><Label htmlFor="workflow-nom">{t('workflow.name')} *</Label><Input id="workflow-nom" value={form.nom} onChange={(event) => updateField('nom', event.target.value)} required maxLength={200} /></div>
          <div><Label htmlFor="workflow-trigger">{t('workflow.trigger')} *</Label><select id="workflow-trigger" value={form.trigger_type} onChange={(event) => updateField('trigger_type', event.target.value)} className="w-full h-9 px-3 border rounded-md text-sm">{TRIGGER_TYPES.map((item) => <option key={item.value} value={item.value}>{triggerLabel(t, item.value)}</option>)}</select></div>
        </div>
        <div><Label htmlFor="workflow-description">{t('workflow.description')}</Label><Textarea id="workflow-description" value={form.description} onChange={(event) => updateField('description', event.target.value)} rows={2} maxLength={5000} /></div>
        {!form.advanced_mode && <Card className="border-blue-100 bg-blue-50"><CardContent className="pt-4 space-y-4"><p className="text-sm font-medium text-blue-900">{t('workflow.guidedTitle')}</p><p className="text-xs text-blue-800">{t('workflow.guidedDesc')}</p><div className="grid grid-cols-1 md:grid-cols-2 gap-4"><div><Label htmlFor="workflow-delay">{t('workflow.delay')}</Label><div className="flex gap-2"><Input id="workflow-delay" type="number" min="1" value={form.simple_delay} onChange={(event) => updateField('simple_delay', event.target.value)} /><select value={form.simple_delay_unit} onChange={(event) => updateField('simple_delay_unit', event.target.value as WorkflowFormValue['simple_delay_unit'])} className="h-9 px-3 border rounded-md text-sm"><option value="hours">{t('workflow.hours')}</option><option value="days">{t('workflow.days')}</option></select></div></div><div><Label htmlFor="workflow-approval">{t('workflow.approval')}</Label><select id="workflow-approval" value={form.require_approval ? 'required' : 'automatic'} onChange={(event) => setForm((current) => ({ ...current, require_approval: event.target.value === 'required' }))} className="w-full h-9 px-3 border rounded-md text-sm"><option value="required">{t('workflow.approvalRequired')}</option><option value="automatic">{t('workflow.approvalAuto')}</option></select></div></div><div><Label htmlFor="workflow-message">{t('workflow.messageLabel')}</Label><Textarea id="workflow-message" value={form.simple_message} onChange={(event) => updateField('simple_message', event.target.value)} rows={3} placeholder={t('workflow.messagePh')} /></div></CardContent></Card>}
        {form.advanced_mode && <div><Label htmlFor="workflow-trigger-config">{t('workflow.advTrigger')}</Label><Textarea id="workflow-trigger-config" value={form.trigger_config_text} onChange={(event) => updateField('trigger_config_text', event.target.value)} rows={3} placeholder={t('workflow.exampleTrigger')} className="font-mono text-xs" /></div>}
        {form.advanced_mode && <div><Label htmlFor="workflow-conditions">{t('workflow.advConditions')}</Label><Textarea id="workflow-conditions" value={form.conditions_text} onChange={(event) => updateField('conditions_text', event.target.value)} rows={3} placeholder={t('workflow.exampleConditions')} className="font-mono text-xs" /></div>}
        <div className="space-y-3"><div className="flex items-center justify-between"><Label>{t('workflow.actions')} *</Label><Button type="button" variant="outline" size="sm" onClick={addAction}><Plus className="w-4 h-4 mr-1" /> {t('workflow.addAction')}</Button></div>
          {form.actions.map((action, index) => <div key={`${index}-${action.type}`} className="border rounded-md p-3 space-y-3">
            <div className="flex items-center gap-2"><select value={action.type} onChange={(event) => updateAction(index, 'type', event.target.value)} className="flex-1 h-9 px-3 border rounded-md text-sm">{ACTION_TYPES.map((item) => <option key={item.value} value={item.value}>{actionLabel(t, item.value)}</option>)}</select><Button type="button" variant="ghost" size="sm" onClick={() => removeAction(index)} disabled={form.actions.length === 1} className="text-red-600"><Trash2 className="w-4 h-4" /></Button></div>
            {form.advanced_mode ? <Textarea value={action.config_text} onChange={(event) => updateAction(index, 'config_text', event.target.value)} rows={4} className="font-mono text-xs" placeholder={t('workflow.exampleMessage')} /> : <p className="text-xs text-muted-foreground">{t('workflow.autoConfig')}</p>}
          </div>)}
        </div>
        <div className="flex items-center justify-between gap-3"><Button type="button" variant="ghost" size="sm" onClick={() => setForm((current) => ({ ...current, advanced_mode: !current.advanced_mode }))}>{form.advanced_mode ? t('workflow.backSimple') : t('workflow.advancedOptions')}</Button><DialogFooter><Button type="button" variant="outline" onClick={() => onOpenChange(false)}>{t('common.cancel')}</Button><Button type="submit" disabled={isSaving}>{isSaving ? <Spinner className="w-4 h-4" /> : mode === 'edit' ? t('messages.save') : t('workflow.createDraft')}</Button></DialogFooter></div>
      </form>
    </DialogContent>
  </Dialog>;
}

function ExecuteWorkflowDialog({ workflow, onOpenChange, onExecute }: { workflow: Workflow | null; onOpenChange: (open: boolean) => void; onExecute: (workflow: Workflow, patientId?: number) => Promise<void>; }) {
  const { t } = useTranslation();
  const [patientId, setPatientId] = useState('');
  useEffect(() => { if (workflow) setPatientId(''); }, [workflow]);
  const submit = async (event: React.FormEvent) => { event.preventDefault(); const parsed = patientId.trim() ? Number(patientId) : undefined; if (patientId.trim() && (!Number.isInteger(parsed) || (parsed || 0) <= 0)) { toast.error(t('workflow.errors.patientId')); return; } if (workflow) await onExecute(workflow, parsed); };
  return <Dialog open={!!workflow} onOpenChange={onOpenChange}><DialogContent><DialogHeader><DialogTitle>{t('workflow.executeTitle', { name: workflow?.nom || '' })}</DialogTitle><DialogDescription>{t('workflow.executeDesc')}</DialogDescription></DialogHeader><form onSubmit={submit} className="space-y-4"><div><Label htmlFor="workflow-patient-id">{t('workflow.patientIdOptional')}</Label><Input id="workflow-patient-id" type="number" min="1" value={patientId} onChange={(event) => setPatientId(event.target.value)} placeholder={t('workflow.ex42')} /></div><DialogFooter><Button type="button" variant="outline" onClick={() => onOpenChange(false)}>{t('common.cancel')}</Button><Button type="submit"><Play className="w-4 h-4 mr-2" /> {t('workflow.run')}</Button></DialogFooter></form></DialogContent></Dialog>;
}

function WorkflowHistoryDialog({ workflow, onOpenChange }: { workflow: Workflow | null; onOpenChange: (open: boolean) => void; }) {
  const { t, i18n } = useTranslation();
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
      .catch((error) => { if (!cancelled) toast.error(getErrorMessage(error, t('workflow.errors.loadHistory'))); })
      .finally(() => { if (!cancelled) setIsLoading(false); });
    return () => { cancelled = true; };
  }, [workflow]);

  useEffect(() => {
    if (!selectedExecutionId) { setActions([]); return; }
    let cancelled = false;
    setIsLoadingActions(true);
    api.get(`/workflows/executions/${selectedExecutionId}/actions`)
      .then((response) => { if (!cancelled) setActions(Array.isArray(response.data?.data) ? response.data.data : []); })
      .catch((error) => { if (!cancelled) toast.error(getErrorMessage(error, t('workflow.errors.loadActions'))); })
      .finally(() => { if (!cancelled) setIsLoadingActions(false); });
    return () => { cancelled = true; };
  }, [selectedExecutionId]);

  const approve = async (action: WorkflowActionLog, executionId: number) => {
    if (!workflow) return;
    try {
      await api.post(`/workflows/executions/${executionId}/approve-action`, { action_id: action.id, workflow_id: workflow.id });
      toast.success(t('workflow.actionApproved'));
      const response = await api.get(`/workflows/executions/${executionId}/actions`);
      setActions(Array.isArray(response.data?.data) ? response.data.data : []);
    } catch (error: any) { toast.error(getErrorMessage(error, t('workflow.errors.approve'))); }
  };

  return <Dialog open={!!workflow} onOpenChange={onOpenChange}><DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto"><DialogHeader><DialogTitle>{t('workflow.historyTitle', { name: workflow?.nom || '' })}</DialogTitle><DialogDescription>{t('workflow.historyDesc')}</DialogDescription></DialogHeader>{isLoading ? <div className="flex justify-center py-8"><Spinner /></div> : executions.length === 0 ? <p className="text-sm text-muted-foreground py-6">{t('workflow.noExecutions')}</p> : <div className="grid grid-cols-1 md:grid-cols-2 gap-4"><div className="space-y-2">{executions.map((execution) => <button type="button" key={execution.id} onClick={() => setSelectedExecutionId(execution.id)} className={`w-full text-left border rounded-md p-3 ${selectedExecutionId === execution.id ? 'border-blue-500 bg-blue-50' : 'hover:bg-gray-50'}`}><div className="flex items-center justify-between gap-2"><span className="font-medium">#{execution.id}</span><ExecutionStatus status={execution.status} /></div><p className="text-xs text-gray-600 mt-1">{execution.trigger_reason}</p><p className="text-xs text-gray-500 mt-1">{new Date(execution.created_at).toLocaleString(i18n.language)}</p></button>)}</div><div className="border rounded-md p-4">{isLoadingActions ? <div className="flex justify-center py-8"><Spinner /></div> : actions.length === 0 ? <p className="text-sm text-muted-foreground">{t('workflow.noActions')}</p> : <div className="space-y-3">{actions.map((action) => <div key={action.id} className="border-b last:border-b-0 pb-3 last:pb-0"><div className="flex items-center justify-between gap-2"><span className="text-sm font-medium">{action.action_type}</span><ExecutionStatus status={action.status} /></div>{action.error_message && <p className="text-xs text-red-600 mt-1">{action.error_message}</p>}{action.status === 'awaiting_approval' && <Button size="sm" className="mt-2" onClick={() => selectedExecutionId && approve(action, selectedExecutionId)}><CheckCircle className="w-4 h-4 mr-1" /> {t('workflow.approve')}</Button>}</div>)}</div>}</div></div>}<DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)}>{t('messages.cancel')}</Button></DialogFooter></DialogContent></Dialog>;
}

function ExecutionStatus({ status }: { status: string }) {
  const { t } = useTranslation();
  const label = statusLabel(t, status);
  if (status === 'completed') return <span className="inline-flex items-center gap-1 text-xs text-green-700"><CheckCircle className="w-3.5 h-3.5" />{label}</span>;
  if (status === 'failed') return <span className="inline-flex items-center gap-1 text-xs text-red-700"><XCircle className="w-3.5 h-3.5" />{label}</span>;
  if (status === 'awaiting_approval') return <span className="inline-flex items-center gap-1 text-xs text-yellow-700"><Clock className="w-3.5 h-3.5" />{label}</span>;
  return <span className="inline-flex items-center gap-1 text-xs text-gray-600"><Clock className="w-3.5 h-3.5" />{label}</span>;
}
