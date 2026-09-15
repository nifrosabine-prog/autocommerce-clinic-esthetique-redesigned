import React, { useState, useEffect, useRef } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api, PublicPraticien, downloadPdf } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import { Spinner } from '@/components/ui/spinner';
import { AlertCircle, BellRing, FileDown, History, PackagePlus, Plus, RefreshCw, Search } from 'lucide-react';
import { toast } from 'sonner';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ConsommablesList } from '@/components/stock/ConsommablesList';
import { ConsommableForm } from '@/components/stock/ConsommableForm';
import { BarcodeCameraScanner } from '@/components/stock/BarcodeCameraScanner';
import { extractErrorMessage, parseDecimalInput } from '@/lib/errors';
import { useTranslation } from 'react-i18next';

interface StockProduct {
  produit_id: number;
  nom: string;
  fabricant?: string;
  categorie: string;
  stock_total: number;
  unite: string;
  stock_minimum: number;
  nb_lots_actifs: number;
  statut: 'rupture' | 'alerte' | 'ok';
}

interface Alert {
  produit: string;
  lot: string;
  message: string;
}

interface StockReminder {
  id: number;
  type_article: 'injectable' | 'consommable';
  article_nom: string;
  niveau: 'alerte' | 'critique';
  message: string;
}

const INJECTION_TYPE_OPTIONS = [
  { value: 'Botox', label: 'Botox' },
  { value: 'Hyaluronic Acid', labelKey: 'stock.injection.typeHyaluronicAcid' },
  { value: 'Mesotherapy', labelKey: 'stock.injection.typeMesotherapy' },
  { value: 'Skinbooster', label: 'Skinbooster' },
  { value: 'Other', labelKey: 'stock.injection.typeOther' },
] as const;

export default function StockPage() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const currentRole = user?.role || '';
  const canManageStock = ['admin', 'directrice', 'assistante'].includes(currentRole);
  const [isLoading, setIsLoading] = useState(true);
  const [stockData, setStockData] = useState<{ produits: StockProduct[] } | null>(null);
  const [alertes, setAlertes] = useState({ rouge: [] as Alert[], orange: [] as Alert[] });
  const [scanValue, setScanValue] = useState('');
  const [addLotOpen, setAddLotOpen] = useState(false);
  const [addConsommableOpen, setAddConsommableOpen] = useState(false);
  const [injectionDialogOpen, setInjectionDialogOpen] = useState(false);
  const [receptionDialogOpen, setReceptionDialogOpen] = useState(false);
  const [scannedLot, setScannedLot] = useState<any>(null);
  const [addLotInitialCode, setAddLotInitialCode] = useState('');
  const [mouvements, setMouvements] = useState<any[]>([]);
  const [stockReminders, setStockReminders] = useState<StockReminder[]>([]);
  const [activeTab, setActiveTab] = useState('injectables');
  const [loadError, setLoadError] = useState<string | null>(null);
  const hiddenInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadStockData();
  }, []);

  const loadStockData = async () => {
    try {
      setIsLoading(true);
      const [stockRes, alertesRes, mvtRes, remindersRes] = await Promise.all([
        api.get('/injectables/stock'),
        api.get('/injectables/alertes'),
        api.get('/injectables/mouvements?limit=12'),
        api.get('/stock-alertes'),
      ]);
      setStockData(stockRes.data);
      setAlertes(alertesRes.data || { rouge: [], orange: [] });
      setMouvements(Array.isArray(mvtRes.data) ? mvtRes.data : []);
      setStockReminders(Array.isArray(remindersRes.data) ? remindersRes.data : []);
      setLoadError(null);
    } catch (err: any) {
      console.error('Failed to load stock:', err);
      setLoadError(t('stock.loadError'));
      toast.error(t('stock.loadErrorShort'));
    } finally {
      setIsLoading(false);
    }
  };

  const exportMouvementsPdf = async () => {
    try {
      const filename = `registre_mouvements_injectables_${new Date().toISOString().slice(0, 10)}.pdf`;
      await downloadPdf('/injectables/mouvements/export-pdf', filename);
      toast.success(t('stock.exportSuccess'));
    } catch (err) {
      toast.error(extractErrorMessage(err, t('stock.exportError')));
    }
  };

  const acknowledgeReminder = async (id: number) => {
    try {
      await api.post(`/stock-alertes/${id}/acquitter`);
      setStockReminders((current) => current.filter((item) => item.id !== id));
      toast.success(t('stock.reminderAcknowledged'));
    } catch (err) {
      toast.error(extractErrorMessage(err, t('stock.reminderAckError')));
    }
  };

  const handleScan = async (code: string, mode: 'injection' | 'reception' = 'injection'): Promise<boolean> => {
    const normalized = code.trim();
    if (!normalized) return false;
    try {
      const response = await api.post('/injectables/scan', { code: normalized });
      setScannedLot({ ...response.data, code: normalized });
      if (mode === 'reception') setReceptionDialogOpen(true);
      else setInjectionDialogOpen(true);
      return true;
    } catch (err) {
      const message = extractErrorMessage(err, t('stock.lotNotFound'));
      if (normalized.length >= 3 && /non trouvé|404/i.test(message)) {
        setAddLotInitialCode(normalized);
        setAddLotOpen(true);
        toast.info(t('stock.unknownLotInfo'));
      } else {
        toast.error(message);
      }
      return false;
    }
  };

  const submitManualScan = async () => {
    const code = scanValue.trim();
    if (code.length < 3) {
      toast.error(t('stock.minCharsError'));
      return;
    }
    if (await handleScan(code)) setScanValue('');
  };

  const getStatusColor = (statut: string) => {
    switch (statut) {
      case 'rupture':
        return 'bg-red-100 text-red-800';
      case 'alerte':
        return 'bg-orange-100 text-orange-800';
      default:
        return 'bg-green-100 text-green-800';
    }
  };

  const getStatusLabel = (statut: string) => {
    const key = ['rupture', 'alerte', 'ok'].includes(statut) ? statut : 'ok';
    return t(`stock.status_${key}`, { defaultValue: statut });
  };

  const totalAlertesCritiques = alertes.rouge.length + alertes.orange.length;

  if (loadError && !stockData) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-96">
          <Card className="w-full max-w-md border-red-300 bg-red-50/70">
            <CardContent className="flex items-center justify-between gap-4 py-6">
              <div className="flex items-center gap-3 text-red-800">
                <AlertCircle className="w-5 h-5 shrink-0" />
                <div>
                  <p className="font-medium">{t('stock.loadErrorTitle')}</p>
                  <p className="text-sm text-red-700">{loadError}</p>
                </div>
              </div>
              <Button variant="outline" onClick={() => void loadStockData()}>
                <RefreshCw className="w-4 h-4 mr-2" /> {t('stock.retry')}
              </Button>
            </CardContent>
          </Card>
        </div>
      </DashboardLayout>
    );
  }

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
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">{t('stock.title')}</h1>
            <p className="text-muted-foreground mt-1">{t('stock.subtitle')}</p>
          </div>
        </div>

        {stockReminders.length > 0 && (
          <Card className="border-orange-300 bg-orange-50/70">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-orange-900">
                <BellRing className="w-5 h-5" /> {t('stock.remindersTitle', { count: stockReminders.length })}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {stockReminders.map((reminder) => (
                <div key={reminder.id} className="flex items-center justify-between gap-3 rounded border border-orange-200 bg-white p-2 text-sm">
                  <div>
                    <span className={`mr-2 inline-block rounded px-2 py-0.5 text-xs font-semibold ${reminder.niveau === 'critique' ? 'bg-red-100 text-red-800' : 'bg-orange-100 text-orange-800'}`}>
                      {t(`stock.reminderLevel_${reminder.niveau === 'critique' ? 'critique' : 'alerte'}`)}
                    </span>
                    <span className="font-medium">{reminder.article_nom}</span>
                    <span className="ml-2 text-muted-foreground">({reminder.type_article}) — {reminder.message}</span>
                  </div>
                  <Button size="sm" variant="outline" onClick={() => void acknowledgeReminder(reminder.id)}>{t('stock.acknowledge')}</Button>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-2 mb-8">
            <TabsTrigger value="injectables">{t('stock.injectablesTab')}</TabsTrigger>
            <TabsTrigger value="consommables">{t('stock.consommablesTab')}</TabsTrigger>
          </TabsList>

          <TabsContent value="injectables" className="space-y-6">
            {canManageStock && (
              <div className="flex justify-end">
                <Button onClick={() => setAddLotOpen(true)}>
                  <Plus className="w-4 h-4 mr-2" />
                  {t('stock.addLot')}
                </Button>
              </div>
            )}

        {totalAlertesCritiques > 0 && (
          <Card className="border-destructive bg-destructive/5">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-destructive" />
                <span className="font-semibold text-destructive">
                  {t('stock.alertsSummary', { red: alertes.rouge.length, orange: alertes.orange.length })}
                </span>
              </div>
            </CardContent>
          </Card>
        )}

            {canManageStock && <Card>
              <CardHeader>
                <CardTitle>{t('stock.scanCardTitle')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <input
              ref={hiddenInputRef}
              type="text"
              tabIndex={-1}
              aria-hidden="true"
              className="absolute opacity-0 w-px h-px pointer-events-none"
              onChange={(e) => {
                const value = e.target.value;
                if (value.length >= 3) {
                  void handleScan(value);
                  e.target.value = '';
                }
              }}
            />
            <div className="flex flex-col sm:flex-row gap-2">
              <div className="flex-1">
                <BarcodeCameraScanner
                  onDetected={(code) => handleScan(code)}
                  onReceptionDetected={(code) => handleScan(code, 'reception')}
                  compact
                />
              </div>
              <div className="flex flex-1 sm:max-w-sm gap-2">
                <Input
                  placeholder={t('stock.scanPlaceholder')}
                  value={scanValue}
                  onChange={(e) => setScanValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') { e.preventDefault(); void submitManualScan(); }
                  }}
                  autoComplete="off"
                  autoCorrect="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  enterKeyHint="search"
                  className="min-w-0"
                />
                <Button type="button" variant="outline" onClick={() => void submitManualScan()} disabled={scanValue.trim().length < 3}>
                  <Search className="w-4 h-4 mr-1" /> {t('stock.searchButton')}
                </Button>
              </div>
            </div>
          </CardContent>
            </Card>}

            <Card>
              <CardHeader>
                <CardTitle>{t('stock.stockByProduct')}</CardTitle>
              </CardHeader>
              <CardContent>
                {stockData?.produits ? (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>{t('stock.product')}</TableHead>
                          <TableHead>{t('stock.category')}</TableHead>
                          <TableHead>{t('stock.stockColumn')}</TableHead>
                          <TableHead>{t('stock.minimum')}</TableHead>
                          <TableHead>{t('stock.lots')}</TableHead>
                          <TableHead>{t('stock.status')}</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {stockData.produits.map((p) => (
                          <TableRow key={p.produit_id}>
                            <TableCell className="font-medium">{p.nom}</TableCell>
                            <TableCell>{p.categorie}</TableCell>
                            <TableCell>
                              {p.stock_total} {p.unite}
                            </TableCell>
                            <TableCell>{p.stock_minimum}</TableCell>
                            <TableCell>{p.nb_lots_actifs}</TableCell>
                            <TableCell>
                              <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${getStatusColor(p.statut)}`}>
                                {getStatusLabel(p.statut)}
                              </span>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                ) : (
                  <p className="text-muted-foreground">{t('stock.noProductFound')}</p>
                )}
              </CardContent>
            </Card>

            {mouvements.length > 0 && (
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                      <History className="w-4 h-4" /> {t('stock.recentMovements')}
                    </CardTitle>
                    {canManageStock && (
                      <Button size="sm" variant="outline" onClick={exportMouvementsPdf} title={t('stock.exportPdfTitle')}>
                        <FileDown className="w-4 h-4 mr-2" />
                        {t('stock.exportPdf')}
                      </Button>
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>{t('stock.date')}</TableHead>
                          <TableHead>{t('stock.productLot')}</TableHead>
                          <TableHead>{t('stock.type')}</TableHead>
                          <TableHead>{t('stock.quantity')}</TableHead>
                          <TableHead>{t('stock.ref')}</TableHead>
                          <TableHead>{t('stock.reason')}</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {mouvements.map((m) => (
                          <TableRow key={m.mouvement_id}>
                            <TableCell className="whitespace-nowrap">{new Date(m.date_mouvement).toLocaleString(i18n.language)}</TableCell>
                            <TableCell>
                              <span className="font-medium">{m.produit_nom}</span>
                              <span className="text-muted-foreground text-xs block">{t('stock.lotNumber', { lot: m.numero_lot })}</span>
                            </TableCell>
                            <TableCell>
                              <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                                m.type_mouvement === 'reception' ? 'bg-green-100 text-green-800' :
                                m.type_mouvement === 'injection' ? 'bg-blue-100 text-blue-800' :
                                'bg-orange-100 text-orange-800'
                              }`}>
                                {t(`stock.mvt_${['reception', 'injection', 'ajustement'].includes(m.type_mouvement) ? m.type_mouvement : 'ajustement'}`, { defaultValue: m.type_mouvement })}
                              </span>
                            </TableCell>
                            <TableCell className={m.quantite > 0 ? 'text-green-600 font-semibold' : 'text-red-600 font-semibold'}>
                              {m.quantite > 0 ? '+' : ''}{m.quantite}
                            </TableCell>
                            <TableCell>{m.reference || '—'}</TableCell>
                            <TableCell>{m.motif || '—'}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="consommables">
            <ConsommablesList canManageStock={canManageStock} onAddClick={() => setAddConsommableOpen(true)} />
          </TabsContent>
        </Tabs>
      </div>

      <AddLotDialog
        open={addLotOpen}
        onOpenChange={setAddLotOpen}
        produits={stockData?.produits || []}
        initialLotCode={addLotInitialCode}
        onCreated={() => { setAddLotInitialCode(''); loadStockData(); }}
      />

      {canManageStock && <ConsommableForm 
        open={addConsommableOpen}
        onOpenChange={setAddConsommableOpen}
        onCreated={() => {
          // The ConsommablesList component refreshes through its own lifecycle or a signal.
          // A dedicated callback or refresh key would be cleaner if this flow evolves.
          window.location.reload(); // Simple fallback to guarantee a full refresh.
        }}
      />}

      <InjectionUsageDialog
        open={injectionDialogOpen}
        onOpenChange={setInjectionDialogOpen}
        lot={scannedLot}
        onSuccess={loadStockData}
      />

      <LotReceptionDialog
        open={receptionDialogOpen}
        onOpenChange={setReceptionDialogOpen}
        lot={scannedLot}
        onSuccess={loadStockData}
      />
    </DashboardLayout>
  );
}

// ─────────────────────────────────────────────────────────

function InjectionUsageDialog({ open, onOpenChange, lot, onSuccess }: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  lot: any;
  onSuccess: () => void;
}) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const currentRole = user?.role || '';
  const canChoosePraticien = ['directrice', 'assistante', 'admin'].includes(currentRole);
  const [patients, setPatients] = useState<any[]>([]);
  const [praticiens, setPraticiens] = useState<PublicPraticien[]>([]);
  const [patientSearch, setPatientSearch] = useState('');
  const [selectedPatientId, setSelectedPatientId] = useState('');
  const [quantite, setQuantite] = useState('');
  const [dateInjection, setDateInjection] = useState(new Date().toISOString().split('T')[0]);
  const [typeInjection, setTypeInjection] = useState('');
  const [praticienId, setPraticienId] = useState(user?.id?.toString() || '');
  const [notes, setNotes] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isLoadingPatients, setIsLoadingPatients] = useState(false);

  useEffect(() => {
    if (open) {
      setQuantite('');
      setDateInjection(new Date().toISOString().split('T')[0]);
      setTypeInjection('');
      setPraticienId(user?.id?.toString() || '');
      setNotes('');
      setSelectedPatientId('');
      setPatientSearch('');
      setPraticiens([]);
      loadPatients();
      if (canChoosePraticien) {
        loadPraticiens();
      }
    }
  }, [open, lot, user, canChoosePraticien]);

  const loadPatients = async (search = '') => {
    try {
      setIsLoadingPatients(true);
      const res = await api.get(`/patients?search=${search}&limit=10`);
      setPatients(res.data);
    } catch (err) {
      console.error('Failed to load patients:', err);
    } finally {
      setIsLoadingPatients(false);
    }
  };

  const loadPraticiens = async () => {
    try {
      const res = await api.get('/agenda/praticiens');
      const praticiensList = Array.isArray(res.data) ? res.data : [];
      setPraticiens(praticiensList);
      setPraticienId((current) => {
        if (current && praticiensList.some((p: PublicPraticien) => p.id.toString() === current)) {
          return current;
        }
        return praticiensList[0]?.id?.toString() || '';
      });
    } catch (err) {
      console.error('Failed to load practitioners:', err);
      toast.error(t('stock.injection.loadDoctorsError'));
    }
  };

  const handleSearchPatient = (e: React.FormEvent) => {
    e.preventDefault();
    loadPatients(patientSearch);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPatientId || !quantite || !praticienId) {
      toast.error(t('stock.injection.requiredFieldsError'));
      return;
    }
    const qty = parseDecimalInput(quantite);
    if (!Number.isFinite(qty) || qty <= 0) {
      toast.error(t('stock.injection.invalidQuantityError'));
      return;
    }

    setIsSaving(true);
    try {
      await api.post('/injectables/utilisation', {
        lot_id: lot.lot_id,
        code: lot.code || undefined,
        patient_id: Number(selectedPatientId),
        praticien_id: Number(praticienId),
        quantite: qty,
        unite: lot.unite,
        type_injection: typeInjection || undefined,
        date_injection: dateInjection ? `${dateInjection}T12:00:00` : undefined,
        notes: notes || undefined,
      });
      toast.success(t('stock.injection.savedSuccess'));
      onOpenChange(false);
      onSuccess();
    } catch (err) {
      toast.error(extractErrorMessage(err, t('stock.injection.saveError')));
    } finally {
      setIsSaving(false);
    }
  };

  if (!lot) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t('stock.injection.title')}</DialogTitle>
          <DialogDescription>
            {t('stock.injection.productLotLine', { product: lot.produit_nom, lot: lot.numero_lot })}
            <br />
            {t('stock.injection.availableStock', { qty: lot.quantite_restante, unit: lot.unite })}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 py-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>{t('stock.injection.patientLabel')}</Label>
              <div className="flex gap-2">
                <Input
                  placeholder={t('stock.injection.searchPatientPlaceholder')}
                  value={patientSearch}
                  onChange={(e) => setPatientSearch(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearchPatient(e)}
                />
                <Button type="button" size="icon" variant="outline" onClick={() => loadPatients(patientSearch)}>
                  <Search className="w-4 h-4" />
                </Button>
              </div>
              <select
                className="w-full h-9 px-3 border rounded-md text-sm"
                value={selectedPatientId}
                onChange={(e) => setSelectedPatientId(e.target.value)}
              >
                <option value="">{t('stock.injection.choosePatient')}</option>
                {patients.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nom} {p.prenom} ({p.telephone})
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="type_injection">{t('stock.injection.injectionTypeLabel')}</Label>
              <select
                id="type_injection"
                className="w-full h-9 px-3 border rounded-md text-sm"
                value={typeInjection}
                onChange={(e) => setTypeInjection(e.target.value)}
              >
                <option value="">{t('stock.injection.notSpecified')}</option>
                {INJECTION_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {'labelKey' in option ? t(option.labelKey) : option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="quantite">{t('stock.injection.quantityInjected', { unit: lot.unite })}</Label>
              <Input
                id="quantite"
                type="number"
                step="0.001"
                placeholder="0.000"
                value={quantite}
                onChange={(e) => setQuantite(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="date_injection">{t('stock.injection.injectionDateLabel')}</Label>
              <Input
                id="date_injection"
                type="date"
                value={dateInjection}
                onChange={(e) => setDateInjection(e.target.value)}
              />
            </div>

            <div className="space-y-2">
                  <Label htmlFor="praticien">{t('stock.injection.doctorLabel')}</Label>
              {canChoosePraticien ? (
                <select
                  id="praticien"
                  className="w-full h-9 px-3 border rounded-md text-sm"
                  value={praticienId}
                  onChange={(e) => setPraticienId(e.target.value)}
                >
                  <option value="">{t('stock.injection.chooseDoctor')}</option>
                  {praticiens.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.nom_complet}
                    </option>
                  ))}
                </select>
              ) : (
                <>
                  <Input
                    id="praticien"
                    value={user?.nom ? `${user.prenom} ${user.nom}` : ''}
                    disabled
                  />
                  <input type="hidden" value={praticienId} />
                </>
              )}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="notes">{t('stock.injection.notesLabel')}</Label>
            <Input
              id="notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={t('stock.injection.notesPlaceholder')}
            />
          </div>

          <DialogFooter className="pt-4">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" disabled={isSaving}>
              {isSaving ? <Spinner className="h-4 w-4 mr-2" /> : null}
              {t('stock.injection.saveUsage')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────

function AddLotDialog({ open, onOpenChange, produits, initialLotCode, onCreated }: {
  open: boolean; onOpenChange: (v: boolean) => void; produits: StockProduct[]; initialLotCode?: string; onCreated: () => void;
}) {
  const { t } = useTranslation();
  const [produitId, setProduitId] = useState('');
  const [catalogue, setCatalogue] = useState<StockProduct[]>(produits);
  const [showProductForm, setShowProductForm] = useState(false);
  const [newProductNom, setNewProductNom] = useState('');
  const [newProductCategorie, setNewProductCategorie] = useState('toxine');
  const [newProductUnite, setNewProductUnite] = useState('unit');
  const [newProductFabricant, setNewProductFabricant] = useState('');
  const [numeroLot, setNumeroLot] = useState('');
  const [dateExpiration, setDateExpiration] = useState('');
  const [quantiteInitiale, setQuantiteInitiale] = useState('');
  const [fournisseur, setFournisseur] = useState('');
  const [prixAchat, setPrixAchat] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setProduitId(''); setNumeroLot(initialLotCode || ''); setDateExpiration('');
      setQuantiteInitiale(''); setFournisseur(''); setPrixAchat('');
      setCatalogue(produits);
      setShowProductForm(produits.length === 0);
      api.get('/injectables/produits').then((res) => {
        const list = Array.isArray(res.data) ? res.data.map((p: any) => ({ ...p, produit_id: p.id, stock_total: 0, stock_minimum: 0, nb_lots_actifs: 0, statut: 'ok', unite: p.unite || 'unit' })) : [];
        setCatalogue(list);
        setShowProductForm(list.length === 0);
      }).catch(() => setCatalogue(produits));
    }
  }, [open, produits, initialLotCode]);

  const handleCreateProduct = async () => {
    if (!newProductNom.trim()) { toast.error(t('stock.addLotDialog.productNameRequired')); return; }
    try {
      const res = await api.post('/injectables/produits', {
        nom: newProductNom.trim(), categorie: newProductCategorie, unite: newProductUnite,
        fabricant: newProductFabricant || undefined,
      });
      const created = { ...res.data, produit_id: res.data.id, stock_total: 0, stock_minimum: 0, nb_lots_actifs: 0, statut: 'ok' };
      setCatalogue((current) => [...current, created]);
      setProduitId(String(created.produit_id));
      setNewProductNom(''); setNewProductFabricant(''); setShowProductForm(false);
      toast.success(t('stock.addLotDialog.productAddedSuccess'));
    } catch (err) { toast.error(extractErrorMessage(err, t('stock.addLotDialog.productAddError'))); }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!produitId || !numeroLot.trim() || !dateExpiration) {
      toast.error(t('stock.addLotDialog.requiredFieldsError'));
      return;
    }
    const quantite = parseDecimalInput(quantiteInitiale);
    if (!Number.isFinite(quantite) || quantite <= 0) {
      toast.error(t('stock.addLotDialog.invalidInitialQtyError'));
      return;
    }
    let prix: number | undefined;
    if (prixAchat.trim()) {
      prix = parseDecimalInput(prixAchat);
      if (!Number.isFinite(prix) || prix < 0) {
        toast.error(t('stock.addLotDialog.invalidPriceError'));
        return;
      }
    }
    setIsSaving(true);
    try {
      await api.post('/injectables/lots', {
        produit_id: Number(produitId),
        numero_lot: numeroLot.trim(),
        date_expiration: dateExpiration,
        quantite_initiale: quantite,
        fournisseur: fournisseur || undefined,
        prix_achat_lot: prix,
      });
      toast.success(t('stock.addLotDialog.lotAddedSuccess'));
      onOpenChange(false);
      onCreated();
    } catch (err) {
      toast.error(extractErrorMessage(err, t('stock.addLotDialog.lotAddError')));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('stock.addLotDialog.title')}</DialogTitle>
          <DialogDescription>{t('stock.addLotDialog.description')}</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between"><Label htmlFor="produit">{t('stock.addLotDialog.productLabel')}</Label><Button type="button" variant="outline" size="sm" onClick={() => setShowProductForm((v) => !v)}>{showProductForm ? t('stock.addLotDialog.hide') : t('stock.addLotDialog.newProduct')}</Button></div>
            <select id="produit" value={produitId} onChange={(e) => setProduitId(e.target.value)} className="w-full h-9 px-3 border rounded-md text-sm">
              <option value="">{catalogue.length ? t('stock.addLotDialog.selectProduct') : t('stock.addLotDialog.noProductCreateBelow')}</option>
              {catalogue.map((p) => <option key={p.produit_id} value={p.produit_id}>{p.nom}{p.fabricant ? ` — ${p.fabricant}` : ''}</option>)}
            </select>
            {showProductForm && <div className="rounded-md border bg-muted/30 p-3 space-y-2"><p className="text-sm font-medium">{t('stock.addLotDialog.createInjectableTitle')}</p><Input placeholder={t('stock.addLotDialog.productNamePlaceholder')} value={newProductNom} onChange={(e) => setNewProductNom(e.target.value)} /><div className="grid grid-cols-2 gap-2"><Input placeholder={t('stock.addLotDialog.categoryPlaceholder')} value={newProductCategorie} onChange={(e) => setNewProductCategorie(e.target.value)} /><Input placeholder={t('stock.addLotDialog.unitPlaceholder')} value={newProductUnite} onChange={(e) => setNewProductUnite(e.target.value)} /></div><Input placeholder={t('stock.addLotDialog.manufacturerPlaceholder')} value={newProductFabricant} onChange={(e) => setNewProductFabricant(e.target.value)} /><Button type="button" size="sm" onClick={handleCreateProduct}>{t('stock.addLotDialog.createAndSelect')}</Button></div>}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="numero_lot">{t('stock.addLotDialog.lotNumberLabel')}</Label>
              <Input id="numero_lot" value={numeroLot} onChange={(e) => setNumeroLot(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="date_expiration">{t('stock.addLotDialog.expiryLabel')}</Label>
              <Input id="date_expiration" type="date" value={dateExpiration} onChange={(e) => setDateExpiration(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="quantite">{t('stock.addLotDialog.initialQtyLabel')}</Label>
              <Input id="quantite" type="number" step="0.001" value={quantiteInitiale} onChange={(e) => setQuantiteInitiale(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="prix_achat">{t('stock.addLotDialog.purchasePriceLabel')}</Label>
              <Input id="prix_achat" type="number" step="0.001" value={prixAchat} onChange={(e) => setPrixAchat(e.target.value)} />
            </div>
          </div>
          <div>
            <Label htmlFor="fournisseur">{t('stock.addLotDialog.supplierLabel')}</Label>
            <Input id="fournisseur" value={fournisseur} onChange={(e) => setFournisseur(e.target.value)} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={isSaving}>{isSaving ? <Spinner className="h-4 w-4" /> : t('stock.addLotDialog.submit')}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────

function LotReceptionDialog({ open, onOpenChange, lot, onSuccess }: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  lot: any;
  onSuccess: () => void;
}) {
  const { t } = useTranslation();
  const [quantite, setQuantite] = useState('');
  const [dateExpiration, setDateExpiration] = useState('');
  const [fournisseur, setFournisseur] = useState('');
  const [prixAchat, setPrixAchat] = useState('');
  const [motif, setMotif] = useState('');
  const [reference, setReference] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (open && lot) {
      setQuantite('');
      setDateExpiration(lot.date_expiration || '');
      setFournisseur('');
      setPrixAchat('');
      setMotif('');
      setReference('');
    }
  }, [open, lot]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!lot) return;
    const qty = parseDecimalInput(quantite);
    if (!Number.isFinite(qty) || qty <= 0) {
      toast.error(t('stock.reception.invalidQuantityError'));
      return;
    }
    setIsSaving(true);
    try {
      await api.post('/injectables/reception', {
        lot_id: lot.lot_id,
        code: lot.code || undefined,
        quantite: qty,
        date_expiration: dateExpiration || undefined,
        fournisseur: fournisseur || undefined,
        prix_achat_lot: prixAchat ? parseDecimalInput(prixAchat) : undefined,
        motif: motif || undefined,
        reference: reference || undefined,
      });
      toast.success(t('stock.reception.savedSuccess'));
      onOpenChange(false);
      onSuccess();
    } catch (err) {
      toast.error(extractErrorMessage(err, t('stock.reception.saveError')));
    } finally {
      setIsSaving(false);
    }
  };

  if (!lot) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t('stock.reception.title')}</DialogTitle>
          <DialogDescription>
            {t('stock.reception.productLotLine', { product: lot.produit_nom, lot: lot.numero_lot })}
            <br />
            {t('stock.reception.currentStock', { qty: lot.quantite_restante, unit: lot.unite })}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 py-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="qte_recue">{t('stock.reception.quantityReceived', { unit: lot.unite })}</Label>
              <Input id="qte_recue" type="number" step="0.001" placeholder="0.000" value={quantite} onChange={(e) => setQuantite(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="date_exp">{t('stock.reception.expiryLabel')}</Label>
              <Input id="date_exp" type="date" value={dateExpiration} onChange={(e) => setDateExpiration(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="fournisseur">{t('stock.reception.supplierLabel')}</Label>
              <Input id="fournisseur" value={fournisseur} onChange={(e) => setFournisseur(e.target.value)} placeholder={t('stock.reception.supplierPlaceholder')} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="prix">{t('stock.reception.purchasePriceLabel')}</Label>
              <Input id="prix" type="number" step="0.001" value={prixAchat} onChange={(e) => setPrixAchat(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="reference">{t('stock.reception.deliveryNoteLabel')}</Label>
              <Input id="reference" value={reference} onChange={(e) => setReference(e.target.value)} placeholder={t('stock.reception.deliveryNotePlaceholder')} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="motif">{t('stock.reception.reasonLabel')}</Label>
              <Input id="motif" value={motif} onChange={(e) => setMotif(e.target.value)} placeholder={t('stock.reception.reasonPlaceholder')} />
            </div>
          </div>

          <DialogFooter className="pt-4">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={isSaving}>
              {isSaving ? <Spinner className="h-4 w-4 mr-2" /> : null}
              {t('stock.reception.saveReception')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
