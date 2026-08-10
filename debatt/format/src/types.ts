// Shared format types for the debatt module: the manually authored
// granskning.json and the publishable timeline.json version 2.
// Spec: docs/debatt-format.md.

import type { Omdome } from "./verdictRules";

export type { Omdome };

export interface Kalla {
  titel: string;
  url: string;
}

export type Ursprung = "manuell" | "ai" | "hybrid";

export interface Faktagranskare {
  id: string;
  namn: string;
  roll?: string;
  profilUrl?: string;
}

export interface Redaktion {
  organisation: string;
  kontakt: string;
  faktagranskare: Faktagranskare[];
}

export type VideoMode = "hosted" | "extern" | "ingen";

export interface VideoRef {
  mode: VideoMode;
  /** Public playback URL; set by the publish step, only when mode is "hosted". */
  url: string | null;
  /** Link to the official player, shown when we do not host the video. */
  externUrl: string | null;
  /** Rights basis for hosted playback, e.g. "egen-inspelning" | "avtal" | "licens". */
  rattighetsgrund: string | null;
  notering?: string;
}

export interface Deltagare {
  namn: string;
  parti: string | null;
  roll: string;
}

export interface TimelineEvent {
  id: string;
  start: number;
  end: number;
  talare: string;
  parti: string | null;
  citat: string;
  pastaende: string;
  typ: string;
  omdome: Omdome;
  gauge: number;
  motivering: string;
  kallor: Kalla[];
  osakerhet: string;
  granskad: boolean;
  ursprung: Ursprung;
  /** Ids into redaktion.faktagranskare; empty for pure pipeline output. */
  granskadAv: string[];
}

export interface SeriesPoint {
  t: number;
  rullande: number;
  kumulativ: number;
  antal: number;
}

export interface AndringsloggEntry {
  datum: string;
  typ: "publicering" | "rattelse" | "fortydligande";
  beskrivning: string;
  eventId?: string;
}

export interface Timeline {
  version: 2;
  debate: {
    id: string;
    titel: string;
    datum: string;
    durationSec: number | null;
    deltagare: Deltagare[];
    video: VideoRef;
  };
  redaktion: Redaktion | null;
  events: TimelineEvent[];
  series: {
    perParti: Record<string, SeriesPoint[]>;
    perTalare: Record<string, SeriesPoint[]>;
  };
  stats: {
    antalPastaenden: number;
    perOmdome: Partial<Record<Omdome, number>>;
    perParti: Record<
      string,
      { antal: number; kumulativ: number | null; perOmdome: Partial<Record<Omdome, number>> }
    >;
  };
  sammanfattning: string;
  disclaimer: string;
  andringslogg: AndringsloggEntry[];
  generatedAt: string;
}

export const SUPPORTED_TIMELINE_VERSION = 2;

// The manually authored input, compiled to a Timeline by compileTimeline().
// Contains no computed fields: gauge, series and stats are always derived.

export interface GranskningEvent {
  id?: string;
  start: number;
  end: number;
  talare: string;
  /** Omit to auto-fill from debate.deltagare by talare name. */
  parti?: string | null;
  citat: string;
  pastaende: string;
  typ: string;
  omdome: Omdome;
  motivering: string;
  kallor: Kalla[];
  osakerhet?: string;
  /** Defaults to "manuell". */
  ursprung?: Ursprung;
  granskadAv: string[];
}

export interface GranskningDoc {
  formatVersion: 1;
  debate: {
    id: string;
    titel: string;
    datum: string;
    durationSec: number | null;
    deltagare: Deltagare[];
    video: {
      mode: VideoMode;
      externUrl?: string | null;
      rattighetsgrund?: string | null;
      notering?: string;
    };
  };
  redaktion: Redaktion;
  events: GranskningEvent[];
  sammanfattning: string;
  /** Omit to get a default matching the events' ursprung. */
  disclaimer?: string;
}
