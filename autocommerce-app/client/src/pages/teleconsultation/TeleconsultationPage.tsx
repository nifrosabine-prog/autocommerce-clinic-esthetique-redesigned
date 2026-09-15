import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { toast } from 'sonner';
import { Video, ExternalLink, Clock, FileText, Plus } from 'lucide-react';

export default function TeleconsultationPage({ rdvId }: { rdvId?: number }) {
  const [isLoading, setIsLoading] = useState(false);
  const [tcData, setTcData] = useState<any>(null);
  const { t } = useTranslation();

  useEffect(() => {
    if (rdvId) {
      loadTeleconsultation();
    }
  }, [rdvId]);

  const loadTeleconsultation = async () => {
    try {
      setIsLoading(true);
      const response = await api.get(`/teleconsultation/${rdvId}/lien`);
      setTcData(response.data);
    } catch (err) {
      // If no existing room is found, the UI offers creation.
      setTcData(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!rdvId) return;
    try {
      setIsLoading(true);
      const response = await api.post('/teleconsultation/creer', { rdv_id: rdvId });
      setTcData(response.data);
      toast.success(t('teleconsultation.created'));
    } catch (err) {
      toast.error(t('teleconsultation.createError'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleComplete = async () => {
    if (!tcData) return;
    try {
      setIsLoading(true);
      await api.post(`/teleconsultation/${tcData.id}/terminer`, {
        duree: 30, // Default duration
        notes: t('teleconsultation.completionNote')
      });
      toast.success(t('teleconsultation.completed'));
      loadTeleconsultation();
    } catch (err) {
      toast.error(t('teleconsultation.genericError'));
    } finally {
      setIsLoading(false);
    }
  };

  if (!rdvId) {
    return (
      <DashboardLayout>
        <div className="flex flex-col items-center justify-center h-96 space-y-4">
          <Video className="w-16 h-16 text-muted-foreground" />
          <h2 className="text-xl font-semibold">{t('teleconsultation.noAppointmentTitle')}</h2>
          <p className="text-muted-foreground">{t('teleconsultation.noAppointmentDesc')}</p>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <Video className="w-8 h-8 text-primary" />
            {t('teleconsultation.title')}
          </h1>
          {tcData && (
            <div className={`px-3 py-1 rounded-full text-sm font-medium ${
              tcData.statut === 'terminee' ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800'
            }`}>
              {tcData.statut === 'terminee' ? t('teleconsultation.status_completed') : t('teleconsultation.status_active')}
            </div>
          )}
        </div>

        {!tcData ? (
          <Card className="text-center py-12">
            <CardContent className="space-y-4">
              <div className="bg-primary/10 w-16 h-16 rounded-full flex items-center justify-center mx-auto">
                <Video className="w-8 h-8 text-primary" />
              </div>
              <div className="space-y-2">
                <CardTitle>{t('teleconsultation.readyTitle')}</CardTitle>
                <CardDescription>
                  {t('teleconsultation.readyDesc')}
                </CardDescription>
              </div>
              <Button onClick={handleCreate} disabled={isLoading} size="lg">
                {isLoading ? <Spinner className="mr-2" /> : <Plus className="mr-2 w-4 h-4" />}
                {t('teleconsultation.createLink')}
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card className="md:col-span-2">
              <CardHeader>
                <CardTitle>{t('teleconsultation.consultationLinkTitle')}</CardTitle>
                <CardDescription>{t('teleconsultation.consultationLinkDesc')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="p-4 bg-muted rounded-lg font-mono text-sm break-all">
                  {tcData.lien_visio}
                </div>
                <div className="flex gap-4">
                  <Button asChild className="flex-1" size="lg">
                    <a href={tcData.lien_visio} target="_blank" rel="noopener noreferrer">
                      <ExternalLink className="mr-2 w-4 h-4" />
                      {t('teleconsultation.join')}
                    </a>
                  </Button>
                  {tcData.statut !== 'terminee' && (
                    <Button variant="outline" onClick={handleComplete} disabled={isLoading}>
                      {t('teleconsultation.markCompleted')}
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>

            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-semibold flex items-center gap-2">
                    <Clock className="w-4 h-4" /> {t('teleconsultation.details')}
                  </CardTitle>
                </CardHeader>
                <CardContent className="text-sm space-y-2">
                  <div className="flex justify-between text-muted-foreground">
                    <span>{t('teleconsultation.appointmentId')}</span>
                    <span className="text-foreground">#{rdvId}</span>
                  </div>
                  <div className="flex justify-between text-muted-foreground">
                    <span>{t('teleconsultation.platform')}</span>
                    <span className="text-foreground">Jitsi Meet</span>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-semibold flex items-center gap-2">
                    <FileText className="w-4 h-4" /> {t('teleconsultation.notes')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <textarea 
                    className="w-full min-h-[100px] p-2 text-sm border rounded-md"
                    placeholder={t('teleconsultation.notesPlaceholder')}
                  ></textarea>
                </CardContent>
              </Card>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
