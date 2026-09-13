import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { api } from '@/lib/api';
import { toast } from 'sonner';
import { Spinner } from '@/components/ui/spinner';

interface PublicPost { id: number; titre: string; description?: string | null }

export default function PublicApplication() {
  const [posts, setPosts] = useState<PublicPost[]>([]);
  const [posteId, setPosteId] = useState('');
  const [nom, setNom] = useState('');
  const [email, setEmail] = useState('');
  const [telephone, setTelephone] = useState('');
  const [cv, setCv] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [sent, setSent] = useState(false);

  useEffect(() => {
    api.get('/public/recrutement/postes').then((response) => setPosts(Array.isArray(response.data) ? response.data : []))
      .catch(() => toast.error('Les postes ouverts sont momentanément indisponibles'));
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!posteId || !nom.trim() || !email.trim()) return toast.error('Poste, nom et e-mail sont obligatoires');
    setSaving(true);
    try {
      const form = new FormData();
      form.append('poste_id', posteId); form.append('nom_candidat', nom.trim());
      form.append('email', email.trim()); if (telephone.trim()) form.append('telephone', telephone.trim());
      if (cv) form.append('cv', cv);
      await api.post('/public/recrutement', form, { headers: { 'Content-Type': 'multipart/form-data' } });
      setSent(true); toast.success('Votre candidature a été envoyée');
    } catch (error: any) { toast.error(error.response?.data?.detail || 'Impossible d’envoyer la candidature'); }
    finally { setSaving(false); }
  };

  if (sent) return <main className="min-h-screen bg-muted/30 grid place-items-center p-6"><Card className="w-full max-w-xl"><CardContent className="p-8 text-center"><h1 className="text-2xl font-bold">Candidature reçue</h1><p className="mt-3 text-muted-foreground">Merci. L’équipe de la clinique examinera votre dossier et reviendra vers vous si votre profil correspond au poste.</p></CardContent></Card></main>;
  return <main className="min-h-screen bg-muted/30 p-6"><Card className="mx-auto mt-10 max-w-2xl"><CardHeader><CardTitle>Rejoindre notre équipe</CardTitle><p className="text-sm text-muted-foreground">Consultez les postes ouverts et transmettez votre candidature à la clinique.</p></CardHeader><CardContent><form onSubmit={submit} className="space-y-5"><div><Label htmlFor="application-post">Poste souhaité *</Label><select id="application-post" className="mt-1 h-10 w-full rounded-md border bg-background px-3 text-sm" value={posteId} onChange={(event) => setPosteId(event.target.value)}><option value="">Sélectionner un poste</option>{posts.map((post) => <option key={post.id} value={post.id}>{post.titre}</option>)}</select>{posts.find((post) => String(post.id) === posteId)?.description && <p className="mt-1 text-xs text-muted-foreground">{posts.find((post) => String(post.id) === posteId)?.description}</p>}</div><div><Label htmlFor="application-name">Nom complet *</Label><Input id="application-name" value={nom} onChange={(event) => setNom(event.target.value)} /></div><div className="grid gap-4 md:grid-cols-2"><div><Label htmlFor="application-email">E-mail *</Label><Input id="application-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} /></div><div><Label htmlFor="application-phone">Téléphone</Label><Input id="application-phone" value={telephone} onChange={(event) => setTelephone(event.target.value)} /></div></div><div><Label htmlFor="application-cv">CV (PDF, DOC ou DOCX)</Label><Input id="application-cv" type="file" accept=".pdf,.doc,.docx" onChange={(event) => setCv(event.target.files?.[0] || null)} /></div><Button type="submit" disabled={saving || posts.length === 0}>{saving ? <Spinner className="h-4 w-4" /> : 'Envoyer ma candidature'}</Button></form></CardContent></Card></main>;
}
