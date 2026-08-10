// GET /api/admin/me -> { username } for a valid session, else 401.

import type { VercelRequest, VercelResponse } from "@vercel/node";
import { endpoint, requireAdmin } from "../_lib/http";

export default endpoint("GET", async (req: VercelRequest, res: VercelResponse) => {
  const username = requireAdmin(req);
  res.status(200).json({ username });
});
