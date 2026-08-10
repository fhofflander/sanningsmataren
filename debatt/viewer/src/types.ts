// Types for timeline.json (version 1), the only artifact the viewer reads.
// Field names mirror the pipeline output, see docs/debatt-format.md.

export type Omdome =
  | "SANT"
  | "MESTADELS SANT"
  | "VILSELEDANDE"
  | "MESTADELS FALSKT"
  | "FALSKT"
  | "GÅR EJ ATT AVGÖRA";

export interface Kalla {
  titel: string;
  url: string;
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
}

export interface SeriesPoint {
  t: number;
  rullande: number;
  kumulativ: number;
  antal: number;
}

export interface Deltagare {
  namn: string;
  parti: string | null;
  roll: string;
}

export interface Timeline {
  version: number;
  debate: {
    id: string;
    titel: string;
    datum: string;
    sourceUrl: string;
    durationSec: number | null;
    deltagare: Deltagare[];
  };
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
  generatedAt: string;
}

export const SUPPORTED_TIMELINE_VERSION = 1;
