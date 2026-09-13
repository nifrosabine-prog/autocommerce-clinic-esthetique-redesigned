import { useEffect, useState } from 'react';
import { Activity, AlertTriangle, CalendarCheck, CheckCircle2, ClipboardList, Plus, RefreshCw, Stethoscope } from 'lucide-react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { clinicalOpsApi, patientsSearchApi, type CureTraitement, type EvenementIndesirable, type PatientSearchResult, type ProtocoleSoin, type SuiviPostActe } from '@/lib/api';
import { toast } from 'sonner';
import { useAuth } from '@/contexts/AuthContext';

interface ClinicalAuditEntry {
  id: number;
  created_at: string;
  utilisateur: string;
  role: string;
  patient_id: number;
  patient: string;
  action: string;
  resource_type: string;
  resource_id: number;
}

interface ClinicalDashboard {
  suivis: { aujourd_hui: number; cette_semaine: number; items: Array<{ id: number; patient_id: number; type_suivi: string; echeance_at: string; statut: string; notes?: string | null }> };
  evenements_indesirables: { ouverts: number; critiques: number; items: Array<{ id: number; patient_id: number; gravite: string; statut: string; survenu_at: string; description: string }> };
  cures_actives: number;
}

const formatDate = (value?: string | null) => value ? new Date(value).toLocaleDateString('fr-FR') : '—';
const formatDateTime = (value?: string | null) => value ? new Date(value).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' }) : '—';

export default function ClinicalOperationsPage() {
  const { user } = useAuth();
  const canViewAudit = ['directrice', 'admin'].includes(user?.role || '');
  const [dashboard, setDashboard] = useState<ClinicalDashboard | null>(null);
  const [auditEntries, setAuditEntries] = useState<ClinicalAuditEntry[]>([]);
  const [cures, setCures] = useState<CureTraitement[]>([]);
  const [followups, setFollowups] = useState<SuiviPostActe[]>([]);
  const [events, setEvents] = useState<EvenementIndesirable[]>([]);
  const [protocols, setProtocols] = useState<ProtocoleSoin[]>([]);
  const [loading, setLoading] = useState(true);
  const [patientId, setPatientId] = useState('');
  const [patientSearch, setPatientSearch] = useState('');
  const [eventPatientSearch, setEventPatientSearch] = useState('');
  const [patientOptions, setPatientOptions] = useState<PatientSearchResult[]>([]);
  const [eventPatientOptions, setEventPatientOptions] = useState<PatientSearchResult[]>([]);
  const [cureForm, setCureForm] = useState({ nom: '', seances_prevues: '6', zone_anatomique: '', premiere_seance_at: '', notes: '' });
  const [eventForm, setEventForm] = useState({ patient_id: '', description: '', gravite: 'faible', zone_anatomique: '', action_effectuee: '', survenu_at: new Date().toISOString().slice(0, 16) });
  const [protocolForm, setProtocolForm] = useState({ nom: '', categorie: 'esthetique', version: '1.0', avant: '', pendant: '', apres: '' });

  const load = async () => {
    try {
      setLoading(true);
      const [dashboardRes, curesRes, followupsRes, eventsRes, protocolsRes, auditRes] = await Promise.all([
        clinicalOpsApi.dashboard(),
        clinicalOpsApi.listCures(),
        clinicalOpsApi.listFollowups({ horizon_days: 30 }),
        clinicalOpsApi.listAdverseEvents({ statut: 'ouvert' }),
        clinicalOpsApi.listProtocols(),
        canViewAudit ? clinicalOpsApi.listGlobalAudit({ limit: 100 }) : Promise.resolve({ data: [] as ClinicalAuditEntry[] }),
      ]);
      setDashboard(dashboardRes.data);
      setCures(curesRes.data);
      setFollowups(followupsRes.data);
      setEvents(eventsRes.data);
      setProtocols(protocolsRes.data);
      setAuditEntries(auditRes.data);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Impossible de charger le cockpit clinique');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [canViewAudit]);

  useEffect(() => {
    const query = patientSearch.trim();
    if (query.length < 2) {
      setPatientOptions([]);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void patientsSearchApi.list(query).then((response) => {
        if (!cancelled) setPatientOptions(response.data);
      }).catch(() => {
        if (!cancelled) setPatientOptions([]);
      });
    }, 250);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [patientSearch]);

  useEffect(() => {
    const query = eventPatientSearch.trim();
    if (query.length < 2) {
      setEventPatientOptions([]);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void patientsSearchApi.list(query).then((response) => {
        if (!cancelled) setEventPatientOptions(response.data);
      }).catch(() => {
        if (!cancelled) setEventPatientOptions([]);
      });
    }, 250);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [eventPatientSearch]);

  const patientLabel = (patient: PatientSearchResult) => `${patient.prenom} ${patient.nom} · ${patient.telephone || 'téléphone non renseigné'} · #${patient.id}`;

  const createCure = async () => {
    const id = Number(patientId);
    const sessions = Number(cureForm.seances_prevues);
    if (!id || !cureForm.nom.trim() || !sessions) {
      toast.error('Patient, nom de cure et nombre de séances sont obligatoires');
      return;
    }
    try {
      await clinicalOpsApi.createCure({
        patient_id: id,
        nom: cureForm.nom.trim(),
        seances_prevues: sessions,
        zone_anatomique: cureForm.zone_anatomique || undefined,
        premiere_seance_at: cureForm.premiere_seance_at ? new Date(cureForm.premiere_seance_at).toISOString() : undefined,
        notes: cureForm.notes || undefined,
      });
      toast.success('Cure créée avec ses séances prévisionnelles');
      setCureForm({ nom: '', seances_prevues: '6', zone_anatomique: '', premiere_seance_at: '', notes: '' });
      await load();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Création de la cure impossible');
    }
  };

  const markSessionDone = async (cure: CureTraitement, sessionId: number) => {
    try {
      await clinicalOpsApi.updateSession(cure.id, sessionId, { statut: 'realisee', realisee_at: new Date().toISOString() });
      toast.success('Séance marquée comme réalisée');
      await load();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Mise à jour impossible');
    }
  };

  const completeFollowup = async (id: number) => {
    try {
      await clinicalOpsApi.updateFollowup(id, { statut: 'termine' });
      setFollowups((rows) => rows.map((row) => row.id === id ? { ...row, statut: 'termine' } : row));
      toast.success('Suivi clôturé');
      await load();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Mise à jour impossible');
    }
  };

  const confirmFollowupAppointment = async (followup: SuiviPostActe) => {
    const defaultSlot = followup.echeance_at.slice(0, 16);
    const slot = window.prompt('Créneau confirmé avec la patiente (AAAA-MM-JJTHH:MM)', defaultSlot);
    if (!slot) return;
    try {
      await clinicalOpsApi.confirmFollowupAppointment(followup.id, {
        date_heure: new Date(slot).toISOString(),
        patient_confirme: true,
      });
      toast.success('Disponibilité confirmée : rendez-vous créé dans l’agenda');
      await load();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Création du rendez-vous impossible');
    }
  };

  const createEvent = async () => {
    if (!Number(eventForm.patient_id) || eventForm.description.trim().length < 5) {
      toast.error('Patient et description détaillée sont obligatoires');
      return;
    }
    try {
      await clinicalOpsApi.createAdverseEvent({
        patient_id: Number(eventForm.patient_id),
        survenu_at: new Date(eventForm.survenu_at).toISOString(),
        description: eventForm.description.trim(),
        gravite: eventForm.gravite,
        zone_anatomique: eventForm.zone_anatomique || undefined,
        action_effectuee: eventForm.action_effectuee || undefined,
        praticien_informe: eventForm.gravite === 'critique' || eventForm.gravite === 'elevee',
      });
      toast.success('Événement indésirable enregistré et journalisé');
      setEventForm({ patient_id: '', description: '', gravite: 'faible', zone_anatomique: '', action_effectuee: '', survenu_at: new Date().toISOString().slice(0, 16) });
      await load();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Enregistrement impossible');
    }
  };

  const createProtocol = async () => {
    if (!protocolForm.nom.trim()) {
      toast.error('Le nom du protocole est obligatoire');
      return;
    }
    try {
      await clinicalOpsApi.createProtocol({
        nom: protocolForm.nom.trim(), categorie: protocolForm.categorie, version: protocolForm.version,
        etapes_avant: protocolForm.avant.split('\n').map((item) => item.trim()).filter(Boolean),
        etapes_pendant: protocolForm.pendant.split('\n').map((item) => item.trim()).filter(Boolean),
        etapes_apres: protocolForm.apres.split('\n').map((item) => item.trim()).filter(Boolean),
      });
      toast.success('Protocole publié');
      setProtocolForm({ nom: '', categorie: 'esthetique', version: '1.0', avant: '', pendant: '', apres: '' });
      await load();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Création du protocole impossible');
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Pilotage clinique</p>
            <h1 className="mt-1 text-3xl font-bold tracking-tight">Suivi des soins</h1>
            <p className="mt-2 max-w-2xl text-muted-foreground">Un cockpit unique pour savoir qui contacter aujourd’hui, suivre les cures et sécuriser les événements post-acte.</p>
          </div>
          <Button variant="outline" onClick={() => void load()} disabled={loading}><RefreshCw className="mr-2 h-4 w-4" />Actualiser</Button>
        </div>

        <div className="grid gap-4 md:grid-cols-4">
          <Card><CardContent className="flex items-center justify-between p-5"><div><p className="text-sm text-muted-foreground">À contrôler aujourd’hui</p><p className="mt-1 text-3xl font-bold">{dashboard?.suivis.aujourd_hui ?? 0}</p></div><CalendarCheck className="h-8 w-8 text-amber-500" /></CardContent></Card>
          <Card><CardContent className="flex items-center justify-between p-5"><div><p className="text-sm text-muted-foreground">Cette semaine</p><p className="mt-1 text-3xl font-bold">{dashboard?.suivis.cette_semaine ?? 0}</p></div><Activity className="h-8 w-8 text-primary" /></CardContent></Card>
          <Card><CardContent className="flex items-center justify-between p-5"><div><p className="text-sm text-muted-foreground">Cures actives</p><p className="mt-1 text-3xl font-bold">{dashboard?.cures_actives ?? 0}</p></div><Stethoscope className="h-8 w-8 text-emerald-600" /></CardContent></Card>
          <Card><CardContent className="flex items-center justify-between p-5"><div><p className="text-sm text-muted-foreground">Événements ouverts</p><p className="mt-1 text-3xl font-bold">{dashboard?.evenements_indesirables.ouverts ?? 0}</p><p className="text-xs text-red-600">{dashboard?.evenements_indesirables.critiques ?? 0} critique(s)</p></div><AlertTriangle className="h-8 w-8 text-red-500" /></CardContent></Card>
        </div>

        <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><CalendarCheck className="h-5 w-5 text-primary" />Suivi du jour</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {followups.filter((item) => item.statut !== 'termine').slice(0, 8).map((item) => (
                <div key={item.id} className="flex items-center justify-between gap-3 rounded-xl border p-3">
                  <div><p className="font-medium">Patient #{item.patient_id} · {item.type_suivi.replaceAll('_', ' ')}</p><p className="text-sm text-muted-foreground">Échéance : {formatDateTime(item.echeance_at)}</p></div>
                  <div className="flex gap-2">
                    {!item.rdv_id && item.episode_id && item.intervention_id && item.statut !== 'termine' && (
                      <Button size="sm" variant="outline" onClick={() => void confirmFollowupAppointment(item)}><CalendarCheck className="mr-1 h-4 w-4" />Confirmer avec la patiente</Button>
                    )}
                    <Button size="sm" variant="outline" onClick={() => void completeFollowup(item.id)}><CheckCircle2 className="mr-1 h-4 w-4" />Clôturer</Button>
                  </div>
                </div>
              ))}
              {!loading && followups.filter((item) => item.statut !== 'termine').length === 0 && <p className="py-8 text-center text-muted-foreground">Aucun suivi en attente dans les 30 prochains jours.</p>}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><AlertTriangle className="h-5 w-5 text-red-500" />Événements à surveiller</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {events.slice(0, 6).map((event) => <div key={event.id} className="rounded-xl border border-red-200 bg-red-50/50 p-3"><div className="flex items-center justify-between"><span className="font-medium">Patient #{event.patient_id}</span><span className="rounded-full bg-red-100 px-2 py-1 text-xs font-semibold uppercase text-red-700">{event.gravite}</span></div><p className="mt-1 text-sm">{event.description}</p><p className="mt-1 text-xs text-muted-foreground">{formatDateTime(event.survenu_at)}</p></div>)}
              {events.length === 0 && <p className="py-8 text-center text-muted-foreground">Aucun événement ouvert.</p>}
            </CardContent>
          </Card>
        </div>

        {canViewAudit && (
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><Activity className="h-5 w-5 text-primary" />Journal clinique global</CardTitle></CardHeader>
            <CardContent>
              {auditEntries.length === 0 ? (
                <p className="py-6 text-center text-muted-foreground">Aucune activité clinique enregistrée.</p>
              ) : (
                <div className="max-h-80 overflow-auto rounded-lg border">
                  <div className="min-w-[760px] divide-y">
                    {auditEntries.map((entry) => (
                      <div key={entry.id} className="grid grid-cols-[150px_1fr_130px_1fr] gap-3 px-3 py-2 text-sm">
                        <span className="text-muted-foreground">{formatDateTime(entry.created_at)}</span>
                        <span><strong>{entry.action.replaceAll('_', ' ')}</strong><br /><span className="text-xs text-muted-foreground">{entry.resource_type} #{entry.resource_id}</span></span>
                        <span className="capitalize">{entry.role}</span>
                        <span>{entry.utilisateur} · {entry.patient}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><Plus className="h-5 w-5" />Créer une cure</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2"><div className="grid gap-2"><Label htmlFor="cure-patient">Patient *</Label><Input id="cure-patient" list="clinical-patients" value={patientSearch} onChange={(e) => { const value = e.target.value; setPatientSearch(value); const selected = patientOptions.find((patient) => patientLabel(patient) === value); setPatientId(selected ? String(selected.id) : ''); }} placeholder="Rechercher par nom, téléphone ou ID" autoComplete="off" /><datalist id="clinical-patients">{patientOptions.map((patient) => <option key={patient.id} value={patientLabel(patient)} />)}</datalist>{patientId && <span className="text-xs text-emerald-700">Patient sélectionné : #{patientId}</span>}</div><div className="grid gap-2"><Label htmlFor="cure-name">Nom de la cure *</Label><Input id="cure-name" value={cureForm.nom} onChange={(e) => setCureForm({ ...cureForm, nom: e.target.value })} placeholder="Acné / peeling" /></div></div>
              <div className="grid gap-4 sm:grid-cols-3"><div className="grid gap-2"><Label htmlFor="sessions">Séances *</Label><Input id="sessions" type="number" min="1" max="100" value={cureForm.seances_prevues} onChange={(e) => setCureForm({ ...cureForm, seances_prevues: e.target.value })} /></div><div className="grid gap-2"><Label htmlFor="zone">Zone</Label><Input id="zone" value={cureForm.zone_anatomique} onChange={(e) => setCureForm({ ...cureForm, zone_anatomique: e.target.value })} placeholder="Visage" /></div><div className="grid gap-2"><Label htmlFor="first-session">Première séance</Label><Input id="first-session" type="datetime-local" value={cureForm.premiere_seance_at} onChange={(e) => setCureForm({ ...cureForm, premiere_seance_at: e.target.value })} /></div></div>
              <div className="grid gap-2"><Label htmlFor="cure-notes">Notes</Label><textarea id="cure-notes" className="min-h-20 rounded-md border bg-background px-3 py-2 text-sm" value={cureForm.notes} onChange={(e) => setCureForm({ ...cureForm, notes: e.target.value })} /></div>
              <Button onClick={() => void createCure()}><Plus className="mr-2 h-4 w-4" />Planifier la cure</Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><ClipboardList className="h-5 w-5" />Cures en cours</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              {cures.slice(0, 6).map((cure) => <div key={cure.id} className="rounded-xl border p-4"><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="font-semibold">{cure.nom}</p><p className="text-sm text-muted-foreground">Patient #{cure.patient_id} · {cure.zone_anatomique || 'Zone non précisée'}</p></div><span className="rounded-full bg-primary/10 px-2 py-1 text-xs font-semibold text-primary">{cure.seances_realisees}/{cure.seances_prevues} séances</span></div><div className="mt-3 h-2 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary transition-all" style={{ width: `${Math.min(100, Math.round((cure.seances_realisees / cure.seances_prevues) * 100))}%` }} /></div><div className="mt-3 grid gap-2 sm:grid-cols-3">{cure.seances.slice(0, 6).map((session) => <div key={session.id} className={`rounded-lg border p-2 text-xs ${session.statut === 'realisee' ? 'border-emerald-200 bg-emerald-50' : 'bg-muted/30'}`}><div className="flex justify-between"><span>Séance {session.numero}</span><span>{session.statut === 'realisee' ? '✓' : formatDate(session.planifiee_at)}</span></div>{session.statut !== 'realisee' && <Button className="mt-2 h-7 w-full text-xs" variant="outline" onClick={() => void markSessionDone(cure, session.id)}>Réaliser</Button>}</div>)}</div></div>)}
              {cures.length === 0 && <p className="py-8 text-center text-muted-foreground">Aucune cure créée.</p>}
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <Card><CardHeader><CardTitle>Déclarer un événement indésirable</CardTitle></CardHeader><CardContent className="space-y-3"><div className="grid gap-3 sm:grid-cols-2"><div className="grid gap-2"><Label htmlFor="event-patient">Patient *</Label><Input id="event-patient" list="event-clinical-patients" aria-label="Patient événement" placeholder="Rechercher par nom, téléphone ou ID" value={eventPatientSearch} onChange={(e) => { const value = e.target.value; const selected = eventPatientOptions.find((patient) => patientLabel(patient) === value); setEventPatientSearch(value); setEventForm({ ...eventForm, patient_id: selected ? String(selected.id) : '' }); }} autoComplete="off" /><datalist id="event-clinical-patients">{eventPatientOptions.map((patient) => <option key={patient.id} value={patientLabel(patient)} />)}</datalist></div><select aria-label="Gravité" className="h-10 rounded-md border bg-background px-3 text-sm" value={eventForm.gravite} onChange={(e) => setEventForm({ ...eventForm, gravite: e.target.value })}><option value="faible">Faible</option><option value="moderee">Modérée</option><option value="elevee">Élevée</option><option value="critique">Critique</option></select></div><Input aria-label="Zone anatomique événement" placeholder="Zone anatomique" value={eventForm.zone_anatomique} onChange={(e) => setEventForm({ ...eventForm, zone_anatomique: e.target.value })} /><textarea aria-label="Description événement" className="min-h-24 w-full rounded-md border bg-background px-3 py-2 text-sm" placeholder="Description détaillée *" value={eventForm.description} onChange={(e) => setEventForm({ ...eventForm, description: e.target.value })} /><textarea aria-label="Action effectuée" className="min-h-20 w-full rounded-md border bg-background px-3 py-2 text-sm" placeholder="Action effectuée" value={eventForm.action_effectuee} onChange={(e) => setEventForm({ ...eventForm, action_effectuee: e.target.value })} /><Button variant="destructive" onClick={() => void createEvent()}><AlertTriangle className="mr-2 h-4 w-4" />Enregistrer l’événement</Button></CardContent></Card>

          <Card><CardHeader><CardTitle>Protocoles de soins structurés</CardTitle></CardHeader><CardContent className="space-y-3"><div className="grid gap-3 sm:grid-cols-2"><Input aria-label="Nom protocole" placeholder="Nom du protocole *" value={protocolForm.nom} onChange={(e) => setProtocolForm({ ...protocolForm, nom: e.target.value })} /><Input aria-label="Version protocole" placeholder="Version" value={protocolForm.version} onChange={(e) => setProtocolForm({ ...protocolForm, version: e.target.value })} /></div><div className="grid gap-3 sm:grid-cols-3"><textarea aria-label="Étapes avant" className="min-h-24 rounded-md border bg-background px-3 py-2 text-sm" placeholder="Avant · une étape par ligne" value={protocolForm.avant} onChange={(e) => setProtocolForm({ ...protocolForm, avant: e.target.value })} /><textarea aria-label="Étapes pendant" className="min-h-24 rounded-md border bg-background px-3 py-2 text-sm" placeholder="Pendant · une étape par ligne" value={protocolForm.pendant} onChange={(e) => setProtocolForm({ ...protocolForm, pendant: e.target.value })} /><textarea aria-label="Étapes après" className="min-h-24 rounded-md border bg-background px-3 py-2 text-sm" placeholder="Après · une étape par ligne" value={protocolForm.apres} onChange={(e) => setProtocolForm({ ...protocolForm, apres: e.target.value })} /></div><Button onClick={() => void createProtocol()}><Plus className="mr-2 h-4 w-4" />Publier le protocole</Button><div className="space-y-2 pt-2">{protocols.slice(0, 4).map((protocol) => <div key={protocol.id} className="flex items-center justify-between rounded-lg border p-3 text-sm"><span className="font-medium">{protocol.nom}</span><span className="text-muted-foreground">v{protocol.version} · {protocol.actif ? 'Actif' : 'Inactif'}</span></div>)}</div></CardContent></Card>
        </div>
      </div>
    </DashboardLayout>
  );
}
