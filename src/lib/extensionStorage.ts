import type { ProviderId, Settings } from "./types";

const PROVIDER_KEY = "sm_provider";
const COST_MODE_KEY = "sm_cost_mode";
const GEMINI_KEY = "sm_key_gemini";
const ANTHROPIC_KEY = "sm_key_anthropic";
const BRAVE_SEARCH_KEY = "sm_key_brave_search";
const PENDING_SELECTION_KEY = "sm_pending_selection";
const MAX_PENDING_AGE_MS = 10 * 60 * 1000;

export interface PendingSelection {
  text: string;
  url?: string;
  title?: string;
  source: "active-tab" | "context-menu" | "selection-bubble" | "whole-page";
  createdAt: number;
}

export const DEFAULT_EXTENSION_SETTINGS: Settings = {
  provider: "gemini",
  costMode: "budget",
  geminiKey: "",
  anthropicKey: "",
  braveSearchKey: "",
};

function hasChromeStorage(): boolean {
  return (
    typeof chrome !== "undefined" &&
    typeof chrome.storage?.local?.get === "function"
  );
}

function readLocal(key: string): string {
  try {
    return localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

function writeLocal(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}

function removeLocal(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}

function storageGet<T>(
  areaName: "local" | "session",
  key: string,
): Promise<T | undefined> {
  return new Promise((resolve) => {
    const area = chrome.storage?.[areaName];
    if (!area?.get) {
      resolve(undefined);
      return;
    }
    area.get(key, (items: Record<string, T | undefined>) => {
      resolve(items?.[key]);
    });
  });
}

function storageSet(
  areaName: "local" | "session",
  values: Record<string, unknown>,
): Promise<void> {
  return new Promise((resolve) => {
    const area = chrome.storage?.[areaName];
    if (!area?.set) {
      resolve();
      return;
    }
    area.set(values, () => resolve());
  });
}

function storageRemove(areaName: "local" | "session", key: string): Promise<void> {
  return new Promise((resolve) => {
    const area = chrome.storage?.[areaName];
    if (!area?.remove) {
      resolve();
      return;
    }
    area.remove(key, () => resolve());
  });
}

export async function loadExtensionSettings(): Promise<Settings> {
  if (!hasChromeStorage()) {
    const provider = readLocal(PROVIDER_KEY) as ProviderId;
    const costMode = readLocal(COST_MODE_KEY);
    return {
      provider: provider === "anthropic" ? "anthropic" : "gemini",
      costMode: costMode === "standard" ? "standard" : "budget",
      geminiKey: readLocal(GEMINI_KEY),
      anthropicKey: readLocal(ANTHROPIC_KEY),
      braveSearchKey: readLocal(BRAVE_SEARCH_KEY),
    };
  }

  const [providerRaw, costModeRaw, geminiKey, anthropicKey, braveSearchKey] =
    await Promise.all([
      storageGet<ProviderId>("local", PROVIDER_KEY),
      storageGet<Settings["costMode"]>("local", COST_MODE_KEY),
      storageGet<string>("local", GEMINI_KEY),
      storageGet<string>("local", ANTHROPIC_KEY),
      storageGet<string>("local", BRAVE_SEARCH_KEY),
    ]);
  return {
    provider: providerRaw === "anthropic" ? "anthropic" : "gemini",
    costMode: costModeRaw === "standard" ? "standard" : "budget",
    geminiKey: geminiKey ?? "",
    anthropicKey: anthropicKey ?? "",
    braveSearchKey: braveSearchKey ?? "",
  };
}

export async function saveExtensionSettings(settings: Settings): Promise<void> {
  const next = {
    [PROVIDER_KEY]: settings.provider,
    [COST_MODE_KEY]: settings.costMode,
    [GEMINI_KEY]: settings.geminiKey.trim(),
    [ANTHROPIC_KEY]: settings.anthropicKey.trim(),
    [BRAVE_SEARCH_KEY]: settings.braveSearchKey.trim(),
  };

  if (!hasChromeStorage()) {
    writeLocal(PROVIDER_KEY, next[PROVIDER_KEY]);
    writeLocal(COST_MODE_KEY, next[COST_MODE_KEY]);
    writeLocal(GEMINI_KEY, next[GEMINI_KEY]);
    writeLocal(ANTHROPIC_KEY, next[ANTHROPIC_KEY]);
    writeLocal(BRAVE_SEARCH_KEY, next[BRAVE_SEARCH_KEY]);
    return;
  }
  await storageSet("local", next);
}

export async function clearExtensionKeys(): Promise<void> {
  if (!hasChromeStorage()) {
    removeLocal(GEMINI_KEY);
    removeLocal(ANTHROPIC_KEY);
    removeLocal(BRAVE_SEARCH_KEY);
    return;
  }
  await Promise.all([
    storageRemove("local", GEMINI_KEY),
    storageRemove("local", ANTHROPIC_KEY),
    storageRemove("local", BRAVE_SEARCH_KEY),
  ]);
}

export async function savePendingSelection(
  selection: Omit<PendingSelection, "createdAt">,
): Promise<void> {
  const pending: PendingSelection = {
    ...selection,
    text: selection.text.trim().slice(0, 12000),
    createdAt: Date.now(),
  };
  await storageSet("session", { [PENDING_SELECTION_KEY]: pending });
}

export async function consumePendingSelection(): Promise<PendingSelection | null> {
  const pending = await storageGet<PendingSelection>(
    "session",
    PENDING_SELECTION_KEY,
  );
  await storageRemove("session", PENDING_SELECTION_KEY);

  if (!pending?.text?.trim()) return null;
  if (Date.now() - pending.createdAt > MAX_PENDING_AGE_MS) return null;
  return pending;
}
