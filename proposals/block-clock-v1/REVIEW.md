# Bitcoin block clock V1 — REVIEW (Saturday)

**Sunil + Pepper work, for Grok Bot + Chief of Staff peer review on Saturday.**
**Test branch only. Nothing here is live. Live only from the Grok side, after
Sunil's yes, one item at a time.**

## What it is
Version 1 of the block clock, built from the dazzled mockup Sunil approved
on 2 Nov (`bitcoin-block-clock-mockup.html`) and added to the Saturday batch
on 4 Nov. It is a real, self-updating page — not a mockup — with the mockup's
features, live:

- Live BTC price + 24h change (CoinGecko, Coinbase fallback), green/red glow
  flash on moves, 24h sparkline (CoinGecko market_chart)
- Scrolling ticker (price + sats per dollar + block height)
- Auto-rotating focus screens every 12s: block height with a ring gauge
  against the 10-minute target, sats per dollar, next halving (progress bar),
  network (fastest fee + mempool unconfirmed count + difficulty-adjustment
  progress) — all from mempool.space
- Sats per $10 / $100, pause-rotation + Refresh now controls
- Last-good-value behaviour on feed failure: it never invents a number
- Wording: "sats per dollar" throughout. The term "Moscow time" appears
  nowhere on the page (Sunil's preference, 2 Nov).

## The secret link (Sunil, 4 Nov)
The clock page lives at `/clock/` but is **not linked from anywhere on the
site** — no header, footer, nav, or sitemap entry points to it. The only
way in, besides typing the address, is the secret trigger:

- In the Bitcoin popup chart (the BTC pill popover, any page), **double-click
  anywhere on the Bitcoin price** (the price + 24h change line at the top of
  the popover). That opens `/clock/` in a new tab.
- There is deliberately no visible hint, label, or tooltip for this on the
  popover. The clock page itself has a "Back to PaperStreet" link at the
  bottom, and a note saying it is not linked from the rest of the site.
- A single click still does what it always did (nothing, on the price line);
  the popover's close behaviour (✕, dim click, Escape, swipe down on the
  phone sheet) is unchanged.

## Files changed
- `clock/index.html` (new) — the whole clock page, self-contained
  (inline styles + script, same as the mockup it was built from).
- `assets/js/btcchart.js` — one dblclick listener on the popover's
  `.bc-px` price line, opening `../../clock/index.html` in a new tab.
  Nothing else in the popover changed.
- `index.html`, `screener.html` — btcchart pin et5 → et6 (script changed).
- `compare/index.html`, `custom/index.html`, `recap/index.html`,
  `recap/2026-*/index.html` — btcchart pin et1 → et2 (same reason).

## Deliberately NOT changed
- No homepage hero, no screener change, no nav/header/footer link to
  `/clock/` (that is the point of the secret link).
- No pipeline, ledger, history, or vehicle changes. The clock reads public
  feeds in the browser only; it writes nothing to the repo.
- This branch does **not** include the BTC pill-expand morph
  (`pepper-btc-pill-expand`) or the screener popover fix
  (`pepper-screener-btc-fix`): all three touch btcchart.js in different
  places (this one: a dblclick listener in build(); pill-expand: open/close;
  screener fix: the drawDaily note), so they should merge cleanly, and all
  three already use pin et6 on index/screener. If either lands first,
  rebase this branch onto it and re-check the popover.

## Checks done by Pepper (pre-review)
- `node --check assets/js/btcchart.js` passes.
- Browser check on this branch (githack, exact commit SHA): the clock page
  loads with live price / block height / sats figures (or last-good values
  with a feed-failure note, never invented numbers); opening the homepage
  pill popover and double-clicking the price opens `/clock/` in a new tab;
  a single click on the price does nothing new. (Filled in after the check
  runs — see verification note below.)

## Checks still for Grok Bot (before deploy)
1. Read the diff, not just this note.
2. Browser-check the branch at phone width (390px): the clock page reads
   cleanly, and the popover price double-click still opens the clock.
3. Confirm the secret-link behaviour is what Sunil wants (no hint, new tab)
   and that the clock page's "not linked" note is acceptable.
4. Merge order with `pepper-btc-pill-expand` and `pepper-screener-btc-fix`
   (see above), then one live check after deploy, with a rollback line
   (remove `clock/` and revert the btcchart listener + pin bumps).
