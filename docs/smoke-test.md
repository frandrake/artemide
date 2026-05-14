# Artemide UI smoke test

Run after every deployment, after migrations, or before sharing access. Aim:
five minutes, end-to-end, real browser, real backend.

**Prereqs**
- Containers up via `docker compose up -d`
- Bearer token to hand
- Database seeded via `docker compose run --rm artemide uv run python scripts/seed_firms.py`

## 1. Login

1. Open `https://<host>/login` (or `http://localhost:8000/login` for local).
2. Paste the bearer token into **Access token** and hit **Sign in**.
3. Expected: redirect to `/`, header shows the FF monogram with Vermillion rule.

If 401 fires: confirm the token matches the active source per
`/api/v1/system/info` → `token_source`. After a rotation, the env value
in `.env` is no longer accepted.

## 2. Dashboard

1. Dashboard should render three widgets: **Primary tier**, **Upcoming
   touches**, **Audit highlights**.
2. Primary tier shows 5 firms: Spencer Stuart, Heidrick & Struggles,
   Russell Reynolds, Egon Zehnder, Korn Ferry — all `cold`.
3. Below the primary grid, a collapsible **+ 6 specialist firms** row.
4. TML Partners appears under specialist with the `warm` pill (Slate
   Blue background, Cool White text).
5. Audit highlights shows the gap actions ("Close 5 primary-tier
   coverage gaps", etc.).

## 3. Firm detail

1. Click **TML Partners** in the specialist row → URL becomes
   `/firms/<ulid>`.
2. Header: firm name in Crimson Pro 48 px Slate Blue, "specialist"
   badge, "London" badge, warm pill.
3. Partners section: **No partners yet** empty state (expected on a
   fresh seed).

## 4. Add a partner

1. From the firms list (`/firms`) navigate back into TML Partners.
2. Use the API directly (no UI add-partner form in this phase):
   ```bash
   curl -X POST https://<host>/api/v1/partners \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"firm_name":"TML Partners","name":"Imogen Carr","title":"Associate Partner","practice":"Marketing leadership"}'
   ```
3. Refresh the firm page: Imogen Carr appears in the Partners grid with
   a "no record" last-contact line.

## 5. Log a contact

1. Click the partner card → `/partners/<ulid>`.
2. Click the Vermillion **Log contact** button.
3. Fill the form: today's date, channel=email, initiated_by=FF (me),
   summary = "Catch-up", value_given = "Shared chapter draft".
4. **Save contact** — dialog closes, partner page refreshes; the
   contact timeline now shows the entry.

## 6. Audit

1. Visit `/audit`. The summary actions block reflects the new activity:
   the "Close 5 primary-tier coverage gaps" line may still be present
   but the specialist coverage block shows TML with a recent contact.
2. Click **Print** — print dialog opens with simplified layout (header
   actions hidden, cards borderless).

## 7. Search

1. Visit `/search`.
2. Type **TML** — debounce kicks in, results group by entity type;
   **Firms** group shows TML Partners.
3. Type **Imogen** — **Partners** group surfaces Imogen Carr.

## 8. Settings

1. Visit `/settings`.
2. System card shows: schema_version (latest migration), build_hash,
   token_source, counts including the new contact and partner.
3. Optional: **Trigger backup now**. Backup list should add the new
   filename.

## 9. Token rotation (do this LAST)

Token rotation is irreversible.

1. Click **Rotate token** → confirm in dialog.
2. Copy the new token from the result panel — it is shown once.
3. Update your `.env`, your Claude MCP config (`X-Artemide-Token` or
   `Authorization: Bearer …` header), and any scripts.
4. Verify: refresh `/api/v1/system/info` — `token_source` should be
   `database`. Old token now 401s; new token 200s.

## Failure triage

- 401 everywhere → check token source and which token is being sent.
- 502 / 503 from `/api/v1/admin/backup` → backup script path or
  permissions on `/data/backups`.
- Empty audit report → DB hasn't been seeded, or you're hitting a
  different DB file than the one you seeded (verify
  `ARTEMIDE_DB_PATH`).
