# TA pill on the Live BTC chart — iPhone layout mockups (phase 1)

Requested by Sunil via Chief of Staff, Fri 13 Nov 2026, 1:55 PM ET. **Mockups only.** No repo code changed, nothing pushed or deployed. The mockups run the real clock page (mirrored read-only from paperstreetbtc.com/clock/, clock V4) with one extra stylesheet and script (`www/clock/ta-mock.css`, `www/clock/ta-mock.js`) layered on top. The TA overlays are illustrative: they are computed from the price line that the real chart actually drew, so they follow the line, but the numbers aren't real indicator math.

## What's the same in all four approaches (the agreed TA plan)

- **TA pill** at the end of a control row: `TA ⌄` when nothing is on, and `TA ②` (a cyan count) when overlays are active.
- **Floating panel** that opens under the pill, right-aligned to the chart, sitting over the plot without pushing the layout. It closes when you tap outside it. Contents: Smart Trendlines, Bollinger Bands (20 · 2σ), Moving average (on/off, a **SMA | EMA** two-way switch, **20 | 50 | 200**), RSI (14). It has no side panel on phones.
- **RSI** is a thin strip under the chart (50px portrait, 38px landscape) with a `RSI 14 · 54 ⌄` tab that collapses it to 20px. It's off by default. The chart draws only what's on.
- Colours stay clear of the asset colours: MA is pink, Bollinger is violet, trendlines are green (support) and red (resistance), and RSI is violet.
- Same site style in dark and light: the pill borders, cyan "on" state and Inter type all match the existing range and chart-type chips.

## The four approaches

| | Approach | One line | Height cost (iPhone 15) |
|---|---|---|---|
| **A** | **Range-row tail** | The TA pill is pinned to the right end of the range row (1D…Max), which already swipes. Row 2 (assets + chart type) is untouched. | 0px. RSI on: chart 518→462 portrait, 231→185 landscape |
| **B** | **One swipe lane** | Chart type and asset chips share a single swipe lane on row 2 (chart type first), with TA pinned at the end. | 0px (same RSI cost as A) |
| **C** | **Compact chart-type picker** | Line / 1H / 4H / Candles / size collapse into one `Line ⌄` / `Candles ⌄` pill (its own small menu), so row 2 = assets + type + TA. | 0px (same RSI cost as A) |
| **D** | **Third toolbar row** | Chart type moves to its own row 3, with TA at the end and room for "active" chips (e.g. `SMA 50`, `Bollinger`). | −38px always: chart 518→480 portrait, 231→195 landscape; with RSI 424 / 149 |

### A — Range-row tail (recommended)
- **Today (before TA ships):** the range row just ends about 52px earlier, with the existing fade. You swipe slightly sooner to reach 10Y/Max, and nothing else moves. This is the cheapest reservation.
- **Pros:** no height cost. The squished row 2 isn't touched at all, so candle options and asset toggles behave exactly as today. The pill is always visible in every range and chart type. In full-screen chart it sits left of the Exit button (row 1 already leaves 150px for Exit).
- **Cons:** the pill sits next to *time* controls rather than *chart-style* controls, so it's a little less "logical". It shows two fewer ranges at once on the first screen, and the panel overlaps row 2's right end while open, which is fine because it closes on an outside tap.

### B — One swipe lane
- **Today:** row 2 becomes one swipe lane `Line 1H 4H | BTC + S&P …` with an empty slot at the end.
- **Pros:** no height cost. TA sits next to the chart-type buttons, where it logically belongs.
- **Cons:** in candle mode (`Line Candles Weekly Monthly`) the asset chips are pushed completely off-screen, so you have to swipe to find S&P/Gold/MSTR. Today you can at least see BTC. It also changes the order Sunil is used to.

### C — Compact chart-type picker
- **Today:** the type buttons become one `Line ⌄` / `Candles ⌄` pill. Asset chips get *more* room than now, even in candle mode (BTC + S&P visible instead of BTC alone).
- **Pros:** no height cost, it fixes today's squish, and the most room is left for future controls. The pill-opens-a-menu pattern matches TA.
- **Cons:** it's the biggest change to existing controls. Switching Line↔Candles or Weekly↔Monthly takes two taps instead of one, and it needs a second small menu (not mocked here). It's more build work.

### D — Third toolbar row
- **Today:** chart type gets its own row 3, so assets get the full row 2 (BTC, S&P, Gold and part of MSTR visible) and candle options no longer squeeze anything.
- **Pros:** the clearest and roomiest option. There's space for active-overlay chips so you can see what's on at a glance, and it's the most future-proof for more TA tools.
- **Cons:** it costs 38px of chart all the time, and landscape hurts most: plot 231→195, and 149px with RSI on. In landscape the open panel only just fits under row 3 (capped at the screen bottom, with 6px to spare). This is the one Sunil would notice as "the chart got smaller".

## Recommendation
**A — Range-row tail.** It's the only option that reserves room with zero change to the row Sunil already finds squished, zero chart height lost, and no new taps for candle and asset controls. That matters most on iPhone landscape, which only has about 230px of plot. Reserving now is just a 52px slot at the end of the range row. If we later want the chart-type row tidied too, C can be added on top of A without moving the TA pill again.

## Overlap check (rectangle checks)
For every shot with the panel open, `make-sheets.py` reads the live DOM rectangles (`window.__taRects()`) and checks the panel against the **BTC price** (price + 24h line), **Keep screen on**, **Exit full screen**, the **Light/Dark pill** and the **Full-screen chart/price buttons**, counting only those actually visible on screen (hit-tested). It also confirms the panel is actually visible (hit-test at its centre) and fully inside the viewport and the chart stage. Results: `shots/overlap-check.json`. Each sheet also prints "no overlap ✓" under every open-panel shot.

**Result: 44 of 44 open-panel shots pass.** No overlap with any protected element; the panel is visible and fully inside the screen and the stage every time. That covers 4 approaches × dark and light × portrait, portrait with candles, landscape and landscape full-screen chart, plus the SE 375×667 and portrait full-screen-chart checks.

Closest clearances (smallest gap between the panel and each element, any shot):

| | BTC price | Keep screen on | Exit full screen | Light/Dark pill | Full-screen buttons |
|---|---|---|---|---|---|
| A | 50px | 215px | 12px (portrait full-screen) | 85px | 200px |
| B | 88px | 253px | 48px | 47px | 200px |
| C | 88px | 253px | 48px | 47px | 200px |
| D | 126px | 291px | 84px | 9px (SE) | 200px |

"Keep screen on" isn't on screen in either full-screen mode (the stage covers it), so the check skips it there. The Light/Dark pill is not a protected item, but it was checked anyway. Note that the RSI strip runs under the floating Light pill at the bottom-right in portrait, the same way the chart's x-axis already does today.

Full-screen price mode hides the chart, so the TA pill and panel aren't shown there (`*-l-fsprice` shots). That makes it trivially safe.

Build note found while mocking: in Fullscreen-API mode (desktop and iPad, not iPhone Safari) the stage is in the browser's top layer, so **the panel must be a child of the `.v4-stage`, not `body`**, or it renders behind the full-screen chart. The mockup does this.

## Files
- Overview sheet: `shots/overview.png`
- Per-approach sheets: `shots/sheet-A.png`, `shots/sheet-B.png`, `shots/sheet-C.png`, `shots/sheet-D.png`. Each has portrait dark and light (today / closed / open / RSI on / candles worst case / candles + open), landscape dark and light (today / open / RSI on), full-screen chart (open, RSI on), full-screen price, SE 375×667 checks, portrait full-screen chart and RSI collapsed.
- Individual shots: `shots/<A|B|C|D>/<approach>-<dark|light>-<p|l|se>-<state>.png`, plus `.json` rectangles.
- Live reference (today, no TA): `shots/live/`
- Mockup layer: `www/clock/ta.html` (mirror of `/clock/` + the two files below), `www/clock/ta-mock.css`, `www/clock/ta-mock.js`
- Scripts: `render.py` (Playwright, iPhone UA, DPR 2), `make-sheets.py`

## How to view
```bash
python3 -m http.server 8790 --directory /workspace/mockups-ta-pill/www --bind 127.0.0.1
# http://127.0.0.1:8790/clock/ta.html?a=A&s=open        (a=A|B|C|D)
# s=today|closed|open|rsi|rsicol   r=1Y&ct=candles   fs=chart|price   ma=sma|ema   p=20|50|200
```
Prices and chart data load live. Viewports: iPhone 15 portrait 393×852, landscape 852×393, SE 375×667.

Phase 2 (iPad + desktop) starts after Sunil picks one.
