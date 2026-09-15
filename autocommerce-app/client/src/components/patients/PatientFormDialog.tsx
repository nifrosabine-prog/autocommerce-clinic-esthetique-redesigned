import { useTranslation } from 'react-i18next';
import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { Spinner } from '@/components/ui/spinner';
import { api } from '@/lib/api';
import { toast } from 'sonner';
import { useAuth } from '@/contexts/AuthContext';

export interface Patient {
  id: number;
  nom: string;
  prenom: string;
  telephone: string;
  whatsapp_phone?: string;
  email?: string;
  date_naissance?: string;
  genre?: string;
  adresse?: string;
  ville?: string;
  groupe_sanguin?: string;
  allergies?: string;
  antecedents_medicaux?: string;
  contre_indications?: string;
  note_interne?: string;
  consentement_marketing?: boolean;
  date_inscription?: string;
}

interface PatientFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  patient?: Patient | null; // undefined/null = mode création
  onSaved: () => void;
}

const EMPTY_FORM = {
  nom: '', prenom: '', telephone: '', email: '', date_naissance: '', genre: '',
  adresse: '', ville: '', groupe_sanguin: '', allergies: '', antecedents_medicaux: '',
  contre_indications: '', note_interne: '', consentement_marketing: false,
};

export function PatientFormDialog({
  open, onOpenChange, patient, onSaved }: PatientFormDialogProps) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const isEdit = !!patient;
  // Les esthéticiennes ne voient pas les antécédents médicaux (matrice RBAC
  // backend) — cohérent avec ce que GET /patients/{id} leur retourne déjà.
  const canSeeAntecedents = user?.role !== 'estheticienne';
  const [form, setForm] = useState(EMPTY_FORM);
  const [isSaving, setIsSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (open) {
      setForm(patient ? {
        nom: patient.nom || '', prenom: patient.prenom || '',
        telephone: patient.telephone || '', email: patient.email || '',
        date_naissance: patient.date_naissance?.slice(0, 10) || '',
        genre: patient.genre || '', adresse: patient.adresse || '',
        ville: patient.ville || '', groupe_sanguin: patient.groupe_sanguin || '',
        allergies: patient.allergies || '', antecedents_medicaux: patient.antecedents_medicaux || '',
        contre_indications: patient.contre_indications || '', note_interne: patient.note_interne || '',
        consentement_marketing: patient.consentement_marketing || false,
      } : EMPTY_FORM);
      setErrors({});
    }
  }, [open, patient]);

  const handleChange = (field: string, value: string | boolean) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!form.nom.trim()) errs.nom = t('componentUi.lastNameRequired');
    if (!form.prenom.trim()) errs.prenom = t('componentUi.firstNameRequired');
    if (!form.telephone.trim()) errs.telephone = t('componentUi.phoneRequired');
    else if (!/^\+?\d{8,15}$/.test(form.telephone.replace(/\s/g, ''))) {
      errs.telephone = t('componentUi.invalidPhone');
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    const payload: Record<string, unknown> = {
      nom: form.nom.trim(),
      prenom: form.prenom.trim(),
      email: form.email || undefined,
      date_naissance: form.date_naissance || undefined,
      genre: form.genre || undefined,
      adresse: form.adresse || undefined,
      ville: form.ville || undefined,
      groupe_sanguin: form.groupe_sanguin || undefined,
      allergies: form.allergies || undefined,
      contre_indications: form.contre_indications || undefined,
      note_interne: form.note_interne || undefined,
      consentement_marketing: form.consentement_marketing,
    };
    if (canSeeAntecedents) {
      payload.antecedents_medicaux = form.antecedents_medicaux || undefined;
    }
    if (!isEdit) {
      payload.telephone = form.telephone.trim();
    }

    setIsSaving(true);
    try {
      if (isEdit) {
        await api.patch(`/patients/${patient!.id}`, payload);
        toast.success(t('componentUi.patientUpdated'));
      } else {
        await api.post('/patients', payload);
        toast.success(t('componentUi.patientCreated'));
      }
      onOpenChange(false);
      onSaved();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (err.response?.status === 409) {
        toast.error(detail || t('componentUi.duplicatePatient'));
      } else if (err.response?.status === 422 && Array.isArray(detail)) {
        toast.error(detail.map((d: any) => d.msg).join(', '));
      } else {
        toast.error(detail || t('componentUi.saveError'));
      }
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? t('componentUi.editPatient') : t('componentUi.newPatient')}</DialogTitle>
          <DialogDescription>
            {isEdit ? t('componentUi.editPatientDescription') : t('componentUi.newPatientDescription')}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="nom">{t('componentUi.lastName')} *</Label>
              <Input id="nom" value={form.nom} onChange={(e) => handleChange('nom', e.target.value)} />
              {errors.nom && <p className="text-xs text-destructive mt-1">{errors.nom}</p>}
            </div>
            <div>
              <Label htmlFor="prenom">{t('componentUi.firstName')} *</Label>
              <Input id="prenom" value={form.prenom} onChange={(e) => handleChange('prenom', e.target.value)} />
              {errors.prenom && <p className="text-xs text-destructive mt-1">{errors.prenom}</p>}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="telephone">{t('componentUi.phone')} *</Label>
              <Input
                id="telephone"
                value={form.telephone}
                onChange={(e) => handleChange('telephone', e.target.value)}
                disabled={isEdit}
                placeholder={t('componentUi.phonePlaceholder')}
              />
              {errors.telephone && <p className="text-xs text-destructive mt-1">{errors.telephone}</p>}
              {isEdit && <p className="text-xs text-muted-foreground mt-1">{t('componentUi.phoneImmutable')}</p>}
            </div>
            <div>
              <Label htmlFor="email">{t('componentUi.email')}</Label>
              <Input id="email" type="email" value={form.email} onChange={(e) => handleChange('email', e.target.value)} />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <Label htmlFor="date_naissance">{t('componentUi.birthDate')}</Label>
              <Input id="date_naissance" type="date" value={form.date_naissance} onChange={(e) => handleChange('date_naissance', e.target.value)} />
            </div>
            <div>
              <Label htmlFor="genre">{t('componentUi.gender')}</Label>
              <select
                id="genre"
                value={form.genre}
                onChange={(e) => handleChange('genre', e.target.value)}
                className="w-full h-9 px-3 border rounded-md text-sm"
              >
                <option value="">{t('componentUi.genderUnspecified')}</option>
                <option value="F">{t('componentUi.female')}</option>
                <option value="M">{t('componentUi.male')}</option>
              </select>
            </div>
            <div>
              <Label htmlFor="groupe_sanguin">{t('componentUi.bloodGroup')}</Label>
              <Input id="groupe_sanguin" value={form.groupe_sanguin} onChange={(e) => handleChange('groupe_sanguin', e.target.value)} placeholder={t('componentUi.bloodGroupPlaceholder')} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="adresse">{t('componentUi.address')}</Label>
              <Input id="adresse" value={form.adresse} onChange={(e) => handleChange('adresse', e.target.value)} />
            </div>
            <div>
              <Label htmlFor="ville">{t('componentUi.city')}</Label>
              <Input id="ville" value={form.ville} onChange={(e) => handleChange('ville', e.target.value)} />
            </div>
          </div>

          <div>
            <Label htmlFor="allergies">{t('componentUi.allergies')}</Label>
            <Textarea id="allergies" value={form.allergies} onChange={(e) => handleChange('allergies', e.target.value)} rows={2} />
          </div>

          <div>
            <Label htmlFor="contre_indications">{t('componentUi.contraindications')}</Label>
            <Textarea id="contre_indications" value={form.contre_indications} onChange={(e) => handleChange('contre_indications', e.target.value)} rows={2} />
          </div>

          {canSeeAntecedents && (
            <div>
              <Label htmlFor="antecedents_medicaux">{t('componentUi.medicalHistory')}</Label>
              <Textarea id="antecedents_medicaux" value={form.antecedents_medicaux} onChange={(e) => handleChange('antecedents_medicaux', e.target.value)} rows={2} />
            </div>
          )}

          <div>
            <Label htmlFor="note_interne">{t('componentUi.internalNote')}</Label>
            <Textarea id="note_interne" value={form.note_interne} onChange={(e) => handleChange('note_interne', e.target.value)} rows={2} />
          </div>

          <div className="flex items-center gap-2">
            <Checkbox
              id="consentement_marketing"
              checked={form.consentement_marketing}
              onCheckedChange={(checked) => handleChange('consentement_marketing', !!checked)}
            />
            <Label htmlFor="consentement_marketing" className="font-normal">
              {t('componentUi.marketingConsent')}
            </Label>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t('componentUi.cancel')}
            </Button>
            <Button type="submit" disabled={isSaving}>
              {isSaving ? <Spinner className="h-4 w-4" /> : isEdit ? t('componentUi.save') : t('componentUi.create')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
