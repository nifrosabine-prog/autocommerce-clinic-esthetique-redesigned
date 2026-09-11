import React, { useEffect, useState } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, Edit2, Globe2, Plus, Save, ShieldCheck } from 'lucide-react';
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
  is_gratuit: boolean;
  is_public: boolean;
}

interface ActeForm {
  nom: string;
  categorie: string;
  duree_minutes: number | '';
  prix_base: number | '';
  description: string;
  protocole: string;
  is_active: boolean;
  is_gratuit: boolean;
  is_public: boolean;
}

const emptyForm = (): ActeForm => ({
  nom: '',
  categorie: '',
  duree_minutes: 30,
  prix_base: '',
  description: '',
  protocole: '',
  is_active: true,
  is_gratuit: false,
  is_public: false,
});

const normalize = (value: string) => value.trim().replace(/\s+/g, ' ');

function apiErrorMessage(error: unknown) {
  const response = error as { response?: { data?: { detail?: string | Array<{ msg?: string }> } } };
  const detail = response.response?.data?.detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).filter(Boolean).join(' · ');
  return detail || 'La sauvegarde a échoué. Vérifiez les champs puis réessayez.';
}

export default function ActesPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [actes, setActes] = useState<Acte[]>([]);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingActe, setEditingActe] = useState<Acte | null>(null);
  const [currency, setCurrency] = useState({ currency_code: 'TND', currency_symbol: 'DT' });
  const [formData, setFormData] = useState<ActeForm>(emptyForm);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    void loadActes();
    void loadCurrency();
  }, []);

  const loadCurrency = async () => {
    try {
      const res = await api.get('/settings/currency');
      setCurrency(res.data);
    } catch {
      toast.error('La devise n’a pas pu être chargée.');
    }
  };

  const loadActes = async () => {
    try {
      setIsLoading(true);
      const res = await api.get('/settings/actes');
      setActes(res.data);
    } catch {
      toast.error('Erreur lors du chargement des actes.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleOpenDialog = (acte?: Acte) => {
    setFormErrors({});
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
        is_gratuit: acte.is_gratuit,
        is_public: acte.is_public,
      });
    } else {
      setEditingActe(null);
      setFormData(emptyForm());
    }
    setIsDialogOpen(true);
  };

  const validate = () => {
    const errors: Record<string, string> = {};
    const nom = normalize(formData.nom);
    const categorie = normalize(formData.categorie);
    const duration = Number(formData.duree_minutes);
    const price = Number(formData.prix_base);

    if (nom.length < 2) errors.nom = 'Indiquez un nom d’au moins 2 caractères.';
    if (categorie.length < 2) errors.categorie = 'Indiquez une catégorie d’au moins 2 caractères.';
    if (!Number.isInteger(duration) || duration < 5 || duration > 480) {
      errors.duree_minutes = 'La durée doit être comprise entre 5 et 480 minutes.';
    }
    if (formData.prix_base === '' || Number.isNaN(price) || price < 0) {
      errors.prix_base = 'Indiquez un prix valide.';
    } else if (!formData.is_gratuit && price <= 0) {
      errors.prix_base = 'Un acte payant doit avoir un prix strictement supérieur à 0.';
    }
    if (formData.is_public && !formData.is_active) {
      errors.is_public = 'Un acte doit être actif avant d’être publié sur la landing.';
    }
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSave = async () => {
    if (!validate()) {
      toast.error('Certaines informations sont incomplètes ou incohérentes.');
      return;
    }
    const payload = {
      ...formData,
      nom: normalize(formData.nom),
      categorie: normalize(formData.categorie),
      duree_minutes: Number(formData.duree_minutes),
      prix_base: Number(formData.prix_base),
    };
    try {
      setIsSaving(true);
      if (editingActe) {
        await api.patch(`/settings/actes/${editingActe.id}`, payload);
        toast.success('Acte mis à jour.');
      } else {
        await api.post('/settings/actes', payload);
        toast.success('Acte créé.');
      }
      setIsDialogOpen(false);
      await loadActes();
    } catch (error) {
      toast.error(apiErrorMessage(error));
    } finally {
      setIsSaving(false);
    }
  };

  const updateField = <K extends keyof ActeForm>(field: K, value: ActeForm[K]) => {
    setFormData((current) => ({ ...current, [field]: value }));
    if (formErrors[field]) setFormErrors((current) => ({ ...current, [field]: '' }));
  };

  return (
    <DashboardLayout>
      <div className="mx-auto max-w-7xl space-y-6 pb-10">
        <section className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:flex-row md:items-end md:justify-between md:p-7">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal-700">Paramètres cliniques</p>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-950 md:text-3xl">Catalogue des actes</h1>
            <p className="max-w-2xl text-sm leading-6 text-slate-600">
              Gérez le référentiel interne et choisissez explicitement les soins publiés sur la landing de réservation.
            </p>
          </div>
          <Button className="bg-teal-700 text-white shadow-sm hover:bg-teal-800" onClick={() => handleOpenDialog()}>
            <Plus className="mr-2 h-4 w-4" /> Nouvel acte
          </Button>
        </section>

        <Card className="overflow-hidden border-slate-200 shadow-sm">
          <CardHeader className="border-b border-slate-100 bg-slate-50/70 px-5 py-4">
            <CardTitle className="flex items-center gap-2 text-base font-semibold text-slate-900">
              <ShieldCheck className="h-4 w-4 text-teal-700" /> Référentiel et publication
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {isLoading ? (
              <div className="flex justify-center p-10"><Spinner /></div>
            ) : actes.length === 0 ? (
              <div className="p-10 text-center text-sm text-slate-600">Aucun acte n’est encore enregistré dans ce catalogue.</div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="border-slate-100 hover:bg-transparent">
                      <TableHead>Acte</TableHead>
                      <TableHead>Durée</TableHead>
                      <TableHead>Prix</TableHead>
                      <TableHead>État interne</TableHead>
                      <TableHead>Landing</TableHead>
                      <TableHead className="text-right">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {actes.map((acte) => (
                      <TableRow key={acte.id} className="border-slate-100">
                        <TableCell>
                          <p className="font-medium text-slate-950">{acte.nom}</p>
                          <p className="mt-0.5 text-xs capitalize text-slate-500">{acte.categorie}</p>
                        </TableCell>
                        <TableCell className="text-slate-700">{acte.duree_minutes} min</TableCell>
                        <TableCell className="font-medium text-slate-800">
                          {acte.is_gratuit ? 'Gratuit' : `${Number(acte.prix_base).toFixed(3)} ${currency.currency_symbol}`}
                        </TableCell>
                        <TableCell>
                          <Badge className={acte.is_active ? 'bg-emerald-50 text-emerald-800 hover:bg-emerald-50' : 'bg-slate-100 text-slate-600 hover:bg-slate-100'}>
                            {acte.is_active ? 'Actif' : 'Archivé'}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge className={acte.is_public ? 'bg-teal-50 text-teal-800 hover:bg-teal-50' : 'bg-slate-100 text-slate-600 hover:bg-slate-100'}>
                            <Globe2 className="mr-1 h-3 w-3" /> {acte.is_public ? 'Publié' : 'Non publié'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button variant="ghost" size="sm" aria-label={`Modifier ${acte.nom}`} onClick={() => handleOpenDialog(acte)}>
                            <Edit2 className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editingActe ? 'Modifier l’acte' : 'Créer un acte'}</DialogTitle>
            <DialogDescription>Les champs marqués d’un astérisque sont requis. La publication reste un choix distinct de l’activation interne.</DialogDescription>
          </DialogHeader>
          <div className="space-y-5 py-3">
            <div className="grid gap-2">
              <Label htmlFor="nom">Nom de l’acte *</Label>
              <Input id="nom" required aria-invalid={Boolean(formErrors.nom)} value={formData.nom} onChange={(e) => updateField('nom', e.target.value)} placeholder="Ex. Consultation esthétique" />
              {formErrors.nom && <p className="text-xs text-red-700">{formErrors.nom}</p>}
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="grid gap-2 sm:col-span-1">
                <Label htmlFor="categorie">Catégorie *</Label>
                <Input id="categorie" required aria-invalid={Boolean(formErrors.categorie)} value={formData.categorie} onChange={(e) => updateField('categorie', e.target.value)} placeholder="Consultation" />
                {formErrors.categorie && <p className="text-xs text-red-700">{formErrors.categorie}</p>}
              </div>
              <div className="grid gap-2">
                <Label htmlFor="duree">Durée (min) *</Label>
                <Input id="duree" type="number" min="5" max="480" step="5" required aria-invalid={Boolean(formErrors.duree_minutes)} value={formData.duree_minutes} onChange={(e) => updateField('duree_minutes', e.target.value === '' ? '' : Number(e.target.value))} />
                {formErrors.duree_minutes && <p className="text-xs text-red-700">{formErrors.duree_minutes}</p>}
              </div>
              <div className="grid gap-2">
                <Label htmlFor="prix">Prix ({currency.currency_symbol}) *</Label>
                <Input id="prix" type="number" min="0" step="0.001" required aria-invalid={Boolean(formErrors.prix_base)} value={formData.prix_base} onChange={(e) => updateField('prix_base', e.target.value === '' ? '' : Number(e.target.value))} disabled={formData.is_gratuit} placeholder={formData.is_gratuit ? '0.000' : 'Ex. 250.000'} />
                {formErrors.prix_base && <p className="text-xs text-red-700">{formErrors.prix_base}</p>}
              </div>
            </div>
            <div className="grid gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm">
              <label className="flex cursor-pointer items-start gap-3 text-slate-700">
                <input type="checkbox" checked={formData.is_gratuit} onChange={(e) => updateField('is_gratuit', e.target.checked)} className="mt-0.5 h-4 w-4 accent-teal-700" />
                <span><strong className="font-medium text-slate-900">Acte gratuit</strong><br />Autorise un prix à 0 uniquement pour un acte explicitement gratuit.</span>
              </label>
              <label className="flex cursor-pointer items-start gap-3 text-slate-700">
                <input type="checkbox" checked={formData.is_active} onChange={(e) => updateField('is_active', e.target.checked)} className="mt-0.5 h-4 w-4 accent-teal-700" />
                <span><strong className="font-medium text-slate-900">Actif dans le catalogue interne</strong><br />Un acte archivé ne peut ni être choisi ni publié.</span>
              </label>
              <label className="flex cursor-pointer items-start gap-3 text-slate-700">
                <input type="checkbox" checked={formData.is_public} onChange={(e) => updateField('is_public', e.target.checked)} className="mt-0.5 h-4 w-4 accent-teal-700" />
                <span><strong className="font-medium text-slate-900">Publier sur la landing</strong><br />Le soin devient visible et réservable depuis le catalogue public.</span>
              </label>
              {formErrors.is_public && <p className="text-xs text-red-700">{formErrors.is_public}</p>}
            </div>
            <div className="grid gap-2">
              <Label htmlFor="description">Description publique courte</Label>
              <Textarea id="description" value={formData.description} onChange={(e) => updateField('description', e.target.value)} rows={2} placeholder="Informations visibles dans le catalogue, sans promesse médicale." />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="protocole">Notes de protocole internes</Label>
              <Textarea id="protocole" value={formData.protocole} onChange={(e) => updateField('protocole', e.target.value)} rows={3} placeholder="Informations réservées à l’équipe clinique." />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDialogOpen(false)} disabled={isSaving}>Annuler</Button>
            <Button className="bg-teal-700 text-white hover:bg-teal-800" onClick={handleSave} disabled={isSaving}>
              {isSaving ? <Spinner className="mr-2 h-4 w-4" /> : <Save className="mr-2 h-4 w-4" />} Sauvegarder
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </DashboardLayout>
  );
}
