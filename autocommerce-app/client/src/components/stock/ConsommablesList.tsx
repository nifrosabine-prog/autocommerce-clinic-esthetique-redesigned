import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api, downloadPdf } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { Plus, Minus, History, AlertTriangle, PackagePlus, SlidersHorizontal, FileDown } from 'lucide-react';
import { toast } from 'sonner';
import { extractErrorMessage } from '@/lib/errors';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';

export interface Consommable {
  id: number;
  nom: string;
  categorie: string;
  unite: string;
  stock_actuel: number;
  seuil_alerte: number;
  stock_minimum: number;
  prix_unitaire: number;
  is_active: boolean;
}

export function ConsommablesList({ onAddClick, canManageStock }: { onAddClick: () => void; canManageStock: boolean }) {
  const [consommables, setConsommables] = useState<Consommable[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [mouvementOpen, setMouvementOpen] = useState(false);
  const [selectedConsommable, setSelectedConsommable] = useState<Consommable | null>(null);
  const [mvtType, setMvtType] = useState<'entree' | 'sortie' | 'ajustement'>('entree');
  const [mvtQuantite, setMvtQuantite] = useState('');
  const [mvtMotif, setMvtMotif] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyRows, setHistoryRows] = useState<any[]>([]);
  const [alertes, setAlertes] = useState<any[]>([]);

  useEffect(() => {
    loadConsommables();
  }, []);

  const loadConsommables = async () => {
    try {
      setIsLoading(true);
      const [listRes, alertesRes] = await Promise.all([
        api.get('/consommables/list'),
        api.get('/consommables/alertes'),
      ]);
      setConsommables(listRes.data);
      setAlertes(Array.isArray(alertesRes.data) ? alertesRes.data : []);
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Erreur lors du chargement des consommables'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleMouvement = (c: Consommable, type: 'entree' | 'sortie' | 'ajustement') => {
    setSelectedConsommable(c);
    setMvtType(type);
    setMvtQuantite('');
    setMvtMotif('');
    setMouvementOpen(true);
  };

  const openHistory = async (c: Consommable) => {
    try {
      const res = await api.get(`/consommables/${c.id}/mouvements`);
      setHistoryRows(Array.isArray(res.data) ? res.data : []);
      setSelectedConsommable(c);
      setHistoryOpen(true);
    } catch (err) {
      toast.error(extractErrorMessage(err, "Impossible de charger l'historique"));
    }
  };

  const exportMouvementsPdf = async () => {
    try {
      const filename = `registre_mouvements_consommables_${new Date().toISOString().slice(0, 10)}.pdf`;
      await downloadPdf('/consommables/mouvements/export-pdf', filename);
      toast.success('Export PDF du registre consommables généré');
    } catch (err) {
      toast.error(extractErrorMessage(err, "Erreur lors de l'export PDF du registre"));
    }
  };

  const submitMouvement = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedConsommable || !mvtQuantite) return;
    if (mvtType === 'ajustement' && !mvtMotif.trim()) {
      toast.error("Un motif est obligatoire pour un ajustement d'inventaire");
      return;
    }

    setIsSaving(true);
    try {
      await api.post(`/consommables/${selectedConsommable.id}/mouvement`, {
        type: mvtType,
        quantite: Number(mvtQuantite),
        motif: mvtMotif
      });
      toast.success('Mouvement enregistré');
      setMouvementOpen(false);
      loadConsommables();
    } catch (err) {
      toast.error(extractErrorMessage(err, "Erreur lors de l'enregistrement du mouvement"));
    } finally {
      setIsSaving(false);
    }
  };

  const getStockStatus = (c: Consommable) => {
    if (c.stock_actuel <= c.stock_minimum) return 'text-red-600 font-bold';
    if (c.stock_actuel <= c.seuil_alerte) return 'text-orange-600 font-semibold';
    return '';
  };

  if (isLoading) return <div className="flex justify-center p-8"><Spinner /></div>;

  return (
    <div className="space-y-4">
      {canManageStock && <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={exportMouvementsPdf} title="Exporter le registre des mouvements en PDF (audit imprimable)">
          <FileDown className="w-4 h-4 mr-2" />
          Exporter PDF
        </Button>
        <Button onClick={onAddClick}>
          <Plus className="w-4 h-4 mr-2" />
          Nouveau consommable
        </Button>
      </div>}

      {alertes.length > 0 && (
        <div className="flex items-start gap-2 rounded-md border border-orange-300 bg-orange-50 p-3 text-sm text-orange-800">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          <div>
            <span className="font-semibold">Alertes consommables ({alertes.length})</span>
            <ul className="mt-1 space-y-0.5">
              {alertes.slice(0, 5).map((a) => (
                <li key={a.id}>
                  {a.nom} : {a.stock_actuel} {a.unite} restant(s) —{' '}
                  <span className={a.niveau === 'critique' ? 'font-bold' : ''}>
                    {a.niveau === 'critique' ? 'CRITIQUE' : 'ALERTE'}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      <Card>
        <CardContent className="pt-6">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nom</TableHead>
                <TableHead>Catégorie</TableHead>
                <TableHead>Stock Actuel</TableHead>
                <TableHead>Unité</TableHead>
                <TableHead>Seuil Alerte</TableHead>
                    {canManageStock && <TableHead className="text-right">Actions</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {consommables.map((c) => (
                <TableRow key={c.id}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      {c.nom}
                      {c.stock_actuel <= c.seuil_alerte && (
                        <AlertTriangle className={`w-4 h-4 ${c.stock_actuel <= c.stock_minimum ? 'text-red-500' : 'text-orange-500'}`} />
                      )}
                    </div>
                  </TableCell>
                  <TableCell>{c.categorie}</TableCell>
                  <TableCell className={getStockStatus(c)}>
                    {c.stock_actuel}
                  </TableCell>
                  <TableCell>{c.unite}</TableCell>
                  <TableCell>{c.seuil_alerte}</TableCell>
                  {canManageStock && <TableCell className="text-right space-x-2">
                    <Button size="sm" variant="outline" onClick={() => handleMouvement(c, 'entree')} title="Entrée de stock">
                      <Plus className="w-4 h-4" />
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => handleMouvement(c, 'sortie')} title="Sortie de stock">
                      <Minus className="w-4 h-4" />
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => handleMouvement(c, 'ajustement')} title="Ajustement d'inventaire">
                      <SlidersHorizontal className="w-4 h-4" />
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => openHistory(c)} title="Historique des mouvements">
                      <History className="w-4 h-4" />
                    </Button>
                  </TableCell>}
                </TableRow>
              ))}
              {consommables.length === 0 && (
                <TableRow>
                  <TableCell colSpan={canManageStock ? 6 : 5} className="text-center py-8 text-muted-foreground">
                    Aucun consommable enregistré
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {canManageStock && <Dialog open={mouvementOpen} onOpenChange={setMouvementOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {mvtType === 'entree' ? 'Entrée de stock' : mvtType === 'sortie' ? 'Sortie de stock' : "Ajustement d'inventaire"} : {selectedConsommable?.nom}
            </DialogTitle>
            <DialogDescription>
              Enregistrez un mouvement de stock pour ce consommable.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={submitMouvement} className="space-y-4">
            <div>
              <Label htmlFor="qte">
                {mvtType === 'ajustement' ? `Stock constaté (${selectedConsommable?.unite}) *` : `Quantité (${selectedConsommable?.unite}) *`}
              </Label>
              <Input 
                id="qte" 
                type="number" 
                step="0.01" 
                value={mvtQuantite} 
                onChange={(e) => setMvtQuantite(e.target.value)} 
                required 
              />
              {mvtType === 'ajustement' && (
                <p className="text-xs text-muted-foreground mt-1">Le stock sera remplacé par la quantité constatée.</p>
              )}
            </div>
            <div>
              <Label htmlFor="motif">Motif / Commentaire {mvtType === 'ajustement' ? '*' : ''}</Label>
              <Input 
                id="motif" 
                value={mvtMotif} 
                onChange={(e) => setMvtMotif(e.target.value)} 
                placeholder={mvtType === 'ajustement' ? 'Ex: Inventaire mensuel (obligatoire)' : 'Ex: Réception commande, Utilisation soin...'}
                required={mvtType === 'ajustement'}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setMouvementOpen(false)}>Annuler</Button>
              <Button type="submit" disabled={isSaving}>
                {isSaving ? <Spinner className="h-4 w-4" /> : 'Enregistrer'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>}

      <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Historique des mouvements : {selectedConsommable?.nom}</DialogTitle>
          </DialogHeader>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Quantité</TableHead>
                  <TableHead>Utilisateur</TableHead>
                  <TableHead>Motif</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {historyRows.map((h) => (
                  <TableRow key={h.mouvement_id}>
                    <TableCell className="whitespace-nowrap">{new Date(h.date_mouvement).toLocaleString('fr-FR')}</TableCell>
                    <TableCell>
                      <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                        h.type === 'entree' ? 'bg-green-100 text-green-800' :
                        h.type === 'sortie' ? 'bg-red-100 text-red-800' : 'bg-orange-100 text-orange-800'
                      }`}>
                        {h.type === 'entree' ? 'Entrée' : h.type === 'sortie' ? 'Sortie' : 'Ajustement'}
                      </span>
                    </TableCell>
                    <TableCell className={h.type === 'entree' ? 'text-green-600 font-semibold' : h.type === 'sortie' ? 'text-red-600 font-semibold' : 'font-semibold'}>
                      {h.type === 'entree' ? '+' : h.type === 'sortie' ? '-' : '='}{h.quantite}
                    </TableCell>
                    <TableCell>{h.utilisateur || '—'}</TableCell>
                    <TableCell>{h.motif || '—'}</TableCell>
                  </TableRow>
                ))}
                {historyRows.length === 0 && (
                  <TableRow><TableCell colSpan={5} className="text-center py-6 text-muted-foreground">Aucun mouvement</TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setHistoryOpen(false)}>Fermer</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
