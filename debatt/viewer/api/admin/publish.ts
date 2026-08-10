// POST /api/admin/publish { granskning, andringsnot? }
// Validates and compiles server-side (what is published is always the
// server's compile), copies hosted video from the private to the public
// bucket, writes timeline.json and upserts index.json.

import type { VercelRequest, VercelResponse } from "@vercel/node";
import { compileTimeline } from "../../../format/src/compile";
import { buildIndexEntry } from "../../../format/src/indexDoc";
import type { DebattIndex } from "../../../format/src/indexDoc";
import type { GranskningDoc, Timeline } from "../../../format/src/types";
import { validateGranskning } from "../../../format/src/validate";
import { requireEnv } from "../_lib/env";
import { HttpError, endpoint, requireAdmin } from "../_lib/http";
import { INDEX_KEY, r2Client, timelineKey, videoKey } from "../_lib/r2";

export default endpoint("POST", async (req: VercelRequest, res: VercelResponse) => {
  const username = requireAdmin(req);

  const { granskning, andringsnot } = (req.body ?? {}) as {
    granskning?: unknown;
    andringsnot?: string;
  };
  const result = validateGranskning(granskning);
  if (result.errors.length > 0) {
    res.status(400).json({
      error: "validation_failed",
      message: "granskning.json är ogiltig.",
      errors: result.errors,
      warnings: result.warnings,
    });
    return;
  }

  const doc = granskning as GranskningDoc;
  const id = doc.debate.id;
  const r2 = r2Client();
  const publicBucket = requireEnv("R2_PUBLIC_BUCKET");
  const now = new Date().toISOString();

  // Hosted video: the raw upload must exist in the private bucket; publish
  // copies it into the public bucket next to the timeline.
  let videoUrl: string | null = null;
  if (doc.debate.video.mode === "hosted") {
    const privateBucket = requireEnv("R2_PRIVATE_BUCKET");
    const key = videoKey(id);
    if (!(await r2.head(privateBucket, key))) {
      throw new HttpError(
        409,
        "video_missing",
        "Ingen uppladdad video hittades för debatten. Ladda upp videon först."
      );
    }
    await r2.copy(privateBucket, key, publicBucket, key);
    const mediaBase = requireEnv("PUBLIC_MEDIA_BASE_URL").replace(/\/$/, "");
    videoUrl = `${mediaBase}/${key}`;
  }

  // Republication carries the changelog forward; every publish appends.
  const existing = await r2.getJson<Timeline>(publicBucket, timelineKey(id));
  const andringslogg = existing
    ? [
        ...existing.andringslogg,
        {
          datum: now,
          typ: "rattelse" as const,
          beskrivning: andringsnot?.trim() || `Ompublicerad av ${username}.`,
        },
      ]
    : [
        {
          datum: now,
          typ: "publicering" as const,
          beskrivning: `Publicerad av ${username}.`,
        },
      ];

  const timeline = compileTimeline(doc, { generatedAt: now, videoUrl, andringslogg });
  await r2.putJson(publicBucket, timelineKey(id), timeline, "public, max-age=60");

  const index =
    (await r2.getJson<DebattIndex>(publicBucket, INDEX_KEY)) ?? { version: 1, debates: [] };
  const publiceradAt =
    index.debates.find((d) => d.id === id)?.publiceradAt ?? now;
  const entry = buildIndexEntry(timeline, timelineKey(id), publiceradAt);
  index.debates = [
    entry,
    ...index.debates.filter((d) => d.id !== id),
  ].sort((a, b) => (a.datum < b.datum ? 1 : a.datum > b.datum ? -1 : 0));
  await r2.putJson(publicBucket, INDEX_KEY, index, "public, max-age=60");

  res.status(200).json({
    ok: true,
    id,
    warnings: result.warnings,
    videoUrl,
    republished: Boolean(existing),
  });
});
