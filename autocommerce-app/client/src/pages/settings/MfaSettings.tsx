import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { authApi, MfaStatusResponse, MfaSetupResponse } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { Shield, ShieldCheck, ShieldOff, Copy, Check } from 'lucide-react';

type Step = 'initial' | 'setup' | 'confirm' | 'enabled';

export default function MfaSettings() {
  const { t, i18n } = useTranslation();
  const [step, setStep] = useState<Step>('initial');
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState<MfaStatusResponse | null>(null);
  const [setupData, setSetupData] = useState<MfaSetupResponse | null>(null);
  const [confirmOtp, setConfirmOtp] = useState('');
  const [disablePassword, setDisablePassword] = useState('');
  const [copied, setCopied] = useState<number | null>(null);

  // Charger le statut MFA au montage
  useEffect(() => {
    const loadStatus = async () => {
      try {
        const res = await authApi.mfaStatus();
        setStatus(res.data);
        setStep(res.data.enabled ? 'enabled' : 'initial');
      } catch {
        // Si le MFA n'est pas accessible, rester sur initial
      }
    };
    loadStatus();
  }, []);

  // Étape 1 : Démarrer la configuration MFA
  const handleSetup = async () => {
    setIsLoading(true);
    try {
      const res = await authApi.mfaSetup();
      setSetupData(res.data);
      setStep('setup');
      toast.success(t('auth.mfaSetupToast'));
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('auth.mfaSetupError'));
    } finally {
      setIsLoading(false);
    }
  };

  // Étape 2 : Confirmer avec le premier OTP
  const handleConfirm = async () => {
    if (confirmOtp.length !== 6) {
      toast.error(t('auth.mfaCodeLength'));
      return;
    }
    setIsLoading(true);
    try {
      await authApi.mfaConfirm(confirmOtp);
      setStatus({ enabled: true, setup_at: new Date().toISOString() });
      setStep('enabled');
      toast.success(t('auth.mfaSuccess'));
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('auth.mfaInvalidCode'));
    } finally {
      setIsLoading(false);
    }
  };

  // Étape 3 : Désactiver le MFA
  const handleDisable = async () => {
    if (!disablePassword) {
      toast.error(t('auth.mfaPasswordRequired'));
      return;
    }
    setIsLoading(true);
    try {
      await authApi.mfaDisable(disablePassword);
      setStatus({ enabled: false, setup_at: null });
      setStep('initial');
      setDisablePassword('');
      toast.success(t('auth.mfaDisabled'));
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('auth.mfaGenericError'));
    } finally {
      setIsLoading(false);
    }
  };

  const copyCode = (code: string, index: number) => {
    navigator.clipboard.writeText(code);
    setCopied(index);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">{t('auth.mfaSettingsTitle')}</h1>
          <p className="text-muted-foreground mt-1">
            {t('auth.mfaSettingsSubtitle')}
          </p>
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {status?.enabled ? (
                  <ShieldCheck className="h-6 w-6 text-green-600" />
                ) : (
                  <ShieldOff className="h-6 w-6 text-muted-foreground" />
                )}
                <div>
                  <CardTitle>{t('auth.mfaCardTitle')}</CardTitle>
                  <CardDescription>
                    {status?.enabled
                      ? t('auth.mfaEnabledDesc')
                      : t('auth.mfaDisabledDesc')}
                  </CardDescription>
                </div>
              </div>
              <Badge variant={status?.enabled ? 'default' : 'secondary'}>
                {status?.enabled ? t('auth.mfaEnabledBadge') : t('auth.mfaDisabledBadge')}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* État initial : proposer d'activer */}
            {step === 'initial' && !status?.enabled && (
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  {t('auth.mfaIntro')}
                </p>
                <Button onClick={handleSetup} disabled={isLoading}>
                  <Shield className="mr-2 h-4 w-4" />
                  {t('auth.mfaConfigure')}
                </Button>
              </div>
            )}

            {/* État setup : afficher le QR et les codes de secours */}
            {step === 'setup' && setupData && (
              <div className="space-y-6">
                <div className="text-center space-y-3">
                  <p className="text-sm font-medium">{t('auth.mfaScanQr')}</p>
                  <img
                    src={`data:image/png;base64,${setupData.qr_code_b64}`}
                    alt={t('auth.mfaQrAlt')}
                    className="w-48 h-48 mx-auto border rounded-lg"
                  />
                  <p className="text-xs text-muted-foreground">
                    {t('auth.mfaManualEntry')} <code className="bg-muted px-1 rounded">{setupData.secret}</code>
                  </p>
                </div>

                <div className="space-y-2">
                  <p className="text-sm font-medium">{t('auth.mfaEnterCode')}</p>
                  <div className="flex gap-2">
                    <Input
                      placeholder={t('auth.mfaCodePlaceholder')}
                      value={confirmOtp}
                      onChange={(e) => setConfirmOtp(e.target.value)}
                      maxLength={6}
                    />
                    <Button onClick={handleConfirm} disabled={isLoading || confirmOtp.length !== 6}>
                      {t('auth.mfaConfirm')}
                    </Button>
                  </div>
                </div>

                <div className="space-y-2 pt-4 border-t">
                  <p className="text-sm font-medium">{t('auth.mfaBackupCodes')}</p>
                  <p className="text-xs text-muted-foreground">
                    {t('auth.mfaBackupHelp')}
                  </p>
                  <div className="grid grid-cols-2 gap-2 mt-2">
                    {setupData.backup_codes.map((code, i) => (
                      <div
                        key={i}
                        className="flex items-center justify-between bg-muted p-2 rounded text-sm font-mono"
                      >
                        <span>{code}</span>
                        <button
                          onClick={() => copyCode(code, i)}
                          className="text-muted-foreground hover:text-foreground"
                        >
                          {copied === i ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* État enabled : proposer de désactiver */}
            {step === 'enabled' && status?.enabled && (
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  {t('auth.mfaActiveInfo')}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t('auth.mfaEnabledOn', { date: status.setup_at ? new Date(status.setup_at).toLocaleDateString(i18n.language) : t('auth.notAvailable') })}
                </p>

                <div className="pt-4 border-t space-y-3">
                  <p className="text-sm font-medium">{t('auth.mfaDisableLabel')}</p>
                  <div className="flex gap-2">
                    <Input
                      type="password"
                      placeholder={t('auth.mfaPasswordPlaceholder')}
                      value={disablePassword}
                      onChange={(e) => setDisablePassword(e.target.value)}
                    />
                    <Button
                      variant="destructive"
                      onClick={handleDisable}
                      disabled={isLoading || !disablePassword}
                    >
                      {t('auth.mfaDisable')}
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
