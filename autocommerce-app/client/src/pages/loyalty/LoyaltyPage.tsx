import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { Gift, TrendingUp, TrendingDown } from 'lucide-react';
import { toast } from 'sonner';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ParrainageSection } from './ParrainageSection';
import { useAuth } from '@/contexts/AuthContext';

interface LoyaltyTransaction {
  id: number;
  patient_nom: string;
  type: 'gain' | 'depense';
  points: number;
  motif: string;
  date: string;
}

export default function LoyaltyPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [transactions, setTransactions] = useState<LoyaltyTransaction[]>([]);
  const [totalPoints, setTotalPoints] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const { user } = useAuth();
  const { t, i18n } = useTranslation();
  const canViewReferrals = ['directrice', 'assistante', 'admin'].includes(user?.role || '');

  useEffect(() => {
    loadLoyaltyData();
  }, []);

  const loadLoyaltyData = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await api.get('/fidelite');
      setTransactions(Array.isArray(response.data?.transactions) ? response.data.transactions : []);
      setTotalPoints(Number(response.data?.total_points) || 0);
    } catch (err: any) {
      console.error('Failed to load loyalty data:', err);
      setTransactions([]);
      setTotalPoints(0);
      setError(t('loyalty.errors.unavailable'));
      toast.error(t('loyalty.errors.load'));
    } finally {
      setIsLoading(false);
    }
  };

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
          <h1 className="text-3xl font-bold">{t('loyalty.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('loyalty.subtitle')}</p>
        </div>

        {error && <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{error}</p>}
        <Tabs defaultValue="historique" className="w-full">
          <TabsList className={`grid w-full ${canViewReferrals ? 'grid-cols-2' : 'grid-cols-1'} mb-8`}>
            <TabsTrigger value="historique">{t('loyalty.tabs.history')}</TabsTrigger>
            {canViewReferrals && <TabsTrigger value="parrainage">{t('loyalty.tabs.referral')}</TabsTrigger>}
          </TabsList>

          <TabsContent value="historique" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Gift className="w-5 h-5" />
                  {t('loyalty.totalPoints')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-primary">{t('loyalty.pointsValue', { count: totalPoints })}</div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t('loyalty.historyTitle')}</CardTitle>
              </CardHeader>
              <CardContent>
                {transactions.length === 0 ? (
                  <p className="text-center text-muted-foreground py-8">{t('loyalty.noTransactions')}</p>
                ) : (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>{t('loyalty.colPatient')}</TableHead>
                          <TableHead>{t('loyalty.colType')}</TableHead>
                          <TableHead>{t('loyalty.colPoints')}</TableHead>
                          <TableHead>{t('loyalty.colReason')}</TableHead>
                          <TableHead>{t('loyalty.colDate')}</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {transactions.map((tx) => (
                          <TableRow key={tx.id}>
                            <TableCell className="font-medium">{tx.patient_nom}</TableCell>
                            <TableCell>
                              <div className="flex items-center gap-2">
                                {tx.type === 'gain' ? (
                                  <>
                                    <TrendingUp className="w-4 h-4 text-green-600" />
                                    <span className="text-green-600">{t('loyalty.typeGain')}</span>
                                  </>
                                ) : (
                                  <>
                                    <TrendingDown className="w-4 h-4 text-red-600" />
                                    <span className="text-red-600">{t('loyalty.typeSpend')}</span>
                                  </>
                                )}
                              </div>
                            </TableCell>
                            <TableCell className="font-semibold">{t('loyalty.pointsValue', { count: tx.points })}</TableCell>
                            <TableCell>{tx.motif}</TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {new Date(tx.date).toLocaleDateString(i18n.language)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {canViewReferrals && (
            <TabsContent value="parrainage">
              <ParrainageSection patientId={1} />
            </TabsContent>
          )}
        </Tabs>
      </div>
    </DashboardLayout>
  );
}
