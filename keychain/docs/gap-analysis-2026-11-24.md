# Keychain: prototype vs C++ firmware — inch-by-inch gap analysis

**Date:** Tue 24 Nov 2026
**Sources (read in full, not from memory):**
- Prototype (original): `~/workspace/ts-spaces/paperstreet-keychain-prototype/index.html` — 2,147 lines
- Firmware: `~/workspace/ps-keychain-firmware/paperstreet-keychain.ino` — 2,826 lines (state after clean redesign, axis/stale/button fixes, triple-attention pass, Auth layout fix)
- Sim frames: `~/workspace/ps-keychain-sim/refine-png3/`, `refine-frames-new/`

**Method:** every screen, control, data element and interaction in the prototype was checked against the firmware, one by one. Status per feature: **FULL** (present and equivalent), **PARTIAL**, **DIFFERENT** (present but behaves differently), **MISSING**.

**Scope notes (read these first, they change how to read the gaps):**
- The prototype is a *simulator page* — a dashboard around a device mockup. Dashboard-only controls (zoom, pause/resume polling, "Refresh now", the Screens jump buttons, feed diagnostics, the theme "System" option) are simulator scaffolding, not device features. They are noted where they have a device analogue, not counted as regressions.
- The prototype's QR codes are **decorative, not scannable** — `drawQR` draws a seeded pseudo-random 29×29 grid with finder patterns; it does not encode the address. The prototype's Auth codes are **demo only** — an FNV hash of a demo seed, not real TOTP.
- The prototype has **no persistence at all** (no localStorage; everything resets on reload) and **no TA** (explicitly excluded by its own "What fits" list).
- Sunil's example understates the problem: he said Auth and Lightning are "behind a toggle". Auth is behind a toggle. **Lightning has no toggle and no screen at all** — it is gone entirely, along with the block clock and the Jade QR page.

**Headroom for fixes (from the last build):** Flash 35.0% used (1,168,899 / 3,342,336) — ~2.17 MB free. RAM 18.2% (59,684 / 327,680) — ~268 KB free. PSRAM (8 MB, ESP32-S3R8) holds the ~135 KB daily file. Nothing in the gap list is blocked by memory; the constraints are screen space (170×320), single-touch input, and build effort.

---

## 1. Ranked regressions (worst first)

### R1 — Block clock app: entirely missing
- **Prototype:** Page 2. Title "BLOCK CLOCK · LIVE · AUTO". A focus card auto-rotating every 12 s through three views (tap the dots to jump, which restarts the timer): (0) block height huge with a cyan ring filling toward a 10-minute target + "X min SS s ago — since the last block"; (1) sats per dollar huge with an explanatory note; (2) next halving — blocks to go to block 1,050,000, progress bar, "% OF THE EPOCH", "≈ APR 2028". Below it a 2×2 stat grid: sats per $10/$100, difficulty adjustment (progress %), network fees (fastest, sat/vB), mempool size (MB). Big ET clock + date line ("Tue, Nov 24, 2026 · Ottawa").
- **C++:** Nothing. The only block-clock data anywhere in the firmware is the block *height* as a number (header + one stat tile), polled every 10 min from mempool.space.
- **User-visible difference:** an entire app is gone. Sunil cannot glance at time-since-last-block, the 10-minute ring, the halving countdown, fees, or mempool on the device at all.
- **Severity:** blocks use.
- **To close it:** feasible, no hardware blocker. A new screen (~200–300 lines): the three focus views + dots + stat grid + ET clock (NTP already exists). Data is all mempool.space, the host the firmware already uses: `/api/blocks` (latest timestamp), `/api/v1/difficulty-adjustment`, `/api/v1/fees/recommended`, `/api/mempool` — all small JSON. Ring gauge via `drawArc`/`fillArc`. Auto-rotate via a 12 s timer. RAM cost negligible; flash a few KB.

### R2 — QR receive pages (Jade + Lightning): entirely missing
- **Prototype:** Pages 3–4. Jade: QR card + truncated `bc1q…` address, "TAP QR FOR FULL ADDRESS"; tap flips to the full address + "Receive only. This is a watch-only address — the keychain holds no keys and can never sign or send." Lightning: same pattern for `paperstreet@walletofsatoshi.com` ("anyone can pay it, nothing on the device can spend from it").
- **C++:** Nothing. No QR screen, no QR rendering, no address display anywhere.
- **User-visible difference:** the device cannot show a receive address at all — no way to receive on-chain or over Lightning from the keychain.
- **Severity:** blocks use.
- **To close it:** feasible, no hardware blocker — and the firmware could *beat* the prototype here, because the prototype's QRs are decorative. A small QR library (e.g. nayuki qrcodegen, ~5–10 KB flash) generates a real, scannable QR from the same hardcoded strings. One screen per address (or one screen, two addresses), tap to flip to full-address text. ~100–150 lines + the library.

### R3 — Comparison overlays (S&P / GOLD / MSTR): entirely missing
- **Prototype:** "VS" row on the chart page — three toggle chips, any mix, line mode only. All lines rebased to 100 at range start so assets share one scale; Y $ labels converted back. Each chip always shows that asset's % for the range, on or off. Each active comparison gets a coloured line (purple/amber/orange) + end dot. Live data: real daily closes stepped to each BTC timestamp; synthetic fallback offline.
- **C++:** Nothing. No VS row, no chips, no overlays, no per-asset %. The chart is BTC-only.
- **User-visible difference:** the "how is BTC doing vs stocks/gold/MSTR" question — a headline feature of the chart page — cannot be asked on the device.
- **Severity:** blocks use (of a headline chart feature).
- **To close it:** feasible, moderate effort (~200 lines). Needs the SPX/GOLD/MSTR daily closes — the site's own files exist (`spx/gold/mstr-daily.json`, same shape as the BTC file the firmware already parses). Three more ~100-point float series in RAM (~1.2 KB). Rebase math + 3 extra lines + chip row UI. The chip row needs vertical room the chart page barely has (see R4 — the page is already full).

### R4 — Swipe navigation model: gone (even for the apps that exist)
- **Prototype:** six pages on a horizontal track, 0.34 s slide, wraps around, six page dots at the bottom (active dot widens, cyan), a hardware "Next screen" side button, and a swipe anywhere on the screen (fires past 34 px, horizontal-dominant). Entering landscape forces page 0. The dashboard copy states the design principle: "Six screens is what fits comfortably in ESP32 firmware — everything else is a swipe away, nothing is buried in menus."
- **C++:** three modes reached only by tapping small pills — Price and Auth are 16 px pills in a control row at the bottom of the chart page; Rotate is a 13 px pill in the scrub row; price-only exits by tapping anywhere. No dots, no next-screen button, no wrap-around, no gesture of any kind. The word "swipe" appears once in the firmware, in a comment explaining that a drag starting on a pill and sliding into the chart is explicitly *ignored*.
- **User-visible difference:** this is the regression Sunil named. There is no spatial model — apps have no "place", no dots showing where you are or how many apps exist, no one-gesture hop between apps. Reaching Authenticator means finding and hitting a small pill at the bottom of a crowded chart page; reaching price-only means finding another. The two missing apps (R1, R2) are unreachable by any means. The prototype's principle is inverted: in the firmware, everything *is* buried in small controls.
- **Severity:** blocks use (of the navigation model itself).
- **To close it:** feasible, no hardware blocker — see §2 for the full treatment. Needs the missing apps built first (swiping to a page that doesn't exist is pointless), then a page manager + swipe recogniser + slide animation + dots.

### R5 — Authenticator: regressed from a 3-account list to a one-account pager, and no hide-codes
- **Prototype:** all three accounts visible at once (PaperStreet, GitHub, Email) as rows with coloured avatars, issuer, account label and code; tap a row to enlarge its code in the box below; HIDE CODES button turns every code into `••• •••` (list + big box) for privacy.
- **C++:** one account at a time in a card; `< Prev` / `Next >` buttons cycle through them (max 4 accounts). No hide-codes control anywhere — a code is always on screen while Auth is open.
- **User-visible difference:** Sunil cannot see all his accounts at a glance, and cannot hide the codes when someone is looking over his shoulder. Cycling one-by-one through 3–4 accounts to find the right code is slower than scanning a list.
- **Severity:** noticeable. (Offset by a genuine gain: the firmware's codes are real RFC 6238 TOTP, the prototype's are demo hashes — see §3, G1.)
- **To close it:** feasible, small (~100–150 lines). A list view of up to 4 rows (same layout language as the prototype), tap a row to enlarge, plus a hide/show toggle that draws `••• •••`. No new data needed; the accounts and TOTP engine already exist.

### R6 — Sleep / wake + power management: missing
- **Prototype:** hardware power button toggles screen sleep (screen dims to ~6% brightness, a wake veil appears: "₿ SCREEN ASLEEP — TAP TO WAKE"); the side button also wakes. The device has a sleep state.
- **C++:** no sleep anywhere in the code (no `esp_sleep` calls, no backlight control, no power-button handling). The screen is on forever; the loop ends in `delay(20)`.
- **User-visible difference:** no way to turn the screen off; the device burns battery at full draw whenever it is on. The build plan's "~1 day always-on" battery figure assumes no sleep — with sleep it would last far longer in a pocket.
- **Severity:** noticeable (battery + a basic device behaviour).
- **To close it:** feasible, moderate effort, needs hardware verification. ST7789 sleep + backlight off (GPIO 38) is a few lines; waking on touch needs the CST816 interrupt pin (GPIO 16, currently polled, not used as IRQ) — light sleep with touch polling, or deep sleep with a GPIO wake (unverified whether GPIO 16 can wake from deep sleep on this board). Wi-Fi reconnect on wake also needed. This is the one item on this list whose exact wake path must be proven on the board.

### R7 — Live-data robustness: regressed (single source, no cross-check, no sanity gate)
- **Prototype:** spot price from **5 parallel sources** (mempool.space, CoinGecko, Coinbase, Kraken, the site's `prices.json`), cross-checked — a tick is trusted only if another independent source lands within 1.5% of it, or it is within 12% of the last good price / latest daily close; a lone wild tick is *never drawn*. `prices.json` trusted only if ≤15 min old. 9 s hard cap per poll. Manual "Refresh now" button; pause/resume polling.
- **C++:** CoinGecko primary, Coinbase spot fallback — one source at a time, no cross-check, no sanity gate against the last good price. `setInsecure()` — the TLS certificate is not verified, so a DNS-spoofing attacker could feed a fake price. No manual refresh, no pause.
- **User-visible difference:** mostly invisible when everything works — and then suddenly visible in the worst way: a bad tick or a spoofed response would be drawn as the price with no second opinion. The prototype was built to never show a wrong price; the firmware trusts the first answer it gets.
- **Severity:** noticeable (a correctness risk, not a daily annoyance).
- **To close it:** feasible, small-to-moderate. Cross-check CoinGecko against the Coinbase spot the firmware already fetches as fallback, plus a sanity gate vs the last-good price (the ±12% rule is a few lines). Certificate pinning via `setCACert()` with the ISRG Root X1 (the stricter alternative is already named in the code). Manual refresh needs a UI affordance (e.g. tapping the LIVE indicator); pause is less meaningful on an always-on device.

### R8 — Theme and brightness: partial (no theme control in landscape, no brightness)
- **Prototype:** Light / Dark / System theme (System follows the OS live), applied to the whole page and the device screen; brightness slider 45–100%.
- **C++:** Dark/Light toggle exists, but only as a pill on the portrait chart page — **there is no theme pill in landscape** (dropped for width), so a user in landscape cannot change theme without rotating back. No brightness/backlight control at all.
- **User-visible difference:** theme is a portrait-only setting; the screen brightness is fixed at full.
- **Severity:** noticeable (landscape) / cosmetic (brightness).
- **To close it:** theme pill in landscape is trivial in code but the landscape control row is already full (9 ranges + Line/Cndl + Portrait) — it needs a layout decision, not just a line of code. Brightness is a few lines (backlight PWM on GPIO 38 via `ledc`) plus a UI for it. Note: "System" theme is **not** a regression — a standalone device has no OS theme to follow; the firmware's persisted theme is the correct model.

### R9 — Touch goes dead during fetches (firmware-only wart)
- **Prototype:** fetches are async; the UI never blocks.
- **C++:** a price/chart fetch blocks the loop for seconds (HTTPS handshake on this chip); touch is unresponsive for 2–5 s during a fetch. The code mitigates it by running the Auth refresh before network polls, but a tap during a fetch is simply lost.
- **User-visible difference:** the device periodically ignores taps for a couple of seconds, with no indication why. On a 60 s poll cycle plus range-change fetches, this is a recurring dead spot.
- **Severity:** noticeable.
- **To close it:** hard to close fully on this stack — the Arduino HTTP client is synchronous. Options: shorten the stall (shorter timeouts, fewer concurrent fetches), or move fetches to the second core / an async client (bigger change). Partial mitigation is cheap; a full fix is a real piece of work.

### R10 — Price-only: exit model and details differ
- **Prototype:** a whole swipe screen; hint "NOTHING BUT THE PRICE — SWIPE FOR THE CHART"; 2 stats (sats per dollar, block height); change shown as "· 24h".
- **C++:** entered by the Price pill, exited by tapping *anywhere except the currency pill*. Hint "TAP PRICE FOR THE CHART". **4 stats** (sats, block, HIGH, LOW — more than the prototype). Change shows the current range span, not always 24h.
- **User-visible difference:** small. Tap-anywhere exit is arguably easier than swiping, but it is also easier to exit by accident (any stray tap on the screen leaves price-only). The extra HIGH/LOW stats are a gain (see §3).
- **Severity:** cosmetic.

### R11 — Chart small regressions (each small; listed together because none blocks use)
- **1D candle label is wrong:** the firmware labels the 1D candle view "24 x 1h" while its granularity is 900 s (15 min). The prototype's 1D candles are 24×1h. Cosmetic bug, one string.
- **Disabled 5Y/MAX pills still act:** in candle mode the 5Y/MAX pills render disabled (32% opacity + strikethrough, same as the prototype) — but tapping one still changes the range (and forces line). In the prototype a disabled button cannot be tapped. A user tapping a greyed-out pill gets a range change they didn't ask for. Noticeable quirk; fix is a disabled-check in `onTap`, a few lines.
- **Landscape change % is not stale-dimmed:** portrait dims the % while a fetch is in flight; `drawPriceL()` (landscape) has no `chartStale()` check, so landscape can show the old range's % at full brightness. Inconsistency, a few lines.
- **Scrub readout % reference differs:** prototype shows the scrubbed point's return **vs the range start**; firmware shows % **vs the last close**. Same screen, different number — the firmware's figure answers a different question. Cosmetic; one-line math change if Sunil prefers the prototype's version.
- **Chart point cap 100 vs prototype 120** (MAX range) — invisible at this screen size. Cosmetic.
- **5Y/MAX have no fetch fallback** (deliberate: the code refuses to show a misleading 300-day window as "5Y") and the **1Y fallback is only ~300 days** of Coinbase daily candles, still labelled "1y". The prototype's daily file covers the full range. Noticeable only when the daily file is unreachable.
- **Severity:** cosmetic (except the disabled-pill tap, which is noticeable).

### R12 — No manual refresh, no pause
- **Prototype:** "Refresh now" button (label flips to "Refreshing…" then "Refreshed ✓") and a Pause/Resume for the 60 s poll loop.
- **C++:** refresh happens only on its timers (60 s price, 15 min intraday chart, 60 min daily chart, 30 s retry). There is no way to force a fresh price, and no way to pause polling.
- **User-visible difference:** if the price looks stale, Sunil's only option is to wait for the next poll.
- **Severity:** cosmetic.
- **To close it:** feasible, small — needs a UI affordance (tap the LIVE indicator, or a small refresh target in the footer). Pause is of marginal value on a device.

---

## 2. The navigation-model regression (its own section)

**The prototype's model.** Six apps on a horizontal track. You move by swiping left/right (fires past 34 px, and only when the gesture is clearly horizontal — 1.4× the vertical movement — so a chart scrub never becomes a page change). The track slides 0.34 s with easing and wraps around, so from Authenticator one more swipe left lands back on the chart. Six dots at the bottom show where you are and how many apps exist (the active dot widens and turns cyan). A hardware side button, "Next screen", advances one page and also wakes the device. Entering landscape forces the chart page. The design principle is written on the page itself: *"Six screens is what fits comfortably in ESP32 firmware — everything else is a swipe away, nothing is buried in menus."*

**The firmware's model.** Three modes, no track, no dots, no wrap, no side button, no gesture. Chart is the home screen; price-only and Authenticator are reached by tapping 16 px pills ("Price", "Auth") in a control row at the bottom of the chart page; landscape is a 13 px "Rotate" pill in the scrub row. To get back you tap "Price" (from Auth) or tap anywhere (from price-only) or "Portrait" (from landscape). Nothing on screen tells you the other modes exist — there is no indicator of how many screens there are or where you are among them.

**What is lost, concretely:**
1. **A spatial model.** In the prototype every app has a place (chart → price-only → clock → Jade → Lightning → Auth) and the dots make that place visible. Sunil can build muscle memory ("two swipes left from the chart is the Jade QR"). In the firmware there is no "place" — only a mode you are in and pills you must find.
2. **One-gesture access.** A swipe is one gross motor gesture anywhere on the screen. The firmware's equivalent is a precise tap on a 13–16 px pill at the bottom of a crowded page — the smallest targets on the screen.
3. **Discoverability.** The dots advertise that six apps exist. The firmware advertises nothing; a user who doesn't already know Auth exists will never find it.
4. **The wrap-around.** From the last app, one more swipe returns home. The firmware has no equivalent loop.
5. **A wake path.** The side button wakes the device and advances a page in one press. The firmware has no wake concept at all (see R6).

**What a swipe implementation on this hardware would need:**
- **Input — already adequate.** The CST816 is a single-touch capacitive controller, polled every 50 ms, giving raw X/Y. A swipe is a one-finger gesture; multi-touch is not needed. The recogniser itself is ~30 lines: record the down-point, and on lift, fire if horizontal travel > ~34 px and clearly horizontal (the prototype's 1.4× rule), with the chart scrub taking precedence when the gesture starts inside the chart — the firmware already distinguishes "starts inside the chart" from "starts on a pill" for scrub.
- **Pages — the missing piece.** Swipe needs pages to swipe *to*. Today there are three modes and two of the prototype's six apps don't exist. The page manager (a small state machine: current page, direction, wrap-around) is the easy part; building the block clock and QR pages (R1, R2) is the real work.
- **Animation — feasible two ways.** (a) Redraw both pages per frame during the 0.34 s slide — the 8-bit parallel bus can push a full 170×320 frame in tens of milliseconds, so a 6–8 frame slide is plausible if each page draws fast. (b) Render each page once into a PSRAM sprite (170×320×2 bytes = ~109 KB per page; PSRAM is 8 MB) and blit the sprite with an X offset per frame — smoother, and the standard TFT_eSPI sprite approach. Either way there is no hardware blocker; the cost is code, not capability.
- **Dots — trivial.** Six small circles at the bottom of the screen, active one widened/cyan. The cost is 6×~12 px of vertical space the chart page doesn't currently spare — the layout would need a few pixels reclaimed from somewhere (the footer row is the obvious candidate).
- **Effort estimate:** recogniser + page manager + dots + slide animation ≈ 300–400 lines, once the missing apps exist. The apps themselves (R1–R3) are the larger job.

---

## 3. Gains — what the C++ version does better (or that the prototype lacks)

| # | Gain | Detail |
|---|---|---|
| G1 | **Real TOTP, not demo codes** | Firmware implements RFC 6238 properly (HMAC-SHA1, 30 s counter, dynamic truncation, verified against the RFC test vectors) with real, user-provisioned secrets. The prototype's codes are an FNV hash of a demo seed — they look right and change every 30 s, but they would never log Sunil into anything. This is the single biggest functional gain in the firmware. |
| G2 | **Persistence across reboots** | Currency, theme, range, chart type, price-only mode and all Auth accounts are saved in NVS and restored at boot. The prototype resets *everything* on reload (no localStorage at all). The firmware also keeps the last-good price across reboots. |
| G3 | **Honest stale state, on the device** | When a range tap is waiting on a fetch, the firmware dims the chart, tiles and % and shows "Updating…" in the scrub row. The prototype only signals staleness in the *dashboard* feed card — the device screen itself just keeps showing old numbers. |
| G4 | **Real battery %** | Firmware reads the battery via ADC (GPIO 4) and shows a real percentage + icon, or "USB" on USB power. The prototype's 87% is hardcoded on all six pages. |
| G5 | **Serial provisioning for real accounts** | `ADD / LIST / DEL / CLEAR` over USB serial (115200), with base32 validation, max 4 accounts, and secrets never printed in full. The prototype has no provisioning path at all — its three accounts are fixed demo rows. |
| G6 | **Visual polish beyond the prototype** | Price glow halo (dark mode); true high *and* low Y-axis labels (the prototype's three quarter-labels understated the HIGH tile — 1Y read "$89.2k" against a $96,929 tile); per-pixel interpolated area fill (the old per-point fill read as a comb texture); date X labels on 1M; smooth anti-aliased toggle capsules; brighter unselected pill text; range pills in a heavier font. |
| G7 | **Price-only shows more** | 4 stats (sats, block, HIGH, LOW) vs the prototype's 2 (sats, block). |
| G8 | **Hardening the prototype never had** | Malformed candle rows skipped (a zero close used to collapse the chart to 0); NVS writes throttled to ≤1 per 10 min to limit flash wear; `DEL` validates the index is numeric (so `DEL abc` can't silently delete account 0); failed font loads cached; `fmtMoney` bounds-guarded. |
| G9 | **Candle scrub snaps to the candle** | In candle mode the scrub dot snaps to the candle centre at its close, and the readout is that candle's close. The prototype's scrub snaps to the nearest *point* in both modes. |
| G10 | **Cheaper fetching** | Chart fetches only on range change or staleness (15 min intraday / 60 min daily) instead of the prototype's 60 s poll of everything. (Offset by R9: a fetch blocks touch for 2–5 s.) |

---

## 4. Full feature table

Status: **FULL** · **PARTIAL** · **DIFFERENT** · **MISSING** · **N/A** (simulator-only or not applicable on a device) · **GAIN** (firmware better).

### Navigation & screens

| Prototype feature | C++ status | Notes |
|---|---|---|
| 6 swipe pages (track, slide, wrap) | MISSING | 3 modes via pill taps; no track, no wrap |
| Swipe left/right (34 px, horizontal-dominant) | MISSING | No gesture recogniser; a drag starting on a pill is explicitly ignored |
| Page dots (6, active widens/cyan) | MISSING | No page indicator of any kind |
| Hardware "Next screen" side button | MISSING | No hardware-button handling at all |
| Hardware power button (sleep/wake) | MISSING | No sleep state; see R6 |
| Wake veil ("SCREEN ASLEEP — TAP TO WAKE") | MISSING | No sleep state |
| Landscape forces chart page | PARTIAL | Rotate is a pill tap, not a mode the device enters from any page; Auth/price-only can't rotate |
| Screen brightness slider | MISSING | Backlight is fixed on |
| Zoom 1×/1.5×/2×/2.5× | N/A | Simulator scaling, not a device feature |
| Theme Light/Dark/System | PARTIAL | Dark/Light on device, portrait only; "System" N/A (no OS) |
| Pause / Resume polling | MISSING | No poll control |
| "Refresh now" button | MISSING | Timers only |
| Screens jump buttons (dashboard) | N/A | Simulator scaffolding |

### Chart page

| Prototype feature | C++ status | Notes |
|---|---|---|
| 9 ranges (1D–MAX) | FULL | Same 9, same order |
| Line / Candles pill | FULL | Same; portrait says "Candles", landscape "Cndl" (inconsistent) |
| Candles only to 1Y; 5Y/MAX disabled in candle mode | FULL | Same; but tapping a disabled pill still changes range (R11) |
| Candle aggregation (24×1h … 52 weekly) | FULL | Same targets; 1D label wrongly says "24 x 1h" for 15-min data (R11) |
| Real OHLC intraday | FULL | Coinbase O/H/L/C used where available |
| Area fill 13% | FULL | Per-pixel interpolated fill (G6) |
| 3 gridlines | FULL | Same |
| End dot (line mode) | FULL | Cyan r=3 + ring |
| End dot hidden in candle mode | FULL | Verified: prototype sets opacity 0 in candle mode (line 1358) |
| Y labels ($, 3 quarter labels) | GAIN | Firmware adds true high + low labels |
| X labels from real timestamps | FULL | 5 labels + "Now"; dates on 1M+ |
| Scrub drag with readout | PARTIAL | Firmware: price·date + % vs last close; prototype: price·date + % vs range start; firmware clears on lift, prototype after 900 ms |
| Scrub line + dot | FULL | Same; candle snap is a gain (G9) |
| Change % from series | FULL | Same; falls back to CoinGecko 24h if no series |
| "Updated HH:MM" time | PARTIAL | Portrait only; landscape has no Updated time |
| Stat tiles: sats, block, HIGH, LOW | FULL | Same; labels vary by range in both |
| Comparison overlays SPX/GOLD/MSTR | MISSING | See R3 |
| Comparison % on chips (always shown) | MISSING | See R3 |
| Rebase-to-100 when comparing | MISSING | See R3 |
| TA overlays (SMA/EMA/RSI/Bollinger) | MISSING in both | Explicitly excluded in prototype; firmware has none either — parity |
| Big price tap toggles currency | MISSING | Prototype: tapping the price toggles USD↔CAD; firmware: price is not a touch target |
| Footer "CoinGecko · Coinbase" | GAIN | Firmware-only addition; prototype has no on-device footer |

### Price-only page

| Prototype feature | C++ status | Notes |
|---|---|---|
| Huge centred price | FULL | Firmware uses a larger font (OutfitXB30 vs XB29) |
| 24h change | FULL | Firmware shows current range span instead of always 24h |
| Cyan rule under price | FULL | Firmware adds a dim halo (dark only) |
| Stats: sats + block | GAIN | Firmware adds HIGH + LOW (4 stats) |
| USD/CAD pill | FULL | Same, centred |
| Hint "NOTHING BUT THE PRICE — SWIPE FOR THE CHART" | DIFFERENT | Firmware: "TAP PRICE FOR THE CHART" |
| Exit by swiping | DIFFERENT | Firmware: tap anywhere except the currency pill |
| "Updated" time | MISSING | Firmware price-only shows no Updated time |

### Block clock page

| Prototype feature | C++ status | Notes |
|---|---|---|
| Block height focus + 10-min ring gauge | MISSING | See R1 |
| Time since last block | MISSING | See R1 |
| Sats-per-dollar focus view | MISSING | (Sats appears as a tile on the chart page only) |
| Halving countdown (blocks to 1,050,000, bar, % of epoch, ≈APR 2028) | MISSING | See R1 |
| Auto-rotate focus every 12 s + dots to jump | MISSING | See R1 |
| Sats per $10 / $100 | MISSING | See R1 |
| Difficulty adjustment (progress %) | MISSING | See R1 |
| Network fees (fastest, sat/vB) | MISSING | See R1 |
| Mempool size (MB) | MISSING | See R1 |
| Big ET clock + date line (Ottawa) | MISSING | See R1 |
| "LIVE · AUTO" indicator | MISSING | See R1 |

### QR pages

| Prototype feature | C++ status | Notes |
|---|---|---|
| Jade QR page (on-chain receive) | MISSING | See R2 |
| Lightning QR page | MISSING | See R2 |
| Tap QR to flip to full address | MISSING | See R2 |
| Watch-only / receive-only warnings | MISSING | See R2 |
| (QRs scannable) | MISSING in both | Prototype QRs are decorative; firmware has none — a real QR would beat the prototype |

### Authenticator page

| Prototype feature | C++ status | Notes |
|---|---|---|
| 3 accounts visible as a list | PARTIAL | Firmware: one-at-a-time pager, max 4 accounts (R5) |
| Tap account to enlarge code | FULL | Firmware: Prev/Next + enlarged code card |
| HIDE CODES / SHOW CODES | MISSING | Codes always visible in firmware (R5) |
| Countdown "NEW CODES IN __s" + draining bar | FULL | Same, 30 s |
| Enlarged code box | FULL | Same |
| Demo note ("SIMULATION ONLY") | DIFFERENT | Firmware: "DEMO — not a real account" only for the seeded demo account; real accounts show a serial-add hint |
| Real TOTP codes | GAIN | Firmware: real RFC 6238; prototype: demo hash (G1) |
| Add accounts | GAIN | Firmware: serial ADD (G5); prototype: fixed 3 demo accounts |

### Data & refresh

| Prototype feature | C++ status | Notes |
|---|---|---|
| Spot price, 5 sources cross-checked + sanity gate | PARTIAL | CoinGecko + Coinbase fallback; no cross-check, no gate (R7) |
| Poll every 60 s | FULL | Same cadence |
| Retry every 15 s before first success | PARTIAL | Firmware retries failed fetches at most every 30 s |
| Intraday cache 5-min TTL | DIFFERENT | Firmware: refetch after 15 min |
| Daily file + history extension | PARTIAL | Firmware: daily file only; 5Y/MAX no fallback (R11) |
| Last-good data kept on failure | FULL | Both keep last-good; firmware adds dimming + "Updating…" (G3) |
| Lone wild tick never drawn | MISSING | No sanity gate (R7) |
| Certificate verification | MISSING | Firmware uses `setInsecure()` (R7) |
| FX CAD/USD | FULL | CoinGecko; carried forward on failure in both |
| Block height (mempool.space) | FULL | Firmware polls every 10 min |
| "Updated" timestamp | PARTIAL | Portrait chart only |

### Status bar & small things

| Prototype feature | C++ status | Notes |
|---|---|---|
| Status-bar clock | FULL | HH:MM, NTP-synced; "--:--" if unsynced |
| Wi-Fi icon | MISSING | Prototype's icon is static (never reflects connectivity) — cosmetic |
| Battery % | GAIN | Real ADC % vs hardcoded 87% (G4) |
| LIVE indicator | FULL | Firmware: LIVE/OFFLINE dot + text |
| Page-title headers ("BLOCK CLOCK", "AUTHENTICATOR · TOTP") | PARTIAL | Auth has one; block clock has no page |
| Hints ("Drag chart to scrub", etc.) | FULL | Same, plus "Updating…" while stale |
| Disabled-state rendering (greyed, struck-through) | FULL | Same rendering; behaviour differs (R11) |
| Empty states ("—", "--:--", "--- ---") | FULL | Same approach |
| Reduced-motion support | N/A | No OS setting on the device |
| Keyboard operation (QR cards) | N/A | No keyboard on the device |
| Chart aria-label / accessibility | N/A | No screen reader on the device |

### Persistence

| Prototype feature | C++ status | Notes |
|---|---|---|
| Remembers nothing (resets on reload) | GAIN | Firmware persists currency, theme, range, type, price-only, accounts + last-good price in NVS (G2) |

---

## 5. What could not be verified from the code (marked, not assumed)

- **Landscape touch remap on real hardware.** The firmware's remap (`dx = 319 − ty, dy = tx` for rotation 1) is derived from the ST7789 MADCTL value and is explicitly flagged in the code as the one thing that must be checked on the board, with a `setRotation(3)` fallback documented. Verified for internal consistency in the sim only.
- **Exact anti-aliasing of the smooth toggle capsules on the real panel.** The sim stub renders `fillSmoothRoundRect` as an SDF approximation; the real TFT_eSPI function (library ≥ 2.4, pinned ^2.5.0) should match, but the edge on glass is unproven.
- **Battery life and sleep behaviour.** No deep sleep exists in the code, so there is no sleep behaviour to verify; the "~1 day always-on" figure is a plan estimate, not a measurement.
- **Wi-Fi connection itself.** The firmware ships with placeholder credentials (`YOUR_WIFI_NAME` / `YOUR_WIFI_PASSWORD`); no connection has been proven on the board.
- **Touch responsiveness during fetches on the board.** The blocking-fetch stall (R9) is evident in the code; its exact duration on hardware depends on the TLS handshake, which varies.
- **QR scannability (prototype).** The prototype's QRs are provably decorative from the code (`drawQR` builds a seeded pseudo-random module grid); whether a phone camera would ever accidentally read one is untested and irrelevant — they encode nothing.
- **Whether the prototype's 1D fallback axis labels ever show in practice.** They only appear when live timestamps are absent; with live data the labels come from real timestamps. Noted as a fallback path, not a live behaviour.

---

## 6. Bottom line

The C++ version is not a port of the prototype — it is a **subset with a different navigation model, plus three things the prototype never had** (real TOTP, persistence, honest stale state). Counted strictly:

- **Whole apps missing:** 2 of 6 (block clock, QR pages — Jade and Lightning are two pages of one missing app area).
- **Headline features missing:** comparison overlays (R3).
- **Navigation model:** replaced wholesale (R4) — the single change Sunil feels most, because it affects every app, including the ones that exist.
- **Regressed interactions:** Authenticator list → pager, no hide-codes (R5); no sleep (R6); no data cross-check (R7).
- **Roughly at parity:** chart rendering (better in places), price-only, theme (portrait), status bar, refresh cadence.
- **Ahead:** real TOTP, NVS persistence, stale honesty, real battery %, serial provisioning, several visual details.

**What closing the gap would take, in total:** the three missing pieces are the block clock (~200–300 lines), the QR pages (~100–150 lines + a small QR library), and comparisons (~200 lines) — then the swipe page manager + animation + dots (~300–400 lines), the Auth list view (~100–150 lines), sleep/wake (moderate, hardware-verified), and the data-robustness work (small-to-moderate). Roughly **900–1,300 lines** on top of the current 2,826, against ~2.17 MB of free flash and ~268 KB of free RAM. No hardware blocker anywhere except the sleep wake path, which needs proving on the board. The touch controller, the display bus, the PSRAM and the flash all support everything on this list — the gap is build effort, not capability.
