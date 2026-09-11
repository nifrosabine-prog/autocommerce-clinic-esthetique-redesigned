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
import { FileText, Image as ImageIcon, CheckCircle, Download, Plus, Trash2, User, Phone, ArrowLeft, Sparkles, Camera, SlidersHorizontal, Eye, Zap, Mic, Square, Loader2, Pencil, Mail } from 'lucide-react';
import { toast } from 'sonner';
import { useLocation } from 'wouter';
import { api, dossierMedicalApi, photosApi, scribeIaApi } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import { SignaturePad } from '@/components/patients/SignaturePad';
import { SimulationCrayonPad } from '@/components/patients/SimulationCrayonPad';

interface PatientHeader {
  id: number;
  nom: string;
  prenom: string;
  telephone: string;
  date_naissance?: string;
  allergies?: string;
  contre_indications?: string;
  antecedents_medicaux?: string;
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
  statut_clinique?: 'brouillon' | 'cloture';
  photos: { id: number; type: string; zone?: string; url: string }[];
}

interface ConsentementItem {
  id: number;
  type: string;
  acte_id?: number;
  signe_le: string;
  methode: string;
  est_valide: boolean;
  est_contractuel?: boolean;
  actes?: Array<{ id: number; nom: string; prix: number; devise: string }>;
  praticien?: string | null;
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

interface AppointmentContext {
  id: number;
  acte_id?: number | null;
  acte_nom: string;
  date_heure: string;
  statut: string;
}

/** Interface pour la réponse de comparaison avant/après */
interface ComparaisonAvantApres {
  avant: { id: number; url: string; date: string }[];
  apres: { id: number; url: string; date: string }[];
}

export default function MedicalFile({ patientId }: { patientId: number }) {
  const { user } = useAuth();
  const [, setLocation] = useLocation();
  const canSeeAntecedents = user?.role !== 'estheticienne';
  // Les opérations cliniques et les signatures de consentement sont réservées
  // aux praticiens ; la directrice conserve un accès de consultation et d’export.
  const canManageClinicalEntries = ['medecin', 'estheticienne'].includes(user?.role ?? '');
  const canManagePhotos = ['medecin', 'estheticienne'].includes(user?.role ?? '');

  const [patient, setPatient] = useState<PatientHeader | null>(null);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [consentements, setConsentements] = useState<ConsentementItem[]>([]);
  const [photos, setPhotos] = useState<PhotoItem[]>([]);
  const [photoUrls, setPhotoUrls] = useState<Record<number, string>>({});
  const [actes, setActes] = useState<Acte[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('dossiers');

  const [dossierDialogOpen, setDossierDialogOpen] = useState(false);
  const [consentDialogOpen, setConsentDialogOpen] = useState(false);
  const [consentActeId, setConsentActeId] = useState<number | undefined>();
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

  const loadAll = useCallback(async () => {
    if (!patientId || Number.isNaN(patientId)) return;
    setIsLoading(true);
    try {
      const [patientRes, timelineRes, consentRes, photosRes, actesRes] = await Promise.allSettled([
        api.get(`/patients/${patientId}`),
        dossierMedicalApi.getTimeline(patientId),
        dossierMedicalApi.listConsentements(patientId),
        dossierMedicalApi.listPhotos(patientId),
        dossierMedicalApi.getActesCliniques(),
      ]);

      if (patientRes.status === 'fulfilled') setPatient(patientRes.value.data);
      else toast.error("Impossible de charger la fiche patient");

      if (timelineRes.status === 'fulfilled') setTimeline(timelineRes.value.data);
      if (consentRes.status === 'fulfilled') setConsentements(consentRes.value.data);
      if (photosRes.status === 'fulfilled') setPhotos(photosRes.value.data);
      if (actesRes.status === 'fulfilled') setActes(actesRes.value.data);
    } finally {
      setIsLoading(false);
    }
  }, [patientId]);

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

  const handleDeletePhoto = async (photoId: number) => {
    try {
      await photosApi.delete(patientId, photoId);
      toast.success('Photo supprimée');
      loadAll();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur lors de la suppression');
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
            <Button variant="ghost" size="sm" className="mb-2 -ml-2" onClick={() => setLocation('/patients')}>
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
          <Button onClick={handleExportPdf} disabled={isExporting}>
            {isExporting ? <Spinner className="h-4 w-4 mr-2" /> : <Download className="w-4 h-4 mr-2" />}
            Exporter PDF
          </Button>
        </div>

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

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="h-auto w-full max-w-full justify-start gap-1 overflow-x-auto rounded-xl border border-slate-200 bg-slate-100 p-1.5">
            <TabsTrigger value="dossiers" className="shrink-0 border border-transparent bg-transparent px-3 py-2 text-slate-600 hover:bg-white hover:text-slate-950 data-[state=active]:border-teal-200 data-[state=active]:bg-white data-[state=active]:text-teal-800 data-[state=active]:shadow-sm"><FileText className="w-4 h-4 mr-1" /> Dossiers ({timeline.length})</TabsTrigger>
            <TabsTrigger value="consentements" className="shrink-0 border border-transparent bg-transparent px-3 py-2 text-slate-600 hover:bg-white hover:text-slate-950 data-[state=active]:border-teal-200 data-[state=active]:bg-white data-[state=active]:text-teal-800 data-[state=active]:shadow-sm"><CheckCircle className="w-4 h-4 mr-1" /> Consentements ({consentements.length})</TabsTrigger>
            <TabsTrigger value="photos" className="shrink-0 border border-transparent bg-transparent px-3 py-2 text-slate-600 hover:bg-white hover:text-slate-950 data-[state=active]:border-teal-200 data-[state=active]:bg-white data-[state=active]:text-teal-800 data-[state=active]:shadow-sm"><ImageIcon className="w-4 h-4 mr-1" /> Photos ({photos.length})</TabsTrigger>
          </TabsList>

          {/* ── Dossiers ── */}
          <TabsContent value="dossiers" className="space-y-4">
            <div className="flex justify-end">
              {canManageClinicalEntries ? (
                <Button size="sm" onClick={() => setDossierDialogOpen(true)}>
                  <Plus className="w-4 h-4 mr-1" /> Nouveau dossier
                </Button>
              ) : (
                <p className="text-sm text-muted-foreground">La création de dossiers est réservée aux praticiens.</p>
              )}
            </div>
            {timeline.length === 0 ? (
              <Card><CardContent className="py-8 text-center text-muted-foreground">Aucun dossier trouvé</CardContent></Card>
            ) : (
              timeline.map((item) => (
                <Card key={item.dossier_id} className={item.statut_clinique === 'brouillon' ? 'border-amber-200 bg-amber-50/30' : 'border-slate-200'}>
                  <CardHeader>
                    <CardTitle className="text-base flex justify-between items-center">
                      <span>{item.acte} — {new Date(item.date).toLocaleDateString('fr-TN')}</span>
                      <div className="flex items-center gap-2">
                        {item.statut_clinique === 'brouillon' && (
                          <Badge variant="outline" className="h-8 border-amber-200 bg-amber-50 text-amber-800">Brouillon clinique</Badge>
                        )}
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
                    {item.statut_clinique === 'brouillon' && canManageClinicalEntries && (
                      <div className="flex items-center justify-between gap-3 border-t border-amber-200 pt-3">
                        <p className="text-xs leading-5 text-amber-800">La clôture vérifie le consentement éclairé spécifique à l’acte.</p>
                        <Button size="sm" className="shrink-0 bg-teal-700 text-white hover:bg-teal-800" onClick={async () => {
                          try {
                            await dossierMedicalApi.close(patientId, item.dossier_id);
                            toast.success('Dossier clôturé.');
                            void loadAll();
                          } catch (error: any) {
                            toast.error(error.response?.data?.detail || 'La clôture du dossier est impossible.');
                          }
                        }}>Clôturer</Button>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))
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
                <p className="text-sm text-muted-foreground">La signature des consentements est réservée aux praticiens.</p>
              )}
            </div>
            {consentements.length === 0 ? (
              <Card><CardContent className="py-8 text-center text-muted-foreground">Aucun consentement trouvé</CardContent></Card>
            ) : (
              <Card>
                <CardContent className="py-4 space-y-3">
                  {consentements.map((c) => (
                    <div key={c.id} className="flex items-center justify-between gap-3 border-b last:border-0 pb-2 last:pb-0">
                      <div>
                        <p className="font-medium">{c.est_contractuel ? 'Contrat de consentement éclairé' : c.type}</p>
                        <p className="text-sm text-muted-foreground">
                          Signé le {new Date(c.signe_le).toLocaleDateString('fr-TN')} ({c.methode})
                        </p>
                        {c.actes?.length ? <p className="mt-1 text-xs text-slate-600">Actes : {c.actes.map((acte) => `${acte.nom} (${acte.prix.toFixed(3)} ${acte.devise})`).join(' · ')}</p> : null}
                        {c.praticien ? <p className="text-xs text-slate-500">Praticien attestant : {c.praticien}</p> : null}
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <Badge variant={c.est_valide ? 'default' : 'destructive'}>{c.est_valide ? 'Valide' : 'Invalide'}</Badge>
                        <Button type="button" variant="outline" size="sm" onClick={() => void dossierMedicalApi.downloadConsentementPdf(patientId, c.id).catch((error: any) => toast.error(error.response?.data?.detail || 'PDF de consentement indisponible.'))}>
                          <Download className="mr-1 h-4 w-4" /> Contrat PDF
                        </Button>
                        {c.est_contractuel ? (
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button type="button" variant="outline" size="sm">
                                <Mail className="mr-1 h-4 w-4" /> Envoyer par e-mail
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>Envoyer le contrat signé au patient ?</AlertDialogTitle>
                                <AlertDialogDescription>Le PDF signé sera transmis à l’adresse e-mail enregistrée dans le dossier patient. Vérifiez cette adresse avant de confirmer ; l’envoi sera journalisé.</AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>Annuler</AlertDialogCancel>
                                <AlertDialogAction onClick={() => void dossierMedicalApi.emailConsentementPdf(patientId, c.id).then((response) => toast.success(`Contrat envoyé à ${response.data.recipient}.`)).catch((error: any) => toast.error(error.response?.data?.detail || 'Envoi du contrat impossible.'))}>Confirmer l’envoi</AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* ── Photos ── */}
          <TabsContent value="photos" className="space-y-4">
            {/* Les photos médicales chiffrées et les simulations associées sont réservées aux praticiens. */}
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
                La gestion des photos et les annotations au crayon sont réservées aux praticiens.
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
        onCreated={loadAll}
        onRequestConsent={(acteId) => {
          setConsentActeId(acteId);
          setDossierDialogOpen(false);
          setConsentDialogOpen(true);
        }}
      />
      <SignConsentDialog
        open={consentDialogOpen}
        onOpenChange={setConsentDialogOpen}
        patientId={patientId}
        actes={actes}
        initialActeId={consentActeId}
        onSigned={loadAll}
      />
      <UploadPhotoDialog
        open={uploadDialogOpen}
        onOpenChange={setUploadDialogOpen}
        patientId={patientId}
        onUploaded={loadAll}
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

function NewDossierDialog({ open, onOpenChange, patientId, actes, onCreated, onRequestConsent }: {
  open: boolean; onOpenChange: (v: boolean) => void; patientId: number; actes: Acte[];
  onCreated: () => void; onRequestConsent: (acteId?: number) => void;
}) {
  const [selectedActes, setSelectedActes] = useState<{id: number, nom: string, prix: number}[]>([]);
  const [manualLignes, setManualLignes] = useState<{nom: string, prix: number}[]>([]);
  const [observations, setObservations] = useState('');
  const [effetsSecondaires, setEffetsSecondaires] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [acteQuery, setActeQuery] = useState('');
  const [appointments, setAppointments] = useState<AppointmentContext[]>([]);
  const [selectedRdvId, setSelectedRdvId] = useState<number | undefined>();
  const [followupRequired, setFollowupRequired] = useState(false);
  const [followupDate, setFollowupDate] = useState('');

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
      setActeQuery('');
      setSelectedRdvId(undefined);
      setFollowupRequired(false);
      setFollowupDate('');
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    void dossierMedicalApi.getAppointmentContext(patientId).then((response) => {
      if (!cancelled) setAppointments(response.data);
    }).catch(() => {
      if (!cancelled) setAppointments([]);
    });
    return () => { cancelled = true; };
  }, [open, patientId]);

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
      setActeQuery('');
    }
  };

  const addManualLigne = () => {
    setManualLignes([...manualLignes, { nom: '', prix: 0 }]);
  };

  const handleSubmit = async (statutClinique: 'brouillon' | 'cloture') => {
    if (selectedActes.length === 0 && manualLignes.filter(l => l.nom).length === 0 && !observations.trim()) {
      toast.error('Ajoutez au moins un acte ou une observation avant d’enregistrer le dossier.');
      return;
    }
    setIsSaving(true);
    try {
      const allActes = [
        ...selectedActes.map(a => ({ id: a.id, nom: a.nom, prix: a.prix })),
        ...manualLignes.filter(l => l.nom).map(l => ({ nom: l.nom, prix: l.prix }))
      ];

      await dossierMedicalApi.create(patientId, {
        acte_id: selectedActes[0]?.id, // Garder le premier comme acte principal pour la compatibilité
        rdv_id: selectedRdvId,
        date_acte: new Date().toISOString(),
        observations: observations || undefined,
        effets_secondaires: effetsSecondaires || undefined,
        actes_details: allActes,
        suivi_requis: followupRequired,
        date_suivi_recommandee: followupRequired && followupDate ? followupDate : undefined,
        statut_clinique: statutClinique,
      });
      toast.success(statutClinique === 'brouillon' ? 'Brouillon clinique enregistré.' : 'Dossier clôturé et transmis à la secrétaire.');
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
          <DialogTitle className="flex items-center gap-2 text-slate-950">
            <FileText className="w-5 h-5 text-teal-700" /> Saisie clinique
          </DialogTitle>
          <DialogDescription>Enregistrez un brouillon à tout moment. La clôture vérifie le consentement éclairé spécifique à l’acte.</DialogDescription>
        </DialogHeader>
        <form onSubmit={(event) => { event.preventDefault(); void handleSubmit('cloture'); }} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <div className="rounded-xl border border-slate-200 bg-white p-3">
                <div className="mb-2 flex items-center justify-between"><Label>Contexte rendez-vous</Label><span className="text-[11px] text-slate-500">Patient actuel</span></div>
                {appointments.length === 0 ? <p className="text-xs text-slate-500">Aucun rendez-vous récent ou à venir à associer.</p> : (
                  <div className="flex flex-wrap gap-2">
                    {appointments.slice(0, 4).map((appointment) => (
                      <button type="button" key={appointment.id} onClick={() => {
                        setSelectedRdvId(appointment.id);
                        const appointmentAct = actes.find((acte) => acte.id === appointment.acte_id);
                        if (appointmentAct && !selectedActes.some((selected) => selected.id === appointmentAct.id)) {
                          setSelectedActes((current) => [...current, { id: appointmentAct.id, nom: appointmentAct.nom, prix: appointmentAct.prix_base || 0 }]);
                        }
                      }} className={`rounded-lg border px-2.5 py-2 text-left text-xs transition-colors ${selectedRdvId === appointment.id ? 'border-teal-300 bg-teal-50 text-teal-900' : 'border-slate-200 text-slate-600 hover:border-teal-200 hover:bg-teal-50'}`}>
                        <span className="block font-medium">{appointment.acte_nom}</span><span>{new Date(appointment.date_heure).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                <div className="mb-2 flex items-center justify-between gap-3"><Label htmlFor="acte-search">Actes habilités</Label><span className="text-[11px] text-slate-500">Catalogue interne</span></div>
                <Input id="acte-search" value={acteQuery} onChange={(event) => setActeQuery(event.target.value)} placeholder="Rechercher un acte" className="bg-white" />
                <div className="mt-2 max-h-36 space-y-1 overflow-y-auto pr-1">
                  {actes.filter((acte) => acte.nom.toLocaleLowerCase('fr-FR').includes(acteQuery.toLocaleLowerCase('fr-FR')) && !selectedActes.some((selected) => selected.id === acte.id)).slice(0, 8).map((acte) => (
                    <button type="button" key={acte.id} onClick={() => addActe(String(acte.id))} className="flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-sm text-slate-700 transition-colors hover:bg-teal-50 hover:text-teal-900">
                      <span className="font-medium">{acte.nom}</span><span className="text-xs text-slate-500">{Number(acte.prix_base || 0).toFixed(3)} DT</span>
                    </button>
                  ))}
                  {actes.length === 0 && <p className="px-2 py-3 text-xs text-amber-800">Aucun acte n’est habilité pour ce praticien. Configurez ses habilitations dans l’équipe.</p>}
                </div>
                <div className="space-y-2">
                  {selectedActes.map((a, i) => (
                    <div key={i} className="mt-2 flex items-center justify-between rounded-lg border border-teal-100 bg-teal-50 p-2.5">
                      <span className="text-sm font-medium">{a.nom}</span>
                      <Button type="button" variant="ghost" size="sm" onClick={() => setSelectedActes(selectedActes.filter((_, idx) => idx !== i))}>
                        <Trash2 className="w-3 h-3 text-destructive" />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <div>
                    <Label>Saisie manuelle</Label>
                    <button type="button" onClick={() => onRequestConsent(selectedActes[0]?.id)} className="mt-1 block text-left text-[11px] font-medium text-amber-800 underline decoration-amber-400 underline-offset-2">Consentement éclairé requis avant clôture</button>
                  </div>
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
                    className="h-7 bg-violet-100 text-violet-800 hover:bg-violet-200"
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
              <div className="rounded-xl border border-teal-100 bg-teal-50 p-3">
                <label className="flex items-start gap-3 text-sm text-teal-950"><input type="checkbox" checked={followupRequired} onChange={(event) => setFollowupRequired(event.target.checked)} className="mt-0.5 accent-teal-700" /><span><strong>Créer un suivi post-acte</strong><br /><span className="text-xs text-teal-800">Le suivi apparaîtra dans la file opérationnelle à la clôture du dossier.</span></span></label>
                {followupRequired && <div className="mt-3"><Label htmlFor="followup-date" className="text-xs text-teal-900">Échéance du suivi</Label><Input id="followup-date" type="date" value={followupDate} onChange={(event) => setFollowupDate(event.target.value)} min={new Date().toISOString().slice(0, 10)} required={followupRequired} className="mt-1 bg-white" /></div>}
              </div>
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button>
            <Button type="button" variant="outline" disabled={isSaving} onClick={() => void handleSubmit('brouillon')}>
              {isSaving ? <Spinner className="h-4 w-4" /> : 'Enregistrer le brouillon'}
            </Button>
            <Button type="submit" disabled={isSaving} className="bg-teal-700 text-white hover:bg-teal-800">
              {isSaving ? <Spinner className="h-4 w-4" /> : 'Clôturer pour facturation'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────
// ── Dialog Signer Consentement (inchangé) ──

function SignConsentDialog({ open, onOpenChange, patientId, actes, initialActeId, onSigned }: {
  open: boolean; onOpenChange: (v: boolean) => void; patientId: number; actes: Acte[]; initialActeId?: number; onSigned: () => void;
}) {
  const [selectedActeIds, setSelectedActeIds] = useState<number[]>([]);
  const [contractPreview, setContractPreview] = useState('');
  const [signing, setSigning] = useState(false);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [practitionerAttested, setPractitionerAttested] = useState(false);
  const [practitionerSignature, setPractitionerSignature] = useState('');

  useEffect(() => {
    if (open) {
      setSelectedActeIds(initialActeId ? [initialActeId] : []);
      setContractPreview('');
      setSigning(false);
      setPractitionerAttested(false);
      setPractitionerSignature('');
    }
  }, [open, initialActeId]);

  const toggleActe = (acteId: number) => {
    setSelectedActeIds((current) => current.includes(acteId) ? current.filter((id) => id !== acteId) : [...current, acteId]);
    setContractPreview('');
  };

  const handlePreview = async () => {
    if (selectedActeIds.length === 0) {
      toast.error('Sélectionnez au moins un acte avant de générer le contrat.');
      return;
    }
    setIsPreviewLoading(true);
    try {
      const response = await dossierMedicalApi.previewConsentementContractuel(patientId, selectedActeIds);
      setContractPreview(response.data.contenu);
      setSigning(true);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Impossible de préparer le contrat.');
    } finally {
      setIsPreviewLoading(false);
    }
  };

  const handleSave = async (base64: string) => {
    try {
      await dossierMedicalApi.signConsentement(patientId, {
        acte_id: selectedActeIds[0],
        acte_ids: selectedActeIds,
        signature_base64: base64,
        signature_praticien_base64: practitionerSignature,
        methode_signature: 'tactile',
        attestation_praticien: practitionerAttested,
      });
      toast.success('Contrat de consentement signé et archivé.');
      onOpenChange(false);
      onSigned();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Erreur lors de la signature');
    }
  };

  const handlePreviewPdf = async () => {
    if (selectedActeIds.length === 0) {
      toast.error('Sélectionnez au moins un acte avant de télécharger l’aperçu.');
      return;
    }
    try {
      await dossierMedicalApi.downloadConsentementPreviewPdf(patientId, selectedActeIds);
      toast.success('Aperçu PDF non signé téléchargé.');
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Impossible de générer l’aperçu PDF.');
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Contrat de consentement éclairé</DialogTitle>
          <DialogDescription>Le contrat est prérempli avec le patient, le praticien, les actes et les tarifs avant signature.</DialogDescription>
        </DialogHeader>
        {!signing ? (
          <div className="space-y-4">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
              <Label className="text-sm font-semibold text-slate-900">Actes inclus dans le contrat</Label>
              <p className="mt-1 text-xs text-slate-600">Les tarifs affichés seront figés dans le document signé.</p>
              <div className="mt-3 space-y-2">
                {actes.map((acte) => <label key={acte.id} className="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm hover:border-teal-200">
                  <span className="flex items-center gap-2"><input type="checkbox" checked={selectedActeIds.includes(acte.id)} onChange={() => toggleActe(acte.id)} className="accent-teal-700" />{acte.nom}</span>
                  <strong className="text-teal-800">{Number(acte.prix_base || 0).toFixed(3)} DT</strong>
                </label>)}
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button>
              <Button type="button" variant="outline" onClick={() => void handlePreviewPdf()} disabled={selectedActeIds.length === 0}><Download className="mr-1 h-4 w-4" /> Aperçu PDF</Button>
              <Button type="button" onClick={() => void handlePreview()} disabled={isPreviewLoading}>{isPreviewLoading ? <Spinner className="h-4 w-4" /> : 'Prévisualiser le contrat'}</Button>
            </DialogFooter>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="max-h-72 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs leading-5 text-slate-800"><pre className="whitespace-pre-wrap font-sans">{contractPreview}</pre></div>
            <label className="flex items-start gap-3 rounded-xl border border-teal-200 bg-teal-50 p-3 text-sm text-teal-950">
              <input type="checkbox" checked={practitionerAttested} onChange={(event) => setPractitionerAttested(event.target.checked)} className="mt-0.5 accent-teal-700" />
              <span><strong>Attestation du praticien</strong><br /><span className="text-xs text-teal-800">Je confirme avoir relu le contrat, présenté les informations cliniques nécessaires et validé les actes et tarifs ci-dessus.</span></span>
            </label>
            {!practitionerAttested ? (
              <DialogFooter><Button type="button" variant="outline" onClick={() => setSigning(false)}>Modifier les actes</Button><Button type="button" disabled>Attestation du praticien requise</Button></DialogFooter>
            ) : !practitionerSignature ? (
              <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-3">
                <p className="text-sm font-semibold text-slate-900">1. Signature du praticien</p>
                <p className="text-xs text-slate-600">Le praticien signe d’abord le contrat qu’il vient d’attester.</p>
                <SignaturePad onSave={(base64) => setPractitionerSignature(base64)} onCancel={() => setSigning(false)} />
              </div>
            ) : (
              <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-3">
                <p className="text-sm font-semibold text-slate-900">2. Signature du patient</p>
                <p className="text-xs text-slate-600">La signature du praticien est enregistrée. Le patient relit le contrat puis signe ci-dessous.</p>
                <SignaturePad onSave={handleSave} onCancel={() => setPractitionerSignature('')} />
              </div>
            )}
          </div>
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
