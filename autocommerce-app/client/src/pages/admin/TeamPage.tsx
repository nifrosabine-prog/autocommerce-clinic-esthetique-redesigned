import React, { useState, useEffect } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { Plus, Edit2, UserPlus, Globe2 } from 'lucide-react';
import { toast } from 'sonner';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { Checkbox } from '@/components/ui/checkbox';

interface Acte {
  id: number;
  nom: string;
  categorie: string;
}

interface User {
  id: number;
  email: string;
  nom: string;
  prenom: string;
  role: string;
  telephone?: string;
  specialite?: string;
  adresse?: string;
  date_embauche?: string;
  diplomes?: string[];
  certifications?: string[];
  documents_professionnels?: string[];
  notes_internes?: string;
  agenda_color?: string;
  is_active: boolean;
  is_public: boolean;
  acte_ids: number[];
}

/** Transforme les détails FastAPI/Pydantic en texte affichable par Sonner. */
function getApiErrorMessage(detail: unknown, fallback: string): string {
  if (typeof detail === 'string' && detail.trim()) return detail;

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === 'string') return item;
        if (!item || typeof item !== 'object') return null;
        const validation = item as { msg?: unknown; loc?: unknown };
        if (typeof validation.msg !== 'string') return null;
        const field = Array.isArray(validation.loc)
          ? validation.loc.filter((part) => part !== 'body').join('.')
          : '';
        return field ? `${field} : ${validation.msg}` : validation.msg;
      })
      .filter((message): message is string => Boolean(message));
    return messages.length ? messages.join(' · ') : fallback;
  }

  if (detail && typeof detail === 'object' && 'message' in detail) {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === 'string' && message.trim()) return message;
  }

  return fallback;
}

export default function TeamPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [users, setUsers] = useState<User[]>([]);
  const [actes, setActes] = useState<Acte[]>([]);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [formData, setFormData] = useState({
    email: '',
    nom: '',
    prenom: '',
    password: '',
    role: 'medecin',
    telephone: '',
    specialite: '',
    adresse: '',
    date_embauche: '',
    diplomes: '',
    certifications: '',
    documents_professionnels: '',
    notes_internes: '',
    agenda_color: '#0066CC',
    is_public: false,
    acte_ids: [] as number[],
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setIsLoading(true);
      const [usersRes, actesRes] = await Promise.all([
        api.get('/users'),
        api.get('/settings/actes')
      ]);
      setUsers(usersRes.data);
      setActes(actesRes.data);
    } catch (err) {
      toast.error('Erreur lors du chargement des données');
    } finally {
      setIsLoading(false);
    }
  };

  const handleOpenDialog = (user?: User) => {
    if (user) {
      setEditingUser(user);
      setFormData({
        email: user.email,
        nom: user.nom,
        prenom: user.prenom,
        password: '',
        role: user.role,
        telephone: user.telephone || '',
        specialite: user.specialite || '',
        adresse: user.adresse || '',
        date_embauche: user.date_embauche || '',
        diplomes: (user.diplomes || []).join('\n'),
        certifications: (user.certifications || []).join('\n'),
        documents_professionnels: (user.documents_professionnels || []).join('\n'),
        notes_internes: user.notes_internes || '',
        agenda_color: user.agenda_color || '#0066CC',
        is_public: user.is_public,
        acte_ids: user.acte_ids || [],
      });
    } else {
      setEditingUser(null);
      setFormData({
        email: '',
        nom: '',
        prenom: '',
        password: '',
        role: 'medecin',
        telephone: '',
        specialite: '',
        adresse: '',
        date_embauche: '',
        diplomes: '',
        certifications: '',
        documents_professionnels: '',
        notes_internes: '',
        agenda_color: '#0066CC',
        is_public: false,
        acte_ids: [],
      });
    }
    setIsDialogOpen(true);
  };

  const handleSave = async () => {
    try {
      const profilePayload = {
        ...formData,
        // FastAPI accepte une date ISO ou null ; une chaîne vide produit une 422.
        date_embauche: formData.date_embauche || undefined,
        diplomes: formData.diplomes.split('\n').map((item) => item.trim()).filter(Boolean),
        certifications: formData.certifications.split('\n').map((item) => item.trim()).filter(Boolean),
        documents_professionnels: formData.documents_professionnels.split('\n').map((item) => item.trim()).filter(Boolean),
      };
      if (editingUser) {
        const { password, ...updateData } = profilePayload;
        const payload = password ? profilePayload : updateData;
        await api.patch(`/users/${editingUser.id}`, payload);
        toast.success('Compte mis à jour');
      } else {
        if (!formData.password) {
          toast.error('Le mot de passe est obligatoire pour un nouveau compte');
          return;
        }
        await api.post('/users', profilePayload);
        toast.success('Compte créé');
      }
      setIsDialogOpen(false);
      loadData();
    } catch (err: any) {
      toast.error(getApiErrorMessage(err?.response?.data?.detail, 'Erreur lors de la sauvegarde'));
    }
  };

  const toggleActe = (acteId: number) => {
    setFormData(prev => ({
      ...prev,
      acte_ids: prev.acte_ids.includes(acteId)
        ? prev.acte_ids.filter(id => id !== acteId)
        : [...prev.acte_ids, acteId]
    }));
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold">Gestion de l'Équipe</h1>
            <p className="text-muted-foreground mt-1">Gérez les comptes praticiens et leurs habilitations</p>
          </div>
          <Button onClick={() => handleOpenDialog()}>
            <UserPlus className="w-4 h-4 mr-2" /> Nouveau membre
          </Button>
        </div>

        <Card>
          <CardContent className="p-0">
            {isLoading ? (
              <div className="flex justify-center p-8"><Spinner /></div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Nom</TableHead>
                    <TableHead>Rôle</TableHead>
                    <TableHead>Spécialité</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Actes</TableHead>
                    <TableHead>Statut</TableHead>
                    <TableHead>Landing</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((u) => (
                    <TableRow key={u.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: u.agenda_color || '#ccc' }} />
                          <span className="font-medium">{u.prenom} {u.nom}</span>
                        </div>
                      </TableCell>
                      <TableCell className="capitalize">{u.role}</TableCell>
                      <TableCell>{u.specialite || '-'}</TableCell>
                      <TableCell>{u.email}</TableCell>
                      <TableCell>{u.acte_ids?.length || 0} acte(s)</TableCell>
                      <TableCell>
                        <span className={`px-2 py-1 rounded-full text-xs ${u.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                          {u.is_active ? 'Actif' : 'Inactif'}
                        </span>
                      </TableCell>
                      <TableCell>
                        {['medecin', 'estheticienne'].includes(u.role) ? (
                          <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs ${u.is_public ? 'bg-teal-50 text-teal-800' : 'bg-slate-100 text-slate-600'}`}>
                            <Globe2 className="h-3 w-3" />{u.is_public ? 'Publié' : 'Non publié'}
                          </span>
                        ) : '—'}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="sm" onClick={() => handleOpenDialog(u)}>
                          <Edit2 className="w-4 h-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingUser ? 'Modifier le membre' : 'Nouveau membre'}</DialogTitle>
            <DialogDescription>Configurez les accès et les pratiques du praticien.</DialogDescription>
          </DialogHeader>
          <div className="space-y-6 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="prenom">Prénom *</Label>
                <Input id="prenom" value={formData.prenom} onChange={(e) => setFormData({...formData, prenom: e.target.value})} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="nom">Nom *</Label>
                <Input id="nom" value={formData.nom} onChange={(e) => setFormData({...formData, nom: e.target.value})} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="email">Email *</Label>
                <Input id="email" type="email" value={formData.email} onChange={(e) => setFormData({...formData, email: e.target.value})} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="password">{editingUser ? 'Mot de passe (laisser vide pour inchangé)' : 'Mot de passe *'}</Label>
                <Input id="password" type="password" value={formData.password} onChange={(e) => setFormData({...formData, password: e.target.value})} />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="role">Rôle *</Label>
                <select 
                  id="role" 
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  value={formData.role} 
                  onChange={(e) => setFormData({...formData, role: e.target.value})}
                >
                  <option value="medecin">Médecin</option>
                  <option value="estheticienne">Esthéticienne</option>
                  <option value="assistante">Assistante</option>
                  <option value="commercial">Commercial</option>
                  <option value="admin">Administrateur</option>
                </select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="specialite">Spécialité</Label>
                <Input id="specialite" value={formData.specialite} onChange={(e) => setFormData({...formData, specialite: e.target.value})} placeholder="ex: Dermatologie" />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="color">Couleur Agenda</Label>
                <div className="flex gap-2">
                  <Input id="color" type="color" value={formData.agenda_color} onChange={(e) => setFormData({...formData, agenda_color: e.target.value})} className="w-12 h-10 p-1" />
                  <Input value={formData.agenda_color} onChange={(e) => setFormData({...formData, agenda_color: e.target.value})} className="flex-1" />
                </div>
              </div>
            </div>

            {['medecin', 'estheticienne'].includes(formData.role) && (
              <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
                <Checkbox checked={formData.is_public} onCheckedChange={(checked) => setFormData({ ...formData, is_public: checked === true })} />
                <span><strong className="font-medium text-slate-900">Publier ce praticien à la réservation</strong><br />Son profil actif pourra apparaître sur la landing publique de la clinique.</span>
              </label>
            )}

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="grid gap-2"><Label htmlFor="adresse">Adresse professionnelle</Label><Input id="adresse" value={formData.adresse} onChange={(e) => setFormData({...formData, adresse: e.target.value})} /></div>
              <div className="grid gap-2"><Label htmlFor="date_embauche">Date d’embauche</Label><Input id="date_embauche" type="date" value={formData.date_embauche} onChange={(e) => setFormData({...formData, date_embauche: e.target.value})} /></div>
              <div className="grid gap-2"><Label htmlFor="diplomes">Diplômes</Label><textarea id="diplomes" className="min-h-20 rounded-md border bg-background px-3 py-2 text-sm" placeholder="Un diplôme par ligne" value={formData.diplomes} onChange={(e) => setFormData({...formData, diplomes: e.target.value})} /></div>
              <div className="grid gap-2"><Label htmlFor="certifications">Certifications</Label><textarea id="certifications" className="min-h-20 rounded-md border bg-background px-3 py-2 text-sm" placeholder="Une certification par ligne" value={formData.certifications} onChange={(e) => setFormData({...formData, certifications: e.target.value})} /></div>
              <div className="grid gap-2"><Label htmlFor="documents_professionnels">Documents professionnels</Label><textarea id="documents_professionnels" className="min-h-20 rounded-md border bg-background px-3 py-2 text-sm" placeholder="Références ou URLs, une par ligne" value={formData.documents_professionnels} onChange={(e) => setFormData({...formData, documents_professionnels: e.target.value})} /></div>
              <div className="grid gap-2"><Label htmlFor="notes_internes">Notes internes</Label><textarea id="notes_internes" className="min-h-20 rounded-md border bg-background px-3 py-2 text-sm" value={formData.notes_internes} onChange={(e) => setFormData({...formData, notes_internes: e.target.value})} /></div>
            </div>

            <div className="space-y-3">
              <Label>Actes pratiqués</Label>
              <div className="grid grid-cols-2 gap-2 border rounded-md p-4 bg-gray-50 max-h-48 overflow-y-auto">
                {actes.map(acte => (
                  <div key={acte.id} className="flex items-center space-x-2">
                    <Checkbox 
                      id={`acte-${acte.id}`} 
                      checked={formData.acte_ids.includes(acte.id)}
                      onCheckedChange={() => toggleActe(acte.id)}
                    />
                    <label htmlFor={`acte-${acte.id}`} className="text-sm cursor-pointer truncate">
                      {acte.nom} <span className="text-xs text-gray-400">({acte.categorie})</span>
                    </label>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDialogOpen(false)}>Annuler</Button>
            <Button onClick={handleSave}>Sauvegarder</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </DashboardLayout>
  );
}
