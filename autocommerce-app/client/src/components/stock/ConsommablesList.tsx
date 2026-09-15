import { useTranslation } from 'react-i18next';
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

export function ConsommablesList({
  onAddClick, canManageStock }: { onAddClick: () => void; canManageStock: boolean }) {
  const { t, i18n } = useTranslation();
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
      toast.error(extractErrorMessage(err, t('componentUi.consumablesLoadError')));
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
      toast.error(extractErrorMessage(err, t('componentUi.historyLoadError')));
    }
  };

  const exportMouvementsPdf = async () => {
    try {
      const filename = `registre_mouvements_consommables_${new Date().toISOString().slice(0, 10)}.pdf`;
      await downloadPdf('/consommables/mouvements/export-pdf', filename);
      toast.success(t('componentUi.pdfExportSuccess'));
    } catch (err) {
      toast.error(extractErrorMessage(err, t('componentUi.pdfExportError')));
    }
  };

  const submitMouvement = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedConsommable || !mvtQuantite) return;
    if (mvtType === 'ajustement' && !mvtMotif.trim()) {
      toast.error(t('componentUi.adjustmentReasonRequired'));
      return;
    }

    setIsSaving(true);
    try {
      await api.post(`/consommables/${selectedConsommable.id}/mouvement`, {
        type: mvtType,
        quantite: Number(mvtQuantite),
        motif: mvtMotif
      });
      toast.success(t('componentUi.movementSaved'));
      setMouvementOpen(false);
      loadConsommables();
    } catch (err) {
      toast.error(extractErrorMessage(err, t('componentUi.movementSaveError')));
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
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">{t('componentUi.consumablesTitle')}</h2>
        {canManageStock && <div className="flex gap-2">
          <Button variant="outline" onClick={exportMouvementsPdf} title={t('componentUi.exportMovementPdf')}>
            <FileDown className="w-4 h-4 mr-2" />
            {t('componentUi.exportPdf')}
          </Button>
          <Button onClick={onAddClick}>
            <Plus className="w-4 h-4 mr-2" />
            {t('componentUi.newConsumable')}
          </Button>
        </div>}
      </div>

      {alertes.length > 0 && (
        <div className="flex items-start gap-2 rounded-md border border-orange-300 bg-orange-50 p-3 text-sm text-orange-800">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          <div>
            <span className="font-semibold">{t('componentUi.alerts', { count: alertes.length })}</span>
            <ul className="mt-1 space-y-0.5">
              {alertes.slice(0, 5).map((a) => (
                <li key={a.id}>
                  {t('componentUi.remainingStock', { name: a.nom, stock: a.stock_actuel, unit: a.unite })} —{' '}
                  <span className={a.niveau === 'critique' ? 'font-bold' : ''}>
                    {a.niveau === 'critique' ? t('componentUi.critical') : t('componentUi.warning')}
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
                <TableHead>{t('componentUi.stockName')}</TableHead>
                <TableHead>{t('componentUi.category')}</TableHead>
                <TableHead>{t('componentUi.currentStock')}</TableHead>
                <TableHead>{t('componentUi.unit')}</TableHead>
                <TableHead>{t('componentUi.alertThresholdShort')}</TableHead>
                {canManageStock && <TableHead className="text-right">{t('componentUi.actions')}</TableHead>}
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
                    <Button size="sm" variant="outline" onClick={() => handleMouvement(c, 'entree')} title={t('componentUi.stockIn')}>
                      <Plus className="w-4 h-4" />
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => handleMouvement(c, 'sortie')} title={t('componentUi.stockOut')}>
                      <Minus className="w-4 h-4" />
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => handleMouvement(c, 'ajustement')} title={t('componentUi.inventoryAdjustment')}>
                      <SlidersHorizontal className="w-4 h-4" />
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => openHistory(c)} title={t('componentUi.movementHistory')}>
                      <History className="w-4 h-4" />
                    </Button>
                  </TableCell>}
                </TableRow>
              ))}
              {consommables.length === 0 && (
                <TableRow>
                  <TableCell colSpan={canManageStock ? 6 : 5} className="text-center py-8 text-muted-foreground">
                    {t('componentUi.noConsumable')}
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
              {mvtType === 'entree' ? t('componentUi.stockIn') : mvtType === 'sortie' ? t('componentUi.stockOut') : t('componentUi.inventoryAdjustment')} : {selectedConsommable?.nom}
            </DialogTitle>
            <DialogDescription>
              {t('componentUi.movementDescription')}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={submitMouvement} className="space-y-4">
            <div>
              <Label htmlFor="qte">
                {mvtType === 'ajustement' ? t('componentUi.observedStock', { unit: selectedConsommable?.unite }) : t('componentUi.quantityUnit', { unit: selectedConsommable?.unite })}
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
                <p className="text-xs text-muted-foreground mt-1">{t('componentUi.stockReplaced')}</p>
              )}
            </div>
            <div>
              <Label htmlFor="motif">{t('componentUi.reasonComment')} {mvtType === 'ajustement' ? '*' : ''}</Label>
              <Input 
                id="motif" 
                value={mvtMotif} 
                onChange={(e) => setMvtMotif(e.target.value)} 
                placeholder={mvtType === 'ajustement' ? t('componentUi.monthlyInventoryPlaceholder') : t('componentUi.movementPlaceholder')}
                required={mvtType === 'ajustement'}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setMouvementOpen(false)}>{t('componentUi.cancel')}</Button>
              <Button type="submit" disabled={isSaving}>
                {isSaving ? <Spinner className="h-4 w-4" /> : t('componentUi.record')}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>}

      <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t('componentUi.movementHistoryTitle', { name: selectedConsommable?.nom })}</DialogTitle>
          </DialogHeader>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('componentUi.date')}</TableHead>
                  <TableHead>{t('componentUi.type')}</TableHead>
                  <TableHead>{t('componentUi.quantity')}</TableHead>
                  <TableHead>{t('componentUi.user')}</TableHead>
                  <TableHead>{t('componentUi.reason')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {historyRows.map((h) => (
                  <TableRow key={h.mouvement_id}>
                    <TableCell className="whitespace-nowrap">{new Date(h.date_mouvement).toLocaleString(i18n.resolvedLanguage || i18n.language)}</TableCell>
                    <TableCell>
                      <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                        h.type === 'entree' ? 'bg-green-100 text-green-800' :
                        h.type === 'sortie' ? 'bg-red-100 text-red-800' : 'bg-orange-100 text-orange-800'
                      }`}>
                        {h.type === 'entree' ? t('componentUi.entry') : h.type === 'sortie' ? t('componentUi.exit') : t('componentUi.adjustment')}
                      </span>
                    </TableCell>
                    <TableCell className={h.type === 'entree' ? 'text-green-600 font-semibold' : h.type === 'sortie' ? 'text-red-600 font-semibold' : 'font-semibold'}>
                      {h.type === 'entree' ? '+' : h.type === 'sortie' ? '-' : '='}{h.quantite}
                    </TableCell>
                    <TableCell>{h.utilisateur || t('componentUi.notProvided')}</TableCell>
                    <TableCell>{h.motif || t('componentUi.notProvided')}</TableCell>
                  </TableRow>
                ))}
                {historyRows.length === 0 && (
                  <TableRow><TableCell colSpan={5} className="text-center py-6 text-muted-foreground">{t('componentUi.noMovement')}</TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setHistoryOpen(false)}>{t('componentUi.close')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
