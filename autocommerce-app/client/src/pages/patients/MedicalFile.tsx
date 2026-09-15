import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import {
  Tooltip, TooltipTrigger, TooltipContent,
} from '@/components/ui/tooltip';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { FileText, Image as ImageIcon, CheckCircle, Download, Plus, Trash2, User, Phone, ArrowLeft, Sparkles, Camera, SlidersHorizontal, Eye, EyeOff, Zap, Mic, Square, Loader2, Pencil, ExternalLink, Save, HeartPulse, Pill, FlaskConical, Paperclip } from 'lucide-react';
import { toast } from 'sonner';
import { useLocation } from 'wouter';
import { api, dossierMedicalApi, medicalFactsApi, prescriptionsApi, photosApi, scribeIaApi, type MedicalFactItem, type PrescriptionItem } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import { useCurrency } from '@/hooks/useCurrency';
import { SignaturePad } from '@/components/patients/SignaturePad';
import { SimulationCrayonPad } from '@/components/patients/SimulationCrayonPad';
import { InjectableAssignmentSelector } from '@/components/stock/InjectableAssignmentSelector';

interface PatientHeader {
  id: number;
  nom: string;
  prenom: string;
  telephone: string;
  date_naissance?: string;
  allergies?: string;
  contre_indications?: string;
  antecedents_medicaux?: string;
  email?: string;
  adresse?: string;
  ville?: string;
  groupe_sanguin?: string;
}

interface TimelineItem {
  dossier_id: number;
  date: string;
  acte: string;
  praticien: string;
  observations: string;
  effets_secondaires?: string;
  satisfaction?: number;
  statut_facturation?: string;
  facture_id?: number | null;
  facture_numero?: string | null;
  facture_statut?: string | null;
  photos: { id: number; type: string; zone?: string; url: string }[];
}

interface ConsentementItem {
  id: number;
  type: string;
  acte_id?: number;
  signe_le: string;
  methode: string;
  est_valide: boolean;
}

interface PhotoItem {
  id: number;
  type: string;
  zone?: string;
  date: string;
  visible_patient: boolean;
}

interface Acte {
  id: number;
  nom: string;
  duree_minutes: number;
  prix_base?: number | null;
}

/** Bloc B — libellés métier des types de faits médicaux structurés. */
const FACT_TYPE_LABELS: Record<string, string> = {
  antecedent_medical: 'medicalFile.factTypeAntecedentMedical',
  antecedent_chirurgical: 'medicalFile.factTypeAntecedentChirurgical',
  antecedent_anesthesique: 'medicalFile.factTypeAntecedentAnesthesique',
  antecedent_familial: 'medicalFile.factTypeAntecedentFamilial',
  allergie: 'medicalFile.factTypeAllergie',
  traitement: 'medicalFile.factTypeTraitement',
  contre_indication: 'medicalFile.factTypeContreIndication',
};

/** Interface pour la réponse de comparaison avant/après */
interface ComparaisonAvantApres {
  avant: { id: number; url: string; date: string }[];
  apres: { id: number; url: string; date: string }[];
}

export default function MedicalFile({ patientId }: { patientId: number }) {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const [location, setLocation] = useLocation();
  const backToPatientIndex = location.startsWith('/medical-record') ? '/medical-record' : '/patients';
  const canSeeAntecedents = user?.role !== 'estheticienne';
  // Les opérations cliniques et les signatures de consentement sont réservées
  // aux médecins ; la directrice conserve un accès de consultation et d’export.
  const canManageClinicalEntries = ['medecin', 'estheticienne'].includes(user?.role ?? '');
  const canManagePhotos = ['medecin', 'estheticienne'].includes(user?.role ?? '');
  const [patient, setPatient] = useState<PatientHeader | null>(null);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [globalTimeline, setGlobalTimeline] = useState<Array<{ type: string; date: string; statut?: string; summary: string }>>([]);
  const [consentements, setConsentements] = useState<ConsentementItem[]>([]);
  const [photos, setPhotos] = useState<PhotoItem[]>([]);
  const [photoUrls, setPhotoUrls] = useState<Record<number, string>>({});
  const [actes, setActes] = useState<Acte[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('dossiers');

  // ── Bloc B : faits médicaux structurés (lecture réservée au rôle médecin) ──
  const [facts, setFacts] = useState<MedicalFactItem[]>([]);
  const [factDialogOpen, setFactDialogOpen] = useState(false);

  // ── Bloc C : prescriptions médicales (lecture réservée au rôle médecin) ──
  const [prescriptions, setPrescriptions] = useState<PrescriptionItem[]>([]);
  const [prescriptionDialogOpen, setPrescriptionDialogOpen] = useState(false);

  const [dossierDialogOpen, setDossierDialogOpen] = useState(false);
  const [consentDialogOpen, setConsentDialogOpen] = useState(false);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [simulationDialogOpen, setSimulationDialogOpen] = useState(false);
  const [selectedPhotoForSim, setSelectedPhotoForSim] = useState<PhotoItem | null>(null);
  const [isExporting, setIsExporting] = useState(false);

  // ── Nouveaux états pour les améliorations UX ──
  const [comparaisonDialogOpen, setComparaisonDialogOpen] = useState(false);
  const [comparaisonData, setComparaisonData] = useState<ComparaisonAvantApres | null>(null);
  const [comparaisonUrls, setComparaisonUrls] = useState<Record<string, string>>({});
  const [isComparaisonLoading, setIsComparaisonLoading] = useState(false);
  const [comparaisonZoneFilter, setComparaisonZoneFilter] = useState<string>('');

  // ── Raccourci « Photo Après » depuis photo avant ──
  const [quickAfterDialogOpen, setQuickAfterDialogOpen] = useState(false);
  const [quickAfterPhoto, setQuickAfterPhoto] = useState<PhotoItem | null>(null);
  const [intake, setIntake] = useState({ nom: '', prenom: '', date_naissance: '', email: '', adresse: '', ville: '', groupe_sanguin: '' });
  const [isSavingIntake, setIsSavingIntake] = useState(false);

  const loadAll = useCallback(async () => {
    if (!patientId || Number.isNaN(patientId)) return;
    setIsLoading(true);
    try {
      const [patientRes, timelineRes, consentRes, photosRes, actesRes, globalTimelineRes, factsRes, prescriptionsRes] = await Promise.allSettled([
        api.get(`/patients/${patientId}`),
        dossierMedicalApi.getTimeline(patientId),
        dossierMedicalApi.listConsentements(patientId),
        dossierMedicalApi.listPhotos(patientId),
        api.get('/agenda/actes'),
        user?.role === 'medecin' ? dossierMedicalApi.getGlobalTimeline(patientId) : Promise.resolve({ data: [] }),
        user?.role === 'medecin' ? medicalFactsApi.list(patientId) : Promise.resolve({ data: [] as MedicalFactItem[] }),
        user?.role === 'medecin' ? prescriptionsApi.list(patientId) : Promise.resolve({ data: [] as PrescriptionItem[] }),
      ]);

      if (patientRes.status === 'fulfilled') setPatient(patientRes.value.data);
      else toast.error(t('medicalFile.loadPatientError'));

      if (timelineRes.status === 'fulfilled') setTimeline(timelineRes.value.data);
      if (consentRes.status === 'fulfilled') setConsentements(consentRes.value.data);
      if (photosRes.status === 'fulfilled') setPhotos(photosRes.value.data);
      if (actesRes.status === 'fulfilled') setActes(actesRes.value.data);
      if (globalTimelineRes.status === 'fulfilled') setGlobalTimeline(globalTimelineRes.value.data);
      if (factsRes.status === 'fulfilled') setFacts(factsRes.value.data);
      else if (factsRes.status === 'rejected') setFacts([]);
      if (prescriptionsRes.status === 'fulfilled') setPrescriptions(prescriptionsRes.value.data);
      else if (prescriptionsRes.status === 'rejected') setPrescriptions([]);
      if (patientRes.status === 'fulfilled') {
        const p = patientRes.value.data;
        setIntake({ nom: p.nom || '', prenom: p.prenom || '', date_naissance: p.date_naissance || '', email: p.email || '', adresse: p.adresse || '', ville: p.ville || '', groupe_sanguin: p.groupe_sanguin || '' });
      }
    } finally {
      setIsLoading(false);
    }
  }, [patientId, user?.role]);

  const handleSaveIntake = async () => {
    setIsSavingIntake(true);
    try {
      const response = await api.patch(`/patients/${patientId}`, {
        ...intake,
        date_naissance: intake.date_naissance || undefined,
      });
      setPatient(response.data);
      toast.success(t('medicalFile.intakeSaved'));
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('medicalFile.intakeSaveError'));
    } finally {
      setIsSavingIntake(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // Charge les vignettes déchiffrées à part (chaque photo = 1 fetch
  // authentifié en blob, pas un simple <img src>)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      for (const p of photos) {
        if (photoUrls[p.id]) continue;
        try {
          const url = await photosApi.getPhotoUrl(patientId, p.id, true);
          if (!cancelled) setPhotoUrls((prev) => ({ ...prev, [p.id]: url }));
        } catch {
          // photo individuelle inaccessible : on l'ignore plutôt que de bloquer la galerie
        }
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [photos, patientId]);

  const handleOpenConsentement = async (consentementId: number) => {
    try {
      await dossierMedicalApi.openConsentement(patientId, consentementId);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('medicalFile.consentDocUnavailable'));
    }
  };

  const handleExportPdf = async () => {
    setIsExporting(true);
    try {
      await dossierMedicalApi.downloadExportPdf(patientId);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('medicalFile.pdfExportError'));
    } finally {
      setIsExporting(false);
    }
  };

  const handleExportStructured = async () => {
    try {
      const response = await dossierMedicalApi.exportStructured(patientId);
      const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url; link.download = `dossier_patient_${patientId}.json`; link.click(); URL.revokeObjectURL(url);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('medicalFile.structuredExportError'));
    }
  };

  const handleDeletePhoto = async (photoId: number) => {
    try {
      await photosApi.delete(patientId, photoId);
      toast.success(t('medicalFile.photoDeleted'));
      loadAll();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('medicalFile.photoDeleteError'));
    }
  };

  // ── Bloc B : désactivation logique d'un fait médical (réservée au médecin) ──
  const handleDeleteFact = async (factId: number) => {
    try {
      await medicalFactsApi.delete(patientId, factId);
      toast.success(t('medicalFile.factArchived'));
      loadAll();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('medicalFile.factDeactivateError'));
    }
  };

  // ── Handlers pour la comparaison avant/après ──
  const handleOpenComparaison = async () => {
    setComparaisonDialogOpen(true);
    setIsComparaisonLoading(true);
    setComparaisonData(null);
    setComparaisonUrls({});
    try {
      const res = await photosApi.getComparaisonAvantApres(
        patientId,
        comparaisonZoneFilter || undefined,
      );
      setComparaisonData(res.data);

      // Charger les URLs déchiffrées pour chaque photo
      const urls: Record<string, string> = {};
      for (const p of [...res.data.avant, ...res.data.apres]) {
        try {
          const url = await photosApi.getPhotoUrl(patientId, p.id);
          urls[`photo_${p.id}`] = url;
        } catch {
          // ignorer si indisponible
        }
      }
      setComparaisonUrls(urls);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('medicalFile.comparisonLoadError'));
    } finally {
      setIsComparaisonLoading(false);
    }
  };

  // ── Handler pour le raccourci « Photo Après » ──
  const handleQuickAfterPhoto = (photo: PhotoItem) => {
    setQuickAfterPhoto(photo);
    setQuickAfterDialogOpen(true);
  };

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex justify-center py-20"><Spinner className="h-8 w-8" /></div>
      </DashboardLayout>
    );
  }

  if (!patient) {
    return (
      <DashboardLayout>
        <Card><CardContent className="py-10 text-center text-muted-foreground">
          {t('medicalFile.notFound')}
        </CardContent></Card>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-start justify-between">
          <div>
            <Button variant="ghost" size="sm" className="mb-2 -ml-2" onClick={() => setLocation(backToPatientIndex)}>
              <ArrowLeft className="w-4 h-4 mr-1" /> {t('medicalFile.backToPatients')}
            </Button>
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <User className="w-7 h-7 text-muted-foreground" />
              {patient.prenom} {patient.nom}
            </h1>
            <p className="text-muted-foreground mt-1 flex items-center gap-1">
              <Phone className="w-4 h-4" /> {patient.telephone}
              {patient.date_naissance && ` · ${t('medicalFile.bornOn', { date: new Date(patient.date_naissance).toLocaleDateString(i18n.language) })}`}
            </p>
          </div>
          {user?.role === 'medecin' && <div className="flex gap-2">
            <Button variant="outline" onClick={handleExportStructured}><Download className="w-4 h-4 mr-2" />{t('medicalFile.exportJson')}</Button>
            <Button onClick={handleExportPdf} disabled={isExporting}>
              {isExporting ? <Spinner className="h-4 w-4 mr-2" /> : <Download className="w-4 h-4 mr-2" />}
              {t('medicalFile.exportPdf')}
            </Button>
          </div>}
        </div>

        {user?.role === 'assistante' && (
          <Card className="border-purple-200 bg-purple-50/30">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base"><FileText className="h-4 w-4" /> {t('medicalFile.adminFileTitle')}</CardTitle>
              <p className="text-sm text-muted-foreground">{t('medicalFile.adminFileDesc')}</p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                {([['prenom', 'medicalFile.fieldFirstName'], ['nom', 'medicalFile.fieldLastName'], ['date_naissance', 'medicalFile.fieldBirthDate'], ['email', 'medicalFile.fieldEmail'], ['adresse', 'medicalFile.fieldAddress'], ['ville', 'medicalFile.fieldCity'], ['groupe_sanguin', 'medicalFile.fieldBloodGroup']] as const).map(([key, label]) => (
                  <div key={key}>
                    <Label htmlFor={`intake-${key}`}>{t(label)}</Label>
                    <Input id={`intake-${key}`} type={key === 'date_naissance' ? 'date' : 'text'} value={intake[key]} onChange={(e) => setIntake((prev) => ({ ...prev, [key]: e.target.value }))} />
                  </div>
                ))}
              </div>
              <div className="flex justify-end">
                <Button onClick={handleSaveIntake} disabled={isSavingIntake}><Save className="mr-2 h-4 w-4" />{isSavingIntake ? t('medicalFile.saving') : t('medicalFile.saveInfo')}</Button>
              </div>
            </CardContent>
          </Card>
        )}

        {(patient.allergies || patient.contre_indications) && (
          <Card className="border-destructive/40 bg-destructive/5">
            <CardContent className="py-4 space-y-1">
              {patient.allergies && <p><strong>{t('medicalFile.allergiesLabel')}</strong> {patient.allergies}</p>}
              {patient.contre_indications && <p><strong>{t('medicalFile.contreIndicationsLabel')}</strong> {patient.contre_indications}</p>}
            </CardContent>
          </Card>
        )}
        {canSeeAntecedents && patient.antecedents_medicaux && (
          <Card>
            <CardContent className="py-4">
              <p><strong>{t('medicalFile.antecedentsLabel')}</strong> {patient.antecedents_medicaux}</p>
            </CardContent>
          </Card>
        )}

        {user?.role === 'medecin' && (
          <Card>
            <CardHeader><CardTitle className="text-base">{t('medicalFile.globalTimeline')}</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {globalTimeline.length === 0 ? <p className="text-sm text-muted-foreground">{t('medicalFile.noClinicalEntry')}</p> : globalTimeline.slice(0, 8).map((entry, index) => (
                <div key={`${entry.type}-${entry.date}-${index}`} className="flex items-center justify-between border-b last:border-0 py-2 text-sm">
                  <span><strong>{entry.type}</strong> — {entry.summary}</span><span className="text-muted-foreground">{new Date(entry.date).toLocaleString(i18n.language)}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="dossiers"><FileText className="w-4 h-4 mr-1" /> {t('medicalFile.tabDossiers')} ({timeline.length})</TabsTrigger>
            <TabsTrigger value="consentements"><CheckCircle className="w-4 h-4 mr-1" /> {t('medicalFile.tabConsents')} ({consentements.length})</TabsTrigger>
            <TabsTrigger value="photos"><ImageIcon className="w-4 h-4 mr-1" /> {t('medicalFile.tabPhotos')} ({photos.length})</TabsTrigger>
            <TabsTrigger value="faits-medicaux"><HeartPulse className="w-4 h-4 mr-1" /> {t('medicalFile.tabFacts')} ({facts.length})</TabsTrigger>
            <TabsTrigger value="prescriptions"><Pill className="w-4 h-4 mr-1" /> {t('medicalFile.tabPrescriptions')} ({prescriptions.length})</TabsTrigger>
          </TabsList>

          {/* ── Dossiers ── */}
          <TabsContent value="dossiers" className="space-y-4">
            {canManageClinicalEntries && user?.id && (
              <InjectableAssignmentSelector
                patientId={patientId}
                praticienId={Number(user.id)}
                onAssigned={loadAll}
              />
            )}
            <div className="flex justify-end">
              {canManageClinicalEntries ? (
                <Button size="sm" onClick={() => setDossierDialogOpen(true)}>
                  <Plus className="w-4 h-4 mr-1" /> {t('medicalFile.newDossier')}
                </Button>
              ) : (
                <p className="text-sm text-muted-foreground">{t('medicalFile.createDossierRestricted')}</p>
              )}
            </div>
            {timeline.length === 0 ? (
              <Card><CardContent className="py-8 text-center text-muted-foreground">{t('medicalFile.noDossier')}</CardContent></Card>
            ) : (
              timeline.map((item) => (
                <Card key={item.dossier_id}>
                  <CardHeader>
                    <CardTitle className="text-base flex justify-between items-center">
                      <span>{item.acte} — {new Date(item.date).toLocaleDateString(i18n.language)}</span>
                      <div className="flex items-center gap-2">
                        {item.facture_id || item.statut_facturation === 'facture' ? (
                          <Badge className="h-8 bg-emerald-100 text-emerald-800 hover:bg-emerald-100">
                            <CheckCircle className="w-3 h-3 mr-1" />
                            {t('medicalFile.alreadyBilled')}{item.facture_numero ? ` · ${item.facture_numero}` : ''}
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="h-8 border-amber-200 bg-amber-50 text-amber-800">
                            {t('medicalFile.awaitingBilling')}
                          </Badge>
                        )}
                        <Badge variant="outline">{item.praticien}</Badge>
                      </div>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    {item.observations && <p><strong>{t('medicalFile.observationsLabel')}</strong> {item.observations}</p>}
                    {item.effets_secondaires && <p><strong>{t('medicalFile.sideEffectsLabel')}</strong> {item.effets_secondaires}</p>}
                    {item.satisfaction && <p><strong>{t('medicalFile.satisfactionLabel')}</strong> {item.satisfaction}/5</p>}
                    {item.photos.length > 0 && (
                      <p className="text-muted-foreground">{t('medicalFile.photosAssociated', { count: item.photos.length })}</p>
                    )}
                  </CardContent>
                </Card>
              ))
            )}
          </TabsContent>

          {/* ── Bloc B : Faits médicaux structurés ── */}
          <TabsContent value="faits-medicaux" className="space-y-4">
            <div className="flex justify-end">
              {user?.role === 'medecin' ? (
                <Button size="sm" onClick={() => setFactDialogOpen(true)}>
                  <Plus className="w-4 h-4 mr-1" /> {t('medicalFile.newFact')}
                </Button>
              ) : (
                <p className="text-sm text-muted-foreground">{t('medicalFile.createFactRestricted')}</p>
              )}
            </div>
            {facts.length === 0 ? (
              <Card><CardContent className="py-8 text-center text-muted-foreground">{t('medicalFile.noFact')}</CardContent></Card>
            ) : (
              <Card>
                <CardContent className="py-4 space-y-3">
                  {facts.map((f) => (
                    <div key={f.id} className="flex items-center justify-between border-b last:border-0 pb-2 last:pb-0 gap-2">
                      <div className="min-w-0">
                        <p className="font-medium">{t(FACT_TYPE_LABELS[f.type_fait] ?? f.type_fait)}</p>
                        <p className="text-sm text-muted-foreground truncate">
                          {Object.entries(f.donnees ?? {}).map(([k, v]) => `${k} : ${String(v)}`).join(' · ') || '—'}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {new Date(f.created_at).toLocaleDateString(i18n.language)}
                          {' · '}{f.verification_status === 'VERIFIED' ? t('medicalFile.verified') : f.verification_status === 'PENDING_VERIFICATION' ? t('medicalFile.toVerify') : t('medicalFile.historicalUnstructured')}
                        </p>
                      </div>
                      {user?.role === 'medecin' && (
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0 text-destructive" aria-label={t('medicalFile.archiveFactAria')}>
                              <Trash2 className="w-3.5 h-3.5" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>{t('medicalFile.archiveFactTitle')}</AlertDialogTitle>
                              <AlertDialogDescription>
                                {t('medicalFile.archiveFactDesc')}
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                              <AlertDialogAction onClick={() => handleDeleteFact(f.id)}>{t('medicalFile.archive')}</AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      )}
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* ── Bloc C : Prescriptions médicales ── */}
          <TabsContent value="prescriptions" className="space-y-4">
            <div className="flex justify-end">
              {user?.role === 'medecin' ? (
                <Button size="sm" onClick={() => setPrescriptionDialogOpen(true)}>
                  <Plus className="w-4 h-4 mr-1" /> {t('medicalFile.newPrescription')}
                </Button>
              ) : (
                <p className="text-sm text-muted-foreground">{t('medicalFile.createPrescriptionRestricted')}</p>
              )}
            </div>
            {prescriptions.length === 0 ? (
              <Card><CardContent className="py-8 text-center text-muted-foreground">{t('medicalFile.noPrescription')}</CardContent></Card>
            ) : (
              <Card>
                <CardContent className="py-4 space-y-3">
                  {prescriptions.map((p) => {
                    const isAnalyse = p.details?.type === 'analyse';
                    return (
                    <div key={p.id} className="border-b last:border-0 pb-3 last:pb-0">
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-medium flex items-center gap-1.5">
                          {isAnalyse ? <FlaskConical className="w-3.5 h-3.5 text-muted-foreground" /> : <Pill className="w-3.5 h-3.5 text-muted-foreground" />}
                          {isAnalyse ? t('medicalFile.analyse') : String(p.details?.medicament ?? t('medicalFile.prescription'))}
                        </p>
                        <Badge
                          variant="outline"
                          className={p.statut === 'ACTIVE' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : p.statut === 'COMPLETED' ? 'border-sky-200 bg-sky-50 text-sky-800' : 'border-slate-200 bg-slate-50 text-slate-600'}
                        >
                          {p.statut === 'ACTIVE' ? t('medicalFile.statusActive') : p.statut === 'COMPLETED' ? t('medicalFile.statusCompleted') : t('medicalFile.statusCancelled')}
                        </Badge>
                      </div>
                      {isAnalyse ? (
                        <>
                          <p className="text-sm text-muted-foreground whitespace-pre-wrap">{String(p.details?.analyse ?? '—')}</p>
                          {p.details?.laboratoire ? <p className="text-xs text-muted-foreground">{t('medicalFile.laboratory')}{String(p.details.laboratoire)}</p> : null}
                        </>
                      ) : (
                        <>
                          <p className="text-sm text-muted-foreground">
                            {[p.details?.dosage, p.details?.frequence, p.details?.duree].filter(Boolean).join(' · ') || '—'}
                          </p>
                          {p.details?.instructions ? <p className="text-sm text-muted-foreground">{String(p.details.instructions)}</p> : null}
                        </>
                      )}
                      <p className="text-xs text-muted-foreground">{t('medicalFile.prescribedOn', { date: new Date(p.date_prescription).toLocaleDateString(i18n.language) })}</p>
                    </div>
                    );
                  })}
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* ── Consentements ── */}
          <TabsContent value="consentements" className="space-y-4">
            <div className="flex justify-end">
              {canManageClinicalEntries ? (
                <Button size="sm" onClick={() => setConsentDialogOpen(true)}>
                  <Plus className="w-4 h-4 mr-1" /> {t('medicalFile.signConsent')}
                </Button>
              ) : (
                <p className="text-sm text-muted-foreground">{t('medicalFile.signConsentRestricted')}</p>
              )}
            </div>
            {consentements.length === 0 ? (
              <Card><CardContent className="py-8 text-center text-muted-foreground">{t('medicalFile.noConsent')}</CardContent></Card>
            ) : (
              <Card>
                <CardContent className="py-4 space-y-3">
                  {consentements.map((c) => (
                    <div key={c.id} className="flex items-center justify-between border-b last:border-0 pb-2 last:pb-0">
                      <div>
                        <p className="font-medium">{c.type}</p>
                        <p className="text-sm text-muted-foreground">
                          {t('medicalFile.signedOn', { date: new Date(c.signe_le).toLocaleDateString(i18n.language), method: c.methode })}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant={c.est_valide ? 'default' : 'destructive'}>
                          {c.est_valide ? t('medicalFile.valid') : t('medicalFile.invalid')}
                        </Badge>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          className="h-8 gap-1"
                          onClick={() => handleOpenConsentement(c.id)}
                          aria-label={t('medicalFile.openSignedConsentAria', { type: c.type })}
                        >
                          <ExternalLink className="w-3.5 h-3.5" /> {t('medicalFile.open')}
                        </Button>
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* ── Photos ── */}
          <TabsContent value="photos" className="space-y-4">
            {/* Les photos médicales chiffrées et les simulations associées sont réservées aux médecins. */}
            {canManagePhotos ? (
              <div className="flex justify-between items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleOpenComparaison}
                  disabled={photos.length === 0}
                >
                  <SlidersHorizontal className="w-4 h-4 mr-1" />
                  {t('medicalFile.compareBeforeAfter')}
                </Button>
                <div className="flex gap-2">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setQuickAfterPhoto(null);
                          setQuickAfterDialogOpen(true);
                        }}
                      >
                        <Camera className="w-4 h-4 mr-1" />
                        {t('medicalFile.photoAfter')}
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="bottom">
                      <p>{t('medicalFile.tooltipSaveAfter')}</p>
                    </TooltipContent>
                  </Tooltip>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button size="sm" onClick={() => setUploadDialogOpen(true)}>
                        <Plus className="w-4 h-4 mr-1" /> {t('medicalFile.addPhoto')}
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="bottom">
                      <p>{t('medicalFile.tooltipAddPhoto')}</p>
                    </TooltipContent>
                  </Tooltip>
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                {t('medicalFile.photosRestricted')}
              </p>
            )}

            {photos.length === 0 ? (
              <Card><CardContent className="py-8 text-center text-muted-foreground">{t('medicalFile.noPhoto')}</CardContent></Card>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {photos.map((p) => (
                  <Card key={p.id} className="overflow-hidden">
                    <div className="aspect-square bg-muted flex items-center justify-center">
                      {photoUrls[p.id] ? (
                        <img src={photoUrls[p.id]} alt={p.type} className="w-full h-full object-cover" />
                      ) : (
                        <Spinner className="h-5 w-5" />
                      )}
                    </div>
                    <CardContent className="p-2 space-y-1">
                      <div className="flex items-center justify-between">
                        <Badge variant="outline" className="text-xs capitalize">{p.type}</Badge>
                        <div className="flex gap-1">
                          {/* Bouton simulateur IA — visible uniquement pour les photos « avant » */}
                          {p.type === 'avant' && canManagePhotos && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-6 w-6 p-0 text-primary"
                                  onClick={() => {
                                    setSelectedPhotoForSim(p);
                                    setSimulationDialogOpen(true);
                                  }}
                                >
                                  <Sparkles className="w-3.5 h-3.5" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent side="top">
                                <p>{t('medicalFile.simulateAi')}</p>
                              </TooltipContent>
                            </Tooltip>
                          )}
                          {/* Raccourci « Photo Après » — visible uniquement pour les photos « avant » */}
                          {p.type === 'avant' && canManagePhotos && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-6 w-6 p-0 text-green-600"
                                  onClick={() => handleQuickAfterPhoto(p)}
                                >
                                  <Camera className="w-3.5 h-3.5" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent side="top">
                                <p>{t('medicalFile.tooltipQuickAfter')}</p>
                              </TooltipContent>
                            </Tooltip>
                          )}
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-destructive">
                                <Trash2 className="w-3.5 h-3.5" />
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>{t('medicalFile.deletePhotoTitle')}</AlertDialogTitle>
                                <AlertDialogDescription>
                                  {t('medicalFile.deletePhotoDesc')}
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                                <AlertDialogAction onClick={() => handleDeletePhoto(p.id)}>{t('common.delete')}</AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        </div>
                      </div>
                      <p className="text-xs text-muted-foreground">{new Date(p.date).toLocaleDateString(i18n.language)}</p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>

      <NewDossierDialog
        open={dossierDialogOpen}
        onOpenChange={setDossierDialogOpen}
        patientId={patientId}
        actes={actes}
        canToggleActePrices={['medecin'].includes(user?.role ?? '')}
        currentUserId={user?.id ? Number(user.id) : 0}
        onCreated={loadAll}
      />
      <SignConsentDialog
        open={consentDialogOpen}
        onOpenChange={setConsentDialogOpen}
        patientId={patientId}
        actes={actes}
        onSigned={loadAll}
      />
      <UploadPhotoDialog
        open={uploadDialogOpen}
        onOpenChange={setUploadDialogOpen}
        patientId={patientId}
        onUploaded={loadAll}
      />
      {/* Bloc B : saisie d'un fait médical structuré (médecin uniquement) */}
      <MedicalFactDialog
        open={factDialogOpen}
        onOpenChange={setFactDialogOpen}
        patientId={patientId}
        onCreated={loadAll}
      />
      {/* Bloc C : saisie d'une prescription médicale (médecin uniquement) */}
      <PrescriptionDialog
        open={prescriptionDialogOpen}
        onOpenChange={setPrescriptionDialogOpen}
        patientId={patientId}
        onCreated={loadAll}
      />
      <SimulationIADialog
        open={simulationDialogOpen}
        onOpenChange={setSimulationDialogOpen}
        patientId={patientId}
        photo={selectedPhotoForSim}
        photoUrl={selectedPhotoForSim ? photoUrls[selectedPhotoForSim.id] : ''}
        consentements={consentements}
        onConsentSigned={loadAll}
      />
      {/* Nouveau dialog : Comparaison Avant/Après */}
      <ComparaisonAvantApresDialog
        open={comparaisonDialogOpen}
        onOpenChange={setComparaisonDialogOpen}
        patientId={patientId}
        data={comparaisonData}
        urls={comparaisonUrls}
        isLoading={isComparaisonLoading}
        zoneFilter={comparaisonZoneFilter}
        onZoneChange={setComparaisonZoneFilter}
        onReload={handleOpenComparaison}
      />
      {/* Nouveau dialog : Raccourci « Photo Après » */}
      <QuickAfterPhotoDialog
        open={quickAfterDialogOpen}
        onOpenChange={setQuickAfterDialogOpen}
        patientId={patientId}
        photoAvant={quickAfterPhoto}
        onUploaded={loadAll}
      />
    </DashboardLayout>
  );
}

// ─────────────────────────────────────────────────────────
// ── Dialog Comparaison Avant/Après ──

function ComparaisonAvantApresDialog({
  open,
  onOpenChange,
  patientId: _patientId,
  data,
  urls,
  isLoading,
  zoneFilter,
  onZoneChange,
  onReload,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  patientId: number;
  data: ComparaisonAvantApres | null;
  urls: Record<string, string>;
  isLoading: boolean;
  zoneFilter: string;
  onZoneChange: (v: string) => void;
  onReload: () => void;
}) {
  const { t, i18n } = useTranslation();
  const [leftIndex, setLeftIndex] = useState(0);
  const [rightIndex, setRightIndex] = useState(0);

  useEffect(() => {
    if (open) {
      setLeftIndex(0);
      setRightIndex(0);
    }
  }, [open]);

  // Le filtre par zone est géré via le champ de saisie + le bouton Filtrer
  // qui relance la requête backend avec le paramètre zone.

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Eye className="w-5 h-5" />
            {t('medicalFile.comparisonTitle')}
          </DialogTitle>
          <DialogDescription>
            {t('medicalFile.comparisonDesc')}
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex justify-center py-16">
            <Spinner className="h-8 w-8" />
          </div>
        ) : !data ? (
          <div className="text-center py-8 text-muted-foreground">
            {t('medicalFile.noComparisonData')}
          </div>
        ) : (
          <div className="space-y-4">
            {/* Sélecteur de zone */}
            <div className="flex items-center gap-2">
              <Label className="text-sm whitespace-nowrap">{t('medicalFile.filterByZone')}</Label>
              <Input
                value={zoneFilter}
                onChange={(e) => onZoneChange(e.target.value)}
                placeholder={t('medicalFile.zonePlaceholder')}
                className="flex-1"
              />
              <Button variant="outline" size="sm" onClick={onReload}>
                {t('medicalFile.filter')}
              </Button>
            </div>

            {/* Sélecteurs de photos */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-sm font-medium text-center block">{t('medicalFile.before')}</Label>
                {data.avant.length > 0 ? (
                  <>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setLeftIndex((i) => Math.max(0, i - 1))}
                        disabled={leftIndex === 0}
                      >
                        ←
                      </Button>
                      <span className="text-xs text-muted-foreground">
                        {data.avant[leftIndex] ? new Date(data.avant[leftIndex].date).toLocaleDateString(i18n.language) : ''}
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setLeftIndex((i) => Math.min(data.avant.length - 1, i + 1))}
                        disabled={leftIndex >= data.avant.length - 1}
                      >
                        →
                      </Button>
                    </div>
                    <div className="aspect-square bg-muted rounded-md overflow-hidden">
                      {data.avant[leftIndex] && urls[`photo_${data.avant[leftIndex].id}`] ? (
                        <img
                          src={urls[`photo_${data.avant[leftIndex].id}`]}
                          alt={t('medicalFile.before')}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                          {data.avant[leftIndex] ? t('medicalFile.loading') : t('medicalFile.noPhotoShort')}
                        </div>
                      )}
                    </div>
                  </>
                ) : (
                  <div className="aspect-square bg-muted rounded-md flex items-center justify-center text-muted-foreground text-sm">
                    {t('medicalFile.noBeforePhoto')}
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <Label className="text-sm font-medium text-center block">{t('medicalFile.after')}</Label>
                {data.apres.length > 0 ? (
                  <>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setRightIndex((i) => Math.max(0, i - 1))}
                        disabled={rightIndex === 0}
                      >
                        ←
                      </Button>
                      <span className="text-xs text-muted-foreground">
                        {data.apres[rightIndex] ? new Date(data.apres[rightIndex].date).toLocaleDateString(i18n.language) : ''}
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setRightIndex((i) => Math.min(data.apres.length - 1, i + 1))}
                        disabled={rightIndex >= data.apres.length - 1}
                      >
                        →
                      </Button>
                    </div>
                    <div className="aspect-square bg-muted rounded-md overflow-hidden">
                      {data.apres[rightIndex] && urls[`photo_${data.apres[rightIndex].id}`] ? (
                        <img
                          src={urls[`photo_${data.apres[rightIndex].id}`]}
                          alt={t('medicalFile.after')}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                          {data.apres[rightIndex] ? t('medicalFile.loading') : t('medicalFile.noPhotoShort')}
                        </div>
                      )}
                    </div>
                  </>
                ) : (
                  <div className="aspect-square bg-muted rounded-md flex items-center justify-center text-muted-foreground text-sm">
                    {t('medicalFile.noAfterPhoto')}
                  </div>
                )}
              </div>
            </div>

            {/* Résumé */}
            <div className="text-center text-xs text-muted-foreground">
              {t('medicalFile.comparisonSummary', { before: data.avant.length, after: data.apres.length })}
              {zoneFilter && <span className="ml-2">{t('medicalFile.zoneLabel', { zone: zoneFilter })}</span>}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────
// ── Dialog Raccourci « Photo Après » ──

function QuickAfterPhotoDialog({
  open,
  onOpenChange,
  patientId,
  photoAvant,
  onUploaded,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  patientId: number;
  photoAvant: PhotoItem | null;
  onUploaded: () => void;
}) {
  const { t, i18n } = useTranslation();
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const zonePrefilled = photoAvant?.zone || '';

  useEffect(() => {
    if (open) {
      setFile(null);
      setIsUploading(false);
    }
  }, [open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) { toast.error(t('medicalFile.selectPhoto')); return; }
    setIsUploading(true);
    try {
      await photosApi.upload(patientId, file, {
        type_photo: 'apres',
        zone: zonePrefilled || undefined,
      });
      toast.success(t('medicalFile.afterPhotoSuccess'));
      onOpenChange(false);
      onUploaded();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('medicalFile.photoUploadError'));
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Camera className="w-5 h-5 text-green-600" />
            {t('medicalFile.addAfterPhoto')}
          </DialogTitle>
          <DialogDescription>
            {photoAvant
              ? t('medicalFile.afterPhotoLinkedDesc', { zone: photoAvant.zone || t('medicalFile.notSpecified'), date: new Date(photoAvant.date).toLocaleDateString(i18n.language) })
              : t('medicalFile.afterPhotoDesc')
            }
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="file-after">{t('medicalFile.photoFile')}</Label>
            <input
              id="file-after"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="w-full text-sm"
            />
            {file && (
              <p className="text-xs text-muted-foreground mt-1">
                {file.name} ({(file.size / 1024).toFixed(1)} Ko)
              </p>
            )}
          </div>
          <div>
            <Label>{t('medicalFile.anatomicalZone')}</Label>
            <div className="text-sm text-muted-foreground">
              {zonePrefilled || <span className="italic">{t('medicalFile.notSpecified')}</span>}
            </div>
          </div>
          <div>
            <Label>{t('medicalFile.type')}</Label>
            <div className="text-sm font-medium text-green-700">{t('medicalFile.after')}</div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={isUploading}>
              {isUploading ? <Spinner className="h-4 w-4 mr-2" /> : <Plus className="w-4 h-4 mr-2" />}
              {t('medicalFile.saveAfterPhoto')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────
// ── Dialog Simulation IA (inchangé — comportement identique) ──

function SimulationIADialog({ 
  open, onOpenChange, patientId, photo, photoUrl, consentements, onConsentSigned 
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  patientId: number;
  photo: PhotoItem | null;
  photoUrl: string;
  consentements: ConsentementItem[];
  onConsentSigned: () => void;
}) {
  const { t } = useTranslation();
  const [zone, setZone] = useState('');
  const [intensite, setIntensite] = useState(20);
  const [instructions, setInstructions] = useState('');
  const [masqueBase64, setMasqueBase64] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [showConsentSign, setShowConsentSign] = useState(false);
  const [showCrayonPad, setShowCrayonPad] = useState(false);

  const hasSimConsent = consentements.some(c => c.type === 'simulation_ia' && c.est_valide);

  useEffect(() => {
    if (open) {
      setZone(photo?.zone || '');
      setIntensite(20);
      setInstructions('');
      setMasqueBase64(null);
      setResultUrl(null);
      setShowConsentSign(false);
      setShowCrayonPad(false);
    }
  }, [open, photo]);

  const handleGenerate = async () => {
    if (!hasSimConsent) {
      setShowConsentSign(true);
      return;
    }

    setIsGenerating(true);
    try {
      const res = await api.post(`/simulation-ia/patients/${patientId}/photos/${photo?.id}/simuler`, {
        zone_anatomique: zone,
        intensite: intensite,
        instructions: instructions,
        masque_base64: masqueBase64
      });
      setResultUrl(res.data.url_resultat);
      toast.success(t('medicalFile.simGenerated'));
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('medicalFile.simError'));
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSignConsent = async (sigB64: string) => {
    try {
      await api.post(`/patients/${patientId}/consentements`, {
        type_consentement: 'simulation_ia',
        signature_base64: sigB64,
        methode_signature: 'tactile'
      });
      toast.success(t('medicalFile.aiConsentSigned'));
      setShowConsentSign(false);
      onConsentSigned();
    } catch (err: any) {
      toast.error(t('medicalFile.signError'));
    }
  };

  if (!photo) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-primary" />
            {t('medicalFile.simTitle')}
          </DialogTitle>
          <DialogDescription>
            {t('medicalFile.simDesc', { zone: photo.zone || t('medicalFile.notSpecified') })}
          </DialogDescription>
        </DialogHeader>

        {showConsentSign ? (
          <div className="space-y-4 py-4">
            <div className="bg-yellow-50 border border-yellow-200 p-4 rounded-md text-sm text-yellow-800">
              <strong>{t('medicalFile.consentRequiredStrong')}</strong> {t('medicalFile.consentRequiredText')}
            </div>
            <Label>{t('medicalFile.patientSignature')}</Label>
            <SignaturePad onSave={handleSignConsent} onCancel={() => setShowConsentSign(false)} />
          </div>
        ) : showCrayonPad ? (
          <SimulationCrayonPad 
            imageUrl={photoUrl} 
            onSave={(mask) => {
              setMasqueBase64(mask);
              setShowCrayonPad(false);
              toast.success(t('medicalFile.markingSaved'));
            }}
            onCancel={() => setShowCrayonPad(false)}
          />
        ) : resultUrl ? (
          <div className="space-y-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-center block">{t('medicalFile.originalBefore')}</Label>
                <div className="aspect-square bg-muted rounded-md overflow-hidden">
                  <img src={photoUrl} alt="Original" className="w-full h-full object-cover" />
                </div>
              </div>
              <div className="space-y-2">
                <Label className="text-center block">{t('medicalFile.aiSimulation')}</Label>
                <div className="aspect-square bg-muted rounded-md overflow-hidden relative">
                  <img src={resultUrl} alt="Simulation" className="w-full h-full object-cover" />
                  <div className="absolute bottom-2 right-2 bg-black/50 text-white text-[10px] px-2 py-0.5 rounded">
                    {t('medicalFile.nonContractual')}
                  </div>
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button onClick={() => onOpenChange(false)}>{t('medicalFile.close')}</Button>
            </DialogFooter>
          </div>
        ) : (
          <div className="space-y-6 py-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="aspect-square bg-muted rounded-md overflow-hidden">
                <img src={photoUrl} alt="Source" className="w-full h-full object-cover" />
              </div>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="zone">{t('medicalFile.anatomicalZone')}</Label>
                  <Input id="zone" value={zone} onChange={(e) => setZone(e.target.value)} placeholder={t('medicalFile.zoneExample')} />
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <Label htmlFor="intensite">{t('medicalFile.intensity')}</Label>
                    <span className="text-sm text-muted-foreground">{intensite}%</span>
                  </div>
                  <input 
                    type="range" 
                    id="intensite" 
                    min="0" max="100" 
                    value={intensite} 
                    onChange={(e) => setIntensite(parseInt(e.target.value))}
                    className="w-full"
                  />
                  <div className="flex justify-between text-[10px] text-muted-foreground">
                    <span>{t('medicalFile.natural')}</span>
                    <span>{t('medicalFile.marked')}</span>
                  </div>
                </div>
                
                <div className="space-y-2">
                  <Label>{t('medicalFile.preciseMarking')}</Label>
                  <Button 
                    variant="outline" 
                    className={`w-full ${masqueBase64 ? 'border-green-500 bg-green-50 text-green-700' : ''}`}
                    onClick={() => setShowCrayonPad(true)}
                  >
                    <Pencil className="w-4 h-4 mr-2" />
                    {masqueBase64 ? t('medicalFile.editMarking') : t('medicalFile.drawOnPhoto')}
                  </Button>
                  {masqueBase64 && <p className="text-[10px] text-green-600 text-center">{t('medicalFile.guideMaskActive')}</p>}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="instructions">{t('medicalFile.instructionEngine')}</Label>
                  <Textarea 
                    id="instructions" 
                    value={instructions} 
                    onChange={(e) => setInstructions(e.target.value)} 
                    placeholder={t('medicalFile.instructionPlaceholder')}
                    className="h-20 text-xs"
                  />
                </div>

                <div className="pt-2">
                  <Button className="w-full" onClick={handleGenerate} disabled={isGenerating}>
                    {isGenerating ? <Spinner className="h-4 w-4 mr-2" /> : <Sparkles className="w-4 h-4 mr-2" />}
                    {hasSimConsent ? t('medicalFile.generateSimulation') : t('medicalFile.signAndGenerate')}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────
// ── Dialog Nouveau Dossier (inchangé) ──

function NewDossierDialog({ open, onOpenChange, patientId, actes, canToggleActePrices, currentUserId, onCreated }: {
  open: boolean; onOpenChange: (v: boolean) => void; patientId: number; actes: Acte[];
  canToggleActePrices: boolean; currentUserId: number; onCreated: () => void;
}) {
  const { t } = useTranslation();
  const currency = useCurrency();
  const [selectedActes, setSelectedActes] = useState<{id: number, nom: string, prix: number}[]>([]);
  const [manualLignes, setManualLignes] = useState<{nom: string, prix: number}[]>([]);
  const [observations, setObservations] = useState('');
  const [effetsSecondaires, setEffetsSecondaires] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [showActePrices, setShowActePrices] = useState(false);

  // ── Scribe IA & Dictée Vocale ──
  const [isRecording, setIsRecording] = useState(false);
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
  const [isTranscribing, setIsRecordingLoading] = useState(false);
  const [isProcessingSoap, setIsProcessingSoap] = useState(false);

  useEffect(() => {
    if (open) { 
      setSelectedActes([]); 
      setManualLignes([]);
      setObservations(''); 
      setEffetsSecondaires(''); 
      setIsSaving(false);
      setShowActePrices(!canToggleActePrices);
    }
  }, [open]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks: Blob[] = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data);
      };

      recorder.onstop = async () => {
        const audioBlob = new Blob(chunks, { type: 'audio/webm' });
        handleTranscribe(audioBlob);
        stream.getTracks().forEach(track => track.stop());
      };

      recorder.start();
      setMediaRecorder(recorder);
      setIsRecording(true);
      toast.info(t('medicalFile.recordingInProgress'));
    } catch (err) {
      toast.error(t('medicalFile.micDenied'));
    }
  };

  const stopRecording = () => {
    if (mediaRecorder && isRecording) {
      mediaRecorder.stop();
      setIsRecording(false);
    }
  };

  const handleTranscribe = async (blob: Blob) => {
    setIsRecordingLoading(true);
    try {
      const res = await scribeIaApi.transcribe(blob);
      setObservations(prev => prev ? prev + "\n" + res.data.text : res.data.text);
      toast.success(t('medicalFile.transcriptionSuccess'));
    } catch (err) {
      toast.error(t('medicalFile.transcriptionFailed'));
    } finally {
      setIsRecordingLoading(false);
    }
  };

  const handleScribeProcess = async () => {
    if (!observations || observations.length < 10) {
      toast.error(t('medicalFile.obsTooShort'));
      return;
    }
    setIsProcessingSoap(true);
    try {
      const res = await scribeIaApi.process(patientId, observations);
      const soap = res.data.notes_structurees_soap;
      const formatted = `[SUBJECTIVE]\n${soap.subjective}\n\n[OBJECTIVE]\n${soap.objective}\n\n[ASSESSMENT]\n${soap.assessment}\n\n[PLAN]\n${soap.plan}`;
      setObservations(formatted);
      toast.success(t('medicalFile.soapGenerated'));
    } catch (err) {
      toast.error(t('medicalFile.scribeError'));
    } finally {
      setIsProcessingSoap(false);
    }
  };

  const addActe = (id: string) => {
    const acte = actes.find(a => String(a.id) === id);
    if (acte && !selectedActes.find(a => a.id === acte.id)) {
      setSelectedActes([...selectedActes, { id: acte.id, nom: acte.nom, prix: acte.prix_base || 0 }]);
    }
  };

  const addManualLigne = () => {
    setManualLignes([...manualLignes, { nom: '', prix: 0 }]);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedActes.length === 0 && manualLignes.filter(l => l.nom).length === 0) {
      toast.error(t('medicalFile.selectActOrLine'));
      return;
    }
    setIsSaving(true);
    try {
      const allActes = [
        ...selectedActes.map(a => ({ id: a.id, nom: a.nom, prix: a.prix })),
        ...manualLignes.filter(l => l.nom).map(l => ({ nom: l.nom, prix: l.prix }))
      ];

      await dossierMedicalApi.create(patientId, {
        praticien_id: currentUserId,
        acte_id: selectedActes[0]?.id, // Garder le premier comme acte principal pour la compatibilité
        date_acte: new Date().toISOString(),
        observations: observations || undefined,
        effets_secondaires: effetsSecondaires || undefined,
        actes_details: allActes
      });
      toast.success(t('medicalFile.dossierCreated'));
      onOpenChange(false);
      onCreated();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('medicalFile.dossierCreateError'));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[95vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-purple-600" />
            {t('medicalFile.newDossierTitle')}
          </DialogTitle>
          <DialogDescription>{t('medicalFile.newDossierDesc')}</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <div>
                <Label>{t('medicalFile.catalogActes')}</Label>
                <select 
                  className="w-full h-9 px-3 border rounded-md text-sm mb-2"
                  onChange={(e) => addActe(e.target.value)}
                  value=""
                >
                  <option value="">{t('medicalFile.addActeOption')}</option>
                  {actes.map((a) => (
                    <option key={a.id} value={a.id}>
                      {showActePrices
                        ? `${a.nom} (${Number(a.prix_base).toFixed(3)} ${currency.currency_symbol})`
                        : a.nom}
                    </option>
                  ))}
                </select>
                
                <div className="space-y-2">
                  {selectedActes.map((a, i) => (
                    <div key={i} className="flex items-center justify-between p-2 bg-purple-50 rounded border border-purple-100">
                      <span className="text-sm font-medium">{a.nom}</span>
                      <Button type="button" variant="ghost" size="sm" onClick={() => setSelectedActes(selectedActes.filter((_, idx) => idx !== i))}>
                        <Trash2 className="w-3 h-3 text-destructive" />
                      </Button>
                    </div>
                  ))}
                </div>
                {canToggleActePrices && (
                  <div className="flex justify-end pt-2">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="text-xs text-muted-foreground"
                      onClick={() => setShowActePrices((visible) => !visible)}
                      aria-pressed={showActePrices}
                      title={showActePrices ? t('medicalFile.hidePrices') : t('medicalFile.showPrices')}
                    >
                      {showActePrices ? <EyeOff className="mr-1.5 h-3.5 w-3.5" /> : <Eye className="mr-1.5 h-3.5 w-3.5" />}
                      {showActePrices ? t('medicalFile.hidePrices') : t('medicalFile.showPrices')}
                    </Button>
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <Label>{t('medicalFile.manualEntry')}</Label>
                  <Button type="button" variant="outline" size="xs" onClick={addManualLigne} className="h-7 text-[10px]">
                    <Plus className="w-3 h-3 mr-1" /> {t('medicalFile.line')}
                  </Button>
                </div>
                {manualLignes.map((l, i) => (
                  <div key={i} className="flex gap-2">
                    <Input 
                      placeholder={t('medicalFile.actePlaceholder')} 
                      value={l.nom} 
                      onChange={(e) => setManualLignes(manualLignes.map((item, idx) => idx === i ? {...item, nom: e.target.value} : item))}
                      className="flex-1 h-8 text-sm"
                    />
                    <Input 
                      type="number" 
                      placeholder={t('medicalFile.pricePlaceholder')} 
                      value={l.prix} 
                      onChange={(e) => setManualLignes(manualLignes.map((item, idx) => idx === i ? {...item, prix: Number(e.target.value)} : item))}
                      className="w-20 h-8 text-sm"
                    />
                    <Button type="button" variant="ghost" size="sm" onClick={() => setManualLignes(manualLignes.filter((_, idx) => idx !== i))}>
                      <Trash2 className="w-3 h-3 text-destructive" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <Label htmlFor="observations">{t('medicalFile.medicalObservations')}</Label>
                <div className="flex gap-1">
                  {isRecording ? (
                    <Button type="button" size="xs" variant="destructive" onClick={stopRecording} className="h-7 animate-pulse">
                      <Square className="w-3 h-3 mr-1" /> {t('medicalFile.stop')}
                    </Button>
                  ) : (
                    <Button type="button" size="xs" variant="outline" onClick={startRecording} className="h-7 text-red-600 border-red-200">
                      <Mic className="w-3 h-3 mr-1" /> {t('medicalFile.dictation')}
                    </Button>
                  )}
                  <Button 
                    type="button" 
                    size="xs" 
                    variant="secondary" 
                    onClick={handleScribeProcess} 
                    disabled={isProcessingSoap || !observations}
                    className="h-7"
                  >
                    {isProcessingSoap ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3 mr-1" />}
                    {t('medicalFile.soap')}
                  </Button>
                </div>
              </div>
              <div className="relative">
                <Textarea 
                  id="observations" 
                  value={observations} 
                  onChange={(e) => setObservations(e.target.value)} 
                  rows={8} 
                  className="text-sm font-mono"
                  placeholder={t('medicalFile.dictationPlaceholder')}
                />
                {isTranscribing && (
                  <div className="absolute inset-0 bg-white/60 flex items-center justify-center">
                    <div className="flex items-center gap-2 text-xs font-medium">
                      <Loader2 className="w-4 h-4 animate-spin" /> {t('medicalFile.transcribing')}
                    </div>
                  </div>
                )}
              </div>
              <div className="grid gap-2">
                <Label htmlFor="effets" className="text-xs">{t('medicalFile.sideEffectsNotes')}</Label>
                <Textarea id="effets" value={effetsSecondaires} onChange={(e) => setEffetsSecondaires(e.target.value)} rows={2} className="text-sm" />
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={isSaving} className="bg-purple-600 hover:bg-purple-700">
              {isSaving ? <Spinner className="h-4 w-4" /> : t('medicalFile.validateForBilling')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────
// ── Dialog Signer Consentement (inchangé) ──

function SignConsentDialog({ open, onOpenChange, patientId, actes, onSigned }: {
  open: boolean; onOpenChange: (v: boolean) => void; patientId: number; actes: Acte[]; onSigned: () => void;
}) {
  const { t } = useTranslation();
  const [acteId, setActeId] = useState('');
  const [signing, setSigning] = useState(false);

  useEffect(() => { if (open) { setActeId(''); setSigning(false); } }, [open]);

  const handleSave = async (base64: string) => {
    try {
      await dossierMedicalApi.signConsentement(patientId, {
        acte_id: acteId ? Number(acteId) : undefined,
        signature_base64: base64,
        methode_signature: 'tactile',
      });
      toast.success(t('medicalFile.consentSigned'));
      onOpenChange(false);
      onSigned();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('medicalFile.signError'));
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('medicalFile.signConsentTitle')}</DialogTitle>
          <DialogDescription>{t('medicalFile.signConsentDesc')}</DialogDescription>
        </DialogHeader>
        {!signing ? (
          <div className="space-y-4">
            <div>
              <Label htmlFor="acte-consent">{t('medicalFile.acteConcerned')}</Label>
              <select id="acte-consent" value={acteId} onChange={(e) => setActeId(e.target.value)} className="w-full h-9 px-3 border rounded-md text-sm">
                <option value="">{t('medicalFile.notSpecifiedOption')}</option>
                {actes.map((a) => <option key={a.id} value={a.id}>{a.nom}</option>)}
              </select>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>{t('common.cancel')}</Button>
              <Button type="button" onClick={() => setSigning(true)}>{t('medicalFile.continueToSignature')}</Button>
            </DialogFooter>
          </div>
        ) : (
          <SignaturePad onSave={handleSave} onCancel={() => setSigning(false)} />
        )}
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────
// ── Dialog Ajouter Photo (inchangé — comportement identique) ──

function UploadPhotoDialog({ open, onOpenChange, patientId, onUploaded }: {
  open: boolean; onOpenChange: (v: boolean) => void; patientId: number; onUploaded: () => void;
}) {
  const { t } = useTranslation();
  const [file, setFile] = useState<File | null>(null);
  const [typePhoto, setTypePhoto] = useState('avant');
  const [zone, setZone] = useState('');
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => { if (open) { setFile(null); setTypePhoto('avant'); setZone(''); } }, [open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) { toast.error(t('medicalFile.selectPhoto')); return; }
    setIsUploading(true);
    try {
      await photosApi.upload(patientId, file, { type_photo: typePhoto, zone: zone || undefined });
      toast.success(t('medicalFile.photoAdded'));
      onOpenChange(false);
      onUploaded();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('medicalFile.photoUploadError'));
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('medicalFile.addMedicalPhoto')}</DialogTitle>
          <DialogDescription>{t('medicalFile.addMedicalPhotoDesc')}</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="file">{t('medicalFile.file')}</Label>
            <input
              id="file"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="w-full text-sm"
            />
          </div>
          <div>
            <Label htmlFor="type_photo">{t('medicalFile.type')}</Label>
            <select id="type_photo" value={typePhoto} onChange={(e) => setTypePhoto(e.target.value)} className="w-full h-9 px-3 border rounded-md text-sm">
              <option value="avant">{t('medicalFile.before')}</option>
              <option value="apres">{t('medicalFile.after')}</option>
              <option value="progression">{t('medicalFile.progression')}</option>
              <option value="complication">{t('medicalFile.complication')}</option>
              <option value="autre">{t('medicalFile.other')}</option>
            </select>
          </div>
          <div>
            <Label htmlFor="zone">{t('medicalFile.anatomicalZone')}</Label>
            <input id="zone" value={zone} onChange={(e) => setZone(e.target.value)} placeholder={t('medicalFile.zoneHint')} className="w-full h-9 px-3 border rounded-md text-sm" />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={isUploading}>{isUploading ? <Spinner className="h-4 w-4" /> : t('medicalFile.send')}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────
// ── Bloc B : Dialog « Nouveau fait médical structuré » ──
// Saisie réservée au médecin ; l'auteur est déduit côté backend
// de l'utilisateur authentifié (jamais envoyé par le client).

const FACT_TYPE_FIELD_LABELS: Record<string, { principal: string; champs: string[] }> = {
  allergie: { principal: 'medicalFile.fieldSubstance', champs: ['substance', 'reaction'] },
  traitement: { principal: 'medicalFile.fieldMedication', champs: ['medicament', 'posologie'] },
  contre_indication: { principal: 'medicalFile.factTypeContreIndication', champs: ['motif'] },
  antecedent_medical: { principal: 'medicalFile.fieldDescription', champs: ['description'] },
  antecedent_chirurgical: { principal: 'medicalFile.fieldIntervention', champs: ['intervention', 'date_intervention'] },
  antecedent_anesthesique: { principal: 'medicalFile.fieldDescription', champs: ['description'] },
  antecedent_familial: { principal: 'medicalFile.fieldDescription', champs: ['description'] },
};

function MedicalFactDialog({
  open,
  onOpenChange,
  patientId,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  patientId: number;
  onCreated: () => void;
}) {
  const { t } = useTranslation();
  const [typeFait, setTypeFait] = useState('allergie');
  const [valeurPrincipale, setValeurPrincipale] = useState('');
  const [champSecondaire, setChampSecondaire] = useState('');
  const [verificationStatus, setVerificationStatus] = useState('VERIFIED');
  const [isSaving, setIsSaving] = useState(false);

  const config = FACT_TYPE_FIELD_LABELS[typeFait] ?? FACT_TYPE_FIELD_LABELS.antecedent_medical;
  const secondaryKey = config.champs[1] ?? null;
  const primaryKey = config.champs[0];

  useEffect(() => {
    if (open) {
      setValeurPrincipale('');
      setChampSecondaire('');
      setVerificationStatus('VERIFIED');
    }
  }, [open, typeFait]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!valeurPrincipale.trim()) return;
    setIsSaving(true);
    try {
      const donnees: Record<string, unknown> = { [primaryKey]: valeurPrincipale.trim() };
      if (secondaryKey && champSecondaire.trim()) donnees[secondaryKey] = champSecondaire.trim();
      await medicalFactsApi.create(patientId, {
        type_fait: typeFait,
        donnees,
        source: 'MANUAL',
        verification_status: verificationStatus as 'VERIFIED' | 'PENDING_VERIFICATION' | 'HISTORICAL_UNSTRUCTURED',
      });
      toast.success(t('medicalFile.factSaved'));
      onOpenChange(false);
      onCreated();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('medicalFile.saveError'));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <HeartPulse className="w-5 h-5" />
            {t('medicalFile.newFactTitle')}
          </DialogTitle>
          <DialogDescription>
            {t('medicalFile.newFactDesc')}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="type_fait">{t('medicalFile.factTypeLabel')}</Label>
            <select
              id="type_fait"
              value={typeFait}
              onChange={(e) => setTypeFait(e.target.value)}
              className="w-full h-9 px-3 border rounded-md text-sm"
            >
              {Object.entries(FACT_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{t(label)}</option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="fait_principal">{t(config.principal)}</Label>
            <Input
              id="fait_principal"
              value={valeurPrincipale}
              onChange={(e) => setValeurPrincipale(e.target.value)}
              required
              className="w-full"
            />
          </div>
          {secondaryKey && (
            <div>
              <Label htmlFor="fait_secondaire">
                {secondaryKey === 'reaction' ? t('medicalFile.reactionObserved') : secondaryKey === 'posologie' ? t('medicalFile.dosage') : secondaryKey === 'date_intervention' ? t('medicalFile.interventionDate') : t('medicalFile.precision')}
              </Label>
              <Input
                id="fait_secondaire"
                value={champSecondaire}
                onChange={(e) => setChampSecondaire(e.target.value)}
                className="w-full"
              />
            </div>
          )}
          <div>
            <Label htmlFor="verification_status">{t('medicalFile.verificationStatus')}</Label>
            <select
              id="verification_status"
              value={verificationStatus}
              onChange={(e) => setVerificationStatus(e.target.value)}
              className="w-full h-9 px-3 border rounded-md text-sm"
            >
              <option value="VERIFIED">{t('medicalFile.verified')}</option>
              <option value="PENDING_VERIFICATION">{t('medicalFile.toVerify')}</option>
              <option value="HISTORICAL_UNSTRUCTURED">{t('medicalFile.historicalUnstructured')}</option>
            </select>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={isSaving}>
              {isSaving ? <Spinner className="h-4 w-4" /> : t('common.save')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────
// ── Bloc C : Dialog « Nouvelle prescription médicale » ──
// Saisie réservée au médecin ; le prescripteur est déduit côté
// backend de l'utilisateur authentifié (jamais envoyé par le client).

function PrescriptionDialog({
  open,
  onOpenChange,
  patientId,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  patientId: number;
  onCreated: () => void;
}) {
  const { t } = useTranslation();
  const [type, setType] = useState<'medicament' | 'analyse'>('medicament');
  const [medicament, setMedicament] = useState('');
  const [dosage, setDosage] = useState('');
  const [frequence, setFrequence] = useState('');
  const [duree, setDuree] = useState('');
  const [instructions, setInstructions] = useState('');
  const [analyse, setAnalyse] = useState('');
  const [laboratoire, setLaboratoire] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setType('medicament');
      setMedicament('');
      setDosage('');
      setFrequence('');
      setDuree('');
      setInstructions('');
      setAnalyse('');
      setLaboratoire('');
    }
  }, [open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (type === 'medicament' && !medicament.trim()) return;
    if (type === 'analyse' && !analyse.trim()) return;
    setIsSaving(true);
    try {
      const details: Record<string, unknown> =
        type === 'analyse'
          ? { type: 'analyse', analyse: analyse.trim(), laboratoire: laboratoire.trim() || undefined, instructions: instructions.trim() || undefined }
          : { type: 'medicament', medicament: medicament.trim(), dosage: dosage.trim() || undefined, frequence: frequence.trim() || undefined, duree: duree.trim() || undefined, instructions: instructions.trim() || undefined };
      await prescriptionsApi.create(patientId, { details, statut: 'ACTIVE' });
      toast.success(type === 'analyse' ? t('medicalFile.analysisRequested') : t('medicalFile.prescriptionSaved'));
      onOpenChange(false);
      onCreated();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('medicalFile.saveError'));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {type === 'analyse' ? <FlaskConical className="w-5 h-5" /> : <Pill className="w-5 h-5" />}
            {type === 'analyse' ? t('medicalFile.requestAnalysis') : t('medicalFile.newPrescriptionTitle')}
          </DialogTitle>
          <DialogDescription>
            {type === 'analyse' ? t('medicalFile.analysisDesc') : t('medicalFile.prescriptionDesc')}
          </DialogDescription>
        </DialogHeader>
        <div className="flex gap-1 rounded-md bg-muted p-1">
          <button
            type="button"
            onClick={() => setType('medicament')}
            className={`flex-1 rounded px-3 py-1.5 text-sm font-medium transition-colors ${type === 'medicament' ? 'bg-background shadow-sm' : 'text-muted-foreground'}`}
          >
            <Pill className="w-3.5 h-3.5 inline mr-1" /> {t('medicalFile.medicationTab')}
          </button>
          <button
            type="button"
            onClick={() => setType('analyse')}
            className={`flex-1 rounded px-3 py-1.5 text-sm font-medium transition-colors ${type === 'analyse' ? 'bg-background shadow-sm' : 'text-muted-foreground'}`}
          >
            <FlaskConical className="w-3.5 h-3.5 inline mr-1" /> {t('medicalFile.analysisTab')}
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          {type === 'medicament' ? (
            <>
              <div>
                <Label htmlFor="presc_medicament">{t('medicalFile.medicationProduct')}</Label>
                <Input
                  id="presc_medicament"
                  value={medicament}
                  onChange={(e) => setMedicament(e.target.value)}
                  required
                  className="w-full"
                  autoFocus
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="presc_dosage">{t('medicalFile.dosage')}</Label>
                  <Input id="presc_dosage" value={dosage} onChange={(e) => setDosage(e.target.value)} placeholder={t('medicalFile.dosageExample')} className="w-full" />
                </div>
                <div>
                  <Label htmlFor="presc_frequence">{t('medicalFile.frequency')}</Label>
                  <Input id="presc_frequence" value={frequence} onChange={(e) => setFrequence(e.target.value)} placeholder={t('medicalFile.frequencyExample')} className="w-full" />
                </div>
              </div>
              <div>
                <Label htmlFor="presc_duree">{t('medicalFile.duration')}</Label>
                <Input id="presc_duree" value={duree} onChange={(e) => setDuree(e.target.value)} placeholder={t('medicalFile.durationExample')} className="w-full" />
              </div>
            </>
          ) : (
            <>
              <div>
                <Label htmlFor="presc_analyse">{t('medicalFile.analysesRequested')}</Label>
                <Textarea
                  id="presc_analyse"
                  value={analyse}
                  onChange={(e) => setAnalyse(e.target.value)}
                  placeholder={t('medicalFile.analysesPlaceholder')}
                  required
                  rows={4}
                  className="w-full"
                  autoFocus
                />
                <p className="text-xs text-muted-foreground mt-1">{t('medicalFile.oneAnalysisPerLine')}</p>
              </div>
              <div>
                <Label htmlFor="presc_labo">{t('medicalFile.laboratoryOptional')}</Label>
                <Input id="presc_labo" value={laboratoire} onChange={(e) => setLaboratoire(e.target.value)} placeholder={t('medicalFile.labExample')} className="w-full" />
              </div>
            </>
          )}
          {type === 'medicament' && (
            <div>
              <Label htmlFor="presc_instructions">{t('medicalFile.instructions')}</Label>
              <Textarea id="presc_instructions" value={instructions} onChange={(e) => setInstructions(e.target.value)} rows={3} className="w-full" />
            </div>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={isSaving}>
              {isSaving ? <Spinner className="h-4 w-4" /> : t('common.save')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
