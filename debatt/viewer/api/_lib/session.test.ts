import { describe, expect, it } from "vitest";
import {
  clearedSessionCookie,
  readSessionCookie,
  sessionCookie,
  signSession,
  verifySession,
} from "./session";

const SECRET = "test-secret";
const NOW = 1_700_000_000;

describe("session tokens", () => {
  it("round-trips a valid session", () => {
    const token = signSession("jonathan", SECRET, NOW);
    expect(verifySession(token, SECRET, NOW + 60)).toBe("jonathan");
  });

  it("expires", () => {
    const token = signSession("jonathan", SECRET, NOW);
    expect(verifySession(token, SECRET, NOW + 13 * 60 * 60)).toBeNull();
  });

  it("rejects tampering and wrong secrets", () => {
    const token = signSession("jonathan", SECRET, NOW);
    expect(verifySession(token, "other-secret", NOW)).toBeNull();
    const [payload, sig] = token.split(".");
    const forged = `${Buffer.from(JSON.stringify({ u: "fredrik", exp: NOW + 9999 })).toString(
      "base64url"
    )}.${sig}`;
    expect(verifySession(forged, SECRET, NOW)).toBeNull();
    expect(verifySession(payload, SECRET, NOW)).toBeNull();
    expect(verifySession("", SECRET, NOW)).toBeNull();
  });
});

describe("session cookie", () => {
  it("sets and reads the cookie", () => {
    const cookie = sessionCookie("abc.def", 3600);
    expect(cookie).toContain("HttpOnly");
    expect(cookie).toContain("SameSite=Strict");
    expect(readSessionCookie("other=1; debatt_admin=abc.def; x=2")).toBe("abc.def");
    expect(readSessionCookie(undefined)).toBeNull();
  });

  it("clears with max-age 0", () => {
    expect(clearedSessionCookie()).toContain("Max-Age=0");
  });
});
