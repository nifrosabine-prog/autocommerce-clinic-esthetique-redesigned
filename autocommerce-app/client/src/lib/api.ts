import axios, { AxiosInstance, AxiosError } from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || '/api/private';
const PUBLIC_API_BASE = import.meta.env.VITE_PUBLIC_API_URL || '/api/public';
const API_ORIGIN = API_BASE.replace(/\/api\/(?:v1|private)\/?$/, '');

export const resolveApiUrl = (url?: string | null) => {
  if (!url) return undefined;
  if (/^https?:\/\//i.test(url)) return url;
  return `${API_ORIGIN}${url.startsWith('/') ? '' : '/'}${url}`;
};

export const normalizeBrandingResponse = (branding: BrandingResponse): BrandingResponse => ({
  ...branding,
  logo_url: resolveApiUrl(branding.logo_url),
  contenu_landing: branding.contenu_landing ? { ...branding.contenu_landing, photo_hero_url: resolveApiUrl(branding.contenu_landing.photo_hero_url) } : branding.contenu_landing,
});

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserOut {
  id: number;
  email: string;
  nom: string;
  prenom: string;
  role: string;
  telephone?: string;
  specialite?: string;
}

export interface BrandingResponse {
  nom_clinique: string;
  couleur_primaire: string;
  couleur_secondaire: string;
  logo_url?: string;
  contenu_landing?: {
    titre?: string;
    sous_titre?: string;
    services_mis_en_avant?: string[];
    adresse?: string;
    ville?: string;
    telephone?: string;
    whatsapp?: string;
    email?: string;
    instagram?: string;
    facebook?: string;
    tiktok?: string;
    photo_hero_url?: string;
    description_longue?: string;
    horaires?: string;
  };
}

export interface PublicPraticien {
  id: number;
  nom: string;
  prenom: string;
  nom_complet: string;
  specialite?: string | null;
  agenda_color?: string | null;
}

export interface PublicActe {
  id: number;
  nom: string;
  categorie: string;
  duree_minutes: number;
  description?: string | null;
  prix_base?: number | null;
}

export interface PublicDisponibilite {
  heure: string;
  datetime: string;
}

export interface PublicDisponibilitesResponse {
  praticien_id: number;
  date: string;
  duree_minutes: number;
  creneaux: PublicDisponibilite[];
}

export interface BookingRequest {
  id: number;
  clinic_id: number;
  nom: string;
  prenom: string;
  telephone: string;
  email?: string | null;
  praticien_id?: number | null;
  praticien_nom?: string | null;
  acte_nom?: string | null;
  acte_id: number;
  date_heure: string;
  statut: 'pending' | 'accepted' | 'rejected' | string;
  patient_id?: number | null;
  rendez_vous_id?: number | null;
  review_notes?: string | null;
  created_at: string;
}

export interface PublicChatResponse {
  reponse: string;
  statut: string;
  escalade: boolean;
  langue?: 'fr' | 'en' | 'ar' | string;
  actions?: { type: string; label: string; href: string }[];
}

export interface PublicContent {
  branding: BrandingResponse;
  expertises: Record<string, { id: number; nom: string; description?: string; prix_base: number }[]>;
  currency: { currency_code: string; currency_symbol: string };
  marketing_summary: string;
  all_actes: { id: number; nom: string; categorie: string; duree_minutes: number }[];
}

// Le refresh token est exclusivement dans un cookie HttpOnly défini par l’API.
// Aucun token d’authentification n’est persisté dans le stockage navigateur.
let accessToken: string | null = null;
let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

const subscribeTokenRefresh = (callback: (token: string) => void) => {
  refreshSubscribers.push(callback);
};

const onTokenRefreshed = (token: string | null) => {
  if (token) {
    refreshSubscribers.forEach(callback => callback(token));
    refreshSubscribers = [];
  }
};

export const createApiClient = (): AxiosInstance => {
  const client = axios.create({
    baseURL: API_BASE,
    timeout: 15000,
    withCredentials: true,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  // Request interceptor: add access token
  client.interceptors.request.use(
    (config) => {
      if (accessToken) {
        config.headers.Authorization = `Bearer ${accessToken}`;
      }
      return config;
    },
    (error) => Promise.reject(error)
  );

  // Response interceptor: handle 401 and refresh token
  client.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const originalRequest = error.config as any;

      const requestUrl = String(originalRequest?.url || '');
      const isAuthEndpoint = requestUrl.includes('/auth/login') || requestUrl.includes('/auth/refresh') || requestUrl.includes('/auth/mfa/verify');
      if (error.response?.status === 401 && !originalRequest._retry && !isAuthEndpoint) {
        if (isRefreshing) {
          // Wait for token refresh to complete
          return new Promise((resolve) => {
            subscribeTokenRefresh((token: string) => {
              originalRequest.headers.Authorization = `Bearer ${token}`;
              resolve(client(originalRequest));
            });
          });
        }

        originalRequest._retry = true;
        isRefreshing = true;

        try {
          const response = await axios.post(`${API_BASE}/auth/refresh`, undefined, {
            withCredentials: true,
            timeout: 15000,
          });

          const { access_token } = response.data;
          accessToken = access_token;

          originalRequest.headers.Authorization = `Bearer ${accessToken}`;
          isRefreshing = false;
          onTokenRefreshed(accessToken as string);

          return client(originalRequest);
        } catch (err) {
          isRefreshing = false;
          // Clear tokens and let app redirect to login
          accessToken = null;
          refreshSubscribers = [];
          return Promise.reject(err);
        }
      }

      return Promise.reject(error);
    }
  );

  return client;
};

export const api = createApiClient();

export interface AccueilAppointment {
  id: number;
  reference?: string | null;
  patient_id: number;
  patient_nom: string;
  telephone?: string | null;
  source: string;
  statut: string;
  praticien_nom?: string | null;
  acte_nom?: string | null;
  date_heure_debut: string;
  salle?: string | null;
  episode_id?: number | null;
}

export const accueilApi = {
  list: (params?: Record<string, string | number | undefined>) =>
    api.get<AccueilAppointment[]>('/accueil', { params }),
  markArrived: (rdvId: number) =>
    api.post<{ rdv_id: number; patient_id: number; episode_id?: number | null; statut: string }>(`/accueil/rdv/${rdvId}/arrivee`),
  confirmPresence: (rdvId: number) => api.post(`/accueil/rdv/${rdvId}/presence`),
  confirmExamAgreement: (rdvId: number) => api.post(`/accueil/rdv/${rdvId}/accord`),
  declareAbsence: (rdvId: number, motif: string) => api.post(`/accueil/rdv/${rdvId}/absence`, { motif }),
  proposeReplanification: (rdvId: number, dates: string[]) => api.post(`/accueil/rdv/${rdvId}/replanification/proposer`, { dates }),
  confirmReplanification: (rdvId: number, date_heure: string) => api.post(`/accueil/rdv/${rdvId}/replanification/confirmer`, { date_heure, confirmation_source: 'whatsapp' }),
  history: (rdvId: number) => api.get(`/accueil/rdv/${rdvId}/evenements`),
};

export interface WorkspaceCard {
  key: string;
  title: string;
  count: number;
  description: string;
  href: string;
  next_action: string;
  patient_id?: number | null;
  episode_id?: number | null;
  rdv_id?: number | null;
}

export const workspaceApi = {
  get: () => api.get<{ role: string; generated_at: string; context: { patient?: number | null; episode?: number | null; rdv?: number | null }; cards: WorkspaceCard[] }>('/workspace'),
};

/** Télécharge un fichier CSV renvoyé par l’API privée. */
export const downloadCsv = async (endpoint: string, fallbackFilename: string) => {
  const response = await api.get(endpoint, { responseType: 'blob' });
  const contentDisposition = response.headers['content-disposition'] as string | undefined;
  const filename = contentDisposition?.match(/filename="?([^";]+)"?/i)?.[1] || fallbackFilename;
  const url = URL.createObjectURL(response.data);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  return filename;
};

/** Télécharge un fichier PDF renvoyé par l'API privée (registre d'audit). */
export const downloadPdf = async (endpoint: string, fallbackFilename: string) => {
  const response = await api.get(endpoint, { responseType: 'blob' });
  const contentDisposition = response.headers['content-disposition'] as string | undefined;
  const filename = contentDisposition?.match(/filename="?([^";]+)"?/i)?.[1] || fallbackFilename;
  const url = URL.createObjectURL(response.data);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  return filename;
};

// Client strictement public : aucun access token et aucun endpoint clinique.
export const publicApiClient = axios.create({
  baseURL: PUBLIC_API_BASE,
  withCredentials: false,
  headers: { 'Content-Type': 'application/json' },
});

// Auth utilities
export const setAccessToken = (access: string) => {
  accessToken = access;
};

export const getAccessToken = () => accessToken;

export const clearTokens = () => {
  accessToken = null;
  refreshSubscribers = [];
};

export const isAuthenticated = () => !!accessToken;

// Jeton de challenge MFA (5 min) : gardé en mémoire uniquement, comme les
// tokens d'accès/refresh — jamais en sessionStorage. Il est perdu si la
// page est rechargée pendant la saisie de l'OTP, ce qui est volontaire :
// l'utilisateur recommence simplement le login, exactement comme pour un
// access_token perdu au refresh.
let mfaChallengeToken: string | null = null;
export const setMfaChallengeToken = (token: string) => { mfaChallengeToken = token; };
export const getMfaChallengeToken = () => mfaChallengeToken;
export const clearMfaChallengeToken = () => { mfaChallengeToken = null; };

export interface MfaStatusResponse {
  enabled: boolean;
  setup_at?: string | null;
}

export interface MfaSetupResponse {
  secret: string;
  qr_uri: string;
  qr_code_b64: string;
  backup_codes: string[];
}

export interface MfaChallengeResponse {
  mfa_required: true;
  challenge_token: string;
}

// Auth endpoints
export const authApi = {
  // Le login retourne soit TokenResponse (pas de MFA), soit
  // MfaChallengeResponse (MFA activé) — à distinguer via `mfa_required`.
  login: (identifier: string, password: string) =>
    api.post<TokenResponse | MfaChallengeResponse>('/auth/login', { identifier, password }),

  refresh: () =>
    api.post<TokenResponse>('/auth/refresh'),

  logout: () => api.post('/auth/logout'),

  me: () => api.get<UserOut>('/auth/me'),

  // challenge_token vient de la réponse de login ci-dessus — il n'y a
  // plus de lookup par email ni de user_id envoyé en clair.
  verifyMfa: (challengeToken: string, otp: string) =>
    api.post<TokenResponse>('/auth/mfa/verify', { challenge_token: challengeToken, otp }),

  mfaSetup: () =>
    api.post<MfaSetupResponse>('/auth/mfa/setup'),

  mfaConfirm: (otp: string) =>
    api.post('/auth/mfa/confirm', { otp }),

  mfaDisable: (password: string) =>
    api.post('/auth/mfa/disable', { password }),

  mfaStatus: () =>
    api.get<MfaStatusResponse>('/auth/mfa/status'),
};

// Settings endpoints
export const settingsApi = {
  getBranding: () =>
    api.get<BrandingResponse>('/settings/branding').then((response) => ({
      ...response,
      data: normalizeBrandingResponse(response.data),
    })),

  updateBranding: (data: Partial<BrandingResponse>) =>
    api.patch<BrandingResponse>('/settings/branding', data).then((response) => ({
      ...response,
      data: normalizeBrandingResponse(response.data),
    })),

  uploadLogo: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<{ logo_url: string }>('/settings/branding/logo', formData, {
      headers: { 'Content-Type': undefined },
    });
  },
  uploadHero: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<{ photo_hero_url: string }>('/settings/branding/hero', formData, {
      headers: { 'Content-Type': undefined },
    });
  },
};

// Public endpoints
export const publicApi = {
  getPraticiens: () => publicApiClient.get<PublicPraticien[]>('/praticiens'),

  getActes: () => publicApiClient.get<PublicActe[]>('/actes'),

  getContent: () => publicApiClient.get<PublicContent>('/content'),

  getDisponibilites: (praticienId: number, params?: { date?: string; acte_id?: number; duree?: number }) =>
    publicApiClient.get<PublicDisponibilitesResponse>(`/disponibilites/${praticienId}`, { params }),

  submitCallback: (data: { nom: string; telephone: string; email?: string; message?: string }) =>
    publicApiClient.post<{ lead_id: number; statut: string; message: string }>('/rappel', data),

  chat: (message: string, session_id?: string) =>
    publicApiClient.post<PublicChatResponse>('/chat', { message, session_id }),

  reserveRdv: (data: {
    nom: string;
    prenom: string;
    telephone: string;
    praticien_id: number;
    acte_id: number;
    date_heure: string;
  }) => publicApiClient.post<{
    booking_request_id: number;
    statut: string;
    duplicate: boolean;
  }>('/reservation', data),
};

export const bookingRequestsApi = {
  list: (statut = 'pending') =>
    api.get<BookingRequest[]>('/booking-requests', { params: { statut } }),
  assign: (id: number, praticien_id: number) =>
    api.patch<BookingRequest>(`/booking-requests/${id}/assign`, { praticien_id }),
  approve: (id: number) => api.post<BookingRequest>(`/booking-requests/${id}/approve`),
  reject: (id: number, notes?: string) =>
    api.post<BookingRequest>(`/booking-requests/${id}/reject`, { notes }),
};

export interface PatientSearchResult {
  id: number;
  nom: string;
  prenom: string;
  telephone?: string | null;
  date_naissance?: string | null;
}

export const patientsSearchApi = {
  list: (search: string) => api.get<PatientSearchResult[]>('/patients', { params: { search, limit: 20 } }),
};

export const photosApi = {
  /** Récupère une photo médicale déchiffrée et retourne une object URL
   * affichable dans une balise <img>. Un <img src="..."> classique ne
   * peut pas porter le header Authorization, d'où ce fetch en blob. */
  getPhotoUrl: async (patientId: number, photoId: number, thumbnail = false): Promise<string> => {
    const res = await api.get(`/patients/${patientId}/photos/${photoId}/view`, {
      params: thumbnail ? { thumbnail: true } : undefined,
      responseType: 'blob',
    });
    return URL.createObjectURL(res.data);
  },

  upload: (patientId: number, file: File, params: { type_photo: string; zone?: string; angle?: string; dossier_id?: number }) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/patients/${patientId}/photos`, formData, {
      params,
      headers: { 'Content-Type': undefined },
    });
  },

  delete: (
    patientId: number,
    photoId: number,
    raison = 'Suppression demandée par le médecin',
  ) =>
    api.delete(`/patients/${patientId}/photos/${photoId}`, { params: { raison } }),

  /** Récupère les photos avant/après pour comparaison côte-à-côte.
   *  Utilise l'endpoint backend dédié qui retourne { avant: [...], apres: [...] }.
   */
  getComparaisonAvantApres: (patientId: number, zone?: string) =>
    api.get<{ avant: { id: number; url: string; date: string }[]; apres: { id: number; url: string; date: string }[] }>(
      `/patients/${patientId}/photos/avant-apres`,
      { params: zone ? { zone } : undefined },
    ),
};

export interface GlobalClinicalTimelineItem {
  type: string; date: string; auteur_id?: number; role: string; patient_id: number;
  episode_id?: number | null; statut: string; classification: string; source_id: number; summary: string;
}
export interface StructuredPatientExport { format: string; exported_at: string; patient_id: number; classification: string; entries: GlobalClinicalTimelineItem[] }
export interface MedicalAuditEntry { id: number; action: string; resource_type: string; resource_id: number; patient_id: number; created_at: string; details: Record<string, unknown> }

export const dossierMedicalApi = {
  getTimeline: (patientId: number) => api.get(`/patients/${patientId}/dossiers`),
  getGlobalTimeline: (patientId: number) => api.get<GlobalClinicalTimelineItem[]>(`/patients/${patientId}/global-timeline`),
  exportStructured: (patientId: number) => api.get<StructuredPatientExport>(`/patients/${patientId}/export-structured`),
  listAudit: (patientId: number, action?: string) => api.get<MedicalAuditEntry[]>('/audit/medical', { params: { patient_id: patientId, action } }),
  uploadMedicalDocument: (patientId: number, file: File, description?: string) => {
    const form = new FormData(); form.append('file', file); if (description) form.append('description', description);
    return api.post(`/patients/${patientId}/medical-documents`, form, { headers: { 'Content-Type': undefined } });
  },

  create: (patientId: number, data: {
    praticien_id: number;
    rdv_id?: number;
    acte_id?: number;
    date_acte: string;
    observations?: string;
    effets_secondaires?: string;
    satisfaction_patient?: number;
    suivi_requis?: boolean;
    date_suivi_recommandee?: string;
    actes_details?: any[];
  }) => api.post(`/patients/${patientId}/dossiers`, data),

  listConsentements: (patientId: number) => api.get(`/patients/${patientId}/consentements`),

  /** Ouvre un consentement signé après récupération authentifiée du PDF. */
  getConsentementUrl: async (patientId: number, consentementId: number): Promise<string> => {
    const res = await api.get(`/patients/${patientId}/consentements/${consentementId}/view`, { responseType: 'blob' });
    return URL.createObjectURL(res.data);
  },

  openConsentement: async (patientId: number, consentementId: number) => {
    const url = await dossierMedicalApi.getConsentementUrl(patientId, consentementId);
    const opened = window.open(url, '_blank', 'noopener,noreferrer');
    if (!opened) {
      const link = document.createElement('a');
      link.href = url;
      link.target = '_blank';
      link.rel = 'noreferrer';
      link.click();
    }
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  },

  signConsentement: (patientId: number, data: { acte_id?: number; signature_base64: string; methode_signature?: string }) =>
    api.post(`/patients/${patientId}/consentements`, data),

  listPhotos: (patientId: number) => api.get(`/patients/${patientId}/photos`),

  /** Déclenche le téléchargement du PDF complet du dossier patient. */
  downloadExportPdf: async (patientId: number) => {
    const res = await api.get(`/patients/${patientId}/export-pdf`, { responseType: 'blob' });
    const url = URL.createObjectURL(res.data);
    const link = document.createElement('a');
    link.href = url;
    link.download = `dossier_patient_${patientId}.pdf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },
};

// ── Equipe Messages (Messagerie interne) ───────────────────

export interface EquipeMessage {
  id: number;
  clinic_id: number;
  expediteur_id: number;
  destinataire_id: number;
  expediteur_nom: string;
  expediteur_prenom: string;
  destinataire_nom: string;
  destinataire_prenom: string;
  sujet: string;
  contenu: string;
  lu: boolean;
  lu_a: string | null;
  cree_a: string;
}

export interface EquipeMessageCreate {
  /** Legacy single-recipient payload remains supported by the API. */
  destinataire_id?: number;
  destinataire_ids?: number[];
  idempotency_key?: string;
  sujet: string;
  contenu: string;
}

export interface EquipeMember {
  id: number;
  email: string;
  nom: string;
  prenom: string;
  role: string;
  telephone?: string | null;
  specialite?: string | null;
  is_active: boolean;
}

export const equipeApi = {
  listMembers: () => api.get<EquipeMember[]>('/equipe/membres'),
  // Envoyer un message
  send: (data: EquipeMessageCreate) =>
    api.post<EquipeMessage & { message_ids?: number[]; destinataire_ids?: number[] }>('/equipe/messages', data),

  // Boîte de réception
  getInbox: (page = 1, page_size = 20) =>
    api.get<EquipeMessage[]>('/equipe/messages', { params: { page, page_size } }),

  // Messages envoyés
  getSent: (page = 1, page_size = 20) =>
    api.get<EquipeMessage[]>('/equipe/messages/sent', { params: { page, page_size } }),

  // Détail d'un message
  getOne: (id: number) =>
    api.get<EquipeMessage>(`/equipe/messages/${id}`),

  // Marquer comme lu
  markRead: (id: number) =>
    api.put(`/equipe/messages/${id}/lu`),

  // Supprimer
  delete: (id: number) =>
    api.delete(`/equipe/messages/${id}`),

  // Nombre de non-lus
  getUnreadCount: () =>
    api.get<{ unread_count: number }>('/equipe/messages/unread-count'),
};

export const scribeIaApi = {
  transcribe: (audioBlob: Blob) => {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'recording.webm');
    // Ne jamais fixer 'multipart/form-data' à la main : sans le paramètre
    // boundary (que seul le navigateur peut générer), le serveur ne peut pas
    // parser le corps de la requête. En passant `undefined`, on efface le
    // Content-Type par défaut ('application/json') du client axios et on
    // laisse le navigateur poser lui-même l'en-tête complet avec boundary.
    return api.post<{ text: string }>('/scribe-ia/transcribe', formData, {
      headers: { 'Content-Type': undefined },
    });
  },
  process: (patientId: number, transcription: string, dossierId?: number) =>
    api.post('/scribe-ia/process', {
      patient_id: patientId,
      dossier_id: dossierId,
      transcription_brute: transcription
    }),
};

export default api;


export interface CureSession {
  id: number;
  numero: number;
  rendez_vous_id?: number | null;
  dossier_id?: number | null;
  praticien_id?: number | null;
  planifiee_at?: string | null;
  realisee_at?: string | null;
  statut: string;
  zone_anatomique?: string | null;
  produits_lots: Array<Record<string, unknown>>;
  photos_ids: number[];
  notes?: string | null;
  suivi_recommande_le?: string | null;
}

export interface CureTraitement {
  id: number;
  patient_id: number;
  acte_id?: number | null;
  nom: string;
  description?: string | null;
  zone_anatomique?: string | null;
  seances_prevues: number;
  seances_realisees: number;
  seances_restantes: number;
  statut: string;
  prochaine_seance_at?: string | null;
  notes?: string | null;
  seances: CureSession[];
}

export interface SuiviPostActe {
  id: number;
  patient_id: number;
  dossier_id?: number | null;
  episode_id?: number | null;
  intervention_id?: number | null;
  rdv_id?: number | null;
  seance_id?: number | null;
  type_suivi: string;
  echeance_at: string;
  statut: string;
  assigne_a_id?: number | null;
  notes?: string | null;
  termine_at?: string | null;
}

export interface EvenementIndesirable {
  id: number;
  patient_id: number;
  dossier_id?: number | null;
  acte_id?: number | null;
  seance_id?: number | null;
  survenu_at: string;
  zone_anatomique?: string | null;
  description: string;
  gravite: 'faible' | 'moderee' | 'elevee' | 'critique' | string;
  action_effectuee?: string | null;
  praticien_informe: boolean;
  suivi?: string | null;
  statut: 'ouvert' | 'surveille' | 'cloture' | string;
}

export interface ProtocoleSoin {
  id: number;
  acte_id?: number | null;
  nom: string;
  categorie: string;
  version: string;
  etapes_avant: string[];
  etapes_pendant: string[];
  etapes_apres: string[];
  actif: boolean;
}

export const clinicalOpsApi = {
  dashboard: () => api.get('/clinical-ops/dashboard'),
  listCures: (patientId?: number) => api.get<CureTraitement[]>('/clinical-ops/cures', { params: patientId ? { patient_id: patientId } : undefined }),
  createCure: (data: { patient_id: number; acte_id?: number; nom: string; description?: string; zone_anatomique?: string; seances_prevues: number; premiere_seance_at?: string; notes?: string }) => api.post<CureTraitement>('/clinical-ops/cures', data),
  addSession: (cureId: number, data: Partial<CureSession> & { numero: number }) => api.post<CureTraitement>(`/clinical-ops/cures/${cureId}/seances`, data),
  updateSession: (cureId: number, sessionId: number, data: { statut: string; realisee_at?: string; dossier_id?: number; notes?: string }) => api.patch<CureTraitement>(`/clinical-ops/cures/${cureId}/seances/${sessionId}`, data),
  listFollowups: (params?: { statut?: string; horizon_days?: number }) => api.get<SuiviPostActe[]>('/clinical-ops/suivis', { params }),
  createFollowup: (data: Omit<SuiviPostActe, 'id' | 'statut' | 'termine_at'>) => api.post('/clinical-ops/suivis', data),
  confirmFollowupAppointment: (id: number, data: { date_heure: string; patient_confirme: boolean; salle?: string }) => api.post(`/clinical-ops/suivis/${id}/confirmer-rdv`, data),
  updateFollowup: (id: number, data: { statut: string; notes?: string }) => api.patch(`/clinical-ops/suivis/${id}`, data),
  listAdverseEvents: (params?: { statut?: string; gravite?: string }) => api.get<EvenementIndesirable[]>('/clinical-ops/evenements-indesirables', { params }),
  createAdverseEvent: (data: Omit<EvenementIndesirable, 'id' | 'statut'>) => api.post('/clinical-ops/evenements-indesirables', data),
  updateAdverseEvent: (id: number, data: { statut: string; action_effectuee?: string; praticien_informe?: boolean; suivi?: string }) => api.patch(`/clinical-ops/evenements-indesirables/${id}`, data),
  listProtocols: () => api.get<ProtocoleSoin[]>('/clinical-ops/protocoles'),
  listGlobalAudit: (params?: { date_debut?: string; date_fin?: string; patient_id?: number; role?: string; action?: string; limit?: number }) => api.get('/clinical-ops/audit-global', { params }),
  createProtocol: (data: Omit<ProtocoleSoin, 'id' | 'actif'>) => api.post('/clinical-ops/protocoles', data),
};

// ── Bloc B — Faits médicaux structurés (antécédents, allergies, traitements,
// contre-indications). Lecture/création/désactivation réservées au médecin ;
// le backend refuse toute identité d'auteur fournie par le client.
export interface MedicalFactItem {
  id: number;
  patient_id: number;
  episode_id?: number | null;
  auteur_id: number;
  type_fait: string;
  classification: string;
  source: string;
  verification_status: string;
  actif: boolean;
  donnees: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export const medicalFactsApi = {
  list: (patientId: number) => api.get<MedicalFactItem[]>(`/patients/${patientId}/medical-facts`),
  create: (patientId: number, data: {
    episode_id?: number;
    type_fait: 'antecedent_medical' | 'antecedent_chirurgical' | 'antecedent_anesthesique' | 'antecedent_familial' | 'allergie' | 'traitement' | 'contre_indication' | string;
    donnees: Record<string, unknown>;
    source?: 'MANUAL' | 'MIGRATED';
    verification_status?: 'VERIFIED' | 'PENDING_VERIFICATION' | 'HISTORICAL_UNSTRUCTURED';
  }) => api.post(`/patients/${patientId}/medical-facts`, data),
  /** Suppression logique : la donnée est masquée, l'historique est conservé. */
  delete: (patientId: number, factId: number) => api.delete(`/patients/${patientId}/medical-facts/${factId}`),
};

// ── Bloc C — Prescriptions médicales sécurisées. Création/lecture réservées
// au médecin ; le prescripteur est déduit côté backend de l'utilisateur
// authentifié (jamais envoyé par le client). Détails chiffrés au repos.
export interface PrescriptionItem {
  id: number;
  patient_id: number;
  episode_id?: number | null;
  consultation_id?: number | null;
  intervention_id?: number | null;
  acte_id?: number | null;
  prescripteur_id: number;
  date_prescription: string;
  details: Record<string, unknown>;
  statut: 'ACTIVE' | 'CANCELLED' | 'COMPLETED' | string;
  classification: string;
  created_at: string;
}

export const prescriptionsApi = {
  list: (patientId: number) => api.get<PrescriptionItem[]>(`/patients/${patientId}/prescriptions`),
  create: (patientId: number, data: {
    episode_id?: number;
    consultation_id?: number;
    intervention_id?: number;
    acte_id?: number;
    date_prescription?: string;
    details: Record<string, unknown>;
    statut?: 'ACTIVE' | 'CANCELLED' | 'COMPLETED';
  }) => api.post(`/patients/${patientId}/prescriptions`, data),
};
