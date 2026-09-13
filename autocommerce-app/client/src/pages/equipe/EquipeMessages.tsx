import { useEffect, useState } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Spinner } from '@/components/ui/spinner';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Mail, MailOpen, Send, Trash2, Plus, Eye } from 'lucide-react';
import { Checkbox } from '@/components/ui/checkbox';
import { equipeApi, EquipeMessage, EquipeMember } from '@/lib/api';

// ── Types ────────────────────────────────────────────────────


// ── Composant principal ──────────────────────────────────────

export default function EquipeMessages() {
  const [tab, setTab] = useState<'inbox' | 'sent'>('inbox');
  const [messages, setMessages] = useState<EquipeMessage[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Composition
  const [composeOpen, setComposeOpen] = useState(false);
  const [selectedDestinataireIds, setSelectedDestinataireIds] = useState<number[]>([]);
  const [recipientSearch, setRecipientSearch] = useState('');
  const [sujet, setSujet] = useState('');
  const [contenu, setContent] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [idempotencyKey, setIdempotencyKey] = useState('');
  const [utilisateurs, setUtilisateurs] = useState<EquipeMember[]>([]);

  // Lecture
  const [readOpen, setReadOpen] = useState(false);
  const [selectedMessage, setSelectedMessage] = useState<EquipeMessage | null>(null);

  // Suppression
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);

  // ── Chargement ────────────────────────────────────────────

  const loadMessages = async () => {
    setIsLoading(true);
    setError(null);
    try {
      if (tab === 'inbox') {
        const res = await equipeApi.getInbox();
        setMessages(res.data);
      } else {
        const res = await equipeApi.getSent();
        setMessages(res.data);
      }
    } catch {
      setError('Impossible de charger les messages.');
      toast.error('Erreur lors du chargement des messages');
    } finally {
      setIsLoading(false);
    }
  };

  const loadUnread = async () => {
    try {
      const res = await equipeApi.getUnreadCount();
      setUnreadCount(res.data.unread_count);
    } catch {
      // Silencieux — pas bloquant
    }
  };

  const loadUtilisateurs = async () => {
    try {
      const response = await equipeApi.listMembers();
      setUtilisateurs(response.data);
    } catch {
      setUtilisateurs([]);
      toast.error('Impossible de charger les membres de l’équipe');
    }
  };

  useEffect(() => {
    loadMessages();
    loadUnread();
  }, [tab]);

  useEffect(() => {
    loadUtilisateurs();
  }, []);

  // ── Handlers ──────────────────────────────────────────────

  const handleSend = async () => {
    if (selectedDestinataireIds.length === 0 || !sujet.trim() || !contenu.trim()) {
      toast.error('Tous les champs sont obligatoires');
      return;
    }
    setIsSending(true);
    try {
      await equipeApi.send({
        destinataire_ids: selectedDestinataireIds,
        idempotency_key: idempotencyKey || (window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`),
        sujet: sujet.trim(),
        contenu: contenu.trim(),
      });
      toast.success('Message envoyé avec succès');
      setComposeOpen(false);
      setSelectedDestinataireIds([]);
      setRecipientSearch('');
      setIdempotencyKey('');
      setSujet('');
      setContent('');
      loadMessages();
      loadUnread();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Erreur lors de l\'envoi');
    } finally {
      setIsSending(false);
    }
  };

  const handleRead = async (msg: EquipeMessage) => {
    setSelectedMessage(msg);
    setReadOpen(true);
    // Marquer comme lu si c'est un message reçu non lu
    if (!msg.lu && tab === 'inbox') {
      try {
        await equipeApi.markRead(msg.id);
        msg.lu = true;
        msg.lu_a = new Date().toISOString();
        loadUnread();
      } catch {
        // Silencieux
      }
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await equipeApi.delete(deleteId);
      toast.success('Message supprimé');
      setDeleteOpen(false);
      setDeleteId(null);
      setReadOpen(false);
      setSelectedMessage(null);
      loadMessages();
      loadUnread();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Erreur lors de la suppression');
    }
  };

  const handleOpenDelete = (id: number) => {
    setDeleteId(id);
    setDeleteOpen(true);
  };

  // ── Rendu ─────────────────────────────────────────────────

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Messagerie Équipe</h1>
            <p className="text-muted-foreground">
              Communication interne entre les membres de la clinique
            </p>
          </div>
          <Button onClick={() => { void loadUtilisateurs(); setIdempotencyKey(window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`); setComposeOpen(true); }}>
            <Plus className="w-4 h-4 mr-2" />
            Nouveau message
          </Button>
        </div>

        {/* Tabs */}
        <Tabs value={tab} onValueChange={(v) => setTab(v as 'inbox' | 'sent')}>
          <TabsList>
            <TabsTrigger value="inbox" className="relative">
              {unreadCount > 0 ? (
                <>
                  <Mail className="w-4 h-4 mr-2" />
                  Boîte de réception
                  <Badge variant="destructive" className="ml-2 h-5 min-w-[20px] px-1">
                    {unreadCount}
                  </Badge>
                </>
              ) : (
                <>
                  <MailOpen className="w-4 h-4 mr-2" />
                  Boîte de réception
                </>
              )}
            </TabsTrigger>
            <TabsTrigger value="sent">
              <Send className="w-4 h-4 mr-2" />
              Envoyés
            </TabsTrigger>
          </TabsList>

          <TabsContent value={tab} className="mt-4">
            <Card>
              <CardContent className="p-0">
                {isLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Spinner className="size-8" />
                  </div>
                ) : error ? (
                  <div className="flex items-center justify-center py-12 text-muted-foreground">
                    {error}
                  </div>
                ) : messages.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                    <Mail className="w-12 h-12 mb-4 opacity-30" />
                    <p>Aucun message {tab === 'inbox' ? 'reçu' : 'envoyé'}</p>
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        {tab === 'inbox' ? (
                          <>
                            <TableHead>De</TableHead>
                            <TableHead>Sujet</TableHead>
                            <TableHead>Date</TableHead>
                            <TableHead className="w-[100px]">Actions</TableHead>
                          </>
                        ) : (
                          <>
                            <TableHead>À</TableHead>
                            <TableHead>Sujet</TableHead>
                            <TableHead>Date</TableHead>
                            <TableHead>Statut</TableHead>
                            <TableHead className="w-[100px]">Actions</TableHead>
                          </>
                        )}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {messages.map((msg) => (
                        <TableRow
                          key={msg.id}
                          className={!msg.lu && tab === 'inbox' ? 'bg-blue-50 font-medium' : ''}
                        >
                          {tab === 'inbox' ? (
                            <>
                              <TableCell>
                                <div className="flex items-center gap-2">
                                  {!msg.lu && (
                                    <div className="w-2 h-2 rounded-full bg-blue-500 shrink-0" />
                                  )}
                                  <span>
                                    {msg.expediteur_prenom} {msg.expediteur_nom}
                                  </span>
                                </div>
                              </TableCell>
                              <TableCell className="max-w-[300px] truncate">
                                {msg.sujet}
                              </TableCell>
                              <TableCell className="text-muted-foreground text-sm">
                                {formatDate(msg.cree_a)}
                              </TableCell>
                              <TableCell>
                                <div className="flex gap-1">
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => handleRead(msg)}
                                    title="Lire"
                                  >
                                    <Eye className="w-4 h-4" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => handleOpenDelete(msg.id)}
                                    title="Supprimer"
                                  >
                                    <Trash2 className="w-4 h-4 text-red-500" />
                                  </Button>
                                </div>
                              </TableCell>
                            </>
                          ) : (
                            <>
                              <TableCell>
                                {msg.destinataire_prenom} {msg.destinataire_nom}
                              </TableCell>
                              <TableCell className="max-w-[300px] truncate">
                                {msg.sujet}
                              </TableCell>
                              <TableCell className="text-muted-foreground text-sm">
                                {formatDate(msg.cree_a)}
                              </TableCell>
                              <TableCell>
                                <Badge variant={msg.lu ? 'default' : 'secondary'}>
                                  {msg.lu ? 'Lu' : 'Non lu'}
                                </Badge>
                              </TableCell>
                              <TableCell>
                                <div className="flex gap-1">
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => handleRead(msg)}
                                    title="Voir"
                                  >
                                    <Eye className="w-4 h-4" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => handleOpenDelete(msg.id)}
                                    title="Supprimer"
                                  >
                                    <Trash2 className="w-4 h-4 text-red-500" />
                                  </Button>
                                </div>
                              </TableCell>
                            </>
                          )}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      {/* ── Dialog : Composer ─────────────────────────────── */}
      <Dialog open={composeOpen} onOpenChange={setComposeOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Nouveau message</DialogTitle>
                          <DialogDescription>
              Envoyez un message à un ou plusieurs membres actifs de l'équipe.
            </DialogDescription>

          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="destinataire-search">Destinataires ({selectedDestinataireIds.length})</Label>
                <div className="flex gap-2 text-xs">
                  <button type="button" className="text-primary hover:underline" onClick={() => setSelectedDestinataireIds(utilisateurs.map((member) => member.id))}>Toute l’équipe</button>
                  <button type="button" className="text-muted-foreground hover:underline" onClick={() => setSelectedDestinataireIds([])}>Tout désélectionner</button>
                </div>
              </div>
              <Input
                id="destinataire-search"
                placeholder="Rechercher un membre..."
                value={recipientSearch}
                onChange={(e) => setRecipientSearch(e.target.value)}
              />
              <div className="max-h-40 overflow-y-auto rounded-md border p-2 space-y-1">
                {utilisateurs
                  .filter((member) => `${member.prenom} ${member.nom} ${member.role}`.toLowerCase().includes(recipientSearch.toLowerCase()))
                  .map((member) => (
                    <label key={member.id} className="flex items-center gap-2 rounded px-2 py-1.5 hover:bg-muted cursor-pointer">
                      <Checkbox
                        checked={selectedDestinataireIds.includes(member.id)}
                        onCheckedChange={(checked) => setSelectedDestinataireIds((current) => checked ? Array.from(new Set([...current, member.id])) : current.filter((id) => id !== member.id))}
                      />
                      <span className="text-sm">{member.prenom} {member.nom} — {member.role} ({member.email})</span>
                    </label>
                  ))}
                {utilisateurs.length === 0 && <p className="text-xs text-muted-foreground px-2 py-1">Aucun autre membre actif disponible.</p>}
              </div>
              {selectedDestinataireIds.length > 0 && <p className="text-xs text-muted-foreground">Sélectionnés : {utilisateurs.filter((member) => selectedDestinataireIds.includes(member.id)).map((member) => `${member.prenom} ${member.nom}`).join(', ')}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="sujet">Sujet</Label>
              <Input
                id="sujet"
                placeholder="Objet du message"
                value={sujet}
                onChange={(e) => setSujet(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="contenu">Message</Label>
              <Textarea
                id="contenu"
                placeholder="Rédigez votre message..."
                rows={6}
                value={contenu}
                onChange={(e) => setContent(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setComposeOpen(false)}>
              Annuler
            </Button>
            <Button onClick={handleSend} disabled={isSending || selectedDestinataireIds.length === 0}>
              {isSending ? <Spinner className="w-4 h-4 mr-2" /> : <Send className="w-4 h-4 mr-2" />}
              Envoyer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog : Lire un message ──────────────────────── */}
      <Dialog open={readOpen} onOpenChange={setReadOpen}>
        <DialogContent className="max-w-lg">
          {selectedMessage && (
            <>
              <DialogHeader>
                <DialogTitle>{selectedMessage.sujet}</DialogTitle>
                <DialogDescription>
                  {tab === 'inbox' ? (
                    <>
                      De : <strong>{selectedMessage.expediteur_prenom} {selectedMessage.expediteur_nom}</strong>
                    </>
                  ) : (
                    <>
                      À : <strong>{selectedMessage.destinataire_prenom} {selectedMessage.destinataire_nom}</strong>
                    </>
                  )}
                  {' '}&mdash; {formatDate(selectedMessage.cree_a)}
                  {selectedMessage.lu && selectedMessage.lu_a && (
                    <>
                      <br />
                      <span className="text-xs text-muted-foreground">
                        Lu le {formatDate(selectedMessage.lu_a)}
                      </span>
                    </>
                  )}
                </DialogDescription>
              </DialogHeader>
              <div className="py-4">
                <p className="whitespace-pre-wrap text-sm">{selectedMessage.contenu}</p>
              </div>
              <DialogFooter>
                <Button
                  variant="destructive"
                  onClick={() => {
                    setReadOpen(false);
                    handleOpenDelete(selectedMessage.id);
                  }}
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  Supprimer
                </Button>
                <Button onClick={() => setReadOpen(false)}>Fermer</Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Alert : Confirmer suppression ─────────────────── */}
      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer ce message ?</AlertDialogTitle>
            <AlertDialogDescription>
              Cette action est irréversible. Le message sera définitivement supprimé.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-red-600 hover:bg-red-700">
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </DashboardLayout>
  );
}
