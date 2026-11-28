// Tests for the PaperStreet live-quote Worker (CF-1).
// Run: node --test worker/test/worker.test.mjs   (node:test, no dependencies)
//
// All upstream fetches are STUBBED — no real network calls, no real API key.
// The Finnhub key used here is a dummy placeholder ('test-key-placeholder').

import test from 'node:test';
import assert from 'node:assert/strict';
import worker, { __test } from '../src/index.js';

const ENV = { FINNHUB_API_KEY: 'test-key-placeholder' };

// --- Stubs -----------------------------------------------------------------

function finnhubQuote(c, pc, t = 1794603600) {
  return { c, h: c + 1, l: c - 1, o: c, pc, dp: 1.0, t };
}

// Finnhub prices for the 19 covered symbols (USD per share; USDCAD is
// CAD per USD ~1.41 and gets inverted by the Worker).
const FINNHUB_PRICES = {
  TSLA: 420.1, PLTR: 180.5, MSTR: 210.3, IBIT: 55.2, MU: 300.4, SPCX: 139.11,
  META: 650.0, 'BRK.B': 592.94, AAPL: 261.74, AMZN: 220.0, MSFT: 500.0,
  NFLX: 900.0, SPOT: 700.0, XYZ: 84.58, GOOGL: 280.0, NVDA: 180.0,
  DIA: 523.15, QQQ: 679.89, 'OANDA:USD_CAD': 1.4268,
};
const FINNHUB_PREV = Object.fromEntries(
  Object.entries(FINNHUB_PRICES).map(([k, v]) => [k, +(v * 0.99).toFixed(4)]),
);

function makeFetchStub({ finnhubOk = true, coinbaseOk = true, statsOk = true, geckoOk = true, finnhubPrices = FINNHUB_PRICES, statsOpen = '70000.00', statsLast = '67280.00' } = {}) {
  const calls = { finnhub: 0, coinbase: 0, stats: 0, gecko: 0 };
  const stub = async (url, opts) => {
    const u = String(url);
    if (u.startsWith('https://finnhub.io/api/v1/quote')) {
      calls.finnhub += 1;
      if (!finnhubOk) return new Response('error', { status: 500 });
      const sym = new URL(u).searchParams.get('symbol');
      const price = finnhubPrices[sym];
      if (price === undefined) return new Response(JSON.stringify({}), { status: 200 });
      return new Response(JSON.stringify(finnhubQuote(price, FINNHUB_PREV[sym])), {
        status: 200, headers: { 'Content-Type': 'application/json' },
      });
    }
    if (u.startsWith('https://api.coinbase.com/v2/prices/BTC-USD/spot')) {
      calls.coinbase += 1;
      if (!coinbaseOk) return new Response('error', { status: 500 });
      return new Response(JSON.stringify({ data: { base: 'BTC', currency: 'USD', amount: '67280.00' } }), {
        status: 200, headers: { 'Content-Type': 'application/json' },
      });
    }
    if (u.startsWith('https://api.exchange.coinbase.com/products/BTC-USD/stats')) {
      calls.stats += 1;
      if (!statsOk) return new Response('error', { status: 500 });
      // statsOpen/statsLast of null omit the field (missing-value case).
      const payload = { open: statsOpen, high: '71000.00', low: '65000.00', last: statsLast, volume: '1000.0' };
      if (statsOpen === null) delete payload.open;
      if (statsLast === null) delete payload.last;
      return new Response(JSON.stringify(payload), {
        status: 200, headers: { 'Content-Type': 'application/json' },
      });
    }
    if (u.startsWith('https://api.coingecko.com/api/v3/simple/price')) {
      calls.gecko += 1;
      if (!geckoOk) return new Response('error', { status: 500 });
      return new Response(JSON.stringify({ bitcoin: { usd: 67250, usd_24h_change: -4.59 } }), {
        status: 200, headers: { 'Content-Type': 'application/json' },
      });
    }
    throw new Error('unexpected fetch: ' + u);
  };
  return { stub, calls };
}

// The 24h change the stubbed Coinbase stats endpoint implies:
// (67280 - 70000) / 70000 * 100. Kept in one place so the tests below
// assert against the same computation the Worker performs.
const STATS_CHG24H = ((67280 - 70000) / 70000) * 100;

function req(path = '/', { origin, ip = '1.2.3.4', method = 'GET', body } = {}) {
  const headers = new Headers();
  if (origin !== undefined) headers.set('Origin', origin);
  if (ip) headers.set('CF-Connecting-IP', ip);
  const init = { method, headers };
  if (body !== undefined) {
    init.body = body;
    headers.set('Content-Type', 'text/plain');
  }
  return new Request(`https://paperstreet-quotes.workers.dev${path}`, init);
}

async function body(res) {
  return JSON.parse(await res.text());
}

// Fake Analytics Engine binding: records every data point written.
function makeEventsStub() {
  const calls = [];
  return {
    calls,
    writeDataPoint(dp) { calls.push(dp); },
  };
}

// Env with the fake Analytics Engine binding (Stage 3 /ev tests).
function envWithEvents(events) {
  return { ...ENV, EVENTS: events };
}

const EV_ORIGIN = 'https://paperstreetbtc.com';
function evReq(event, page, src, extra = {}) {
  const payload = { event, page };
  if (src !== undefined) payload.src = src;
  return req('/ev', { origin: EV_ORIGIN, method: 'POST', body: JSON.stringify(payload), ...extra });
}

test.beforeEach(() => {
  __test.reset();
});

// --- Response shape ---------------------------------------------------------

test('response mirrors prices.json shape and keys', async () => {
  const { stub } = makeFetchStub();
  globalThis.fetch = stub;
  const res = await worker.fetch(req('/', { origin: 'https://paperstreetbtc.com' }), ENV);
  assert.equal(res.status, 200);
  const p = await body(res);
  assert.equal(typeof p.updated, 'string');
  assert.equal(typeof p.asOf, 'string');
  assert.equal(p.btc.usd, 67280);
  // 24h change comes from Coinbase Exchange stats first (not CoinGecko):
  // (67280 - 70000) / 70000 * 100.
  assert.ok(Math.abs(p.btc.chg24h - STATS_CHG24H) < 1e-9, `got ${p.btc.chg24h}, want ${STATS_CHG24H}`);
  assert.equal(p.btc.src, 'Coinbase');
  assert.equal(p.stocks['BRK.B'].c, 592.94);
  assert.equal(p.stocks['BRK.B'].pc, FINNHUB_PREV['BRK.B']);
  assert.equal(p.stocks['BRK.B'].t, 1794603600);
  assert.equal(p.stocks['BRK.B'].src, 'Finnhub');
  assert.equal(p.stocks.AAPL.c, 261.74);
  assert.equal(p.stale, false);
  assert.deepEqual(p.staleSymbols, []);
});

test('USDCAD is served as USD per CAD (~0.709), inverted from the Finnhub forex quote', async () => {
  const { stub } = makeFetchStub();
  globalThis.fetch = stub;
  const res = await worker.fetch(req('/'), ENV);
  const p = await body(res);
  // Finnhub OANDA:USD_CAD returns ~1.4268 CAD per USD; the Worker inverts it.
  const expected = 1 / 1.4268;
  assert.ok(Math.abs(p.stocks.USDCAD.c - expected) < 1e-9, `got ${p.stocks.USDCAD.c}, want ${expected}`);
  assert.ok(p.stocks.USDCAD.c > 0.69 && p.stocks.USDCAD.c < 0.72);
  assert.equal(p.stocks.USDCAD.src, 'Finnhub');
});

test('the five uncovered symbols are omitted and listed in missing (never fabricated)', async () => {
  const { stub } = makeFetchStub();
  globalThis.fetch = stub;
  const res = await worker.fetch(req('/'), ENV);
  const p = await body(res);
  for (const sym of ['WTI', 'GOLD', 'US10Y', 'VIX', 'DXY']) {
    assert.equal(p.stocks[sym], undefined, sym + ' must not be present');
    assert.ok(p.missing.includes(sym), sym + ' must be listed in missing');
  }
  assert.equal(Object.keys(p.stocks).length, 19);
});

// --- Caching ----------------------------------------------------------------

test('second call within the window does NOT hit Finnhub again', async () => {
  const { stub, calls } = makeFetchStub();
  globalThis.fetch = stub;
  await worker.fetch(req('/', { ip: '1.2.3.4' }), ENV);
  await worker.fetch(req('/', { ip: '5.6.7.8' }), ENV);
  await worker.fetch(req('/', { ip: '9.9.9.9' }), ENV);
  // 19 Finnhub calls once (first refresh), then zero — the cache serves the rest.
  assert.equal(calls.finnhub, 19);
  assert.equal(calls.coinbase, 1);
  assert.equal(calls.stats, 1);
  assert.equal(calls.gecko, 1);
});

// --- Fallback ---------------------------------------------------------------

test('Finnhub error serves last-good values with stale flags, never an error', async () => {
  const good = makeFetchStub();
  globalThis.fetch = good.stub;
  const first = await body(await worker.fetch(req('/'), ENV));
  assert.equal(first.stocks.AAPL.c, 261.74);
  assert.equal(first.stale, false);

  // Now Finnhub fails entirely. Expire the fresh cache so the Worker must
  // refresh — it must serve the last-good payload with stale:true.
  await __test.expireFresh();
  const failing = makeFetchStub({ finnhubOk: false, coinbaseOk: false, geckoOk: false });
  globalThis.fetch = failing.stub;
  const p = await body(await worker.fetch(req('/'), ENV));
  assert.equal(p.stocks.AAPL.c, 261.74, 'last-good AAPL must be served');
  assert.equal(p.btc.usd, 67280, 'last-good BTC must be served');
  assert.equal(p.stale, true);
});

test('one symbol fails while the rest succeed: only that symbol goes stale', async () => {
  const good = makeFetchStub();
  globalThis.fetch = good.stub;
  await worker.fetch(req('/'), ENV);

  // Expire fresh, then fail only NVDA.
  await __test.expireFresh();
  const partial = makeFetchStub({
    finnhubPrices: Object.fromEntries(
      Object.entries(FINNHUB_PRICES).filter(([k]) => k !== 'NVDA'),
    ),
  });
  globalThis.fetch = partial.stub;
  const p = await body(await worker.fetch(req('/'), ENV));
  assert.equal(p.stocks.NVDA.c, 180.0, 'last-good NVDA must be served');
  assert.deepEqual(p.staleSymbols, ['NVDA']);
  assert.equal(p.stale, true);
  assert.equal(p.stocks.AAPL.c, 261.74, 'fresh AAPL must be served');
});

test('no Finnhub API key configured: Finnhub symbols omitted, BTC still served', async () => {
  const { stub, calls } = makeFetchStub();
  globalThis.fetch = stub;
  const res = await worker.fetch(req('/'), {});
  const p = await body(res);
  assert.equal(calls.finnhub, 0, 'must not call Finnhub without a key');
  assert.equal(p.btc.usd, 67280);
  assert.equal(Object.keys(p.stocks).length, 0);
  for (const s of __test.symbols) assert.ok(p.missing.includes(s.key));
});

test('Coinbase fails: CoinGecko price is used; both fail: btc is null, never fabricated', async () => {
  // "Coinbase fails" means both Coinbase endpoints (spot + stats) are down,
  // so the 24h change must come from CoinGecko here.
  const noCoinbase = makeFetchStub({ coinbaseOk: false, statsOk: false });
  globalThis.fetch = noCoinbase.stub;
  let p = await body(await worker.fetch(req('/'), ENV));
  assert.equal(p.btc.usd, 67250);
  assert.equal(p.btc.src, 'CoinGecko');
  assert.equal(p.btc.chg24h, -4.59);

  __test.reset();
  const bothDown = makeFetchStub({ coinbaseOk: false, statsOk: false, geckoOk: false });
  globalThis.fetch = bothDown.stub;
  p = await body(await worker.fetch(req('/'), ENV));
  assert.equal(p.btc, null);
});

// --- BTC 24h change: Coinbase Exchange stats first, CoinGecko fallback ---
//
// Live, the CoinGecko fetch fails from the Worker's Cloudflare IP, so
// chg24h was null. The change now comes from Coinbase Exchange stats
// ((last - open) / open * 100), with CoinGecko as the fallback.

test('24h change comes from Coinbase stats when CoinGecko fails', async () => {
  const { stub } = makeFetchStub({ geckoOk: false });
  globalThis.fetch = stub;
  const p = await body(await worker.fetch(req('/'), ENV));
  assert.equal(p.btc.usd, 67280);
  assert.equal(p.btc.src, 'Coinbase');
  assert.ok(Math.abs(p.btc.chg24h - STATS_CHG24H) < 1e-9, `got ${p.btc.chg24h}, want ${STATS_CHG24H}`);
});

test('24h change falls back to CoinGecko when Coinbase stats fails', async () => {
  const { stub } = makeFetchStub({ statsOk: false });
  globalThis.fetch = stub;
  const p = await body(await worker.fetch(req('/'), ENV));
  assert.equal(p.btc.usd, 67280);
  assert.equal(p.btc.chg24h, -4.59);
});

test('stats and CoinGecko both fail: chg24h is null but the Coinbase spot price still serves', async () => {
  const { stub } = makeFetchStub({ statsOk: false, geckoOk: false });
  globalThis.fetch = stub;
  const p = await body(await worker.fetch(req('/'), ENV));
  assert.equal(p.btc.usd, 67280);
  assert.equal(p.btc.src, 'Coinbase');
  assert.equal(p.btc.chg24h, null);
});

test('stats with a zero open: no divide-by-zero — chg24h is null, never Infinity or NaN', async () => {
  const { stub } = makeFetchStub({ statsOpen: '0', geckoOk: false });
  globalThis.fetch = stub;
  const p = await body(await worker.fetch(req('/'), ENV));
  assert.equal(p.btc.usd, 67280);
  assert.equal(p.btc.chg24h, null);
});

test('stats with a zero open and CoinGecko up: chg24h falls back to CoinGecko', async () => {
  const { stub } = makeFetchStub({ statsOpen: '0' });
  globalThis.fetch = stub;
  const p = await body(await worker.fetch(req('/'), ENV));
  assert.equal(p.btc.chg24h, -4.59);
});

test('stats with a missing open: chg24h falls back to CoinGecko, never NaN', async () => {
  const { stub } = makeFetchStub({ statsOpen: null });
  globalThis.fetch = stub;
  const p = await body(await worker.fetch(req('/'), ENV));
  assert.equal(p.btc.chg24h, -4.59);
  assert.ok(Number.isFinite(p.btc.chg24h));
});

// --- BTC 24h change: last-good change + short TTL when it is null --------
//
// Nov 15: when both change sources (Coinbase stats + CoinGecko) fail, the
// Worker served chg24h null and cached it for the full 55s, so the pills
// showed no 24h change. Now the last good change is kept (in memory, and
// in the last-good cache for a cold isolate) and served instead, and a
// payload whose change is still null goes stale after a short TTL.

test('both change sources fail after a good fetch: last-good change is served, not null', async () => {
  const good = makeFetchStub();
  globalThis.fetch = good.stub;
  const first = await body(await worker.fetch(req('/'), ENV));
  assert.ok(Math.abs(first.btc.chg24h - STATS_CHG24H) < 1e-9, 'good fetch must carry the stats change');

  // Both change sources now fail (price still answers). Expire fresh so the
  // Worker must refresh — it must serve the last-good change.
  await __test.expireFresh();
  const failing = makeFetchStub({ statsOk: false, geckoOk: false });
  globalThis.fetch = failing.stub;
  const p = await body(await worker.fetch(req('/'), ENV));
  assert.equal(p.btc.usd, 67280, 'price still comes from Coinbase spot');
  assert.ok(Math.abs(p.btc.chg24h - STATS_CHG24H) < 1e-9, `got ${p.btc.chg24h}, want last-good ${STATS_CHG24H}`);
});

test('cold isolate: last-good change comes from the cache when memory is empty', async () => {
  const good = makeFetchStub();
  globalThis.fetch = good.stub;
  await worker.fetch(req('/'), ENV);

  // Simulate a cold isolate: memory cleared, cache still warm.
  __test.resetLastGoodChg();
  await __test.expireFresh();
  const failing = makeFetchStub({ statsOk: false, geckoOk: false });
  globalThis.fetch = failing.stub;
  const p = await body(await worker.fetch(req('/'), ENV));
  assert.equal(p.btc.usd, 67280);
  assert.ok(Math.abs(p.btc.chg24h - STATS_CHG24H) < 1e-9, `got ${p.btc.chg24h}, want cached last-good ${STATS_CHG24H}`);
});

test('no last-good anywhere: chg24h is null, and the null payload is cached within the short window', async () => {
  const { stub, calls } = makeFetchStub({ statsOk: false, geckoOk: false });
  globalThis.fetch = stub;
  const first = await body(await worker.fetch(req('/'), ENV));
  assert.equal(first.btc.usd, 67280);
  assert.equal(first.btc.chg24h, null, 'with no last-good value the change is null');

  // Immediate re-fetch serves the cached null payload (no new upstream
  // calls) — the short TTL only shortens how long it stays fresh.
  const callsBefore = { ...calls };
  const second = await body(await worker.fetch(req('/'), ENV));
  assert.equal(second.btc.chg24h, null);
  assert.deepEqual(calls, callsBefore, 'second request inside the window must not re-fetch upstream');
});

test('a null change goes stale after the short TTL, not the full window', async () => {
  assert.equal(__test.nullChgTtlSeconds, 15, 'short TTL for a null change must be 15s');
  assert.ok(__test.nullChgTtlSeconds < __test.cacheTtlSeconds, 'short TTL must be under the normal 55s window');
});

test('a good change restores the last-good value after a failure', async () => {
  // Good fetch, then a failing round (serves last-good), then a good round
  // again — the last-good value must be the fresh change, not the old one.
  const good = makeFetchStub();
  globalThis.fetch = good.stub;
  await worker.fetch(req('/'), ENV);

  await __test.expireFresh();
  const failing = makeFetchStub({ statsOk: false, geckoOk: false });
  globalThis.fetch = failing.stub;
  const mid = await body(await worker.fetch(req('/'), ENV));
  assert.ok(Math.abs(mid.btc.chg24h - STATS_CHG24H) < 1e-9);

  // Fresh stats with a different change (open 68000, last 67280).
  await __test.expireFresh();
  const changed = makeFetchStub({ statsOpen: '68000.00', statsLast: '67280.00' });
  globalThis.fetch = changed.stub;
  const p = await body(await worker.fetch(req('/'), ENV));
  const want = ((67280 - 68000) / 68000) * 100;
  assert.ok(Math.abs(p.btc.chg24h - want) < 1e-9, `got ${p.btc.chg24h}, want ${want}`);
});

// --- BTC 24h change: carried change expires after 10 minutes -------------
//
// Nov 15 r2 (Grok Bot must-fix): the last-good change was rewritten every
// round the price was fresh, even when the value was itself carried over,
// so a days-old change was served as current with stale:false (confirmed
// at +1h, +6h, +30h and after a cold start). A carried change is now
// reused only while it is at most 10 minutes old; past that, null is
// served so the 15s refresh and the page's CoinGecko fill take over.

test('a fresh change carries chgAt and chgStale:false', async () => {
  assert.equal(__test.lastGoodChgMaxAgeMs, 10 * 60 * 1000, 'carried-change cap must be 10 minutes');
  const { stub } = makeFetchStub();
  globalThis.fetch = stub;
  const p = await body(await worker.fetch(req('/'), ENV));
  assert.ok(Math.abs(p.btc.chg24h - STATS_CHG24H) < 1e-9);
  assert.equal(typeof p.btc.chgAt, 'string', 'a fresh change must carry chgAt');
  assert.ok(!Number.isNaN(Date.parse(p.btc.chgAt)), 'chgAt must be a parseable timestamp');
  assert.equal(p.btc.chgStale, false, 'a fresh change is not stale');
});

test('a carried change within the cap is served and marked stale, chgAt not refreshed', async () => {
  const good = makeFetchStub();
  globalThis.fetch = good.stub;
  const first = await body(await worker.fetch(req('/'), ENV));
  assert.ok(Math.abs(first.btc.chg24h - STATS_CHG24H) < 1e-9, 'good fetch must carry the stats change');
  assert.equal(first.btc.chgStale, false);

  // Both change sources now fail (price still answers). Expire fresh so the
  // Worker must refresh — it must serve the carried change, marked stale.
  await __test.expireFresh();
  const failing = makeFetchStub({ statsOk: false, geckoOk: false });
  globalThis.fetch = failing.stub;
  const p = await body(await worker.fetch(req('/'), ENV));
  assert.equal(p.btc.usd, 67280, 'price still comes from Coinbase spot');
  assert.ok(Math.abs(p.btc.chg24h - STATS_CHG24H) < 1e-9, `got ${p.btc.chg24h}, want carried ${STATS_CHG24H}`);
  assert.equal(p.btc.chgStale, true, 'a carried change must be marked stale');
  assert.equal(p.btc.chgAt, first.btc.chgAt, 'a carried change must not refresh chgAt');
});

test('a carried change older than the cap returns null (in-memory and cold-start)', async () => {
  const good = makeFetchStub();
  globalThis.fetch = good.stub;
  const first = await body(await worker.fetch(req('/'), ENV));
  assert.ok(Math.abs(first.btc.chg24h - STATS_CHG24H) < 1e-9, 'good fetch must carry the stats change');

  // Age both the in-memory last-good change and the cached copy past the
  // cap, so neither the carried path nor the cold-start fill may reuse it.
  const aged = Date.now() - __test.lastGoodChgMaxAgeMs - 60_000;
  __test.setLastGoodChg(STATS_CHG24H, aged);
  await __test.setLastGoodCacheChgAt(new Date(aged).toISOString());

  // Both change sources now fail (price still answers). Expire fresh so the
  // Worker must refresh — it must serve null, not the expired change.
  await __test.expireFresh();
  const failing = makeFetchStub({ statsOk: false, geckoOk: false });
  globalThis.fetch = failing.stub;
  const p = await body(await worker.fetch(req('/'), ENV));
  assert.equal(p.btc.usd, 67280, 'price still comes from Coinbase spot');
  assert.equal(p.btc.chg24h, null, 'an expired carried change must not be served');
});

// --- BTC stale-price branch: the carried change AND the carried price expire
//
// Nov 15 r3 (Grok Bot round-2 must-fix + should-fix #1): when no price
// source answers, the Worker served lastGood.btc whole, so its old change
// skipped the 10-minute cap (served at +1h, +6h, +30h with chgStale:false,
// and old cache entries with no chgAt did the same). The carried change is
// now capped in that branch too. And a carried price older than ~10
// minutes is not served at all — the pages fetch the price directly.

test('stale-price branch: all sources down and chgAt older than the cap returns chg24h null, price still served', async () => {
  const good = makeFetchStub();
  globalThis.fetch = good.stub;
  const first = await body(await worker.fetch(req('/'), ENV));
  assert.ok(Math.abs(first.btc.chg24h - STATS_CHG24H) < 1e-9, 'good fetch must carry the stats change');

  // Age only the change in the last-good cache past the cap; the price
  // itself is still fresh, so it must be carried — but without a change.
  const aged = Date.now() - __test.lastGoodChgMaxAgeMs - 60_000;
  await __test.setLastGoodCacheChgAt(new Date(aged).toISOString());

  // All BTC price and change sources now fail. Expire fresh so the Worker
  // must refresh from the last-good cache.
  await __test.expireFresh();
  const failing = makeFetchStub({ coinbaseOk: false, statsOk: false, geckoOk: false });
  globalThis.fetch = failing.stub;
  const p = await body(await worker.fetch(req('/'), ENV));
  assert.equal(p.btc.usd, 67280, 'a fresh carried price must still be served');
  assert.equal(p.btc.chg24h, null, 'an expired carried change must not ride along with the price');
  assert.equal(p.btc.chgStale, true, 'a carried value is marked stale');
});

test('stale-price branch: chgAt missing from the cache returns chg24h null', async () => {
  const good = makeFetchStub();
  globalThis.fetch = good.stub;
  await worker.fetch(req('/'), ENV);

  // Drop chgAt from the cached entry (old cache entries predate it).
  // JSON.stringify drops undefined, so the stored entry has no chgAt.
  await __test.setLastGoodCacheChgAt(undefined);

  await __test.expireFresh();
  const failing = makeFetchStub({ coinbaseOk: false, statsOk: false, geckoOk: false });
  globalThis.fetch = failing.stub;
  const p = await body(await worker.fetch(req('/'), ENV));
  assert.equal(p.btc.usd, 67280, 'a fresh carried price must still be served');
  assert.equal(p.btc.chg24h, null, 'a carried change with no timestamp must not be served');
});

test('stale-price branch: a carried price older than ~10 minutes is not served (btc null)', async () => {
  const good = makeFetchStub();
  globalThis.fetch = good.stub;
  await worker.fetch(req('/'), ENV);

  // Age the cached price past the cap.
  const aged = Date.now() - __test.lastGoodChgMaxAgeMs - 60_000;
  await __test.setLastGoodCachePriceAt(new Date(aged).toISOString());

  // All BTC sources down. Expire fresh so the Worker must refresh.
  await __test.expireFresh();
  const failing = makeFetchStub({ coinbaseOk: false, statsOk: false, geckoOk: false });
  globalThis.fetch = failing.stub;
  const p = await body(await worker.fetch(req('/'), ENV));
  assert.equal(p.btc, null, 'an expired carried price must not be served — the pages fetch directly');
});

// --- BTC stale-price branch, round 4: no fallback to time -----------------
//
// Nov 15 r4 (Grok Bot round-3 must-fix): old cache entries have no
// priceAt, so the code fell back to time. The old Worker refreshed time
// on every save, so during a full BTC-source outage a days-old price
// could look 0–1 min old and get served for up to 10 min right after
// deploy. The branch now uses priceAt only; a missing priceAt means the
// price is expired (btc null), however fresh time looks.

test('stale-price branch: a cache entry with no priceAt and time = now returns btc null', async () => {
  const good = makeFetchStub();
  globalThis.fetch = good.stub;
  await worker.fetch(req('/'), ENV);

  // Simulate an old cache entry: no priceAt, but time refreshed to now.
  await __test.dropLastGoodCachePriceAt();

  // All BTC sources down. Expire fresh so the Worker must refresh.
  await __test.expireFresh();
  const failing = makeFetchStub({ coinbaseOk: false, statsOk: false, geckoOk: false });
  globalThis.fetch = failing.stub;
  const p = await body(await worker.fetch(req('/'), ENV));
  assert.equal(p.btc, null, 'a carried price with no priceAt must not be served, even with a fresh time');
});

test('stale-price branch: a carried price 9 minutes old is still served', async () => {
  const good = makeFetchStub();
  globalThis.fetch = good.stub;
  await worker.fetch(req('/'), ENV);

  // Age the cached price to 9 minutes — inside the ~10 min cap.
  const nineMin = Date.now() - 9 * 60 * 1000;
  await __test.setLastGoodCachePriceAt(new Date(nineMin).toISOString());

  // All BTC sources down. Expire fresh so the Worker must refresh.
  await __test.expireFresh();
  const failing = makeFetchStub({ coinbaseOk: false, statsOk: false, geckoOk: false });
  globalThis.fetch = failing.stub;
  const p = await body(await worker.fetch(req('/'), ENV));
  assert.equal(p.btc.usd, 67280, 'a carried price inside the cap must still be served');
  assert.equal(p.btc.chgStale, true, 'a carried value is marked stale');
});

test('a fresh price carries priceAt, and time is the capture time', async () => {
  const { stub } = makeFetchStub();
  globalThis.fetch = stub;
  const p = await body(await worker.fetch(req('/'), ENV));
  assert.equal(typeof p.btc.priceAt, 'string', 'a fresh price must carry priceAt');
  assert.ok(!Number.isNaN(Date.parse(p.btc.priceAt)), 'priceAt must be a parseable timestamp');
  assert.equal(p.btc.time, p.btc.priceAt, 'time must be the price capture time, not the payload build time');
});

test('Finnhub returns an empty quote for a symbol: it is omitted, not priced at 0', async () => {
  const { stub } = makeFetchStub({
    finnhubPrices: Object.fromEntries(
      Object.entries(FINNHUB_PRICES).filter(([k]) => k !== 'NVDA'),
    ),
  });
  globalThis.fetch = stub;
  // Prime last-good with the full set first, then reset the fresh cache only
  // is not exposed — so instead: fresh fetch with NVDA missing from the
  // stub must omit NVDA (no last-good exists yet on a cold cache).
  __test.reset();
  const p = await body(await worker.fetch(req('/'), ENV));
  assert.equal(p.stocks.NVDA, undefined);
  assert.ok(p.missing.includes('NVDA'));
  assert.equal(p.stocks.AAPL.c, 261.74);
});

// --- CORS -------------------------------------------------------------------

test('CORS: paperstreetbtc.com allowed, other origins rejected, localhost allowed', async () => {
  const { stub } = makeFetchStub();
  globalThis.fetch = stub;

  let res = await worker.fetch(req('/', { origin: 'https://paperstreetbtc.com' }), ENV);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get('Access-Control-Allow-Origin'), 'https://paperstreetbtc.com');

  res = await worker.fetch(req('/', { origin: 'https://evil.example.com' }), ENV);
  assert.equal(res.status, 403);

  res = await worker.fetch(req('/', { origin: 'http://localhost:8787' }), ENV);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get('Access-Control-Allow-Origin'), 'http://localhost:8787');

  // No Origin header (curl / server-to-server): allowed, no CORS headers.
  res = await worker.fetch(req('/'), ENV);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get('Access-Control-Allow-Origin'), null);

  // Preflight from an allowed origin.
  res = await worker.fetch(req('/', { origin: 'https://paperstreetbtc.com', method: 'OPTIONS' }), ENV);
  assert.equal(res.status, 204);
  assert.equal(res.headers.get('Access-Control-Allow-Origin'), 'https://paperstreetbtc.com');
});

// --- Rate limiting ----------------------------------------------------------

test('rate limiting: more than 30 requests/min from one IP gets 429', async () => {
  const { stub } = makeFetchStub();
  globalThis.fetch = stub;
  const ip = '10.0.0.1';
  let last;
  for (let i = 0; i < 31; i++) {
    last = await worker.fetch(req('/', { ip }), ENV);
  }
  assert.equal(last.status, 429);
  assert.equal(last.headers.get('Retry-After'), '60');
  // A different IP is unaffected.
  const other = await worker.fetch(req('/', { ip: '10.0.0.2' }), ENV);
  assert.equal(other.status, 200);
});

// --- Routes -----------------------------------------------------------------

test('/health never touches an upstream provider', async () => {
  const { stub, calls } = makeFetchStub();
  globalThis.fetch = stub;
  const res = await worker.fetch(req('/health'), ENV);
  assert.equal(res.status, 200);
  assert.equal((await body(res)).ok, true);
  assert.equal(calls.finnhub, 0);
  assert.equal(calls.coinbase, 0);
  assert.equal(calls.stats, 0);
  assert.equal(calls.gecko, 0);
});

test('unknown route is 404, non-GET is 405', async () => {
  const { stub } = makeFetchStub();
  globalThis.fetch = stub;
  assert.equal((await worker.fetch(req('/nope'), ENV)).status, 404);
  assert.equal((await worker.fetch(req('/', { method: 'POST' }), ENV)).status, 405);
});

// --- Stage 2 analytics: POST /err + GET /err ------------------------------
//
// The Worker never runs against a real D1 in tests: FakeD1 below is an
// in-memory stand-in implementing exactly the statements index.js uses
// (prepare/bind/run/all/first). The read secret here is a placeholder,
// the same pattern as FINNHUB_API_KEY above.

class FakeD1 {
  constructor() {
    this.rows = [];
    this.nextId = 1;
  }
  prepare(sql) {
    const self = this;
    const stmt = {
      bind(...params) {
        return {
          async run() { return self._run(sql, params); },
          async all() { return { results: self._all(sql, params) }; },
          async first() { return self._first(sql, params); },
        };
      },
      async run() { return self._run(sql, []); },
      async all() { return { results: self._all(sql, []) }; },
      async first() { return self._first(sql, []); },
    };
    return stmt;
  }
  _run(sql, p) {
    if (sql.startsWith('INSERT INTO errors')) {
      const [ts, path, message, file, line, browser, device, pin, kind, src] = p;
      this.rows.push({ id: this.nextId++, ts, path, message, file, line, browser, device, pin, kind, src });
      return { success: true };
    }
    if (sql.startsWith('DELETE FROM errors WHERE ts <')) {
      const cutoff = p[0];
      this.rows = this.rows.filter((r) => !(r.ts < cutoff));
      return { success: true };
    }
    if (sql.startsWith('DELETE FROM errors WHERE id IN')) {
      const limit = p[0];
      const sorted = [...this.rows].sort((a, b) => (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : a.id - b.id));
      const drop = new Set(sorted.slice(0, limit).map((r) => r.id));
      this.rows = this.rows.filter((r) => !drop.has(r.id));
      return { success: true };
    }
    throw new Error('fake D1: unhandled run: ' + sql);
  }
  _all(sql, p) {
    if (sql.includes('GROUP BY message')) {
      const since = p[0];
      const groups = new Map();
      for (const r of this.rows) {
        if (r.ts < since) continue;
        const g = groups.get(r.message) || { message: r.message, n: 0, last: '', path: '' };
        g.n += 1;
        if (r.ts >= g.last) { g.last = r.ts; g.path = r.path; }
        groups.set(r.message, g);
      }
      return [...groups.values()].sort((a, b) => b.n - a.n).slice(0, 10);
    }
    if (sql.includes('ORDER BY ts DESC LIMIT 50')) {
      const since = p[0];
      return this.rows
        .filter((r) => r.ts >= since)
        .sort((a, b) => (a.ts < b.ts ? 1 : a.ts > b.ts ? -1 : b.id - a.id))
        .slice(0, 50);
    }
    if (sql.includes('GROUP BY src')) {
      const since = p[0];
      const groups = new Map();
      for (const r of this.rows) {
        if (r.ts < since) continue;
        const k = r.src === null || r.src === undefined ? null : r.src;
        groups.set(k, (groups.get(k) || 0) + 1);
      }
      return [...groups.entries()].map(([src, n]) => ({ src, n })).sort((a, b) => b.n - a.n);
    }
    throw new Error('fake D1: unhandled all: ' + sql);
  }
  _first(sql, p) {
    if (sql.startsWith('SELECT COUNT(*) AS n FROM errors')) {
      if (p.length === 0) return { n: this.rows.length };
      const since = p[0];
      return { n: this.rows.filter((r) => r.ts >= since).length };
    }
    throw new Error('fake D1: unhandled first: ' + sql);
  }
}

function errEnv(db) {
  return { FINNHUB_API_KEY: 'test-key-placeholder', ERR_READ_SECRET: 'test-read-secret', ERR_DB: db };
}

function errPayload(over = {}) {
  return JSON.stringify({
    path: '/screener.html', message: 'boom', file: 'btcchart.js', line: 12,
    browser: 'Safari', device: 'phone', pin: 'err1', kind: 'onerror', src: 'x', ...over,
  });
}

function errReq({ origin = 'https://paperstreetbtc.com', ip = '1.2.3.4', body = null, contentType = 'text/plain' } = {}) {
  const headers = new Headers();
  if (origin) headers.set('Origin', origin);
  if (ip) headers.set('CF-Connecting-IP', ip);
  if (contentType) headers.set('Content-Type', contentType);
  return new Request('https://paperstreet-quotes.workers.dev/err', { method: 'POST', headers, body });
}

function errReadReq({ secret = 'test-read-secret', origin = undefined, days = undefined } = {}) {
  const headers = new Headers();
  if (secret) headers.set('Authorization', `Bearer ${secret}`);
  if (origin !== undefined) headers.set('Origin', origin);
  const qs = days === undefined ? '' : `?days=${days}`;
  return new Request(`https://paperstreet-quotes.workers.dev/err${qs}`, { method: 'GET', headers });
}

test('POST /err happy path: 204, row stored, read endpoint shows it with src', async () => {
  const db = new FakeD1();
  const env = errEnv(db);
  const res = await worker.fetch(errReq({ body: errPayload() }), env);
  assert.equal(res.status, 204);
  assert.equal(res.headers.get('Access-Control-Allow-Origin'), 'https://paperstreetbtc.com');
  assert.equal(res.headers.get('Cache-Control'), null, 'no quotes max-age=15 on /err');
  assert.equal(db.rows.length, 1);
  assert.equal(db.rows[0].path, '/screener.html');
  assert.equal(db.rows[0].message, 'boom');
  assert.equal(db.rows[0].src, 'x');

  const read = await worker.fetch(errReadReq({}), env);
  assert.equal(read.status, 200);
  const p = await body(read);
  assert.equal(p.ok, true);
  assert.equal(p.days, 7);
  assert.equal(p.count, 1);
  assert.equal(p.top.length, 1);
  assert.equal(p.top[0].message, 'boom');
  assert.equal(p.top[0].count, 1);
  assert.equal(p.top[0].path, '/screener.html');
  assert.equal(p.recent.length, 1);
  assert.equal(p.recent[0].kind, 'onerror');
  assert.equal(p.recent[0].browser, 'Safari');
  assert.equal(p.recent[0].device, 'phone');
  assert.equal(p.recent[0].src, 'x');
  assert.deepEqual(p.bySrc, [{ src: 'x', count: 1 }]);
  assert.equal(read.headers.get('Cache-Control'), 'no-store');
});

test('POST /err: bad or missing origin is 403, localhost is allowed', async () => {
  const db = new FakeD1();
  const env = errEnv(db);
  assert.equal((await worker.fetch(errReq({ origin: 'https://evil.example.com', body: errPayload() }), env)).status, 403);
  assert.equal((await worker.fetch(errReq({ origin: '', body: errPayload() }), env)).status, 403);
  assert.equal(db.rows.length, 0, 'rejected reports must not be stored');
  const ok = await worker.fetch(errReq({ origin: 'http://localhost:8787', body: errPayload() }), env);
  assert.equal(ok.status, 204);
  assert.equal(db.rows.length, 1);
});

test('POST /err: oversized body is 413, invalid JSON is 400, bad report is 400', async () => {
  const db = new FakeD1();
  const env = errEnv(db);
  const big = await worker.fetch(errReq({ body: 'x'.repeat(2049) }), env);
  assert.equal(big.status, 413);
  const badJson = await worker.fetch(errReq({ body: '{not json' }), env);
  assert.equal(badJson.status, 400);
  const badPath = await worker.fetch(errReq({ body: errPayload({ path: 'https://evil.example.com/x' }) }), env);
  assert.equal(badPath.status, 400);
  const badKind = await worker.fetch(errReq({ body: errPayload({ kind: 'explode' }) }), env);
  assert.equal(badKind.status, 400);
  const queryPath = await worker.fetch(errReq({ body: errPayload({ path: '/screener.html?x=1' }) }), env);
  assert.equal(queryPath.status, 400);
  assert.equal(db.rows.length, 0);
});

test('POST /err: unknown fields dropped, file is basenamed, enums defaulted', async () => {
  const db = new FakeD1();
  const env = errEnv(db);
  const res = await worker.fetch(
    errReq({ body: errPayload({ file: 'https://paperstreetbtc.com/assets/js/btcchart.js?v=wr14', browser: 'Lynx', device: 'toaster', userAgent: 'secret-ua', ip: '1.2.3.4' }) }),
    env,
  );
  assert.equal(res.status, 204);
  const row = db.rows[0];
  assert.equal(row.file, 'btcchart.js', 'file must be a basename with the query stripped');
  assert.equal(row.browser, 'Other', 'unknown browser defaults to Other');
  assert.equal(row.device, 'desktop', 'unknown device defaults to desktop');
  assert.equal(row.userAgent, undefined, 'raw UA must never be stored');
  assert.equal(row.ip, undefined, 'IP must never be stored');
});

test('POST /err rate limit: 5/min per IP, 6th is 429, other IP unaffected', async () => {
  const db = new FakeD1();
  const env = errEnv(db);
  let last;
  for (let i = 0; i < 6; i++) {
    last = await worker.fetch(errReq({ ip: '10.1.1.1', body: errPayload({ message: 'm' + i }) }), env);
  }
  assert.equal(last.status, 429);
  assert.equal(last.headers.get('Retry-After'), '60');
  assert.equal(db.rows.length, 5, 'only the first 5 posts are stored');
  const other = await worker.fetch(errReq({ ip: '10.1.1.2', body: errPayload() }), env);
  assert.equal(other.status, 204, 'a different IP is unaffected');
});

test('POST /err with D1 down still returns 204', async () => {
  const env = { FINNHUB_API_KEY: 'test-key-placeholder', ERR_READ_SECRET: 'test-read-secret' };
  const res = await worker.fetch(errReq({ body: errPayload() }), env);
  assert.equal(res.status, 204);
});

test('POST /err: old rows pruned (30 days) and table capped at 5,000', async () => {
  const db = new FakeD1();
  const env = errEnv(db);
  const oldTs = new Date(Date.now() - 40 * 24 * 60 * 60 * 1000).toISOString();
  db.rows.push({ id: db.nextId++, ts: oldTs, path: '/old', message: 'old', file: '', line: 0, browser: 'Other', device: 'desktop', pin: 'err1', kind: 'onerror', src: null });
  const res = await worker.fetch(errReq({ body: errPayload() }), env);
  assert.equal(res.status, 204);
  assert.equal(db.rows.length, 1, 'the 40-day-old row must be pruned');
  assert.equal(db.rows[0].message, 'boom');

  // Flood the table past the cap, then post once: it must shrink to 5,000.
  const now = new Date().toISOString();
  for (let i = 0; i < 5002; i++) {
    db.rows.push({ id: db.nextId++, ts: now, path: '/flood', message: 'flood', file: '', line: 0, browser: 'Other', device: 'desktop', pin: 'err1', kind: 'onerror', src: null });
  }
  await worker.fetch(errReq({ ip: '9.9.9.9', body: errPayload({ message: 'after-flood' }) }), env);
  assert.equal(db.rows.length, 5000, 'the table must be capped at 5,000 rows');
  assert.ok(db.rows.some((r) => r.message === 'after-flood'), 'the new row must survive the cap');
});

test('GET /err: right secret returns the shape, count 0 is a valid week', async () => {
  const db = new FakeD1();
  const env = errEnv(db);
  const res = await worker.fetch(errReadReq({}), env);
  assert.equal(res.status, 200);
  const p = await body(res);
  assert.deepEqual(p, { ok: true, days: 7, count: 0, top: [], recent: [], bySrc: [] });
});

test('GET /err: no secret is 401, wrong secret is 401, secret not configured is 500', async () => {
  const db = new FakeD1();
  const env = errEnv(db);
  assert.equal((await worker.fetch(errReadReq({ secret: '' }), env)).status, 401);
  assert.equal((await worker.fetch(errReadReq({ secret: 'wrong-secret' }), env)).status, 401);
  const noSecretEnv = { FINNHUB_API_KEY: 'test-key-placeholder', ERR_DB: db };
  assert.equal((await worker.fetch(errReadReq({}), noSecretEnv)).status, 500);
  const noDbEnv = { FINNHUB_API_KEY: 'test-key-placeholder', ERR_READ_SECRET: 'test-read-secret' };
  assert.equal((await worker.fetch(errReadReq({}), noDbEnv)).status, 500);
});

test('GET /err: days param clamps to 1..30, no CORS headers even with an Origin', async () => {
  const db = new FakeD1();
  const env = errEnv(db);
  const p30 = await body(await worker.fetch(errReadReq({ days: 99 }), env));
  assert.equal(p30.days, 30);
  const p1 = await body(await worker.fetch(errReadReq({ days: 0 }), env));
  assert.equal(p1.days, 1);
  const res = await worker.fetch(errReadReq({ origin: 'https://evil.example.com' }), env);
  assert.equal(res.status, 200, 'the read route is not origin-gated');
  assert.equal(res.headers.get('Access-Control-Allow-Origin'), null, 'no CORS on the read route');
});

test('OPTIONS allows POST now, and POST / is still 405', async () => {
  const { stub } = makeFetchStub();
  globalThis.fetch = stub;
  const env = errEnv(new FakeD1());
  const pre = await worker.fetch(req('/', { origin: 'https://paperstreetbtc.com', method: 'OPTIONS' }), env);
  assert.equal(pre.status, 204);
  assert.ok((pre.headers.get('Access-Control-Allow-Methods') || '').includes('POST'), 'OPTIONS must list POST for /err');
  assert.equal((await worker.fetch(req('/', { method: 'POST' }), env)).status, 405);
  assert.equal((await worker.fetch(req('/err', { method: 'POST' }), env)).status, 403, 'POST /err without an origin is 403, not 405');
});

test('/err does not change the quote routes or their CORS', async () => {
  const { stub } = makeFetchStub();
  globalThis.fetch = stub;
  const env = errEnv(new FakeD1());
  const post = await worker.fetch(errReq({ body: errPayload() }), env);
  assert.equal(post.status, 204);
  const q = await worker.fetch(req('/', { origin: 'https://paperstreetbtc.com' }), env);
  assert.equal(q.status, 200);
  const p = await body(q);
  assert.equal(p.btc.usd, 67280);
  assert.equal(q.headers.get('Access-Control-Allow-Origin'), 'https://paperstreetbtc.com');
  const h = await worker.fetch(req('/health'), env);
  assert.equal(h.status, 200);
  assert.equal((await body(h)).ok, true);
});

// --- Stage 3: POST /ev (event analytics) ------------------------------------

test('POST /ev happy path writes one data point and answers 204', async () => {
  const events = makeEventsStub();
  const res = await worker.fetch(evReq('desk_open', '/screener.html', 'x'), envWithEvents(events));
  assert.equal(res.status, 204);
  assert.equal(res.headers.get('Access-Control-Allow-Origin'), EV_ORIGIN);
  assert.equal(events.calls.length, 1);
  assert.deepEqual(events.calls[0].blobs, ['desk_open', '/screener.html', 'x']);
  assert.deepEqual(events.calls[0].doubles, [1]);
  assert.deepEqual(events.calls[0].indexes, ['desk_open']);
});

test('POST /ev without src writes an empty src blob', async () => {
  const events = makeEventsStub();
  const res = await worker.fetch(evReq('xfollow', '/'), envWithEvents(events));
  assert.equal(res.status, 204);
  assert.equal(events.calls.length, 1);
  assert.deepEqual(events.calls[0].blobs, ['xfollow', '/', '']);
});

test('POST /ev rejects a missing or disallowed origin with 403 and writes nothing', async () => {
  const events = makeEventsStub();
  const env = envWithEvents(events);
  // No Origin header at all.
  let res = await worker.fetch(req('/ev', { method: 'POST', body: JSON.stringify({ event: 'desk_open', page: '/' }) }), env);
  assert.equal(res.status, 403);
  // Disallowed origin.
  res = await worker.fetch(evReq('desk_open', '/', undefined, { origin: 'https://evil.example.com' }), env);
  assert.equal(res.status, 403);
  assert.equal(events.calls.length, 0);
});

test('POST /ev rejects a bad event, bad page, bad JSON, and oversized body', async () => {
  const events = makeEventsStub();
  const env = envWithEvents(events);
  // Unknown event name.
  let res = await worker.fetch(evReq('nope', '/', undefined), env);
  assert.equal(res.status, 400);
  // Page without a leading slash.
  res = await worker.fetch(evReq('desk_open', 'screener.html'), env);
  assert.equal(res.status, 400);
  // Page with a query string.
  res = await worker.fetch(evReq('desk_open', '/screener.html?x=1'), env);
  assert.equal(res.status, 400);
  // Not JSON.
  res = await worker.fetch(req('/ev', { origin: EV_ORIGIN, method: 'POST', body: 'not json' }), env);
  assert.equal(res.status, 400);
  // Oversized body (> 2 KB).
  res = await worker.fetch(
    req('/ev', { origin: EV_ORIGIN, method: 'POST', body: JSON.stringify({ event: 'desk_open', page: '/', pad: 'x'.repeat(3000) }) }),
    env,
  );
  assert.equal(res.status, 413);
  assert.equal(events.calls.length, 0);
});

test('POST /ev with an invalid src drops the tag but still records the event', async () => {
  const events = makeEventsStub();
  const res = await worker.fetch(evReq('range_switch', '/clock/', 'bad src!'), envWithEvents(events));
  assert.equal(res.status, 204);
  assert.equal(events.calls.length, 1);
  assert.deepEqual(events.calls[0].blobs, ['range_switch', '/clock/', '']);
});

test('POST /ev without the Analytics Engine binding still answers 204', async () => {
  // No EVENTS in env (local test without the binding): the write is
  // skipped, the send still succeeds.
  const res = await worker.fetch(evReq('desk_open', '/screener.html', 'x'), ENV);
  assert.equal(res.status, 204);
});

test('POST /ev rate limit: more than 30/min from one IP gets 429', async () => {
  const events = makeEventsStub();
  const env = envWithEvents(events);
  const ip = '10.0.0.9';
  let last;
  for (let i = 0; i < 31; i++) {
    last = await worker.fetch(evReq('desk_open', '/screener.html', undefined, { ip }), env);
  }
  assert.equal(last.status, 429);
  assert.equal(last.headers.get('Retry-After'), '60');
  assert.equal(events.calls.length, 30);
  // A different IP is unaffected, and quotes are unaffected too.
  const other = await worker.fetch(evReq('desk_open', '/screener.html', undefined, { ip: '10.0.0.10' }), env);
  assert.equal(other.status, 204);
});

test('POST / is still 405, GET /ev is 405, unknown route is still 404', async () => {
  const events = makeEventsStub();
  const env = envWithEvents(events);
  assert.equal((await worker.fetch(req('/', { method: 'POST' }), env)).status, 405);
  assert.equal((await worker.fetch(req('/ev', { origin: EV_ORIGIN }), env)).status, 405);
  assert.equal((await worker.fetch(req('/nope'), env)).status, 404);
  assert.equal(events.calls.length, 0);
});

test('OPTIONS preflight allows POST', async () => {
  const res = await worker.fetch(req('/', { origin: EV_ORIGIN, method: 'OPTIONS' }), ENV);
  assert.equal(res.status, 204);
  assert.ok(res.headers.get('Access-Control-Allow-Methods').includes('POST'));
});
