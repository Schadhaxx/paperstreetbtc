# Easy SEO fixes — test branch, for Saturday review

Built 4 Nov 2026 at Sunil's yes, from the same-day SEO
audit. Test branch only, NOT live. No visible change, no
JavaScript change, no data change — head tags and one XML
file only.

## Changes
- `sitemap.xml`: was homepage-only, lastmod 2026-10-21.
  Now lists the homepage + Compare + Tools + Monthly
  recap, all lastmod 2026-11-04 (the build date). The
  screener is DELIBERATELY NOT listed: it is hidden,
  leaf-only, and listing it would defeat that.
- Meta descriptions (one line each, new — none existed):
  - Compare: "Compare the four PaperStreet sleeves
    against spot BTC, gold, and MSTR, year to date.
    Spot BTC is the hurdle. Not financial advice."
  - Tools: "Build a custom sleeve and compare it with
    the four PaperStreet sleeves and spot BTC. Not
    financial advice."
  - Monthly recap: "Monthly recaps of the four
    PaperStreet sleeves — performance, dividends, and
    what changed. Not financial advice."
  Homepage description unchanged (it already had one).
- Canonical tags (one line each, new — none existed):
  homepage → https://paperstreetbtc.com/,
  Compare → …/compare/, Tools → …/custom/,
  Recap → …/recap/ (clean directory URLs, which GitHub
  Pages serves from the index.html files).
- Homepage JSON-LD (new): a single WebSite block
  (name, url, description matching the existing meta
  description). WebSite only — no Organisation claim,
  since this is a personal site, not a company page.

## Deliberately NOT in this branch
- Screener: no description, no canonical, not in the
  sitemap. It stays hidden.
- No lastmod automation: a static sitemap goes stale
  again (that is how 21 Oct happened). If Grok wants
  it, the pipeline could regenerate sitemap.xml on
  deploy — that is a Grok-side decision, not in this
  branch.

## Validation (before push)
- sitemap.xml parses as XML, 4 URLs.
- JSON-LD parses as JSON.
- Exactly 1 meta description and 1 canonical per
  page (homepage description count unchanged at 1).

## Saturday checks
- View source on each page: description + canonical
  present, no duplicates.
- Fetch /sitemap.xml after deploy: 4 URLs, no
  screener URL.
- Optional: Google's Rich Results Test on the
  homepage for the WebSite block.
- Merge note: touches index.html head only (plus
  the three subpage heads and sitemap.xml) — no
  overlap with the Saturday JS branches except the
  index.html head region, which none of them touch.
