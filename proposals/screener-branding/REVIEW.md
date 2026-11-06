# Screener branding — REVIEW

Branch: `pepper-screener-branding` · Base: main `dd71e0d`.

## What this is

The maple-leaf screener page had no PaperStreet identity on it at all — its
header was just "Your watchlist, at a glance." It now opens with the site's
brand, matching the homepage header: the owl (`assets/img/owl-220.png` /
`.webp`, the site logo) + "Paperstreet" with an orange "BTC" badge.

## Changes

- `screener.html` only. A `.brand-row` div is the first child of `<header>`,
  above the h1. Its CSS lives in the page's own `<style>` block (the
  screener does not load `styles.css`, so the homepage's `.logo` /
  `.brand-text` classes were not reused — the rules are copied in
  self-contained form). No data, JS, or behaviour change; nothing else on
  the page moves.

## Merge notes (for Grok Bot)

- This branch is based on main `dd71e0d` and contains ONLY the branding.
  It does NOT include the V1 floating clock pill or the V2 btcchart pin bump
  on this page — those come via items 5 and 11. Merge it with the other
  screener changes by hand; the brand row sits above the h1 and does not
  touch the pill or the scripts.

## Check list

1. The screener opens with the owl + "Paperstreet BTC" at the top.
2. The h1, About box, BTC pill, boxes, and charts are all where they were.
3. Phone width (390px): the brand row fits on one line, no overflow.
