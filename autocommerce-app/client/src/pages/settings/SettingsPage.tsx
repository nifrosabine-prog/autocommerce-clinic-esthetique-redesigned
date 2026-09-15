import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation();
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
      console.error('settings.currencyLoadFailed');
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
      toast.success(t('settings.saved'));

      // Upload logo if selected
      if (logoFile) {
        try {
          await settingsApi.uploadLogo(logoFile);
          toast.success(t('settings.logoUploaded'));
          setLogoFile(null);
          if (heroFile) {
        await settingsApi.uploadHero(heroFile);
        toast.success(t('settings.heroUploaded'));
        setHeroFile(null);
      }
    } catch (err: any) {
          const message = err.response?.data?.detail || t('settings.errors.logoUpload');
          toast.error(message);
        }
      }
    } catch (err: any) {
      const message = err.response?.data?.detail || t('settings.errors.save');
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
          <h1 className="text-3xl font-bold">{t('settings.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('settings.subtitle')}</p>
        </div>

        <Card className="border-blue-200 bg-blue-50/60">
          <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <div className="rounded-lg bg-blue-100 p-2 text-blue-700">
                <ClipboardList className="h-5 w-5" />
              </div>
              <div>
                <h2 className="font-semibold text-blue-950">{t('settings.actsTitle')}</h2>
                <p className="mt-1 text-sm text-blue-900/75">{t('settings.actsDesc')}</p>
              </div>
            </div>
            <Button type="button" onClick={() => setLocation('/settings/actes')} className="shrink-0">
              {t('settings.manageActs')}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('settings.generalInfo')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="nom_clinique">{t('settings.clinicName')}</Label>
              <Input
                id="nom_clinique"
                name="nom_clinique"
                value={formData.nom_clinique || ''}
                onChange={handleInputChange}
                placeholder={t('settings.clinicNamePh')}
              />
            </div>

            <div>
              <Label>{t('settings.logo')}</Label>
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
                  <p className="text-xs text-muted-foreground mt-1">{t('settings.logoHint')}</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('settings.currencyTitle')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="currency_code">{t('settings.currencyCode')}</Label>
                <Input
                  id="currency_code"
                  value={currency.currency_code}
                  onChange={(e) => setCurrency({ ...currency, currency_code: e.target.value.toUpperCase() })}
                  placeholder="TND"
                />
              </div>
              <div>
                <Label htmlFor="currency_symbol">{t('settings.currencySymbol')}</Label>
                <Input
                  id="currency_symbol"
                  value={currency.currency_symbol}
                  onChange={(e) => setCurrency({ ...currency, currency_symbol: e.target.value })}
                  placeholder="DT"
                />
              </div>
            </div>
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              <p className="font-medium">{t('settings.currencyWarningTitle')}</p>
              <p className="mt-1 text-amber-900/80">
                {t('settings.currencyWarning')}
              </p>
            </div>
            <p className="text-xs text-muted-foreground">{t('settings.currencyNote')}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('settings.colorsTitle')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="couleur_primaire">{t('settings.primaryColor')}</Label>
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
              <Label htmlFor="couleur_secondaire">{t('settings.secondaryColor')}</Label>
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
            <CardTitle>{t('settings.landingTitle')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="contenu_titre">{t('settings.titleLabel')}</Label>
              <Input
                id="contenu_titre"
                name="contenu_titre"
                value={formData.contenu_landing?.titre || ''}
                onChange={handleInputChange}
                placeholder={t('settings.titlePh')}
              />
            </div>

            <div>
              <Label htmlFor="contenu_sous_titre">{t('settings.subtitleLabel')}</Label>
              <Input
                id="contenu_sous_titre"
                name="contenu_sous_titre"
                value={formData.contenu_landing?.sous_titre || ''}
                onChange={handleInputChange}
                placeholder={t('settings.subtitlePh')}
              />
            </div>

            <div>
              <Label htmlFor="contenu_adresse">{t('settings.addressLabel')}</Label>
              <Input
                id="contenu_adresse"
                name="contenu_adresse"
                value={formData.contenu_landing?.adresse || ''}
                onChange={handleInputChange}
                placeholder={t('settings.addressPh')}
              />
            </div>

            <div>
              <Label htmlFor="contenu_telephone">{t('settings.phoneLabel')}</Label>
              <Input
                id="contenu_telephone"
                name="contenu_telephone"
                value={formData.contenu_landing?.telephone || ''}
                onChange={handleInputChange}
                placeholder={t('settings.phonePh')}
              />
            </div>

            <div>
              <Label htmlFor="contenu_horaires">{t('settings.hoursLabel')}</Label>
              <Textarea
                id="contenu_horaires"
                name="contenu_horaires"
                value={formData.contenu_landing?.horaires || ''}
                onChange={handleInputChange}
                placeholder={t('settings.hoursPh')}
                rows={3}
              />
            </div>
          </CardContent>
        </Card>


        <Card>
          <CardHeader><CardTitle>{t('settings.socialTitle')}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div><Label htmlFor="contenu_description_longue">{t('settings.longPresentation')}</Label><Textarea id="contenu_description_longue" name="contenu_description_longue" value={formData.contenu_landing?.description_longue || ''} onChange={handleInputChange} rows={5} placeholder={t('settings.presentationPh')} /></div>
            <div className="grid gap-4 md:grid-cols-2"><div><Label htmlFor="contenu_ville">{t('settings.city')}</Label><Input id="contenu_ville" name="contenu_ville" value={formData.contenu_landing?.ville || ''} onChange={handleInputChange} /></div><div><Label htmlFor="contenu_email">{t('settings.email')}</Label><Input id="contenu_email" name="contenu_email" type="email" value={formData.contenu_landing?.email || ''} onChange={handleInputChange} /></div></div>
            <div className="grid gap-4 md:grid-cols-2"><div><Label htmlFor="contenu_whatsapp">{t('settings.whatsapp')}</Label><Input id="contenu_whatsapp" name="contenu_whatsapp" value={formData.contenu_landing?.whatsapp || ''} onChange={handleInputChange} placeholder="216XXXXXXXX" /></div><div><Label htmlFor="contenu_photo_hero_url">{t('settings.heroUrl')}</Label><Input id="contenu_photo_hero_url" name="contenu_photo_hero_url" value={formData.contenu_landing?.photo_hero_url || ''} onChange={handleInputChange} /></div></div>
            <div className="grid gap-4 md:grid-cols-3"><div><Label htmlFor="contenu_instagram">{t('settings.instagram')}</Label><Input id="contenu_instagram" name="contenu_instagram" value={formData.contenu_landing?.instagram || ''} onChange={handleInputChange} /></div><div><Label htmlFor="contenu_facebook">{t('settings.facebook')}</Label><Input id="contenu_facebook" name="contenu_facebook" value={formData.contenu_landing?.facebook || ''} onChange={handleInputChange} /></div><div><Label htmlFor="contenu_tiktok">{t('settings.tiktok')}</Label><Input id="contenu_tiktok" name="contenu_tiktok" value={formData.contenu_landing?.tiktok || ''} onChange={handleInputChange} /></div></div>
            <div><Label>{t('settings.heroPhoto')}</Label><Input type="file" accept="image/*" onChange={handleHeroChange} className="cursor-pointer" /><p className="text-xs text-muted-foreground mt-1">{t('settings.heroHint')}</p></div>
          </CardContent>
        </Card>

        <div className="flex gap-2">
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? t('settings.saving') : t('settings.save')}
          </Button>
        </div>
      </div>
    </DashboardLayout>
  );
}
