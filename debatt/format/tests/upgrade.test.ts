import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { upgradeTimeline } from "../src/upgrade";

// The real v1 artifact the viewer ships with.
const sample = JSON.parse(
  readFileSync(new URL("../../viewer/public/sample-timeline.json", import.meta.url), "utf8")
) as { version: number; debate: { sourceUrl: string }; events: unknown[] };

describe("upgradeTimeline", () => {
  it("upgrades the shipped v1 sample to v2 with ai defaults", () => {
    const upgraded = upgradeTimeline(sample);
    expect(upgraded.version).toBe(2);
    // The fictional sample has an empty sourceUrl, so no video at all.
    expect(upgraded.debate.video.mode).toBe(sample.debate.sourceUrl ? "extern" : "ingen");
    expect(upgraded.debate.video.externUrl).toBe(sample.debate.sourceUrl || null);
    expect(upgraded.debate.video.url).toBeNull();
    expect(upgraded.redaktion).toBeNull();
    expect(upgraded.andringslogg).toEqual([]);
    expect(upgraded.events).toHaveLength(sample.events.length);
    for (const event of upgraded.events) {
      expect(event.ursprung).toBe("ai");
      expect(event.granskadAv).toEqual([]);
    }
  });

  it("passes v2 documents through unchanged", () => {
    const v2 = upgradeTimeline(sample);
    expect(upgradeTimeline(v2)).toBe(v2);
  });

  it("rejects unknown versions and junk", () => {
    expect(() => upgradeTimeline({ version: 3 })).toThrow("Okänd timeline-version: 3");
    expect(() => upgradeTimeline(null)).toThrow("saknar version");
    expect(() => upgradeTimeline("{}")).toThrow("saknar version");
  });
});
