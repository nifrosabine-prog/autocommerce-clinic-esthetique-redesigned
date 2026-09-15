import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { Beaker, Calendar, Package, Plus } from 'lucide-react';
import { toast } from 'sonner';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

type Labo = { id: number; nom: string; contact?: string };
type Delegue = { id: number; nom_complet: string; labo_id: number };

export default function DeleguesPage() {
  const { t, i18n } = useTranslation();
  const [isLoading, setIsLoading] = useState(true);
  const [labos, setLabos] = useState<Labo[]>([]);
  const [visites, setVisites] = useState<any[]>([]);
  const [delegues, setDelegues] = useState<Delegue[]>([]);
  const [laboOpen, setLaboOpen] = useState(false);
  const [visiteOpen, setVisiteOpen] = useState(false);

  const loadData = async () => {
    try {
      setIsLoading(true);
      const [labosRes, visitesRes, deleguesRes] = await Promise.all([
        api.get('/delegues/labos'), api.get('/delegues/visites'), api.get('/delegues/delegues'),
      ]);
      setLabos(Array.isArray(labosRes.data) ? labosRes.data : []);
      setVisites(Array.isArray(visitesRes.data) ? visitesRes.data : []);
      setDelegues(Array.isArray(deleguesRes.data) ? deleguesRes.data : []);
    } catch { toast.error(t('delegues.loadError')); }
    finally { setIsLoading(false); }
  };
  useEffect(() => { loadData(); }, []);

  if (isLoading) return <DashboardLayout><div className="flex items-center justify-center h-96"><Spinner /></div></DashboardLayout>;
  return <DashboardLayout><div className="space-y-6">
    <div><h1 className="text-3xl font-bold">{t('delegues.title')}</h1><p className="text-muted-foreground mt-1">{t('delegues.subtitle')}</p></div>
    <Tabs defaultValue="visites">
      <TabsList><TabsTrigger value="visites"><Calendar className="w-4 h-4 mr-2" />{t('delegues.tabVisits')}</TabsTrigger><TabsTrigger value="labos"><Beaker className="w-4 h-4 mr-2" />{t('delegues.tabLabs')}</TabsTrigger></TabsList>
      <TabsContent value="visites" className="space-y-4"><Card><CardHeader className="flex flex-row items-center justify-between"><CardTitle>{t('delegues.visitsHistory')}</CardTitle><Button size="sm" onClick={() => setVisiteOpen(true)}><Calendar className="w-4 h-4 mr-2" />{t('delegues.newVisit')}</Button></CardHeader><CardContent><Table><TableHeader><TableRow><TableHead>{t('delegues.colDate')}</TableHead><TableHead>{t('delegues.colDelegate')}</TableHead><TableHead>{t('delegues.colSubject')}</TableHead><TableHead>{t('delegues.colSamples')}</TableHead></TableRow></TableHeader><TableBody>{visites.length === 0 ? <TableRow><TableCell colSpan={4} className="text-center py-8 text-muted-foreground">{t('delegues.noVisits')}</TableCell></TableRow> : visites.map(v => <TableRow key={v.id}><TableCell>{new Date(v.date).toLocaleDateString(i18n.language)}</TableCell><TableCell className="font-medium">{v.delegue}</TableCell><TableCell>{v.objet}</TableCell><TableCell>{v.echantillons ? <span className="text-xs bg-purple-100 text-purple-800 px-2 py-1 rounded"><Package className="w-3 h-3 inline mr-1" />{t('delegues.received')}</span> : '—'}</TableCell></TableRow>)}</TableBody></Table></CardContent></Card></TabsContent>
      <TabsContent value="labos" className="space-y-4"><Card><CardHeader className="flex flex-row items-center justify-between"><CardTitle>{t('delegues.labs')}</CardTitle><Button size="sm" onClick={() => setLaboOpen(true)}><Plus className="w-4 h-4 mr-2" />{t('delegues.addLab')}</Button></CardHeader><CardContent><div className="grid grid-cols-1 md:grid-cols-3 gap-4">{labos.length === 0 ? <p className="text-muted-foreground">{t('delegues.noLabs')}</p> : labos.map(l => <Card key={l.id} className="border-l-4 border-l-blue-500"><CardContent className="pt-6"><div className="font-bold text-lg">{l.nom}</div><div className="text-sm text-muted-foreground mt-1">{t('delegues.contact')} : {l.contact || t('delegues.notSpecified')}</div></CardContent></Card>)}</div></CardContent></Card></TabsContent>
    </Tabs>
    <LaboDialog open={laboOpen} onOpenChange={setLaboOpen} onCreated={loadData} />
    <VisiteDialog open={visiteOpen} onOpenChange={setVisiteOpen} delegues={delegues} onCreated={loadData} />
  </div></DashboardLayout>;
}

function LaboDialog({ open, onOpenChange, onCreated }: { open: boolean; onOpenChange: (v: boolean) => void; onCreated: () => void }) {
  const { t } = useTranslation();
  const [nom, setNom] = useState(''); const [contactNom, setContactNom] = useState(''); const [telephone, setTelephone] = useState(''); const [email, setEmail] = useState(''); const [delegueNom, setDelegueNom] = useState(''); const [deleguePrenom, setDeleguePrenom] = useState(''); const [saving, setSaving] = useState(false);
  const reset = () => { setNom(''); setContactNom(''); setTelephone(''); setEmail(''); setDelegueNom(''); setDeleguePrenom(''); };
  const submit = async (e: React.FormEvent) => { e.preventDefault(); if (!nom.trim()) return toast.error(t('delegues.labNameRequired')); setSaving(true); try { const labo = await api.post('/delegues/labos', { nom: nom.trim(), contact_nom: contactNom || undefined, telephone: telephone || undefined, email: email || undefined }); if (delegueNom.trim() && deleguePrenom.trim()) await api.post('/delegues/delegues', { labo_id: labo.data.id, nom: delegueNom.trim(), prenom: deleguePrenom.trim() }); toast.success(t('delegues.labAdded')); onOpenChange(false); reset(); onCreated(); } catch (err: any) { toast.error(err.response?.data?.detail || t('delegues.labAddError')); } finally { setSaving(false); } };
  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent><DialogHeader><DialogTitle>{t('delegues.addLabTitle')}</DialogTitle><DialogDescription>{t('delegues.addLabDesc')}</DialogDescription></DialogHeader><form onSubmit={submit} className="space-y-4"><div><Label>{t('delegues.labName')}</Label><Input value={nom} onChange={e => setNom(e.target.value)} /></div><div className="grid grid-cols-2 gap-3"><div><Label>{t('delegues.contact')}</Label><Input value={contactNom} onChange={e => setContactNom(e.target.value)} /></div><div><Label>{t('delegues.phone')}</Label><Input value={telephone} onChange={e => setTelephone(e.target.value)} /></div></div><div><Label>{t('delegues.email')}</Label><Input type="email" value={email} onChange={e => setEmail(e.target.value)} /></div><div className="border-t pt-3"><p className="text-sm font-medium mb-2">{t('delegues.mainDelegate')}</p><div className="grid grid-cols-2 gap-3"><Input placeholder={t('delegues.firstName')} value={deleguePrenom} onChange={e => setDeleguePrenom(e.target.value)} /><Input placeholder={t('delegues.lastName')} value={delegueNom} onChange={e => setDelegueNom(e.target.value)} /></div></div><DialogFooter><Button type="button" variant="outline" onClick={() => onOpenChange(false)}>{t('delegues.cancel')}</Button><Button type="submit" disabled={saving}>{saving ? <Spinner className="h-4 w-4" /> : t('delegues.save')}</Button></DialogFooter></form></DialogContent></Dialog>;
}

function VisiteDialog({ open, onOpenChange, delegues, onCreated }: { open: boolean; onOpenChange: (v: boolean) => void; delegues: Delegue[]; onCreated: () => void }) {
  const { t } = useTranslation();
  const [delegueId, setDelegueId] = useState(''); const [date, setDate] = useState(new Date().toISOString().slice(0, 16)); const [objet, setObjet] = useState(t('delegues.objetDefault')); const [compteRendu, setCompteRendu] = useState(''); const [saving, setSaving] = useState(false);
  const submit = async (e: React.FormEvent) => { e.preventDefault(); if (!delegueId || !objet.trim()) return toast.error(delegues.length ? t('delegues.selectDelegateError') : t('delegues.addLabFirst')); setSaving(true); try { await api.post('/delegues/visites', { delegue_id: Number(delegueId), date_visite: new Date(date).toISOString(), objet: objet.trim(), compte_rendu: compteRendu || undefined }); toast.success(t('delegues.visitSaved')); onOpenChange(false); setCompteRendu(''); onCreated(); } catch (err: any) { toast.error(err.response?.data?.detail || t('delegues.visitSaveError')); } finally { setSaving(false); } };
  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent><DialogHeader><DialogTitle>{t('delegues.newVisitTitle')}</DialogTitle><DialogDescription>{t('delegues.newVisitDesc')}</DialogDescription></DialogHeader><form onSubmit={submit} className="space-y-4"><div><Label>{t('delegues.delegateLabel')}</Label><select className="w-full h-9 px-3 border rounded-md text-sm" value={delegueId} onChange={e => setDelegueId(e.target.value)}><option value="">{t('delegues.selectDelegate')}</option>{delegues.map(d => <option key={d.id} value={d.id}>{d.nom_complet}</option>)}</select></div><div><Label>{t('delegues.datetime')}</Label><Input type="datetime-local" value={date} onChange={e => setDate(e.target.value)} /></div><div><Label>{t('delegues.subjectLabel')}</Label><Input value={objet} onChange={e => setObjet(e.target.value)} /></div><div><Label>{t('delegues.reportLabel')}</Label><Input value={compteRendu} onChange={e => setCompteRendu(e.target.value)} /></div><DialogFooter><Button type="button" variant="outline" onClick={() => onOpenChange(false)}>{t('delegues.cancel')}</Button><Button type="submit" disabled={saving}>{saving ? <Spinner className="h-4 w-4" /> : t('delegues.saveVisit')}</Button></DialogFooter></form></DialogContent></Dialog>;
}
