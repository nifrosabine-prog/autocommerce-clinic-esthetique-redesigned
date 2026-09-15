import { useTranslation } from 'react-i18next';
import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { Clock, LogIn, LogOut, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

export function PointageWidget() {
  const { t, i18n } = useTranslation();
  const [isLoading, setIsLoading] = useState(true);
  const [isClockedIn, setIsClockedIn] = useState(false);
  const [currentPointage, setCurrentPointage] = useState<any>(null);
  const [elapsedTime, setElapsedTime] = useState<string>('00:00:00');

  useEffect(() => {
    loadStatus();
  }, []);

  useEffect(() => {
    let interval: any;
    if (isClockedIn && currentPointage) {
      interval = setInterval(() => {
        const start = new Date(currentPointage.debut).getTime();
        const now = new Date().getTime();
        const diff = now - start;
        
        const h = Math.floor(diff / 3600000);
        const m = Math.floor((diff % 3600000) / 60000);
        const s = Math.floor((diff % 60000) / 1000);
        
        setElapsedTime(
          `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
        );
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isClockedIn, currentPointage]);

  const loadStatus = async () => {
    try {
      setIsLoading(true);
      const res = await api.get('/pointage/statut');
      setIsClockedIn(res.data.is_clocked_in);
      setCurrentPointage(res.data.current_pointage);
    } catch (err) {
      console.error('Erreur pointage status', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClockAction = async () => {
    const action = isClockedIn ? 'sortie' : 'entree';
    try {
      setIsLoading(true);
      const res = await api.post(`/pointage/${action}`);
      setIsClockedIn(!isClockedIn);
      setCurrentPointage(isClockedIn ? null : res.data);
      toast.success(isClockedIn ? t('componentUi.departureRecorded') : t('componentUi.arrivalRecorded'));
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('componentUi.clockError'));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card className={isClockedIn ? 'border-green-500 bg-green-50/30' : ''}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Clock className="w-4 h-4 text-muted-foreground" />
          {t('componentUi.clockedInStatus')}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-4">
          <div className="text-center">
            <p
              className="text-3xl font-bold font-mono"
              aria-label={t('componentUi.elapsedTime', { time: isClockedIn ? elapsedTime : '00:00:00' })}
            >
              {isClockedIn ? elapsedTime : '00:00:00'}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {isClockedIn 
                ? t('componentUi.arrivalAt', { time: new Date(currentPointage?.debut).toLocaleTimeString(i18n.resolvedLanguage || i18n.language, { hour: '2-digit', minute: '2-digit' }) })
                : t('componentUi.notClockedIn')
              }
            </p>
          </div>
          
          <Button 
            variant={isClockedIn ? 'destructive' : 'default'}
            className="w-full"
            onClick={handleClockAction}
            disabled={isLoading}
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : isClockedIn ? (
              <LogOut className="w-4 h-4 mr-2" />
            ) : (
              <LogIn className="w-4 h-4 mr-2" />
            )}
            {isClockedIn ? t('componentUi.clockOut') : t('componentUi.clockIn')}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
