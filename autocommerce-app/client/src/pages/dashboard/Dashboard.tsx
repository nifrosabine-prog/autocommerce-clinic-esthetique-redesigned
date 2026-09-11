import React, { useState, useEffect } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent } from '@/components/ui/card';
import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import {
  AlertCircle,
  ArrowUpRight,
  Calendar,
  CheckCircle2,
  Clock3,
  DollarSign,
  FileText,
  MessageCircle,
  PackageSearch,
  Sparkles,
  Stethoscope,
  TrendingUp,
  Users,
} from 'lucide-react';
import { Link } from 'wouter';
import { PointageWidget } from '@/components/dashboard/PointageWidget';

interface DashboardStats {
  todayAppointments: number;
  missingConsent: number;
  stockAlerts: number;
  unpaidInvoices: number;
  socialMessages: number;
}

interface AgendaItem {
  id: number;
  patient_id: number;
  patient_nom: string;
  praticien_nom: string;
  acte_nom?: string | null;
  date_heure_debut: string;
  consentement_manquant: boolean;
}

interface ActivityItem {
  id: number;
  entite_type: string;
  action: string;
  modifie_par_nom?: string;
  created_at: string;
}

interface AssignedTask {
  id: number;
  titre: string;
  priorite: string;
  statut: string;
  due_at?: string | null;
}

function todayLocalDate(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

const statCards = [
  {
    key: 'todayAppointments' as const,
    label: "Rendez-vous aujourd'hui",
    helper: 'agenda du jour',
    icon: Calendar,
    accent: 'bg-blue-50 text-blue-700',
    href: '/agenda',
  },
  {
    key: 'missingConsent' as const,
    label: 'Consentements à signer',
    helper: 'avant clôture de l’acte',
    icon: Stethoscope,
    accent: 'bg-amber-50 text-amber-700',
    href: '/dossiers',
  },
  {
    key: 'unpaidInvoices' as const,
    label: 'Factures à suivre',
    helper: 'en attente de paiement',
    icon: DollarSign,
    accent: 'bg-emerald-50 text-emerald-700',
    href: '/invoices',
  },
  {
    key: 'socialMessages' as const,
    label: 'Messages à traiter',
    helper: 'demandes sociales nouvelles',
    icon: MessageCircle,
    accent: 'bg-teal-50 text-teal-700',
    href: '/social',
  },
];

export default function Dashboard() {
  const { user } = useAuth();
  const [isLoading, setIsLoading] = useState(true);
  const [stats, setStats] = useState<DashboardStats>({
    todayAppointments: 0,
    missingConsent: 0,
    stockAlerts: 0,
    unpaidInvoices: 0,
    socialMessages: 0,
  });
  const [agendaItems, setAgendaItems] = useState<AgendaItem[]>([]);
  const [pendingBookings, setPendingBookings] = useState(0);
  const [pendingCallbacks, setPendingCallbacks] = useState(0);
  const [dueFollowups, setDueFollowups] = useState(0);
  const [recentActivity, setRecentActivity] = useState<ActivityItem[]>([]);
  const [assignedTasks, setAssignedTasks] = useState<AssignedTask[]>([]);
  const [hasDataWarning, setHasDataWarning] = useState(false);

  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        setIsLoading(true);
        const today = todayLocalDate();
        const [agendaRes, stockRes, facturesRes, socialRes, bookingsRes, callbacksRes, auditRes, followupsRes, tasksRes] = await Promise.allSettled([
          api.get(`/agenda?date_debut=${today}T00:00:00&date_fin=${today}T23:59:59&vue=jour`),
          api.get('/injectables/stock'),
          api.get('/factures'),
          api.get('/social/analytics'),
          api.get('/booking-requests?statut=pending'),
          api.get('/callback-leads?statut=pending'),
          api.get('/factures/audit-logs'),
          api.get('/clinical-ops/suivis?statut=a_faire&horizon_days=7'),
          api.get('/workflows/tasks/mine'),
        ]);

        let todayAppointments = 0;
        let missingConsent = 0;
        if (agendaRes.status === 'fulfilled' && Array.isArray(agendaRes.value.data)) {
          todayAppointments = agendaRes.value.data.length;
          const items = agendaRes.value.data as AgendaItem[];
          missingConsent = items.filter((item) => item.consentement_manquant).length;
          setAgendaItems(items);
        }

        let stockAlerts = 0;
        if (stockRes.status === 'fulfilled' && stockRes.value.data?.total_alertes !== undefined) {
          stockAlerts = stockRes.value.data.total_alertes;
        }

        let unpaidInvoices = 0;
        if (facturesRes.status === 'fulfilled' && Array.isArray(facturesRes.value.data)) {
          unpaidInvoices = facturesRes.value.data.filter((f: { statut: string }) =>
            ['envoyee', 'partiellement_payee'].includes(f.statut)
          ).length;
        }

        let socialMessages = 0;
        if (socialRes.status === 'fulfilled' && socialRes.value.data?.messages) {
          const msgs = socialRes.value.data.messages;
          socialMessages = Object.values(msgs).reduce(
            (total: number, platformStats: any) => total + (platformStats.nouveau || 0),
            0,
          );
        }

        if (bookingsRes.status === 'fulfilled' && Array.isArray(bookingsRes.value.data)) setPendingBookings(bookingsRes.value.data.length);
        if (callbacksRes.status === 'fulfilled' && Array.isArray(callbacksRes.value.data)) setPendingCallbacks(callbacksRes.value.data.length);
        if (auditRes.status === 'fulfilled' && Array.isArray(auditRes.value.data)) setRecentActivity(auditRes.value.data.slice(0, 5));
        if (followupsRes.status === 'fulfilled' && Array.isArray(followupsRes.value.data)) setDueFollowups(followupsRes.value.data.length);
        if (tasksRes.status === 'fulfilled' && Array.isArray(tasksRes.value.data?.data)) setAssignedTasks(tasksRes.value.data.data);
        setHasDataWarning([agendaRes, stockRes, facturesRes, socialRes, bookingsRes, callbacksRes, auditRes, followupsRes, tasksRes].some((result) => {
          if (result.status !== 'rejected') return false;
          const httpStatus = (result.reason as any)?.response?.status;
          return httpStatus !== 401 && httpStatus !== 403;
        }));
        setStats({ todayAppointments, missingConsent, stockAlerts, unpaidInvoices, socialMessages });
      } finally {
        setIsLoading(false);
      }
    };

    loadDashboardData();
  }, []);

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex min-h-[28rem] items-center justify-center">
          <Spinner />
        </div>
      </DashboardLayout>
    );
  }

  const displayName = `${user?.prenom || ''} ${user?.nom || ''}`.trim();
  const today = new Intl.DateTimeFormat('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(new Date());
  const recommendations = [
    stats.missingConsent > 0 ? { label: `Faire signer ${stats.missingConsent} consentement${stats.missingConsent > 1 ? 's' : ''}`, detail: 'Sécuriser les clôtures cliniques du jour.', href: '/dossiers' } : null,
    pendingBookings > 0 ? { label: `Traiter ${pendingBookings} demande${pendingBookings > 1 ? 's' : ''} de rendez-vous`, detail: 'Rappeler, qualifier puis confirmer le créneau.', href: '/agenda' } : null,
    pendingCallbacks > 0 ? { label: `Rappeler ${pendingCallbacks} patient${pendingCallbacks > 1 ? 's' : ''}`, detail: 'Réduire les délais de réponse de la clinique.', href: '/social' } : null,
    stats.stockAlerts > 0 ? { label: `Vérifier ${stats.stockAlerts} alerte${stats.stockAlerts > 1 ? 's' : ''} de stock`, detail: 'Prévenir toute rupture pendant une consultation.', href: '/stock' } : null,
  ].filter((item): item is { label: string; detail: string; href: string } => Boolean(item));

  return (
    <DashboardLayout>
      <div className="mx-auto max-w-[1500px] space-y-6 pb-8">
        <section className="relative overflow-hidden rounded-[1.5rem] bg-[#071a3b] px-6 py-7 text-white shadow-[0_20px_60px_-28px_rgba(7,26,59,0.7)] sm:px-8 sm:py-9">
          <div className="absolute -right-20 -top-24 h-72 w-72 rounded-full bg-cyan-400/20 blur-3xl" />
          <div className="absolute bottom-[-6rem] left-1/3 h-52 w-52 rounded-full bg-blue-500/20 blur-3xl" />
          <div className="relative flex flex-col justify-between gap-7 lg:flex-row lg:items-end">
            <div>
              <div className="mb-4 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-cyan-200">
                <Sparkles className="h-4 w-4" />
                Pilotage clinique
              </div>
              <h1 className="max-w-2xl text-3xl font-semibold tracking-tight sm:text-4xl">
                Bonjour {displayName || 'à vous'}.
              </h1>
              <p className="mt-2 max-w-xl text-sm leading-6 text-blue-100/75">
                Une vision claire de l’activité essentielle de votre clinique, sans bruit et sans métriques décoratives.
              </p>
            </div>
            <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/10 px-4 py-3 backdrop-blur-sm">
              <Clock3 className="h-5 w-5 text-cyan-200" />
              <div>
                <p className="text-[11px] uppercase tracking-[0.14em] text-blue-100/60">Aujourd’hui</p>
                <p className="mt-1 text-sm font-medium capitalize">{today}</p>
              </div>
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {statCards.map((item) => {
            const Icon = item.icon;
            const value = stats[item.key];
            return (
              <Link href={item.href} key={item.key} className="group block">
                <Card className="h-full rounded-2xl border-slate-200/80 bg-white shadow-sm transition-all duration-200 group-hover:-translate-y-0.5 group-hover:border-blue-200 group-hover:shadow-lg">
                  <CardContent className="p-5">
                    <div className="flex items-start justify-between gap-4">
                      <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${item.accent}`}>
                        <Icon className="h-5 w-5" />
                      </div>
                      <ArrowUpRight className="h-4 w-4 text-slate-300 transition-colors group-hover:text-blue-600" />
                    </div>
                    <p className="mt-5 text-sm font-medium text-slate-600">{item.label}</p>
                    <div className="mt-1 flex items-end justify-between gap-3">
                      <p className="text-3xl font-semibold tracking-tight text-[#071a3b]">{value}</p>
                      <TrendingUp className="mb-1 h-4 w-4 text-emerald-500" />
                    </div>
                    <p className="mt-1 text-xs text-slate-400">{item.helper}</p>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </section>

        {hasDataWarning && (
          <div role="status" className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            Certaines données du tableau de bord sont momentanément indisponibles. Les autres indicateurs restent consultables.
          </div>
        )}

        <section className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
          <Card className="overflow-hidden rounded-2xl border-slate-200 bg-white shadow-sm">
            <CardContent className="p-0">
              <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
                <div><p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal-700">Agenda du jour</p><h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-950">Les prochaines consultations</h2></div>
                <Link href="/agenda" className="text-sm font-medium text-teal-700 hover:text-teal-900">Voir l’agenda</Link>
              </div>
              {agendaItems.length === 0 ? <p className="p-8 text-center text-sm text-slate-500">Aucun rendez-vous planifié aujourd’hui.</p> : (
                <div className="divide-y divide-slate-100">
                  {agendaItems.slice(0, 5).map((item) => (
                    <Link key={item.id} href={`/patients/${item.patient_id}`} className="flex items-center justify-between gap-3 px-5 py-3.5 transition-colors hover:bg-slate-50">
                      <div className="min-w-0"><p className="truncate text-sm font-semibold text-slate-900">{item.patient_nom}</p><p className="truncate text-xs text-slate-500">{item.acte_nom || 'Consultation'} · {item.praticien_nom}</p></div>
                      <div className="shrink-0 text-right"><p className="text-sm font-semibold text-slate-800">{new Date(item.date_heure_debut).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}</p>{item.consentement_manquant && <p className="mt-0.5 text-[11px] font-medium text-amber-700">Consentement requis</p>}</div>
                    </Link>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="rounded-2xl border-slate-200 bg-white shadow-sm">
            <CardContent className="p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal-700">À traiter</p><h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-950">File opérationnelle</h2>
              <div className="mt-4 space-y-3">
                <Link href="/agenda" className="flex items-center justify-between rounded-xl border border-slate-200 p-3 transition-colors hover:border-teal-200 hover:bg-teal-50"><span className="text-sm text-slate-700">Demandes de rendez-vous en attente</span><span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-800">{pendingBookings}</span></Link>
                <Link href="/social" className="flex items-center justify-between rounded-xl border border-slate-200 p-3 transition-colors hover:border-teal-200 hover:bg-teal-50"><span className="text-sm text-slate-700">Demandes de rappel à rappeler</span><span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-800">{pendingCallbacks}</span></Link>
                <Link href="/dossiers" className="flex items-center justify-between rounded-xl border border-slate-200 p-3 transition-colors hover:border-teal-200 hover:bg-teal-50"><span className="text-sm text-slate-700">Consentements à signer aujourd’hui</span><span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-800">{stats.missingConsent}</span></Link>
                <Link href="/clinical-ops" className="flex items-center justify-between rounded-xl border border-slate-200 p-3 transition-colors hover:border-teal-200 hover:bg-teal-50"><span className="text-sm text-slate-700">Suivis post-acte à réaliser sous 7 jours</span><span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-800">{dueFollowups}</span></Link>
                <div className="rounded-xl border border-slate-200 p-3"><div className="flex items-center justify-between gap-3"><span className="text-sm text-slate-700">Tâches qui vous sont attribuées</span><span className="rounded-full bg-teal-100 px-2.5 py-1 text-xs font-semibold text-teal-800">{assignedTasks.length}</span></div>{assignedTasks.length > 0 && <div className="mt-2 space-y-1.5 border-t border-slate-100 pt-2">{assignedTasks.slice(0, 3).map((task) => <p key={task.id} className="truncate text-xs font-medium text-slate-600">{task.titre} <span className="font-normal text-slate-400">· {task.statut.replace('_', ' ')}</span></p>)}</div>}</div>
              </div>
            </CardContent>
          </Card>
        </section>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
          <Card className="overflow-hidden rounded-2xl border-emerald-100 bg-gradient-to-br from-emerald-50 via-white to-cyan-50 shadow-sm">
            <CardContent className="p-6 sm:p-7">
              <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
                <div>
                  <div className="flex items-center gap-2 text-sm font-semibold text-emerald-900">
                    <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                    État opérationnel
                  </div>
                  <p className="mt-3 max-w-xl text-sm leading-6 text-slate-600">
                    Les indicateurs affichés sont issus des modules Agenda, Stock, Facturation et Social CRM. Utilisez les cartes ci-dessus pour accéder directement à l’action utile.
                  </p>
                </div>
                <div className="rounded-xl bg-white/80 px-4 py-3 text-right shadow-sm ring-1 ring-emerald-100">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-slate-400">Priorité du jour</p>
                  <p className="mt-1 text-sm font-semibold text-emerald-800">
                    {stats.stockAlerts > 0 ? 'Vérifier le stock' : stats.unpaidInvoices > 0 ? 'Suivre les règlements' : 'Tout est sous contrôle'}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
          <PointageWidget />
        </div>

        <section className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <Card className="rounded-2xl border-teal-100 bg-gradient-to-br from-teal-50 via-white to-white shadow-sm">
            <CardContent className="p-5">
              <div className="flex items-start gap-3"><div className="rounded-xl bg-teal-100 p-2 text-teal-700"><Sparkles className="h-5 w-5" /></div><div><p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal-700">Priorités métier</p><h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-950">Recommandations actionnables</h2></div></div>
              {recommendations.length === 0 ? <p className="mt-5 rounded-xl bg-white/80 p-4 text-sm text-slate-600">Aucune priorité urgente détectée dans les données actuellement disponibles.</p> : <div className="mt-4 space-y-2">{recommendations.map((item) => <Link key={item.label} href={item.href} className="block rounded-xl border border-teal-100 bg-white p-3 transition-colors hover:border-teal-300 hover:bg-teal-50"><p className="text-sm font-semibold text-slate-900">{item.label}</p><p className="mt-1 text-xs text-slate-500">{item.detail}</p></Link>)}</div>}
            </CardContent>
          </Card>
          <Card className="rounded-2xl border-slate-200 bg-white shadow-sm">
            <CardContent className="p-5"><p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal-700">Activité récente</p><h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-950">Événements disponibles</h2>
              {recentActivity.length === 0 ? <p className="mt-5 rounded-xl bg-slate-50 p-4 text-sm text-slate-500">Aucun événement récent accessible pour votre rôle, ou aucune action financière récente n’a été enregistrée.</p> : <div className="mt-4 space-y-3">{recentActivity.map((item) => <div key={item.id} className="flex items-start justify-between gap-3 border-b border-slate-100 pb-3 last:border-0 last:pb-0"><div><p className="text-sm font-medium text-slate-800">{item.action} · {item.entite_type}</p><p className="mt-1 text-xs text-slate-500">{item.modifie_par_nom || 'Utilisateur clinique'}</p></div><time className="shrink-0 text-xs text-slate-400">{new Date(item.created_at).toLocaleDateString('fr-FR')}</time></div>)}</div>}
            </CardContent>
          </Card>
        </section>

        <Card className="rounded-2xl border-slate-200/80 bg-white shadow-sm">
          <CardContent className="p-6">
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">Accès rapide</p>
                <h2 className="mt-1 text-xl font-semibold tracking-tight text-[#071a3b]">Passer de l’indicateur à l’action</h2>
              </div>
              <p className="text-sm text-slate-500">Les raccourcis conservent les routes existantes.</p>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
              {[
                { href: '/agenda', label: 'Agenda', icon: Calendar },
                { href: '/patients', label: 'Patients', icon: Users },
                { href: '/invoices', label: 'Factures', icon: FileText },
                { href: '/stock', label: 'Stock', icon: AlertCircle },
              ].map(({ href, label, icon: Icon }) => (
                <Link href={href} key={href} className="flex items-center justify-between rounded-xl border border-slate-200 px-4 py-3 text-sm font-medium text-slate-700 transition-colors hover:border-blue-200 hover:bg-blue-50 hover:text-blue-800">
                  <span className="flex items-center gap-3"><Icon className="h-4 w-4 text-blue-600" />{label}</span>
                  <ArrowUpRight className="h-4 w-4 text-slate-300" />
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
