// Data loading for the public app. Published JSON (index.json + per-debate
// timeline.json) is served either from the app origin (dev, demo) or from a
// separate public bucket domain via VITE_DATA_BASE_URL.

import type { DebattIndex, IndexEntry, Timeline } from "../types";
import { upgradeTimeline } from "../../../format/src/upgrade";

const RAW_BASE =
  (import.meta.env.VITE_DATA_BASE_URL as string | undefined) ?? import.meta.env.BASE_URL;
const DATA_BASE = RAW_BASE.endsWith("/") ? RAW_BASE : `${RAW_BASE}/`;

function indexUrl(): URL {
  return new URL("index.json", new URL(DATA_BASE, window.location.href));
}

export async function fetchIndex(): Promise<DebattIndex> {
  const res = await fetch(indexUrl());
  if (!res.ok) throw new Error("Kunde inte hämta debattlistan (index.json).");
  const parsed = (await res.json()) as DebattIndex;
  if (parsed.version !== 1 || !Array.isArray(parsed.debates)) {
    throw new Error("Ogiltig debattlista (index.json).");
  }
  return parsed;
}

export async function fetchTimeline(entry: IndexEntry): Promise<Timeline> {
  const res = await fetch(new URL(entry.timelineUrl, indexUrl()));
  if (!res.ok) throw new Error(`Kunde inte hämta debatten "${entry.id}".`);
  return upgradeTimeline(await res.json());
}
