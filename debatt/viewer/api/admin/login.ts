// POST /api/admin/login { username, password } -> session cookie.

import type { VercelRequest, VercelResponse } from "@vercel/node";
import { requireEnv } from "../_lib/env";
import { HttpError, endpoint, sendError } from "../_lib/http";
import { SESSION_TTL_SEC, sessionCookie, signSession } from "../_lib/session";
import { parseAdminUsers, verifyPassword } from "../_lib/users";

// Per-instance limiter: serverless instances are ephemeral, so this is a
// speed bump, not a guarantee. Real protection is long passwords + bcrypt.
const attempts = new Map<string, { count: number; resetAt: number }>();
const MAX_ATTEMPTS = 10;
const WINDOW_MS = 15 * 60 * 1000;

function rateLimit(ip: string) {
  const now = Date.now();
  const entry = attempts.get(ip);
  if (!entry || entry.resetAt <= now) {
    attempts.set(ip, { count: 1, resetAt: now + WINDOW_MS });
    return;
  }
  entry.count += 1;
  if (entry.count > MAX_ATTEMPTS) {
    throw new HttpError(429, "too_many_attempts", "För många inloggningsförsök. Vänta en stund.");
  }
}

export default endpoint("POST", async (req: VercelRequest, res: VercelResponse) => {
  const ip = (req.headers["x-forwarded-for"] as string | undefined)?.split(",")[0] ?? "unknown";
  rateLimit(ip);

  const { username, password } = (req.body ?? {}) as { username?: string; password?: string };
  if (typeof username !== "string" || typeof password !== "string" || !username || !password) {
    throw new HttpError(400, "bad_request", "Ange användarnamn och lösenord.");
  }

  const users = parseAdminUsers(requireEnv("ADMIN_USERS"));
  const ok = await verifyPassword(users, username, password);
  if (!ok) {
    sendError(res, 401, "invalid_credentials", "Fel användarnamn eller lösenord.");
    return;
  }

  const token = signSession(username, requireEnv("SESSION_SECRET"), Math.floor(Date.now() / 1000));
  res.setHeader("Set-Cookie", sessionCookie(token, SESSION_TTL_SEC));
  res.status(200).json({ username });
});
