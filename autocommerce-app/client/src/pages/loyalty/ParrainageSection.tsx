import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { toast } from 'sonner';
import { Copy, Users, Gift, CheckCircle } from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

export function ParrainageSection({ patientId }: { patientId: number }) {
  const [isLoading, setIsLoading] = useState(true);
  const [code, setCode] = useState('');
  const [filleuls, setFilleuls] = useState<any[]>([]);
  const [newFilleulId, setNewFilleulId] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loadError, setLoadError] = useState('');
  const { t, i18n } = useTranslation();

  useEffect(() => {
    if (patientId) {
      loadParrainageData();
    }
  }, [patientId]);

  const loadParrainageData = async () => {
    try {
      setIsLoading(true);
      setLoadError('');
      const [codeRes, filleulsRes] = await Promise.all([
        api.get(`/parrainage/code/${patientId}`),
        api.get(`/parrainage/filleuls/${patientId}`)
      ]);
      setCode(codeRes.data.code);
      setFilleuls(filleulsRes.data);
    } catch (err: any) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      const message = detail || (status === 404
        ? t('loyalty.referral.errors.patientNotFound')
        : t('loyalty.referral.errors.load'));
      setLoadError(message);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const copyCode = () => {
    navigator.clipboard.writeText(code);
    toast.success(t('loyalty.referral.codeCopied'));
  };

  const handleUseCode = async (e: React.FormEvent) => {
    e.preventDefault();
    const filleulId = Number(newFilleulId.trim());
    if (!Number.isInteger(filleulId) || filleulId <= 0) {
      toast.error(t('loyalty.referral.errors.invalidPatientId'));
      return;
    }
    if (filleulId === patientId) {
      toast.error(t('loyalty.referral.errors.selfReferral'));
      return;
    }
    
    setIsSubmitting(true);
    try {
      await api.post('/parrainage/utiliser', {
        code: code,
        filleul_id: filleulId
      });
      toast.success(t('loyalty.referral.validated'));
      setNewFilleulId('');
      loadParrainageData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('loyalty.referral.errors.validate'));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) return <div className="flex justify-center p-4"><Spinner /></div>;
  if (loadError) {
    return (
      <Card>
        <CardContent className="space-y-3 p-6">
          <p role="alert" className="text-sm text-destructive">{loadError}</p>
          <Button type="button" variant="outline" onClick={loadParrainageData}>
            {t('loyalty.referral.retry')}
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card className="border-primary/20 bg-primary/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Gift className="w-5 h-5 text-primary" />
              {t('loyalty.referral.codeTitle')}
            </CardTitle>
            <CardDescription>
              {t('loyalty.referral.codeDescription')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Input 
                  value={code} 
                  readOnly 
                  className="pr-10 font-mono text-lg text-center tracking-wider font-bold border-primary/30"
                />
              </div>
              <Button onClick={copyCode} variant="outline" size="icon">
                <Copy className="w-4 h-4" />
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="w-5 h-5 text-primary" />
              {t('loyalty.referral.registerTitle')}
            </CardTitle>
            <CardDescription>
              {t('loyalty.referral.registerDescription')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleUseCode} className="flex gap-2">
              <Input 
                placeholder={t('loyalty.referral.patientIdPlaceholder')} 
                value={newFilleulId}
                onChange={(e) => setNewFilleulId(e.target.value)}
              />
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? <Spinner className="h-4 w-4" /> : t('loyalty.referral.validate')}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('loyalty.referral.referralsTitle', { count: filleuls.length })}</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('loyalty.referral.colDate')}</TableHead>
                <TableHead>{t('loyalty.referral.colPatientId')}</TableHead>
                <TableHead>{t('loyalty.referral.colRewardStatus')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filleuls.map((f) => (
                <TableRow key={f.id}>
                  <TableCell>{new Date(f.date).toLocaleDateString(i18n.language)}</TableCell>
                  <TableCell>{t('loyalty.referral.patientRef', { id: f.filleul_id })}</TableCell>
                  <TableCell>
                    {f.recompense_attribuee ? (
                      <span className="flex items-center gap-1 text-green-600 font-medium">
                        <CheckCircle className="w-4 h-4" /> {t('loyalty.referral.rewardGranted')}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">{t('loyalty.referral.rewardPending')}</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {filleuls.length === 0 && (
                <TableRow>
                  <TableCell colSpan={3} className="text-center py-8 text-muted-foreground">
                    {t('loyalty.referral.empty')}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
