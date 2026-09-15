import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'wouter';
import { Activity, AlertTriangle, Building2, CheckCircle2, CreditCard, Database, Gauge, LogOut, RefreshCw, Server, ShieldCheck, Users, XCircle } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Spinner } from '@/components/ui/spinner';

interface DashboardData {
  kpis: { clinics_total: number; clinics_active: number; users_total: number; revenue_paid: number; subscriptions_total: number };
  clinics: Clinic[];
  alerts: { type: string; severity: string; message: string }[];
  generated_at: string;
}

interface Clinic {
  clinic_id: number;
  name: string;
  status: string;
  plan?: string | null;
  users: number;
  active_users: number;
  patients: number;
  revenue: number;
  last_access?: string | null;
  subscription_id?: number | null;
  expires_at?: string | null;
}

interface Subscription {
  id: number;
  clinic_id: number;
  clinic_name: string;
  plan: string;
  status: string;
  expires_at?: string | null;
  monthly_amount: number;
  max_users: number;
}

interface HealthData {
  checked_at: string;
  api: { status: string; latency_ms?: number | null };
  database: { status: string; latency_ms?: number | null; detail?: string };
  redis: { status: string; latency_ms?: number | null; detail?: string };
  celery: { status: string; workers: number; worker_names: string[]; detail?: string };
}

interface PerformanceData {
  window: string;
  requests_proxy: number;
  requests_total?: number;
  requests_per_minute?: number;
  active_users: number;
  average_response_ms?: number | null;
  error_rate_4xx?: number | null;
  error_rate_5xx?: number | null;
  note?: string;
}

const formatMoney = (value: number, language: string) => `${Number(value || 0).toLocaleString(language, { minimumFractionDigits: 3 })} DT`;
const formatDate = (value: string | null | undefined, language: string, fallback: string) => value ? new Date(value).toLocaleString(language) : fallback;

function StatusBadge({ status, label }: { status: string; label: string }) {
  const ok = status === 'ok' || status === 'active' || status === 'trial';
  const warning = status === 'degraded' || status === 'past_due' || status === 'unconfigured';
  return <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${ok ? 'bg-emerald-100 text-emerald-800' : warning ? 'bg-amber-100 text-amber-800' : 'bg-rose-100 text-rose-800'}`}>{label}</span>;
}

export default function SuperAdminDashboard() {
  const { t, i18n } = useTranslation();
  const { user, logout } = useAuth();
  const [, setLocation] = useLocation();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [performance, setPerformance] = useState<PerformanceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [updatingId, setUpdatingId] = useState<number | null>(null);

  const load = useCallback(async (background = false) => {
    background ? setRefreshing(true) : setLoading(true);
    try {
      const [dashboardResponse, subscriptionsResponse, healthResponse, performanceResponse] = await Promise.all([
        api.get<DashboardData>('/super-admin/dashboard'),
        api.get<Subscription[]>('/super-admin/subscriptions'),
        api.get<HealthData>('/super-admin/health'),
        api.get<PerformanceData>('/super-admin/performance'),
      ]);
      setDashboard(dashboardResponse.data);
      setSubscriptions(subscriptionsResponse.data);
      setHealth(healthResponse.data);
      setPerformance(performanceResponse.data);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || t('superAdmin.loadError'));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const subscriptionByClinic = useMemo(() => new Map(subscriptions.map(item => [item.clinic_id, item])), [subscriptions]);

  const updateStatus = async (subscription: Subscription, status: string) => {
    setUpdatingId(subscription.id);
    try {
      await api.patch(`/super-admin/subscriptions/${subscription.id}`, { status });
      toast.success(status === 'active' ? t('superAdmin.subscriptionReactivated') : t('superAdmin.subscriptionUpdated'));
      await load(true);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || t('superAdmin.updateError'));
    } finally {
      setUpdatingId(null);
    }
  };

  const statusLabel = (status: string) => {
    switch (status) {
      case 'ok': return t('superAdmin.statusOk');
      case 'active': return t('superAdmin.statusActive');
      case 'trial': return t('superAdmin.statusTrial');
      case 'degraded': return t('superAdmin.statusDegraded');
      case 'past_due': return t('superAdmin.statusPastDue');
      case 'unconfigured': return t('superAdmin.statusUnconfigured');
      case 'suspended': return t('superAdmin.statusSuspended');
      default: return status;
    }
  };

  if (loading) return <div className="min-h-screen grid place-items-center bg-slate-950 text-white"><Spinner /></div>;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-white/10 bg-slate-900/90 px-4 py-4 backdrop-blur sm:px-6">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <div className="flex items-center gap-3"><div className="rounded-xl bg-cyan-400/15 p-2 text-cyan-300"><ShieldCheck className="h-6 w-6" /></div><div><p className="text-xs uppercase tracking-[0.25em] text-cyan-300">{t('superAdmin.controlPlane')}</p><h1 className="text-xl font-semibold">{t('superAdmin.consoleTitle')}</h1></div></div>
          <div className="flex items-center gap-3"><span className="hidden text-sm text-slate-400 md:inline">{t('superAdmin.securedSession', { name: `${user?.prenom || ''} ${user?.nom || ''}`.trim() })}</span><Button variant="outline" className="border-white/15 bg-transparent text-slate-100 hover:bg-white/10" onClick={() => { logout(); setLocation('/login'); }}><LogOut className="mr-2 h-4 w-4" />{t('superAdmin.logout')}</Button></div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-8 px-4 py-6 sm:px-6 sm:py-8">
        <section className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-sm text-slate-400">{t('superAdmin.globalView')}</p><h2 className="mt-1 text-3xl font-semibold tracking-tight">{t('superAdmin.operationsTitle')}</h2></div><Button variant="outline" className="border-white/15 bg-transparent text-slate-100 hover:bg-white/10" onClick={() => void load(true)} disabled={refreshing}><RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />{t('superAdmin.refresh')}</Button></section>

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          {[
            { label: t('superAdmin.activeClinics'), value: dashboard?.kpis.clinics_active ?? 0, icon: Building2, color: 'text-cyan-300' },
            { label: t('superAdmin.userAccounts'), value: dashboard?.kpis.users_total ?? 0, icon: Users, color: 'text-violet-300' },
            { label: t('superAdmin.collectedRevenue'), value: formatMoney(dashboard?.kpis.revenue_paid ?? 0, i18n.language), icon: CreditCard, color: 'text-emerald-300' },
            { label: t('superAdmin.subscriptions'), value: dashboard?.kpis.subscriptions_total ?? 0, icon: Activity, color: 'text-amber-300' },
            { label: t('superAdmin.users24h'), value: performance?.active_users ?? 0, icon: Gauge, color: 'text-pink-300' },
          ].map(item => { const Icon = item.icon; return <Card key={item.label} className="border-white/10 bg-slate-900 text-slate-100 shadow-2xl shadow-black/20"><CardContent className="p-5"><Icon className={`mb-5 h-5 w-5 ${item.color}`} /><p className="text-sm text-slate-400">{item.label}</p><p className="mt-1 text-2xl font-semibold">{item.value}</p></CardContent></Card>; })}
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
          <Card className="border-white/10 bg-slate-900 text-slate-100"><CardHeader><CardTitle className="flex items-center gap-2"><Building2 className="h-5 w-5 text-cyan-300" />{t('superAdmin.clinicAccounts')}</CardTitle></CardHeader><CardContent><div className="space-y-3 md:hidden">{(dashboard?.clinics ?? []).map(clinic => <div key={clinic.clinic_id} className="rounded-xl border border-white/10 bg-white/[0.03] p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-medium">{clinic.name}</p><p className="text-xs text-slate-500">{t('superAdmin.tenant')} #{clinic.clinic_id}</p></div><StatusBadge status={clinic.status} label={statusLabel(clinic.status)} /></div><dl className="mt-4 grid grid-cols-2 gap-3 text-sm"><div><dt className="text-xs text-slate-500">{t('superAdmin.plan')}</dt><dd className="mt-1 text-slate-200">{clinic.plan || '—'}</dd></div><div><dt className="text-xs text-slate-500">{t('superAdmin.users')}</dt><dd className="mt-1 text-slate-200">{clinic.active_users}/{clinic.users}</dd></div><div><dt className="text-xs text-slate-500">{t('superAdmin.patients')}</dt><dd className="mt-1 text-slate-200">{clinic.patients}</dd></div><div><dt className="text-xs text-slate-500">{t('superAdmin.revenue')}</dt><dd className="mt-1 text-slate-200">{formatMoney(clinic.revenue, i18n.language)}</dd></div></dl><p className="mt-3 text-xs text-slate-500">{t('superAdmin.lastAccess')} : {formatDate(clinic.last_access, i18n.language, t('superAdmin.never'))}</p></div>)}</div><div className="hidden overflow-x-auto md:block"><table className="w-full min-w-[720px] text-left text-sm"><thead className="border-b border-white/10 text-xs uppercase tracking-wide text-slate-500"><tr><th className="pb-3">{t('superAdmin.clinic')}</th><th className="pb-3">{t('superAdmin.status')}</th><th className="pb-3">{t('superAdmin.plan')}</th><th className="pb-3">{t('superAdmin.users')}</th><th className="pb-3">{t('superAdmin.patients')}</th><th className="pb-3">{t('superAdmin.revenue')}</th><th className="pb-3">{t('superAdmin.lastAccess')}</th></tr></thead><tbody>{(dashboard?.clinics ?? []).map(clinic => <tr key={clinic.clinic_id} className="border-b border-white/5"><td className="py-3 font-medium">{clinic.name}<span className="ml-2 text-xs text-slate-500">#{clinic.clinic_id}</span></td><td className="py-3"><StatusBadge status={clinic.status} label={statusLabel(clinic.status)} /></td><td className="py-3 text-slate-300">{clinic.plan || '—'}</td><td className="py-3">{clinic.active_users}/{clinic.users}</td><td className="py-3">{clinic.patients}</td><td className="py-3">{formatMoney(clinic.revenue, i18n.language)}</td><td className="py-3 text-slate-400">{formatDate(clinic.last_access, i18n.language, t('superAdmin.never'))}</td></tr>)}</tbody></table></div></CardContent></Card>

          <Card className="border-white/10 bg-slate-900 text-slate-100"><CardHeader><CardTitle className="flex items-center gap-2"><Server className="h-5 w-5 text-violet-300" />{t('superAdmin.technicalHealth')}</CardTitle></CardHeader><CardContent className="space-y-3">{health ? [
            { label: 'API', data: health.api, icon: Activity },
            { label: 'PostgreSQL', data: health.database, icon: Database },
            { label: 'Redis', data: health.redis, icon: Server },
            { label: t('superAdmin.celeryWorkers', { count: health.celery.workers }), data: health.celery, icon: Gauge },
          ].map(item => { const Icon = item.icon; return <div key={item.label} className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3"><span className="flex items-center gap-3"><Icon className="h-4 w-4 text-slate-400" /><span>{item.label}</span></span><span className="flex items-center gap-3"><span className="text-xs text-slate-500">{(item.data as { latency_ms?: number | null }).latency_ms != null ? `${(item.data as { latency_ms?: number | null }).latency_ms} ms` : ''}</span><StatusBadge status={item.data.status} label={statusLabel(item.data.status)} /></span></div>; }) : <p className="text-sm text-slate-400">{t('superAdmin.healthUnavailable')}</p>}</CardContent></Card>
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
          <Card className="border-white/10 bg-slate-900 text-slate-100"><CardHeader><CardTitle className="flex items-center gap-2"><CreditCard className="h-5 w-5 text-emerald-300" />{t('superAdmin.subscriptionsDecisions')}</CardTitle></CardHeader><CardContent><div className="space-y-3">{subscriptions.map(subscription => <div key={subscription.id} className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-white/10 bg-white/[0.03] p-4"><div><p className="font-medium">{subscription.clinic_name}</p><p className="text-sm text-slate-400">{t('superAdmin.subscriptionLine', { plan: subscription.plan, amount: formatMoney(subscription.monthly_amount, i18n.language), users: subscription.max_users })}</p><p className="mt-1 text-xs text-slate-500">{t('superAdmin.expiration')} : {formatDate(subscription.expires_at, i18n.language, t('superAdmin.never'))}</p></div><div className="flex items-center gap-3"><StatusBadge status={subscription.status} label={statusLabel(subscription.status)} /><Button size="sm" variant="outline" className="border-white/15 bg-transparent text-slate-100 hover:bg-white/10" disabled={updatingId === subscription.id} onClick={() => void updateStatus(subscription, subscription.status === 'active' ? 'suspended' : 'active')}>{updatingId === subscription.id ? <Spinner className="h-4 w-4" /> : subscription.status === 'active' ? t('superAdmin.suspend') : t('superAdmin.reactivate')}</Button></div></div>)}</div>{subscriptions.length === 0 && <p className="text-sm text-slate-400">{t('superAdmin.noSubscriptions')}</p>}</CardContent></Card>

          <Card className="border-white/10 bg-slate-900 text-slate-100"><CardHeader><CardTitle className="flex items-center gap-2"><Activity className="h-5 w-5 text-pink-300" />{t('superAdmin.appPerformance')}</CardTitle></CardHeader><CardContent className="space-y-4">{performance && <><div className="grid grid-cols-3 gap-3"><div className="rounded-xl bg-white/[0.04] p-4"><p className="text-xs text-slate-500">{t('superAdmin.window')}</p><p className="mt-1 text-lg font-semibold">{performance.window}</p></div><div className="rounded-xl bg-white/[0.04] p-4"><p className="text-xs text-slate-500">{t('superAdmin.totalRequests')}</p><p className="mt-1 text-lg font-semibold">{performance.requests_total ?? performance.requests_proxy}</p></div><div className="rounded-xl bg-white/[0.04] p-4"><p className="text-xs text-slate-500">{t('superAdmin.requestsPerMin')}</p><p className="mt-1 text-lg font-semibold">{performance.requests_per_minute ?? '—'}</p></div></div><div className="space-y-2 text-sm"><div className="flex justify-between"><span className="text-slate-400">{t('superAdmin.avgLatency')}</span><span>{performance.average_response_ms == null ? '—' : `${performance.average_response_ms} ms`}</span></div><div className="flex justify-between"><span className="text-slate-400">{t('superAdmin.errors4xx')}</span><span>{performance.error_rate_4xx == null ? '—' : `${performance.error_rate_4xx}%`}</span></div><div className="flex justify-between"><span className="text-slate-400">{t('superAdmin.errors5xx')}</span><span>{performance.error_rate_5xx == null ? '—' : `${performance.error_rate_5xx}%`}</span></div></div><p className="text-xs leading-5 text-slate-500">{performance.note}</p></>}</CardContent></Card>
        </section>

        <section className="grid gap-6 lg:grid-cols-2">
          <Card className="border-white/10 bg-slate-900 text-slate-100"><CardHeader><CardTitle className="flex items-center gap-2"><AlertTriangle className="h-5 w-5 text-amber-300" />{t('superAdmin.decisionAlerts')}</CardTitle></CardHeader><CardContent className="space-y-3">{(dashboard?.alerts ?? []).map((alert, index) => <div key={`${alert.type}-${index}`} className="flex gap-3 rounded-xl border border-amber-300/20 bg-amber-300/10 p-4 text-sm text-amber-100"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{alert.message}</div>)}{dashboard?.alerts.length === 0 && <div className="flex items-center gap-3 rounded-xl border border-emerald-300/20 bg-emerald-300/10 p-4 text-sm text-emerald-100"><CheckCircle2 className="h-4 w-4" />{t('superAdmin.noCriticalAlerts')}</div>}</CardContent></Card>
          <Card className="border-white/10 bg-slate-900 text-slate-100"><CardHeader><CardTitle className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-cyan-300" />{t('superAdmin.controlScope')}</CardTitle></CardHeader><CardContent className="space-y-2 text-sm text-slate-400"><p>{t('superAdmin.controlScopeText1')}</p><p>{t('superAdmin.controlScopeText2')}</p><p>{t('superAdmin.lastCollection')} : {formatDate(dashboard?.generated_at, i18n.language, t('superAdmin.never'))}</p></CardContent></Card>
        </section>
      </main>
    </div>
  );
}
