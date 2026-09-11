import { render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Dashboard from '@/pages/dashboard/Dashboard';
import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';

vi.mock('@/contexts/AuthContext', () => ({ useAuth: vi.fn() }));
vi.mock('@/components/layout/DashboardLayout', () => ({ DashboardLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock('@/components/dashboard/PointageWidget', () => ({ PointageWidget: () => <div>Pointage</div> }));

describe('Dashboard — file opérationnelle', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.mocked(useAuth).mockReturnValue({ user: { prenom: 'Ada', nom: 'Martin', role: 'directrice' } } as ReturnType<typeof useAuth>);
    vi.spyOn(api, 'get').mockImplementation((url: string) => {
      if (url.startsWith('/agenda?')) return Promise.resolve({ data: [{ id: 1, patient_id: 8, patient_nom: 'Patient Test', praticien_nom: 'Dr Martin', acte_nom: 'Consultation', date_heure_debut: '2030-01-20T09:00:00Z', consentement_manquant: true }] }) as never;
      if (url === '/booking-requests?statut=pending') return Promise.resolve({ data: [{ id: 1 }, { id: 2 }] }) as never;
      if (url === '/callback-leads?statut=pending') return Promise.resolve({ data: [{ id: 1 }] }) as never;
      if (url === '/clinical-ops/suivis?statut=a_faire&horizon_days=7') return Promise.resolve({ data: [{ id: 1 }, { id: 2 }, { id: 3 }] }) as never;
      if (url === '/factures') return Promise.resolve({ data: [{ statut: 'envoyee' }, { statut: 'payee' }, { statut: 'partiellement_payee' }] }) as never;
      if (url === '/injectables/stock') return Promise.resolve({ data: { total_alertes: 2 } }) as never;
      if (url === '/social/analytics') return Promise.resolve({ data: { messages: { whatsapp: { nouveau: 3 }, instagram: { nouveau: 1 } } } }) as never;
      if (url === '/factures/audit-logs') return Promise.resolve({ data: [{ id: 77, entite_type: 'facture', action: 'Facture envoyée', modifie_par_nom: 'Lina Durand', created_at: '2030-01-20T09:00:00Z' }] }) as never;
      if (url === '/workflows/tasks/mine') return Promise.resolve({ data: { data: [{ id: 31, titre: 'Vérifier le suivi post-acte', priorite: 'medium', statut: 'a_faire' }] } }) as never;
      return Promise.resolve({ data: [] }) as never;
    });
  });

  it('affiche une file opérationnelle basée sur les rappels persistés', async () => {
    render(<Dashboard />);
    expect(await screen.findByText('Les prochaines consultations')).toBeInTheDocument();
    expect(screen.getByText('Demandes de rendez-vous en attente')).toBeInTheDocument();
    expect(screen.getByText('Demandes de rappel à rappeler')).toBeInTheDocument();
    expect(screen.getByText('Consentements à signer aujourd’hui')).toBeInTheDocument();
    expect(screen.getByText('Suivis post-acte à réaliser sous 7 jours')).toBeInTheDocument();
    expect(screen.getByText('Tâches qui vous sont attribuées')).toBeInTheDocument();
    expect(screen.getByText(/Vérifier le suivi post-acte/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByText('3').length).toBeGreaterThan(0));
  });

  it('transforme un consentement manquant de l’agenda en rappel opérationnel visible', async () => {
    render(<Dashboard />);
    expect(await screen.findByText('Consentements à signer')).toBeInTheDocument();
    expect(screen.getByText('Consentements à signer aujourd’hui')).toBeInTheDocument();
    expect(screen.getByText('Consentement requis')).toBeInTheDocument();
  });

  it('affiche des KPI calculés et une activité récente à partir des modules disponibles', async () => {
    render(<Dashboard />);

    const appointmentsCard = (await screen.findByText("Rendez-vous aujourd'hui")).closest('a');
    const invoicesCard = screen.getByText('Factures à suivre').closest('a');
    const messagesCard = screen.getByText('Messages à traiter').closest('a');
    expect(appointmentsCard).not.toBeNull();
    expect(invoicesCard).not.toBeNull();
    expect(messagesCard).not.toBeNull();
    expect(within(appointmentsCard as HTMLElement).getByText('1')).toBeInTheDocument();
    expect(within(invoicesCard as HTMLElement).getByText('2')).toBeInTheDocument();
    expect(within(messagesCard as HTMLElement).getByText('4')).toBeInTheDocument();
    expect(screen.getByText('Facture envoyée · facture')).toBeInTheDocument();
    expect(screen.getByText('Lina Durand')).toBeInTheDocument();
    expect(screen.queryByText(/Aucun événement récent accessible/i)).not.toBeInTheDocument();
  });

  it('rend les états vides sans inventer de priorité ou d’activité', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [] } as never);
    render(<Dashboard />);

    expect(await screen.findByText('Aucun rendez-vous planifié aujourd’hui.')).toBeInTheDocument();
    expect(screen.getByText('Aucune priorité urgente détectée dans les données actuellement disponibles.')).toBeInTheDocument();
    expect(screen.getByText(/Aucun événement récent accessible pour votre rôle/i)).toBeInTheDocument();
  });

  it('signale une indisponibilité de données sans masquer les autres cartes', async () => {
    vi.mocked(api.get).mockImplementation(() => Promise.reject(new Error('service indisponible')) as never);
    render(<Dashboard />);

    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(9));
    expect(await screen.findByText(/Certaines données du tableau de bord sont momentanément indisponibles/i)).toBeInTheDocument();
    expect(screen.getByText("Rendez-vous aujourd'hui")).toBeInTheDocument();
  });

  it('ne présente pas une restriction RBAC attendue comme une indisponibilité', async () => {
    vi.mocked(api.get).mockImplementation(() => Promise.reject({ response: { status: 403 } }) as never);
    render(<Dashboard />);

    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(9));
    expect(screen.queryByText(/Certaines données du tableau de bord sont momentanément indisponibles/i)).not.toBeInTheDocument();
    expect(screen.getByText("Rendez-vous aujourd'hui")).toBeInTheDocument();
  });
});
