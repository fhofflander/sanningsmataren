// POST /api/admin/upload-url { debateId } -> presigned PUT URL for the raw
// video, into the PRIVATE bucket. The browser uploads directly to R2 (Vercel
// functions cap request bodies at ~4.5 MB). Single PUT supports up to 5 GB,
// plenty for a broadcast-length mp4.

import type { VercelRequest, VercelResponse } from "@vercel/node";
import { requireEnv } from "../_lib/env";
import { HttpError, endpoint, requireAdmin } from "../_lib/http";
import { r2Client, videoKey } from "../_lib/r2";

const SLUG = /^[a-z0-9][a-z0-9-]*$/;
const EXPIRES_SEC = 3600;

export default endpoint("POST", async (req: VercelRequest, res: VercelResponse) => {
  requireAdmin(req);

  const { debateId } = (req.body ?? {}) as { debateId?: string };
  if (typeof debateId !== "string" || !SLUG.test(debateId)) {
    throw new HttpError(400, "bad_request", "debateId ska vara en url-vänlig slug.");
  }

  const key = videoKey(debateId);
  const url = await r2Client().presignPut(requireEnv("R2_PRIVATE_BUCKET"), key, EXPIRES_SEC);
  res.status(200).json({ url, key, expiresIn: EXPIRES_SEC });
});
