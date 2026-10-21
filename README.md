# PaperStreet BTC – live tracker notes

## Finnhub key (stock prices)
The free Finnhub.io key is set in `index.html` (search for `const FINNHUB_API_KEY`).

**Warning:** this is a static site. Anyone can see the key with "View source". It is a free-tier key with no billing attached.

## Data and refresh
- BTC comes from the CoinGecko public API (no key). It refreshes every 60 s. If a fetch fails it shows the last price (or "Price unavailable") and tries again after 90 s.
- MSTR, STRC, TSLA and PLTR come from Finnhub `/api/v1/quote?symbol={T}` (current price `c`, prior close `pc`, time `t`). The page fetches them once on load and then every 5 min (4 requests each time, well within the free tier's 60 requests/min). Daily moves use `pc`; BTC uses CoinGecko's 24h change.
- If the key is missing, a quote returns c=0, or a request fails or hits the rate limit, the page uses the baked "last close 2026-10-19" price. Each ticker shows where its price came from.
- Holdings (units) are baked in as of the 2026-10-19 close, taken from paperstreet `weights_2026-10-19.csv` / `daily_nav.csv`. YTD is measured against the $100,000 start on January 1st, 2026.
