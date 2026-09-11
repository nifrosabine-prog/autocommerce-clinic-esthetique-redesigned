import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import WorkflowEngine from "@/pages/workflow/WorkflowEngine";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

vi.mock("@/contexts/AuthContext", () => ({ useAuth: vi.fn() }));
vi.mock("@/components/layout/DashboardLayout", () => ({
  DashboardLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const mockedUseAuth = vi.mocked(useAuth);

const workflow = {
  id: 3,
  nom: "Rappel post-opératoire",
  description: "Relance après acte",
  trigger_type: "appointment_completed",
  enabled: true,
  status: "active",
  created_at: "2030-01-15T10:00:00Z",
};

const stats = {
  total_executions: 20,
  completed: 18,
  failed: 2,
  drafts_awaiting_approval: 1,
  success_rate: 90,
};

const auth = {
  user: { id: 1, email: "admin@clinic.test", nom: "Admin", prenom: "A", role: "admin" },
  isLoading: false,
  isAuthenticated: true,
  login: vi.fn(),
  verifyMfa: vi.fn(),
  logout: vi.fn(),
  refreshUser: vi.fn(),
};

describe("WorkflowEngine — états et actions", () => {
  beforeEach(() => {
    mockedUseAuth.mockReturnValue(auth);
    vi.spyOn(api, "get").mockImplementation((url: string) => {
      if (url === "/workflows/") return Promise.resolve({ data: { data: [workflow] } }) as never;
      return Promise.resolve({ data: { data: stats } }) as never;
    });
  });

  it("affiche les workflows et les statistiques après chargement", async () => {
    render(<WorkflowEngine />);

    expect(await screen.findByText("Rappel post-opératoire")).toBeInTheDocument();
    expect(screen.getByText("90.0%")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("charge un déclencheur depuis le catalogue métier API", async () => {
    vi.mocked(api.get).mockImplementation((url: string) => {
      if (url === "/workflows/") return Promise.resolve({ data: { data: [workflow] } }) as never;
      if (url === "/workflows/catalog") return Promise.resolve({ data: { data: {
        triggers: [{ key: "six_month_review", trigger_type: "event_based", event_type: "six_month_review", label: "Contrôle à six mois", description: "Revue clinique différée." }],
        actions: [{ value: "create_task", label: "Créer une tâche interne", description: "Visible dans la file de l’équipe.", tone: "teal" }],
        patient_segments: [{ value: "all", label: "Tous les patients éligibles" }],
        appointment_scopes: [{ value: "any", label: "Tout contexte de rendez-vous" }],
      } } }) as never;
      return Promise.resolve({ data: { data: stats } }) as never;
    });
    render(<WorkflowEngine />);
    await screen.findByText("Rappel post-opératoire");
    fireEvent.click(screen.getByRole("button", { name: "Nouveau scénario" }));
    expect(await screen.findByText("Contrôle à six mois")).toBeInTheDocument();
  });

  it("exécute un workflow puis recharge la liste", async () => {
    const postSpy = vi.spyOn(api, "post").mockResolvedValue({ data: { status: "queued" } } as never);
    render(<WorkflowEngine />);
    await screen.findByText("Rappel post-opératoire");
    fireEvent.click(screen.getByRole("button", { name: "Exécuter" }));

    await waitFor(() => expect(postSpy).toHaveBeenCalledWith("/workflows/3/execute"));
    expect(api.get).toHaveBeenCalledWith("/workflows/");
  });

  it("supprime seulement après confirmation utilisateur", async () => {
    const deleteSpy = vi.spyOn(api, "delete").mockResolvedValue({ data: {} } as never);
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<WorkflowEngine />);
    await screen.findByText("Rappel post-opératoire");
    fireEvent.click(screen.getByRole("button", { name: "Supprimer" }));
    expect(deleteSpy).not.toHaveBeenCalled();

    vi.mocked(window.confirm).mockReturnValue(true);
    fireEvent.click(screen.getByRole("button", { name: "Supprimer" }));
    await waitFor(() => expect(deleteSpy).toHaveBeenCalledWith("/workflows/3"));
  });

  it("affiche l’erreur API au lieu de présenter un workflow comme disponible", async () => {
    vi.spyOn(api, "get").mockRejectedValue(new Error("forbidden"));
    render(<WorkflowEngine />);

    expect(await screen.findByText("forbidden")).toBeInTheDocument();
  });

  it("propose un constructeur clinique sans exposer de champ JSON", async () => {
    render(<WorkflowEngine />);
    await screen.findByText("Rappel post-opératoire");
    fireEvent.click(screen.getByRole("button", { name: "Nouveau scénario" }));

    expect(await screen.findByText("1. Quand faut-il agir ?")).toBeInTheDocument();
    expect(screen.getByText("2. Pour quels patients ?")).toBeInTheDocument();
    expect(screen.getByText("3. Que doit faire l’équipe ?")).toBeInTheDocument();
    expect(screen.queryByText(/JSON/i)).not.toBeInTheDocument();
  });

  it("propose un scénario éditable à partir d’un besoin formulé en langage métier", async () => {
    render(<WorkflowEngine />);
    await screen.findByText("Rappel post-opératoire");
    fireEvent.click(screen.getByRole("button", { name: "Nouveau scénario" }));
    fireEvent.change(await screen.findByLabelText("Génération guidée par modèles métier"), { target: { value: "Rappeler un patient après une injection" } });
    fireEvent.click(screen.getByRole("button", { name: "Proposer une base" }));

    expect(screen.getByDisplayValue(/Scénario — Rappeler un patient après une injection/)).toBeInTheDocument();
    expect(screen.getByDisplayValue("Rappeler le patient")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Créer le brouillon à valider" })).toBeInTheDocument();
  });

  it.each([
    ["Relancer le consentement demain", "1", "Relancer la signature du consentement"],
    ["Rappeler un patient après injection dans 3 jours", "3", "Rappeler le patient"],
    ["Relancer un devis non accepté après 7 jours", "7", "Vérifier le suivi patient"],
    ["Contacter un patient inactif dans 14 jours", "14", "Vérifier le suivi patient"],
  ])("génère une base vérifiable pour « %s »", async (brief, delay, expectedTask) => {
    render(<WorkflowEngine />);
    await screen.findByText("Rappel post-opératoire");
    fireEvent.click(screen.getByRole("button", { name: "Nouveau scénario" }));
    fireEvent.change(await screen.findByLabelText("Génération guidée par modèles métier"), { target: { value: brief } });
    fireEvent.click(screen.getByRole("button", { name: "Proposer une base" }));
    expect(screen.getByDisplayValue(delay)).toBeInTheDocument();
    expect(screen.getByDisplayValue(expectedTask)).toBeInTheDocument();
  });

  it("traite une formulation ambiguë comme un brouillon manuel à relire", async () => {
    render(<WorkflowEngine />);
    await screen.findByText("Rappel post-opératoire");
    fireEvent.click(screen.getByRole("button", { name: "Nouveau scénario" }));
    fireEvent.change(await screen.findByLabelText("Génération guidée par modèles métier"), { target: { value: "Prévoir quelque chose pour les patients concernés" } });
    fireEvent.click(screen.getByRole("button", { name: "Proposer une base" }));

    expect(screen.getByDisplayValue(/Scénario — Prévoir quelque chose/)).toBeInTheDocument();
    expect(screen.getByText(/aucune règle n’est activée automatiquement/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Créer le brouillon à valider" })).toBeInTheDocument();
  });

  it("bloque l’activation jusqu’à la revue explicite du scénario", async () => {
    vi.spyOn(api, "get").mockImplementation((url: string) => {
      if (url === "/workflows/") return Promise.resolve({ data: { data: [{ ...workflow, enabled: false, status: "draft", actions: [{ type: "create_task", config: {} }] }] } }) as never;
      return Promise.resolve({ data: { data: stats } }) as never;
    });
    const putSpy = vi.spyOn(api, "put").mockResolvedValue({ data: {} } as never);
    render(<WorkflowEngine />);
    await screen.findByText("Rappel post-opératoire");
    fireEvent.click(screen.getByRole("button", { name: "Revoir puis activer" }));

    expect(await screen.findByText("Revoir avant activation")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Activer le scénario" })).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Activer le scénario" }));
    await waitFor(() => expect(putSpy).toHaveBeenCalledWith("/workflows/3", { enabled: true }));
  });

  it("sérialise l’assignation par rôle depuis le constructeur visuel", async () => {
    const postSpy = vi.spyOn(api, "post").mockResolvedValue({ data: { data: { id: 9 } } } as never);
    render(<WorkflowEngine />);
    await screen.findByText("Rappel post-opératoire");
    fireEvent.click(screen.getByRole("button", { name: "Nouveau scénario" }));
    fireEvent.change(await screen.findByLabelText(/Nom du scénario/), { target: { value: "Rappel consentement" } });
    fireEvent.change(screen.getByLabelText("Rôle responsable de la tâche 1"), { target: { value: "assistante" } });
    fireEvent.click(screen.getByRole("button", { name: "Créer le brouillon à valider" }));

    await waitFor(() => expect(postSpy).toHaveBeenCalledWith("/workflows/", expect.objectContaining({
      actions: [expect.objectContaining({ type: "create_task", config: expect.objectContaining({ assignee_role: "assistante" }) })],
    })));
  });

  it("conserve la file commune lorsqu’aucune assignation n’est choisie", async () => {
    const postSpy = vi.spyOn(api, "post").mockResolvedValue({ data: { data: { id: 10 } } } as never);
    render(<WorkflowEngine />);
    await screen.findByText("Rappel post-opératoire");
    fireEvent.click(screen.getByRole("button", { name: "Nouveau scénario" }));
    fireEvent.change(await screen.findByLabelText(/Nom du scénario/), { target: { value: "File commune" } });
    fireEvent.click(screen.getByRole("button", { name: "Créer le brouillon à valider" }));

    await waitFor(() => expect(postSpy).toHaveBeenCalledWith("/workflows/", expect.objectContaining({
      actions: [expect.objectContaining({ type: "create_task", config: expect.not.objectContaining({ assignee_id: expect.anything(), assignee_role: expect.anything() }) })],
    })));
  });

  it("sérialise l’assignation à un membre précis de l’équipe", async () => {
    vi.mocked(api.get).mockImplementation((url: string) => {
      if (url === "/workflows/") return Promise.resolve({ data: { data: [workflow] } }) as never;
      if (url === "/users") return Promise.resolve({ data: [{ id: 41, prenom: "Lina", nom: "Durand", role: "assistante", is_active: true }] }) as never;
      return Promise.resolve({ data: { data: stats } }) as never;
    });
    const postSpy = vi.spyOn(api, "post").mockResolvedValue({ data: { data: { id: 11 } } } as never);
    render(<WorkflowEngine />);
    await screen.findByText("Rappel post-opératoire");
    fireEvent.click(screen.getByRole("button", { name: "Nouveau scénario" }));
    fireEvent.change(await screen.findByLabelText(/Nom du scénario/), { target: { value: "Assignation Lina" } });
    fireEvent.change(screen.getByLabelText("Responsable nommé de la tâche 1"), { target: { value: "41" } });
    fireEvent.click(screen.getByRole("button", { name: "Créer le brouillon à valider" }));

    await waitFor(() => expect(postSpy).toHaveBeenCalledWith("/workflows/", expect.objectContaining({
      actions: [expect.objectContaining({ type: "create_task", config: expect.objectContaining({ assignee_id: 41 }) })],
    })));
  });

  it("sérialise les filtres métier et le destinataire sans exposer de JSON", async () => {
    const postSpy = vi.spyOn(api, "post").mockResolvedValue({ data: { data: { id: 12 } } } as never);
    render(<WorkflowEngine />);
    await screen.findByText("Rappel post-opératoire");
    fireEvent.click(screen.getByRole("button", { name: "Nouveau scénario" }));
    fireEvent.change(await screen.findByLabelText(/Nom du scénario/), { target: { value: "Relance VIP" } });
    fireEvent.change(screen.getByLabelText("Segment clinique"), { target: { value: "vip" } });
    fireEvent.change(screen.getByLabelText("Contexte du rendez-vous"), { target: { value: "completed" } });
    fireEvent.change(screen.getByLabelText("Destinataire de l’action 1"), { target: { value: "patient" } });
    fireEvent.click(screen.getByRole("button", { name: "Créer le brouillon à valider" }));

    await waitFor(() => expect(postSpy).toHaveBeenCalledWith("/workflows/", expect.objectContaining({
      conditions: expect.objectContaining({ patient_segment: "vip", appointment_status: "completed" }),
      actions: [expect.objectContaining({ config: expect.objectContaining({ recipient: "patient" }) })],
    })));
  });
});
