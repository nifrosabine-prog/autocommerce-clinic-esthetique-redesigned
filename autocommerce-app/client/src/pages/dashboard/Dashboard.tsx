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
  TrendingUp,
  Users,
} from 'lucide-react';
import { Link } from 'wouter';
import { PointageWidget } from '@/components/dashboard/PointageWidget';
import { useTranslation } from 'react-i18next';

interface DashboardStats {
  todayAppointments: number;
  stockAlerts: number;
  unpaidInvoices: number;
  socialMessages: number;
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
    labelKey: 'dashboard.today_appointments',
    helperKey: 'dashboard.today_appointments_helper',
    icon: Calendar,
    accent: 'bg-blue-50 text-blue-700',
    href: '/agenda',
  },
  {
    key: 'stockAlerts' as const,
    labelKey: 'dashboard.stock_alerts',
    helperKey: 'dashboard.stock_alerts_helper',
    icon: PackageSearch,
    accent: 'bg-amber-50 text-amber-700',
    href: '/stock',
  },
  {
    key: 'unpaidInvoices' as const,
    labelKey: 'dashboard.unpaid_invoices',
    helperKey: 'dashboard.unpaid_invoices_helper',
    icon: DollarSign,
    accent: 'bg-emerald-50 text-emerald-700',
    href: '/invoices',
  },
  {
    key: 'socialMessages' as const,
    labelKey: 'dashboard.social_messages',
    helperKey: 'dashboard.social_messages_helper',
    icon: MessageCircle,
    accent: 'bg-violet-50 text-violet-700',
    href: '/social',
  },
];

export default function Dashboard() {
  const { user } = useAuth();
  const { t, i18n } = useTranslation();
  const canManageStock = ['admin', 'directrice', 'assistante'].includes(user?.role || '');
  const [isLoading, setIsLoading] = useState(true);
  const [stats, setStats] = useState<DashboardStats>({
    todayAppointments: 0,
    stockAlerts: 0,
    unpaidInvoices: 0,
    socialMessages: 0,
  });

  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        setIsLoading(true);
        const today = todayLocalDate();
        const [agendaRes, stockRes, facturesRes, socialRes] = await Promise.allSettled([
          api.get(`/agenda?date_debut=${today}T00:00:00&date_fin=${today}T23:59:59&vue=jour`),
          canManageStock ? api.get('/injectables/stock') : Promise.resolve({ data: {} }),
          api.get('/factures'),
          api.get('/social/analytics'),
        ]);

        let todayAppointments = 0;
        if (agendaRes.status === 'fulfilled' && Array.isArray(agendaRes.value.data)) {
          todayAppointments = agendaRes.value.data.length;
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

        setStats({ todayAppointments, stockAlerts, unpaidInvoices, socialMessages });
      } finally {
        setIsLoading(false);
      }
    };

    loadDashboardData();
  }, [canManageStock]);

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
  const today = new Intl.DateTimeFormat(i18n.resolvedLanguage || 'fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(new Date());

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
                {t('dashboard.clinical_pilot')}
              </div>
              <h1 className="max-w-2xl text-3xl font-semibold tracking-tight sm:text-4xl">
                {t('dashboard.greeting', { name: displayName || t('dashboard.you') })}.
              </h1>
              <p className="mt-2 max-w-xl text-sm leading-6 text-blue-100/75">
                {t('dashboard.subtitle')}
              </p>
            </div>
            <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/10 px-4 py-3 backdrop-blur-sm">
              <Clock3 className="h-5 w-5 text-cyan-200" />
              <div>
                <p className="text-[11px] uppercase tracking-[0.14em] text-blue-100/60">{t('dashboard.today')}</p>
                <p className="mt-1 text-sm font-medium capitalize">{today}</p>
              </div>
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {statCards.filter((item) => canManageStock || item.key !== 'stockAlerts').map((item) => {
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
                    <p className="mt-5 text-sm font-medium text-slate-600">{t(item.labelKey)}</p>
                    <div className="mt-1 flex items-end justify-between gap-3">
                      <p className="text-3xl font-semibold tracking-tight text-[#071a3b]">{value}</p>
                      <TrendingUp className="mb-1 h-4 w-4 text-emerald-500" />
                    </div>
                    <p className="mt-1 text-xs text-slate-400">{t(item.helperKey)}</p>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </section>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
          <Card className="overflow-hidden rounded-2xl border-emerald-100 bg-gradient-to-br from-emerald-50 via-white to-cyan-50 shadow-sm">
            <CardContent className="p-6 sm:p-7">
              <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
                <div>
                  <div className="flex items-center gap-2 text-sm font-semibold text-emerald-900">
                    <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                    {t('dashboard.operational_status')}
                  </div>
                  <p className="mt-3 max-w-xl text-sm leading-6 text-slate-600">
                    {t('dashboard.operational_description')}
                  </p>
                </div>
                <div className="rounded-xl bg-white/80 px-4 py-3 text-right shadow-sm ring-1 ring-emerald-100">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-slate-400">{t('dashboard.daily_priority')}</p>
                  <p className="mt-1 text-sm font-semibold text-emerald-800">
                    {stats.stockAlerts > 0 ? t('dashboard.check_stock') : stats.unpaidInvoices > 0 ? t('dashboard.follow_payments') : t('dashboard.all_under_control')}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
          <PointageWidget />
        </div>

        <Card className="rounded-2xl border-slate-200/80 bg-white shadow-sm">
          <CardContent className="p-6">
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">{t('dashboard.quick_access')}</p>
                <h2 className="mt-1 text-xl font-semibold tracking-tight text-[#071a3b]">{t('dashboard.from_metric_to_action')}</h2>
              </div>
              <p className="text-sm text-slate-500">{t('dashboard.shortcuts_description')}</p>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
              {[
                { href: '/agenda', labelKey: 'nav.agenda', icon: Calendar },
                { href: '/patients', labelKey: 'nav.patients', icon: Users },
                { href: '/invoices', labelKey: 'nav.invoices', icon: FileText },
                ...(canManageStock ? [{ href: '/stock', labelKey: 'nav.stock', icon: AlertCircle }] : []),
              ].map(({ href, labelKey, icon: Icon }) => (
                <Link href={href} key={href} className="flex items-center justify-between rounded-xl border border-slate-200 px-4 py-3 text-sm font-medium text-slate-700 transition-colors hover:border-blue-200 hover:bg-blue-50 hover:text-blue-800">
                  <span className="flex items-center gap-3"><Icon className="h-4 w-4 text-blue-600" />{t(labelKey)}</span>
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
