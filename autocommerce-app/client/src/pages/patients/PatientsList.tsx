import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { api, downloadCsv } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { Download, Plus, Search, Phone, ShieldOff, Pencil, Eye } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/contexts/AuthContext';
import { useLocation } from 'wouter';
import { PatientFormDialog, type Patient } from '@/components/patients/PatientFormDialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

export default function PatientsList({ mode = 'patients' }: { mode?: 'patients' | 'medical-record' }) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const isMedicalRecordIndex = mode === 'medical-record';
  const [, setLocation] = useLocation();
  const canAnonymize = user?.role === 'directrice' || user?.role === 'admin';
  const canCreatePatient = ['directrice', 'medecin', 'estheticienne', 'assistante', 'admin'].includes(user?.role || '');
  const [isLoading, setIsLoading] = useState(true);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [filteredPatients, setFilteredPatients] = useState<Patient[]>([]);
  const [anonymizingId, setAnonymizingId] = useState<number | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [editingPatient, setEditingPatient] = useState<Patient | null>(null);

  useEffect(() => {
    loadPatients();
  }, []);

  useEffect(() => {
    // Correctif 2026-09-11 (audit AUD-002 suite) : recherche par nom OU
    // téléphone fonctionnelle pour tous les rôles. Le téléphone est comparé
    // en chiffres uniquement (« 20 000 001 », « +216… », « 20000001 » ou
    // « 21620000001 » trouvent tous le même patient) et whatsapp_phone est
    // inclus s'il est renvoyé par l'API.
    const q = searchQuery.trim().toLowerCase();
    const qDigits = searchQuery.replace(/\D/g, '');
    const filtered = patients.filter((p) => {
      if (!q && !qDigits) return true;
      const matchText =
        (p.nom || '').toLowerCase().includes(q) ||
        (p.prenom || '').toLowerCase().includes(q);
      const telDigits = (p.telephone || '').replace(/\D/g, '');
      const waDigits = ((p as unknown as { whatsapp_phone?: string }).whatsapp_phone || '').replace(/\D/g, '');
      const matchPhone = qDigits.length > 0 && (telDigits.includes(qDigits) || waDigits.includes(qDigits));
      return matchText || matchPhone;
    });
    setFilteredPatients(filtered);
  }, [searchQuery, patients]);

  const loadPatients = async () => {
    try {
      setIsLoading(true);
      const response = await api.get('/patients');
      setPatients(Array.isArray(response.data) ? response.data : response.data.patients || []);
    } catch (err: any) {
      console.error('Failed to load patients:', err);
      // Ne jamais conserver des données cliniques d’une session/clinique précédente
      // lorsqu’un rechargement privé est refusé ou échoue.
      setPatients([]);
      toast.error(t('patients.loadError'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleAnonymize = async (patient: Patient) => {
    try {
      setAnonymizingId(patient.id);
      await api.delete(`/patients/${patient.id}/rgpd`);
      toast.success(t('patients.anonymizeSuccess'));
      loadPatients();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('patients.anonymizeError'));
    } finally {
      setAnonymizingId(null);
    }
  };

  const handleExportCsv = async () => {
    try {
      setIsExporting(true);
      const endpoint = searchQuery.trim()
        ? `/patients/export.csv?search=${encodeURIComponent(searchQuery.trim())}`
        : '/patients/export.csv';
      await downloadCsv(endpoint, 'patients.csv');
      toast.success(t('patients.exportSuccess'));
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('patients.exportError'));
    } finally {
      setIsExporting(false);
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
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">{isMedicalRecordIndex ? t('patients.medicalRecordsTitle') : t('common.patients')}</h1>
            <p className="text-muted-foreground mt-1">{isMedicalRecordIndex ? t('patients.medicalRecordsCount', { count: patients.length }) : t('patients.registeredCount', { count: patients.length })}</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={handleExportCsv} disabled={isExporting}>
              <Download className="w-4 h-4 mr-2" />
              {isExporting ? t('patients.exporting') : t('patients.exportCsv')}
            </Button>
            {canCreatePatient && (
              <Button onClick={() => { setEditingPatient(null); setFormOpen(true); }}>
                <Plus className="w-4 h-4 mr-2" />
                {t('patients.newPatient')}
              </Button>
            )}
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{t('common.search')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Search className="w-4 h-4 text-muted-foreground" />
              <Input
                placeholder={t('patients.searchPlaceholder')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="flex-1"
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            {filteredPatients.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">{t('patients.no_patient_found')}</p>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('patients.name')}</TableHead>
                      <TableHead>{t('patients.firstName')}</TableHead>
                      <TableHead>{t('patients.phone')}</TableHead>
                      <TableHead>{t('patients.email')}</TableHead>
                      <TableHead>{t('patients.registrationDate')}</TableHead>
                      <TableHead>{t('patients.actions')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredPatients.map((patient) => (
                      <TableRow key={patient.id} className="hover:bg-muted/50">
                        <TableCell className="font-medium">{patient.nom}</TableCell>
                        <TableCell>{patient.prenom}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Phone className="w-4 h-4 text-muted-foreground" />
                            {patient.telephone}
                          </div>
                        </TableCell>
                        <TableCell>{patient.email || '-'}</TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {patient.date_inscription
                            ? new Date(patient.date_inscription).toLocaleDateString('fr-FR')
                            : '-'}
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setLocation(isMedicalRecordIndex ? `/medical-record/${patient.id}` : `/patients/${patient.id}`)}
                            >
                              <Eye className="w-4 h-4 mr-1" />
                              {isMedicalRecordIndex ? t('patients.openFile') : t('patients.view')}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => { setEditingPatient(patient); setFormOpen(true); }}
                            >
                              <Pencil className="w-4 h-4 mr-1" />
                              {t('common.edit')}
                            </Button>
                            {canAnonymize && (
                              <AlertDialog>
                                <AlertDialogTrigger asChild>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="text-destructive hover:text-destructive"
                                    aria-label={t('patients.deleteAnonymizeAria', { name: `${patient.prenom} ${patient.nom}` })}
                                    title={t('patients.deleteAnonymizeAria', { name: `${patient.prenom} ${patient.nom}` })}
                                    disabled={anonymizingId === patient.id}
                                  >
                                    <ShieldOff className="w-4 h-4 mr-1" />
                                    {t('common.delete')}
                                  </Button>
                                </AlertDialogTrigger>
                                <AlertDialogContent>
                                  <AlertDialogHeader>
                                    <AlertDialogTitle>{t('patients.anonymizeTitle')}</AlertDialogTitle>
                                    <AlertDialogDescription>
                                      {t('patients.anonymizeWarning', { name: `${patient.prenom} ${patient.nom}` })}
                                    </AlertDialogDescription>
                                  </AlertDialogHeader>
                                  <AlertDialogFooter>
                                    <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                                    <AlertDialogAction
                                      onClick={() => handleAnonymize(patient)}
                                      className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                    >
                                      {t('patients.confirmAnonymize')}
                                    </AlertDialogAction>
                                  </AlertDialogFooter>
                                </AlertDialogContent>
                              </AlertDialog>
                            )}
                          </div>
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

      <PatientFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        patient={editingPatient}
        onSaved={loadPatients}
      />
    </DashboardLayout>
  );
}
