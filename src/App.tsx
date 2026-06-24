import { useMemo, useState } from "react";
import { ClaimCard, type CardState } from "./components/ClaimCard";
import { ClaimInput } from "./components/ClaimInput";
import { Footer } from "./components/Footer";
import { Settings } from "./components/Settings";
import { StatusLine } from "./components/StatusLine";
import { runPool } from "./lib/concurrency";
import { createProvider } from "./lib/providers";
import {
  activeKey,
  loadSettings,
  saveSettings,
  clearKeys,
} from "./lib/storage";
import { KeyError, type Settings as SettingsType } from "./lib/types";

const CONCURRENCY = 3;

export default function App() {
  const [settings, setSettings] = useState<SettingsType>(() => loadSettings());
  const [cards, setCards] = useState<CardState[]>([]);
  const [busy, setBusy] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);

  const doneCount = useMemo(
    () => cards.filter((c) => c.status !== "pending").length,
    [cards],
  );

  const handleSave = (next: SettingsType) => {
    setSettings(next);
    saveSettings(next);
  };

  const handleClear = () => {
    clearKeys();
    setSettings((s) => ({ ...s, geminiKey: "", anthropicKey: "" }));
  };

  const updateCard = (index: number, patch: Partial<CardState>) => {
    setCards((prev) =>
      prev.map((c, i) => (i === index ? { ...c, ...patch } : c)),
    );
  };

  const handleSubmit = async (text: string) => {
    setGlobalError(null);
    setCards([]);

    if (!activeKey(settings)) {
      setGlobalError(
        "Ingen API-nyckel angiven. Öppna Inställningar och klistra in din nyckel.",
      );
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
        const msg =
          e instanceof KeyError ? e.message : (e as Error).message;
        updateCard(i, { status: "error", error: msg });
      }
    });

    setBusy(false);
  };

  return (
    <div className="mx-auto flex min-h-full max-w-3xl flex-col px-4 py-8 sm:py-12">
      <header className="mb-8">
        <h1 className="font-mono text-2xl font-bold tracking-tight text-accent-deep sm:text-3xl">
          Sanningsmätaren
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-600">
          Klistra in ett citat, ett inlägg eller ett debattutdrag. Appen
          plockar ut de kontrollerbara faktapåståendena och granskar vart och
          ett mot svenska primärkällor - med ett sourcat omdöme per påstående.
        </p>
      </header>

      <div className="space-y-6">
        <Settings
          settings={settings}
          onSave={handleSave}
          onClear={handleClear}
        />

        <ClaimInput onSubmit={handleSubmit} busy={busy} />

        {globalError && (
          <p className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
            {globalError}
          </p>
        )}

        <StatusLine done={doneCount} total={cards.length} />

        <div className="space-y-4">
          {cards.map((card, i) => (
            <ClaimCard key={i} state={card} />
          ))}
        </div>
      </div>

      <div className="flex-1" />
      <Footer />
    </div>
  );
}
