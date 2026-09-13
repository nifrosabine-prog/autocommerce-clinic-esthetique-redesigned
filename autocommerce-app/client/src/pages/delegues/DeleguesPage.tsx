import React, { useEffect, useState } from 'react';
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
    } catch { toast.error('Erreur lors du chargement des délégués et laboratoires'); }
    finally { setIsLoading(false); }
  };
  useEffect(() => { loadData(); }, []);

  if (isLoading) return <DashboardLayout><div className="flex items-center justify-center h-96"><Spinner /></div></DashboardLayout>;
  return <DashboardLayout><div className="space-y-6">
    <div><h1 className="text-3xl font-bold">Délégués & Labos</h1><p className="text-muted-foreground mt-1">Gestion des relations laboratoires et échantillons médicaux</p></div>
    <Tabs defaultValue="visites">
      <TabsList><TabsTrigger value="visites"><Calendar className="w-4 h-4 mr-2" />Visites & Dotations</TabsTrigger><TabsTrigger value="labos"><Beaker className="w-4 h-4 mr-2" />Laboratoires Partenaires</TabsTrigger></TabsList>
      <TabsContent value="visites" className="space-y-4"><Card><CardHeader className="flex flex-row items-center justify-between"><CardTitle>Historique des Visites</CardTitle><Button size="sm" onClick={() => setVisiteOpen(true)}><Calendar className="w-4 h-4 mr-2" />Nouvelle Visite</Button></CardHeader><CardContent><Table><TableHeader><TableRow><TableHead>Date</TableHead><TableHead>Délégué</TableHead><TableHead>Objet</TableHead><TableHead>Échantillons</TableHead></TableRow></TableHeader><TableBody>{visites.length === 0 ? <TableRow><TableCell colSpan={4} className="text-center py-8 text-muted-foreground">Aucune visite enregistrée</TableCell></TableRow> : visites.map(v => <TableRow key={v.id}><TableCell>{new Date(v.date).toLocaleDateString('fr-FR')}</TableCell><TableCell className="font-medium">{v.delegue}</TableCell><TableCell>{v.objet}</TableCell><TableCell>{v.echantillons ? <span className="text-xs bg-purple-100 text-purple-800 px-2 py-1 rounded"><Package className="w-3 h-3 inline mr-1" />Reçus</span> : '—'}</TableCell></TableRow>)}</TableBody></Table></CardContent></Card></TabsContent>
      <TabsContent value="labos" className="space-y-4"><Card><CardHeader className="flex flex-row items-center justify-between"><CardTitle>Laboratoires</CardTitle><Button size="sm" onClick={() => setLaboOpen(true)}><Plus className="w-4 h-4 mr-2" />Ajouter Labo</Button></CardHeader><CardContent><div className="grid grid-cols-1 md:grid-cols-3 gap-4">{labos.length === 0 ? <p className="text-muted-foreground">Aucun laboratoire enregistré.</p> : labos.map(l => <Card key={l.id} className="border-l-4 border-l-blue-500"><CardContent className="pt-6"><div className="font-bold text-lg">{l.nom}</div><div className="text-sm text-muted-foreground mt-1">Contact : {l.contact || 'Non spécifié'}</div></CardContent></Card>)}</div></CardContent></Card></TabsContent>
    </Tabs>
    <LaboDialog open={laboOpen} onOpenChange={setLaboOpen} onCreated={loadData} />
    <VisiteDialog open={visiteOpen} onOpenChange={setVisiteOpen} delegues={delegues} onCreated={loadData} />
  </div></DashboardLayout>;
}

function LaboDialog({ open, onOpenChange, onCreated }: { open: boolean; onOpenChange: (v: boolean) => void; onCreated: () => void }) {
  const [nom, setNom] = useState(''); const [contactNom, setContactNom] = useState(''); const [telephone, setTelephone] = useState(''); const [email, setEmail] = useState(''); const [delegueNom, setDelegueNom] = useState(''); const [deleguePrenom, setDeleguePrenom] = useState(''); const [saving, setSaving] = useState(false);
  const reset = () => { setNom(''); setContactNom(''); setTelephone(''); setEmail(''); setDelegueNom(''); setDeleguePrenom(''); };
  const submit = async (e: React.FormEvent) => { e.preventDefault(); if (!nom.trim()) return toast.error('Le nom du laboratoire est requis'); setSaving(true); try { const labo = await api.post('/delegues/labos', { nom: nom.trim(), contact_nom: contactNom || undefined, telephone: telephone || undefined, email: email || undefined }); if (delegueNom.trim() && deleguePrenom.trim()) await api.post('/delegues/delegues', { labo_id: labo.data.id, nom: delegueNom.trim(), prenom: deleguePrenom.trim() }); toast.success('Laboratoire ajouté'); onOpenChange(false); reset(); onCreated(); } catch (err: any) { toast.error(err.response?.data?.detail || "Erreur lors de l'ajout du laboratoire"); } finally { setSaving(false); } };
  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent><DialogHeader><DialogTitle>Ajouter un laboratoire</DialogTitle><DialogDescription>Ajoutez un partenaire et, si besoin, son délégué principal.</DialogDescription></DialogHeader><form onSubmit={submit} className="space-y-4"><div><Label>Nom du laboratoire *</Label><Input value={nom} onChange={e => setNom(e.target.value)} /></div><div className="grid grid-cols-2 gap-3"><div><Label>Contact</Label><Input value={contactNom} onChange={e => setContactNom(e.target.value)} /></div><div><Label>Téléphone</Label><Input value={telephone} onChange={e => setTelephone(e.target.value)} /></div></div><div><Label>Email</Label><Input type="email" value={email} onChange={e => setEmail(e.target.value)} /></div><div className="border-t pt-3"><p className="text-sm font-medium mb-2">Délégué principal (facultatif)</p><div className="grid grid-cols-2 gap-3"><Input placeholder="Prénom" value={deleguePrenom} onChange={e => setDeleguePrenom(e.target.value)} /><Input placeholder="Nom" value={delegueNom} onChange={e => setDelegueNom(e.target.value)} /></div></div><DialogFooter><Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button><Button type="submit" disabled={saving}>{saving ? <Spinner className="h-4 w-4" /> : 'Enregistrer'}</Button></DialogFooter></form></DialogContent></Dialog>;
}

function VisiteDialog({ open, onOpenChange, delegues, onCreated }: { open: boolean; onOpenChange: (v: boolean) => void; delegues: Delegue[]; onCreated: () => void }) {
  const [delegueId, setDelegueId] = useState(''); const [date, setDate] = useState(new Date().toISOString().slice(0, 16)); const [objet, setObjet] = useState('Présentation Produit'); const [compteRendu, setCompteRendu] = useState(''); const [saving, setSaving] = useState(false);
  const submit = async (e: React.FormEvent) => { e.preventDefault(); if (!delegueId || !objet.trim()) return toast.error(delegues.length ? 'Sélectionnez un délégué' : 'Ajoutez d’abord un laboratoire et un délégué'); setSaving(true); try { await api.post('/delegues/visites', { delegue_id: Number(delegueId), date_visite: new Date(date).toISOString(), objet: objet.trim(), compte_rendu: compteRendu || undefined }); toast.success('Visite enregistrée'); onOpenChange(false); setCompteRendu(''); onCreated(); } catch (err: any) { toast.error(err.response?.data?.detail || "Erreur lors de l'enregistrement de la visite"); } finally { setSaving(false); } };
  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent><DialogHeader><DialogTitle>Nouvelle visite</DialogTitle><DialogDescription>Enregistrez une visite de délégué avec des données synthétiques.</DialogDescription></DialogHeader><form onSubmit={submit} className="space-y-4"><div><Label>Délégué *</Label><select className="w-full h-9 px-3 border rounded-md text-sm" value={delegueId} onChange={e => setDelegueId(e.target.value)}><option value="">Sélectionner un délégué</option>{delegues.map(d => <option key={d.id} value={d.id}>{d.nom_complet}</option>)}</select></div><div><Label>Date et heure *</Label><Input type="datetime-local" value={date} onChange={e => setDate(e.target.value)} /></div><div><Label>Objet *</Label><Input value={objet} onChange={e => setObjet(e.target.value)} /></div><div><Label>Compte rendu</Label><Input value={compteRendu} onChange={e => setCompteRendu(e.target.value)} /></div><DialogFooter><Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button><Button type="submit" disabled={saving}>{saving ? <Spinner className="h-4 w-4" /> : 'Enregistrer la visite'}</Button></DialogFooter></form></DialogContent></Dialog>;
}
