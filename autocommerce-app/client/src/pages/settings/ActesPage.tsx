import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { Plus, Edit2, Trash2, Save, X } from 'lucide-react';
import { toast } from 'sonner';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';

interface Acte {
  id: number;
  nom: string;
  categorie: string;
  duree_minutes: number;
  prix_base: number;
  description?: string;
  protocole?: string;
  is_active: boolean;
}

export default function ActesPage() {
  const { t } = useTranslation();
  const [isLoading, setIsLoading] = useState(true);
  const [actes, setActes] = useState<Acte[]>([]);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingActe, setEditingActe] = useState<Acte | null>(null);
  const [currency, setCurrency] = useState({ currency_code: 'TND', currency_symbol: 'DT' });
  const [formData, setFormData] = useState({
    nom: '',
    categorie: '',
    duree_minutes: 30,
    prix_base: 0,
    description: '',
    protocole: '',
    is_active: true,
  });

  useEffect(() => {
    loadActes();
    loadCurrency();
  }, []);

  const loadCurrency = async () => {
    try {
      const res = await api.get('/settings/currency');
      setCurrency(res.data);
    } catch (err) {
      console.error('Erreur devise');
    }
  };

  const loadActes = async () => {
    try {
      setIsLoading(true);
      const res = await api.get('/settings/actes');
      setActes(res.data);
    } catch (err) {
      toast.error(t('settings.actesLoadError'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleOpenDialog = (acte?: Acte) => {
    if (acte) {
      setEditingActe(acte);
      setFormData({
        nom: acte.nom,
        categorie: acte.categorie,
        duree_minutes: acte.duree_minutes,
        prix_base: acte.prix_base,
        description: acte.description || '',
        protocole: acte.protocole || '',
        is_active: acte.is_active,
      });
    } else {
      setEditingActe(null);
      setFormData({
        nom: '',
        categorie: '',
        duree_minutes: 30,
        prix_base: 0,
        description: '',
        protocole: '',
        is_active: true,
      });
    }
    setIsDialogOpen(true);
  };

  const handleSave = async () => {
    try {
      if (editingActe) {
        await api.patch(`/settings/actes/${editingActe.id}`, formData);
        toast.success(t('settings.acteUpdated'));
      } else {
        await api.post('/settings/actes', formData);
        toast.success(t('settings.acteCreated'));
      }
      setIsDialogOpen(false);
      loadActes();
    } catch (err) {
      toast.error(t('settings.acteSaveError'));
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold">{t('settings.actesPageTitle')}</h1>
            <p className="text-muted-foreground mt-1">{t('settings.actesPageSubtitle')}</p>
          </div>
          <Button onClick={() => handleOpenDialog()}>
            <Plus className="w-4 h-4 mr-2" /> {t('settings.newActe')}
          </Button>
        </div>

        <Card>
          <CardContent className="p-0">
            {isLoading ? (
              <div className="flex justify-center p-8"><Spinner /></div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('settings.acteName')}</TableHead>
                    <TableHead>{t('settings.category')}</TableHead>
                    <TableHead>{t('settings.durationMinutes')}</TableHead>
                    <TableHead>{t('settings.basePrice', { symbol: currency.currency_symbol })}</TableHead>
                    <TableHead>{t('settings.status')}</TableHead>
                    <TableHead className="text-right">{t('settings.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {actes.map((acte) => (
                    <TableRow key={acte.id}>
                      <TableCell className="font-medium">{acte.nom}</TableCell>
                      <TableCell className="capitalize">{acte.categorie}</TableCell>
                      <TableCell>{acte.duree_minutes}</TableCell>
                      <TableCell>{Number(acte.prix_base).toFixed(3)}</TableCell>
                      <TableCell>
                        <span className={`px-2 py-1 rounded-full text-xs ${acte.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                          {acte.is_active ? t('settings.active') : t('settings.inactive')}
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="sm" onClick={() => handleOpenDialog(acte)}>
                          <Edit2 className="w-4 h-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingActe ? t('settings.editActe') : t('settings.newActe')}</DialogTitle>
            <DialogDescription>{t('settings.acteDialogDesc')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="nom">{t('settings.acteNameRequired')}</Label>
              <Input id="nom" value={formData.nom} onChange={(e) => setFormData({...formData, nom: e.target.value})} placeholder={t('settings.acteNamePlaceholder')} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="categorie">{t('settings.category')}</Label>
                <Input id="categorie" value={formData.categorie} onChange={(e) => setFormData({...formData, categorie: e.target.value})} placeholder={t('settings.categoryPlaceholder')} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="prix">{t('settings.basePrice', { symbol: currency.currency_symbol })}</Label>
                <Input id="prix" type="number" step="0.001" value={formData.prix_base} onChange={(e) => setFormData({...formData, prix_base: Number(e.target.value)})} />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="description">{t('settings.description')}</Label>
              <Textarea id="description" value={formData.description} onChange={(e) => setFormData({...formData, description: e.target.value})} rows={2} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="protocole">{t('settings.protocolInstructions')}</Label>
              <Textarea id="protocole" value={formData.protocole} onChange={(e) => setFormData({...formData, protocole: e.target.value})} rows={3} placeholder={t('settings.protocolPlaceholder')} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDialogOpen(false)}>{t('settings.cancel')}</Button>
            <Button onClick={handleSave}>{t('settings.save')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </DashboardLayout>
  );
}
