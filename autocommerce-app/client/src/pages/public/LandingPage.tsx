import React, { useEffect, useMemo, useState } from 'react';
import { useBranding } from '@/contexts/BrandingContext';
import {
  publicApi,
  type PublicActe,
  type PublicDisponibilite,
  type PublicPraticien,
  type PublicContent,
} from '@/lib/api';
import { Button } from '@/components/ui/button';
import LanguageSwitcher from '@/components/LanguageSwitcher';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Spinner } from '@/components/ui/spinner';
import { Calendar, Phone, MapPin, Clock, Stethoscope, UserRound, MessageCircle } from 'lucide-react';
import { toast } from 'sonner';

const todayLocalDate = () => {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

export default function LandingPage() {
  const { branding: privateBranding } = useBranding();

  const [isBootstrapLoading, setIsBootstrapLoading] = useState(true);
  const [isSlotsLoading, setIsSlotsLoading] = useState(false);
  const [praticiens, setPraticiens] = useState<PublicPraticien[]>([]);
  const [actes, setActes] = useState<PublicActe[]>([]);
  const [publicContent, setPublicContent] = useState<PublicContent | null>(null);
  // Sur le domaine public, le branding privé est volontairement bloqué par Nginx.
  // Le contenu public consolidé devient donc la source prioritaire.
  const effectiveBranding = publicContent?.branding ?? privateBranding;
  const [availabilities, setAvailabilities] = useState<PublicDisponibilite[]>([]);
  const [bootstrapError, setBootstrapError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    nom: '',
    prenom: '',
    telephone: '',
    praticien_id: '',
    acte_id: '',
    date: todayLocalDate(),
    date_heure: '',
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [bookingPrivacyAccepted, setBookingPrivacyAccepted] = useState(false);

  const [callbackData, setCallbackData] = useState({ nom: '', telephone: '', email: '', message: '' });
  const [isCallbackSubmitting, setIsCallbackSubmitting] = useState(false);
  const [callbackPrivacyAccepted, setCallbackPrivacyAccepted] = useState(false);
  const [callbackConfirmation, setCallbackConfirmation] = useState<number | null>(null);
  const [bookingConfirmation, setBookingConfirmation] = useState<{
    id: number;
    duplicate: boolean;
    status: string;
  } | null>(null);

  useEffect(() => {
    const bootstrap = async () => {
      try {
        setIsBootstrapLoading(true);
        // Les endpoints publics historiques restent la source de secours du
        // formulaire de réservation. Le contenu consolidé enrichit la vitrine
        // mais ne doit pas empêcher un patient de réserver si ce service est
        // momentanément indisponible.
        const [praticiensResponse, actesResponse] = await Promise.all([
          publicApi.getPraticiens(),
          publicApi.getActes(),
        ]);

        setPraticiens(praticiensResponse.data);
        setActes(actesResponse.data);
        setBootstrapError(null);

        // Le contenu marketing est chargé en arrière-plan : il ne doit jamais
        // bloquer l'ouverture immédiate du formulaire public.
        void publicApi.getContent()
          .then((contentResponse) => {
            setPublicContent(contentResponse.data);
            if (Array.isArray(contentResponse.data.all_actes) && contentResponse.data.all_actes.length > 0) {
              setActes(contentResponse.data.all_actes as PublicActe[]);
            }
          })
          .catch(() => {
            setPublicContent(null);
          });
      } catch (err) {
        console.error('Failed to bootstrap landing page:', err);
        setBootstrapError('Le module de réservation est temporairement indisponible.');
      } finally {
        setIsBootstrapLoading(false);
      }
    };

    bootstrap();
  }, []);

  useEffect(() => {
    const loadDisponibilites = async () => {
      if (!formData.praticien_id || !formData.date) {
        setAvailabilities([]);
        setFormData((current) => ({ ...current, date_heure: '' }));
        return;
      }

      try {
        setIsSlotsLoading(true);
        const response = await publicApi.getDisponibilites(Number(formData.praticien_id), {
          date: formData.date,
          acte_id: formData.acte_id ? Number(formData.acte_id) : undefined,
        });
        setAvailabilities(response.data.creneaux || []);

        setFormData((current) => {
          const stillExists = (response.data.creneaux || []).some(
            (slot) => slot.datetime === current.date_heure
          );
          return stillExists ? current : { ...current, date_heure: '' };
        });
      } catch (err: any) {
        console.error('Failed to load availabilities:', err);
        setAvailabilities([]);
        setFormData((current) => ({ ...current, date_heure: '' }));
        const message = err.response?.data?.detail || 'Impossible de charger les disponibilités';
        toast.error(message);
      } finally {
        setIsSlotsLoading(false);
      }
    };

    loadDisponibilites();
  }, [formData.praticien_id, formData.acte_id, formData.date]);

  const featuredServices = useMemo(() => {
    const fromBranding = effectiveBranding?.contenu_landing?.services_mis_en_avant || [];
    if (fromBranding.length > 0) return fromBranding;
    return actes.slice(0, 3).map((acte) => acte.nom);
  }, [effectiveBranding?.contenu_landing?.services_mis_en_avant, actes]);

  const selectedActe = useMemo(
    () => actes.find((acte) => acte.id === Number(formData.acte_id)),
    [actes, formData.acte_id]
  );

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target;
    setFormData((current) => ({
      ...current,
      [name]: value,
      ...(name === 'praticien_id' || name === 'acte_id' || name === 'date'
        ? { date_heure: '' }
        : {}),
    }));
  };


  const handleCallbackSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (callbackData.nom.trim().length < 2 || !callbackData.telephone.match(/^\+?[0-9 ]{8,15}$/)) {
      toast.error('Veuillez renseigner un nom et un téléphone valides');
      return;
    }
    if (!callbackPrivacyAccepted) {
      toast.error('Veuillez accepter la notice de confidentialité');
      return;
    }
    try {
      setIsCallbackSubmitting(true);
      const response = await publicApi.submitCallback({ ...callbackData, nom: callbackData.nom.trim(), telephone: callbackData.telephone.trim() });
      setCallbackConfirmation(response.data.lead_id);
      setCallbackData({ nom: '', telephone: '', email: '', message: '' });
      setCallbackPrivacyAccepted(false);
      toast.success('Votre demande de rappel a bien été transmise à la clinique.');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Impossible d’enregistrer votre demande de rappel');
    } finally {
      setIsCallbackSubmitting(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.telephone.match(/^\+?[0-9 ]{8,15}$/)) {
      toast.error('Format de téléphone invalide');
      return;
    }

    if (!formData.date_heure) {
      toast.error('Veuillez sélectionner un créneau disponible');
      return;
    }
    if (!bookingPrivacyAccepted) {
      toast.error('Veuillez accepter la notice de confidentialité');
      return;
    }

    try {
      setIsSubmitting(true);

      const response = await publicApi.reserveRdv({
        nom: formData.nom,
        prenom: formData.prenom,
        telephone: formData.telephone,
        praticien_id: Number(formData.praticien_id),
        acte_id: Number(formData.acte_id),
        date_heure: formData.date_heure,
      });
      const confirmation = response.data;
      setBookingConfirmation({
        id: confirmation.booking_request_id,
        duplicate: Boolean(confirmation.duplicate),
        status: confirmation.statut,
      });
      toast.success(
        confirmation.duplicate
          ? 'Cette demande existe déjà et attend la confirmation de la clinique.'
          : 'Demande de rendez-vous reçue — confirmation par la clinique à venir.'
      );
      setFormData({
        nom: '',
        prenom: '',
        telephone: '',
        praticien_id: '',
        acte_id: '',
        date: todayLocalDate(),
        date_heure: '',
      });
      setBookingPrivacyAccepted(false);
      setAvailabilities([]);
    } catch (err: any) {
      if (err.response?.status === 429) {
        toast.error('Trop de tentatives. Réessayez dans une minute.');
      } else {
        const message = err.response?.data?.detail || 'Erreur lors de la réservation';
        toast.error(message);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#f5f3ee] text-[#172126]">
      <header className="absolute inset-x-0 top-0 z-50 border-b border-white/20 bg-[#172126]/35 text-white backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-5 lg:px-8">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex h-11 w-11 items-center justify-center rounded-full border border-[#d7b77a]/60 bg-[#d7b77a]/15 text-[#f4d99f]">
              {effectiveBranding?.logo_url ? (
                <img src={effectiveBranding.logo_url} alt="Logo" className="h-8 w-8 object-contain" />
              ) : (
                <Stethoscope className="h-5 w-5" />
              )}
            </div>
            <div className="min-w-0">
              <p className="text-[10px] font-medium uppercase tracking-[0.28em] text-[#f4d99f]">Médecine esthétique</p>
              <h1 className="truncate text-lg font-semibold tracking-tight">
              {effectiveBranding?.nom_clinique || 'Clinique'}
            </h1>
            </div>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <LanguageSwitcher />
            {effectiveBranding?.contenu_landing?.telephone && <a href={`tel:${effectiveBranding.contenu_landing.telephone}`} className="hidden rounded-full border border-white/30 px-3 py-2 text-xs font-medium text-white sm:inline-flex"><Phone className="mr-1 h-3.5 w-3.5" />Appeler</a>}
            {effectiveBranding?.contenu_landing?.whatsapp && <a href={`https://wa.me/${effectiveBranding.contenu_landing.whatsapp.replace(/[^0-9]/g, '')}`} target="_blank" rel="noreferrer" className="hidden rounded-full bg-[#25D366] px-3 py-2 text-xs font-semibold text-white sm:inline-flex"><MessageCircle className="mr-1 h-3.5 w-3.5" />WhatsApp</a>}
            <a href="/login" className="hidden rounded-full border border-white/30 px-4 py-2 text-xs font-medium text-white transition hover:border-[#f4d99f] hover:text-[#f4d99f] sm:inline-flex">
              Accès professionnel
            </a>
          </div>
        </div>
      </header>

      <section
        className="relative min-h-[760px] overflow-hidden px-5 pb-16 pt-36 sm:px-8 sm:pb-20 sm:pt-44 lg:px-12"
        style={{
          backgroundImage: effectiveBranding?.contenu_landing?.photo_hero_url
            ? `linear-gradient(120deg, rgba(23,33,38,0.96) 0%, rgba(23,33,38,0.68) 48%, rgba(23,33,38,0.32) 100%), url("${effectiveBranding.contenu_landing.photo_hero_url}")`
            : 'linear-gradient(120deg, #172126 0%, #344b4d 48%, #8da7a0 100%), radial-gradient(circle at 78% 20%, rgba(244,217,159,0.24), transparent 28%)',
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      >
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-gradient-to-r from-[#101d21]/90 via-[#172126]/65 to-[#172126]/25"
        />
        <div className="relative mx-auto grid max-w-7xl items-center gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:gap-20">
          <div className="max-w-2xl">
            <div className="mb-6 flex items-center gap-3 text-xs font-medium uppercase tracking-[0.24em] text-[#f4d99f]">
              <span className="h-px w-10 bg-[#d7b77a]" />
              Beauté naturelle, expertise médicale
            </div>
            <h2 className="max-w-xl text-5xl font-semibold leading-[1.04] tracking-[-0.04em] text-white drop-shadow-sm sm:text-6xl lg:text-7xl">
              {publicContent?.branding?.contenu_landing?.titre || effectiveBranding?.contenu_landing?.titre || 'Bienvenue'}
            </h2>
            <p className="mb-6 max-w-lg text-lg leading-8 text-white/80 sm:text-xl">
              {publicContent?.branding?.contenu_landing?.sous_titre || effectiveBranding?.contenu_landing?.sous_titre || 'Votre clinique esthétique de confiance'}
            </p>
            {publicContent?.marketing_summary && (
              <p className="mb-9 max-w-lg text-base italic leading-7 text-[#f4d99f]/90">
                {publicContent.marketing_summary}
              </p>
            )}

            <div className="mb-8 flex flex-wrap gap-3">
              <a href="#rappel" className="inline-flex items-center rounded-full bg-[#f4d99f] px-5 py-3 text-sm font-semibold text-[#172126] transition hover:bg-white">Être rappelé</a>
              {effectiveBranding?.contenu_landing?.telephone && <a href={`tel:${effectiveBranding.contenu_landing.telephone}`} className="inline-flex items-center rounded-full border border-white/35 px-5 py-3 text-sm font-semibold text-white"><Phone className="mr-2 h-4 w-4" />Téléphoner</a>}
              {effectiveBranding?.contenu_landing?.whatsapp && <a href={`https://wa.me/${effectiveBranding.contenu_landing.whatsapp.replace(/[^0-9]/g, '')}`} target="_blank" rel="noreferrer" className="inline-flex items-center rounded-full border border-[#25D366]/70 px-5 py-3 text-sm font-semibold text-white"><MessageCircle className="mr-2 h-4 w-4" />WhatsApp</a>}
            </div>

            {publicContent?.expertises && Object.keys(publicContent.expertises).length > 0 && (
              <div className="space-y-6">
                <p className="text-xs font-medium uppercase tracking-[0.2em] text-white/65 border-b border-white/10 pb-2">
                  Nos Expertises
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {Object.entries(publicContent.expertises).map(([cat, acts]: [string, any]) => (
                    <div key={cat} className="space-y-2">
                      <h3 className="text-[#f4d99f] text-sm font-bold uppercase tracking-wider">{cat}</h3>
                      <ul className="space-y-1">
                        {acts.slice(0, 4).map((a: any) => (
                          <li key={a.id} className="text-white/70 text-sm flex items-start gap-2">
                            <span className="mt-1.5 h-1 w-1 rounded-full bg-[#d7b77a] shrink-0" />
                            <span>{a.nom}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <Card className="border-white/70 bg-[#fbfaf7]/95 shadow-[0_30px_90px_rgba(10,28,32,0.28)] backdrop-blur-xl">
            <CardHeader className="border-b border-[#172126]/10 px-6 pb-5 pt-6 sm:px-8">
              <CardTitle className="flex items-center gap-3 text-lg tracking-tight text-[#172126]">
                <Calendar className="w-5 h-5" />
                Réserver un rendez-vous
              </CardTitle>
            </CardHeader>
            <CardContent className="px-6 pb-7 pt-6 sm:px-8">
              {bookingConfirmation && (
                <div
                  role="status"
                  className="mb-5 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900"
                >
                  <p className="font-semibold">
                    {bookingConfirmation.duplicate ? 'Demande déjà enregistrée' : 'Demande reçue'}
                  </p>
                  <p className="mt-1">
                    Référence #{bookingConfirmation.id}. La clinique doit encore confirmer ce créneau ;
                    l’accueil le retrouvera dans les demandes publiques à traiter.
                  </p>
                </div>
              )}
              {isBootstrapLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Spinner className="h-5 w-5" />
                </div>
              ) : bootstrapError ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                  {bootstrapError} Veuillez contacter la clinique pour prendre rendez-vous.
                </div>
              ) : praticiens.length === 0 || actes.length === 0 ? (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
                  Les disponibilités de réservation seront ouvertes après le paramétrage des praticiens et des prestations.
                </div>
              ) : (
                <>
                  <p className="mb-4 text-sm leading-6 text-muted-foreground">
                    Cette réservation crée une demande auprès de la clinique. L’accueil vérifiera le créneau,
                    créera ou retrouvera votre dossier, puis vous confirmera le rendez-vous.
                  </p>
                  <div className="mb-4 rounded-lg border border-teal-200 bg-teal-50 p-3 text-xs leading-5 text-teal-950"><strong>À savoir :</strong> cette étape autorise uniquement le traitement de votre demande et de vos coordonnées. Le consentement éclairé propre à un acte médical vous sera présenté séparément par le praticien avant tout soin.</div>
                  <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="prenom">Prénom</Label>
                      <Input id="prenom" name="prenom" value={formData.prenom} onChange={handleInputChange} required />
                    </div>
                    <div>
                      <Label htmlFor="nom">Nom</Label>
                      <Input id="nom" name="nom" value={formData.nom} onChange={handleInputChange} required />
                    </div>
                  </div>

                  <div>
                    <Label htmlFor="telephone">Téléphone</Label>
                    <Input
                      id="telephone"
                      name="telephone"
                      type="tel"
                      value={formData.telephone}
                      onChange={handleInputChange}
                      placeholder="+216 XX XXX XXX"
                      required
                    />
                    <p className="text-xs text-muted-foreground mt-1">Format international ou local, 8 chiffres minimum</p>
                  </div>

                  <div>
                    <Label htmlFor="praticien_id">Praticien</Label>
                    <select
                      id="praticien_id"
                      name="praticien_id"
                      value={formData.praticien_id}
                      onChange={handleInputChange}
                      className="w-full px-3 py-2 border rounded-md bg-background"
                      required
                    >
                      <option value="">Sélectionner un praticien</option>
                      {praticiens.map((praticien) => (
                        <option key={praticien.id} value={praticien.id}>
                          {praticien.nom_complet}
                          {praticien.specialite ? ` — ${praticien.specialite}` : ''}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <Label htmlFor="acte_id">Acte</Label>
                    <select
                      id="acte_id"
                      name="acte_id"
                      value={formData.acte_id}
                      onChange={handleInputChange}
                      className="w-full px-3 py-2 border rounded-md bg-background"
                      required
                    >
                      <option value="">Sélectionner un acte</option>
                      {actes.map((acte) => (
                        <option key={acte.id} value={acte.id}>
                          {acte.nom}
                        </option>
                      ))}
                    </select>
                    {selectedActe?.description && (
                      <p className="text-xs text-muted-foreground mt-1">{selectedActe.description}</p>
                    )}
                  </div>

                  <div>
                    <Label htmlFor="date">Date souhaitée</Label>
                    <Input
                      id="date"
                      name="date"
                      type="date"
                      min={todayLocalDate()}
                      value={formData.date}
                      onChange={handleInputChange}
                      required
                    />
                  </div>

                  <div>
                    <Label htmlFor="date_heure">Créneau disponible</Label>
                    <select
                      id="date_heure"
                      name="date_heure"
                      value={formData.date_heure}
                      onChange={handleInputChange}
                      className="w-full px-3 py-2 border rounded-md bg-background"
                      required
                      disabled={!formData.praticien_id || isSlotsLoading}
                    >
                      <option value="">
                        {isSlotsLoading
                          ? 'Chargement des créneaux...'
                          : 'Sélectionner un créneau'}
                      </option>
                      {availabilities.map((slot) => (
                        <option key={slot.datetime} value={slot.datetime}>
                          {slot.heure}
                        </option>
                      ))}
                    </select>
                    {isSlotsLoading && (
                      <div className="flex items-center gap-2 text-xs text-muted-foreground mt-2">
                        <Spinner className="h-3.5 w-3.5" />
                        Chargement des disponibilités
                      </div>
                    )}
                    {!isSlotsLoading && formData.praticien_id && availabilities.length === 0 && (
                      <p className="text-xs text-muted-foreground mt-2">
                        Aucun créneau disponible pour cette date.
                      </p>
                    )}
                  </div>

                  <label className="flex items-start gap-3 text-xs leading-5 text-muted-foreground">
                    <input
                      type="checkbox"
                      checked={bookingPrivacyAccepted}
                      onChange={(event) => setBookingPrivacyAccepted(event.target.checked)}
                      required
                      className="mt-1 h-4 w-4 rounded border-slate-300"
                    />
                    <span>J’accepte que mes coordonnées soient utilisées uniquement pour traiter cette demande. Cet accord ne vaut pas consentement éclairé à un acte médical. <a className="underline hover:text-foreground" href="#confidentialite">Voir la notice de confidentialité</a>.</span>
                  </label>
                  <Button type="submit" className="w-full" disabled={isSubmitting || isBootstrapLoading}>
                    {isSubmitting ? (
                      <>
                        <Spinner className="mr-2 h-4 w-4" />
                        Réservation en cours...
                      </>
                    ) : (
                      'Réserver'
                    )}
                    </Button>
                  </form>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </section>


      <section id="rappel" className="bg-[#172126] px-5 py-14 text-white sm:px-8 lg:px-12">
        <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
          <div><p className="mb-3 text-xs font-medium uppercase tracking-[0.22em] text-[#f4d99f]">Un premier échange, simplement</p><h3 className="text-3xl font-semibold tracking-tight">Vous préférez être contacté ?</h3><p className="mt-3 max-w-lg text-white/70">Laissez votre numéro. L’accueil de la clinique vous rappelle pour comprendre votre besoin et vous orienter.</p></div>
          <Card className="border-white/10 bg-white/10 text-white"><CardContent className="p-6">
            {callbackConfirmation && <div className="mb-4 rounded-lg border border-emerald-300/30 bg-emerald-400/10 p-3 text-sm">Demande reçue — référence #{callbackConfirmation}.</div>}
            <form onSubmit={handleCallbackSubmit} className="grid gap-4 sm:grid-cols-2"><div><Label htmlFor="callback_nom" className="text-white">Nom pour le rappel</Label><Input id="callback_nom" value={callbackData.nom} onChange={(e) => setCallbackData({ ...callbackData, nom: e.target.value })} required className="mt-1 bg-white text-[#172126]" /></div><div><Label htmlFor="callback_telephone" className="text-white">Téléphone pour le rappel</Label><Input id="callback_telephone" type="tel" value={callbackData.telephone} onChange={(e) => setCallbackData({ ...callbackData, telephone: e.target.value })} required className="mt-1 bg-white text-[#172126]" /></div><div className="sm:col-span-2"><Label htmlFor="callback_email" className="text-white">Email (facultatif)</Label><Input id="callback_email" type="email" value={callbackData.email} onChange={(e) => setCallbackData({ ...callbackData, email: e.target.value })} className="mt-1 bg-white text-[#172126]" /></div><div className="sm:col-span-2"><Label htmlFor="callback_message" className="text-white">Votre besoin (facultatif)</Label><Input id="callback_message" value={callbackData.message} onChange={(e) => setCallbackData({ ...callbackData, message: e.target.value })} className="mt-1 bg-white text-[#172126]" /></div><label className="sm:col-span-2 flex items-start gap-3 text-xs leading-5 text-white/70"><input type="checkbox" checked={callbackPrivacyAccepted} onChange={(event) => setCallbackPrivacyAccepted(event.target.checked)} required className="mt-1 h-4 w-4 rounded border-white/40" /><span>J’accepte que mes coordonnées soient utilisées uniquement pour être recontacté. Cet accord n’est pas le consentement éclairé nécessaire avant un acte. <a className="underline hover:text-white" href="#confidentialite">Notice de confidentialité</a>.</span></label><Button type="submit" disabled={isCallbackSubmitting} className="sm:col-span-2 bg-[#f4d99f] text-[#172126] hover:bg-white">{isCallbackSubmitting ? 'Envoi…' : 'Demander un rappel'}</Button></form>
          </CardContent></Card>
        </div>
      </section>

      <section className="border-y border-[#172126]/10 bg-[#fbfaf7] px-5 py-10 sm:px-8 lg:px-12">
        <div className="mx-auto grid max-w-7xl grid-cols-1 gap-4 md:grid-cols-3">
          {effectiveBranding?.contenu_landing?.adresse && (
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-start gap-3">
                  <MapPin className="w-5 h-5 text-primary mt-1 flex-shrink-0" />
                  <div>
                    <p className="font-semibold text-sm">Adresse</p>
                    <p className="text-sm text-muted-foreground whitespace-pre-line">
                      {effectiveBranding.contenu_landing.adresse}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {effectiveBranding?.contenu_landing?.telephone && (
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-start gap-3">
                  <Phone className="w-5 h-5 text-primary mt-1 flex-shrink-0" />
                  <div>
                    <p className="font-semibold text-sm">Téléphone</p>
                    <a href={`tel:${effectiveBranding.contenu_landing.telephone}`} className="text-sm text-primary hover:underline">
                      {effectiveBranding.contenu_landing.telephone}
                    </a>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {effectiveBranding?.contenu_landing?.horaires && (
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-start gap-3">
                  <Clock className="w-5 h-5 text-primary mt-1 flex-shrink-0" />
                  <div>
                    <p className="font-semibold text-sm">Horaires</p>
                    <p className="text-sm text-muted-foreground whitespace-pre-line">
                      {effectiveBranding.contenu_landing.horaires}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </section>

      {praticiens.length > 0 && (
        <section className="bg-[#f5f3ee] px-5 py-16 sm:px-8 lg:px-12">
          <div className="mx-auto max-w-7xl">
            <div className="mb-6">
              <p className="mb-3 text-xs font-medium uppercase tracking-[0.22em] text-[#b0884b]">Une équipe dédiée</p>
              <h3 className="text-3xl font-semibold tracking-tight text-[#172126]">Nos praticiens</h3>
              <p className="mt-2 max-w-xl text-[#172126]/65">Des professionnels sélectionnés pour une prise en charge précise, douce et confidentielle.</p>
            </div>
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {praticiens.map((praticien) => (
                <Card key={praticien.id} className="border-[#172126]/10 bg-[#fbfaf7] shadow-[0_12px_35px_rgba(23,33,38,0.06)] transition hover:-translate-y-1 hover:shadow-[0_18px_45px_rgba(23,33,38,0.12)]">
                  <CardContent className="pt-6">
                    <div className="flex items-start gap-3">
                      <UserRound className="w-5 h-5 text-primary mt-1" />
                      <div>
                        <p className="font-semibold">{praticien.nom_complet}</p>
                        {praticien.specialite && (
                          <p className="text-sm text-muted-foreground">{praticien.specialite}</p>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>
      )}

      <section id="confidentialite" className="bg-[#fbfaf7] px-5 py-8 text-sm text-[#172126]/75 sm:px-8 lg:px-12">
        <div className="mx-auto max-w-7xl">
          <h3 className="font-semibold text-[#172126]">Notice de confidentialité</h3>
          <p className="mt-2 max-w-3xl leading-6">Les informations transmises sur cette page servent uniquement à traiter votre demande de rendez-vous ou de rappel. Elles sont communiquées à la clinique sélectionnée et conservées pendant la durée nécessaire à ce traitement, conformément à sa politique de confidentialité. Cet accord de traitement de la demande est distinct du consentement éclairé, spécifique à chaque acte médical, qui sera recueilli par le praticien avant réalisation du soin. Vous pouvez demander l’accès, la rectification ou la suppression de vos données auprès de la clinique.</p>
        </div>
      </section>

      <footer className="border-t border-[#172126]/10 bg-[#172126] px-5 py-9 text-white/65 sm:px-8 lg:px-12">
        <div className="mx-auto max-w-7xl text-center text-sm">
          <p>&copy; {new Date().getFullYear()} {effectiveBranding?.nom_clinique || 'Clinique'}. Tous droits réservés.</p>
          <div className="mt-4 flex flex-wrap justify-center gap-4 text-xs">
            {effectiveBranding?.contenu_landing?.instagram && <a href={effectiveBranding.contenu_landing.instagram} target="_blank" rel="noreferrer" className="hover:text-white">Instagram</a>}
            {effectiveBranding?.contenu_landing?.facebook && <a href={effectiveBranding.contenu_landing.facebook} target="_blank" rel="noreferrer" className="hover:text-white">Facebook</a>}
            {effectiveBranding?.contenu_landing?.tiktok && <a href={effectiveBranding.contenu_landing.tiktok} target="_blank" rel="noreferrer" className="hover:text-white">TikTok</a>}
            {effectiveBranding?.contenu_landing?.email && <a href={`mailto:${effectiveBranding.contenu_landing.email}`} className="hover:text-white">Email</a>}
          </div>
        </div>
      </footer>
    </div>
  );
}
