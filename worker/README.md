# PaperStreet live-quote Worker

A small Cloudflare Worker that serves near-1-minute quotes for the Desk
symbols + fast BTC spot, mirroring the `prices.json` shape so site consumers
can swap with minimal code change. Live display prices only — it never
changes portfolio math, recaps, DCA, or official-close data.

## What it serves

`GET /` (or `GET /quotes`) returns JSON shaped like `prices.json`:

```json
{
  "updated": "2026-11-14T03:20:00Z",
  "asOf": "2026-11-14T03:20:00Z",
  "btc": { "usd": 67280, "chg24h": -4.59, "src": "Coinbase", "time": "...", "priceAt": "...", "chgAt": "...", "chgStale": false },
  "stocks": {
    "AAPL": { "c": 261.74, "pc": 259.45, "t": 1582641000, "src": "Finnhub" },
    "USDCAD": { "c": 0.7009, "pc": 0.7018, "t": 1794609216, "src": "Finnhub" }
  },
  "missing": ["DXY", "VIX", "WTI", "GOLD", "US10Y"],
  "stale": false,
  "staleSymbols": []
}
```

- `stocks` — one entry per Desk symbol the Worker can serve (19 of 24).
  `c` = last price, `pc` = previous close, `t` = unix timestamp,
  `src` = provider. Keys match `prices.json` exactly (`BRK.B` with a dot,
  `USDCAD` as USD per CAD).
- `missing` — symbols omitted from this response. Consumers fall back to
  `prices.json` for them. A symbol is omitted because Finnhub does not cover
  it, or because it failed and there is no last-good value. Never fabricated.
- `stale` / `staleSymbols` — the payload (or those symbols) came from the
  last-good cache because an upstream fetch failed.
- `btc.chgAt` — ISO timestamp of when the 24h change was captured. Fresh
  change: now. Carried change: its original capture time (never refreshed).
- `btc.chgStale` — `true` when the served change is a carried last-good
  value; `false` when fresh.
- `btc.priceAt` — ISO timestamp of when the price was captured (`time` is
  the same value). The stale-price branch serves `btc: null` once the price
  is more than ~10 minutes old, so the pages fetch the price directly
  instead of showing a stale one.
- `GET /health` returns `{ ok: true }` and never touches an upstream provider.
- `POST /err` accepts page-error reports from `ps-err.js` on the site
  (text/plain body, JSON inside). Origin must be
  `https://paperstreetbtc.com` (or localhost); missing or disallowed
  origin is 403. Body cap 2 KB. Only `path`, `message`, `file`, `line`,
  `browser`, `device`, `pin`, `kind`, `src` are kept — no IP, no raw
  User-Agent, no cookies, no query strings. Own rate limit: 5 posts/min
  per IP (separate from the 30/min quote bucket). Response is 204, even
  when D1 is down. Rows live in D1 `paperstreet-errors` for 30 days,
  capped at ~5,000 rows (oldest deleted past the cap).
- `GET /err` is the secret-protected read for the weekday health check:
  `Authorization: Bearer <ERR_READ_SECRET>` (header only, never a query
  string). No CORS on this route. `?days=` defaults to 7, max 30.
  Returns `{ ok, days, count, top, recent, bySrc }` with
  `Cache-Control: no-store`. Without the secret it is 401; if the secret
  is not configured on the Worker it is 500, never open. `ERR_READ_SECRET`
  is set in the Cloudflare dashboard and is NEVER in this repo, this
  file, a handback, or a chat.

## Upstream sources

- **Desk quotes — Finnhub `/quote` (free tier, 60 calls/min).** One call per
  symbol, once per minute, for the 19 symbols Finnhub covers. The API key
  comes from a Worker secret (`FINNHUB_API_KEY`) — never in code.
- **BTC spot — Coinbase spot (keyless), fallback CoinGecko `simple/price`.**
  Coinbase gives the price; the 24h change comes from Coinbase Exchange
  `stats` (`(last - open) / open * 100`), with CoinGecko's `usd_24h_change`
  as the fallback. CoinGecko is the fallback for the change because its
  fetch fails from the Worker's Cloudflare IP. CoinGecko is still the price
  fallback if Coinbase spot fails.
- **BTC 24h change — last-good, capped at 10 minutes (Nov 15).** When both
  change sources fail in a round, the Worker serves the last good change
  (kept in memory, and in the last-good cache for a cold isolate) instead
  of null, so the pills keep showing a change — but only while it is at
  most 10 minutes old (`LASTGOOD_CHG_MAX_AGE_MS = 10 * 60 * 1000`),
  checked against its capture time. A carried value never refreshes its
  timestamp and is marked stale (`chgAt` keeps the original capture time,
  `chgStale: true`); past the cap, null is served so the page consumers
  fill the change from CoinGecko instead. Old cache entries with no `chgAt`
  serve a null change. A payload whose change is still null (no last-good
  value anywhere) goes stale after 15 s, not the full 55 s, so the next
  request retries the change sources soon. The page consumers
  also fill a null Worker change from CoinGecko while keeping the Worker
  price (s5.js, btcchart.js, clock).

## Coverage (Finnhub free `/quote`)

Covered (19): TSLA, PLTR, MSTR, IBIT, MU, SPCX, META, BRK.B, AAPL, AMZN,
MSFT, NFLX, SPOT, XYZ, GOOGL, NVDA, DIA, QQQ, USDCAD (via `OANDA:USD_CAD`,
inverted to USD per CAD).

Not covered (5, omitted — fall back to `prices.json`): WTI, GOLD, US10Y,
VIX, DXY. Finnhub `/quote` is documented for US stocks (and forex pairs via
`BROKER:PAIR`); it does not cover indices, commodities, or bond yields. The
free tier also has no OHLC candles — the Desk in-progress candle OHLC stays
on `desk-live.json`; the Worker only patches the close.

## Quota protection

- The Worker caches the upstream response server-side for ~55 s (Cache API,
  in-memory fallback). Finnhub is hit at most once per minute — 19 calls/min
  against a 60/min free-tier limit — no matter how many pages call the Worker.
- Light per-IP rate limit (30 requests/min, 429 beyond it) so one client
  cannot hammer the Worker.
- CORS: `https://paperstreetbtc.com` only, plus `http://localhost:*` for
  testing. No wildcard.

## Deploy (Site Launch)

1. Create the Worker in the Cloudflare dashboard (account
   schadha08@gmail.com, free tier). Suggested name: `paperstreet-quotes`.
2. Add the Finnhub API key as a Worker secret (`FINNHUB_API_KEY`).
   Never in chat, never in code, never committed.
3. Confirm the `workers.dev` subdomain/address for the Worker.
4. Deploy this code (`wrangler deploy` from `worker/`, or dashboard upload).
   The Worker is NOT wired live on the site until Sunil's yes.

## Stage 3 event analytics (27 Nov 2026) — POST /ev

The site counts seven key actions (client: `assets/js/ps-ev.js`, pin `ev1`)
and sends each as one fire-and-forget POST to `/ev`, which writes one data
point to Workers Analytics Engine (dataset `paperstreet-events`, binding
`EVENTS` in `wrangler.toml`). Counts only: event name + page + the `?src=`
tag. No cookies, no personal data, no IP stored. No dashboard.

- Events: `desk_open`, `lab_model`, `range_switch`, `btc_chart_open`,
  `xfollow`, `screener_use`, `compare_use`. Anything else is a 400.
- Body: JSON as `text/plain` (so `sendBeacon` sends no CORS preflight),
  max 2 KB. `page` is a pathname only (must start with `/`, no `?`/`#`,
  max 100 chars). `src` is the `?src=` tag (max 40 chars,
  `[A-Za-z0-9._-]`); anything else is dropped to `''`.
- `POST /ev` requires an allowed `Origin` (missing or disallowed is 403)
  and has its own per-IP rate limit (30/min, 429 beyond it), separate from
  the quotes bucket. Response is 204. If the Analytics Engine binding is
  missing, the write is skipped and the endpoint still answers 204.
- `POST /` is still 405; any other method on `/ev` is 405.

### Weekly count (no dashboard)

Query the dataset with the Analytics Engine SQL API (one API token with
Analytics Engine read permission, created once in the Cloudflare dashboard;
fill in `{account_id}` from the dashboard URL):

```sql
SELECT blob1 AS event, blob3 AS src, SUM(double1) AS n
FROM paperstreet-events
WHERE timestamp > NOW() - INTERVAL '7' DAY
GROUP BY event, src
ORDER BY n DESC
```

```bash
curl -s -X POST \
  "https://api.cloudflare.com/client/v4/accounts/{account_id}/analytics_engine/sql" \
  -H "Authorization: Bearer $CF_API_TOKEN" -H "Content-Type: application/json" \
  -d '{"query": "SELECT blob1 AS event, blob3 AS src, SUM(double1) AS n FROM paperstreet-events WHERE timestamp > NOW() - INTERVAL '\''7'\'' DAY GROUP BY event, src ORDER BY n DESC"}'
```

`blob1` is the event name, `blob2` the page, `blob3` the `?src=` tag
(`''` when the visit had none), `double1` is always 1. Free tier is
100,000 data points written/day and 10,000 read queries/day — this site's
volume is a handful of events per day. Cloudflare states Analytics Engine
usage is not currently billed.

## Tests

`node --test worker/test/worker.test.mjs` (node:test, no dependencies).
Covers caching, rate limiting, CORS, fallback (last-good + omission),
USDCAD inversion, the `prices.json` response shape, the Stage 2
`/err` report + read routes (fake in-memory D1 binding, placeholder
`ERR_READ_SECRET`), and the Stage 3 `/ev` endpoint (happy path, origin
checks, validation, rate limit). All upstream fetches are stubbed — no
real network calls, no real key.

## D1 migration (Stage 2)

`worker/migrations/0001_errors.sql` creates the `errors` table. Apply it
once the branch is deployed (`wrangler d1 migrations apply
paperstreet-errors` from `worker/`, or the dashboard equivalent). The
database `paperstreet-errors` already exists (created by Site Launch,
26 Nov 2026); its id is in `wrangler.toml` (an id is not a secret).
