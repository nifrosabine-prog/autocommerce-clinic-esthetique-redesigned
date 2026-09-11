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

export interface EmailDeliverySettings {
  provider: 'resend';
  sending_domain: string;
  from_email: string;
  byok_secret_configured: boolean;
  email_channel_allowed: boolean;
  ready: boolean;
  secret_storage: 'deployment_secret_only';
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
  acte_id: number;
  date_heure: string;
  statut: 'pending' | 'accepted' | 'rejected' | string;
  patient_id?: number | null;
  rendez_vous_id?: number | null;
  review_notes?: string | null;
  created_at: string;
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
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  uploadHero: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<{ photo_hero_url: string }>('/settings/branding/hero', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  getEmailDelivery: () => api.get<EmailDeliverySettings>('/settings/email-delivery'),
  updateEmailDelivery: (data: Pick<EmailDeliverySettings, 'provider' | 'sending_domain' | 'from_email'>) =>
    api.put<EmailDeliverySettings>('/settings/email-delivery', data),
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
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  delete: (patientId: number, photoId: number) =>
    api.delete(`/patients/${patientId}/photos/${photoId}`),

  /** Récupère les photos avant/après pour comparaison côte-à-côte.
   *  Utilise l'endpoint backend dédié qui retourne { avant: [...], apres: [...] }.
   */
  getComparaisonAvantApres: (patientId: number, zone?: string) =>
    api.get<{ avant: { id: number; url: string; date: string }[]; apres: { id: number; url: string; date: string }[] }>(
      `/patients/${patientId}/photos/avant-apres`,
      { params: zone ? { zone } : undefined },
    ),
};

export const dossierMedicalApi = {
  getTimeline: (patientId: number) => api.get(`/patients/${patientId}/dossiers`),

  getActesCliniques: () => api.get('/clinical/actes'),

  getAppointmentContext: (patientId: number) => api.get<Array<{
    id: number; acte_id?: number | null; acte_nom: string; date_heure: string; statut: string;
  }>>(`/patients/${patientId}/contexte-rendez-vous`),

  create: (patientId: number, data: {
    praticien_id?: number;
    rdv_id?: number;
    acte_id?: number;
    date_acte: string;
    observations?: string;
    effets_secondaires?: string;
    satisfaction_patient?: number;
    suivi_requis?: boolean;
    date_suivi_recommandee?: string;
    actes_details?: any[];
    statut_clinique?: 'brouillon' | 'cloture';
  }) => api.post(`/patients/${patientId}/dossiers`, data),

  close: (patientId: number, dossierId: number) =>
    api.post(`/patients/${patientId}/dossiers/${dossierId}/cloturer`),

  listConsentements: (patientId: number) => api.get(`/patients/${patientId}/consentements`),

  previewConsentementContractuel: (patientId: number, acteIds: number[]) =>
    api.post<{ contenu: string; snapshot: { actes: Array<{ id: number; nom: string; prix: number; devise: string }> } }>(
      `/patients/${patientId}/consentements/apercu-contrat`,
      { acte_ids: acteIds },
    ),

  downloadConsentementPreviewPdf: async (patientId: number, acteIds: number[]) => {
    const res = await api.post(`/patients/${patientId}/consentements/apercu-contrat-pdf`, { acte_ids: acteIds }, { responseType: 'blob' });
    const url = URL.createObjectURL(res.data);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'apercu-contrat-consentement-non-signe.pdf';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },

  signConsentement: (patientId: number, data: {
    acte_id?: number;
    acte_ids?: number[];
    signature_base64: string;
    signature_praticien_base64?: string;
    methode_signature?: string;
    attestation_praticien?: boolean;
  }) =>
    api.post(`/patients/${patientId}/consentements`, data),

  downloadConsentementPdf: async (patientId: number, consentementId: number) => {
    const res = await api.get(`/patients/${patientId}/consentements/${consentementId}/export-pdf`, { responseType: 'blob' });
    const url = URL.createObjectURL(res.data);
    const link = document.createElement('a');
    link.href = url;
    link.download = `contrat-consentement-${consentementId}.pdf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },

  emailConsentementPdf: (patientId: number, consentementId: number) =>
    api.post<{ status: 'sent'; recipient: string; external_message_id?: string }>(
      `/patients/${patientId}/consentements/${consentementId}/envoyer-email`,
      { confirmation: true },
    ),

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
  destinataire_id: number;
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
    api.post<EquipeMessage>('/equipe/messages', data),

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
    return api.post<{ text: string }>('/scribe-ia/transcribe', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
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
  updateFollowup: (id: number, data: { statut: string; notes?: string }) => api.patch(`/clinical-ops/suivis/${id}`, data),
  listAdverseEvents: (params?: { statut?: string; gravite?: string }) => api.get<EvenementIndesirable[]>('/clinical-ops/evenements-indesirables', { params }),
  createAdverseEvent: (data: Omit<EvenementIndesirable, 'id' | 'statut'>) => api.post('/clinical-ops/evenements-indesirables', data),
  updateAdverseEvent: (id: number, data: { statut: string; action_effectuee?: string; praticien_informe?: boolean; suivi?: string }) => api.patch(`/clinical-ops/evenements-indesirables/${id}`, data),
  listProtocols: () => api.get<ProtocoleSoin[]>('/clinical-ops/protocoles'),
  createProtocol: (data: Omit<ProtocoleSoin, 'id' | 'actif'>) => api.post('/clinical-ops/protocoles', data),
};
