// Stateless admin sessions: an HMAC-signed token in an HttpOnly cookie.
// No session store; revocation = rotating SESSION_SECRET or waiting out exp.

import { createHmac, timingSafeEqual } from "node:crypto";

export const COOKIE_NAME = "debatt_admin";
export const SESSION_TTL_SEC = 12 * 60 * 60;

interface SessionPayload {
  u: string;
  exp: number;
}

function b64url(buf: Buffer): string {
  return buf.toString("base64url");
}

function hmac(data: string, secret: string): Buffer {
  return createHmac("sha256", secret).update(data).digest();
}

export function signSession(username: string, secret: string, nowSec: number): string {
  const payload = b64url(
    Buffer.from(JSON.stringify({ u: username, exp: nowSec + SESSION_TTL_SEC }))
  );
  return `${payload}.${b64url(hmac(payload, secret))}`;
}

export function verifySession(token: string, secret: string, nowSec: number): string | null {
  const dot = token.indexOf(".");
  if (dot < 0) return null;
  const payload = token.slice(0, dot);
  const givenSig = token.slice(dot + 1);
  const expectedSig = b64url(hmac(payload, secret));
  const a = Buffer.from(givenSig);
  const b = Buffer.from(expectedSig);
  if (a.length !== b.length || !timingSafeEqual(a, b)) return null;
  try {
    const parsed = JSON.parse(Buffer.from(payload, "base64url").toString()) as SessionPayload;
    if (typeof parsed.u !== "string" || typeof parsed.exp !== "number") return null;
    if (parsed.exp <= nowSec) return null;
    return parsed.u;
  } catch {
    return null;
  }
}

export function sessionCookie(token: string, maxAgeSec: number): string {
  return [
    `${COOKIE_NAME}=${token}`,
    `Max-Age=${maxAgeSec}`,
    "Path=/",
    "HttpOnly",
    "Secure",
    "SameSite=Strict",
  ].join("; ");
}

export function clearedSessionCookie(): string {
  return sessionCookie("", 0);
}

export function readSessionCookie(cookieHeader: string | undefined): string | null {
  if (!cookieHeader) return null;
  for (const part of cookieHeader.split(";")) {
    const [name, ...rest] = part.trim().split("=");
    if (name === COOKIE_NAME) return rest.join("=") || null;
  }
  return null;
}
