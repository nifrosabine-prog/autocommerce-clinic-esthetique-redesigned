import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'wouter';
import { Search, UserCheck, FileText, RefreshCw, CalendarOff, ListTodo } from 'lucide-react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Spinner } from '@/components/ui/spinner';
import { toast } from 'sonner';
import { accueilApi, api, type AccueilAppointment } from '@/lib/api';

function PatientReplanification({ appointments, onDone }: { appointments: AccueilAppointment[]; onDone: () => void }) {
  const { t, i18n } = useTranslation();
  const absent = appointments.filter((item) => item.statut === 'no_show');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [options, setOptions] = useState<{ datetime: string; score: number }[]>([]);
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(false);
  const propose = async (appointment: AccueilAppointment) => {
    const base = new Date(appointment.date_heure_debut);
    const dates = [1, 2, 3].map((offset) => { const date = new Date(base); date.setDate(date.getDate() + offset); return date.toISOString().slice(0, 10); });
    setLoading(true);
    try { const response = await accueilApi.proposeReplanification(appointment.id, dates); setSelectedId(appointment.id); setOptions(response.data.options || []); setDraft(response.data.whatsapp_draft || ''); toast.success(t('accueil.proposeSuccess')); }
    catch (error: any) { toast.error(error.response?.data?.detail || t('accueil.proposeError')); }
    finally { setLoading(false); }
  };
  const confirm = async (date_heure: string) => {
    if (!selectedId) return;
    setLoading(true);
    try { await accueilApi.confirmReplanification(selectedId, date_heure); toast.success(t('accueil.confirmSuccess')); setOptions([]); setDraft(''); setSelectedId(null); onDone(); }
    catch (error: any) { toast.error(error.response?.data?.detail || t('accueil.confirmError')); }
    finally { setLoading(false); }
  };
  if (!absent.length) return null;
  return <Card><CardHeader><CardTitle>{t('accueil.replanTitle')}</CardTitle></CardHeader><CardContent className="space-y-3">
    {absent.map(item => <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded border p-3 text-sm"><span><strong>{t('accueil.appointmentNumber', { id: item.id })}</strong> · {item.patient_nom} · {new Date(item.date_heure_debut).toLocaleString(i18n.language)}</span><Button size="sm" onClick={() => void propose(item)} disabled={loading}>{t('accueil.proposeWhatsapp')}</Button></div>)}
    {draft && <div className="rounded border bg-muted/30 p-3 text-sm"><p className="mb-2 font-medium">{t('accueil.draftTitle')}</p><p>{draft}</p></div>}
    {options.length > 0 && <div className="space-y-2"><p className="text-sm font-medium">{t('accueil.chooseConfirmed')}</p>{options.map(option => <Button key={option.datetime} variant="outline" className="mr-2" onClick={() => void confirm(option.datetime)} disabled={loading}>{new Date(option.datetime).toLocaleString(i18n.language)}</Button>)}</div>}
  </CardContent></Card>;
}

export default function AccueilPatients() {
  const { t, i18n } = useTranslation();
  const [, setLocation] = useLocation();
  const [query, setQuery] = useState('');
  const [appointments, setAppointments] = useState<AccueilAppointment[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await accueilApi.list({ q: query || undefined });
      setAppointments(response.data || []);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || t('accueil.loadError'));
    } finally {
      setLoading(false);
    }
  }, [query, t]);

  useEffect(() => { void load(); }, [load]);

  const markArrived = async (appointment: AccueilAppointment) => {
    try {
      const response = await accueilApi.markArrived(appointment.id);
      toast.success(t('accueil.arrivalRegistered'));
      setLocation(`/medical-record/${response.data.patient_id}?rdvId=${appointment.id}&episodeId=${response.data.episode_id || ''}`);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || t('accueil.arrivalError'));
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
          <div>
            <h1 className="text-3xl font-bold">{t('accueil.title')}</h1>
            <p className="text-muted-foreground">{t('accueil.subtitle')}</p>
          </div>
          <Button variant="outline" onClick={() => void load()}><RefreshCw className="mr-2 h-4 w-4" /> {t('accueil.refresh')}</Button>
        </div>
        <AbsenceManager />
        <PatientReplanification appointments={appointments} onDone={() => void load()} />
        <TachesInternes />
        <Card>
          <CardContent className="pt-6">
            <div className="flex gap-2">
              <Search className="mt-2 h-4 w-4 text-muted-foreground" />
              <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t('accueil.searchPlaceholder')} />
            </div>
          </CardContent>
        </Card>
        {loading ? <div className="flex justify-center py-12"><Spinner /></div> : appointments.length === 0 ? (
          <Card><CardContent className="py-10 text-center text-muted-foreground">{t('accueil.noAppointments')}</CardContent></Card>
        ) : (
          <div className="space-y-3">
            {appointments.map((appointment) => (
              <Card key={appointment.id}>
                <CardContent className="flex flex-col gap-4 p-5 md:flex-row md:items-center md:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2"><span className="font-semibold">{appointment.patient_nom}</span><Badge variant="outline">{t(`accueil.status_${appointment.statut}`, { defaultValue: appointment.statut })}</Badge></div>
                    <p className="text-sm text-muted-foreground">{new Date(appointment.date_heure_debut).toLocaleString(i18n.language)} · {appointment.acte_nom || t('accueil.actNotSpecified')}</p>
                    <p className="text-xs text-muted-foreground">{appointment.reference || t('accueil.appointmentNumber', { id: appointment.id })} · {appointment.telephone || t('accueil.phoneNotProvided')} · {appointment.source}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {(appointment.statut === 'planifie' || appointment.statut === 'confirme') && <Button onClick={() => void markArrived(appointment)}><UserCheck className="mr-2 h-4 w-4" /> {t('accueil.patientArrived')}</Button>}
                    {(appointment.statut === 'arrive' || appointment.statut === 'accord') && <Button variant="secondary" onClick={() => setLocation(`/medical-record/${appointment.patient_id}?rdvId=${appointment.id}`)}><FileText className="mr-2 h-4 w-4" /> {t('accueil.openFile')}</Button>}
                    <Link href={`/patients/${appointment.patient_id}`}><Button variant="outline">{t('accueil.patientCard')}</Button></Link>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

function AbsenceManager() {
  const { t, i18n } = useTranslation();
  const [users, setUsers] = useState<{ id: number; nom: string; prenom: string; role: string }[]>([]);
  const [praticienId, setPraticienId] = useState(''); const [debut, setDebut] = useState(''); const [fin, setFin] = useState(''); const [motif, setMotif] = useState('');
  const [suggestions, setSuggestions] = useState<any[]>([]); const [saving, setSaving] = useState(false);
  const [reassignments, setReassignments] = useState<{ absenceId: number; propositionId: number; rdvId: number; praticienProposeId: number | null }[]>([]);
  const practitionerName = (id: number | null) => { const u = users.find(x => x.id === id); return u ? `${u.prenom} ${u.nom}` : t('accueil.practitionerToDefine'); };
  const loadReassignments = useCallback(() => {
    api.get('/agenda/absences-praticiens').then(r => {
      const flattened = (r.data || []).flatMap((absence: any) =>
        (absence.propositions || [])
          .filter((p: any) => p.statut === 'a_valider')
          .map((p: any) => ({ absenceId: absence.id, propositionId: p.id, rdvId: p.rdv_id, praticienProposeId: p.praticien_propose_id }))
      );
      setReassignments(flattened);
    }).catch(() => undefined);
  }, []);
  useEffect(() => { api.get('/users').then(r => setUsers((r.data || []).filter((u: any) => ['medecin', 'estheticienne', 'prestataire'].includes(u.role)))).catch(() => undefined); api.get('/agenda/suggestions-remplacement').then(r => setSuggestions(r.data || [])).catch(() => undefined); loadReassignments(); }, [loadReassignments]);
  const declare = async () => { if (!praticienId || !debut || !fin) return toast.error(t('accueil.requiredFields')); setSaving(true); try { const r = await api.post('/agenda/absences-praticiens', { praticien_id: Number(praticienId), debut: new Date(debut).toISOString(), fin: new Date(fin).toISOString(), motif: motif || undefined }); toast.success(t('accueil.declared', { count: r.data.rdvs_concernes || 0 })); setPraticienId(''); setDebut(''); setFin(''); setMotif(''); loadReassignments(); } catch (e: any) { toast.error(e.response?.data?.detail || t('accueil.declareError')); } finally { setSaving(false); } };
  const validate = async (id: number) => { try { await api.post(`/agenda/suggestions-remplacement/${id}/valider`); setSuggestions(suggestions.filter(s => s.id !== id)); toast.success(t('accueil.validated')); } catch (e: any) { toast.error(e.response?.data?.detail || t('accueil.slotUnavailable')); } };
  const validateReassignment = async (absenceId: number, propositionId: number) => { try { await api.post(`/agenda/absences-praticiens/${absenceId}/reaffectations/${propositionId}/valider`); setReassignments(current => current.filter(r => r.propositionId !== propositionId)); toast.success(t('accueil.reassigned')); } catch (e: any) { toast.error(e.response?.data?.detail || t('accueil.reassignError')); } };
  return <div className="grid gap-4 lg:grid-cols-2"><Card><CardHeader><CardTitle className="flex items-center gap-2 text-base"><CalendarOff className="h-4 w-4" /> {t('accueil.absenceTitle')}</CardTitle></CardHeader><CardContent className="space-y-3"><div className="grid gap-3 md:grid-cols-2"><select className="h-10 rounded-md border bg-background px-3 text-sm" value={praticienId} onChange={e => setPraticienId(e.target.value)}><option value="">{t('accueil.choosePractitioner')}</option>{users.map(u => <option key={u.id} value={u.id}>{u.prenom} {u.nom}</option>)}</select><Input placeholder={t('accueil.reasonOptional')} value={motif} onChange={e => setMotif(e.target.value)} /></div><div className="grid gap-3 md:grid-cols-2"><div><label className="text-xs text-muted-foreground">{t('accueil.start')}</label><Input type="datetime-local" value={debut} onChange={e => setDebut(e.target.value)} /></div><div><label className="text-xs text-muted-foreground">{t('accueil.end')}</label><Input type="datetime-local" value={fin} onChange={e => setFin(e.target.value)} /></div></div><Button onClick={() => void declare()} disabled={saving}><CalendarOff className="mr-2 h-4 w-4" /> {t('accueil.declare')}</Button></CardContent></Card><Card><CardHeader><CardTitle className="text-base">{t('accueil.reassignTitle')}</CardTitle></CardHeader><CardContent>{reassignments.length === 0 ? <p className="text-sm text-muted-foreground">{t('accueil.noReassign')}</p> : <div className="space-y-2">{reassignments.map(r => <div key={r.propositionId} className="flex items-center justify-between gap-2 rounded border p-2 text-sm"><span>{t('accueil.reassignLine', { id: r.rdvId, practitioner: practitionerName(r.praticienProposeId) })}</span>{r.praticienProposeId ? <Button size="sm" onClick={() => void validateReassignment(r.absenceId, r.propositionId)}>{t('accueil.validate')}</Button> : <span className="text-xs text-muted-foreground">{t('accueil.noPractitionerAvailable')}</span>}</div>)}</div>}</CardContent></Card><Card><CardHeader><CardTitle className="text-base">{t('accueil.slotsTitle')}</CardTitle></CardHeader><CardContent>{suggestions.length === 0 ? <p className="text-sm text-muted-foreground">{t('accueil.noSuggestion')}</p> : <div className="space-y-2">{suggestions.map(s => <div key={s.id} className="flex items-center justify-between gap-2 rounded border p-2 text-sm"><span>{new Date(s.date_heure_debut).toLocaleString(i18n.language)} · {t('accueil.appointmentNumber', { id: s.rdv_annule_id })}</span><Button size="sm" onClick={() => void validate(s.id)}>{t('accueil.validate')}</Button></div>)}</div>}</CardContent></Card></div>;
}

function TachesInternes() {
  const { t } = useTranslation();
  const [taches, setTaches] = useState<{ id: number; titre: string; description?: string | null; priorite: string; created_at: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const load = useCallback(() => {
    setLoading(true);
    api.get('/taches-internes').then(r => setTaches(r.data || [])).catch(() => undefined).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);
  const traiter = async (id: number) => {
    try {
      await api.post(`/taches-internes/${id}/traiter`);
      setTaches(current => current.filter(t => t.id !== id));
      toast.success(t('accueil.taskDone'));
    } catch (e: any) {
      toast.error(e.response?.data?.detail || t('accueil.taskError'));
    }
  };
  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2 text-base"><ListTodo className="h-4 w-4" /> {t('accueil.tasksTitle')}</CardTitle></CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner className="h-4 w-4" /> {t('accueil.loading')}</div>
        ) : taches.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t('accueil.noTask')}</p>
        ) : (
          <div className="space-y-2">
            {taches.map(task => (
              <div key={task.id} className="flex items-start justify-between gap-3 rounded border p-2 text-sm">
                <div>
                  <p className="font-medium">{task.titre}</p>
                  {task.description && <p className="text-xs text-muted-foreground mt-0.5">{task.description}</p>}
                </div>
                <Button size="sm" variant="outline" onClick={() => void traiter(task.id)}>{t('accueil.markDone')}</Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
