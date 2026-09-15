import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { AlertCircle, CheckCircle, Clock, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useAuth } from '@/contexts/AuthContext';
import { useCurrency } from '@/hooks/useCurrency';
import { formatMoney } from '@/lib/currency';

interface Commission {
  id: number;
  commercial_id: number;
  commercial_nom: string;
  montant: number;
  statut: 'en_attente' | 'validation_partielle' | 'validee' | 'payee';
  validateur_1_id?: number;
  validateur_1_nom?: string;
  validateur_2_id?: number;
  validateur_2_nom?: string;
  validee_par_id_2?: number;
  validated_at_2?: string;
  date_creation: string;
}

export default function CommissionsPage() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const currency = useCurrency();
  const [isLoading, setIsLoading] = useState(true);
  const [commissions, setCommissions] = useState<Commission[]>([]);
  const [validatingId, setValidatingId] = useState<number | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    loadCommissions();
  }, []);

  const loadCommissions = async () => {
    try {
      setIsLoading(true);
      const response = await api.get('/commissions');
      // Le backend renvoie un tableau brut, pas { commissions: [...] }
      setCommissions(Array.isArray(response.data) ? response.data : []);
      setLoadError(null);
    } catch (err: any) {
      console.error('Failed to load commissions:', err);
      setLoadError(t('commissions.loadError'));
      toast.error(t('commissions.loadError'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleValidate = async (commission: Commission) => {
    try {
      setValidatingId(commission.id);
      await api.patch(`/commissions/${commission.id}/valider`);
      toast.success(t('commissions.validated'));
      loadCommissions();
    } catch (err: any) {
      const message = err.response?.data?.detail || t('commissions.validateError');
      toast.error(message);
    } finally {
      setValidatingId(null);
    }
  };

  const handlePay = async (commission: Commission) => {
    try {
      setValidatingId(commission.id);
      await api.post(`/commissions/${commission.id}/payer`, { date_paiement: new Date().toISOString().split('T')[0] });
      toast.success(t('commissions.paid'));
      loadCommissions();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('commissions.payError'));
    } finally {
      setValidatingId(null);
    }
  };

  const canPay = ['directrice', 'admin'].includes(user?.role || '');

  const canValidate = (commission: Commission) => {
    // For partial validation, only the first validator can validate again
    if (commission.statut === 'validation_partielle') {
      return commission.validateur_1_id !== user?.id;
    }
    // For pending, anyone can validate
    return commission.statut === 'en_attente';
  };

  const getStatusColor = (statut: string) => {
    switch (statut) {
      case 'en_attente':
        return 'bg-yellow-100 text-yellow-800';
      case 'validation_partielle':
        return 'bg-blue-100 text-blue-800';
      case 'validee':
        return 'bg-green-100 text-green-800';
      case 'payee':
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusIcon = (statut: string) => {
    switch (statut) {
      case 'en_attente':
        return <Clock className="w-4 h-4" />;
      case 'validation_partielle':
        return <AlertCircle className="w-4 h-4" />;
      case 'validee':
        return <CheckCircle className="w-4 h-4" />;
      default:
        return null;
    }
  };

  const getStatusLabel = (statut: string, commission?: Commission) => {
    switch (statut) {
      case 'en_attente':
        return t('commissions.statusPending');
      case 'validation_partielle':
        return t('commissions.statusPartial');
      case 'validee':
        return (commission?.validateur_2_id || commission?.validee_par_id_2)
          ? t('commissions.statusDoubleValidated')
          : t('commissions.statusValidated');
      case 'payee':
        return t('commissions.statusPaid');
      default:
        return statut;
    }
  };

  const needsDoubleValidation = (montant: number) => montant > 500;

  if (loadError && commissions.length === 0) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-96">
          <Card className="w-full max-w-md border-red-300 bg-red-50/70">
            <CardContent className="flex items-center justify-between gap-4 py-6">
              <div className="flex items-center gap-3 text-red-800">
                <AlertCircle className="w-5 h-5 shrink-0" />
                <div>
                  <p className="font-medium">{t('commissions.cannotLoad')}</p>
                  <p className="text-sm text-red-700">{loadError}</p>
                </div>
              </div>
              <Button variant="outline" onClick={() => void loadCommissions()}>
                <RefreshCw className="w-4 h-4 mr-2" /> {t('commissions.retry')}
              </Button>
            </CardContent>
          </Card>
        </div>
      </DashboardLayout>
    );
  }

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-96">
          <Spinner />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">{t('commissions.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('commissions.subtitle')}</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{t('commissions.validationFlow')}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            <p>{t('commissions.flowDirect')}</p>
            <p>{t('commissions.flowDouble')}</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            {commissions.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">{t('commissions.none')}</p>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('commissions.salesperson')}</TableHead>
                      <TableHead>{t('commissions.amount')}</TableHead>
                      <TableHead>{t('commissions.status')}</TableHead>
                      <TableHead>{t('commissions.validators')}</TableHead>
                      <TableHead>{t('commissions.date')}</TableHead>
                      <TableHead>{t('commissions.actions')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {commissions.map((commission) => (
                      <TableRow key={commission.id}>
                        <TableCell className="font-medium">{commission.commercial_nom}</TableCell>
                        <TableCell>
                          <span className={needsDoubleValidation(commission.montant) ? 'font-bold text-orange-600' : ''}>
                            {formatMoney(commission.montant, currency)}
                          </span>
                          {needsDoubleValidation(commission.montant) && (
                            <span className="ml-2 text-xs bg-orange-100 text-orange-800 px-2 py-1 rounded">
                              {t('commissions.doubleValidation')}
                            </span>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {getStatusIcon(commission.statut)}
                            <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${getStatusColor(commission.statut)}`}>
                              {getStatusLabel(commission.statut, commission)}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="text-sm">
                          <div>{commission.validateur_1_nom || <span className="text-muted-foreground">-</span>}</div>
                          {commission.validateur_2_nom && (
                            <div className="text-xs text-muted-foreground">
                              {t('commissions.secondValidator')} : {commission.validateur_2_nom}
                            </div>
                          )}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {new Date(commission.date_creation).toLocaleDateString(i18n.language)}
                        </TableCell>
                        <TableCell>
                          {canValidate(commission) ? (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleValidate(commission)}
                              disabled={validatingId === commission.id}
                            >
                              {validatingId === commission.id ? t('commissions.validating') : t('commissions.validate')}
                            </Button>
                          ) : commission.statut === 'validee' && canPay ? (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handlePay(commission)}
                              disabled={validatingId === commission.id}
                            >
                              {validatingId === commission.id ? t('commissions.paying') : t('commissions.pay')}
                            </Button>
                          ) : (
                            <Button variant="ghost" size="sm" disabled>
                              {commission.statut === 'payee' ? t('commissions.statusPaid') : t('commissions.statusValidated')}
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
