import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { LANDING_TRANSLATIONS, type LandingLanguage } from '@/i18n/landingTranslations';
import { LANDING_SERVICES } from '@/i18n/landingServicesTranslations';
import { LANDING_FORM } from '@/i18n/landingFormTranslations';
import { LANDING_EXTRA } from '@/i18n/landingExtraTranslations';
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
import LinaChatWidget from '@/components/public/LinaChatWidget';
import {
  ArrowRight,
  Calendar,
  Check,
  Clock,
  HeartHandshake,
  MapPin,
  MessageCircle,
  Menu,
  Phone,
  X,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  UserRound,
} from 'lucide-react';
import { toast } from 'sonner';

const formatLocalDate = (value: Date) => {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const todayLocalDate = () => formatLocalDate(new Date());

const nextBusinessDate = (isoDate: string) => {
  const [year, month, day] = isoDate.split('-').map(Number);
  const candidate = new Date(year, month - 1, day, 12);
  do {
    candidate.setDate(candidate.getDate() + 1);
  } while (candidate.getDay() === 0 || candidate.getDay() === 6);
  return formatLocalDate(candidate);
};

type BookingPeriod = 'matin' | 'apres_midi' | '';

const getBookingPeriod = (slot: PublicDisponibilite): Exclude<BookingPeriod, ''> => {
  const hour = Number(slot.heure.split(':')[0]);
  return hour < 12 ? 'matin' : 'apres_midi';
};

const periodLabel = (period: Exclude<BookingPeriod, ''>, slots: PublicDisponibilite[]) => {
  const periodSlots = slots.filter((slot) => getBookingPeriod(slot) === period);
  if (periodSlots.length === 0) return period === 'matin' ? 'Matin — indisponible' : 'Après-midi — indisponible';
  const first = periodSlots[0].heure;
  const last = periodSlots[periodSlots.length - 1].heure;
  return period === 'matin' ? `Matin (${first}–${last})` : `Après-midi (${first}–${last})`;
};

const MBA_LOGO_URL = '/branding/mba-clinic-monogram.png';
const MBA_HERO_URL = '/branding/mba-clinic-waiting-room.jpg';
const SERVICE_IMAGES = ['/branding/consultation-esthetique.jpg', '/branding/soin-visage-premium.jpg', '/branding/injection-esthetique.jpg'];
const SERVICE_DETAILS = [
  { title: 'Consultation esthétique', description: 'Un premier échange médical pour comprendre vos attentes, analyser votre peau et construire un parcours réaliste, naturel et personnalisé.', points: ['Écoute et analyse personnalisées', 'Recommandations transparentes', 'Plan de soins adapté à votre rythme'] },
  { title: 'Soin visage premium', description: 'Un soin expert pensé pour raviver l’éclat, hydrater et apaiser la peau dans un cadre calme, précis et confortable.', points: ['Diagnostic de peau', 'Gestes doux et produits sélectionnés', 'Conseils simples pour prolonger les effets'] },
  { title: 'Injection esthétique', description: 'Une approche médicale mesurée, fondée sur l’équilibre des volumes et la recherche d’un résultat subtil, sans promesse irréaliste.', points: ['Évaluation médicale préalable', 'Protocole expliqué étape par étape', 'Suivi après le soin'] },
];

export default function LandingPage() {
  const { branding: privateBranding } = useBranding();
  const { t, i18n } = useTranslation();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [expandedService, setExpandedService] = useState<number | null>(null);
  const language = ((i18n.resolvedLanguage || i18n.language || 'fr').split('-')[0] as LandingLanguage);
  const copy = LANDING_TRANSLATIONS[language] || LANDING_TRANSLATIONS.fr;
  const formCopy = LANDING_FORM[language] || LANDING_FORM.fr;
  const extraCopy = LANDING_EXTRA[language] || LANDING_EXTRA.fr;
  const isEnglish = language === 'en';

  useEffect(() => {
    const isArabic = language === 'ar';
    document.documentElement.lang = language;
    document.documentElement.dir = isArabic ? 'rtl' : 'ltr';
    return () => { document.documentElement.dir = 'ltr'; };
  }, [language]);

  const [isBootstrapLoading, setIsBootstrapLoading] = useState(true);
  const [isSlotsLoading, setIsSlotsLoading] = useState(false);
  const [praticiens, setPraticiens] = useState<PublicPraticien[]>([]);
  const [actes, setActes] = useState<PublicActe[]>([]);
  const [publicContent, setPublicContent] = useState<PublicContent | null>(null);
  // Sur le domaine public, le branding privé est volontairement bloqué par Nginx.
  // Le contenu public consolidé devient donc la source prioritaire.
  const effectiveBranding = publicContent?.branding ?? privateBranding;
  const landingContent = effectiveBranding?.contenu_landing;
  const clinicName = effectiveBranding?.nom_clinique && effectiveBranding.nom_clinique !== 'Clinique'
    ? effectiveBranding.nom_clinique
    : 'MBA Clinic';
  const clinicPhone = landingContent?.telephone || '';
  const clinicWhatsapp = landingContent?.whatsapp || '';
  const clinicCity = landingContent?.ville || (language === 'fr' ? 'Adresse communiquée par la clinique' : 'Clinic address to be configured');
  const heroImage = landingContent?.photo_hero_url || MBA_HERO_URL;
  const heroTitle = !landingContent?.titre || landingContent.titre === 'Bienvenue'
    ? 'L’art de révéler votre beauté naturelle.'
    : landingContent.titre;
  const heroSubtitle = !landingContent?.sous_titre || landingContent.sous_titre === 'Votre clinique esthétique de confiance'
    ? 'Une médecine esthétique précise, douce et personnalisée au cœur de Tunis.'
    : landingContent.sous_titre;
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
    periode: '' as BookingPeriod,
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
        const slots = response.data.creneaux || [];

        if (slots.length === 0 && formData.date === todayLocalDate()) {
          const nextDate = nextBusinessDate(formData.date);
          setAvailabilities([]);
          setFormData((current) => ({ ...current, date: nextDate, date_heure: '', periode: '' }));
          toast.info('Aucun créneau restant aujourd’hui. Nous vous proposons le prochain jour ouvré.');
          return;
        }

        setAvailabilities(slots);

        setFormData((current) => {
          const selectedPeriod = current.periode as BookingPeriod;
          const selectedPeriodSlot = selectedPeriod
            ? slots.find((slot) => getBookingPeriod(slot) === selectedPeriod)
            : undefined;
          return selectedPeriodSlot
            ? { ...current, date_heure: selectedPeriodSlot.datetime }
            : { ...current, date_heure: '', periode: '' };
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
        ? { date_heure: '', periode: '' as BookingPeriod }
        : {}),
    }));
  };


  const handleBookingPeriodChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const periode = event.target.value as BookingPeriod;
    const slot = periode
      ? availabilities.find((candidate) => getBookingPeriod(candidate) === periode)
      : undefined;
    setFormData((current) => ({
      ...current,
      periode,
      date_heure: slot?.datetime || '',
    }));
    if (periode && !slot) {
      toast.error(`La période ${periode === 'matin' ? 'du matin' : 'de l’après-midi'} n’est pas disponible pour cette date.`);
    }
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
        periode: '',
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
    <div className="landing-mba min-h-screen bg-[#f5f3ee] text-[#172126]">
      <header className="absolute inset-x-0 top-0 z-50 border-b border-white/15 bg-[#172126]/80 text-white backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3 sm:px-6 sm:py-4 lg:px-8">
          <a href="#accueil" className="flex min-w-0 items-center gap-2.5" aria-label={`${clinicName}, accueil`} onClick={() => setIsMobileMenuOpen(false)}>
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-[#d7b77a]/60 bg-[#d7b77a]/10 p-1.5 sm:h-12 sm:w-12 sm:p-2"><img src={effectiveBranding?.logo_url || MBA_LOGO_URL} alt="Monogramme MBA Clinic" className="h-full w-full object-contain" /></span>
            <span className="min-w-0"><span className="hidden text-[10px] font-medium uppercase tracking-[0.2em] text-[#f4d99f] sm:block">{t('landing.eyebrow')}</span><span className="block truncate font-serif text-lg font-medium tracking-[0.06em] text-white sm:text-xl">MBA <span className="font-sans text-[0.62em] font-semibold tracking-[0.22em] text-[#f4d99f]">CLINIC</span></span></span>
          </a>
          <nav className="hidden items-center gap-6 text-sm text-white/75 lg:flex" aria-label={t('landing.navLabel')}><a href="#qui-sommes-nous" className="transition hover:text-[#f4d99f]">{t('landing.nav.about')}</a><a href="#nos-actes" className="transition hover:text-[#f4d99f]">{t('landing.nav.services')}</a><a href="#contact" className="transition hover:text-[#f4d99f]">{t('landing.nav.contact')}</a></nav>
          <div className="flex shrink-0 items-center gap-1.5 sm:gap-3"><div className="hidden sm:block"><LanguageSwitcher /></div>{clinicPhone && <a href={`tel:${clinicPhone}`} aria-label={t('landing.call')} className="hidden rounded-full border border-white/30 px-3 py-2 text-xs font-medium text-white transition hover:border-[#f4d99f] hover:text-[#f4d99f] sm:inline-flex"><Phone className="mr-1 h-3.5 w-3.5" />{t('landing.call')}</a>}<a href="#reservation" onClick={() => setIsMobileMenuOpen(false)} className="rounded-full bg-[#f4d99f] px-3.5 py-2.5 text-[11px] font-semibold text-[#172126] shadow-[0_8px_22px_rgba(244,217,159,0.2)] transition hover:bg-white sm:px-4 sm:text-xs">{t('landing.book')}</a><button type="button" className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-white/25 text-white lg:hidden" aria-label={isMobileMenuOpen ? t('landing.closeMenu') : t('landing.openMenu')} aria-expanded={isMobileMenuOpen} onClick={() => setIsMobileMenuOpen((open) => !open)}>{isMobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}</button></div>
        </div>
        {isMobileMenuOpen && <div className="border-t border-white/10 bg-[#172126] px-4 py-4 lg:hidden"><nav className="grid gap-2" aria-label={t('landing.navLabel')}><a onClick={() => setIsMobileMenuOpen(false)} href="#qui-sommes-nous" className="rounded-xl px-4 py-3 text-sm text-white/85 hover:bg-white/10">{t('landing.nav.about')}</a><a onClick={() => setIsMobileMenuOpen(false)} href="#nos-actes" className="rounded-xl px-4 py-3 text-sm text-white/85 hover:bg-white/10">{t('landing.nav.services')}</a><a onClick={() => setIsMobileMenuOpen(false)} href="#contact" className="rounded-xl px-4 py-3 text-sm text-white/85 hover:bg-white/10">{t('landing.nav.contact')}</a><div className="px-4 py-2 sm:hidden"><LanguageSwitcher /></div></nav></div>}
      </header>

      <section
        id="accueil"
        className="relative min-h-[760px] overflow-hidden px-4 pb-12 pt-32 sm:px-8 sm:pb-20 sm:pt-44 lg:px-12"
        style={{
          backgroundImage: `linear-gradient(108deg, rgba(23,33,38,0.98) 0%, rgba(23,33,38,0.86) 38%, rgba(23,33,38,0.46) 72%, rgba(23,33,38,0.28) 100%), url("${heroImage}")`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      >
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-gradient-to-r from-[#101d21]/90 via-[#172126]/65 to-[#172126]/25"
        />
        <div className="relative mx-auto grid max-w-7xl items-center gap-8 sm:gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:gap-20">
          <div className="max-w-2xl">
            <div className="mb-6 flex items-center gap-3 text-xs font-medium uppercase tracking-[0.24em] text-[#f4d99f]">
              <span className="h-px w-10 bg-[#d7b77a]" />
              {copy.aboutLabel} · {language === 'ar' ? 'تونس' : 'Tunis'}
            </div>
            <h2 className="max-w-2xl font-serif text-[2.7rem] font-medium leading-[1.04] tracking-[-0.035em] text-white drop-shadow-sm sm:text-6xl lg:text-7xl">
              {landingContent?.titre && landingContent.titre !== 'Bienvenue' && language === 'fr' ? landingContent.titre : extraCopy.heroTitle}
            </h2>
            <p className="mb-6 mt-6 max-w-xl text-lg leading-8 text-white/82 sm:text-xl">
              {landingContent?.sous_titre && landingContent.sous_titre !== 'Votre clinique esthétique de confiance' && language === 'fr' ? landingContent.sous_titre : extraCopy.heroSubtitle}
            </p>
            <p className="mb-9 max-w-xl text-base leading-7 text-white/68">
              {extraCopy.heroText}
            </p>

            <div className="mb-8 flex flex-col gap-3 sm:mb-10 sm:flex-row sm:flex-wrap">
              <a href="#reservation" className="group inline-flex min-h-12 items-center justify-center rounded-full bg-[#f4d99f] px-5 py-3 text-sm font-semibold text-[#172126] shadow-[0_14px_30px_rgba(244,217,159,0.2)] transition hover:bg-white">
                {copy.book} <ArrowRight className="ml-2 h-4 w-4 transition group-hover:translate-x-1" />
              </a>
              <a href="#qui-sommes-nous" className="inline-flex min-h-12 items-center justify-center rounded-full border border-white/35 px-5 py-3 text-sm font-semibold text-white transition hover:border-[#f4d99f] hover:text-[#f4d99f]">{language === 'fr' ? 'Découvrir MBA Clinic' : language === 'ar' ? 'اكتشف MBA Clinic' : language === 'it' ? 'Scopri MBA Clinic' : language === 'de' ? 'MBA Clinic entdecken' : 'Discover MBA Clinic'}</a>
            </div>

            <div className="grid max-w-xl grid-cols-1 gap-3 text-sm text-white/75 sm:grid-cols-3">
              <div className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-[#f4d99f]" /> {language === 'fr' ? 'Écoute confidentielle' : language === 'ar' ? 'رعاية سرية' : language === 'it' ? 'Cura riservata' : language === 'de' ? 'Diskrete Betreuung' : 'Confidential care'}</div>
              <div className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-[#f4d99f]" /> {language === 'fr' ? 'Résultats naturels' : language === 'ar' ? 'نتائج طبيعية' : language === 'it' ? 'Risultati naturali' : language === 'de' ? 'Natürlich wirkende Ergebnisse' : 'Natural-looking results'}</div>
              <div className="flex items-center gap-2"><HeartHandshake className="h-4 w-4 text-[#f4d99f]" /> {language === 'fr' ? 'Suivi personnalisé' : language === 'ar' ? 'متابعة شخصية' : language === 'it' ? 'Follow-up personalizzato' : language === 'de' ? 'Persönliche Nachsorge' : 'Personalised follow-up'}</div>
            </div>
          </div>

          <Card id="reservation" className="border-white/70 bg-[#fbfaf7]/95 shadow-[0_30px_90px_rgba(10,28,32,0.28)] backdrop-blur-xl">
            <CardHeader className="border-b border-[#172126]/10 px-6 pb-5 pt-6 sm:px-8">
              <CardTitle className="flex items-center gap-3 text-lg tracking-tight text-[#172126]">
                <Calendar className="w-5 h-5" />
                {language === 'fr' ? 'Réserver un rendez-vous' : language === 'ar' ? 'حجز موعد' : language === 'it' ? 'Prenota un appuntamento' : language === 'de' ? 'Termin buchen' : 'Book an appointment'}
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
                  Les disponibilités de réservation seront ouvertes après le paramétrage des médecins et des prestations.
                </div>
              ) : (
                <>
                  <p className="mb-4 text-sm leading-6 text-muted-foreground">
                    {language === 'fr' ? 'Cette réservation crée une demande auprès de la clinique. L’accueil vérifiera le créneau, créera ou retrouvera votre dossier, puis vous confirmera le rendez-vous.' : language === 'ar' ? 'يراجع فريق العيادة هذا الطلب ويؤكد التوفر والموعد.' : language === 'it' ? 'Il team della clinica esaminerà la richiesta e confermerà disponibilità e appuntamento.' : language === 'de' ? 'Das Klinikteam prüft die Anfrage und bestätigt Verfügbarkeit und Termin.' : 'This request is reviewed by the clinic team, who will confirm availability and your appointment.'}
                  </p>
                  <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="prenom">{formCopy.first}</Label>
                      <Input id="prenom" name="prenom" value={formData.prenom} onChange={handleInputChange} required />
                    </div>
                    <div>
                      <Label htmlFor="nom">{formCopy.last}</Label>
                      <Input id="nom" name="nom" value={formData.nom} onChange={handleInputChange} required />
                    </div>
                  </div>

                  <div>
                    <Label htmlFor="telephone">{formCopy.phone}</Label>
                    <Input
                      id="telephone"
                      name="telephone"
                      type="tel"
                      value={formData.telephone}
                      onChange={handleInputChange}
                      placeholder="+216 XX XXX XXX"
                      required
                    />
                    <p className="text-xs text-muted-foreground mt-1">{formCopy.format}</p>
                  </div>

                  <div>
                    <Label htmlFor="praticien_id">{formCopy.practitioner}</Label>
                    <select
                      id="praticien_id"
                      name="praticien_id"
                      value={formData.praticien_id}
                      onChange={handleInputChange}
                      className="w-full px-3 py-2 border rounded-md bg-background"
                      required
                    >
                      <option value="">{formCopy.selectPractitioner}</option>
                      {praticiens.map((praticien) => (
                        <option key={praticien.id} value={praticien.id}>
                          {praticien.nom_complet}
                          {praticien.specialite ? ` — ${praticien.specialite}` : ''}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <Label htmlFor="acte_id">{formCopy.treatment}</Label>
                    <select
                      id="acte_id"
                      name="acte_id"
                      value={formData.acte_id}
                      onChange={handleInputChange}
                      className="w-full px-3 py-2 border rounded-md bg-background"
                      required
                    >
                      <option value="">{formCopy.selectTreatment}</option>
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
                    <Label htmlFor="date">{formCopy.date}</Label>
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
                    <Label htmlFor="periode">{formCopy.time}</Label>
                    <select
                      id="periode"
                      name="periode"
                      value={formData.periode}
                      onChange={handleBookingPeriodChange}
                      className="w-full px-3 py-2 border rounded-md bg-background"
                      required
                      disabled={!formData.praticien_id || isSlotsLoading || availabilities.length === 0}
                    >
                      <option value="">
                        {isSlotsLoading
                          ? formCopy.loading
                          : formCopy.selectTime}
                      </option>
                      <option value="matin" disabled={!availabilities.some((slot) => getBookingPeriod(slot) === 'matin')}>
                        {periodLabel('matin', availabilities)}
                      </option>
                      <option value="apres_midi" disabled={!availabilities.some((slot) => getBookingPeriod(slot) === 'apres_midi')}>
                        {periodLabel('apres_midi', availabilities)}
                      </option>
                    </select>
                    {formData.date_heure && formData.periode && (
                      <p className="text-xs text-muted-foreground mt-2">
                        La clinique proposera un horaire précis dans la période choisie (à partir de {availabilities.find((slot) => slot.datetime === formData.date_heure)?.heure}).
                      </p>
                    )}
                    {isSlotsLoading && (
                      <div className="flex items-center gap-2 text-xs text-muted-foreground mt-2">
                        <Spinner className="h-3.5 w-3.5" />
                        Chargement des disponibilités
                      </div>
                    )}
                    {!isSlotsLoading && formData.praticien_id && availabilities.length === 0 && (
                      <p className="text-xs text-muted-foreground mt-2">
                        {formCopy.noSlots}
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
                    <span>{formCopy.privacy} <a className="underline hover:text-foreground" href="#confidentialite">{formCopy.privacyLink}</a>.</span>
                  </label>
                  <Button type="submit" className="w-full" disabled={isSubmitting || isBootstrapLoading}>
                    {isSubmitting ? (
                      <>
                        <Spinner className="mr-2 h-4 w-4" />
                        Réservation en cours...
                      </>
                    ) : (
                      formCopy.book
                    )}
                    </Button>
                  </form>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </section>

      <section id="qui-sommes-nous" className="relative overflow-hidden bg-[#fbfaf7] px-5 py-20 sm:px-8 lg:px-12">
        <div className="absolute -right-24 top-0 h-72 w-72 rounded-full bg-[#d7b77a]/10 blur-3xl" aria-hidden="true" />
        <div className="relative mx-auto grid max-w-7xl gap-12 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
          <div>
            <p className="mb-4 flex items-center gap-3 text-xs font-semibold uppercase tracking-[0.24em] text-[#b0884b]"><span className="h-px w-10 bg-[#d7b77a]" /> {copy.aboutLabel}</p>
            <h3 className="max-w-lg font-serif text-4xl font-medium leading-tight tracking-[-0.03em] text-[#172126] sm:text-5xl">{copy.aboutTitle}</h3>
          </div>
          <div className="grid gap-6 md:grid-cols-2">
            <p className="text-base leading-8 text-[#172126]/68">{copy.aboutOne}</p>
            <p className="text-base leading-8 text-[#172126]/68">{copy.aboutTwo}</p>
          </div>
        </div>
      </section>

      <section id="nos-actes" className="bg-[#f5f3ee] px-5 py-20 sm:px-8 lg:px-12">
        <div className="mx-auto max-w-7xl">
          <div className="mb-10 flex flex-col justify-between gap-5 md:flex-row md:items-end">
            <div>
              <p className="mb-4 flex items-center gap-3 text-xs font-semibold uppercase tracking-[0.24em] text-[#b0884b]"><span className="h-px w-10 bg-[#d7b77a]" /> {copy.servicesLabel}</p>
              <h3 className="font-serif text-4xl font-medium tracking-[-0.03em] text-[#172126] sm:text-5xl">{copy.servicesTitle}</h3>
            </div>
            <p className="max-w-md text-sm leading-6 text-[#172126]/60">{copy.servicesIntro}</p>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {(featuredServices.length > 0 ? featuredServices : SERVICE_DETAILS.map((service) => service.title)).slice(0, 3).map((service, index) => {
              const detail = SERVICE_DETAILS[index];
              const isExpanded = expandedService === index;
              const serviceCopy = LANDING_SERVICES[language] || LANDING_SERVICES.fr;
              const titles = serviceCopy.titles;
              const descriptions = serviceCopy.descriptions;
              const points = serviceCopy.points[index];
              return <article key={`${service}-${index}`} className="group overflow-hidden rounded-[1.5rem] border border-[#172126]/10 bg-[#fbfaf7] shadow-[0_18px_50px_rgba(23,33,38,0.05)] transition duration-200 hover:-translate-y-1 hover:border-[#d7b77a]/70 hover:shadow-[0_24px_60px_rgba(23,33,38,0.1)]"><img src={SERVICE_IMAGES[index]} alt={isEnglish ? ['Aesthetic consultation in a calm clinic', 'Premium facial treatment in a bright care room', 'Medical aesthetic treatment prepared with precision'][index] : ['Consultation esthétique dans un cabinet calme', 'Soin visage premium dans une cabine lumineuse', 'Préparation précise d’un acte de médecine esthétique'][index]} loading="lazy" className="h-44 w-full object-cover transition duration-500 group-hover:scale-[1.03]" /><div className="p-6"><div className="mb-6 flex items-center justify-between"><span className="flex h-11 w-11 items-center justify-center rounded-full bg-[#172126] text-[#f4d99f]"><Sparkles className="h-5 w-5" /></span><span className="text-xs font-medium text-[#172126]/35">0{index + 1}</span></div><h4 className="text-xl font-semibold text-[#172126]">{titles[index]}</h4><p className="mt-3 text-sm leading-6 text-[#172126]/60">{descriptions[index]}</p><button type="button" aria-expanded={isExpanded} onClick={() => setExpandedService(isExpanded ? null : index)} className="mt-5 inline-flex min-h-11 items-center text-sm font-semibold text-[#b0884b]">{isExpanded ? copy.hide : copy.discover} <ArrowRight className="ml-2 h-4 w-4 transition group-hover:translate-x-1" /></button>{isExpanded && <div className="mt-5 border-t border-[#172126]/10 pt-4"><ul className="grid gap-2 text-sm text-[#172126]/70">{points.map((point) => <li key={point} className="flex items-start gap-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-[#b0884b]" />{point}</li>)}</ul><a href="#reservation" className="mt-4 inline-flex min-h-11 items-center rounded-full bg-[#172126] px-4 py-2.5 text-xs font-semibold text-white">{copy.book}<ArrowRight className="ml-2 h-4 w-4" /></a></div>}</div></article>;
            })}
          </div>
          <div className="mt-8 rounded-[1.5rem] border border-[#d7b77a]/35 bg-[#172126] p-6 text-white sm:p-8">
            <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
              <div><p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#f4d99f]">{copy.journeyLabel}</p><p className="mt-2 text-lg text-white/80">{copy.journeyText}</p></div>
              <a href="#reservation" className="inline-flex shrink-0 items-center justify-center rounded-full bg-[#f4d99f] px-5 py-3 text-sm font-semibold text-[#172126] transition hover:bg-white">{copy.chooseSlot} <ArrowRight className="ml-2 h-4 w-4" /></a>
            </div>
          </div>
        </div>
      </section>

      <section id="rappel" className="bg-[#172126] px-5 py-14 text-white sm:px-8 lg:px-12">
        <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
          <div><p className="mb-3 text-xs font-medium uppercase tracking-[0.22em] text-[#f4d99f]">{copy.callbackEyebrow}</p><h3 className="text-3xl font-semibold tracking-tight">{copy.callbackTitle}</h3><p className="mt-3 max-w-lg text-white/70">{copy.callbackText}</p></div>
          <Card className="border-white/10 bg-white/10 text-white"><CardContent className="p-6">
            {callbackConfirmation && <div className="mb-4 rounded-lg border border-emerald-300/30 bg-emerald-400/10 p-3 text-sm">Demande reçue — référence #{callbackConfirmation}.</div>}
            <form onSubmit={handleCallbackSubmit} className="grid gap-4 sm:grid-cols-2"><div><Label htmlFor="callback_nom" className="text-white">{copy.callbackName}</Label><Input id="callback_nom" value={callbackData.nom} onChange={(e) => setCallbackData({ ...callbackData, nom: e.target.value })} required className="mt-1 bg-white text-[#172126]" /></div><div><Label htmlFor="callback_telephone" className="text-white">{copy.callbackPhone}</Label><Input id="callback_telephone" type="tel" value={callbackData.telephone} onChange={(e) => setCallbackData({ ...callbackData, telephone: e.target.value })} required className="mt-1 bg-white text-[#172126]" /></div><div className="sm:col-span-2"><Label htmlFor="callback_email" className="text-white">Email ({copy.optional})</Label><Input id="callback_email" type="email" value={callbackData.email} onChange={(e) => setCallbackData({ ...callbackData, email: e.target.value })} className="mt-1 bg-white text-[#172126]" /></div><div className="sm:col-span-2"><Label htmlFor="callback_message" className="text-white">{copy.need} ({copy.optional})</Label><Input id="callback_message" value={callbackData.message} onChange={(e) => setCallbackData({ ...callbackData, message: e.target.value })} className="mt-1 bg-white text-[#172126]" /></div><label className="sm:col-span-2 flex items-start gap-3 text-xs leading-5 text-white/70"><input type="checkbox" checked={callbackPrivacyAccepted} onChange={(event) => setCallbackPrivacyAccepted(event.target.checked)} required className="mt-1 h-4 w-4 rounded border-white/40" /><span>{copy.consentCallback} <a className="underline hover:text-white" href="#confidentialite">{copy.privacy}</a>.</span></label><Button type="submit" disabled={isCallbackSubmitting} className="sm:col-span-2 bg-[#f4d99f] text-[#172126] hover:bg-white">{isCallbackSubmitting ? 'Envoi…' : copy.callbackSubmit}</Button></form>
          </CardContent></Card>
        </div>
      </section>

      <section id="contact" className="border-y border-[#172126]/10 bg-[#fbfaf7] px-5 py-20 sm:px-8 lg:px-12">
        <div className="mx-auto max-w-7xl">
          <div className="mb-9 flex flex-col justify-between gap-4 md:flex-row md:items-end">
            <div>
              <p className="mb-4 flex items-center gap-3 text-xs font-semibold uppercase tracking-[0.24em] text-[#b0884b]"><span className="h-px w-10 bg-[#d7b77a]" /> {copy.contactLabel}</p>
              <h3 className="font-serif text-4xl font-medium tracking-[-0.03em] text-[#172126] sm:text-5xl">{copy.contactTitle}</h3>
            </div>
            <p className="max-w-sm text-sm leading-6 text-[#172126]/60">{copy.contactText}</p>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <Card className="border-[#172126]/10 bg-[#f5f3ee] shadow-none"><CardContent className="p-6"><MapPin className="mb-8 h-5 w-5 text-[#b0884b]" /><p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#172126]/45">{copy.location}</p><p className="mt-2 text-lg font-semibold text-[#172126]">{language === 'fr' ? (landingContent?.adresse || clinicCity) : extraCopy.locationDemo}</p><p className="mt-2 text-sm leading-6 text-[#172126]/60">{copy.locationText}</p></CardContent></Card>
            <Card className="border-[#172126]/10 bg-[#f5f3ee] shadow-none"><CardContent className="p-6"><Phone className="mb-8 h-5 w-5 text-[#b0884b]" /><p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#172126]/45">{copy.phoneWhatsapp}</p>{clinicPhone ? <a href={`tel:${clinicPhone}`} className="mt-2 block text-lg font-semibold text-[#172126] hover:text-[#b0884b]">{clinicPhone}</a> : <p className="mt-2 text-sm text-[#172126]/60">{language === 'fr' ? 'Coordonnées communiquées par la clinique' : 'Contact details to be configured'}</p>}{clinicWhatsapp && <a href={`https://wa.me/${clinicWhatsapp.replace(/[^0-9]/g, '')}`} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center text-sm font-medium text-[#b0884b] hover:underline"><MessageCircle className="mr-2 h-4 w-4" />{copy.writeWhatsapp}</a>}</CardContent></Card>
            <Card className="border-[#172126]/10 bg-[#f5f3ee] shadow-none"><CardContent className="p-6"><Clock className="mb-8 h-5 w-5 text-[#b0884b]" /><p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#172126]/45">{copy.availability}</p><p className="mt-2 text-lg font-semibold text-[#172126]">{language === 'fr' ? (landingContent?.horaires || extraCopy.hours) : extraCopy.hours}</p><a href="#reservation" className="mt-2 inline-flex items-center text-sm font-medium text-[#b0884b] hover:underline">{extraCopy.viewSlots} <ArrowRight className="ml-2 h-4 w-4" /></a></CardContent></Card>
          </div>
        </div>
      </section>

      {praticiens.length > 0 && (
        <section className="bg-[#f5f3ee] px-5 py-16 sm:px-8 lg:px-12">
          <div className="mx-auto max-w-7xl">
            <div className="mb-6">
              <p className="mb-3 text-xs font-medium uppercase tracking-[0.22em] text-[#b0884b]">{copy.teamEyebrow}</p>
              <h3 className="text-3xl font-semibold tracking-tight text-[#172126]">{copy.practitioners}</h3>
              <p className="mt-2 max-w-xl text-[#172126]/65">{copy.practitionerText}</p>
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
          <h3 className="font-semibold text-[#172126]">{copy.privacyTitle}</h3>
          <p className="mt-2 max-w-3xl leading-6">Les informations transmises sur cette page servent uniquement à traiter votre demande de rendez-vous ou de rappel. Elles sont communiquées à la clinique sélectionnée et conservées pendant la durée nécessaire à ce traitement, conformément à sa politique de confidentialité. Vous pouvez demander l’accès, la rectification ou la suppression de vos données auprès de la clinique.</p>
        </div>
      </section>

      <footer className="border-t border-[#f4d99f]/15 bg-[#172126] px-5 py-10 text-white/65 sm:px-8 lg:px-12">
        <div className="mx-auto flex max-w-7xl flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div><div className="flex items-center gap-3"><img src={effectiveBranding?.logo_url || MBA_LOGO_URL} alt="Monogramme MBA Clinic" className="h-10 w-10 object-contain" /><span className="font-serif text-lg tracking-[0.08em] text-white">MBA <span className="font-sans text-[0.62em] font-semibold tracking-[0.25em] text-[#f4d99f]">CLINIC</span></span></div><p className="mt-3 text-xs text-white/45">{copy.footerTagline}</p></div>
          <div className="flex flex-wrap items-center gap-4 text-xs">
            <a href="#qui-sommes-nous" className="hover:text-white">{extraCopy.footerAbout}</a>
            <a href="#nos-actes" className="hover:text-white">{extraCopy.footerServices}</a>
            <a href="#contact" className="hover:text-white">{extraCopy.footerContact}</a>
            {landingContent?.instagram && <a href={landingContent.instagram} target="_blank" rel="noreferrer" className="hover:text-white">Instagram</a>}
            {landingContent?.facebook && <a href={landingContent.facebook} target="_blank" rel="noreferrer" className="hover:text-white">Facebook</a>}
            {landingContent?.email && <a href={`mailto:${landingContent.email}`} className="hover:text-white">Email</a>}
          </div>
          <p className="text-xs text-white/40 md:text-right">© {new Date().getFullYear()} {clinicName}</p>
        </div>
      </footer>
      {clinicWhatsapp && <LinaChatWidget whatsapp={clinicWhatsapp} />}
    </div>
  );
}
