import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
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
  const { t, i18n } = useTranslation();
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
      setError(t('equipe.loadError'));
      toast.error(t('equipe.loadErrorToast'));
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
      toast.error(t('equipe.membersError'));
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
      toast.error(t('equipe.fieldsRequired'));
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
      toast.success(t('equipe.sent'));
      setComposeOpen(false);
      setSelectedDestinataireIds([]);
      setRecipientSearch('');
      setIdempotencyKey('');
      setSujet('');
      setContent('');
      loadMessages();
      loadUnread();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t('equipe.sendError'));
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
      toast.success(t('equipe.deleted'));
      setDeleteOpen(false);
      setDeleteId(null);
      setReadOpen(false);
      setSelectedMessage(null);
      loadMessages();
      loadUnread();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t('equipe.deleteError'));
    }
  };

  const handleOpenDelete = (id: number) => {
    setDeleteId(id);
    setDeleteOpen(true);
  };

  // ── Rendu ─────────────────────────────────────────────────

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleString(i18n.language, {
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
            <h1 className="text-2xl font-bold tracking-tight">{t('equipe.title')}</h1>
            <p className="text-muted-foreground">
              {t('equipe.subtitle')}
            </p>
          </div>
          <Button onClick={() => { void loadUtilisateurs(); setIdempotencyKey(window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`); setComposeOpen(true); }}>
            <Plus className="w-4 h-4 mr-2" />
            {t('equipe.newMessage')}
          </Button>
        </div>

        {/* Tabs */}
        <Tabs value={tab} onValueChange={(v) => setTab(v as 'inbox' | 'sent')}>
          <TabsList>
            <TabsTrigger value="inbox" className="relative">
              {unreadCount > 0 ? (
                <>
                  <Mail className="w-4 h-4 mr-2" />
                  {t('equipe.inbox')}
                  <Badge variant="destructive" className="ml-2 h-5 min-w-[20px] px-1">
                    {unreadCount}
                  </Badge>
                </>
              ) : (
                <>
                  <MailOpen className="w-4 h-4 mr-2" />
                  {t('equipe.inbox')}
                </>
              )}
            </TabsTrigger>
            <TabsTrigger value="sent">
              <Send className="w-4 h-4 mr-2" />
              {t('equipe.sentTab')}
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
                    <p>{t(tab === 'inbox' ? 'equipe.noMessageReceived' : 'equipe.noMessageSent')}</p>
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        {tab === 'inbox' ? (
                          <>
                            <TableHead>{t('equipe.from')}</TableHead>
                            <TableHead>{t('equipe.subject')}</TableHead>
                            <TableHead>{t('equipe.date')}</TableHead>
                            <TableHead className="w-[100px]">{t('equipe.actions')}</TableHead>
                          </>
                        ) : (
                          <>
                            <TableHead>{t('equipe.to')}</TableHead>
                            <TableHead>{t('equipe.subject')}</TableHead>
                            <TableHead>{t('equipe.date')}</TableHead>
                            <TableHead>{t('equipe.status')}</TableHead>
                            <TableHead className="w-[100px]">{t('equipe.actions')}</TableHead>
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
                                    title={t('equipe.read')}
                                  >
                                    <Eye className="w-4 h-4" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => handleOpenDelete(msg.id)}
                                    title={t('equipe.delete')}
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
                                  {msg.lu ? t('equipe.readBadge') : t('equipe.unreadBadge')}
                                </Badge>
                              </TableCell>
                              <TableCell>
                                <div className="flex gap-1">
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => handleRead(msg)}
                                    title={t('equipe.view')}
                                  >
                                    <Eye className="w-4 h-4" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => handleOpenDelete(msg.id)}
                                    title={t('equipe.delete')}
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
            <DialogTitle>{t('equipe.newMessage')}</DialogTitle>
                          <DialogDescription>
              {t('equipe.composeDesc')}
            </DialogDescription>

          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="destinataire-search">{t('equipe.recipients', { total: selectedDestinataireIds.length })}</Label>
                <div className="flex gap-2 text-xs">
                  <button type="button" className="text-primary hover:underline" onClick={() => setSelectedDestinataireIds(utilisateurs.map((member) => member.id))}>{t('equipe.wholeTeam')}</button>
                  <button type="button" className="text-muted-foreground hover:underline" onClick={() => setSelectedDestinataireIds([])}>{t('equipe.deselectAll')}</button>
                </div>
              </div>
              <Input
                id="destinataire-search"
                placeholder={t('equipe.searchMember')}
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
                {utilisateurs.length === 0 && <p className="text-xs text-muted-foreground px-2 py-1">{t('equipe.noOtherMember')}</p>}
              </div>
              {selectedDestinataireIds.length > 0 && <p className="text-xs text-muted-foreground">{t('equipe.selected')} : {utilisateurs.filter((member) => selectedDestinataireIds.includes(member.id)).map((member) => `${member.prenom} ${member.nom}`).join(', ')}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="sujet">{t('equipe.subjectLabel')}</Label>
              <Input
                id="sujet"
                placeholder={t('equipe.subjectPlaceholder')}
                value={sujet}
                onChange={(e) => setSujet(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="contenu">{t('equipe.messageLabel')}</Label>
              <Textarea
                id="contenu"
                placeholder={t('equipe.messagePlaceholder')}
                rows={6}
                value={contenu}
                onChange={(e) => setContent(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setComposeOpen(false)}>
              {t('equipe.cancel')}
            </Button>
            <Button onClick={handleSend} disabled={isSending || selectedDestinataireIds.length === 0}>
              {isSending ? <Spinner className="w-4 h-4 mr-2" /> : <Send className="w-4 h-4 mr-2" />}
              {t('equipe.send')}
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
                      {t('equipe.fromLabel')} <strong>{selectedMessage.expediteur_prenom} {selectedMessage.expediteur_nom}</strong>
                    </>
                  ) : (
                    <>
                      {t('equipe.toLabel')} <strong>{selectedMessage.destinataire_prenom} {selectedMessage.destinataire_nom}</strong>
                    </>
                  )}
                  {' '}&mdash; {formatDate(selectedMessage.cree_a)}
                  {selectedMessage.lu && selectedMessage.lu_a && (
                    <>
                      <br />
                      <span className="text-xs text-muted-foreground">
                        {t('equipe.readOn', { date: formatDate(selectedMessage.lu_a) })}
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
                  {t('equipe.deleteButton')}
                </Button>
                <Button onClick={() => setReadOpen(false)}>{t('equipe.close')}</Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Alert : Confirmer suppression ─────────────────── */}
      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('equipe.confirmDeleteTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('equipe.confirmDeleteDesc')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('equipe.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-red-600 hover:bg-red-700">
              {t('equipe.deleteButton')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </DashboardLayout>
  );
}
