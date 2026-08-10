// Admin accounts from the ADMIN_USERS env var:
//   ADMIN_USERS="jonathan:$2b$12$...,fredrik:$2b$12$..."
// Hashes are bcrypt, generated locally with scripts/hash-password.mjs so
// plaintext passwords never touch the repo, the server config UI, or chat.

import bcrypt from "bcryptjs";

// An unused hash compared against when the username is unknown, so login
// timing does not reveal which usernames exist.
const DUMMY_HASH = bcrypt.hashSync("not-a-real-password", 10);

export function parseAdminUsers(raw: string): Map<string, string> {
  const users = new Map<string, string>();
  for (const entry of raw.split(",")) {
    const trimmed = entry.trim();
    if (!trimmed) continue;
    const colon = trimmed.indexOf(":");
    if (colon <= 0) throw new Error("ADMIN_USERS entry must be username:bcrypt-hash");
    users.set(trimmed.slice(0, colon), trimmed.slice(colon + 1));
  }
  if (users.size === 0) throw new Error("ADMIN_USERS contains no users");
  return users;
}

export async function verifyPassword(
  users: Map<string, string>,
  username: string,
  password: string
): Promise<boolean> {
  const hash = users.get(username);
  const ok = await bcrypt.compare(password, hash ?? DUMMY_HASH);
  return Boolean(hash) && ok;
}
