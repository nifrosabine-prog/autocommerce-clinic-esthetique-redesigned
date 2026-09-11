import { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'wouter';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import { api } from '@/lib/api';
import { FileHeart, Search, Stethoscope } from 'lucide-react';
import { toast } from 'sonner';
import type { Patient } from '@/components/patients/PatientFormDialog';

export default function ClinicalRecordsList() {
  const [, setLocation] = useLocation();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadPatients = async () => {
      try {
        const response = await api.get('/patients');
        setPatients(Array.isArray(response.data) ? response.data : response.data.patients || []);
      } catch {
        setPatients([]);
        toast.error('Les dossiers cliniques n’ont pas pu être chargés.');
      } finally {
        setIsLoading(false);
      }
    };
    void loadPatients();
  }, []);

  const filteredPatients = useMemo(() => {
    const term = query.trim().toLocaleLowerCase('fr-FR');
    if (!term) return patients;
    return patients.filter((patient) => [patient.nom, patient.prenom, patient.telephone].some((value) => value?.toLocaleLowerCase('fr-FR').includes(term)));
  }, [patients, query]);

  return (
    <DashboardLayout>
      <div className="mx-auto max-w-6xl space-y-6 pb-10">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:p-7">
          <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal-700">Espace clinique</p>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950 md:text-3xl">Dossiers cliniques</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
                Accédez au contexte patient, aux consentements et à la saisie clinique depuis une liste dédiée.
              </p>
            </div>
            <div className="flex items-center gap-2 text-sm text-slate-600"><Stethoscope className="h-4 w-4 text-teal-700" /> {patients.length} patient{patients.length > 1 ? 's' : ''} au dossier accessible</div>
          </div>
        </section>

        <Card className="border-slate-200 shadow-sm">
          <CardContent className="p-5">
            <div className="relative max-w-xl">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <Input value={query} onChange={(event) => setQuery(event.target.value)} className="pl-9" placeholder="Rechercher un patient par nom, prénom ou téléphone" aria-label="Rechercher un dossier clinique" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200 shadow-sm">
          <CardContent className="p-0">
            {isLoading ? (
              <div className="flex min-h-56 items-center justify-center"><Spinner /></div>
            ) : filteredPatients.length === 0 ? (
              <div className="p-10 text-center text-sm text-slate-600">Aucun patient ne correspond à cette recherche.</div>
            ) : (
              <ul className="divide-y divide-slate-100">
                {filteredPatients.map((patient) => (
                  <li key={patient.id} className="flex flex-col gap-4 p-5 transition-colors hover:bg-slate-50 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-teal-50 text-teal-700"><FileHeart className="h-5 w-5" /></div>
                      <div className="min-w-0">
                        <p className="truncate font-medium text-slate-950">{patient.prenom} {patient.nom}</p>
                        <p className="truncate text-sm text-slate-500">{patient.telephone}{patient.email ? ` · ${patient.email}` : ''}</p>
                      </div>
                    </div>
                    <Button className="shrink-0 bg-teal-700 text-white hover:bg-teal-800" onClick={() => setLocation(`/patients/${patient.id}`)}>
                      Ouvrir le dossier
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
