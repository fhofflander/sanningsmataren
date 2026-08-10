// Small endpoint wrapper: method guard, same-origin check on mutations,
// admin session requirement, uniform JSON error envelope in Swedish.

import type { VercelRequest, VercelResponse } from "@vercel/node";
import { requireEnv } from "./env";
import { readSessionCookie, verifySession } from "./session";

export class HttpError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string
  ) {
    super(message);
  }
}

export function sendError(res: VercelResponse, status: number, code: string, message: string) {
  res.status(status).json({ error: code, message });
}

function checkOrigin(req: VercelRequest) {
  const origin = req.headers.origin;
  if (!origin) return; // non-CORS requests (same-origin form posts, curl)
  const host = req.headers.host;
  let originHost: string;
  try {
    originHost = new URL(origin).host;
  } catch {
    throw new HttpError(403, "forbidden_origin", "Ogiltig origin.");
  }
  if (originHost !== host) {
    throw new HttpError(403, "forbidden_origin", "Begäran kommer från fel origin.");
  }
}

export function requireAdmin(req: VercelRequest): string {
  const token = readSessionCookie(req.headers.cookie);
  const username = token
    ? verifySession(token, requireEnv("SESSION_SECRET"), Math.floor(Date.now() / 1000))
    : null;
  if (!username) {
    throw new HttpError(401, "unauthorized", "Inloggning krävs.");
  }
  return username;
}

export function endpoint(
  method: "GET" | "POST",
  handler: (req: VercelRequest, res: VercelResponse) => Promise<void>
) {
  return async (req: VercelRequest, res: VercelResponse) => {
    try {
      if (req.method !== method) {
        throw new HttpError(405, "method_not_allowed", `Använd ${method}.`);
      }
      if (method === "POST") checkOrigin(req);
      await handler(req, res);
    } catch (e) {
      if (e instanceof HttpError) {
        sendError(res, e.status, e.code, e.message);
      } else {
        console.error(e);
        sendError(res, 500, "internal_error", "Internt fel.");
      }
    }
  };
}
