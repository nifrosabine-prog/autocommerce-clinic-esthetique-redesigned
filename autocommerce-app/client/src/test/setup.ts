import "@testing-library/jest-dom/vitest";
import { afterEach, beforeAll, beforeEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";
import i18n from "../i18n/config";
import frCommon from "../../public/locales/fr/common.json";

beforeAll(async () => {
  await i18n.init({
    lng: "fr",
    fallbackLng: "fr",
    defaultNS: "common",
    resources: { fr: { common: frCommon } },
    interpolation: { escapeValue: false },
  });
});

beforeEach(async () => {
  await i18n.changeLanguage("fr");
  window.localStorage.clear();
  window.sessionStorage.clear();
});

// Les composants utilisent sonner pour les notifications; les tests vérifient
// l’appel au notifier sans monter de portail global.
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  },
}));

if (!globalThis.ResizeObserver) {
  class ResizeObserverMock {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  globalThis.ResizeObserver = ResizeObserverMock as typeof ResizeObserver;
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.useRealTimers();
});
