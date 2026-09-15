import { useEffect, useState } from 'react';
import { Link } from 'wouter';
import { ArrowUpRight, BriefcaseBusiness, RefreshCw } from 'lucide-react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { workspaceApi, type WorkspaceCard } from '@/lib/api';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

const roleLabels: Record<string, string> = { assistante: 'roleAssistante', medecin: 'roleMedecin', estheticienne: 'roleEstheticienne', prestataire: 'rolePrestataire', directrice: 'roleDirectrice', admin: 'roleAdmin' };

export default function WorkspacePage() {
  const { t } = useTranslation();
  const [cards, setCards] = useState<WorkspaceCard[]>([]);
  const [role, setRole] = useState('');
  const [loading, setLoading] = useState(true);
  const load = async () => {
    setLoading(true);
    try { const response = await workspaceApi.get(); setCards(response.data.cards || []); setRole(response.data.role); }
    catch (error: any) { toast.error(error.response?.data?.detail || t('workspace.loadError')); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);
  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div><p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">{t('workspace.title')}</p><h1 className="mt-1 text-3xl font-bold">{role && roleLabels[role] ? t(`workspace.${roleLabels[role]}`) : t('workspace.teamFallback')}</h1><p className="mt-2 text-muted-foreground">{t('workspace.subtitle')}</p></div>
          <Button variant="outline" onClick={() => void load()} disabled={loading}><RefreshCw className="mr-2 h-4 w-4" />{t('workspace.refresh')}</Button>
        </div>
        {loading ? <div className="flex justify-center py-16"><Spinner /></div> : <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{cards.map((card) => <Card key={card.key} className="border-slate-200 shadow-sm"><CardHeader><CardTitle className="flex items-center justify-between gap-3 text-lg"><span className="flex items-center gap-2"><BriefcaseBusiness className="h-5 w-5 text-primary" />{card.title}</span><span className="text-3xl font-bold text-primary">{card.count}</span></CardTitle></CardHeader><CardContent><p className="text-sm text-muted-foreground">{card.description}</p><Link href={card.href}><Button className="mt-5 w-full justify-between">{card.next_action}<ArrowUpRight className="h-4 w-4" /></Button></Link></CardContent></Card>)}</div>}
        <Card className="border-blue-100 bg-blue-50/40"><CardContent className="p-5"><p className="font-medium">{t('workspace.clinicalContext')}</p><p className="mt-1 text-sm text-muted-foreground">{t('workspace.clinicalContextText')}</p></CardContent></Card>
      </div>
    </DashboardLayout>
  );
}
