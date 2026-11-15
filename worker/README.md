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
  "btc": { "usd": 67280, "chg24h": -4.59, "src": "Coinbase", "time": "..." },
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
- `GET /health` returns `{ ok: true }` and never touches an upstream provider.

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

## Tests

`node --test worker/test/worker.test.mjs` (node:test, no dependencies).
Covers caching, rate limiting, CORS, fallback (last-good + omission),
USDCAD inversion, and the `prices.json` response shape. All upstream fetches
are stubbed — no real network calls, no real key.
