import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';
import { Plus, Edit2, Trash2, Home } from 'lucide-react';
import { toast } from 'sonner';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';

interface Salle {
  id: number;
  nom: string;
  type: string;
  description?: string;
  is_active: boolean;
}

export default function RoomsPage() {
  const { t } = useTranslation();
  const [isLoading, setIsLoading] = useState(true);
  const [salles, setSalles] = useState<Salle[]>([]);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingSalle, setEditingSalle] = useState<Salle | null>(null);
  const [formData, setFormData] = useState({
    nom: '',
    type: 'consultation',
    description: '',
  });

  useEffect(() => {
    loadSalles();
  }, []);

  const loadSalles = async () => {
    try {
      setIsLoading(true);
      const res = await api.get('/salles');
      setSalles(res.data);
    } catch (err) {
      toast.error(t('rooms.loadError'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleOpenDialog = (salle?: Salle) => {
    if (salle) {
      setEditingSalle(salle);
      setFormData({
        nom: salle.nom,
        type: salle.type,
        description: salle.description || '',
      });
    } else {
      setEditingSalle(null);
      setFormData({
        nom: '',
        type: 'consultation',
        description: '',
      });
    }
    setIsDialogOpen(true);
  };

  const handleSave = async () => {
    try {
      if (editingSalle) {
        await api.patch(`/salles/${editingSalle.id}`, formData);
        toast.success(t('rooms.updated'));
      } else {
        await api.post('/salles', formData);
        toast.success(t('rooms.created'));
      }
      setIsDialogOpen(false);
      loadSalles();
    } catch (err) {
      toast.error(t('rooms.saveError'));
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm(t('rooms.confirmDelete'))) return;
    try {
      await api.delete(`/salles/${id}`);
      toast.success(t('rooms.deleted'));
      loadSalles();
    } catch (err) {
      toast.error(t('rooms.deleteError'));
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold">{t('rooms.title')}</h1>
            <p className="text-muted-foreground mt-1">{t('rooms.subtitle')}</p>
          </div>
          <Button onClick={() => handleOpenDialog()}>
            <Plus className="w-4 h-4 mr-2" /> {t('rooms.newRoom')}
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
                    <TableHead>{t('rooms.nom')}</TableHead>
                    <TableHead>{t('rooms.type')}</TableHead>
                    <TableHead>{t('rooms.description')}</TableHead>
                    <TableHead>{t('rooms.status')}</TableHead>
                    <TableHead className="text-right">{t('rooms.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {salles.map((salle) => (
                    <TableRow key={salle.id}>
                      <TableCell className="font-medium">{salle.nom}</TableCell>
                      <TableCell className="capitalize">{salle.type}</TableCell>
                      <TableCell>{salle.description || '-'}</TableCell>
                      <TableCell>
                        <span className={`px-2 py-1 rounded-full text-xs ${salle.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                          {salle.is_active ? t('rooms.active') : t('rooms.inactive')}
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button variant="ghost" size="sm" onClick={() => handleOpenDialog(salle)}>
                            <Edit2 className="w-4 h-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleDelete(salle.id)} className="text-red-600">
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                  {salles.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                        {t('rooms.empty')}
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingSalle ? t('rooms.editTitle') : t('rooms.newTitle')}</DialogTitle>
            <DialogDescription>{t('rooms.dialogDesc')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="nom">{t('rooms.roomName')}</Label>
              <Input id="nom" value={formData.nom} onChange={(e) => setFormData({...formData, nom: e.target.value})} placeholder={t('rooms.roomNamePh')} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="type">{t('rooms.spaceType')}</Label>
              <select 
                id="type" 
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                value={formData.type} 
                onChange={(e) => setFormData({...formData, type: e.target.value})}
              >
                <option value="consultation">{t('rooms.typeConsultation')}</option>
                <option value="operation">{t('rooms.typeOperation')}</option>
                <option value="soins">{t('rooms.typeSoins')}</option>
                <option value="repos">{t('rooms.typeRepos')}</option>
              </select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="description">{t('rooms.description')}</Label>
              <Input id="description" value={formData.description} onChange={(e) => setFormData({...formData, description: e.target.value})} placeholder={t('rooms.descriptionPh')} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDialogOpen(false)}>{t('rooms.cancel')}</Button>
            <Button onClick={handleSave}>{t('rooms.save')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </DashboardLayout>
  );
}
