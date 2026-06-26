import { useEffect, useMemo, useState } from "react";
import { AppShell } from "../components/AppShell";
import { ClaimCard, type CardState } from "../components/ClaimCard";
import { ClaimInput } from "../components/ClaimInput";
import { EmptyState } from "../components/EmptyState";
import { KeyNotice } from "../components/KeyNotice";
import { Settings } from "../components/Settings";
import { StatusLine } from "../components/StatusLine";
import { createProvider } from "../lib/providers";
import { missingRequiredKeyMessage } from "../lib/storage";
import {
  clearExtensionKeys,
  consumePendingSelection,
  DEFAULT_EXTENSION_SETTINGS,
  loadExtensionSettings,
  type PendingSelection,
  saveExtensionSettings,
} from "../lib/extensionStorage";
import { KeyError, type Settings as SettingsType } from "../lib/types";
import { verifyClaims } from "../lib/verification";

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
        func: () => {
          const normalize = (text: string) =>
            text
              .replace(/\u00a0/g, " ")
              .replace(/[ \t]+/g, " ")
              .replace(/\n[ \t]+/g, "\n")
              .replace(/\n{3,}/g, "\n\n")
              .trim();

          const candidates = Array.from(
            document.querySelectorAll(
              "article, main, [role='main'], [itemprop='articleBody']",
            ),
          )
            .map((el) => normalize((el as HTMLElement).innerText ?? ""))
            .filter((text) => text.length >= 200);

          const score = (text: string) => {
            const sentenceLike = (text.match(/[.!?]\s+[A-ZÅÄÖ]/g) ?? []).length;
            const quoteLike = (text.match(/[”"]/g) ?? []).length;
            return text.length + sentenceLike * 80 + quoteLike * 30;
          };

          const bestCandidate = candidates.sort((a, b) => score(b) - score(a))[0];
          const bodyText = normalize(document.body?.innerText ?? "");
          const text = bestCandidate || bodyText;

          return {
            text: text.slice(0, 50000),
            title: document.title,
            url: location.href,
          };
        },
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

  const response = await readSelectionByInjection(tab);

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

  const response = await readPageTextByInjection(tab);

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

// Reading the active tab via chrome.scripting needs host access to that page.
// We don't ship that broad permission at install (privacy); instead we request
// it on demand from the button gesture. Calling request() when already granted
// resolves true with no prompt. Must be the first await in the click handler so
// the user gesture is still active.
function ensureHostAccess(): Promise<boolean> {
  if (typeof chrome === "undefined" || !chrome.permissions?.request) {
    return Promise.resolve(true);
  }
  return chrome.permissions
    .request({ origins: ["*://*/*"] })
    .catch(() => false);
}

export function ExtensionPopup() {
  const [settings, setSettings] = useState<SettingsType>(
    DEFAULT_EXTENSION_SETTINGS,
  );
  const [initialText, setInitialText] = useState("");
  const [initialTextVersion, setInitialTextVersion] = useState(0);
  const [selection, setSelection] = useState<PendingSelection | null>(null);
  const [cards, setCards] = useState<CardState[]>([]);
  const [busy, setBusy] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [progressMessage, setProgressMessage] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const missingKeyMessage = missingRequiredKeyMessage(settings);
  const hasKey = !missingKeyMessage;

  const doneCount = useMemo(
    () => cards.filter((c) => c.status !== "pending").length,
    [cards],
  );

  const applyPendingSelection = async (): Promise<boolean> => {
    const pendingSelection = await consumePendingSelection();
    if (!pendingSelection) return false;
    setSelection(pendingSelection);
    setInitialText(pendingSelection.text);
    setInitialTextVersion((version) => version + 1);
    return true;
  };

  useEffect(() => {
    let alive = true;

    void (async () => {
      const storedSettings = await loadExtensionSettings();
      if (!alive) return;

      setSettings(storedSettings);
      setSettingsOpen(!!missingRequiredKeyMessage(storedSettings));

      const hadPendingSelection = await applyPendingSelection();
      if (!alive || hadPendingSelection) return;

      const foundSelection = await readActiveTabSelection();
      if (!alive || !foundSelection) return;

      setSelection(foundSelection);
      setInitialText(foundSelection.text);
      setInitialTextVersion((version) => version + 1);
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

  const handleUseSelection = async () => {
    setGlobalError(null);
    setProgressMessage("Hämtar markerad text från aktiv flik...");
    if (!(await ensureHostAccess())) {
      setGlobalError(
        "Behörighet att läsa sidan nekades. Du kan klistra in texten manuellt istället.",
      );
      setProgressMessage(null);
      return;
    }
    const foundSelection = await readActiveTabSelection();
    if (!foundSelection) {
      setGlobalError(
        "Ingen markerad text hittades på den aktiva fliken. Markera texten och försök igen.",
      );
      setProgressMessage(null);
      return;
    }
    setSelection(foundSelection);
    setInitialText(foundSelection.text);
    setInitialTextVersion((version) => version + 1);
    setProgressMessage(null);
  };

  const handleSubmit = async (text: string) => {
    setGlobalError(null);
    setProgressMessage(null);
    setCards([]);

    const keyError = missingRequiredKeyMessage(settings);
    if (keyError) {
      setGlobalError(keyError);
      setSettingsOpen(true);
      return;
    }

    const provider = createProvider(settings);
    setBusy(true);
    setProgressMessage("Läser texten och letar efter kontrollerbara påståenden...");

    let claims;
    try {
      claims = await provider.extract(text);
    } catch (e) {
      setGlobalError(
        e instanceof KeyError
          ? e.message
          : `Kunde inte extrahera påståenden: ${(e as Error).message}`,
      );
      setProgressMessage(null);
      setBusy(false);
      return;
    }

    if (claims.length === 0) {
      setGlobalError(
        "Hittade inga kontrollerbara faktapåståenden i texten. Prova ett mer konkret citat.",
      );
      setProgressMessage(null);
      setBusy(false);
      return;
    }

    setCards(claims.map((claim) => ({ claim, status: "pending" as const })));
    setProgressMessage(
      `Hittade ${claims.length} påståenden. Förbereder källgranskning...`,
    );

    await verifyClaims(provider, claims, CONCURRENCY, updateCard, (progress) => {
      setProgressMessage(progress.message);
    });

    setProgressMessage(null);
    setBusy(false);
  };

  const handleReviewPage = async () => {
    setGlobalError(null);
    setProgressMessage("Läser hela sidan från aktiv flik...");
    if (!(await ensureHostAccess())) {
      setGlobalError(
        "Behörighet att läsa sidan nekades. Du kan klistra in texten manuellt istället.",
      );
      setProgressMessage(null);
      return;
    }
    const foundPage = await readActiveTabPageText();
    if (!foundPage) {
      setGlobalError("Kunde inte läsa texten från den aktiva fliken.");
      setProgressMessage(null);
      return;
    }

    setSelection(foundPage);
    setInitialText(foundPage.text);
    setInitialTextVersion((version) => version + 1);
    await handleSubmit(foundPage.text);
  };

  return (
    <AppShell
      variant="extension"
      subtitle={
        selection?.url ? (
          <p className="mt-1 truncate text-xs text-ink-faint" title={selection.url}>
            {selection.source === "whole-page" ? "Hela sidan" : "Markerad text"} från{" "}
            {sourceLabel(selection.url)}
          </p>
        ) : undefined
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

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={handleUseSelection}
          disabled={busy}
          className="min-h-9 rounded-md border border-line-strong px-3 py-2 font-mono text-xs uppercase tracking-wide text-ink-muted hover:border-accent hover:text-accent disabled:opacity-40"
        >
          Hämta markerad text
        </button>
        <button
          type="button"
          onClick={handleReviewPage}
          disabled={busy}
          className="min-h-9 rounded-md bg-accent px-3 py-2 font-mono text-xs font-semibold uppercase tracking-wide text-white hover:bg-accent-deep disabled:opacity-40"
        >
          Granska hela sidan
        </button>
      </div>

      <ClaimInput
        onSubmit={handleSubmit}
        busy={busy}
        initialText={initialText}
        initialTextVersion={initialTextVersion}
      />

      {globalError && (
        <p
          className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          role="alert"
        >
          {globalError}
        </p>
      )}

      <StatusLine done={doneCount} total={cards.length} message={progressMessage} />

      {cards.length === 0 && !busy && !globalError && <EmptyState />}

      <div className="space-y-4" aria-busy={busy}>
        {cards.map((card, i) => (
          <ClaimCard key={i} state={card} />
        ))}
      </div>
    </AppShell>
  );
}
