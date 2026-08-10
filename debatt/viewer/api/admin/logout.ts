// POST /api/admin/logout -> clears the session cookie.

import type { VercelRequest, VercelResponse } from "@vercel/node";
import { endpoint } from "../_lib/http";
import { clearedSessionCookie } from "../_lib/session";

export default endpoint("POST", async (_req: VercelRequest, res: VercelResponse) => {
  res.setHeader("Set-Cookie", clearedSessionCookie());
  res.status(200).json({ ok: true });
});
