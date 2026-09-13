import React, { useState, useEffect } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { api, BrandingResponse, settingsApi } from '@/lib/api';
import { useBranding } from '@/contexts/BrandingContext';
import { useLocation } from 'wouter';
import { Spinner } from '@/components/ui/spinner';
import { ClipboardList, Upload } from 'lucide-react';
import { toast } from 'sonner';

export default function SettingsPage() {
  const { branding, applyTheme } = useBranding();
  const [, setLocation] = useLocation();
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [formData, setFormData] = useState<Partial<BrandingResponse>>({});
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [heroFile, setHeroFile] = useState<File | null>(null);
  const [currency, setCurrency] = useState({ currency_code: 'TND', currency_symbol: 'DT' });

  useEffect(() => {
    if (branding) {
      setFormData({
        nom_clinique: branding.nom_clinique,
        couleur_primaire: branding.couleur_primaire,
        couleur_secondaire: branding.couleur_secondaire,
        contenu_landing: branding.contenu_landing,
      });
    }
    loadCurrency();
  }, [branding]);

  const loadCurrency = async () => {
    try {
      const res = await api.get('/settings/currency');
      setCurrency(res.data);
    } catch (err) {
      console.error('Erreur lors du chargement de la devise');
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    if (name.startsWith('contenu_')) {
      const key = name.replace('contenu_', '');
      setFormData({
        ...formData,
        contenu_landing: {
          ...formData.contenu_landing,
          [key]: value,
        },
      });
    } else {
      setFormData({
        ...formData,
        [name]: value,
      });
    }
  };

  const handleLogoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      setLogoFile(e.target.files[0]);
    }
  };

  const handleHeroChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) setHeroFile(e.target.files[0]);
  };

  const handleSave = async () => {
    try {
      setIsSaving(true);

      // Update currency
      await api.put('/settings/currency', currency);

      // Update branding settings
      const response = await settingsApi.updateBranding(formData);
      applyTheme(response.data);
      toast.success('Paramètres sauvegardés');

      // Upload logo if selected
      if (logoFile) {
        try {
          await settingsApi.uploadLogo(logoFile);
          toast.success('Logo téléchargé');
          setLogoFile(null);
          if (heroFile) {
        await settingsApi.uploadHero(heroFile);
        toast.success('Photo de présentation téléchargée');
        setHeroFile(null);
      }
    } catch (err: any) {
          const message = err.response?.data?.detail || 'Erreur lors du téléchargement du logo';
          toast.error(message);
        }
      }
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Erreur lors de la sauvegarde';
      toast.error(message);
    } finally {
      setIsSaving(false);
    }
  };

  if (!branding) {
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
      <div className="space-y-6 max-w-2xl">
        <div>
          <h1 className="text-3xl font-bold">Paramètres</h1>
          <p className="text-muted-foreground mt-1">Configuration du branding et de la clinique</p>
        </div>

        <Card className="border-blue-200 bg-blue-50/60">
          <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <div className="rounded-lg bg-blue-100 p-2 text-blue-700">
                <ClipboardList className="h-5 w-5" />
              </div>
              <div>
                <h2 className="font-semibold text-blue-950">Configuration des actes médicaux</h2>
                <p className="mt-1 text-sm text-blue-900/75">Gérez le catalogue des soins, les durées et les tarifs utilisés pour les rendez-vous et la facturation.</p>
              </div>
            </div>
            <Button type="button" onClick={() => setLocation('/settings/actes')} className="shrink-0">
              Gérer les actes
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Informations générales</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="nom_clinique">Nom de la clinique</Label>
              <Input
                id="nom_clinique"
                name="nom_clinique"
                value={formData.nom_clinique || ''}
                onChange={handleInputChange}
                placeholder="Nom de votre clinique"
              />
            </div>

            <div>
              <Label>Logo</Label>
              <div className="flex items-center gap-4">
                {branding.logo_url && (
                  <img src={branding.logo_url} alt="Logo" className="h-16 w-16 object-contain border rounded" />
                )}
                <div className="flex-1">
                  <Input
                    type="file"
                    accept="image/*"
                    onChange={handleLogoChange}
                    className="cursor-pointer"
                  />
                  <p className="text-xs text-muted-foreground mt-1">PNG, JPG (max 2 Mo)</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Devise Globale</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="currency_code">Code Devise (ex: TND, EUR)</Label>
                <Input
                  id="currency_code"
                  value={currency.currency_code}
                  onChange={(e) => setCurrency({ ...currency, currency_code: e.target.value.toUpperCase() })}
                  placeholder="TND"
                />
              </div>
              <div>
                <Label htmlFor="currency_symbol">Symbole (ex: DT, €)</Label>
                <Input
                  id="currency_symbol"
                  value={currency.currency_symbol}
                  onChange={(e) => setCurrency({ ...currency, currency_symbol: e.target.value })}
                  placeholder="DT"
                />
              </div>
            </div>
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              <p className="font-medium">Important — historique financier</p>
              <p className="mt-1 text-amber-900/80">
                Le changement de devise s’applique uniquement aux nouvelles opérations. Les factures existantes conservent leur montant,
                leur devise, leur TVA et leur historique d’origine. Aucune conversion automatique n’est effectuée.
              </p>
            </div>
            <p className="text-xs text-muted-foreground">Cette devise sera utilisée pour les nouveaux actes, nouvelles factures et nouveaux rapports.</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Couleurs</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="couleur_primaire">Couleur primaire</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="couleur_primaire"
                  name="couleur_primaire"
                  type="color"
                  value={formData.couleur_primaire || '#0066CC'}
                  onChange={handleInputChange}
                  className="w-16 h-10 cursor-pointer"
                />
                <Input
                  type="text"
                  value={formData.couleur_primaire || '#0066CC'}
                  onChange={handleInputChange}
                  name="couleur_primaire"
                  placeholder="#0066CC"
                  className="flex-1"
                />
              </div>
            </div>

            <div>
              <Label htmlFor="couleur_secondaire">Couleur secondaire</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="couleur_secondaire"
                  name="couleur_secondaire"
                  type="color"
                  value={formData.couleur_secondaire || '#6B7280'}
                  onChange={handleInputChange}
                  className="w-16 h-10 cursor-pointer"
                />
                <Input
                  type="text"
                  value={formData.couleur_secondaire || '#6B7280'}
                  onChange={handleInputChange}
                  name="couleur_secondaire"
                  placeholder="#6B7280"
                  className="flex-1"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Contenu de la landing page</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="contenu_titre">Titre</Label>
              <Input
                id="contenu_titre"
                name="contenu_titre"
                value={formData.contenu_landing?.titre || ''}
                onChange={handleInputChange}
                placeholder="Titre de votre clinique"
              />
            </div>

            <div>
              <Label htmlFor="contenu_sous_titre">Sous-titre</Label>
              <Input
                id="contenu_sous_titre"
                name="contenu_sous_titre"
                value={formData.contenu_landing?.sous_titre || ''}
                onChange={handleInputChange}
                placeholder="Sous-titre"
              />
            </div>

            <div>
              <Label htmlFor="contenu_adresse">Adresse</Label>
              <Input
                id="contenu_adresse"
                name="contenu_adresse"
                value={formData.contenu_landing?.adresse || ''}
                onChange={handleInputChange}
                placeholder="Adresse de la clinique"
              />
            </div>

            <div>
              <Label htmlFor="contenu_telephone">Téléphone</Label>
              <Input
                id="contenu_telephone"
                name="contenu_telephone"
                value={formData.contenu_landing?.telephone || ''}
                onChange={handleInputChange}
                placeholder="Numéro de téléphone"
              />
            </div>

            <div>
              <Label htmlFor="contenu_horaires">Horaires</Label>
              <Textarea
                id="contenu_horaires"
                name="contenu_horaires"
                value={formData.contenu_landing?.horaires || ''}
                onChange={handleInputChange}
                placeholder="Horaires d'ouverture"
                rows={3}
              />
            </div>
          </CardContent>
        </Card>


        <Card>
          <CardHeader><CardTitle>Présentation, coordonnées et réseaux sociaux</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div><Label htmlFor="contenu_description_longue">Présentation longue</Label><Textarea id="contenu_description_longue" name="contenu_description_longue" value={formData.contenu_landing?.description_longue || ''} onChange={handleInputChange} rows={5} placeholder="Présentez l’expertise et les engagements de la clinique." /></div>
            <div className="grid gap-4 md:grid-cols-2"><div><Label htmlFor="contenu_ville">Ville</Label><Input id="contenu_ville" name="contenu_ville" value={formData.contenu_landing?.ville || ''} onChange={handleInputChange} /></div><div><Label htmlFor="contenu_email">Email</Label><Input id="contenu_email" name="contenu_email" type="email" value={formData.contenu_landing?.email || ''} onChange={handleInputChange} /></div></div>
            <div className="grid gap-4 md:grid-cols-2"><div><Label htmlFor="contenu_whatsapp">WhatsApp</Label><Input id="contenu_whatsapp" name="contenu_whatsapp" value={formData.contenu_landing?.whatsapp || ''} onChange={handleInputChange} placeholder="216XXXXXXXX" /></div><div><Label htmlFor="contenu_photo_hero_url">URL photo hero (facultatif)</Label><Input id="contenu_photo_hero_url" name="contenu_photo_hero_url" value={formData.contenu_landing?.photo_hero_url || ''} onChange={handleInputChange} /></div></div>
            <div className="grid gap-4 md:grid-cols-3"><div><Label htmlFor="contenu_instagram">Instagram</Label><Input id="contenu_instagram" name="contenu_instagram" value={formData.contenu_landing?.instagram || ''} onChange={handleInputChange} /></div><div><Label htmlFor="contenu_facebook">Facebook</Label><Input id="contenu_facebook" name="contenu_facebook" value={formData.contenu_landing?.facebook || ''} onChange={handleInputChange} /></div><div><Label htmlFor="contenu_tiktok">TikTok</Label><Input id="contenu_tiktok" name="contenu_tiktok" value={formData.contenu_landing?.tiktok || ''} onChange={handleInputChange} /></div></div>
            <div><Label>Photo de présentation</Label><Input type="file" accept="image/*" onChange={handleHeroChange} className="cursor-pointer" /><p className="text-xs text-muted-foreground mt-1">JPG, PNG ou WebP, 2 Mo maximum.</p></div>
          </CardContent>
        </Card>

        <div className="flex gap-2">
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? 'Sauvegarde...' : 'Sauvegarder'}
          </Button>
        </div>
      </div>
    </DashboardLayout>
  );
}
