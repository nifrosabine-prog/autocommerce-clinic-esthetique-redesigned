import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { api, bookingRequestsApi, dossierMedicalApi, accueilApi, type BookingRequest } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { useAuth } from '@/contexts/AuthContext';
import { Calendar, Plus, Clock, User, Video, ChevronLeft, ChevronRight, ClipboardList, CheckCircle, XCircle, Search, RotateCcw } from 'lucide-react';
import { Link, useLocation } from 'wouter';
import { toast } from 'sonner';
import { PatientAutocomplete, type PatientOption } from '@/components/patients/PatientAutocomplete';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';

const toLocalDateInput = (value: Date = new Date()) => {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

interface Appointment {
  id: number;
  date_heure_debut: string;
  patient_id: number;
  patient_nom: string;
  praticien_id: number;
  praticien_nom: string;
  acte_nom?: string;
  statut: string;
  consentement_manquant: boolean;
  consentement_id?: number | null;
  salle?: string | null;
}

const STATUT_COLORS: Record<string, string> = {
  planifie: 'bg-blue-100 text-blue-800',
  confirme: 'bg-green-100 text-green-800',
  en_cours: 'bg-yellow-100 text-yellow-800',
  termine: 'bg-gray-200 text-gray-800',
  annule: 'bg-red-100 text-red-800',
  no_show: 'bg-orange-100 text-orange-800',
  arrive: 'bg-indigo-100 text-indigo-800',
  accord: 'bg-teal-100 text-teal-800',
};
const STATUT_KEYS = Object.keys(STATUT_COLORS);

export default function AgendaView() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const [, setLocation] = useLocation();
  const canManage = user?.role === 'directrice' || user?.role === 'assistante' || user?.role === 'medecin';
  const canCancel = user?.role === 'directrice' || user?.role === 'assistante';
  const canReviewPublicBookings = user?.role === 'directrice' || user?.role === 'assistante' || user?.role === 'admin';
  const [isLoading, setIsLoading] = useState(true);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [bookingRequests, setBookingRequests] = useState<BookingRequest[]>([]);
  const [dispatchPractitioners, setDispatchPractitioners] = useState<Praticien[]>([]);
  const [isBookingRequestsLoading, setIsBookingRequestsLoading] = useState(false);
  const [view, setView] = useState<'jour' | 'semaine'>('jour');
  const [selectedDate, setSelectedDate] = useState(() => {
    return toLocalDateInput();
  });
  const [createOpen, setCreateOpen] = useState(false);
  const [cancelTarget, setCancelTarget] = useState<Appointment | null>(null);
  const [rescheduleTarget, setRescheduleTarget] = useState<Appointment | null>(null);
  const [patientSearch, setPatientSearch] = useState('');
  const [heureSearch, setHeureSearch] = useState('');

  const dateStr = selectedDate;
  
  const getWeekDates = (baseDate: string) => {
    const d = new Date(`${baseDate}T12:00:00`);
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1); // Lundi
    const monday = new Date(d.setDate(diff));
    return Array.from({ length: 7 }, (_, i) => {
      const date = new Date(monday);
      date.setDate(monday.getDate() + i);
      return toLocalDateInput(date);
    });
  };

  const weekDates = getWeekDates(dateStr);

  const selectedDateLabel = (() => {
    if (view === 'jour') {
      const parsed = new Date(`${dateStr}T12:00:00`);
      return parsed.toLocaleDateString(i18n.language, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
    }
    const first = new Date(`${weekDates[0]}T12:00:00`);
    const last = new Date(`${weekDates[weekDates.length - 1]}T12:00:00`);
    return t('agenda.weekOf', {
      start: first.toLocaleDateString(i18n.language, { day: 'numeric', month: 'short' }),
      end: last.toLocaleDateString(i18n.language, { day: 'numeric', month: 'short', year: 'numeric' }),
    });
  })();

  useEffect(() => {
    loadAppointments();
    if (canReviewPublicBookings) {
      loadBookingRequests();
      loadDispatchPractitioners();
    }
  }, [dateStr, view, canReviewPublicBookings, patientSearch, heureSearch]);

  const loadAppointments = async () => {
    try {
      const baseParams = view === 'jour'
        ? { vue: 'jour', date_debut: `${dateStr}T00:00:00`, date_fin: `${dateStr}T23:59:59` }
        : { vue: 'semaine', date_debut: `${weekDates[0]}T00:00:00`, date_fin: `${weekDates[5]}T23:59:59` };
      const params = {
        ...baseParams,
        ...(patientSearch.trim() ? { patient_search: patientSearch.trim() } : {}),
        ...(heureSearch ? { heure: heureSearch } : {}),
      };
      
      const response = await api.get('/agenda', { params });
      setAppointments(Array.isArray(response.data) ? response.data : []);
    } catch (err: any) {
      toast.error(t('agenda.loadError'));
    } finally {
      setIsLoading(false);
    }
  };

  const loadBookingRequests = async () => {
    try {
      setIsBookingRequestsLoading(true);
      const response = await bookingRequestsApi.list('pending');
      setBookingRequests(Array.isArray(response.data) ? response.data : []);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('agenda.requestsLoadError'));
    } finally {
      setIsBookingRequestsLoading(false);
    }
  };

  const loadDispatchPractitioners = async () => {
    try {
      const response = await api.get('/agenda/praticiens');
      setDispatchPractitioners(Array.isArray(response.data) ? response.data : []);
    } catch {
      toast.error(t('agenda.practitionersLoadError'));
    }
  };

  const handleBookingRequestAssignment = async (requestId: number, practitionerId: number) => {
    try {
      await bookingRequestsApi.assign(requestId, practitionerId);
      toast.success(t('agenda.dispatchSuccess'));
      await loadBookingRequests();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('agenda.dispatchError'));
    }
  };

  const handleBookingRequestDecision = async (request: BookingRequest, decision: 'approve' | 'reject') => {
    try {
      if (decision === 'approve') {
        await bookingRequestsApi.approve(request.id);
        toast.success(t('agenda.approveSuccess'));
      } else {
        await bookingRequestsApi.reject(request.id, t('agenda.rejectReason'));
        toast.success(t('agenda.rejectSuccess'));
      }
      await Promise.all([loadBookingRequests(), loadAppointments()]);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('agenda.requestDecisionError'));
    }
  };

  const navigateDate = (direction: number) => {
    const d = new Date(`${dateStr}T12:00:00`);
    if (view === 'jour') d.setDate(d.getDate() + direction);
    else d.setDate(d.getDate() + (direction * 7));
    setSelectedDate(toLocalDateInput(d));
  };

  const handleStatusChange = async (rdv: Appointment, statut: string) => {
    try {
      await api.patch(`/agenda/rdv/${rdv.id}/statut`, { statut });
      toast.success(t('agenda.statusUpdated'));
      loadAppointments();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('agenda.statusUpdateError'));
    }
  };

  const handlePatientArrived = async (rdv: Appointment) => {
    try {
      const response = await accueilApi.markArrived(rdv.id);
      toast.success(t('agenda.arrivalRegistered'));
      const episode = response.data.episode_id ? `&episodeId=${response.data.episode_id}` : '';
      setLocation(`/medical-record/${response.data.patient_id}?rdvId=${rdv.id}${episode}`);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('agenda.arrivalError'));
    }
  };

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-96">
          <Spinner />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">{t('agenda.title')}</h1>
            <div className="flex items-center gap-2 mt-1">
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => navigateDate(-1)}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <p className="text-muted-foreground font-medium min-w-[200px] text-center">
                {selectedDateLabel}
              </p>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => navigateDate(1)}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="bg-muted p-1 rounded-md flex">
              <Button 
                variant={view === 'jour' ? 'secondary' : 'ghost'} 
                size="sm" 
                className="h-8 text-xs"
                onClick={() => setView('jour')}
              >
                {t('agenda.day')}
              </Button>
              <Button 
                variant={view === 'semaine' ? 'secondary' : 'ghost'} 
                size="sm" 
                className="h-8 text-xs"
                onClick={() => setView('semaine')}
              >
                {t('agenda.week')}
              </Button>
            </div>
            {canManage && (
              <Button onClick={() => setCreateOpen(true)} className="h-9">
                <Plus className="w-4 h-4 mr-2" />
                {t('agenda.newAppointment')}
              </Button>
            )}
          </div>
        </div>

        {canReviewPublicBookings && (
          <Card className="border-purple-200 bg-purple-50/40">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <ClipboardList className="h-4 w-4 text-purple-700" />
                {t('agenda.publicRequestsTitle')}
                <span className="rounded-full bg-purple-600 px-2 py-0.5 text-xs text-white">
                  {bookingRequests.length}
                </span>
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                {t('agenda.publicRequestsHint')}
              </p>
            </CardHeader>
            <CardContent className="space-y-3">
              {isBookingRequestsLoading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner /> {t('agenda.loadingRequests')}</div>
              ) : bookingRequests.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t('agenda.noPendingRequests')}</p>
              ) : (
                bookingRequests.map((request) => (
                  <div key={request.id} className="flex flex-col gap-3 rounded-lg border bg-white p-3 md:flex-row md:items-center md:justify-between">
                    <div>
                      <p className="font-medium">{request.prenom} {request.nom}</p>
                      <p className="text-sm text-muted-foreground">{request.telephone} · {new Date(request.date_heure).toLocaleString(i18n.language)}</p>
                      <p className="text-sm text-muted-foreground">{t('agenda.requestNumber', { id: request.id })}</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <select
                        aria-label={t('agenda.dispatchLabel')}
                        value={request.praticien_id ? String(request.praticien_id) : ''}
                        onChange={(event) => {
                          const value = Number(event.target.value);
                          if (value) void handleBookingRequestAssignment(request.id, value);
                        }}
                        className="h-9 rounded-md border bg-white px-2 text-sm"
                      >
                        <option value="">{t('agenda.dispatchPlaceholder')}</option>
                        {dispatchPractitioners.map((practitioner) => (
                          <option key={practitioner.id} value={practitioner.id}>
                            {practitioner.prenom} {practitioner.nom}
                          </option>
                        ))}
                      </select>
                      <Button size="sm" onClick={() => handleBookingRequestDecision(request, 'approve')}>
                        <CheckCircle className="mr-1 h-3.5 w-3.5" /> {t('agenda.approve')}
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => handleBookingRequestDecision(request, 'reject')}>
                        <XCircle className="mr-1 h-3.5 w-3.5" /> {t('agenda.reject')}
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        )}

        <Card className="border-slate-200 bg-slate-50/70">
          <CardContent className="p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
              <div className="flex-1">
                <Label htmlFor="agenda-patient-search" className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground"><Search className="h-3.5 w-3.5" /> {t('agenda.searchLabel')}</Label>
                <Input id="agenda-patient-search" value={patientSearch} onChange={(e) => setPatientSearch(e.target.value)} placeholder={t('agenda.searchPlaceholder')} />
              </div>
              <div className="w-full lg:w-40">
                <Label htmlFor="agenda-hour-search" className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{t('agenda.time')}</Label>
                <Input id="agenda-hour-search" type="time" value={heureSearch} onChange={(e) => setHeureSearch(e.target.value)} />
              </div>
              <Button type="button" variant="outline" className="gap-2" onClick={() => { setPatientSearch(''); setHeureSearch(''); }} disabled={!patientSearch && !heureSearch}><RotateCcw className="h-4 w-4" /> {t('agenda.reset')}</Button>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">{t('agenda.searchHint')}</p>
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 gap-6">
          {view === 'semaine' ? (
            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-7 gap-4">
              {weekDates.map((date) => {
                const dayRdvs = appointments.filter(a => a.date_heure_debut.startsWith(date));
                const d = new Date(date);
                const isToday = date === toLocalDateInput();
                return (
                  <div key={date} className={`space-y-3 p-3 rounded-lg border ${isToday ? 'bg-purple-50/50 border-purple-200' : 'bg-card'}`}>
                    <div className="text-center pb-2 border-b">
                      <p className="text-[10px] uppercase text-muted-foreground font-bold">
                        {d.toLocaleDateString(i18n.language, { weekday: 'short' })}
                      </p>
                      <p className={`text-lg font-bold ${isToday ? 'text-purple-700' : ''}`}>
                        {d.getDate()}
                      </p>
                    </div>
                    <div className="space-y-2 min-h-[100px]">
                      {dayRdvs.length === 0 ? (
                        <p className="text-[10px] text-center text-muted-foreground pt-4 italic">{t('agenda.free')}</p>
                      ) : (
                        dayRdvs.map(rdv => (
                          <div key={rdv.id} className="p-2 rounded bg-white border text-[10px] shadow-sm">
                            <p className="font-bold">{new Date(rdv.date_heure_debut).toLocaleTimeString(i18n.language, { hour: '2-digit', minute: '2-digit' })}</p>
                            <p className="truncate">{rdv.patient_nom}</p>
                            <p className="text-muted-foreground truncate">{rdv.acte_nom}</p>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="space-y-4">
              {appointments.length === 0 ? (
                <Card><CardContent className="pt-6 text-center text-muted-foreground">{t('agenda.noAppointments')}</CardContent></Card>
              ) : (
                appointments.map((appointment) => {
              const statutInfo = { label: t(`agenda.status.${appointment.statut}`, { defaultValue: appointment.statut }), color: STATUT_COLORS[appointment.statut] || 'bg-gray-100 text-gray-800' };
              return (
                <Card key={appointment.id} className="hover:shadow-md transition-shadow">
                  <CardContent className="pt-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <Clock className="w-4 h-4 text-muted-foreground" />
                          <span className="font-semibold">
                            {new Date(appointment.date_heure_debut).toLocaleTimeString(i18n.language, { hour: '2-digit', minute: '2-digit' })}
                          </span>
                          <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${statutInfo.color}`}>
                            {statutInfo.label}
                          </span>
                          {appointment.consentement_manquant && (
                            <span className="inline-block px-2 py-1 rounded text-xs font-medium bg-red-100 text-red-800">
                              {t('agenda.missingConsent')}
                            </span>
                          )}
                          {!appointment.consentement_manquant && appointment.consentement_id && (
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              className="h-7 gap-1 text-xs"
                              onClick={async () => {
                                try {
                                  await dossierMedicalApi.openConsentement(appointment.patient_id, appointment.consentement_id!);
                                } catch (err: any) {
                                  toast.error(err.response?.data?.detail || t('agenda.signedConsentUnavailable'));
                                }
                              }}
                            >
                              {t('agenda.signedConsent')}
                            </Button>
                          )}
                        </div>
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <User className="w-4 h-4 text-muted-foreground" />
                            <span className="text-sm">{appointment.patient_nom}</span>
                          </div>
                          <p className="text-sm text-muted-foreground">{appointment.acte_nom || t('agenda.noActeSpecified')}</p>
                          <p className="text-xs text-muted-foreground">{t('agenda.practitionerLabel', { name: appointment.praticien_nom })}</p>
                          {appointment.statut !== 'annule' && appointment.statut !== 'termine' && (
                            <div className="pt-2">
                              <Link href={`/teleconsultation/${appointment.id}`}>
                                <Button size="sm" variant="outline" className="h-8 text-xs gap-2">
                                  <Video className="w-3.5 h-3.5" />
                                  {t('agenda.startVideo')}
                                </Button>
                              </Link>
                            </div>
                          )}
                        </div>
                      </div>
                      {canManage && appointment.statut !== 'annule' && (
                        <div className="flex gap-2">
                          {(appointment.statut === 'planifie' || appointment.statut === 'confirme') && (
                            <Button variant="default" size="sm" onClick={() => handlePatientArrived(appointment)}>
                              <CheckCircle className="mr-1 h-3.5 w-3.5" /> {t('agenda.patientArrived')}
                            </Button>
                          )}
                          <select
                            value={appointment.statut}
                            onChange={(e) => handleStatusChange(appointment, e.target.value)}
                            className="text-sm border rounded-md px-2 py-1"
                          >
                            {STATUT_KEYS.filter((k) => k !== 'annule').map((k) => (
                              <option key={k} value={k}>{t(`agenda.status.${k}`)}</option>
                            ))}
                          </select>
                          <Button variant="outline" size="sm" onClick={() => setRescheduleTarget(appointment)}>
                            {t('agenda.editReschedule')}
                          </Button>
                          {canCancel && (
                            <Button variant="ghost" size="sm" onClick={() => setCancelTarget(appointment)}>
                              {t('common.cancel')}
                            </Button>
                          )}
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              );
            })
          )}
            </div>
          )}
        </div>
      </div>

      <NewRdvDialog open={createOpen} onOpenChange={setCreateOpen} defaultDate={dateStr} onCreated={loadAppointments} />
      <CancelRdvDialog appointment={cancelTarget} onOpenChange={() => setCancelTarget(null)} onCancelled={loadAppointments} />
      <RescheduleRdvDialog appointment={rescheduleTarget} onOpenChange={() => setRescheduleTarget(null)} onRescheduled={loadAppointments} />
    </DashboardLayout>
  );
}

// ─────────────────────────────────────────────────────────

interface Praticien { id: number; nom: string; prenom: string; specialite?: string | null }
interface Acte { id: number; nom: string; duree_minutes: number }
interface CreneauDisponible { heure: string; datetime: string }

function NewRdvDialog({ open, onOpenChange, defaultDate, onCreated }: {
  open: boolean; onOpenChange: (v: boolean) => void; defaultDate: string; onCreated: () => void;
}) {
  const { t, i18n } = useTranslation();
  const [patientAutocompleteKey, setPatientAutocompleteKey] = useState(0);
  const [selectedPatient, setSelectedPatient] = useState<PatientOption | null>(null);
  const [patientId, setPatientId] = useState('');
  const [praticiens, setPraticiens] = useState<Praticien[]>([]);
  const [praticienId, setPraticienId] = useState('');
  const [actes, setActes] = useState<Acte[]>([]);
  const [acteId, setActeId] = useState('');
  const [date, setDate] = useState(defaultDate);
  const [creneaux, setCreneaux] = useState<CreneauDisponible[]>([]);
  const [creneau, setCreneau] = useState('');
  const [salle, setSalle] = useState('');
  const [isLoadingCreneaux, setIsLoadingCreneaux] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const handlePatientSelect = (patient: PatientOption | null) => {
    setSelectedPatient(patient);
    setPatientId(patient ? String(patient.id) : '');
  };

  useEffect(() => {
    if (open) {
      setSelectedPatient(null); setPatientId('');
      setPatientAutocompleteKey((prev) => prev + 1);
      setPraticienId(''); setActeId(''); setDate(defaultDate);
      setCreneaux([]); setCreneau(''); setSalle('');
      api.get('/agenda/praticiens').then((r) => setPraticiens(r.data)).catch(() => {});
      api.get('/agenda/actes').then((r) => setActes(r.data)).catch(() => {});
    }
  }, [open, defaultDate]);

  useEffect(() => {
    const acteSelectionne = actes.find((acte) => String(acte.id) === acteId);
    if (!praticienId || !date || !acteSelectionne) {
      setCreneaux([]);
      setCreneau('');
      setIsLoadingCreneaux(false);
      return;
    }

    let cancelled = false;
    setIsLoadingCreneaux(true);
    setCreneau('');

    api.get(`/agenda/disponibilites/${praticienId}`, {
      params: { date, duree: acteSelectionne.duree_minutes },
    })
      .then((r) => {
        if (cancelled) return;
        const rawSlots = Array.isArray(r.data?.creneaux) ? r.data.creneaux : [];
        const normalizedSlots = rawSlots
          .map((slot: unknown): CreneauDisponible | null => {
            if (typeof slot === 'string') {
              const parsed = new Date(slot);
              return {
                datetime: slot,
                heure: Number.isNaN(parsed.getTime())
                  ? slot
                  : parsed.toLocaleTimeString(i18n.language, { hour: '2-digit', minute: '2-digit' }),
              };
            }
            if (!slot || typeof slot !== 'object') return null;
            const candidate = slot as { heure?: unknown; datetime?: unknown };
            if (typeof candidate.datetime !== 'string' || !candidate.datetime) return null;
            return {
              datetime: candidate.datetime,
              heure: typeof candidate.heure === 'string' && candidate.heure
                ? candidate.heure
                : new Date(candidate.datetime).toLocaleTimeString(i18n.language, {
                    hour: '2-digit', minute: '2-digit',
                  }),
            };
          })
          .filter((slot: CreneauDisponible | null): slot is CreneauDisponible => Boolean(slot));
        setCreneaux(normalizedSlots);
      })
      .catch(() => {
        if (!cancelled) setCreneaux([]);
      })
      .finally(() => {
        if (!cancelled) setIsLoadingCreneaux(false);
      });

    return () => { cancelled = true; };
  }, [praticienId, date, acteId, actes]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!patientId || !praticienId || !acteId || !creneau) {
      toast.error(t('agenda.fillRequiredFields'));
      return;
    }
    if (!creneaux.some((slot) => slot.datetime === creneau)) {
      toast.error(t('agenda.slotNoLongerAvailable'));
      return;
    }
    setIsSaving(true);
    try {
      await api.post('/agenda/rdv', {
        patient_id: Number(patientId),
        praticien_id: Number(praticienId),
        acte_id: Number(acteId),
        date_heure: creneau,
        salle: salle || undefined,
      });
      toast.success(t('agenda.createAppointmentSuccess'));
      onOpenChange(false);
      onCreated();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('agenda.createAppointmentError'));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('agenda.newAppointmentTitle')}</DialogTitle>
          <DialogDescription>{t('agenda.newAppointmentDescription')}</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <PatientAutocomplete
            key={patientAutocompleteKey}
            selectedPatient={selectedPatient}
            onSelect={handlePatientSelect}
          />

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="praticien">{t('agenda.practitioner')} *</Label>
              <select id="praticien" value={praticienId} onChange={(e) => setPraticienId(e.target.value)} className="w-full h-9 px-3 border rounded-md text-sm">
                <option value="">{t('common.select')}</option>
                {praticiens.map((p) => <option key={p.id} value={p.id}>{p.prenom} {p.nom}</option>)}
              </select>
            </div>
            <div>
              <Label htmlFor="acte">{t('agenda.act')} *</Label>
              <select id="acte" value={acteId} onChange={(e) => setActeId(e.target.value)} className="w-full h-9 px-3 border rounded-md text-sm">
                <option value="">{t('common.select')}</option>
                {actes.map((a) => <option key={a.id} value={a.id}>{a.nom}</option>)}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="rdv-date">{t('agenda.date')} *</Label>
              <Input id="rdv-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="creneau">{t('agenda.slot')} *</Label>
              {!acteId ? (
                <p className="text-xs text-muted-foreground py-2">{t('agenda.chooseActFirst')}</p>
              ) : isLoadingCreneaux ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground py-2"><Spinner className="h-4 w-4" /> {t('agenda.searching')}</div>
              ) : (
                <select id="creneau" value={creneau} onChange={(e) => setCreneau(e.target.value)} className="w-full h-9 px-3 border rounded-md text-sm" disabled={creneaux.length === 0}>
                  <option value="">{creneaux.length === 0 ? t('agenda.noSlotAvailable') : t('common.select')}</option>
                  {creneaux.map((c) => (
                    <option key={c.datetime} value={c.datetime}>{c.heure}</option>
                  ))}
                </select>
              )}
            </div>
          </div>

          <div>
            <Label htmlFor="salle">{t('agenda.room')}</Label>
            <Input id="salle" value={salle} onChange={(e) => setSalle(e.target.value)} placeholder={t('common.optional')} />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={isSaving}>{isSaving ? <Spinner className="h-4 w-4" /> : t('agenda.createButton')}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function CancelRdvDialog({ appointment, onOpenChange, onCancelled }: {
  appointment: Appointment | null; onOpenChange: () => void; onCancelled: () => void;
}) {
  const { t, i18n } = useTranslation();
  const [raison, setRaison] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => { setRaison(''); }, [appointment]);

  const handleConfirm = async () => {
    if (!appointment) return;
    if (raison.trim().length < 3) {
      toast.error(t('agenda.cancelReasonTooShort'));
      return;
    }
    setIsSaving(true);
    try {
      await api.delete(`/agenda/rdv/${appointment.id}`, { params: { raison: raison.trim() } });
      toast.success(t('agenda.cancelSuccess'));
      onOpenChange();
      onCancelled();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('agenda.cancelError'));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={!!appointment} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('agenda.cancelAppointment')}</DialogTitle>
          <DialogDescription>
            {appointment && `${appointment.patient_nom} — ${new Date(appointment.date_heure_debut).toLocaleString(i18n.language)}`}
          </DialogDescription>
        </DialogHeader>
        <div>
          <Label htmlFor="raison">{t('agenda.cancelReasonLabel')} *</Label>
          <Textarea id="raison" value={raison} onChange={(e) => setRaison(e.target.value)} rows={3} />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onOpenChange}>{t('agenda.back')}</Button>
          <Button variant="destructive" onClick={handleConfirm} disabled={isSaving}>
            {isSaving ? <Spinner className="h-4 w-4" /> : t('agenda.confirmCancel')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}


function RescheduleRdvDialog({ appointment, onOpenChange, onRescheduled }: {
  appointment: Appointment | null;
  onOpenChange: () => void;
  onRescheduled: () => void;
}) {
  const { user } = useAuth();
  const { t, i18n } = useTranslation();
  const [date, setDate] = useState('');
  const [heure, setHeure] = useState('');
  const [salle, setSalle] = useState('');
  const [praticienId, setPraticienId] = useState('');
  const [praticiens, setPraticiens] = useState<{ id: number; nom_complet?: string; nom?: string; prenom?: string }[]>([]);
  const [suggestions, setSuggestions] = useState<{ datetime: string; score: number; reason: string }[]>([]);
  const [isLoadingSuggestions, setIsLoadingSuggestions] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!appointment) return;
    const current = new Date(appointment.date_heure_debut);
    setDate(toLocalDateInput(current));
    setHeure(current.toLocaleTimeString(i18n.language, { hour: '2-digit', minute: '2-digit' }));
    setSalle(appointment.salle || '');
    setPraticienId(String(appointment.praticien_id));
    setSuggestions([]);
    api.get('/agenda/praticiens').then((response) => {
      setPraticiens(Array.isArray(response.data) ? response.data : []);
    }).catch(() => toast.error(t('agenda.practitionersLoadError')));
  }, [appointment]);

  const loadSuggestions = async () => {
    if (!appointment || !date) return;
    setIsLoadingSuggestions(true);
    try {
      const response = await api.get(`/agenda/rdv/${appointment.id}/suggestions`, { params: { date } });
      setSuggestions(Array.isArray(response.data?.suggestions) ? response.data.suggestions : []);
      if (!response.data?.suggestions?.length) toast.info(t('agenda.noSlotForDate'));
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('agenda.suggestionsError'));
    } finally {
      setIsLoadingSuggestions(false);
    }
  };

  const selectSuggestion = (datetime: string) => {
    const parsed = new Date(datetime);
    if (Number.isNaN(parsed.getTime())) return;
    setDate(toLocalDateInput(parsed));
    setHeure(parsed.toLocaleTimeString(i18n.language, { hour: '2-digit', minute: '2-digit' }));
  };

  const handleSave = async () => {
    if (!appointment || !date || !heure) {
      toast.error(t('agenda.selectDateTime'));
      return;
    }
    setIsSaving(true);
    try {
      await api.patch(`/agenda/rdv/${appointment.id}/replanifier`, {
        date_heure: `${date}T${heure}:00`,
        salle: salle || null,
        praticien_id: praticienId ? Number(praticienId) : null,
      });
      toast.success(t('agenda.rescheduleSuccess'));
      onOpenChange();
      onRescheduled();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('agenda.rescheduleConflict'));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={!!appointment} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{t('agenda.rescheduleTitle')}</DialogTitle>
          <DialogDescription>
            {appointment && `${appointment.patient_nom} · ${appointment.acte_nom || t('agenda.noActeSpecified')} · ${appointment.praticien_nom}`}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div><Label htmlFor="reschedule-date">{t('agenda.date')} *</Label><Input id="reschedule-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} /></div>
            <div><Label htmlFor="reschedule-time">{t('agenda.time')} *</Label><Input id="reschedule-time" type="time" value={heure} onChange={(e) => setHeure(e.target.value)} /></div>
          </div>
          <div>
            <Label htmlFor="reschedule-practitioner">{t('agenda.practitioner')} *</Label>
            <select id="reschedule-practitioner" value={praticienId} onChange={(e) => setPraticienId(e.target.value)} className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-sm">
              {/* Doit rester aligné avec CLINICAL_SELF_SCOPED_ROLES côté backend (agenda_clinic.py) */}
              {praticiens.filter((praticien) => !['medecin', 'estheticienne'].includes(user?.role || '') || praticien.id === user?.id).map((praticien) => (
                <option key={praticien.id} value={praticien.id}>{praticien.nom_complet || `${praticien.prenom || ''} ${praticien.nom || ''}`.trim()}</option>
              ))}
            </select>
          </div>
          <div><Label htmlFor="reschedule-room">{t('agenda.room')}</Label><Input id="reschedule-room" value={salle} onChange={(e) => setSalle(e.target.value)} placeholder={t('agenda.roomPlaceholder')} /></div>
          <div className="rounded-lg border bg-slate-50 p-3">
            <div className="flex items-center justify-between gap-3"><div><p className="font-medium">{t('agenda.schedulingAssistant')}</p><p className="text-xs text-muted-foreground">{t('agenda.schedulingAssistantHint')}</p></div><Button type="button" size="sm" variant="outline" onClick={loadSuggestions} disabled={isLoadingSuggestions || !date}>{isLoadingSuggestions ? <Spinner className="h-4 w-4" /> : t('agenda.suggest')}</Button></div>
            {suggestions.length > 0 && <div className="mt-3 space-y-2">{suggestions.map((suggestion) => <button type="button" key={suggestion.datetime} onClick={() => selectSuggestion(suggestion.datetime)} className="flex w-full items-center justify-between rounded-md border bg-white p-2 text-left transition hover:border-primary"><span><strong className="block text-sm">{new Date(suggestion.datetime).toLocaleString(i18n.language)}</strong><small className="text-muted-foreground">{suggestion.reason}</small></span><span className="text-xs font-semibold text-emerald-700">{t('agenda.score', { value: suggestion.score })}</span></button>)}</div>}
          </div>
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onOpenChange}>{t('common.cancel')}</Button>
          <Button type="button" onClick={handleSave} disabled={isSaving}>{isSaving ? <Spinner className="h-4 w-4" /> : t('agenda.saveChanges')}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
