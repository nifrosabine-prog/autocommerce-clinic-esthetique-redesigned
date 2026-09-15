import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { Calendar as CalendarIcon, Download, Search, Clock, User } from 'lucide-react';
import { toast } from 'sonner';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';

interface User {
  id: number;
  nom: string;
  prenom: string;
  role: string;
}

interface PointageDetail {
  date: string;
  debut: string;
  fin: string;
  duree_minutes: number;
}

interface ReportData {
  utilisateur_id: number;
  nom_complet: string;
  total_minutes: number;
  details: PointageDetail[];
}

interface AttendanceSummary {
  aujourd_hui_minutes: number;
  semaine_minutes: number;
  mois_minutes: number;
  pointages_mois: number;
}

export default function ReportingRH() {
  const { t, i18n } = useTranslation();
  const [isLoading, setIsLoading] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string>('');
  const [dateDebut, setDateDebut] = useState<string>(() => {
    const d = new Date();
    d.setDate(1); // 1er du mois
    return d.toISOString().split('T')[0];
  });
  const [dateFin, setDateFin] = useState<string>(() => {
    return new Date().toISOString().split('T')[0];
  });
  const [report, setReport] = useState<ReportData | null>(null);
  const [summary, setSummary] = useState<AttendanceSummary | null>(null);

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      const res = await api.get('/users');
      setUsers(res.data);
      if (res.data.length > 0) setSelectedUserId(res.data[0].id.toString());
    } catch (err) {
      toast.error(t('reportingRH.loadEmployeesError'));
    }
  };

  const handleGenerateReport = async () => {
    if (!selectedUserId) {
      toast.error(t('reportingRH.selectEmployeeError'));
      return;
    }
    setIsLoading(true);
    try {
      const [reportRes, summaryRes] = await Promise.all([
        api.get('/pointage/admin/rapport', { params: { utilisateur_id: selectedUserId, date_debut: dateDebut, date_fin: dateFin } }),
        api.get('/pointage/admin/synthese', { params: { utilisateur_id: selectedUserId } }),
      ]);
      setReport(reportRes.data);
      setSummary(summaryRes.data);
    } catch (err) {
      toast.error(t('reportingRH.generateError'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownloadCsv = async () => {
    if (!selectedUserId) {
      toast.error(t('reportingRH.selectEmployeeError'));
      return;
    }
    try {
      const response = await api.get('/pointage/admin/rapport.csv', {
        params: { utilisateur_id: selectedUserId, date_debut: dateDebut, date_fin: dateFin },
        responseType: 'blob',
      });
      const contentDisposition = response.headers['content-disposition'] as string | undefined;
      const filename = contentDisposition?.match(/filename="?([^";]+)"?/i)?.[1] || `reporting-rh-${selectedUserId}.csv`;
      const url = URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      toast.success(t('reportingRH.csvDownloaded'));
    } catch (err) {
      toast.error(t('reportingRH.csvError'));
    }
  };

  const formatDuration = (minutes: number) => {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return t('reportingRH.durationFormat', { hours: h, minutes: m.toString().padStart(2, '0') });
  };

  return (
    <DashboardLayout>
      <div className="mx-auto max-w-[1500px] space-y-6 pb-8">
        <div className="relative overflow-hidden rounded-[1.5rem] bg-[#071a3b] px-6 py-7 text-white shadow-[0_20px_60px_-28px_rgba(7,26,59,0.7)] sm:px-8 sm:py-9">
          <div className="absolute -right-16 -top-20 h-64 w-64 rounded-full bg-cyan-400/20 blur-3xl" />
          <div className="relative">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-cyan-200">{t('reportingRH.heroEyebrow')}</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">{t('reportingRH.title')}</h1>
            <p className="mt-2 max-w-xl text-sm leading-6 text-blue-100/75">{t('reportingRH.subtitle')}</p>
          </div>
        </div>

        <Card className="rounded-2xl border-slate-200/80 bg-white shadow-sm">
          <CardHeader>
            <CardTitle className="text-lg text-[#071a3b]">{t('reportingRH.parameters')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
              <div className="space-y-2">
                <Label htmlFor="user">{t('reportingRH.employee')}</Label>
                <select 
                  id="user"
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  value={selectedUserId}
                  onChange={(e) => setSelectedUserId(e.target.value)}
                >
                  <option value="">{t('reportingRH.select')}</option>
                  {users.map(u => (
                    <option key={u.id} value={u.id}>{u.prenom} {u.nom} ({u.role})</option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="start">{t('reportingRH.from')}</Label>
                <Input id="start" type="date" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="end">{t('reportingRH.to')}</Label>
                <Input id="end" type="date" value={dateFin} onChange={(e) => setDateFin(e.target.value)} />
              </div>
              <div className="flex gap-2">
                <Button onClick={handleGenerateReport} disabled={isLoading}>
                  {isLoading ? <Spinner className="w-4 h-4 mr-2" /> : <Search className="w-4 h-4 mr-2" />}
                  {t('reportingRH.generate')}
                </Button>
                <Button variant="outline" onClick={handleDownloadCsv} disabled={!selectedUserId} title={t('reportingRH.downloadTitle')}>
                  <Download className="w-4 h-4 mr-2" />
                  CSV
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {report && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
              <Card className="rounded-2xl border-blue-100 bg-blue-50/70 shadow-sm">
                <CardContent className="pt-6">
                  <div className="flex items-center gap-4">
                    <div className="p-3 bg-primary/10 rounded-full">
                      <User className="w-6 h-6 text-primary" />
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">{t('reportingRH.employee')}</p>
                      <p className="text-xl font-bold">{report.nom_complet}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Card className="rounded-2xl border-emerald-100 bg-emerald-50/70 shadow-sm">
                <CardContent className="pt-6">
                  <div className="flex items-center gap-4">
                    <div className="p-3 bg-green-100 rounded-full">
                      <Clock className="w-6 h-6 text-green-700" />
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">{t('reportingRH.totalHours')}</p>
                      <p className="text-xl font-bold text-green-700">{formatDuration(report.total_minutes)}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Card className="rounded-2xl border-amber-100 bg-amber-50/70 shadow-sm">
                <CardContent className="pt-6">
                  <div className="flex items-center gap-4"><div className="p-3 bg-amber-100 rounded-full"><Clock className="w-6 h-6 text-amber-700" /></div><div><p className="text-sm text-muted-foreground">{t('reportingRH.today')}</p><p className="text-xl font-bold text-amber-700">{formatDuration(summary?.aujourd_hui_minutes || 0)}</p></div></div>
                </CardContent>
              </Card>
              <Card className="rounded-2xl border-cyan-100 bg-cyan-50/70 shadow-sm">
                <CardContent className="pt-6">
                  <div className="flex items-center gap-4">
                    <div className="p-3 bg-blue-100 rounded-full">
                      <CalendarIcon className="w-6 h-6 text-blue-700" />
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">{t('reportingRH.period')}</p>
                      <p className="text-sm font-bold text-blue-700">{t('reportingRH.periodRange', { start: new Date(dateDebut).toLocaleDateString(i18n.language), end: new Date(dateFin).toLocaleDateString(i18n.language) })}</p>
                      <p className="mt-1 text-xs text-muted-foreground">{t('reportingRH.summaryRange', { week: formatDuration(summary?.semaine_minutes || 0), month: formatDuration(summary?.mois_minutes || 0) })}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            <Card className="rounded-2xl border-slate-200/80 bg-white shadow-sm">
              <CardHeader>
                <CardTitle className="text-lg text-[#071a3b]">{t('reportingRH.dailyDetail')}</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('reportingRH.date')}</TableHead>
                      <TableHead>{t('reportingRH.arrival')}</TableHead>
                      <TableHead>{t('reportingRH.departure')}</TableHead>
                      <TableHead className="text-right">{t('reportingRH.duration')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {report.details.map((d, i) => (
                      <TableRow key={i}>
                        <TableCell className="font-medium">{new Date(d.date).toLocaleDateString(i18n.language, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</TableCell>
                        <TableCell>{new Date(d.debut).toLocaleTimeString(i18n.language, { hour: '2-digit', minute: '2-digit' })}</TableCell>
                        <TableCell>{d.fin ? new Date(d.fin).toLocaleTimeString(i18n.language, { hour: '2-digit', minute: '2-digit' }) : '-'}</TableCell>
                        <TableCell className="text-right font-mono">{formatDuration(d.duree_minutes)}</TableCell>
                      </TableRow>
                    ))}
                    {report.details.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={4} className="text-center py-8 text-muted-foreground">
                          {t('reportingRH.noAttendance')}
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
