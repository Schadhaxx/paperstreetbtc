# PaperStreet keychain — phases 1–3 handoff

**Branch:** `keychain-rebuild` in `Schadhaxx/paperstreetbtc`  
**Tip:** `27879e89bd001d7279064b0050d1f7b5e97dc03b`  
**Date:** Friday 27 Nov 2026, 3:00 PM ET (America/Toronto)  
**For:** Sunil, via Site Launch / Grok Bot  
**Scope:** UI-layer rebuild of the C++ firmware against the Spaces prototype. No changes to `main`, `data`, `keychain-handover`, the live site, or the public Netlify sim.

Checkout used for this work: `/workspace/keychain-handover/repo`.  
Side-by-side shots: `/workspace/keychain-handover/shots/phase1/`, `phase2/`, `phase3/`.

---

## Commits

All of these are on `keychain-rebuild` only, pushed with a plain fast-forward (no force).

### Phase 1 — main price-and-chart screen
- `ed3e1d0517e672c963c2c1d95dbd5fdaeaea9cfd` — restack the chart page to match the prototype (header, plot, type/VS/ranges, stat tiles; drop Dark/Light/Price/Auth shortcut pills from this page; tap the big price for USD/CAD).

### Phase 2 — the other four screens (one commit per screen)
- `056ec9875e1e388e09c4bb6f37b72757f778057b` — price-only: just the price, always show the 24h change, drop HIGH/LOW / Updated / brightness stepper, swipe back to the chart.
- `e3b8bbe1ce38c823d62a5f9cf0407a7f49052971` — block clock: 12-hour time, capsule focus dots, LIVE · AUTO as a green live-dot, drop shortcut pills.
- `06c6412f19d1f7a43776af0d0efaa2ec937af4b2` — QR: coloured Jade / Lightning badges, compact flipped address card.
- `8a73b9470e4c519da848602c272f22ab054a27fb` — authenticator: HIDE CODES / SHOW CODES wording, 44 px rows, drop Price/Clock/QR pills.

### Phase 3 — feel, plus low-risk polish
- `14c577b75d2e2bfa252ef3810b96ef4e82317710` — swipe slide feel: both pages captured once and composited as a moving track, 0.34 s, `cubic-bezier(.32,.72,.28,1)`, no per-frame redraw.
- `aa36be0d1cf205826ef0d699ec9264777ab86378` — page dots: 5×5 inactive, 13×5 active capsule, 5 px gaps, 5 px above the bottom edge, prototype inactive colours.
- `6ed1980edfac99b9d0d173582ea0dc352b65bb0f` — immediate press feedback on finger-down, without waiting for a full-screen redraw.
- `27879e89bd001d7279064b0050d1f7b5e97dc03b` — muted `C_PILL2` (#67748e), 1Y axis packing so a long “Nov” cannot clip, “PaperStreet” fits in the auth row.

Auth, QR encode/ECC, data fetches, Wi-Fi, TOTP, and NVS logic were not redesigned. No new features, and no new theme or brightness controls were added.

---

## What changed, in plain words

**Phase 1.** The chart page was restacked to follow the prototype’s order: status, “BITCOIN · LIVE PRICE” + block + currency pill, big price, change line, scrub hint, plot, axis, Line/Candles, VS chips, ranges, stat tiles, page dots. The extra theme / Price / Auth shortcut pills came off this page. Tapping the big price switches USD/CAD, as in the prototype. Landscape Light/Dark and Rotate stay in the landscape / scrub row.

**Phase 2.** Price-only is once again “nothing but the price”: 24h change always on, two-stat column kept (those are in the prototype), brightness stepper and HIGH/LOW / Updated gone, swipe (not tap) goes back to the chart. The block clock uses 12-hour time with seconds and “PM ET” (Sunil’s call; the prototype’s JS clock is 24-hour). Focus dots are capsules, wider when active. QR pages got a green “J” badge and an amber lightning badge (the bolt is drawn; ϟ is not in the device fonts). A flipped QR is a compact address card, not a tall empty box. The authenticator uses the prototype hide/show wording and 44 px list spacing. Shortcut pills were dropped on all four of these screens (Sunil: “Drop them, match the prototype”); swipe and dots are the navigation.

**Phase 3.** A swipe now moves both pages together, like the prototype’s track, with the same 0.34 s cubic-bezier easing, instead of uncovering a stationary incoming page and redrawing it every frame. Page dots match the prototype’s size, colour, and placement. Tapping a pill lights it in the on-state as soon as the finger goes down; the full redraw happens after the lift. `C_PILL2` is the prototype’s muted grey rather than the earlier brightened one. Axis labels are packed so a 1Y “Nov” cannot run into “Now” or off the edge. “PaperStreet” in an auth row is no longer clipped to “PaperStree” (the code-area clear was overpainting the last letter).

---

## Screenshots

### Phase 1
`/workspace/keychain-handover/shots/phase1/` — chart side-by-sides (1D line dark/light, 1Y candles, 1Y line with a comparison) and `phase1-chart-comparison.png`.

### Phase 2
`/workspace/keychain-handover/shots/phase2/` — side-by-sides for price-only (dark/light), clock focuses 0–2, Jade/Lightning QR (unflipped and flipped), authenticator shown/hidden and a 4-account spacing check, plus `phase2-contact-sheet.png`.

### Phase 3
`/workspace/keychain-handover/shots/phase3/`

- `slide-p1-p2-strip.png` — prototype vs firmware frame sequence, price-only → block clock, seven eased samples from t=0 to t=1.
- `dots-side-by-side.png` and `dots-closeup-side-by-side.png` — page-dot size and placement.
- `tap-1w-sequence.png` — idle (1D selected) → finger down on 1W (pill lights, chart still 1D) → after lift (1W selected, chart redrawn).
- `axis-1y-side-by-side.png` — 1Y axis packing and muted secondary text.
- `auth-paperstreet-side-by-side.png` — full “PaperStreet” in the auth row.
- `phase3-contact-sheet.png` — all of the above on one sheet.

Prices, clock time, and TOTP codes differ on purpose (live prototype vs local sim snapshot). Compare the layout and the motion.

---

## Test results (Phase 3 tip)

Recompiled against the current `.ino` and ran the full native sim suite. All passed:

| Harness | Result |
|---|---|
| `range-fix-test` | PASS |
| `swipe-test` | PASS (wrap, mid-slide two-page composite, clock dots, swipe-back from price-only, pill-start swipe) |
| `live-tap-check` | PASS |
| `tour-seq-test` | PASS |
| `fetch-path-check` | PASS |
| `ring-check` | PASS |
| `step3-frames` | PASS |
| `edge-case-test` fail (`data-empty` + good `data`) | 9/9 PASS |
| `edge-case-test` poison (`data-poison`) | 8/8 PASS |
| `edge-case-test` interact (`data`) | 19/19 PASS |
| `new-apps-frames`, `auth-list-4up`, `refine-frames` | compiled and ran PASS |

No WASM rebuild (no emsdk on the box used for this work). The public Netlify sim was not modified.

---

## Accepted deviations

These were shown to Sunil during phases 1–2, or are honest limits of the fonts / data model. They still stand unless he asks to change them.

- **Status bar** shows LIVE / USB rather than the prototype’s Wi-Fi icon + battery %. Battery % and the real radio are hardware-unverified.
- **1D VS chips** stay hidden (flat +0% data on a 1D window).
- **Rotate** remains a small control on the chart scrub row (the prototype’s landscape control is on the dashboard around the device).
- **Clock is 12-hour** with “PM ET”, per Sunil. The prototype’s JS clock is 24-hour. The status bar stays 24-hour, matching the prototype status bar.
- **Halving title** “NEXT HALVING · THE CLOCK INSIDE THE CLOCK” is split onto two lines (it does not fit one Mono 6 line).
- **“~ APR 2028”** — ≈ is not in the device fonts.
- **Some clock tile labels** are shortened (“DIFFICULTY ADJ”, “FEES · FASTEST”) to fit.
- **QR lightning mark** is drawn geometrically; ϟ is not in any `.vlw`.
- **Flipped QR** has “TAP ANYWHERE TO GO BACK” on the page background. The prototype hides the QR card when flipped and has no obvious unflip control.
- **QR patterns** can still differ from the prototype’s JS generator (encode/ECC were not changed).
- **Auth has no “personal login” subline.** Accounts store only a label; the issuer is vertically centred. The Email avatar is “E” (first letter of the label); the prototype uses “M”.
- **Auth demo footer** is the shorter “DEMO CODES - SIMULATION ONLY”, plus “Codes refresh every 30 s”.
- **Em dash** is a middot in device copy (“NOTHING BUT THE PRICE · SWIPE FOR THE CHART”).
- **Brightness** is still stored in NVS (45–100%) but has no on-screen control after the price-only stepper was removed. Landscape still has Light/Dark.
- **C_PILL2** is now the prototype muted grey (#67748e, rounded to RGB565 #687488). At 6–7 px this is quieter than the old brightened #93a5c4; if it ever reads too faint on the real panel, that is worth a look on hardware.
- **1Y axis format** is still “Nov 24” (month + day), not the prototype’s “Nov '25” (month + year).
- **WASM / public sim** was not rebuilt.

---

## Unverified on hardware

Nothing in these three phases was run on a LilyGo T-Display-S3. Still unverified, and worth a first-device pass:

- Real ST7789 panel, colours, and font weight at 170×320 (especially muted `C_PILL2` and the 6–7 px labels).
- CST816 feel: swipe vs scrub vs long-press-sleep, mid-slide abort, and the new immediate press highlight vs actual tap latency.
- The 0.34 s two-buffer track slide on device (needs PSRAM; ~218 KB for the two frame buffers). Landscape and a failed buffer alloc still cut instantly.
- Battery % in the status bar, backlight PWM, light-sleep / veil, GPIO wake.
- Phone-camera scan of the nayuki QRs.
- TLS / Wi-Fi on the board, NTP, and real (non-demo) TOTP against a phone authenticator.
- Landscape touch remap.

---

## How to build, simulate, and flash

The sketch is `keychain/firmware/paperstreet-keychain.ino`. The board is a LilyGo T-Display-S3 Touch (ESP32-S3R8, 170×320 ST7789, CST816). PSRAM must be on — the daily history parse and the slide buffers use it.

**Fonts.** The 16 `.vlw` files are gitignored. Generate them with `keychain/sim/tools/genvlw.py` from the official Outfit, Inter, and IBM Plex Mono TTFs, and copy them into both `keychain/sim/data/` and `keychain/firmware/data/`. The firmware falls back to built-in fonts if a face is missing.

**Wi-Fi.** Credentials in the sketch are placeholders (`YOUR_WIFI_NAME` / `YOUR_WIFI_PASSWORD`). Do not commit real secrets.

### Local native sim (what this work used)

There is no emsdk on the machine that did phases 1–3, so the public WASM sim was not rebuilt and should not be overwritten as part of this branch.

```sh
cd keychain/sim
# ArduinoJson 7.4.2 is expected at sim/third_party/ArduinoJson (also gitignored).
./build-native.sh -o /tmp/swipe-test tools/swipe-test.cpp \
    src/stubs.cpp src/tft.cpp src/md.cpp \
    ../firmware/lib/qrcodegen/qrcodegen.cpp
/tmp/swipe-test data
```

The other harnesses in `keychain/sim/tools/` take the same shape. `data/`, `data-empty/`, and `data-poison/` are the fixture directories.

### PlatformIO (device)

From `keychain/firmware/platformio.ini`:

```sh
cd keychain/firmware
mkdir -p src && cp paperstreet-keychain.ino src/
pio run                 # build
pio run -t upload       # flash the sketch
pio run -t uploadfs     # LittleFS: the .vlw fonts in data/
```

Serial monitor is 115200 baud. Auth accounts are provisioned over USB: `ADD <label> <base32secret>`, `LIST`, `DEL <index>`, `CLEAR`, `HELP`. `LIST` prints only the first four characters of a secret.

### Arduino IDE (device)

Open `paperstreet-keychain.ino`. Display setup for the IDE build is `User_Setup.h` (TFT_eSPI Setup206 for this board). Enable PSRAM, flash the sketch, and upload the LittleFS data folder so the fonts land on the device.

---

## Open decisions for Sunil

Theme and brightness are **not** on the portrait screens any more, and no new controls were added. The prototype keeps both on the dashboard around the device, not on the keychain screen itself. Landscape still has Light/Dark in the scrub row. Brightness (45–100%) is still saved in NVS but has no on-screen stepper.

Options, if he wants a control somewhere:

1. **Leave them on the dashboard only**, as the prototype does — Theme in Display, brightness on the page around the device. The keychain screen stays clean. This is the closest match.
2. **Landscape scrub row**, next to the existing Light/Dark pills. Portrait stays clean; brightness could join them there.
3. **A long-press or hold-on-the-status-bar gesture** that opens a small theme / brightness overlay, without a new track page.
4. **A dedicated settings screen**, reached by a special gesture or a new swipe page. That would be a new feature, not a prototype match.
5. **No on-device control** — theme from landscape only (or a one-time NVS default), brightness only via NVS / a future serial command.

Everything else that still differs from the prototype is listed under Accepted deviations. The next hardware pass should settle whether muted `C_PILL2`, the slide buffers, and CST816 swipe/tap feel are good enough on the real panel.
