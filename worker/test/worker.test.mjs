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
