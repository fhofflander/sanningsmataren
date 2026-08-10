// index.json: the list of published debates the public frontend browses.
// Written by the publish step next to the per-debate timeline.json files.

import type { Omdome, Timeline, VideoMode } from "./types";

export interface IndexEntry {
  id: string;
  titel: string;
  datum: string;
  /** Distinct party codes among deltagare, in first-appearance order. */
  partier: string[];
  antalPastaenden: number;
  perOmdome: Partial<Record<Omdome, number>>;
  videoMode: VideoMode;
  /** Resolved relative to the index.json location. */
  timelineUrl: string;
  publiceradAt: string;
  demo?: boolean;
}

export interface DebattIndex {
  version: 1;
  debates: IndexEntry[];
}

export function buildIndexEntry(
  timeline: Timeline,
  timelineUrl: string,
  publiceradAt: string,
  demo = false
): IndexEntry {
  const partier = [
    ...new Set(
      timeline.debate.deltagare
        .map((d) => d.parti)
        .filter((p): p is string => p !== null)
    ),
  ];
  return {
    id: timeline.debate.id,
    titel: timeline.debate.titel,
    datum: timeline.debate.datum,
    partier,
    antalPastaenden: timeline.stats.antalPastaenden,
    perOmdome: timeline.stats.perOmdome,
    videoMode: timeline.debate.video.mode,
    timelineUrl,
    publiceradAt,
    ...(demo ? { demo: true } : {}),
  };
}
