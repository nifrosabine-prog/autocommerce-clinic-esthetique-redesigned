import React, { useState, useEffect, useCallback } from 'react';
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
import { FileText, Image as ImageIcon, CheckCircle, Download, Plus, Trash2, User, Phone, ArrowLeft, Sparkles, Camera, SlidersHorizontal, Eye, EyeOff, Zap, Mic, Square, Loader2, Pencil, ExternalLink, Save, HeartPulse, Pill } from 'lucide-react';
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
  antecedent_medical: 'Antécédent médical',
  antecedent_chirurgical: 'Antécédent chirurgical',
  antecedent_anesthesique: 'Antécédent anesthésique',
  antecedent_familial: 'Antécédent familial',
  allergie: 'Allergie',
  traitement: 'Traitement',
  contre_indication: 'Contre-indication',
};

/** Interface pour la réponse de comparaison avant/après */
interface ComparaisonAvantApres {
  avant: { id: number; url: string; date: string }[];
  apres: { id: number; url: string; date: string }[];
}

export default function MedicalFile({ patientId }: { patientId: number }) {
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
      else toast.error("Impossible de charger la fiche patient");

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
      toast.success('Dossier patient enregistré avec succès');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Impossible d’enregistrer le dossier patient');
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
      toast.error(err.response?.data?.detail || 'Document signé indisponible');
    }
  };

  const handleExportPdf = async () => {
    setIsExporting(true);
    try {
      await dossierMedicalApi.downloadExportPdf(patientId);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Erreur lors de l'export PDF");
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
      toast.error(err.response?.data?.detail || 'Erreur lors de l’export structuré');
    }
  };

  const handleDeletePhoto = async (photoId: number) => {
    try {
      await photosApi.delete(patientId, photoId);
      toast.success('Photo supprimée');
      loadAll();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur lors de la suppression');
    }
  };

  // ── Bloc B : désactivation logique d'un fait médical (réservée au médecin) ──
  const handleDeleteFact = async (factId: number) => {
    try {
      await medicalFactsApi.delete(patientId, factId);
      toast.success('Donnée médicale archivée');
      loadAll();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur lors de la désactivation');
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
      toast.error(err.response?.data?.detail || "Erreur lors du chargement de la comparaison");
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
          Patient introuvable ou accès non autorisé.
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
              <ArrowLeft className="w-4 h-4 mr-1" /> Retour aux patients
            </Button>
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <User className="w-7 h-7 text-muted-foreground" />
              {patient.prenom} {patient.nom}
            </h1>
            <p className="text-muted-foreground mt-1 flex items-center gap-1">
              <Phone className="w-4 h-4" /> {patient.telephone}
              {patient.date_naissance && ` · Né(e) le ${new Date(patient.date_naissance).toLocaleDateString('fr-TN')}`}
            </p>
          </div>
          {user?.role === 'medecin' && <div className="flex gap-2">
            <Button variant="outline" onClick={handleExportStructured}><Download className="w-4 h-4 mr-2" />Export JSON</Button>
            <Button onClick={handleExportPdf} disabled={isExporting}>
              {isExporting ? <Spinner className="h-4 w-4 mr-2" /> : <Download className="w-4 h-4 mr-2" />}
              Exporter PDF
            </Button>
          </div>}
        </div>

        {user?.role === 'assistante' && (
          <Card className="border-purple-200 bg-purple-50/30">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base"><FileText className="h-4 w-4" /> Fiche administrative patient</CardTitle>
              <p className="text-sm text-muted-foreground">Complétez les coordonnées et informations déclaratives. La création du dossier clinique reste réservée au médecin.</p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                {([['prenom', 'Prénom'], ['nom', 'Nom'], ['date_naissance', 'Date de naissance'], ['email', 'E-mail'], ['adresse', 'Adresse'], ['ville', 'Ville'], ['groupe_sanguin', 'Groupe sanguin']] as const).map(([key, label]) => (
                  <div key={key}>
                    <Label htmlFor={`intake-${key}`}>{label}</Label>
                    <Input id={`intake-${key}`} type={key === 'date_naissance' ? 'date' : 'text'} value={intake[key]} onChange={(e) => setIntake((prev) => ({ ...prev, [key]: e.target.value }))} />
                  </div>
                ))}
              </div>
              <div className="flex justify-end">
                <Button onClick={handleSaveIntake} disabled={isSavingIntake}><Save className="mr-2 h-4 w-4" />{isSavingIntake ? 'Enregistrement…' : 'Enregistrer les informations'}</Button>
              </div>
            </CardContent>
          </Card>
        )}

        {(patient.allergies || patient.contre_indications) && (
          <Card className="border-destructive/40 bg-destructive/5">
            <CardContent className="py-4 space-y-1">
              {patient.allergies && <p><strong>Allergies :</strong> {patient.allergies}</p>}
              {patient.contre_indications && <p><strong>Contre-indications :</strong> {patient.contre_indications}</p>}
            </CardContent>
          </Card>
        )}
        {canSeeAntecedents && patient.antecedents_medicaux && (
          <Card>
            <CardContent className="py-4">
              <p><strong>Antécédents médicaux :</strong> {patient.antecedents_medicaux}</p>
            </CardContent>
          </Card>
        )}

        {user?.role === 'medecin' && (
          <Card>
            <CardHeader><CardTitle className="text-base">Chronologie clinique globale</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {globalTimeline.length === 0 ? <p className="text-sm text-muted-foreground">Aucune entrée clinique.</p> : globalTimeline.slice(0, 8).map((entry, index) => (
                <div key={`${entry.type}-${entry.date}-${index}`} className="flex items-center justify-between border-b last:border-0 py-2 text-sm">
                  <span><strong>{entry.type}</strong> — {entry.summary}</span><span className="text-muted-foreground">{new Date(entry.date).toLocaleString('fr-TN')}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="dossiers"><FileText className="w-4 h-4 mr-1" /> Dossiers ({timeline.length})</TabsTrigger>
            <TabsTrigger value="consentements"><CheckCircle className="w-4 h-4 mr-1" /> Consentements ({consentements.length})</TabsTrigger>
            <TabsTrigger value="photos"><ImageIcon className="w-4 h-4 mr-1" /> Photos ({photos.length})</TabsTrigger>
            <TabsTrigger value="faits-medicaux"><HeartPulse className="w-4 h-4 mr-1" /> Faits médicaux ({facts.length})</TabsTrigger>
            <TabsTrigger value="prescriptions"><Pill className="w-4 h-4 mr-1" /> Prescriptions ({prescriptions.length})</TabsTrigger>
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
                  <Plus className="w-4 h-4 mr-1" /> Nouveau dossier
                </Button>
              ) : (
                <p className="text-sm text-muted-foreground">La création de dossiers est réservée aux médecins.</p>
              )}
            </div>
            {timeline.length === 0 ? (
              <Card><CardContent className="py-8 text-center text-muted-foreground">Aucun dossier trouvé</CardContent></Card>
            ) : (
              timeline.map((item) => (
                <Card key={item.dossier_id}>
                  <CardHeader>
                    <CardTitle className="text-base flex justify-between items-center">
                      <span>{item.acte} — {new Date(item.date).toLocaleDateString('fr-TN')}</span>
                      <div className="flex items-center gap-2">
                        {item.facture_id || item.statut_facturation === 'facture' ? (
                          <Badge className="h-8 bg-emerald-100 text-emerald-800 hover:bg-emerald-100">
                            <CheckCircle className="w-3 h-3 mr-1" />
                            Déjà facturé{item.facture_numero ? ` · ${item.facture_numero}` : ''}
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="h-8 border-amber-200 bg-amber-50 text-amber-800">
                            En attente de facturation
                          </Badge>
                        )}
                        <Badge variant="outline">{item.praticien}</Badge>
                      </div>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    {item.observations && <p><strong>Observations :</strong> {item.observations}</p>}
                    {item.effets_secondaires && <p><strong>Effets secondaires :</strong> {item.effets_secondaires}</p>}
                    {item.satisfaction && <p><strong>Satisfaction :</strong> {item.satisfaction}/5</p>}
                    {item.photos.length > 0 && (
                      <p className="text-muted-foreground">{item.photos.length} photo(s) associée(s)</p>
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
                  <Plus className="w-4 h-4 mr-1" /> Nouveau fait médical
                </Button>
              ) : (
                <p className="text-sm text-muted-foreground">La saisie des faits médicaux est réservée aux médecins.</p>
              )}
            </div>
            {facts.length === 0 ? (
              <Card><CardContent className="py-8 text-center text-muted-foreground">Aucun fait médical enregistré</CardContent></Card>
            ) : (
              <Card>
                <CardContent className="py-4 space-y-3">
                  {facts.map((f) => (
                    <div key={f.id} className="flex items-center justify-between border-b last:border-0 pb-2 last:pb-0 gap-2">
                      <div className="min-w-0">
                        <p className="font-medium">{FACT_TYPE_LABELS[f.type_fait] ?? f.type_fait}</p>
                        <p className="text-sm text-muted-foreground truncate">
                          {Object.entries(f.donnees ?? {}).map(([k, v]) => `${k} : ${String(v)}`).join(' · ') || '—'}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {new Date(f.created_at).toLocaleDateString('fr-TN')}
                          {' · '}{f.verification_status === 'VERIFIED' ? 'Vérifié' : f.verification_status === 'PENDING_VERIFICATION' ? 'À vérifier' : 'Historique non structuré'}
                        </p>
                      </div>
                      {user?.role === 'medecin' && (
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0 text-destructive" aria-label="Archiver ce fait médical">
                              <Trash2 className="w-3.5 h-3.5" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Archiver cette donnée médicale ?</AlertDialogTitle>
                              <AlertDialogDescription>
                                La donnée sera masquée (suppression logique) ; l'historique clinique et le journal d'audit médical sont conservés.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Annuler</AlertDialogCancel>
                              <AlertDialogAction onClick={() => handleDeleteFact(f.id)}>Archiver</AlertDialogAction>
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
                  <Plus className="w-4 h-4 mr-1" /> Nouvelle prescription
                </Button>
              ) : (
                <p className="text-sm text-muted-foreground">La création de prescriptions est réservée aux médecins.</p>
              )}
            </div>
            {prescriptions.length === 0 ? (
              <Card><CardContent className="py-8 text-center text-muted-foreground">Aucune prescription enregistrée</CardContent></Card>
            ) : (
              <Card>
                <CardContent className="py-4 space-y-3">
                  {prescriptions.map((p) => (
                    <div key={p.id} className="border-b last:border-0 pb-3 last:pb-0">
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-medium">{String(p.details?.medicament ?? 'Prescription')}</p>
                        <Badge
                          variant="outline"
                          className={p.statut === 'ACTIVE' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : p.statut === 'COMPLETED' ? 'border-sky-200 bg-sky-50 text-sky-800' : 'border-slate-200 bg-slate-50 text-slate-600'}
                        >
                          {p.statut === 'ACTIVE' ? 'Active' : p.statut === 'COMPLETED' ? 'Terminée' : 'Annulée'}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {[p.details?.dosage, p.details?.frequence, p.details?.duree].filter(Boolean).join(' · ') || '—'}
                      </p>
                      {p.details?.instructions ? <p className="text-sm text-muted-foreground">{String(p.details.instructions)}</p> : null}
                      <p className="text-xs text-muted-foreground">Prescrite le {new Date(p.date_prescription).toLocaleDateString('fr-TN')}</p>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* ── Consentements ── */}
          <TabsContent value="consentements" className="space-y-4">
            <div className="flex justify-end">
              {canManageClinicalEntries ? (
                <Button size="sm" onClick={() => setConsentDialogOpen(true)}>
                  <Plus className="w-4 h-4 mr-1" /> Signer un consentement
                </Button>
              ) : (
                <p className="text-sm text-muted-foreground">La signature des consentements est réservée aux médecins.</p>
              )}
            </div>
            {consentements.length === 0 ? (
              <Card><CardContent className="py-8 text-center text-muted-foreground">Aucun consentement trouvé</CardContent></Card>
            ) : (
              <Card>
                <CardContent className="py-4 space-y-3">
                  {consentements.map((c) => (
                    <div key={c.id} className="flex items-center justify-between border-b last:border-0 pb-2 last:pb-0">
                      <div>
                        <p className="font-medium">{c.type}</p>
                        <p className="text-sm text-muted-foreground">
                          Signé le {new Date(c.signe_le).toLocaleDateString('fr-TN')} ({c.methode})
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant={c.est_valide ? 'default' : 'destructive'}>
                          {c.est_valide ? 'Valide' : 'Invalide'}
                        </Badge>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          className="h-8 gap-1"
                          onClick={() => handleOpenConsentement(c.id)}
                          aria-label={`Ouvrir le consentement signé ${c.type}`}
                        >
                          <ExternalLink className="w-3.5 h-3.5" /> Ouvrir
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
                  Comparer Avant/Après
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
                        Photo Après
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="bottom">
                      <p>Enregistrer une photo « Après » pour le patient</p>
                    </TooltipContent>
                  </Tooltip>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button size="sm" onClick={() => setUploadDialogOpen(true)}>
                        <Plus className="w-4 h-4 mr-1" /> Ajouter une photo
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="bottom">
                      <p>Ajouter une photo Avant, Après, Progression, etc.</p>
                    </TooltipContent>
                  </Tooltip>
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                La gestion des photos et les annotations au crayon sont réservées aux médecins.
              </p>
            )}

            {photos.length === 0 ? (
              <Card><CardContent className="py-8 text-center text-muted-foreground">Aucune photo trouvée</CardContent></Card>
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
                                <p>Simuler un résultat IA</p>
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
                                <p>Ajouter une photo « Après » pour cette zone</p>
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
                                <AlertDialogTitle>Supprimer cette photo ?</AlertDialogTitle>
                                <AlertDialogDescription>
                                  La photo sera archivée (suppression réversible par un administrateur), pas effacée définitivement.
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>Annuler</AlertDialogCancel>
                                <AlertDialogAction onClick={() => handleDeletePhoto(p.id)}>Supprimer</AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        </div>
                      </div>
                      <p className="text-xs text-muted-foreground">{new Date(p.date).toLocaleDateString('fr-TN')}</p>
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
            Comparaison Avant / Après
          </DialogTitle>
          <DialogDescription>
            Visualisez côte-à-côte les photos avant et après traitement du patient.
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex justify-center py-16">
            <Spinner className="h-8 w-8" />
          </div>
        ) : !data ? (
          <div className="text-center py-8 text-muted-foreground">
            Aucune donnée de comparaison disponible.
          </div>
        ) : (
          <div className="space-y-4">
            {/* Sélecteur de zone */}
            <div className="flex items-center gap-2">
              <Label className="text-sm whitespace-nowrap">Filtrer par zone :</Label>
              <Input
                value={zoneFilter}
                onChange={(e) => onZoneChange(e.target.value)}
                placeholder="Laisser vide pour toutes les zones"
                className="flex-1"
              />
              <Button variant="outline" size="sm" onClick={onReload}>
                Filtrer
              </Button>
            </div>

            {/* Sélecteurs de photos */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-sm font-medium text-center block">Avant</Label>
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
                        {data.avant[leftIndex] ? new Date(data.avant[leftIndex].date).toLocaleDateString('fr-TN') : ''}
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
                          alt="Avant"
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                          {data.avant[leftIndex] ? 'Chargement...' : 'Pas de photo'}
                        </div>
                      )}
                    </div>
                  </>
                ) : (
                  <div className="aspect-square bg-muted rounded-md flex items-center justify-center text-muted-foreground text-sm">
                    Aucune photo avant
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <Label className="text-sm font-medium text-center block">Après</Label>
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
                        {data.apres[rightIndex] ? new Date(data.apres[rightIndex].date).toLocaleDateString('fr-TN') : ''}
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
                          alt="Après"
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                          {data.apres[rightIndex] ? 'Chargement...' : 'Pas de photo'}
                        </div>
                      )}
                    </div>
                  </>
                ) : (
                  <div className="aspect-square bg-muted rounded-md flex items-center justify-center text-muted-foreground text-sm">
                    Aucune photo après
                  </div>
                )}
              </div>
            </div>

            {/* Résumé */}
            <div className="text-center text-xs text-muted-foreground">
              {data.avant.length} photo(s) avant · {data.apres.length} photo(s) après
              {zoneFilter && <span className="ml-2">(zone : {zoneFilter})</span>}
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
    if (!file) { toast.error('Sélectionnez une photo'); return; }
    setIsUploading(true);
    try {
      await photosApi.upload(patientId, file, {
        type_photo: 'apres',
        zone: zonePrefilled || undefined,
      });
      toast.success('Photo « Après » ajoutée avec succès');
      onOpenChange(false);
      onUploaded();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Erreur lors de l'envoi de la photo");
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
            Ajouter une photo « Après »
          </DialogTitle>
          <DialogDescription>
            {photoAvant
              ? `Photo « Après » associée à la zone : ${photoAvant.zone || 'Non spécifiée'} (photo Avant du ${new Date(photoAvant.date).toLocaleDateString('fr-TN')})`
              : 'Enregistrez la photo après traitement du patient.'
            }
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="file-after">Fichier photo</Label>
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
            <Label>Zone anatomique</Label>
            <div className="text-sm text-muted-foreground">
              {zonePrefilled || <span className="italic">Non spécifiée</span>}
            </div>
          </div>
          <div>
            <Label>Type</Label>
            <div className="text-sm font-medium text-green-700">Après</div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button>
            <Button type="submit" disabled={isUploading}>
              {isUploading ? <Spinner className="h-4 w-4 mr-2" /> : <Plus className="w-4 h-4 mr-2" />}
              Enregistrer la photo Après
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
      toast.success('Simulation générée avec succès');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur lors de la génération');
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
      toast.success('Consentement IA signé');
      setShowConsentSign(false);
      onConsentSigned();
    } catch (err: any) {
      toast.error("Erreur lors de la signature");
    }
  };

  if (!photo) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-primary" />
            Simulation de résultat par IA
          </DialogTitle>
          <DialogDescription>
            Générez une simulation visuelle du résultat attendu pour la zone : {photo.zone || 'Non spécifiée'}
          </DialogDescription>
        </DialogHeader>

        {showConsentSign ? (
          <div className="space-y-4 py-4">
            <div className="bg-yellow-50 border border-yellow-200 p-4 rounded-md text-sm text-yellow-800">
              <strong>Consentement requis :</strong> Le patient doit accepter que sa photo soit traitée par un algorithme d'IA
              avant toute simulation. Cette simulation n'est pas contractuelle.
            </div>
            <Label>Signature du patient</Label>
            <SignaturePad onSave={handleSignConsent} onCancel={() => setShowConsentSign(false)} />
          </div>
        ) : showCrayonPad ? (
          <SimulationCrayonPad
            imageUrl={photoUrl}
            onSave={(mask) => {
              setMasqueBase64(mask);
              setShowCrayonPad(false);
              toast.success('Marquage enregistré');
            }}
            onCancel={() => setShowCrayonPad(false)}
          />
        ) : resultUrl ? (
          <div className="space-y-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-center block">Original (Avant)</Label>
                <div className="aspect-square bg-muted rounded-md overflow-hidden">
                  <img src={photoUrl} alt="Original" className="w-full h-full object-cover" />
                </div>
              </div>
              <div className="space-y-2">
                <Label className="text-center block">Simulation IA</Label>
                <div className="aspect-square bg-muted rounded-md overflow-hidden relative">
                  <img src={resultUrl} alt="Simulation" className="w-full h-full object-cover" />
                  <div className="absolute bottom-2 right-2 bg-black/50 text-white text-[10px] px-2 py-0.5 rounded">
                    Simulation non contractuelle
                  </div>
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button onClick={() => onOpenChange(false)}>Fermer</Button>
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
                  <Label htmlFor="zone">Zone anatomique</Label>
                  <Input id="zone" value={zone} onChange={(e) => setZone(e.target.value)} placeholder="Ex: Lèvres, Sillon nasogénien..." />
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <Label htmlFor="intensite">Intensité du résultat</Label>
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
                    <span>Naturel</span>
                    <span>Prononcé</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Marquage précis (Crayon)</Label>
                  <Button
                    variant="outline"
                    className={`w-full ${masqueBase64 ? 'border-green-500 bg-green-50 text-green-700' : ''}`}
                    onClick={() => setShowCrayonPad(true)}
                  >
                    <Pencil className="w-4 h-4 mr-2" />
                    {masqueBase64 ? 'Modifier le marquage' : 'Dessiner sur la photo'}
                  </Button>
                  {masqueBase64 && <p className="text-[10px] text-green-600 text-center">✓ Masque de guidage actif</p>}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="instructions">Moteur d'instructions (Engine)</Label>
                  <Textarea
                    id="instructions"
                    value={instructions}
                    onChange={(e) => setInstructions(e.target.value)}
                    placeholder="Instructions pour l'IA (ex: Augmenter le volume en gardant un aspect naturel...)"
                    className="h-20 text-xs"
                  />
                </div>

                <div className="pt-2">
                  <Button className="w-full" onClick={handleGenerate} disabled={isGenerating}>
                    {isGenerating ? <Spinner className="h-4 w-4 mr-2" /> : <Sparkles className="w-4 h-4 mr-2" />}
                    {hasSimConsent ? 'Générer la simulation' : 'Signer le consentement et générer'}
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
      toast.info("Enregistrement en cours...");
    } catch (err) {
      toast.error("Accès micro refusé ou non supporté");
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
      toast.success("Transcription réussie");
    } catch (err) {
      toast.error("Échec de la transcription");
    } finally {
      setIsRecordingLoading(false);
    }
  };

  const handleScribeProcess = async () => {
    if (!observations || observations.length < 10) {
      toast.error("Observations trop courtes pour l'IA");
      return;
    }
    setIsProcessingSoap(true);
    try {
      const res = await scribeIaApi.process(patientId, observations);
      const soap = res.data.notes_structurees_soap;
      const formatted = `[SUBJECTIVE]\n${soap.subjective}\n\n[OBJECTIVE]\n${soap.objective}\n\n[ASSESSMENT]\n${soap.assessment}\n\n[PLAN]\n${soap.plan}`;
      setObservations(formatted);
      toast.success("Note SOAP générée par IA");
    } catch (err) {
      toast.error("Erreur Scribe IA");
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
      toast.error('Sélectionnez au moins un acte ou saisissez une ligne manuelle');
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
      toast.success('Dossier créé et transmis à la secrétaire');
      onOpenChange(false);
      onCreated();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur lors de la création du dossier');
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
            Validation des Actes & Scribe IA
          </DialogTitle>
          <DialogDescription>Sélectionnez les actes et utilisez la dictée vocale pour vos notes.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <div>
                <Label>Actes du catalogue</Label>
                <select
                  className="w-full h-9 px-3 border rounded-md text-sm mb-2"
                  onChange={(e) => addActe(e.target.value)}
                  value=""
                >
                  <option value="">— Ajouter un acte —</option>
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
                      title={showActePrices ? 'Masquer les prix' : 'Afficher les prix'}
                    >
                      {showActePrices ? <EyeOff className="mr-1.5 h-3.5 w-3.5" /> : <Eye className="mr-1.5 h-3.5 w-3.5" />}
                      {showActePrices ? 'Masquer les prix' : 'Afficher les prix'}
                    </Button>
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <Label>Saisie manuelle</Label>
                  <Button type="button" variant="outline" size="xs" onClick={addManualLigne} className="h-7 text-[10px]">
                    <Plus className="w-3 h-3 mr-1" /> Ligne
                  </Button>
                </div>
                {manualLignes.map((l, i) => (
                  <div key={i} className="flex gap-2">
                    <Input
                      placeholder="Acte"
                      value={l.nom}
                      onChange={(e) => setManualLignes(manualLignes.map((item, idx) => idx === i ? {...item, nom: e.target.value} : item))}
                      className="flex-1 h-8 text-sm"
                    />
                    <Input
                      type="number"
                      placeholder="Prix"
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
                <Label htmlFor="observations">Observations Médicales</Label>
                <div className="flex gap-1">
                  {isRecording ? (
                    <Button type="button" size="xs" variant="destructive" onClick={stopRecording} className="h-7 animate-pulse">
                      <Square className="w-3 h-3 mr-1" /> Stop
                    </Button>
                  ) : (
                    <Button type="button" size="xs" variant="outline" onClick={startRecording} className="h-7 text-red-600 border-red-200">
                      <Mic className="w-3 h-3 mr-1" /> Dictée
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
                    SOAP
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
                  placeholder="Dictez ou saisissez vos notes ici..."
                />
                {isTranscribing && (
                  <div className="absolute inset-0 bg-white/60 flex items-center justify-center">
                    <div className="flex items-center gap-2 text-xs font-medium">
                      <Loader2 className="w-4 h-4 animate-spin" /> Transcription...
                    </div>
                  </div>
                )}
              </div>
              <div className="grid gap-2">
                <Label htmlFor="effets" className="text-xs">Effets secondaires / Notes post-acte</Label>
                <Textarea id="effets" value={effetsSecondaires} onChange={(e) => setEffetsSecondaires(e.target.value)} rows={2} className="text-sm" />
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button>
            <Button type="submit" disabled={isSaving} className="bg-purple-600 hover:bg-purple-700">
              {isSaving ? <Spinner className="h-4 w-4" /> : 'Valider pour Facturation'}
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
      toast.success('Consentement signé');
      onOpenChange(false);
      onSigned();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur lors de la signature');
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Signer un consentement</DialogTitle>
          <DialogDescription>Le patient doit signer directement ci-dessous.</DialogDescription>
        </DialogHeader>
        {!signing ? (
          <div className="space-y-4">
            <div>
              <Label htmlFor="acte-consent">Acte concerné</Label>
              <select id="acte-consent" value={acteId} onChange={(e) => setActeId(e.target.value)} className="w-full h-9 px-3 border rounded-md text-sm">
                <option value="">— Non spécifié —</option>
                {actes.map((a) => <option key={a.id} value={a.id}>{a.nom}</option>)}
              </select>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button>
              <Button type="button" onClick={() => setSigning(true)}>Continuer vers la signature</Button>
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
  const [file, setFile] = useState<File | null>(null);
  const [typePhoto, setTypePhoto] = useState('avant');
  const [zone, setZone] = useState('');
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => { if (open) { setFile(null); setTypePhoto('avant'); setZone(''); } }, [open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) { toast.error('Sélectionnez une photo'); return; }
    setIsUploading(true);
    try {
      await photosApi.upload(patientId, file, { type_photo: typePhoto, zone: zone || undefined });
      toast.success('Photo ajoutée');
      onOpenChange(false);
      onUploaded();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Erreur lors de l'envoi de la photo");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Ajouter une photo médicale</DialogTitle>
          <DialogDescription>JPEG/PNG/WEBP, 20 Mo max. EXIF retiré et filigrane appliqués automatiquement.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="file">Fichier</Label>
            <input
              id="file"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="w-full text-sm"
            />
          </div>
          <div>
            <Label htmlFor="type_photo">Type</Label>
            <select id="type_photo" value={typePhoto} onChange={(e) => setTypePhoto(e.target.value)} className="w-full h-9 px-3 border rounded-md text-sm">
              <option value="avant">Avant</option>
              <option value="apres">Après</option>
              <option value="progression">Progression</option>
              <option value="complication">Complication</option>
              <option value="autre">Autre</option>
            </select>
          </div>
          <div>
            <Label htmlFor="zone">Zone anatomique</Label>
            <input id="zone" value={zone} onChange={(e) => setZone(e.target.value)} placeholder="ex : visage, lèvres" className="w-full h-9 px-3 border rounded-md text-sm" />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button>
            <Button type="submit" disabled={isUploading}>{isUploading ? <Spinner className="h-4 w-4" /> : 'Envoyer'}</Button>
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
  allergie: { principal: 'Substance / produit concerné', champs: ['substance', 'reaction'] },
  traitement: { principal: 'Médicament / traitement', champs: ['medicament', 'posologie'] },
  contre_indication: { principal: 'Contre-indication', champs: ['motif'] },
  antecedent_medical: { principal: 'Description', champs: ['description'] },
  antecedent_chirurgical: { principal: 'Intervention', champs: ['intervention', 'date_intervention'] },
  antecedent_anesthesique: { principal: 'Description', champs: ['description'] },
  antecedent_familial: { principal: 'Description', champs: ['description'] },
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
      toast.success('Fait médical enregistré');
      onOpenChange(false);
      onCreated();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur lors de l\'enregistrement');
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
            Nouveau fait médical structuré
          </DialogTitle>
          <DialogDescription>
            Donnée chiffrée, journalisée dans l'audit médical et réservée au rôle médecin.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="type_fait">Type de fait médical</Label>
            <select
              id="type_fait"
              value={typeFait}
              onChange={(e) => setTypeFait(e.target.value)}
              className="w-full h-9 px-3 border rounded-md text-sm"
            >
              {Object.entries(FACT_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="fait_principal">{config.principal}</Label>
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
                {secondaryKey === 'reaction' ? 'Réaction observée' : secondaryKey === 'posologie' ? 'Posologie' : secondaryKey === 'date_intervention' ? 'Date de l\'intervention' : 'Précision'}
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
            <Label htmlFor="verification_status">Statut de vérification</Label>
            <select
              id="verification_status"
              value={verificationStatus}
              onChange={(e) => setVerificationStatus(e.target.value)}
              className="w-full h-9 px-3 border rounded-md text-sm"
            >
              <option value="VERIFIED">Vérifié</option>
              <option value="PENDING_VERIFICATION">À vérifier</option>
              <option value="HISTORICAL_UNSTRUCTURED">Historique non structuré</option>
            </select>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button>
            <Button type="submit" disabled={isSaving}>
              {isSaving ? <Spinner className="h-4 w-4" /> : 'Enregistrer'}
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
  const [medicament, setMedicament] = useState('');
  const [dosage, setDosage] = useState('');
  const [frequence, setFrequence] = useState('');
  const [duree, setDuree] = useState('');
  const [instructions, setInstructions] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setMedicament('');
      setDosage('');
      setFrequence('');
      setDuree('');
      setInstructions('');
    }
  }, [open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!medicament.trim()) return;
    setIsSaving(true);
    try {
      const details: Record<string, unknown> = { medicament: medicament.trim() };
      if (dosage.trim()) details.dosage = dosage.trim();
      if (frequence.trim()) details.frequence = frequence.trim();
      if (duree.trim()) details.duree = duree.trim();
      if (instructions.trim()) details.instructions = instructions.trim();
      await prescriptionsApi.create(patientId, { details, statut: 'ACTIVE' });
      toast.success('Prescription enregistrée');
      onOpenChange(false);
      onCreated();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur lors de l\'enregistrement');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Pill className="w-5 h-5" />
            Nouvelle prescription médicale
          </DialogTitle>
          <DialogDescription>
            Prescription chiffrée, journalisée dans l'audit médical et réservée au rôle médecin.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="presc_medicament">Médicament / produit *</Label>
            <Input
              id="presc_medicament"
              value={medicament}
              onChange={(e) => setMedicament(e.target.value)}
              required
              className="w-full"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="presc_dosage">Dosage</Label>
              <Input id="presc_dosage" value={dosage} onChange={(e) => setDosage(e.target.value)} placeholder="ex : 10 mg" className="w-full" />
            </div>
            <div>
              <Label htmlFor="presc_frequence">Fréquence</Label>
              <Input id="presc_frequence" value={frequence} onChange={(e) => setFrequence(e.target.value)} placeholder="ex : 1/jour" className="w-full" />
            </div>
          </div>
          <div>
            <Label htmlFor="presc_duree">Durée</Label>
            <Input id="presc_duree" value={duree} onChange={(e) => setDuree(e.target.value)} placeholder="ex : 7 jours" className="w-full" />
          </div>
          <div>
            <Label htmlFor="presc_instructions">Instructions</Label>
            <Textarea id="presc_instructions" value={instructions} onChange={(e) => setInstructions(e.target.value)} rows={3} className="w-full" />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button>
            <Button type="submit" disabled={isSaving}>
              {isSaving ? <Spinner className="h-4 w-4" /> : 'Enregistrer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
