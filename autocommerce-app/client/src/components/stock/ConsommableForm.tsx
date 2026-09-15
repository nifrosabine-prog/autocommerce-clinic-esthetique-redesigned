import { useTranslation } from 'react-i18next';
import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { toast } from 'sonner';
import { extractErrorMessage } from '@/lib/errors';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';

interface ConsommableFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

export function ConsommableForm({
  open, onOpenChange, onCreated }: ConsommableFormProps) {
  const { t } = useTranslation();
  const [formData, setFormData] = useState({
    nom: '',
    categorie: '',
    unite: 'pièce',
    stock_actuel: '0',
    seuil_alerte: '5',
    stock_minimum: '2',
    prix_unitaire: '0'
  });
  const [isSaving, setIsSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      await api.post('/consommables/create', {
        ...formData,
        stock_actuel: Number(formData.stock_actuel),
        seuil_alerte: Number(formData.seuil_alerte),
        stock_minimum: Number(formData.stock_minimum),
        prix_unitaire: Number(formData.prix_unitaire),
      });
      toast.success(t('componentUi.consumableCreated'));
      onCreated();
      onOpenChange(false);
      setFormData({
        nom: '',
        categorie: '',
        unite: 'pièce',
        stock_actuel: '0',
        seuil_alerte: '5',
        stock_minimum: '2',
        prix_unitaire: '0'
      });
    } catch (err) {
      toast.error(extractErrorMessage(err, t('componentUi.createConsumableError')));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>{t('componentUi.newConsumable')}</DialogTitle>
          <DialogDescription>
            {t('componentUi.addConsumableDescription')}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-4">
          <div className="space-y-2">
            <Label htmlFor="nom">{t('componentUi.name')} *</Label>
            <Input 
              id="nom" 
              value={formData.nom} 
              onChange={(e) => setFormData({...formData, nom: e.target.value})} 
              required 
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="categorie">{t('componentUi.category')} *</Label>
              <Input 
                id="categorie" 
                value={formData.categorie} 
                onChange={(e) => setFormData({...formData, categorie: e.target.value})} 
                placeholder={t('componentUi.categoryPlaceholder')}
                required 
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="unite">{t('componentUi.unit')} *</Label>
              <select 
                id="unite" 
                value={formData.unite} 
                onChange={(e) => setFormData({...formData, unite: e.target.value})}
                className="w-full h-9 px-3 border rounded-md text-sm"
              >
                <option value="pièce">{t('componentUi.piece')}</option>
                <option value="boite">{t('componentUi.box')}</option>
                <option value="paquet">{t('componentUi.pack')}</option>
                <option value="rouleau">{t('componentUi.roll')}</option>
                <option value="litre">{t('componentUi.litre')}</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="stock">{t('componentUi.initialStock')}</Label>
              <Input 
                id="stock" 
                type="number" 
                value={formData.stock_actuel} 
                onChange={(e) => setFormData({...formData, stock_actuel: e.target.value})} 
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="seuil">{t('componentUi.alertThreshold')}</Label>
              <Input 
                id="seuil" 
                type="number" 
                value={formData.seuil_alerte} 
                onChange={(e) => setFormData({...formData, seuil_alerte: e.target.value})} 
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="min">{t('componentUi.minimum')}</Label>
              <Input 
                id="min" 
                type="number" 
                value={formData.stock_minimum} 
                onChange={(e) => setFormData({...formData, stock_minimum: e.target.value})} 
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="prix">{t('componentUi.unitPrice')}</Label>
            <Input 
              id="prix" 
              type="number" 
              step="0.001" 
              value={formData.prix_unitaire} 
              onChange={(e) => setFormData({...formData, prix_unitaire: e.target.value})} 
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t('componentUi.cancel')}
            </Button>
            <Button type="submit" disabled={isSaving}>
              {isSaving ? <Spinner className="h-4 w-4" /> : t('componentUi.create')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
