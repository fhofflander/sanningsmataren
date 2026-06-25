import { useEffect, useMemo, useState } from "react";
import { ClaimCard, type CardState } from "../components/ClaimCard";
import { ClaimInput } from "../components/ClaimInput";
import { Settings } from "../components/Settings";
import { StatusLine } from "../components/StatusLine";
import { runPool } from "../lib/concurrency";
import { createProvider } from "../lib/providers";
import { activeKey } from "../lib/storage";
import {
  clearExtensionKeys,
  consumePendingSelection,
  DEFAULT_EXTENSION_SETTINGS,
  loadExtensionSettings,
  type PendingSelection,
  saveExtensionSettings,
} from "../lib/extensionStorage";
import { KeyError, type Settings as SettingsType } from "../lib/types";

const CONCURRENCY = 3;
const MIN_PAGE_TEXT_LENGTH = 20;

interface ActiveTab {
  id?: number;
  title?: string;
  url?: string;
}

interface SelectionResponse {
  text?: string;
  title?: string;
  url?: string;
}

function queryActiveTab(): Promise<ActiveTab | null> {
  return new Promise((resolve) => {
    if (typeof chrome === "undefined" || !chrome.tabs?.query) {
      resolve(null);
      return;
    }

    chrome.tabs.query({ active: true, currentWindow: true }, (tabs: ActiveTab[]) => {
      resolve(tabs[0] ?? null);
    });
  });
}

function readSelectionFromContentScript(
  tab: ActiveTab,
): Promise<SelectionResponse | null> {
  return new Promise((resolve) => {
    if (!tab.id || !chrome.tabs?.sendMessage) {
      resolve(null);
      return;
    }

    chrome.tabs.sendMessage(
      tab.id,
      { type: "SM_GET_SELECTION" },
      (response?: SelectionResponse) => {
        if (chrome.runtime?.lastError || !response?.text?.trim()) {
          resolve(null);
          return;
        }
        resolve(response);
      },
    );
  });
}

function readPageTextFromContentScript(
  tab: ActiveTab,
): Promise<SelectionResponse | null> {
  return new Promise((resolve) => {
    if (!tab.id || !chrome.tabs?.sendMessage) {
      resolve(null);
      return;
    }

    chrome.tabs.sendMessage(
      tab.id,
      { type: "SM_GET_PAGE_TEXT" },
      (response?: SelectionResponse) => {
        if (chrome.runtime?.lastError || !response?.text?.trim()) {
          resolve(null);
          return;
        }
        resolve(response);
      },
    );
  });
}

function readSelectionByInjection(
  tab: ActiveTab,
): Promise<SelectionResponse | null> {
  return new Promise((resolve) => {
    if (!tab.id || !chrome.scripting?.executeScript) {
      resolve(null);
      return;
    }

    chrome.scripting.executeScript(
      {
        target: { tabId: tab.id },
        func: () => ({
          text:
            window
              .getSelection()
              ?.toString()
              .replace(/\s+/g, " ")
              .trim()
              .slice(0, 12000) ?? "",
          title: document.title,
          url: location.href,
        }),
      },
      (results?: Array<{ result?: SelectionResponse }>) => {
        if (chrome.runtime?.lastError) {
          resolve(null);
          return;
        }
        const response = results?.[0]?.result;
        resolve(response?.text?.trim() ? response : null);
      },
    );
  });
}

function readPageTextByInjection(
  tab: ActiveTab,
): Promise<SelectionResponse | null> {
  return new Promise((resolve) => {
    if (!tab.id || !chrome.scripting?.executeScript) {
      resolve(null);
      return;
    }

    chrome.scripting.executeScript(
      {
        target: { tabId: tab.id },
        func: () => ({
          text: (document.body?.innerText ?? "")
            .replace(/\s+/g, " ")
            .trim()
            .slice(0, 50000),
          title: document.title,
          url: location.href,
        }),
      },
      (results?: Array<{ result?: SelectionResponse }>) => {
        if (chrome.runtime?.lastError) {
          resolve(null);
          return;
        }
        const response = results?.[0]?.result;
        resolve(response?.text?.trim() ? response : null);
      },
    );
  });
}

async function readActiveTabSelection(): Promise<PendingSelection | null> {
  const tab = await queryActiveTab();
  if (!tab?.id) return null;

  const response =
    (await readSelectionFromContentScript(tab)) ??
    (await readSelectionByInjection(tab));

  if (!response?.text?.trim()) return null;

  return {
    text: response.text,
    title: response.title ?? tab.title,
    url: response.url ?? tab.url,
    source: "active-tab",
    createdAt: Date.now(),
  };
}

async function readActiveTabPageText(): Promise<PendingSelection | null> {
  const tab = await queryActiveTab();
  if (!tab?.id) return null;

  const response =
    (await readPageTextFromContentScript(tab)) ??
    (await readPageTextByInjection(tab));

  if (!response?.text?.trim() || response.text.trim().length < MIN_PAGE_TEXT_LENGTH) {
    return null;
  }

  return {
    text: response.text,
    title: response.title ?? tab.title,
    url: response.url ?? tab.url,
    source: "whole-page",
    createdAt: Date.now(),
  };
}

function sourceLabel(url: string): string {
  try {
    const parsed = new URL(url);
    return parsed.hostname || parsed.protocol.replace(":", "");
  } catch {
    return "aktuell sida";
  }
}

export function ExtensionPopup() {
  const [settings, setSettings] = useState<SettingsType>(
    DEFAULT_EXTENSION_SETTINGS,
  );
  const [initialText, setInitialText] = useState("");
  const [selection, setSelection] = useState<PendingSelection | null>(null);
  const [cards, setCards] = useState<CardState[]>([]);
  const [busy, setBusy] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);

  const doneCount = useMemo(
    () => cards.filter((c) => c.status !== "pending").length,
    [cards],
  );

  const applyPendingSelection = async (): Promise<boolean> => {
    const pendingSelection = await consumePendingSelection();
    if (!pendingSelection) return false;
    setSelection(pendingSelection);
    setInitialText(pendingSelection.text);
    return true;
  };

  useEffect(() => {
    let alive = true;

    void (async () => {
      const storedSettings = await loadExtensionSettings();
      if (!alive) return;

      setSettings(storedSettings);

      const hadPendingSelection = await applyPendingSelection();
      if (!alive || hadPendingSelection) return;

      const foundSelection = await readActiveTabSelection();
      if (!alive || !foundSelection) return;

      setSelection(foundSelection);
      setInitialText(foundSelection.text);
    })();

    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (typeof chrome === "undefined" || !chrome.runtime?.onMessage) return;

    const listener = (
      message: { type?: string },
      _sender: unknown,
      sendResponse: (response: { ok: boolean }) => void,
    ) => {
      if (message?.type !== "SM_PENDING_SELECTION_CHANGED") return false;

      void (async () => {
        const ok = await applyPendingSelection();
        sendResponse({ ok });
      })();

      return true;
    };

    chrome.runtime.onMessage.addListener(listener);
    return () => chrome.runtime.onMessage.removeListener(listener);
  }, []);

  const handleSave = (next: SettingsType) => {
    setSettings(next);
    void saveExtensionSettings(next);
  };

  const handleClear = () => {
    void clearExtensionKeys();
    setSettings((s) => ({ ...s, geminiKey: "", anthropicKey: "" }));
  };

  const updateCard = (index: number, patch: Partial<CardState>) => {
    setCards((prev) =>
      prev.map((c, i) => (i === index ? { ...c, ...patch } : c)),
    );
  };

  const handleUseSelection = async () => {
    setGlobalError(null);
    const foundSelection = await readActiveTabSelection();
    if (!foundSelection) {
      setGlobalError("Ingen markerad text hittades på den aktiva fliken.");
      return;
    }
    setSelection(foundSelection);
    setInitialText(foundSelection.text);
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
        const msg = e instanceof KeyError ? e.message : (e as Error).message;
        updateCard(i, { status: "error", error: msg });
      }
    });

    setBusy(false);
  };

  const handleReviewPage = async () => {
    setGlobalError(null);
    const foundPage = await readActiveTabPageText();
    if (!foundPage) {
      setGlobalError("Kunde inte läsa texten från den aktiva fliken.");
      return;
    }

    setSelection(foundPage);
    setInitialText(foundPage.text);
    await handleSubmit(foundPage.text);
  };

  return (
    <div className="min-h-screen w-full bg-surface-page">
      <div className="mx-auto flex min-h-screen max-w-xl flex-col px-4 py-5">
        <header className="mb-5">
          <h1 className="font-mono text-xl font-bold tracking-tight text-accent-deep">
            Sanningsmätaren
          </h1>
          {selection?.url && (
            <p className="mt-1 truncate text-xs text-slate-500" title={selection.url}>
              {selection.source === "whole-page" ? "Hela sidan" : "Markerad text"} från{" "}
              {sourceLabel(selection.url)}
            </p>
          )}
        </header>

        <div className="space-y-4">
          <Settings
            settings={settings}
            onSave={handleSave}
            onClear={handleClear}
          />

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleUseSelection}
              disabled={busy}
              className="rounded-md border border-slate-300 px-3 py-2 font-mono text-xs uppercase tracking-wide text-slate-600 hover:border-accent hover:text-accent disabled:opacity-40"
            >
              Hämta markerad text
            </button>
            <button
              type="button"
              onClick={handleReviewPage}
              disabled={busy}
              className="rounded-md bg-accent px-3 py-2 font-mono text-xs font-semibold uppercase tracking-wide text-white hover:bg-accent-deep disabled:opacity-40"
            >
              Granska hela sidan
            </button>
          </div>

          <ClaimInput
            onSubmit={handleSubmit}
            busy={busy}
            initialText={initialText}
          />

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
      </div>
    </div>
  );
}
