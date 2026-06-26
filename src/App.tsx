import { useMemo, useState } from "react";
import { AppShell } from "./components/AppShell";
import { ClaimCard, type CardState } from "./components/ClaimCard";
import { ClaimInput } from "./components/ClaimInput";
import { EmptyState } from "./components/EmptyState";
import { KeyNotice } from "./components/KeyNotice";
import { Settings } from "./components/Settings";
import { StatusLine } from "./components/StatusLine";
import { runPool } from "./lib/concurrency";
import { createProvider } from "./lib/providers";
import {
  loadSettings,
  missingRequiredKeyMessage,
  saveSettings,
  clearKeys,
} from "./lib/storage";
import { KeyError, type Settings as SettingsType } from "./lib/types";

const CONCURRENCY = 3;

export default function App() {
  const [settings, setSettings] = useState<SettingsType>(() => loadSettings());
  const [settingsOpen, setSettingsOpen] = useState(
    () => !!missingRequiredKeyMessage(loadSettings()),
  );
  const [cards, setCards] = useState<CardState[]>([]);
  const [busy, setBusy] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);

  const doneCount = useMemo(
    () => cards.filter((c) => c.status !== "pending").length,
    [cards],
  );
  const missingKeyMessage = missingRequiredKeyMessage(settings);
  const hasKey = !missingKeyMessage;

  const handleSave = (next: SettingsType) => {
    setSettings(next);
    saveSettings(next);
  };

  const handleClear = () => {
    clearKeys();
    setSettings((s) => ({
      ...s,
      geminiKey: "",
      anthropicKey: "",
      braveSearchKey: "",
    }));
  };

  const updateCard = (index: number, patch: Partial<CardState>) => {
    setCards((prev) =>
      prev.map((c, i) => (i === index ? { ...c, ...patch } : c)),
    );
  };

  const handleSubmit = async (text: string) => {
    setGlobalError(null);
    setCards([]);

    const keyError = missingRequiredKeyMessage(settings);
    if (keyError) {
      setGlobalError(keyError);
      setSettingsOpen(true);
      return;
    }

    const provider = createProvider(settings);
    setBusy(true);

    let claims;
    try {
      claims = await provider.extract(text);
    } catch (e) {
      setGlobalError(
        e instanceof KeyError
          ? e.message
          : `Kunde inte extrahera påståenden: ${(e as Error).message}`,
      );
      setBusy(false);
      return;
    }

    if (claims.length === 0) {
      setGlobalError(
        "Hittade inga kontrollerbara faktapåståenden i texten. Prova ett mer konkret citat.",
      );
      setBusy(false);
      return;
    }

    setCards(claims.map((claim) => ({ claim, status: "pending" as const })));

    await runPool(claims.length, CONCURRENCY, async (i) => {
      try {
        const verdict = await provider.verify(
          claims[i].pastaende,
          claims[i].talare,
        );
        updateCard(i, { status: "done", verdict });
      } catch (e) {
        const msg = e instanceof KeyError ? e.message : (e as Error).message;
        updateCard(i, { status: "error", error: msg });
      }
    });

    setBusy(false);
  };

  return (
    <AppShell
      variant="web"
      subtitle={
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-muted">
          Klistra in ett citat, ett inlägg eller ett debattutdrag. Appen plockar
          ut de kontrollerbara faktapåståendena och granskar vart och ett mot
          svenska primärkällor - med ett sourcat omdöme per påstående.
        </p>
      }
    >
      <Settings
        settings={settings}
        onSave={handleSave}
        onClear={handleClear}
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
      />

      {!hasKey && <KeyNotice onOpenSettings={() => setSettingsOpen(true)} />}

      <ClaimInput onSubmit={handleSubmit} busy={busy} />

      {globalError && (
        <p
          className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          role="alert"
        >
          {globalError}
        </p>
      )}

      <StatusLine done={doneCount} total={cards.length} />

      {cards.length === 0 && !busy && !globalError && <EmptyState />}

      <div className="space-y-4" aria-busy={busy}>
        {cards.map((card, i) => (
          <ClaimCard key={i} state={card} />
        ))}
      </div>
    </AppShell>
  );
}
