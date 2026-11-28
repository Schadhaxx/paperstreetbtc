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
// When the served BTC 24h change is null (no last-good value anywhere),
// the cached payload goes stale after this many seconds instead of the
// full window, so the next request retries the change sources soon
// instead of serving a blank change for a minute. (Nov 15: a null change
// was cached for the full 55s and the pills showed no 24h change.)
const NULL_CHG_TTL_SECONDS = 15;
// Treat a cached payload older than this as stale even if the cache still
// holds it (belt-and-braces against early/late cache eviction).
const MAX_PAYLOAD_AGE_SECONDS = 60;

// Last good BTC 24h change, kept in memory so a transient failure of both
// change sources (Coinbase stats + CoinGecko) does not blank the pills.
// Stored as {chg, at} (value + the millisecond timestamp it was computed),
// because a carried change must EXPIRE: Grok Bot (Nov 15) showed the old
// plain-number value was rewritten every round the price was fresh, even
// when the value was itself carried over, so a days-old change was served
// as current with stale:false. A carried change is reused only while it is
// at most LASTGOOD_CHG_MAX_AGE_MS old; past that, null is served so the
// 15s refresh and the page's CoinGecko fill take over. Never persisted —
// a cold Worker isolate has no value here, and the last-good cache (below)
// covers that case instead (its btc.chgAt gets the same check).
let lastGoodBtcChg = null;

// A carried (not fresh this round) 24h change is reused only while it is
// at most this old. Past it, the change is served as null.
const LASTGOOD_CHG_MAX_AGE_MS = 10 * 60 * 1000;

// Per-client rate limit: max requests per IP per rolling minute.
const RATE_LIMIT_PER_MINUTE = 30;

// Stage 2 analytics (27 Nov 2026): POST /err has its OWN bucket —
// 5 posts per IP per minute — so an error flood cannot starve quotes
// and quote traffic cannot block reports. Never share the 30/min bucket.
const ERR_RATE_LIMIT_PER_MINUTE = 5;
const ERR_MAX_ROWS = 5000; // D1 cap: delete the oldest past this many rows
const ERR_RETENTION_DAYS = 30;
const errRateLimitStore = new Map(); // ip -> array of request timestamps (ms)

function isErrRateLimited(ip) {
  const now = Date.now();
  const windowStart = now - 60_000;
  let hits = errRateLimitStore.get(ip);
  if (!hits) {
    hits = [];
    errRateLimitStore.set(ip, hits);
    if (errRateLimitStore.size > RATE_LIMIT_MAX_IPS) {
      const oldest = errRateLimitStore.keys().next().value;
      errRateLimitStore.delete(oldest);
    }
  }
  while (hits.length && hits[0] < windowStart) hits.shift();
  if (hits.length >= ERR_RATE_LIMIT_PER_MINUTE) return true;
  hits.push(now);
  return false;
}

// ---------------------------------------------------------------------------
// Stage 3 event analytics (27 Nov 2026): POST /ev
// ---------------------------------------------------------------------------
//
// The site counts seven key actions (client: assets/js/ps-ev.js) and sends
// each as one fire-and-forget POST to /ev. The Worker writes one data
// point per event to Workers Analytics Engine (dataset paperstreet-events,
// binding EVENTS in wrangler.toml). Counts only: event name + page +
// the ?src= tag. No cookies, no personal data, no IP stored.
//
// Analytics Engine free tier (100,000 data points written/day) is far
// above this site's volume (a handful of events per day). The weekly
// count is a SQL query against the dataset (see worker/README.md).

// The only event names the Worker accepts. Anything else is a 400, so a
// stray or abusive POST cannot pollute the counts.
const EV_EVENTS = ['desk_open', 'lab_model', 'range_switch', 'btc_chart_open', 'xfollow', 'screener_use', 'compare_use'];
const EV_MAX_BODY_BYTES = 2000;
// Separate per-IP bucket from the quotes 30/min limiter, so an event
// flood cannot starve quotes and quote traffic cannot block events.
// Events are user actions, so 30/min per IP is generous.
const EV_RATE_LIMIT_PER_MINUTE = 30;
const evRateLimitStore = new Map(); // ip -> array of request timestamps (ms)

function isEvRateLimited(ip) {
  const now = Date.now();
  const windowStart = now - 60_000;
  let hits = evRateLimitStore.get(ip);
  if (!hits) {
    hits = [];
    evRateLimitStore.set(ip, hits);
    if (evRateLimitStore.size > RATE_LIMIT_MAX_IPS) {
      const oldest = evRateLimitStore.keys().next().value;
      evRateLimitStore.delete(oldest);
    }
  }
  while (hits.length && hits[0] < windowStart) hits.shift();
  if (hits.length >= EV_RATE_LIMIT_PER_MINUTE) return true;
  hits.push(now);
  return false;
}

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
        // 4s timeout (Nov 15 r3): one hung Finnhub call used to hang the
        // whole refresh. A timed-out symbol is just omitted (see below).
        { headers: { 'X-Finnhub-Token': apiKey }, signal: AbortSignal.timeout(4000) },
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
  // Each upstream fetch has a 4s timeout (Nov 15 r2): one hung source used
  // to hang the whole response.
  const [coinbase, stats, gecko] = await Promise.allSettled([
    fetch(COINBASE_SPOT_URL, { signal: AbortSignal.timeout(4000) }).then((r) => (r.ok ? r.json() : Promise.reject(new Error('coinbase ' + r.status)))),
    fetch(COINBASE_STATS_URL, { signal: AbortSignal.timeout(4000) }).then((r) => (r.ok ? r.json() : Promise.reject(new Error('coinbase-stats ' + r.status)))),
    fetch(COINGECKO_URL, { signal: AbortSignal.timeout(4000) }).then((r) => (r.ok ? r.json() : Promise.reject(new Error('coingecko ' + r.status)))),
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
  const now = Date.now();
  // A fresh change computed this round is saved to the in-memory last-good
  // (with its timestamp) even when no price source answers — Nov 15 r2:
  // the old early return for no price dropped a good change it already had.
  if (Number.isFinite(chg24h)) {
    lastGoodBtcChg = { chg: chg24h, at: now };
  }
  if (usd === null) return null;
  // Last-good 24h change (Nov 15, expiry added Nov 15 r2): when both
  // change sources fail this round, serve the previous valid change
  // instead of null so the pills keep showing a change — but ONLY while
  // it is at most LASTGOOD_CHG_MAX_AGE_MS old. A carried value must not
  // refresh chgAt, and is marked stale in the payload.
  let chgAt = null;
  let chgStale = false;
  if (Number.isFinite(chg24h)) {
    // Fresh change this round: timestamp is now.
    chgAt = new Date(now).toISOString();
  } else if (
    lastGoodBtcChg &&
    Number.isFinite(lastGoodBtcChg.chg) &&
    now - lastGoodBtcChg.at <= LASTGOOD_CHG_MAX_AGE_MS
  ) {
    // Carried change, still within the cap. Keep its original timestamp.
    chg24h = lastGoodBtcChg.chg;
    chgAt = new Date(lastGoodBtcChg.at).toISOString();
    chgStale = true;
  } else {
    // No fresh change and no usable carried change (or it expired): drop
    // the stale in-memory value and serve null, so the 15s refresh and
    // the page's CoinGecko fill take over.
    lastGoodBtcChg = null;
    chg24h = null;
  }
  // priceAt is the original capture time of this price (Nov 15 r3): the
  // stale-price branch reuses it so a carried price keeps its age instead
  // of getting a fresh timestamp on every re-save.
  return { usd, chg24h, src: src || 'Coinbase', chgAt, chgStale, priceAt: new Date(now).toISOString() };
}

// ---------------------------------------------------------------------------
// Response building
// ---------------------------------------------------------------------------

function buildPayload({ stocks, btc, asOf, stale, staleSymbols, missing }) {
  return {
    updated: asOf,
    asOf,
    btc: btc
      // time/priceAt are the price CAPTURE time (Nov 15 r3), not the
      // payload build time: a carried price must keep its original
      // timestamp, or the re-save below would refresh it every round and
      // the price would never age out. No page consumer reads btc.time.
      ? { usd: btc.usd, chg24h: btc.chg24h, src: btc.src, time: btc.priceAt ?? asOf, priceAt: btc.priceAt ?? asOf, chgAt: btc.chgAt ?? null, chgStale: !!btc.chgStale }
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
  // Finnhub and BTC run together (Nov 15 r3): they used to run one after
  // the other, so a slow Finnhub round delayed the BTC price too. Both
  // sides are timeout-bounded (~4s each), so the worst case is about 4s.
  const [finnhub, btc] = await Promise.all([
    apiKey ? fetchFinnhubQuotes(apiKey) : Promise.resolve(new Map()),
    fetchBtc(),
  ]);

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
    // Price age check (Nov 15 r3, should-fix #1; r4: no fallback to time):
    // a carried price older than ~10 minutes is not served at all — the
    // pages fetch the price directly. The original capture time is
    // priceAt; entries without one (old cache entries predate it) are
    // treated as expired, never as fresh via time.
    const priceAtMs = Date.parse(lastGood.btc.priceAt);
    if (Number.isFinite(priceAtMs) && Date.now() - priceAtMs <= LASTGOOD_CHG_MAX_AGE_MS) {
      // Change age check (Nov 15 r2 must-fix, applied here too): the
      // carried change is reused only while it is at most 10 minutes old.
      // Old cache entries with no chgAt serve null.
      const at = Date.parse(lastGood.btc.chgAt);
      const ok = typeof lastGood.btc.chg24h === 'number' && Number.isFinite(at) && Date.now() - at <= LASTGOOD_CHG_MAX_AGE_MS;
      btcOut = { ...lastGood.btc, priceAt: lastGood.btc.priceAt, chg24h: ok ? lastGood.btc.chg24h : null, chgAt: ok ? lastGood.btc.chgAt : null, chgStale: true };
      btcStale = true;
    }
    // Past the price cap (or no timestamp): leave btcOut null so the
    // pages fetch the price directly.
  }
  // Cold-start protection (Nov 15): the in-memory last-good change is empty
  // on a fresh isolate, so a fresh price with a null change would clobber
  // the cached good change. Fill it from the last-good cache instead, so
  // the payload (and the cache) never carries a null change while a good
  // one is cached. (Nov 15 r2): only reuse the cached change while it is
  // at most LASTGOOD_CHG_MAX_AGE_MS old — the same cap as the in-memory
  // value, checked against lastGood.btc.chgAt. Past that, leave null so
  // the 15s refresh and the page's CoinGecko fill take over. A carried
  // value keeps its original chgAt and is marked stale.
  if (btcOut && typeof btcOut.chg24h !== 'number' && lastGood?.btc && typeof lastGood.btc.chg24h === 'number') {
    const cachedAt = Date.parse(lastGood.btc.chgAt);
    if (Number.isFinite(cachedAt) && Date.now() - cachedAt <= LASTGOOD_CHG_MAX_AGE_MS) {
      btcOut = { ...btcOut, chg24h: lastGood.btc.chg24h, chgAt: lastGood.btc.chgAt, chgStale: true };
    }
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
  if (fresh) {
    // A cached payload whose BTC change is null goes stale after the short
    // TTL (Nov 15), so the next request retries the change sources soon
    // instead of serving a blank change for the full window. A payload
    // with a valid change keeps the normal window.
    const chgNull = !fresh.btc || typeof fresh.btc.chg24h !== 'number';
    const maxAge = chgNull ? NULL_CHG_TTL_SECONDS : MAX_PAYLOAD_AGE_SECONDS;
    if (payloadAgeSeconds(fresh) < maxAge) return fresh;
  }
  const payload = await refreshQuotes(env);
  // If the refresh produced nothing at all (no upstream, no last-good),
  // return the payload as-is (empty stocks, btc null, everything missing)
  // — the consumer falls back to prices.json. Never fabricate a price.
  return payload;
}

// ---------------------------------------------------------------------------
// Stage 2 analytics: page-error reports (POST /err) + secret read (GET /err)
// ---------------------------------------------------------------------------
//
// POST /err: the public pages' ps-err.js hook reports window.onerror,
// unhandledrejection, and BTC-chart lineFail here. No personal data:
// pathname only, basename only, browser/device parsed client-side.
// D1 down (or binding missing) still returns 204 — the page must never
// see a stack or a secret. GET /err: secret-protected read for Chief of
// Staff's weekday health check. No CORS on the read route (curl/script).

const ERR_BROWSERS = ['Chrome', 'Safari', 'Firefox', 'Edge', 'Other'];
const ERR_DEVICES = ['phone', 'desktop'];
const ERR_KINDS = ['onerror', 'unhandledrejection', 'lineFail'];
const ERR_SRC_RE = /^[A-Za-z0-9._-]{1,40}$/;

// Constant-time string compare (no early exit on the first mismatch).
function timingSafeEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') return false;
  let diff = a.length === b.length ? 0 : 1;
  const len = Math.max(a.length, b.length);
  for (let i = 0; i < len; i++) {
    const ca = i < a.length ? a.charCodeAt(i) : 0;
    const cb = i < b.length ? b.charCodeAt(i) : 0;
    diff |= ca ^ cb;
  }
  return diff === 0;
}

function validateErrBody(data) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return null;
  const path = data.path;
  if (typeof path !== 'string' || !path.startsWith('/') || path.includes('?') || path.includes('#') || path.length > 100) return null;
  const kind = data.kind;
  if (typeof kind !== 'string' || !ERR_KINDS.includes(kind)) return null;
  const message = typeof data.message === 'string' ? data.message.slice(0, 200) : '';
  let file = '';
  if (typeof data.file === 'string') {
    const stripped = data.file.split('?')[0].split('#')[0];
    const slash = stripped.lastIndexOf('/');
    file = (slash >= 0 ? stripped.slice(slash + 1) : stripped).slice(0, 80);
  }
  let line = 0;
  if (typeof data.line === 'number' && Number.isInteger(data.line)) line = data.line;
  const browser = typeof data.browser === 'string' && ERR_BROWSERS.includes(data.browser) ? data.browser : 'Other';
  const device = typeof data.device === 'string' && ERR_DEVICES.includes(data.device) ? data.device : 'desktop';
  const pin = typeof data.pin === 'string' ? data.pin.slice(0, 20) : '';
  const src = typeof data.src === 'string' && ERR_SRC_RE.test(data.src) ? data.src : null;
  return { path, message, file, line, browser, device, pin, kind, src };
}

async function pruneErrTable(db) {
  const cutoff = new Date(Date.now() - ERR_RETENTION_DAYS * 24 * 60 * 60 * 1000).toISOString();
  await db.prepare('DELETE FROM errors WHERE ts < ?').bind(cutoff).run();
  const total = await db.prepare('SELECT COUNT(*) AS n FROM errors').first();
  const n = total && typeof total.n === 'number' ? total.n : 0;
  if (n > ERR_MAX_ROWS) {
    await db.prepare('DELETE FROM errors WHERE id IN (SELECT id FROM errors ORDER BY ts ASC LIMIT ?)').bind(n - ERR_MAX_ROWS).run();
  }
}

async function handleErrPost(request, env, cors) {
  // Missing or disallowed Origin: 403 (the main abuse check). The quote
  // routes allow no-Origin curl; /err does not.
  const origin = request.headers.get('Origin');
  if (!origin || !isAllowedOrigin(origin)) {
    return jsonResponse({ error: 'origin not allowed' }, 403, cors);
  }
  const ip = request.headers.get('CF-Connecting-IP') || request.headers.get('X-Forwarded-For') || 'unknown';
  if (isErrRateLimited(ip)) {
    return jsonResponse({ error: 'rate limited' }, 429, { ...cors, 'Retry-After': '60' });
  }
  const lenHeader = request.headers.get('Content-Length');
  if (lenHeader !== null && Number(lenHeader) > 2048) {
    return jsonResponse({ error: 'body too large' }, 413, cors);
  }
  let text = '';
  try {
    text = await request.text();
  } catch {
    return jsonResponse({ error: 'bad body' }, 400, cors);
  }
  if (text.length > 2048) {
    return jsonResponse({ error: 'body too large' }, 413, cors);
  }
  let data = null;
  try {
    data = JSON.parse(text);
  } catch {
    return jsonResponse({ error: 'bad json' }, 400, cors);
  }
  const row = validateErrBody(data);
  if (!row) {
    return jsonResponse({ error: 'bad report' }, 400, cors);
  }
  // D1 down (or binding missing, or table not migrated yet): still 204.
  // The page must never see a stack, a secret, or a 5xx for reporting.
  try {
    const db = env && env.ERR_DB;
    if (db) {
      const ts = new Date().toISOString();
      await db
        .prepare('INSERT INTO errors (ts, path, message, file, line, browser, device, pin, kind, src) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)')
        .bind(ts, row.path, row.message, row.file, row.line, row.browser, row.device, row.pin, row.kind, row.src)
        .run();
      await pruneErrTable(db);
    }
  } catch {
    // Swallow D1 errors: the report is best-effort, the page is unaffected.
  }
  return new Response(null, { status: 204, headers: { ...cors } });
}

async function handleErrRead(request, env) {
  // No CORS on this route: it is for Chief's script / curl, not the site.
  const secret = env && typeof env.ERR_READ_SECRET === 'string' ? env.ERR_READ_SECRET : '';
  if (!secret) {
    return jsonResponse({ error: 'not configured' }, 500, { 'Cache-Control': 'no-store' });
  }
  const auth = request.headers.get('Authorization') || '';
  const token = auth.startsWith('Bearer ') ? auth.slice(7) : '';
  if (!timingSafeEqual(token, secret)) {
    return jsonResponse({ error: 'unauthorized' }, 401, { 'Cache-Control': 'no-store' });
  }
  let days = 7;
  try {
    const d = parseInt(new URL(request.url).searchParams.get('days') || '', 10);
    if (Number.isFinite(d)) days = Math.min(30, Math.max(1, d));
  } catch {
    days = 7;
  }
  const db = env && env.ERR_DB;
  if (!db) {
    return jsonResponse({ error: 'not configured' }, 500, { 'Cache-Control': 'no-store' });
  }
  const since = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();
  let countRow, topRows, recentRows, srcRows;
  try {
    countRow = await db.prepare('SELECT COUNT(*) AS n FROM errors WHERE ts >= ?').bind(since).first();
    topRows = await db
      .prepare('SELECT message, COUNT(*) AS n, MAX(ts) AS last, path FROM errors WHERE ts >= ? GROUP BY message ORDER BY n DESC LIMIT 10')
      .bind(since)
      .all();
    recentRows = await db
      .prepare('SELECT ts, path, message, file, line, browser, device, pin, kind, src FROM errors WHERE ts >= ? ORDER BY ts DESC LIMIT 50')
      .bind(since)
      .all();
    srcRows = await db
      .prepare('SELECT src, COUNT(*) AS n FROM errors WHERE ts >= ? GROUP BY src ORDER BY n DESC')
      .bind(since)
      .all();
  } catch {
    return jsonResponse({ error: 'not configured' }, 500, { 'Cache-Control': 'no-store' });
  }
  return jsonResponse(
    {
      ok: true,
      days,
      count: countRow && typeof countRow.n === 'number' ? countRow.n : 0,
      top: (topRows && topRows.results ? topRows.results : []).map((r) => ({ message: r.message, count: r.n, last: r.last, path: r.path })),
      recent: (recentRows && recentRows.results ? recentRows.results : []).map((r) => ({
        ts: r.ts, path: r.path, message: r.message, file: r.file, line: r.line,
        browser: r.browser, device: r.device, pin: r.pin, kind: r.kind, src: r.src || null,
      })),
      bySrc: (srcRows && srcRows.results ? srcRows.results : []).map((r) => ({ src: r.src || null, count: r.n })),
    },
    200,
    { 'Cache-Control': 'no-store' },
  );
}

// ---------------------------------------------------------------------------
// Stage 3: POST /ev — record one counted event in Analytics Engine.
// ---------------------------------------------------------------------------

async function handleEvPost(request, env, cors) {
  // The main abuse check (same as /err): an event POST must carry an
  // allowed Origin. A missing Origin (curl / server-to-server) is 403 —
  // real browsers always send one on a cross-origin sendBeacon/fetch.
  const origin = request.headers.get('Origin');
  if (!origin || !isAllowedOrigin(origin)) {
    return jsonResponse({ error: 'origin not allowed' }, 403, cors);
  }
  const ip = request.headers.get('CF-Connecting-IP') || request.headers.get('X-Forwarded-For') || 'unknown';
  if (isEvRateLimited(ip)) {
    return jsonResponse({ error: 'rate limited' }, 429, { ...cors, 'Retry-After': '60' });
  }
  let text;
  try {
    text = await request.text();
  } catch {
    return jsonResponse({ error: 'bad body' }, 400, cors);
  }
  if (text.length > EV_MAX_BODY_BYTES) {
    return jsonResponse({ error: 'body too large' }, 413, cors);
  }
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    return jsonResponse({ error: 'bad json' }, 400, cors);
  }
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return jsonResponse({ error: 'bad body' }, 400, cors);
  }
  const event = data.event;
  if (typeof event !== 'string' || EV_EVENTS.indexOf(event) < 0) {
    return jsonResponse({ error: 'bad event' }, 400, cors);
  }
  const page = data.page;
  if (
    typeof page !== 'string' ||
    page.length === 0 ||
    page.length > 100 ||
    page[0] !== '/' ||
    page.indexOf('?') >= 0 ||
    page.indexOf('#') >= 0 ||
    page.indexOf('\\') >= 0
  ) {
    return jsonResponse({ error: 'bad page' }, 400, cors);
  }
  // The ?src= tag rides along so the weekly totals split by source.
  // Only a short safe token is kept; anything else is dropped to ''.
  let src = '';
  if (typeof data.src === 'string' && /^[A-Za-z0-9._-]{1,40}$/.test(data.src)) src = data.src;
  // Write the data point. writeDataPoint is non-blocking (fire-and-
  // forget on the Worker side too). If the Analytics Engine binding is
  // missing (a local test without it), skip the write but still answer
  // 204 — the page must never see an error for an analytics send.
  try {
    if (env && env.EVENTS && typeof env.EVENTS.writeDataPoint === 'function') {
      env.EVENTS.writeDataPoint({ blobs: [event, page, src], doubles: [1], indexes: [event] });
    }
  } catch {
    // Never fail the send.
  }
  return new Response(null, { status: 204, headers: { ...cors } });
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

  // GET /err is the secret-protected read route (Chief's script / curl):
  // no CORS, no origin check — it runs before the CORS gate below.
  if (url.pathname === '/err' && request.method === 'GET') {
    return handleErrRead(request, env);
  }

  const cors = corsHeaders(request);
  if (cors === null) {
    return jsonResponse({ error: 'origin not allowed' }, 403);
  }

  // Preflight. POST is allowed for /err and /ev (sendBeacon posts
  // text/plain and must not hit a preflight it cannot complete);
  // POST / stays 405.
  if (request.method === 'OPTIONS') {
    return new Response(null, {
      status: 204,
      headers: {
        ...cors,
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Max-Age': '86400',
      },
    });
  }

  // POST /err: page-error reports (Stage 2). Origin + rate limit inside.
  if (url.pathname === '/err' && request.method === 'POST') {
    return handleErrPost(request, env, cors);
  }

  // Stage 3: POST /ev records one counted event (Analytics Engine).
  // Origin + rate limit inside.
  if (url.pathname === '/ev') {
    if (request.method !== 'POST') {
      return jsonResponse({ error: 'method not allowed' }, 405, cors);
    }
    return handleEvPost(request, env, cors);
  }

  if (request.method !== 'GET') {
    return jsonResponse({ error: 'method not allowed' }, 405, cors);
  }

  // Only four route families: / (or /quotes) serves the quotes payload;
  // /health is a cheap liveness check that never touches an upstream
  // provider; /err is the Stage 2 page-error report (POST) and its
  // secret-protected read (GET, handled before the CORS gate above);
  // /ev is the Stage 3 counted-event POST.
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
    errRateLimitStore.clear();
    evRateLimitStore.clear();
    lastGoodBtcChg = null;
  },
  // Clear only the in-memory last-good 24h change (simulates a cold
  // isolate: the cache still holds a good change, the memory does not).
  resetLastGoodChg() {
    lastGoodBtcChg = null;
  },
  // Set the in-memory last-good 24h change with an explicit timestamp
  // (simulates an aged carried change for the expiry test).
  setLastGoodChg(chg, at) {
    lastGoodBtcChg = { chg, at };
  },
  // Rewrite the last-good cache entry's BTC change timestamp (simulates
  // an aged cached change for the cold-start expiry test).
  async setLastGoodCacheChgAt(iso) {
    const cache = getCache();
    const payload = await readCachedPayload(cache, LASTGOOD_CACHE_KEY);
    if (payload && payload.btc) {
      payload.btc.chgAt = iso;
      await cache.put(
        LASTGOOD_CACHE_KEY,
        new Response(JSON.stringify(payload), { headers: { 'Content-Type': 'application/json' } }),
      );
    }
  },
  // Rewrite the last-good cache entry's BTC price timestamp (simulates
  // an aged carried price for the price-expiry test).
  async setLastGoodCachePriceAt(iso) {
    const cache = getCache();
    const payload = await readCachedPayload(cache, LASTGOOD_CACHE_KEY);
    if (payload && payload.btc) {
      payload.btc.priceAt = iso;
      payload.btc.time = iso;
      await cache.put(
        LASTGOOD_CACHE_KEY,
        new Response(JSON.stringify(payload), { headers: { 'Content-Type': 'application/json' } }),
      );
    }
  },
  // Drop priceAt from the last-good cache entry and refresh time to now
  // (simulates an old cache entry written by the pre-priceAt Worker, which
  // refreshed time on every save but never wrote priceAt). Used by the
  // no-priceAt expiry test: the old code fell back to time and served the
  // days-old price as fresh; the fixed code treats it as expired.
  async dropLastGoodCachePriceAt() {
    const cache = getCache();
    const payload = await readCachedPayload(cache, LASTGOOD_CACHE_KEY);
    if (payload && payload.btc) {
      delete payload.btc.priceAt;
      payload.btc.time = new Date().toISOString();
      await cache.put(
        LASTGOOD_CACHE_KEY,
        new Response(JSON.stringify(payload), { headers: { 'Content-Type': 'application/json' } }),
      );
    }
  },
  // Delete only the fresh cache entry so the next request must refresh from
  // upstream (exercising the last-good fallback path in tests).
  async expireFresh() {
    await getCache().delete(FRESH_CACHE_KEY);
  },
  coverageGaps: COVERAGE_GAPS,
  symbols: SYMBOLS,
  cacheTtlSeconds: CACHE_TTL_SECONDS,
  nullChgTtlSeconds: NULL_CHG_TTL_SECONDS,
  lastGoodChgMaxAgeMs: LASTGOOD_CHG_MAX_AGE_MS,
};
