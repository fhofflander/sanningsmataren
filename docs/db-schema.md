# Database schema

Proposed storage for the backend (#9, #10, #11). Two stores:

- **Postgres** (managed, EU region: Supabase/Neon) for users, consent, and logs.
- **Redis** (Upstash, EU region) for the daily quota counter. Optional; a
  Postgres table works too (see the alternative below).

All identifiers and timestamps are UTC. The schema is built around the GDPR
constraints in `docs/gdpr-policy.md` and `docs/privacy-policy.md`: explicit
consent gating logs, defined retention, and a clean deletion path.

## Postgres

```sql
-- Users, keyed by the Google subject id.
CREATE TABLE users (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  google_sub    text NOT NULL UNIQUE,
  email         text NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  -- Article 9 explicit consent for logging questions/answers.
  consent_logging  boolean NOT NULL DEFAULT false,
  consent_at       timestamptz,
  -- Soft delete so we can honour erasure without breaking referential history.
  deleted_at    timestamptz
);

-- One row per fact-check submission (the "question").
CREATE TABLE request_logs (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  input_text  text NOT NULL,          -- may reveal political opinions (Art. 9)
  provider    text NOT NULL,          -- 'gemini' | 'anthropic'
  model       text,
  cost_mode   text                    -- 'budget' | 'standard'
);

-- One row per verified claim/verdict (the "answer"), mirrors Verdict.
CREATE TABLE verdict_logs (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id  uuid NOT NULL REFERENCES request_logs(id) ON DELETE CASCADE,
  pastaende   text NOT NULL,
  talare      text,
  typ         text,                   -- ClaimType
  omdome      text NOT NULL,          -- Omdome
  motivering  text,
  kallor      jsonb NOT NULL DEFAULT '[]',  -- [{ titel, url }]
  osakerhet   text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- Quota as a table (alternative to Redis). One row per user per day.
CREATE TABLE daily_usage (
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  usage_date  date NOT NULL,
  count       integer NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, usage_date)
);

CREATE INDEX request_logs_created_at_idx ON request_logs (created_at);
CREATE INDEX verdict_logs_created_at_idx ON verdict_logs (created_at);
CREATE INDEX request_logs_user_idx ON request_logs (user_id);
```

### Quota increment (table version)

```sql
INSERT INTO daily_usage (user_id, usage_date, count)
VALUES ($1, current_date, 1)
ON CONFLICT (user_id, usage_date)
DO UPDATE SET count = daily_usage.count + 1
RETURNING count;
```
Reject the request when the returned `count` exceeds the daily limit `[X]`.

## Redis (recommended for quota)

Simpler and faster than the table for a hot counter:

```
KEY:  quota:<google_sub>:<YYYY-MM-DD>
INCR the key, set EXPIRE to end-of-day (or 24h) on first write.
Reject when value > [X].
```
Use Redis for the counter and Postgres for everything durable.

## GDPR notes

- **Consent gate:** write to `request_logs`/`verdict_logs` only when
  `users.consent_logging = true`.
- **Retention:** scheduled job deletes or anonymises `request_logs` and
  `verdict_logs` older than the retention period in the privacy policy
  (placeholder `[12 months]`). `daily_usage` resets daily.
- **Erasure:** on a deletion request, hard-delete the user's logs (cascade) and
  either delete the `users` row or set `deleted_at` and null the PII.
- **Pseudonymisation option:** `request_logs.user_id` uses
  `ON DELETE SET NULL`, so logs can be retained in anonymised form after a user
  is removed, if that is the chosen retention design. Decide this with the legal
  review.

## Open decisions

- Redis vs `daily_usage` table for the counter.
- Retention period (drives the cleanup job).
- Whether to pseudonymise logs by default or keep them user-linked until erasure.
