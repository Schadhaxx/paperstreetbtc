# PaperStreet keychain — handover for Site Launch

**Branch:** `keychain-handover` (in `Schadhaxx/paperstreetbtc` — this branch only;
nothing here touches `main` or the live site.)
**Date:** 25 Nov 2026
**For:** Site Launch, via Grok Bot
**From:** Pepper (Muse), for Sunil

## The job

Sunil is unsatisfied with many of the UI and usability regressions in the C++
version of the keychain compared with the original Spaces prototype. Your call:

- **Improve the C++ version** until it matches the Spaces prototype, or
- **Rebuild it** from the Spaces prototype if that is cleaner.

Both builds are in this folder so you can decide from the code, not from a
description. There is no token budget set for this — use your judgment, and
check back with Grok Bot if the rebuild grows.

## The two builds

| | Original (design target) | Current (C++ implementation) |
|---|---|---|
| Path | `spaces-prototype/index.html` | `firmware/paperstreet-keychain.ino` |
| What it is | The Spaces prototype Sunil approved — open `index.html` in a browser, it just runs | Real ESP32 firmware (Arduino sketch, 4,884 lines) for the LilyGo T-Display-S3 Touch, 170×320 ST7789 |
| Run it | Open the file | See `sim/` below, or the live sim link |

Live running version of the C++ build:
**https://paperstreet-keychain-sim.netlify.app**
(89-second tour video is on that page.)

## What the device is

- **Hardware:** LilyGo T-Display-S3 Touch, 1.9" ST7789 170×320, CST816 touch.
  Not yet tested on real hardware — everything below was verified in the sim.
- **Screens (swipe between them):** chart → price-only → block clock → Jade QR →
  Lightning QR → Authenticator (TOTP). Wrap-around, dots, 0.34 s slide.
- **Data:** CoinGecko spot price (60 s poll, Coinbase fallback), candles from
  Coinbase + the site's daily file. Comparisons SPX / GOLD / MSTR rebased to 100.
  Ranges 1D–MAX. USD default, CAD one tap away.
- **Other:** real TOTP (RFC 6238, up to 4 accounts, serial provisioning),
  real scannable QRs (nayuki qrcodegen, vendored in `firmware/lib/`),
  light sleep with veil, NVS persistence, theme + brightness.
- **Firmware build:** PlatformIO, see `firmware/platformio.ini` and
  `firmware/README.md`. Needs PSRAM. Wi-Fi credentials are placeholders
  (`YOUR_WIFI_NAME` / `YOUR_WIFI_PASSWORD`).

## Current state (25 Nov 2026)

- Fix loop complete 24 Nov: gap fixes + 2 analyze-and-fix rounds (5 passes).
  Final live check 24 Nov: all 9 items passed. Compile + all harness tests pass.
  RAM 20.1%, Flash 41.6%.
- **Known nits (not fixed):** last 1Y x-axis "Nov" label slightly clipped at the
  right edge; Auth page "Price" button goes to the chart page, not price-only;
  QR flipped cards still ~25–30% empty below the last line; fast-tap highlight
  lags 0.3–0.5 s.
- **Never verified on hardware:** deep-sleep GPIO-16 wake; landscape touch
  remap; QR scannability on a real phone camera; TLS chains on the board;
  backlight PWM / sleep brightness.
- **Background:** `docs/gap-analysis-2026-11-24.md` is the feature-by-feature
  comparison of the firmware against the prototype (24 Nov, before the fix
  loop). It is reference for the rebuild decision, not a work list.

## The sim (how to run the C++ build in a browser)

`sim/` compiles the unmodified firmware sketch to WebAssembly with Emscripten:

- `sim/build-wasm.sh` — builds it; `sim/web/` is the page (open `index.html`).
- `sim/src/` — the harness (`wasm.cpp`, `stubs.cpp`, `tft.cpp`, `main.cpp`).
- `sim/data/` — snapshot data the sim runs on (Nov 24). `sim/tools/` — the
  verification harnesses used during the fix loop (ring, swipe, edge-case,
  fetch-path, live-tap) plus `genvlw.py` / `genfont.py` (font generation).

## Not in this repo (binary, can't be pushed this way)

- **`.vlw` fonts** (15 files, Outfit / Inter / IBM Plex Mono, in `firmware/data/`
  on the build machine): regenerate with `sim/tools/genvlw.py` from the
  matching TTFs, or ask Pepper for the files. The firmware degrades gracefully
  if a font is missing (falls back, caches the failure).
- **Built `keychain.wasm` + tour video:** on the live sim link above.
- **Demo TOTP account** in the firmware uses the public RFC 6238 test secret —
  it is not a real account.

## Out of scope

- No new features, no behaviour changes beyond what the rebuild needs.
- The Pi prototype / blind oracle are separate and are not in this handover.
- Do not touch the live site (`paperstreetbtc.com`) or `main` — this branch
  only. If the rebuild lands anywhere, that is a separate decision with Sunil.
