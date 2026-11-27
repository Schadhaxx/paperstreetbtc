# PaperStreet keychain — UI assessment and plan

**Date:** Friday 27 Nov 2026, 2:03 PM ET (America/Toronto)  
**Branch:** `keychain-handover` of `Schadhaxx/paperstreetbtc`  
**SHA:** `0324a7f5a66900b269b03c365c3efda0966feed3`  
**Commit:** 25 Nov 2026, 2:41 PM ET — “Keychain handover for Site Launch: Spaces prototype + C++ firmware + sim”  
**Checkout (read-only):** `/workspace/keychain-handover/repo`  
**This plan:** `/workspace/keychain-handover/PLAN.md` (outside the clone; the repo was not modified)  
**Scope of this step:** assessment and plan only. No build, no commit, no push, no flash, no change to the live site or the public sim.

Sources read in full or by section, not from memory:

- `keychain/README.md` (current state, known nits, hardware-unverified items, fonts/WASM)
- `keychain/spaces-prototype/index.html` (2,147 lines — the approved design target)
- `keychain/firmware/paperstreet-keychain.ino` (4,884 lines — current C++ implementation)
- `keychain/firmware/README.md`, `platformio.ini`, vendored `firmware/lib/qrcodegen/`
- `keychain/sim/` (harness, snapshot data, web shell, verification tools)
- `keychain/docs/gap-analysis-2026-11-24.md` (historical only — see below)
- Live sim, curl/inspect only: https://paperstreet-keychain-sim.netlify.app (HTTP 200; serves `keychain.js` and the 90-second tour video). Nothing on that site was changed.

The 24 Nov gap analysis was written against a 2,826-line firmware, *before* the 24 Nov fix loop. It is useful background, not a current work list. The missing apps it ranked first (block clock, Jade/Lightning QR, comparison overlays, swipe track, sleep veil, Auth list + hide-codes) are now present in this SHA. What remains is visual and usability fidelity against the prototype.

---

## Recommendation

**Rebuild the UI layer from the prototype on top of the existing hardware and data code** — do not start the firmware from a blank sketch, and do not keep patching the current crowded layouts in place.

### Why this, not “improve in place” or “rebuild everything”

The C++ structure underneath is sound and should be kept:

- Hardware drivers: LilyGo T-Display-S3 (ST7789, CST816 touch, backlight PWM, battery ADC)
- Networking and data: Wi-Fi, TLS trust roots (no `setInsecure()`), CoinGecko spot with Coinbase fallback, Coinbase candles, the site daily file, SPX/GOLD/MSTR comparisons rebased to 100, mempool.space clock feeds, 60 s price poll, last-good data, stale dimming
- On-device apps that beat the prototype: real RFC 6238 TOTP (up to 4 accounts, serial provisioning), real scannable QRs (nayuki qrcodegen), NVS persistence, honest “Fetching… / Updating… / OFFLINE” states, real battery percentage
- Sleep/wake (light sleep + dim veil), theme, brightness, swipe track with a 0.34 s slide, page dots

The UI is the problem, and it is not a handful of pixel nits:

- Almost every screen’s drawing lives in one 4,884-line sketch, mixed with fetch, TOTP, and touch, behind magic button IDs and fixed Y coordinates. Chart-page positions are also what the sim tap tests use, so “nudge a row” quickly breaks tests without making the screen look like the prototype.
- The portrait chart page is structurally overcrowded. Extra on-device chrome (Dark/Light, Price, Auth, a Rotate pill in the scrub row, VS chips forced into the former footer) pushed the stat tiles *above* the chart and reversed the control order versus the prototype. That cannot be fixed by tightening padding.
- Remaining regressions are mostly layout, typography, chrome, and feel — exactly what you get if the screens are recomposed from the prototype’s hierarchy, using the existing draw primitives (`fillPill`, segmented pills, fonts, theme palette) and the existing data hooks.

A from-scratch rewrite would re-litigate Wi-Fi, TLS, fetches, TOTP, QR encoding, NVS, and touch, and would put unverified hardware behaviour back at risk. A UI-layer rebuild keeps that code and replaces how screens are composed, spaced, labelled, and navigated.

---

## Regression list, by screen

Dashboard-only prototype controls (zoom, pause/resume polling, “Refresh now”, the Screens jump list, feed diagnostics, theme “System”) are *not* counted as device regressions. Prototype QRs are decorative and Auth codes are a demo hash; real QRs and real TOTP in the firmware are gains, not regressions.

### Navigation and feel (all portrait screens)

| Item | Prototype | Firmware (this SHA) | Severity |
|---|---|---|---|
| Six-page swipe track, wrap-around | chart → price-only → block clock → Jade QR → Lightning QR → Auth | Same order. Present. | At parity (structure) |
| Slide timing | 0.34 s, `cubic-bezier(.32,.72,.28,1)` | 0.34 s, ease-out cubic `1-(1-e)³`. Close, not the same curve. Landscape and a failed slide-buffer alloc skip the slide (instant cut). Mid-slide tap aborts. Each frame full-redraws the incoming page, which can feel heavier. | Medium |
| Swipe threshold | 34 px, horizontal-dominant (`dx > dy * 1.4`) | Same 34 px rule (comments and handleTouch). | At parity |
| Page dots | Inactive 5×5 circles, 5 px gap; active is a 13×5 cyan capsule | Inactive radius-2 circles; active is a 10×4 cyan capsule; tighter 11 px spacing, sitting on y 317 | Medium — reads smaller and less “on” |
| Sleep / wake | Case power button dims to ~6%; veil is a cyan ₿ plus “SCREEN ASLEEP / TAP TO WAKE” | Long-press 1.2 s on empty background, sleep on lift; veil is a crescent moon plus the same words and a cyan rule. Wake swallows that touch. Light sleep in 50 ms slices. | Medium visually (glyph); behaviour is a reasonable device analogue of a hardware button the board may not expose the same way |
| Tap feedback | Instant CSS state change | No press highlight. State changes only after lift + a full `drawAll()`. README still lists a 0.3–0.5 s lag on fast taps. Debounce is 30 ms, so the delay is the redraw, not the debounce. | High (feel) |
| On-device shortcut pills (Chart / Clock / QR / Auth / Price) | None. Swipe + dots are the only on-device navigation. | Present on clock, QR, Auth, and (Price + Auth + theme) on the chart page. Useful, but they steal rows the prototype uses for content and change the look of every app. | High (layout) |

### Chart (page 0)

| Item | Prototype | Firmware (this SHA) | Severity |
|---|---|---|---|
| Vertical order | Status → header → price → change/Updated → scrub → chart 154×58 → axis → type (Line/Candles) → VS chips → ranges → stat tiles at the bottom | Status → header → price → change → **stat tiles above the chart** → scrub (with Rotate) → chart → axis → **ranges** → type → Dark/Light + Price + Auth → VS chips in the old footer row | **High** — the main visual and usability regression |
| Header copy | “BITCOIN · LIVE PRICE” plus “BLOCK …” | “BTC” plus “BLOCK …” | Medium |
| Currency pill | “USD $” / “CAD $”. Tapping the **big price** also toggles currency. | “USD” / “CAD” only. The price is not a hit target. | High (usability) |
| Status bar | Clock on the left; static Wi-Fi icon + battery on the right | LIVE/OFFLINE word + dot on the left; battery + 24-hour clock on the right. No Wi-Fi icon. LIVE/OFFLINE and a real battery % are gains, but the arrangement does not match. | Medium |
| Theme + nav chrome | Theme lives on the simulator dashboard, not on the device chart | Dark/Light, Price, and Auth pills on the chart control row. Rotate sits in the scrub row. This is why the page ran out of vertical room. | High (cause of the restack) |
| VS chips | Directly under the type row, labelled “S&P / GOLD / MSTR”, always showing the range %. Hidden/disabled in candle mode. | Forced to y 300 (former footer; “CoinGecko · Coinbase” was removed to make room). Labelled “SPX” not “S&P”. Hidden on 1D (a firmware layout decision). No row in landscape. | Medium |
| Range pills | Under VS, wrapped row, 17 px, 5 px radius, mono 7.5 px | Two fixed rows above the type row; same 17 px / radius 5 (good). Hit boxes were expanded (good). 5Y/MAX in candle mode are greyed and untappable (now at parity). | Low once restacked |
| Stat tiles | 2×2 under the ranges | 2×2 *above* the chart, squeezing the price-to-chart flow | High (placement) |
| Typography / colour | Inactive secondary text `#67748e` | `C_PILL2` was deliberately brightened to `#93a5c4` for contrast at 6–7 px. Honest, but it is a visible palette drift. | Low |
| Chart drawing | Line, 13% area fill, end dot, 3 gridlines, candles to 1Y, comparisons rebased to 100, scrub % vs range start, leave-scrub after 900 ms | Same capabilities, plus high/low Y labels and candle snap (gains). Scrub % is vs range start (fixed). Scrub readout clears **on lift**, not after 900 ms. | Low (scrub linger) |
| Known nit: 1Y right-edge “Nov” | Dates have room | README still flags the last 1Y x-axis “Nov” label as slightly clipped. Code now right-aligns “Now” and centres other labels; worth re-checking in the sim, not assumed fixed. | Low |
| Landscape | The whole device mockup turns sideways; chart uses a 320-wide grid; type + VS + all 9 ranges share one bottom row; other pages stay usable, just tighter | Only the chart view rotates, via a Rotate button (no tilt sensor — fair). Bottom row is 9 ranges + “Line/Cndl” (abbreviated) + Portrait. No VS chips, no Updated time, theme lives in the scrub row. Price-only / clock / QR / Auth cannot be used sideways. | Medium |

### Price-only (page 1)

| Item | Prototype | Firmware (this SHA) | Severity |
|---|---|---|---|
| Hero | Centred “BITCOIN · LIVE PRICE”, block, 30 px price with cyan $ and glow, 24h change, cyan rule, **two** stats (sats, block), currency pill | Label is just “BITCOIN”. Change is the **selected chart range**, not always 24h. **Four** stats (adds HIGH/LOW). “Updated” time was added (good). | Medium |
| Extra chrome | None on-device. Hint: “NOTHING BUT THE PRICE — SWIPE FOR THE CHART” | Brightness − / + stepper (45–100%). Hint: “TAP FOR CHART · HOLD TO SLEEP”. Exit is tap-anywhere (except the currency pill), not swipe-as-the-named-exit — swipe still works via the track, but the copy is wrong. | High (the screen is no longer “nothing but the price”) |
| Currency via price tap | Yes (shared `.price` handler) | No | High (same as chart) |

### Block clock (page 2)

Feature parity is largely **full**: three focus views, 12 s auto-rotate, tap dots to jump and restart the timer, 10-minute ring, sats focus, halving to block 1,050,000, 2×2 stats (sats per $10/$100, difficulty, fastest fee, mempool), big ET clock, “Tue, Nov 24, 2026 · Ottawa”, mempool.space feeds. The regressions are visual and typographic.

| Item | Prototype | Firmware (this SHA) | Severity |
|---|---|---|---|
| Title tag | “LIVE · AUTO” as a green pulsing live-dot | “LIVE · AUTO” as a cyan filled pill with dark text | Medium |
| Focus dots | 16 px capsules (26 px when on), 6 px tall, cyan glow | Circles, radius 3 / 4, no glow | Medium |
| Halving title | “NEXT HALVING · THE CLOCK INSIDE THE CLOCK” | “NEXT HALVING” only | Low |
| Halving ETA | “≈ APR 2028” | “~ APR 2028” (ASCII tilde; the ≈ glyph is not in the vlw fonts) | Low |
| Big clock | 24-hour `HH:MM:SS` plus a small “ET” | 12-hour `4:32 PM · ET`, no seconds. Colon is hand-drawn (Outfit vlw has no `:`). | Medium |
| Sats $10/$100 tile | Full figures (“10,800 / 108,000”) | Abbreviated (“16.5k / 165k”) because the full string did not fit the tile font | Low–medium |
| Tile labels | “DIFFICULTY ADJUSTMENT”, “NETWORK FEES · FASTEST” | Shortened (“DIFFICULTY ADJ”, “FEES · FASTEST”) | Low |
| Nav pills | None | Chart / QR / Auth row above the dots | Medium (chrome) |
| Ring | SVG with a cyan drop-shadow, updates every second with the “ago” line | Arc gauge; “ago” updates every second, ring only every 30 s | Low (feel) |

### QR — Jade (page 3) and Lightning (page 4)

Feature parity is largely **full**, and the firmware QRs are a gain (real, ECC Medium, same placeholder addresses as the prototype). Flip-to-address and the watch-only warnings exist.

| Item | Prototype | Firmware (this SHA) | Severity |
|---|---|---|---|
| Header | Coloured badge (green “J” / amber “ϟ”) + name + “ON-CHAIN · RECEIVE” / “RECEIVE” | Text title “JADE · ON-CHAIN” / “LIGHTNING · RECEIVE”, no badge | Medium |
| Jade/Lightning switch | Swipe only (two pages on the track) | Track pages plus a centred Jade/Lightning segmented pill | Low as a shortcut; it changes the header layout |
| Card | 138×138, radius 10, 7 px padding, 124 px canvas | 148×148, radius 7, module 4 px + quiet zone (sized for a v3 29-module code) | Low |
| Flipped card | Address + amber warning, no large empty band called out | Warning is muted grey, not amber (`#fbbf24` / light-mode `#b45309`). README still flags ~25–30% empty space below the last line; a later pass grew the card and centred content, but the nit is not clearly gone. Em-dashes became ASCII hyphens. | Medium |
| Nav pills | None | Chart / Clock / Auth at y 294 | Medium (chrome) |
| Scannability | Decorative (not a real encode) | Real QR. **Not verified on a phone camera.** | Unverified (hardware) |

### Authenticator (page 5)

Feature parity is much closer than the 24 Nov analysis: list view (not a Prev/Next pager), hide/show codes, countdown + bar, enlarged code, up to 4 accounts, real TOTP. Remaining gaps are typography, wording, density, and one wrong destination.

| Item | Prototype | Firmware (this SHA) | Severity |
|---|---|---|---|
| Title + hide | “AUTHENTICATOR” + TOTP tag; pill says “HIDE CODES” / “SHOW CODES” | Title + cyan TOTP pill; button says only “HIDE” / “SHOW” | Medium |
| Countdown | “NEW CODES IN” + seconds on the right; 4 px bar, ~0.9 s width transition | “{N}s until new code”; 5 px bar, redrawn without the CSS ease | Medium (wording and feel) |
| List rows | min-height 44 px, issuer + account subline (“personal login”), 12.5 px codes | 30 px rows, subline is the generic “One-time code”, codes on the right. Short lists are recentred and the code box grows — an improvement, still not the prototype’s density. | High (touch target and scanability) |
| Enlarged box | “PAPERSTREET · TAP AN ACCOUNT TO ENLARGE” (or “CODES HIDDEN — TAP SHOW CODES”) + 19 px code | Label is “CODE”; hidden state is six drawn dots (the mono font has no bullets — fair). | Low–medium |
| Nav | None on-device | “Price” / Clock / QR. **Known nit: Price goes to the chart page, not price-only.** | High (wrong destination) + Medium (chrome) |
| Demo note | “DEMO CODES — SIMULATION ONLY” | “DEMO - not a real account” plus the serial ADD hint when the shipped demo account is showing. Appropriate for real firmware; typography and hyphen vs dash still differ. | Low |

### Data, status, and small behaviour (not screen-chrome, but user-visible)

These are secondary to the UI brief, noted so the plan does not “fix” them by accident or silently drop a gain:

- Firmware keeps last-good data, dims a stale chart, and can show OFFLINE — a gain. Prototype has a multi-source spot cross-check and a sanity gate against a lone wild tick; firmware still uses CoinGecko + Coinbase fallback only.
- Intraday refetch is 15 min in firmware vs a 5 min TTL in the prototype.
- Status-bar clock is Eastern 24-hour `HH:MM` after NTP; unsynced it is `--:--`.
- Brightness 45–100% is on the price-only page only (chart and landscape have no room). Prototype’s slider is dashboard-only.
- Firmware README still describes the old Auth Prev/Next pager in places — docs drift, not a device bug.

---

## What stays untouched

- `main`, the `data` branch, paperstreetbtc.com, and the public Netlify sim. No deploys, no flashes, no `workflow_dispatch`.
- Wi-Fi / TLS / fetch paths, TOTP math, QR encoding library, NVS keys, touch driver, backlight PWM, battery ADC, light-sleep path — unless a UI change absolutely requires a small hook (for example, making the big price a currency hit target, or drawing a press highlight before `drawAll()`).
- No new features. No behaviour changes beyond what matching the prototype requires. Gains listed below are kept unless Sunil chooses otherwise.
- Placeholder Wi-Fi credentials stay placeholders. No secrets printed or committed. The shipped Auth demo account stays the public RFC 6238 test secret, labelled as a demo.
- Article numbers, site banner, and site wording are out of scope (this branch is keychain only).

### Gains to keep (do not throw away in a UI rebuild)

- Real TOTP, serial ADD/REMOVE, time-sync lockout (dashes until NTP)
- Real scannable QRs
- NVS persistence (currency, theme, range, type, accounts, last price, brightness)
- Stale/off-line honesty (“Fetching…”, “Updating…”, LIVE/OFFLINE, dimmed stale series)
- Real battery percentage (and USB when on cable)
- Disabled 5Y/MAX in candle mode actually untappable
- Scrub % vs range start; 1D candles labelled as 15-minute data
- Comparison overlays and rebase-to-100
- Expanded range-pill hit targets (visual size can still match the prototype)

---

## Phased plan

Work stays on a keychain branch (never `main`). Each phase is checked in the *local* sim (`keychain/sim/`), not by changing the public Netlify sim. Visual check: side-by-side screenshots of the prototype (`spaces-prototype/index.html`) and the WASM sim, same theme, same range, same fixture data where possible (the sim’s 24 Nov 2026 snapshot plus the prototype’s live/fallback path). Existing harnesses in `sim/tools/` (ring, swipe, edge-case, fetch-path, live-tap, tour-seq) are rerun after any navigation or hit-box change.

**Prerequisite (before Phase 1 screenshots mean anything):** obtain the 15 `.vlw` fonts (Outfit / Inter / IBM Plex Mono). They are not in the repo. Regenerate with `sim/tools/genvlw.py` from the matching TTFs, or ask Pepper for the files. Fallback fonts would make typography comparisons misleading. The built WASM is also not in the repo; build locally with `sim/build-wasm.sh` (Emscripten). Do not publish over the live sim.

### Phase 0 — Harness and baseline (about half a day)

- Local sim build; font files in place; screenshot script for all six portrait screens, both themes, plus landscape chart, price-only, QR flipped, Auth hidden/shown, and the sleep veil.
- Capture a matching prototype set at the same 170×320 logical size.
- Record current tap-test coordinates so Phase 1 can update them deliberately.
- **Check:** baseline album exists; sim boots; no code behaviour change.

### Phase 1 — Restack the chart page (about 2–3 days)

The critical phase. Recompose portrait chart to the prototype’s order and spacing:

1. Status → “BITCOIN · LIVE PRICE” + BLOCK + currency pill → big price → change + Updated → scrub (“Drag chart to scrub”) → chart 154×58 → axis → type row → VS chips (“S&P / GOLD / MSTR”) → ranges → stat tiles at the bottom → page dots.
2. Remove Dark/Light, Price, and Auth from this page (swipe already reaches price-only and Auth). Relocate theme and Rotate so they do not steal a content row — proposal: theme with brightness on a place Sunil approves (see open decisions); Rotate can stay as a small control that does not sit on the plot or the scrub hint.
3. Restore price-tap to toggle USD/CAD (prototype behaviour). Keep the currency pill too.
4. Match pill shapes, type sizes, and the status-bar arrangement as closely as the fonts allow. Decide LIVE/OFFLINE vs a Wi-Fi icon with Sunil (gain vs match).
5. Update sim tap tests for the new coordinates.

**Check:** side-by-side screenshots for 1D line, 1Y candles, 1Y line with a comparison on, light and dark; swipe still wraps; range/type/VS taps still work; disabled 5Y/MAX do nothing in candle mode; no overlay on the plot.

### Phase 2 — Price-only (about half a day to one day)

- Restore “BITCOIN · LIVE PRICE”, the two-stat column as the default layout, the prototype hint (“NOTHING BUT THE PRICE — SWIPE FOR THE CHART”), and swipe as the named way back.
- Move the brightness stepper off this screen unless Sunil wants it kept (open decision). HIGH/LOW and “Updated” can stay if they do not break the calm centred layout — otherwise they belong on the chart tiles only.
- Price-tap currency toggle, same as Phase 1.

**Check:** light/dark screenshots vs prototype; swipe and tap-exit behaviour documented; currency toggle works.

### Phase 3 — Block clock visuals (about one day)

- Title “LIVE · AUTO” as a green live-dot, not a cyan pill.
- Focus dots as capsules with the active state wider, not circles.
- Restore “NEXT HALVING · THE CLOCK INSIDE THE CLOCK”.
- Big clock as 24-hour `HH:MM:SS ET` to match the prototype (or confirm 12-hour with Sunil). Keep the Ottawa date line.
- Use “≈ APR 2028” if the font can; if not, “~ APR 2028” is already the documented font limitation — do not invent a glyph.
- Remove Chart / QR / Auth pills (swipe + dots are enough).
- Prefer full figures in the sats $10/$100 tile if a slightly tighter font fits; otherwise keep the k-form and note it.

**Check:** screenshots of all three focus views, both themes; 12 s rotate and tap-to-jump still work; per-second “ago” update has no full-screen flicker.

### Phase 4 — QR visuals (about half a day to one day)

- Restore badge + title treatment (green J, amber lightning mark).
- Keep the Jade/Lightning shortcut pill only if it can sit without breaking the header; otherwise swipe-only, like the prototype (open decision).
- Tighten flipped-card typography and warning colour (amber), and close any remaining empty band below the last line.
- Remove Chart / Clock / Auth pills.
- Do not change encoded strings or ECC in this phase.

**Check:** unflipped and flipped screenshots, both QR pages, both themes; flip still toggles; encode path unchanged (harness / visual inspection of modules). Phone-camera scan stays a hardware item.

### Phase 5 — Authenticator visuals and the Price button (about one day)

- “HIDE CODES” / “SHOW CODES” wording; “NEW CODES IN Xs” layout.
- Taller list rows (toward 44 px), issuer + a real account subline, not “One-time code”.
- Enlarged-box label in the prototype’s voice (“{NAME} · TAP AN ACCOUNT TO ENLARGE” / “CODES HIDDEN — TAP SHOW CODES”).
- **Fix the Price button destination** if the button remains — it must go to price-only, not the chart. Preferred: remove the nav pills and let swipe + dots do the job (then the nit disappears).
- Keep real TOTP, hide/show, demo warning, and the time-sync lockout.

**Check:** screenshots with 1 and 4 accounts, hidden and shown, unsynced dashes; codes still roll every 30 s; serial ADD still works in the native/sim harness.

### Phase 6 — Feel: dots, slide, and tap highlight (about one day)

- Page dots: 5 px inactive, ~13 px active capsule, prototype spacing.
- Slide curve closer to `cubic-bezier(.32,.72,.28,1)` (or a documented close approximation). Avoid a full incoming-page redraw every frame if a captured-buffer approach can paint both sides more cheaply.
- Immediate press highlight on lift-less-than-frame: paint the hit pill in the “on” colours as soon as the finger goes down, then commit on lift. This is the honest fix for the 0.3–0.5 s lag.
- Re-verify swipe vs scrub vs long-press-sleep (sleep still fires on lift, a drag cancels it).

**Check:** swipe, wrap, mid-slide abort, scrub, long-press sleep, and the existing swipe/ring/live-tap harnesses. Screen-record a short side-by-side of a swipe and a range tap vs the prototype.

### Phase 7 — Landscape (about one day, after open decisions)

Default proposal: keep “chart-only landscape via a button” (the board has no tilt sensor), but make the landscape *chart* match the prototype’s 320-wide grid: type + VS + ranges on one bottom row, “Candles” not “Cndl” if width allows, Updated time if it fits, no theme pill crowding the ranges. Do not invent sideways clock/QR/Auth unless Sunil asks for prototype-like tightening of those pages.

**Check:** portrait ↔ landscape round-trip keeps range, type, and comparison state; touch hit boxes in the sim; note that **landscape touch remap on hardware is still unverified**.

### Phase 8 — Close-out (about half a day)

- Full screenshot album vs prototype, light and dark, all six pages plus flipped QR, hidden Auth, sleep veil, landscape chart.
- Rerun the sim harnesses. Compile (PlatformIO) for flash/RAM use; last reported figures were RAM 20.1%, Flash 41.6% — there is headroom, but record the new numbers.
- Update `keychain/README.md` and the firmware README (Auth pager text is stale; known nits should reflect what Phase 1–7 actually closed).
- Hand Sunil the album, the remaining hardware-only items, and the branch SHA. **Where that work lands is his decision. No merge to `main`, no live-site or public-sim publish in this plan.**

**Rough total:** about 8–10 focused days in the sim, assuming fonts are in hand and no hardware debug. If it grows past that, stop and check with Sunil (via Grok Bot) before continuing, per the handover note.

---

## What is unverifiable without hardware

Do not claim these are done after a sim pass. They stay on a hardware checklist for a later board session (no flash in this plan):

- Deep-sleep GPIO-16 wake (the firmware correctly uses light sleep instead, and documents this)
- Landscape touch remap (`dx = 319 − ty`, `dy = tx` for rotation 1, with a rotation-3 fallback)
- QR scannability on a real phone camera (module size, brightness, glare)
- TLS chains on the board (trust store is in the sketch; the handshake is unproven on device)
- Backlight PWM and sleep brightness (6% veil readability on glass)
- Anti-aliased capsule edges and vlw glyphs on the real ST7789 (the sim SDF is an approximation)
- Touch latency during a live fetch (fetches still block; duration depends on the TLS handshake)
- Wi-Fi association with real credentials (placeholders only in the sketch)
- Long-press sleep vs accidental holds, in the hand

---

## Open decisions for Sunil

1. **Where the rebuild lands.** This plan stays off `main` and off the live site. A dedicated branch (continue `keychain-handover`, or a fresh branch from this SHA) is a product call for Sunil. The public sim is also left alone until he says to update it.
2. **Extra on-device buttons.** The prototype navigates only by swipe and dots. The firmware added theme, Price, Auth, Chart, Clock, QR, and Jade/Lightning shortcut pills, which are the main reason the screens feel crowded. Recommendation: take them off the pages and rely on swipe + dots, and put theme/brightness in one quiet place (or leave theme as a long-press / settings gesture). Sunil can keep specific shortcuts if he wants them.
3. **Gains that slightly change the look.** Recommendation: keep real TOTP, real QRs, saved settings, stale/off-line honesty, and a real battery reading. LIVE/OFFLINE in the status bar, HIGH/LOW on price-only, and the brightness stepper are optional — they help, but they are not in the approved prototype layout.
4. **Authenticator “Price” button.** If that button stays, it should go to the price-only screen, not the chart. If we drop the nav pills (decision 2), this goes away.
5. **Landscape scope.** Match the sideways *chart* to the prototype, and keep other screens portrait (the board has no tilt sensor). Extending sideways layouts to clock / QR / Auth / price-only is optional extra work.
6. **Price-only change figure.** Prototype always shows 24h. Firmware shows the selected chart range. Which does he want?
7. **Block-clock time format.** Prototype is 24-hour with seconds. Firmware is 12-hour without seconds. Which should the device show?
8. **Currency labels.** “USD $” / “CAD $” as in the prototype, or the shorter “USD” / “CAD”?

No code will be written until Sunil has this choice and plan, and has said to proceed.
