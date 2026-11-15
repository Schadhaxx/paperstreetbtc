# Regular Grok's TA spec (pasted by Sunil, Fri Nov 13 2026 3:40 PM ET)
Build the overlay system for the Bitcoin pill chart first, then other charts after the chart rewrite.
Core: smart trendlines (horizontal S/R from pivot clustering + sloped lines); comparative scoring layer picks strongest lines;
Bollinger Bands; SMA and EMA mutually exclusive; RSI; timeframe-aware periods incl. 200.
UI: independent toggle per overlay; expanding "TA" pill (side panel backup); chart must stay readable.
Implementation: lightweight scheduled Python job makes overlay data; front end only draws; sample scoring logic available (not yet received);
no AI in the job; phased ~2 weeks, BTC first.
Chief's review notes (sent 3:41 PM): BTC chart is clock page + popover, not Desk; timeframes are Line/1H/4H/Candles; compute BB/MA/RSI in browser,
Python only for trendlines+scoring; job = GitHub Action writing to data branch; cap lines, hysteresis, hide when stale; drop side panel (C chosen);
need the sample scoring logic.
