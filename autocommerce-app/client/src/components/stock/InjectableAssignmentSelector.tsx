import { useTranslation } from 'react-i18next';
import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import { api } from '@/lib/api';
import { toast } from 'sonner';
import { extractErrorMessage } from '@/lib/errors';

interface AvailableLot {
  lot_id: number;
  produit_id: number;
  produit_nom: string;
  fabricant?: string;
  numero_lot: string;
  quantite_restante: number;
  unite: string;
  date_expiration: string;
}

export function InjectableAssignmentSelector({
  patientId,
  praticienId,
  onAssigned,
}: {
  patientId: number;
  praticienId: number;
  onAssigned?: () => void;
}) {
  const { t } = useTranslation();
  const [lots, setLots] = useState<AvailableLot[]>([]);
  const [selectedLotId, setSelectedLotId] = useState('');
  const [quantite, setQuantite] = useState('');
  const [typeInjection, setTypeInjection] = useState('');
  const [notes, setNotes] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  const loadLots = async () => {
    try {
      setIsLoading(true);
      const response = await api.get('/injectables/lots');
      setLots(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      toast.error(extractErrorMessage(error, t('componentUi.loadLotsError')));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadLots();
  }, []);

  const selectedLot = lots.find((lot) => String(lot.lot_id) === selectedLotId);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const quantity = Number(quantite);
    if (!selectedLot || !quantity || quantity <= 0 || quantity > selectedLot.quantite_restante) {
      toast.error(t('componentUi.selectLotQuantity'));
      return;
    }
    if (!praticienId) {
      toast.error(t('componentUi.doctorNotFound'));
      return;
    }

    try {
      setIsSaving(true);
      await api.post('/injectables/utilisation', {
        lot_id: selectedLot.lot_id,
        patient_id: patientId,
        praticien_id: praticienId,
        quantite: quantity,
        unite: selectedLot.unite,
        type_injection: typeInjection || undefined,
        notes: notes || undefined,
      });
      toast.success(t('componentUi.injectableAssigned'));
      setSelectedLotId('');
      setQuantite('');
      setTypeInjection('');
      setNotes('');
      await loadLots();
      onAssigned?.();
    } catch (error) {
      toast.error(extractErrorMessage(error, t('componentUi.injectableAssignmentError')));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card className="border-primary/20 bg-primary/[0.02]">
      <CardHeader>
        <CardTitle className="text-base">{t('componentUi.assignInjectable')}</CardTitle>
        <p className="text-sm text-muted-foreground">
          {t('componentUi.injectableDescription')}
        </p>
      </CardHeader>
      <CardContent>
        {isLoading ? <div className="flex justify-center py-4"><Spinner /></div> : (
          <form onSubmit={handleSubmit} className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="injectable-lot">{t('componentUi.productLot')}</Label>
              <select
                id="injectable-lot"
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={selectedLotId}
                onChange={(event) => setSelectedLotId(event.target.value)}
                required
              >
                <option value="">{t('componentUi.chooseProductLot')}</option>
                {lots.map((lot) => (
                  <option key={lot.lot_id} value={lot.lot_id}>
                    {t('componentUi.injectableLotOption', {
                      product: lot.fabricant ? `${lot.produit_nom} · ${lot.fabricant}` : lot.produit_nom,
                      lot: lot.numero_lot,
                      quantity: lot.quantite_restante,
                      unit: lot.unite,
                    })}
                  </option>
                ))}
              </select>
              {lots.length === 0 && <p className="text-sm text-amber-700">{t('componentUi.availableLotsEmpty')}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="injectable-quantity">{t('componentUi.quantityRequired', { unit: selectedLot?.unite || t('componentUi.unit') })}</Label>
              <Input
                id="injectable-quantity"
                type="number"
                min="0.001"
                max={selectedLot?.quantite_restante}
                step="0.001"
                value={quantite}
                onChange={(event) => setQuantite(event.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="injectable-type">{t('componentUi.injectionType')}</Label>
              <Input id="injectable-type" value={typeInjection} onChange={(event) => setTypeInjection(event.target.value)} placeholder={t('componentUi.injectionPlaceholder')} />
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="injectable-notes">{t('componentUi.clinicalNote')}</Label>
              <Input id="injectable-notes" value={notes} onChange={(event) => setNotes(event.target.value)} placeholder={t('componentUi.clinicalNotePlaceholder')} />
            </div>
            <div className="md:col-span-2 flex justify-end">
              <Button type="submit" disabled={isSaving || !selectedLot || !praticienId}>
                {isSaving ? <Spinner className="mr-2 h-4 w-4" /> : null}
                {t('componentUi.assignAndDebit')}
              </Button>
            </div>
          </form>
        )}
      </CardContent>
    </Card>
  );
}

export default InjectableAssignmentSelector;


