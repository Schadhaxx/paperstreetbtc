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

function req(path = '/', { origin, ip = '1.2.3.4', method = 'GET' } = {}) {
  const headers = new Headers();
  if (origin !== undefined) headers.set('Origin', origin);
  if (ip) headers.set('CF-Connecting-IP', ip);
  return new Request(`https://paperstreet-quotes.workers.dev${path}`, { method, headers });
}

async function body(res) {
  return JSON.parse(await res.text());
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
