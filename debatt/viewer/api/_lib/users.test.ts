import bcrypt from "bcryptjs";
import { describe, expect, it } from "vitest";
import { parseAdminUsers, verifyPassword } from "./users";

const HASH = bcrypt.hashSync("correct horse battery staple", 4);

describe("parseAdminUsers", () => {
  it("parses username:hash pairs", () => {
    const users = parseAdminUsers(`jonathan:${HASH}, fredrik:${HASH}`);
    expect([...users.keys()]).toEqual(["jonathan", "fredrik"]);
    expect(users.get("jonathan")).toBe(HASH);
  });

  it("rejects malformed entries and empty lists", () => {
    expect(() => parseAdminUsers("no-colon-here")).toThrow();
    expect(() => parseAdminUsers("")).toThrow();
  });
});

describe("verifyPassword", () => {
  const users = parseAdminUsers(`jonathan:${HASH}`);

  it("accepts the right password", async () => {
    expect(await verifyPassword(users, "jonathan", "correct horse battery staple")).toBe(true);
  });

  it("rejects wrong password and unknown user", async () => {
    expect(await verifyPassword(users, "jonathan", "wrong")).toBe(false);
    expect(await verifyPassword(users, "nisse", "correct horse battery staple")).toBe(false);
  });
});
