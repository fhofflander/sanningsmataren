// Accept timeline.json version 1 or 2 and return version 2. Version 1 files
// come from the AI pipeline, so upgraded defaults reflect that origin. Kept
// dependency-free so the public viewer bundle does not pull in zod.

import type { Deltagare, Kalla, Omdome, Timeline } from "./types";
import { SUPPORTED_TIMELINE_VERSION } from "./types";

interface TimelineV1 {
  version: 1;
  debate: {
    id: string;
    titel: string;
    datum: string;
    sourceUrl: string;
    durationSec: number | null;
    deltagare: Deltagare[];
  };
  events: Array<{
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
  }>;
  series: Timeline["series"];
  stats: Timeline["stats"];
  sammanfattning: string;
  disclaimer: string;
  generatedAt: string;
}

export function upgradeTimeline(data: unknown): Timeline {
  if (typeof data !== "object" || data === null || !("version" in data)) {
    throw new Error("Ogiltig timeline: saknar version.");
  }
  const version = (data as { version: unknown }).version;
  if (version === SUPPORTED_TIMELINE_VERSION) {
    return data as Timeline;
  }
  if (version === 1) {
    const v1 = data as TimelineV1;
    return {
      version: 2,
      debate: {
        id: v1.debate.id,
        titel: v1.debate.titel,
        datum: v1.debate.datum,
        durationSec: v1.debate.durationSec,
        deltagare: v1.debate.deltagare,
        video: {
          mode: v1.debate.sourceUrl ? "extern" : "ingen",
          url: null,
          externUrl: v1.debate.sourceUrl || null,
          rattighetsgrund: null,
        },
      },
      redaktion: null,
      events: v1.events.map((e) => ({ ...e, ursprung: "ai" as const, granskadAv: [] })),
      series: v1.series,
      stats: v1.stats,
      sammanfattning: v1.sammanfattning,
      disclaimer: v1.disclaimer,
      andringslogg: [],
      generatedAt: v1.generatedAt,
    };
  }
  throw new Error(`Okänd timeline-version: ${String(version)}`);
}
