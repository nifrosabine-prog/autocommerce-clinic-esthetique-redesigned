import { useState } from 'react';
import { MessageCircle, Send, X } from 'lucide-react';
import { publicApi } from '@/lib/api';

type ChatMessage = { from: 'lina' | 'visitor'; text: string; urgent?: boolean; action?: { label: string; href: string } };

function WhatsAppLogo({ size = 22 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" fill="currentColor"><path d="M20.52 3.48A11.82 11.82 0 0 0 12.08 0C5.55 0 .24 5.3.24 11.83c0 2.08.54 4.12 1.56 5.92L.14 24l6.4-1.63a11.82 11.82 0 0 0 5.54 1.37h.01c6.53 0 11.83-5.31 11.83-11.84 0-3.16-1.23-6.13-3.4-8.42ZM12.09 21.7h-.01a9.82 9.82 0 0 1-5-1.37l-.36-.22-3.8.97 1.01-3.7-.23-.38a9.82 9.82 0 1 1 8.39 4.7Zm5.39-7.36c-.3-.15-1.77-.87-2.04-.97-.27-.1-.47-.15-.67.15-.2.3-.77.97-.94 1.17-.17.2-.35.22-.65.07-.3-.15-1.27-.47-2.42-1.5-.9-.8-1.5-1.78-1.68-2.08-.17-.3-.02-.46.13-.61.14-.14.3-.35.45-.52.15-.17.2-.3.3-.5.1-.2.05-.37-.03-.52-.07-.15-.67-1.62-.92-2.22-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.08-.79.37-.27.3-1.04 1.02-1.04 2.5s1.07 2.9 1.22 3.1c.15.2 2.1 3.2 5.1 4.49.71.31 1.27.49 1.7.63.72.23 1.38.2 1.9.12.58-.09 1.77-.72 2.02-1.42.25-.7.25-1.3.17-1.42-.07-.12-.27-.2-.57-.35Z" /></svg>;
}

export default function LinaChatWidget({ whatsapp }: { whatsapp: string }) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { from: 'lina', text: 'Bonjour, je suis Lina, l’assistante virtuelle de MBA Clinic. Je peux vous renseigner sur les horaires, l’adresse, les actes publiés et la réservation.' },
  ]);

  const send = async () => {
    const message = value.trim();
    if (!message || loading) return;
    setValue('');
    setMessages((current) => [...current, { from: 'visitor', text: message }]);
    setLoading(true);
    try {
      const response = await publicApi.chat(message);
      const reservation = response.data.actions?.find((action) => action.type === 'reservation');
      const action = reservation ? { label: reservation.label, href: reservation.href } : undefined;
      setMessages((current) => [...current, { from: 'lina' as const, text: response.data.reponse, urgent: response.data.escalade, action }].slice(-8));
    } catch {
      setMessages((current) => [...current, { from: 'lina', text: 'Le chat est momentanément indisponible. Contactez la clinique ou utilisez le bouton WhatsApp.' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end gap-3" aria-live="polite">
      {open && (
        <section className="w-[min(92vw,370px)] overflow-hidden rounded-2xl border border-[#172126]/10 bg-[#fbfaf7] shadow-2xl" aria-label="Chat Lina">
          <header className="flex items-center justify-between bg-[#172126] px-4 py-3 text-white">
            <div className="flex items-center gap-3"><span className="grid h-9 w-9 items-center justify-center rounded-full bg-[#25D366] text-white"><WhatsAppLogo size={21} /></span><div><p className="font-semibold">Lina</p><p className="text-xs text-white/65">Assistante MBA Clinic</p></div></div>
            <button type="button" onClick={() => setOpen(false)} aria-label="Fermer le chat"><X size={20} /></button>
          </header>
          <div className="max-h-80 space-y-3 overflow-y-auto p-4">
            {messages.map((item, index) => <div key={`${item.from}-${index}`} className={`max-w-[88%] rounded-xl px-3 py-2 text-sm ${item.from === 'visitor' ? 'ml-auto bg-[#172126] text-white' : 'bg-[#f0ede5] text-[#172126]'} ${item.urgent ? 'border border-red-300' : ''}`}><div>{item.text}</div>{item.action && <a href={item.action.href} onClick={() => setOpen(false)} className="mt-2 inline-block font-semibold text-[#b0884b] underline">{item.action.label}</a>}</div>)}
            {loading && <div className="text-xs text-[#172126]/55">Lina prépare une réponse…</div>}
          </div>
          <div className="border-t border-[#172126]/10 p-3"><p className="mb-2 text-[11px] leading-4 text-[#172126]/55">Assistante virtuelle, pas un médecin. Ne partagez pas d’informations médicales sensibles dans ce chat.</p><div className="flex gap-2"><input value={value} onChange={(event) => setValue(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void send(); }} placeholder="Votre question…" maxLength={2000} className="min-w-0 flex-1 rounded-lg border border-[#172126]/15 bg-white px-3 py-2 text-sm outline-none focus:border-[#b0884b]" aria-label="Votre question" /><button type="button" onClick={() => void send()} disabled={loading || !value.trim()} className="rounded-lg bg-[#b0884b] px-3 text-white disabled:opacity-50" aria-label="Envoyer"><Send size={17} /></button></div></div>
        </section>
      )}
      <div className="flex gap-2"><a href={`https://wa.me/${whatsapp.replace(/[^0-9]/g, '')}`} target="_blank" rel="noreferrer" className="grid h-12 w-12 place-items-center rounded-full bg-[#25D366] text-white shadow-lg" aria-label="Ouvrir WhatsApp" title="Contacter MBA Clinic sur WhatsApp"><WhatsAppLogo size={27} /></a><button type="button" onClick={() => setOpen((current) => !current)} className="flex items-center gap-2 rounded-full bg-[#172126] px-4 py-3 text-sm font-semibold text-white shadow-lg" aria-expanded={open}><MessageCircle size={19} />{open ? 'Fermer' : 'Parler à Lina'}</button></div>
    </div>
  );
}
