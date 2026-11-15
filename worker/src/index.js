// PaperStreet live-quote Worker (CF-1).
//
// Serves near-1-minute quotes for the Desk symbols + fast BTC spot, mirroring
// the prices.json shape so site consumers can swap with minimal code change.
//
// Upstream sources:
//   - Desk quotes: Finnhub /quote (free tier, 60 calls/min). Key comes from a
//     Worker SECRET (env.FINNHUB_API_KEY) — never hardcoded, never in code.
//   - BTC spot: Coinbase spot (keyless), fallback CoinGecko simple/price.
//   - BTC 24h change: Coinbase Exchange stats (keyless), fallback
//     CoinGecko. (CoinGecko's fetch fails from the Worker's Cloudflare IP,
//     so it is the fallback for the change, not the source.)
//
// Design:
//   - Server-side cache (~55 s) so Finnhub is hit at most once per minute
//     (19 calls/min) no matter how many pages call the Worker.
//   - Last-good cache: if an upstream fetch fails, serve the last-good value
//     for that symbol with a staleness flag instead of an error.
//   - Symbols Finnhub does NOT cover are OMITTED (never fabricated); the
//     site consumer falls back to prices.json for them.
//   - CORS restricted to https://paperstreetbtc.com (+ http://localhost:*).
//   - Light per-IP rate limit so one client cannot hammer the Worker.
//
// This file has no build step. It is tested with node:test (see test/).

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const FINNHUB_BASE = 'https://finnhub.io/api/v1';
const COINBASE_SPOT_URL = 'https://api.coinbase.com/v2/prices/BTC-USD/spot';
const COINBASE_STATS_URL = 'https://api.exchange.coinbase.com/products/BTC-USD/stats';
const COINGECKO_URL =
  'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true';

// How long a server-side cached response stays fresh (seconds). The Worker
// re-fetches Finnhub at most once per this window, so upstream calls are
// ~19/min against a 60/min free-tier limit.
const CACHE_TTL_SECONDS = 55;
// Treat a cached payload older than this as stale even if the cache still
// holds it (belt-and-braces against early/late cache eviction).
const MAX_PAYLOAD_AGE_SECONDS = 60;

// Per-client rate limit: max requests per IP per rolling minute.
const RATE_LIMIT_PER_MINUTE = 30;

// Allowed CORS origins. localhost (any port) is for local testing only.
const ALLOWED_ORIGINS = ['https://paperstreetbtc.com'];
function isAllowedOrigin(origin) {
  if (!origin) return false;
  if (ALLOWED_ORIGINS.includes(origin)) return true;
  try {
    const u = new URL(origin);
    return u.protocol === 'http:' && (u.hostname === 'localhost' || u.hostname === '127.0.0.1');
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Symbol map: Desk key -> Finnhub /quote symbol.
// ---------------------------------------------------------------------------
//
// Finnhub /quote is documented as "real-time quote data for US stocks"
// (finnhub.io/docs/api/quote). It also serves forex pairs when the symbol is
// formatted BROKER:PAIR (e.g. OANDA:USD_CAD). It does NOT cover indices,
// commodities, or bond yields — those symbols are listed in COVERAGE_GAPS and
// are omitted from the response (consumer falls back to prices.json).
//
// Desk key is also the prices.json key, so the Worker response uses the Desk
// key verbatim (e.g. BRK.B with a dot, USDCAD as USD per CAD).

const SYMBOLS = [
  // 16 Desk stocks (US equities / ETFs — bare ticker via /quote).
  { key: 'TSLA', finnhub: 'TSLA' },
  { key: 'PLTR', finnhub: 'PLTR' },
  { key: 'MSTR', finnhub: 'MSTR' },
  { key: 'IBIT', finnhub: 'IBIT' },
  { key: 'MU', finnhub: 'MU' },
  { key: 'SPCX', finnhub: 'SPCX' },
  { key: 'META', finnhub: 'META' },
  { key: 'BRK.B', finnhub: 'BRK.B' },
  { key: 'AAPL', finnhub: 'AAPL' },
  { key: 'AMZN', finnhub: 'AMZN' },
  { key: 'MSFT', finnhub: 'MSFT' },
  { key: 'NFLX', finnhub: 'NFLX' },
  { key: 'SPOT', finnhub: 'SPOT' },
  { key: 'XYZ', finnhub: 'XYZ' },
  { key: 'GOOGL', finnhub: 'GOOGL' },
  { key: 'NVDA', finnhub: 'NVDA' },
  // 2 indicator ETFs (US-listed — bare ticker via /quote).
  { key: 'DIA', finnhub: 'DIA' },
  { key: 'QQQ', finnhub: 'QQQ' },
  // 1 forex pair: Finnhub quotes USD/CAD as CAD per USD (~1.41). The Desk
  // shows USDCAD as USD per CAD (~0.709), so the Worker inverts it.
  { key: 'USDCAD', finnhub: 'OANDA:USD_CAD', invert: true },
];

// Desk symbols the free Finnhub /quote endpoint does NOT cover. The Worker
// omits these from `stocks` and lists them in `missing` so the consumer
// falls back to prices.json. Never fabricated, never fetched elsewhere.
const COVERAGE_GAPS = [
  { key: 'WTI', reason: 'crude-oil future, not a US stock; /quote does not cover commodities' },
  { key: 'GOLD', reason: 'gold future/spot, not a US stock; /quote does not cover commodities' },
  { key: 'US10Y', reason: '10-year Treasury yield, not a stock price; /quote does not cover bond yields' },
  { key: 'VIX', reason: 'CBOE volatility index, not a US stock; /quote does not cover indices' },
  { key: 'DXY', reason: 'US Dollar Index, not a US stock; /quote does not cover indices' },
];

// ---------------------------------------------------------------------------
// Cache (Cache API when available, in-memory fallback for local tests)
// ---------------------------------------------------------------------------

class MemoryCache {
  constructor() {
    this.store = new Map();
  }
  async match(key) {
    const k = typeof key === 'string' ? key : key.url;
    const hit = this.store.get(k);
    return hit ? hit.clone() : undefined;
  }
  async put(key, response) {
    const k = typeof key === 'string' ? key : key.url;
    this.store.set(k, response.clone());
  }
  async delete(key) {
    const k = typeof key === 'string' ? key : key.url;
    return this.store.delete(k);
  }
  clear() {
    this.store.clear();
  }
}

const memoryCache = new MemoryCache();

function getCache() {
  if (typeof caches !== 'undefined' && caches.default) return caches.default;
  return memoryCache;
}

const FRESH_CACHE_KEY = 'https://paperstreet-quotes.internal/v1/fresh';
const LASTGOOD_CACHE_KEY = 'https://paperstreet-quotes.internal/v1/lastgood';

// ---------------------------------------------------------------------------
// Per-IP rate limit (in-memory sliding window; a safety valve, not billing)
// ---------------------------------------------------------------------------

const rateLimitStore = new Map(); // ip -> array of request timestamps (ms)
const RATE_LIMIT_MAX_IPS = 1000;

function isRateLimited(ip) {
  const now = Date.now();
  const windowStart = now - 60_000;
  let hits = rateLimitStore.get(ip);
  if (!hits) {
    hits = [];
    rateLimitStore.set(ip, hits);
    if (rateLimitStore.size > RATE_LIMIT_MAX_IPS) {
      const oldest = rateLimitStore.keys().next().value;
      rateLimitStore.delete(oldest);
    }
  }
  while (hits.length && hits[0] < windowStart) hits.shift();
  if (hits.length >= RATE_LIMIT_PER_MINUTE) return true;
  hits.push(now);
  return false;
}

// ---------------------------------------------------------------------------
// Upstream fetches
// ---------------------------------------------------------------------------

async function fetchFinnhubQuotes(apiKey) {
  // One /quote call per symbol, in parallel. Returns Map: Desk key -> quote.
  const results = new Map();
  const jobs = SYMBOLS.map(async ({ key, finnhub, invert }) => {
    try {
      const res = await fetch(
        `${FINNHUB_BASE}/quote?symbol=${encodeURIComponent(finnhub)}`,
        { headers: { 'X-Finnhub-Token': apiKey } },
      );
      if (!res.ok) return;
      const q = await res.json();
      // A valid quote must carry a numeric current price. Finnhub returns
      // {} or c:0 for unknown/uncovered symbols — treat that as "no data",
      // never as a price of 0.
      if (typeof q.c !== 'number' || !Number.isFinite(q.c) || q.c <= 0) return;
      const price = invert ? 1 / q.c : q.c;
      const prevClose =
        typeof q.pc === 'number' && Number.isFinite(q.pc) && q.pc > 0
          ? invert
            ? 1 / q.pc
            : q.pc
          : null;
      results.set(key, {
        c: price,
        pc: prevClose,
        t: typeof q.t === 'number' ? q.t : Math.floor(Date.now() / 1000),
        src: 'Finnhub',
      });
    } catch {
      // Per-symbol failure: leave it out; the caller fills from last-good
      // or omits it. Never throw for one symbol.
    }
  });
  await Promise.allSettled(jobs);
  return results;
}

async function fetchBtc() {
  // Coinbase spot (primary, keyless) for the price; 24h change from
  // Coinbase Exchange stats (keyless) with CoinGecko as the fallback.
  // CoinGecko is also the price fallback. Returns { usd, chg24h, src }
  // or null if no price source answers.
  //
  // Why stats, not CoinGecko, for the change: the CoinGecko fetch fails
  // from the Worker's Cloudflare IP (rate-limited/blocked there), so
  // chg24h was null live even though CoinGecko answers fine elsewhere.
  // Stats gives {open, last} for the last 24h; the change is
  // (last - open) / open * 100.
  const [coinbase, stats, gecko] = await Promise.allSettled([
    fetch(COINBASE_SPOT_URL).then((r) => (r.ok ? r.json() : Promise.reject(new Error('coinbase ' + r.status)))),
    fetch(COINBASE_STATS_URL).then((r) => (r.ok ? r.json() : Promise.reject(new Error('coinbase-stats ' + r.status)))),
    fetch(COINGECKO_URL).then((r) => (r.ok ? r.json() : Promise.reject(new Error('coingecko ' + r.status)))),
  ]);

  let usd = null;
  let chg24h = null;
  let src = null;

  if (coinbase.status === 'fulfilled') {
    const amount = Number(coinbase.value?.data?.amount);
    if (Number.isFinite(amount) && amount > 0) {
      usd = amount;
      src = 'Coinbase';
    }
  }
  // 24h change, first choice: Coinbase Exchange stats. Guarded like every
  // other upstream value: both numbers must be finite and open must be
  // > 0 (no divide-by-zero, no NaN); a bad stats payload just means "no
  // change from this source" and the CoinGecko fallback is tried next.
  if (stats.status === 'fulfilled') {
    const open = Number(stats.value?.open);
    const last = Number(stats.value?.last);
    if (Number.isFinite(open) && open > 0 && Number.isFinite(last)) {
      chg24h = ((last - open) / open) * 100;
    }
  }
  if (gecko.status === 'fulfilled') {
    const b = gecko.value?.bitcoin;
    const gUsd = Number(b?.usd);
    const gChg = Number(b?.usd_24h_change);
    // CoinGecko's change is the fallback — only used when stats gave us
    // nothing (stats down or unparseable).
    if (chg24h === null && Number.isFinite(gChg)) chg24h = gChg;
    if (usd === null && Number.isFinite(gUsd) && gUsd > 0) {
      usd = gUsd;
      src = 'CoinGecko';
    }
  }
  if (usd === null) return null;
  return { usd, chg24h, src: src || 'Coinbase' };
}

// ---------------------------------------------------------------------------
// Response building
// ---------------------------------------------------------------------------

function buildPayload({ stocks, btc, asOf, stale, staleSymbols, missing }) {
  return {
    updated: asOf,
    asOf,
    btc: btc
      ? { usd: btc.usd, chg24h: btc.chg24h, src: btc.src, time: asOf }
      : null,
    stocks,
    // Symbols omitted from this response (not covered by Finnhub, or failed
    // with no last-good value). Consumers fall back to prices.json for them.
    missing,
    // True when the whole payload came from the last-good cache (upstream
    // fetch failed). staleSymbols lists the symbols served from last-good
    // when only some of them failed.
    stale,
    staleSymbols,
  };
}

async function readCachedPayload(cache, key) {
  try {
    const res = await cache.match(key);
    if (!res) return null;
    const payload = await res.json();
    if (!payload || typeof payload !== 'object' || !payload.asOf) return null;
    return payload;
  } catch {
    return null;
  }
}

function payloadAgeSeconds(payload) {
  const t = Date.parse(payload.asOf);
  if (!Number.isFinite(t)) return Infinity;
  return (Date.now() - t) / 1000;
}

async function refreshQuotes(env) {
  const cache = getCache();
  const asOf = new Date().toISOString();
  const lastGood = await readCachedPayload(cache, LASTGOOD_CACHE_KEY);

  const apiKey = env && typeof env.FINNHUB_API_KEY === 'string' ? env.FINNHUB_API_KEY : '';
  const finnhub = apiKey ? await fetchFinnhubQuotes(apiKey) : new Map();
  const btc = await fetchBtc();

  const stocks = {};
  const staleSymbols = [];
  const missing = COVERAGE_GAPS.map((g) => g.key);

  for (const { key } of SYMBOLS) {
    const fresh = finnhub.get(key);
    if (fresh) {
      stocks[key] = fresh;
      continue;
    }
    // Symbol failed (or no API key): use its last-good value if we have one.
    const prev = lastGood?.stocks?.[key];
    if (prev && typeof prev.c === 'number' && Number.isFinite(prev.c) && prev.c > 0) {
      stocks[key] = { ...prev, src: prev.src || 'Finnhub' };
      staleSymbols.push(key);
    } else {
      missing.push(key);
    }
  }

  let btcOut = btc;
  let btcStale = false;
  if (!btcOut && lastGood?.btc && typeof lastGood.btc.usd === 'number' && lastGood.btc.usd > 0) {
    btcOut = lastGood.btc;
    btcStale = true;
  }

  const allFinnhubFailed = finnhub.size === 0 && SYMBOLS.length > 0;
  const stale = (allFinnhubFailed && !btc) || staleSymbols.length > 0 || btcStale;
  const payload = buildPayload({
    stocks,
    btc: btcOut,
    asOf,
    stale,
    staleSymbols,
    missing,
  });

  // Store fresh (55 s TTL) and last-good (long-lived) copies.
  const freshRes = new Response(JSON.stringify(payload), {
    headers: { 'Content-Type': 'application/json', 'Cache-Control': `max-age=${CACHE_TTL_SECONDS}` },
  });
  const lastGoodRes = new Response(JSON.stringify({ ...payload, stale: false }), {
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'max-age=86400' },
  });
  await cache.put(FRESH_CACHE_KEY, freshRes.clone());
  // Only overwrite last-good when we actually got fresh upstream data; a
  // fully-stale refresh must not clobber the good copy with itself.
  if (finnhub.size > 0 || btc) await cache.put(LASTGOOD_CACHE_KEY, lastGoodRes.clone());
  return payload;
}

async function getQuotes(env) {
  const cache = getCache();
  const fresh = await readCachedPayload(cache, FRESH_CACHE_KEY);
  if (fresh && payloadAgeSeconds(fresh) < MAX_PAYLOAD_AGE_SECONDS) return fresh;
  const payload = await refreshQuotes(env);
  // If the refresh produced nothing at all (no upstream, no last-good),
  // return the payload as-is (empty stocks, btc null, everything missing)
  // — the consumer falls back to prices.json. Never fabricate a price.
  return payload;
}

// ---------------------------------------------------------------------------
// HTTP handler
// ---------------------------------------------------------------------------

function corsHeaders(request) {
  const origin = request.headers.get('Origin');
  if (!origin) return {};
  if (!isAllowedOrigin(origin)) return null; // disallowed origin
  return { 'Access-Control-Allow-Origin': origin, Vary: 'Origin' };
}

function jsonResponse(payload, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'max-age=15', ...extraHeaders },
  });
}

async function handleFetch(request, env) {
  const url = new URL(request.url);
  const cors = corsHeaders(request);
  if (cors === null) {
    return jsonResponse({ error: 'origin not allowed' }, 403);
  }

  // Preflight.
  if (request.method === 'OPTIONS') {
    return new Response(null, {
      status: 204,
      headers: {
        ...cors,
        'Access-Control-Allow-Methods': 'GET, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Max-Age': '86400',
      },
    });
  }
  if (request.method !== 'GET') {
    return jsonResponse({ error: 'method not allowed' }, 405, cors);
  }

  // Only two routes: / (or /quotes) serves the quotes payload; /health is a
  // cheap liveness check that never touches an upstream provider.
  if (url.pathname === '/health') {
    return jsonResponse({ ok: true, asOf: new Date().toISOString() }, 200, cors);
  }
  if (url.pathname !== '/' && url.pathname !== '/quotes') {
    return jsonResponse({ error: 'not found' }, 404, cors);
  }

  // Per-IP rate limit (Cloudflare passes the real client IP here).
  const ip = request.headers.get('CF-Connecting-IP') || request.headers.get('X-Forwarded-For') || 'unknown';
  if (isRateLimited(ip)) {
    return jsonResponse({ error: 'rate limited' }, 429, { ...cors, 'Retry-After': '60' });
  }

  const payload = await getQuotes(env);
  return jsonResponse(payload, 200, cors);
}

export default {
  async fetch(request, env, ctx) {
    try {
      return await handleFetch(request, env);
    } catch (err) {
      // Never leak a stack or an upstream error body to the client.
      return jsonResponse({ error: 'internal error' }, 500);
    }
  },
};

// Test hooks (not used by the Worker runtime). Lets the node:test suite reset
// the in-memory cache and rate limiter between tests.
export const __test = {
  reset() {
    memoryCache.clear();
    rateLimitStore.clear();
  },
  // Delete only the fresh cache entry so the next request must refresh from
  // upstream (exercising the last-good fallback path in tests).
  async expireFresh() {
    await getCache().delete(FRESH_CACHE_KEY);
  },
  coverageGaps: COVERAGE_GAPS,
  symbols: SYMBOLS,
  cacheTtlSeconds: CACHE_TTL_SECONDS,
};
