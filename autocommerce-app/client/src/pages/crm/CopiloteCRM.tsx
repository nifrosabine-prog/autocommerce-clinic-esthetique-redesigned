import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import {
  Search,
  FileText,
  AlertCircle,
  MessageSquare,
  Mail,
  TrendingDown,
  CheckCircle,
  Clock,
  Zap,
} from 'lucide-react';

interface PatientSummary {
  patient_id: number;
  data: {
    patient: {
      id: number;
      prenom: string;
      nom: string;
      email: string | null;
      telephone: string | null;
      notes: string | null;
    };
    actes_summary: Record<string, {
      count: number;
      last_date: string | null;
      avg_satisfaction: number | null;
    }>;
    rdvs: {
      total: number;
      completed: number;
      cancelled: number;
      no_show: number;
      next: { id: number; date: string; acte: string | null; praticien: string | null } | null;
    };
    factures: { count: number };
    photos: { series_count: number };
  };
  llm_summary: string | null;
  llm_status: string;
}

interface AtRiskPatient {
  patient_id: number;
  patient_name: string;
  risk_score: number;
  risk_level: 'critical' | 'high' | 'medium';
  reasons: string[];
}

export default function CopiloteCRM() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const [selectedPatientId, setSelectedPatientId] = useState<number | null>(() => {
    const stored = Number(sessionStorage.getItem('copilote-selected-patient'));
    return Number.isFinite(stored) && stored > 0 ? stored : null;
  });
  const [patientSummary, setPatientSummary] = useState<PatientSummary | null>(null);
  const [atRiskPatients, setAtRiskPatients] = useState<AtRiskPatient[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'summary' | 'at-risk' | 'draft'>('summary');
  const [draft, setDraft] = useState<{ channel: string; subject?: string; body?: string; content?: string } | null>(null);

  const loadPatientSummary = async (patientId: number) => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await api.get(`/copilote-crm/patient/${patientId}/summary`);
      if (response.data?.data) {
        setPatientSummary(response.data.data);
        setSelectedPatientId(patientId);
        sessionStorage.setItem('copilote-selected-patient', String(patientId));
      }
    } catch (err: any) {
      setError(err.message || t('crm.loadSummaryError'));
    } finally {
      setIsLoading(false);
    }
  };

  const loadAtRiskPatients = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await api.get('/copilote-crm/at-risk-patients');
      const payload = response.data?.data;
      if (payload) {
        const now = Date.now();
        const items = Array.isArray(payload.items) ? payload.items : [];
        setAtRiskPatients(items.map((item: { id: number; name?: string; last_visit?: string | null }) => {
          const lastVisit = item.last_visit ? new Date(item.last_visit).getTime() : null;
          const daysSinceVisit = lastVisit ? Math.max(0, Math.floor((now - lastVisit) / 86400000)) : null;
          const riskScore = daysSinceVisit === null
            ? 100
            : Math.min(100, Math.round((daysSinceVisit / 120) * 100));
          const riskLevel = riskScore >= 80 ? 'critical' : riskScore >= 50 ? 'high' : 'medium';
          return {
            patient_id: item.id,
            patient_name: item.name?.trim() || t('crm.patientFallback', { id: item.id }),
            risk_score: riskScore,
            risk_level: riskLevel,
            reasons: [
              daysSinceVisit === null
                ? t('crm.noVisit')
                : t('crm.lastVisitDays', { days: daysSinceVisit }),
            ],
          };
        }));
      }
    } catch (err: any) {
      setError(err.message || t('crm.loadAtRiskError'));
    } finally {
      setIsLoading(false);
    }
  };

  const generateDraft = async (channel: 'whatsapp' | 'email') => {
    if (!selectedPatientId) {
      setError(t('crm.selectPatientFirst'));
      return;
    }
    try {
      setIsLoading(true);
      setError(null);
      const endpoint = channel === 'whatsapp' ? 'whatsapp-draft' : 'email-draft';
      const response = await api.get(`/copilote-crm/patient/${selectedPatientId}/${endpoint}`);
      setDraft(response.data?.data ?? null);
    } catch (err: any) {
      setError(err.message || t('crm.draftError', { channel }));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadAtRiskPatients();
  }, []);

  const totalActes = patientSummary
    ? Object.values(patientSummary.data.actes_summary).reduce((total, acte) => total + acte.count, 0)
    : 0;

  if (isLoading && !patientSummary) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-screen">
          <Spinner />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Titre */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900">{t('crm.title')}</h1>
          <p className="text-gray-600 mt-2">{t('crm.subtitle')}</p>
        </div>

        {/* Erreur */}
        {error && (
          <Card className="border-red-200 bg-red-50">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 text-red-700">
                <AlertCircle className="w-5 h-5" />
                <span>{error}</span>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Onglets */}
        <div className="flex gap-2 border-b">
          <button
            onClick={() => setActiveTab('summary')}
            className={`px-4 py-2 font-medium border-b-2 transition ${
              activeTab === 'summary'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            <FileText className="w-4 h-4 inline mr-2" />
            {t('crm.tabSummary')}
          </button>
          <button
            onClick={() => setActiveTab('at-risk')}
            className={`px-4 py-2 font-medium border-b-2 transition ${
              activeTab === 'at-risk'
                ? 'border-red-600 text-red-600'
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            <AlertCircle className="w-4 h-4 inline mr-2" />
            {t('crm.tabAtRisk', { total: atRiskPatients.length })}
          </button>
          <button
            onClick={() => setActiveTab('draft')}
            className={`px-4 py-2 font-medium border-b-2 transition ${
              activeTab === 'draft'
                ? 'border-green-600 text-green-600'
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            <MessageSquare className="w-4 h-4 inline mr-2" />
            {t('crm.tabDrafts')}
          </button>
        </div>

        {/* Onglet Résumé Patient */}
        {activeTab === 'summary' && (
          <div className="space-y-6">
            {/* Recherche patient */}
            <Card>
              <CardHeader>
                <CardTitle>{t('crm.searchPatient')}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex gap-2">
                  <input
                    type="number"
                    placeholder={t('crm.patientIdPlaceholder')}
                    className="flex-1 px-3 py-2 border rounded-lg"
                    onKeyPress={(e) => {
                      if (e.key === 'Enter') {
                        const patientId = parseInt((e.target as HTMLInputElement).value);
                        if (patientId) loadPatientSummary(patientId);
                      }
                    }}
                  />
                  <button
                    onClick={() => {
                      const input = document.querySelector('input[type="number"]') as HTMLInputElement;
                      if (input?.value) loadPatientSummary(parseInt(input.value));
                    }}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                  >
                    <Search className="w-4 h-4" />
                  </button>
                </div>
              </CardContent>
            </Card>

            {/* Résumé du patient */}
            {patientSummary && (
              <div className="space-y-4">
                {/* Infos patient */}
                <Card>
                  <CardHeader>
                    <CardTitle>{`${patientSummary.data.patient.prenom} ${patientSummary.data.patient.nom}`.trim()}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-sm text-gray-600">{t('crm.phone')}</p>
                        <p className="font-medium">{patientSummary.data.patient.telephone || t('crm.notProvided')}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">{t('crm.email')}</p>
                        <p className="font-medium">{patientSummary.data.patient.email || t('crm.notProvided')}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">{t('crm.notes')}</p>
                        <p className="font-medium">{patientSummary.data.patient.notes || t('crm.noNote')}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Historique médical */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <FileText className="w-5 h-5" />
                      {t('crm.medicalHistory')}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      <div>
                        <p className="text-sm text-gray-600">{t('crm.totalActes')}</p>
                        <p className="text-2xl font-bold">{totalActes}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600 mb-2">{t('crm.actesPerformed')}</p>
                        <div className="space-y-1">
                          {Object.entries(patientSummary.data.actes_summary).map(([acte, data]: any) => (
                            <div key={acte} className="text-sm">
                              <span className="font-medium">{acte}</span>
                              <span className="text-gray-600"> - {data.count} {t('crm.times')}</span>
                              {data.avg_satisfaction && (
                                <span className="text-yellow-600"> - ⭐ {data.avg_satisfaction.toFixed(1)}</span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Rendez-vous */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Clock className="w-5 h-5" />
                      {t('crm.appointments')}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div>
                        <p className="text-sm text-gray-600">{t('crm.total')}</p>
                        <p className="text-2xl font-bold">{patientSummary.data.rdvs.total}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">{t('crm.completed')}</p>
                        <p className="text-2xl font-bold text-green-600">{patientSummary.data.rdvs.completed}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">{t('crm.cancelled')}</p>
                        <p className="text-2xl font-bold text-orange-600">{patientSummary.data.rdvs.cancelled}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">{t('crm.noShow')}</p>
                        <p className="text-2xl font-bold text-red-600">{patientSummary.data.rdvs.no_show}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Finances */}
                <Card>
                  <CardHeader>
                    <CardTitle>{t('crm.finances')}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-sm text-gray-600">{t('crm.invoices')}</p>
                        <p className="text-2xl font-bold">{patientSummary.data.factures.count}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">{t('crm.photoSeries')}</p>
                        <p className="text-2xl font-bold text-blue-600">{patientSummary.data.photos.series_count}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
          </div>
        )}

        {/* Onglet Patients à Risque */}
        {activeTab === 'at-risk' && (
          <div className="space-y-4">
            {atRiskPatients.length === 0 ? (
              <Card>
                <CardContent className="pt-12 pb-12 text-center">
                  <p className="text-gray-500">{t('crm.noAtRisk')}</p>
                </CardContent>
              </Card>
            ) : (
              atRiskPatients.map((patient) => (
                <Card
                  key={patient.patient_id}
                  className={
                    patient.risk_level === 'critical'
                      ? 'border-red-300 bg-red-50'
                      : patient.risk_level === 'high'
                      ? 'border-orange-300 bg-orange-50'
                      : 'border-yellow-300 bg-yellow-50'
                  }
                >
                  <CardContent className="pt-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <p className="font-bold text-lg">{patient.patient_name}</p>
                        <p className="text-sm text-gray-600 mt-1">{t('crm.riskScore', { score: patient.risk_score })}</p>
                        <div className="mt-2 space-y-1">
                          {patient.reasons.map((reason, idx) => (
                            <p key={idx} className="text-sm text-gray-700">• {reason}</p>
                          ))}
                        </div>
                      </div>
                      <span
                        className={`px-3 py-1 rounded-full text-xs font-bold ${
                          patient.risk_level === 'critical'
                            ? 'bg-red-200 text-red-800'
                            : patient.risk_level === 'high'
                            ? 'bg-orange-200 text-orange-800'
                            : 'bg-yellow-200 text-yellow-800'
                        }`}
                      >
                        {t(`crm.risk_${patient.risk_level}`)}
                      </span>
                    </div>
                    <button
                      onClick={() => {
                        setSelectedPatientId(patient.patient_id);
                        loadPatientSummary(patient.patient_id);
                        setActiveTab('summary');
                      }}
                      className="mt-4 px-3 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
                    >
                      {t('crm.viewFile')}
                    </button>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        )}

        {/* Onglet Brouillons */}
        {activeTab === 'draft' && (
          <Card>
            <CardHeader>
              <CardTitle>{t('crm.draftsTitle')}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-gray-600">
                {t('crm.draftsEmpty')}
              </p>
              {selectedPatientId && (
                <div className="mt-4 space-y-4">
                  <button onClick={() => void generateDraft('whatsapp')} disabled={isLoading} className="w-full px-4 py-2 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 flex items-center gap-2 disabled:opacity-50">
                    <MessageSquare className="w-4 h-4" />
                    {t('crm.generateWhatsapp')}
                  </button>
                  <button onClick={() => void generateDraft('email')} disabled={isLoading} className="w-full px-4 py-2 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 flex items-center gap-2 disabled:opacity-50">
                    <Mail className="w-4 h-4" />
                    {t('crm.generateEmail')}
                  </button>
                  {draft && (
                    <div className="rounded-lg border bg-white p-4 space-y-2">
                      <p className="text-sm font-semibold">{t('crm.draftChannel', { channel: draft.channel })}</p>
                      {draft.subject && <p className="text-sm"><strong>{t('crm.subjectLabel')}</strong> {draft.subject}</p>}
                      <p className="whitespace-pre-wrap text-sm text-gray-700">{draft.body || draft.content || t('crm.draftNoContent')}</p>
                      <p className="text-xs text-gray-500">{t('crm.draftOnly')}</p>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}
