# PaperStreet Keychain — ESP32 Firmware

Real C++ firmware for the PaperStreet BTC keychain. It turns a LilyGo
T-Display-S3 into a live Bitcoin price + chart device: a big BTC price,
the % change for the selected range, and a line or candle chart — the
same behaviour as the PaperStreet keychain web prototype, rewritten for
the ESP32-S3. There is no browser on this chip; every pixel is drawn by
hand and every number comes from a plain HTTPS request.

**Files in this folder**

| File | What it is |
|---|---|
| `paperstreet-keychain.ino` | The firmware. Open this in Arduino IDE. |
| `User_Setup.h` | Display config for the TFT_eSPI library (the library's own Setup206 for this exact board). |
| `platformio.ini` | Alternative build with PlatformIO (`pio run -t upload`). |
| `README.md` | This file. |

## Hardware

- **LilyGo T-Display-S3 Touch Edition** — ESP32-S3R8, 1.9" 170×320
  ST7789 TFT (8-bit parallel bus), CST816 capacitive touch, USB-C.
- A USB-C cable to flash it. A battery is optional (JST-GH, ≥580 mAh
  protected LiPo — see the build plan; a USB-only keychain is the
  safest v1).

## What it does

- **Big live BTC price**, USD by default (the international reference
  point), with a CAD toggle. % change for the selected range
  underneath, plus sats per dollar.
- **Chart:** line or candles, 9 ranges — 1D, 1W, 1M, 3M, 6M, YTD, 1Y,
  5Y, MAX. Candles work up to 1Y (24 × 1h on 1D, 52 weekly on 1Y);
  5Y and MAX are line-only, exactly like the prototype.
- **Light / dark** themes (the site's real palette), and a **price-only**
  mode that hides the chart and shows the price huge.
- **Touch:** tap the range buttons, the Line/Candles, USD/CAD,
  Light/Dark, Price and **Auth** buttons. Tap the chart area to leave
  price-only mode.
- **Landscape chart view:** tap the **Rotate** button on the chart
  and the chart redraws 320 px wide — turn the device clockwise to
  read it. Tap **Portrait** to go back. Chart only; price-only and
  Auth stay portrait. See below.
- **Authenticator (TOTP 2FA):** the **Auth** button opens a second
  screen that shows 6-digit time-based one-time passwords for up to
  4 accounts, with a countdown to the next code. A demo account
  ships on first boot (the public RFC 6238 test secret, labelled
  DEMO — not a real account). Add real accounts over USB Serial
  (see below). Codes are only correct when the clock is synced
  over NTP; until then the screen says so and shows dashes.
- **Live data:** price polls every 60 seconds; the chart is fetched
  only when you change range (and refreshed when stale). The last good
  price and chart stay on screen if Wi-Fi drops, and the last price is
  saved to flash so the screen is never blank on boot.
- Settings (currency, theme, range, chart type) and Auth accounts
  survive a reboot.

## Authenticator (TOTP) — how to use it

The Auth screen is a personal 2FA authenticator, like the app on
your phone, running on the keychain. It shows a 6-digit code for
each account, refreshing every 30 seconds, with a countdown and a
progress bar. Tap **< Prev** / **Next >** to switch accounts, and
**Price** to go back to the price screen.

**Adding accounts (USB Serial, 115200 baud).** Plug the board in,
open the Serial Monitor, and type one command per line
(case-insensitive):

| Command | What it does |
|---|---|
| `ADD <label> <base32secret>` | Add an account (label max 20 chars, secret max 64 chars, base32 A–Z / 2–7). Example: `ADD GitHub JBSWY3DPEHPK3PXP` |
| `LIST` | List accounts (the secret is shown as its first 4 chars only — the full secret is never printed) |
| `DEL <index>` | Delete the account at that index (see `LIST`) |
| `CLEAR` | Delete all accounts |
| `HELP` | Show the command list |

The secret is the base32 string from your 2FA setup — the one your
authenticator app normally gets from a QR code. Paste the secret
itself (the keychain has no camera, so it cannot scan the QR).
Up to 4 accounts fit. The shipped **Demo** account uses the public
RFC 6238 test secret (`GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ`, the test
vector for "12345678901234567890"); it is labelled DEMO on screen.
Delete it with `DEL 0` once you have added a real account.

**Security — read this.** The TOTP secrets are stored in the
ESP32's flash (Preferences / NVS) so they survive a reboot. This
chip has **no secure element**. Anyone who gets the device and can
read its flash can extract those secrets, so a stolen keychain
means the 2FA for those accounts must be treated as compromised:
revoke and re-enrol them. For real use, **enable ESP32 flash
encryption** (Arduino IDE: Tools → Flash Encryption, or
`pio run -t encrypted-upload`; back up the encryption key or the
device becomes unrecoverable) so the secrets are not sitting in
plaintext flash. The keychain still never holds a seed or a
private key and never signs anything — but a TOTP secret is enough
to generate valid codes for that account, so do not treat it as
harmless. Codes are only correct when the clock is synced (NTP
over Wi-Fi); with no Wi-Fi or before the first sync, the Auth
screen shows dashes and says the codes may be wrong.

## Landscape chart view

The chart can go landscape. Tap the **Rotate** button at the
top-right of the chart and it redraws 320 px wide — the whole point
is more of the series visible at once (up to 100 points spread over
312 px instead of 162). **Turn the device clockwise** to read it
(the USB-C end goes to the left). Tap **Portrait** on the landscape
control row to go back. The range and the line/candles setting are
kept when you rotate; nothing is reset.

- **Button, not tilt.** The keychain has no accelerometer, so
  rotation is a tap, not a physical tilt. The Rotate button only
  appears when the chart is on screen (not in price-only mode, and
  not before the first chart has loaded).
- **Chart only.** Only the chart view goes landscape. Price-only
  mode and the Auth screen stay portrait, and the device always
  boots in portrait — the landscape setting is not saved.
- **What you get in landscape:** the same price row (price + %
  change + sats/$), the same chart (line or candles, same range),
  all 9 range buttons in one row, and Line/Candles, USD/CAD and
  Light/Dark. There is no Auth button in landscape — tap Portrait,
  then Auth. There is no footer line (candle meaning / high-low)
  in landscape; that info is on the portrait screen.
- **Touch in landscape.** The touch chip reports in the panel's
  native (portrait) orientation, so the firmware remaps the
  coordinates when rotated (drawing x = 319 − native y, drawing y
  = native x, derived from the ST7789 MADCTL for `setRotation(1)`).
  **Check this on the real board:** if taps in landscape land
  mirrored (a tap on the left hits the right), the rotation is the
  other way — change `setRotation(1)` to `setRotation(3)` in
  `drawAll()` and the remap in `touchRead()` to
  `dx = ty, dy = 169 - tx`. See the comment in `touchRead()`.

## Data sources (all public, no API key)

| Data | Source | When |
|---|---|---|
| Price (USD + CAD + 24h %) | CoinGecko simple price | every 60 s |
| Price fallback (USD) | Coinbase spot price | if CoinGecko fails |
| 1D / 1W / 1M chart | Coinbase candles (15m / 1h / 6h) | on range change |
| 3M–MAX chart | paperstreetbtc.com daily closes file | on range change |

## Install & flash (Arduino IDE)

1. Install the **ESP32 board package** (Espressif): Arduino IDE →
   File → Preferences → Additional Boards Manager URLs, add
   `https://espressif.github.io/arduino-esp32/package_esp32_index.json`,
   then Tools → Board → Boards Manager → install **esp32**.
2. Install two libraries (Sketch → Include Library → Manage Libraries):
   - **TFT_eSPI** by Bodmer
   - **ArduinoJson** by Benoit Blanchon (v7)
3. Configure TFT_eSPI for this board: copy `User_Setup.h` from this
   folder **over** `Documents/Arduino/libraries/TFT_eSPI/User_Setup.h`
   (back up the original first). This is the library's own Setup206
   for the T-Display-S3 — the display is on an 8-bit parallel bus,
   not SPI, so the default setup will not work.
4. Open `paperstreet-keychain.ino`. At the top, fill in your Wi-Fi:
   ```cpp
   const char *WIFI_SSID = "YOUR_WIFI_NAME";
   const char *WIFI_PASS = "YOUR_WIFI_PASSWORD";
   ```
   (If you would rather not hard-code a password, use the WiFiManager
   library — it opens a captive portal on first boot so you can pick a
   network from your phone. The rest of the sketch does not depend on it.)
5. Board settings (Tools menu):
   - Board: **ESP32S3 Dev Module** (or "LilyGo T-Display-S3" if you
     installed LilyGo's board package)
   - USB CDC On Boot: **Enabled**
   - Flash Size: **16MB**
   - **PSRAM: "OPI PSRAM" / Enabled** — required. The daily history
     file is ~135 KB of JSON and is parsed in PSRAM.
   - Partition Scheme: Default
   - Upload Speed: 921600
6. Plug the board in over USB-C, pick the port, and hit Upload.
   Open the Serial Monitor at 115200 to watch it connect and fetch.

**PlatformIO instead:** copy this folder, put the sketch in `src/`
(`mkdir -p src && cp paperstreet-keychain.ino src/`), then
`pio run -t upload`. The `platformio.ini` already enables PSRAM and
carries the whole display setup as `-D` flags (the documented TFT_eSPI
method for PlatformIO — `User_Setup.h` is only for the Arduino IDE
path, PlatformIO ignores it). If the display setup is wrong you will
get a clear compile error from the guard at the top of the sketch,
not a silently wrong build.

## Limitations — what to expect

- **No browser, no HTML/JS/CSS.** All drawing is pixel-by-pixel, so
  the UI is deliberately simple: built-in fonts, flat colours, no
  anti-aliased text. It looks like a device, not a web page.
- **Memory is tight.** Only ~100 chart points are kept (the screen is
  170 px wide, so more would be invisible anyway). Long ranges are
  downsampled to ~100 points, and 1Y daily candles (365) are
  aggregated into 52 weekly candles.
- **HTTPS is heavy.** Each fetch takes a few seconds for the TLS
  handshake. That is why the price polls once a minute and the chart
  only on range change — not continuously.
- **Certificate check is off** (`setInsecure()`): the connection is
  still encrypted, but the chip does not verify the server's
  certificate. For a public price feed that is the accepted trade;
  the sketch comments explain how to pin the Let's Encrypt root CA
  if you want the strict version.
- **CoinGecko rate limits.** The free API allows roughly 10–30 calls
  a minute; we make one a minute, which is fine. If it ever answers
  429, the firmware falls back to Coinbase spot and retries.
- **Wi-Fi must stay connected.** The sketch reconnects automatically,
  and the last good data stays on screen while it does. There is no
  deep-sleep in v1 (it would pause the live price); the battery will
  last hours, not days. Deep-sleep between polls is a future option.
- **No comparisons, no TA, no QR screens in v1.** The web prototype
  has SPX/GOLD/MSTR comparison chips; the keychain is BTC-only by
  design (see the build plan). QR receive screens are a separate
  step, and the keychain must never hold a seed or private key.
- **The Auth screen stores TOTP secrets in flash.** That is the
  one secret this firmware does hold (see the Authenticator section
  above). No secure element, so treat a stolen keychain as
  compromised 2FA and enable flash encryption for real use.
- **TOTP needs the clock.** Codes are only correct when NTP has
  synced the clock over Wi-Fi. With no Wi-Fi, or before the first
  sync, the Auth screen shows dashes instead of a code.
- **Wokwi emulator:** the ST7789 part in Wokwi is display-only
  (no touch), so the on-screen buttons do not tap there — including
  the Auth screen's Prev / Next / Price buttons and the chart's
  **Rotate** button. The Auth screen is view-only in Wokwi (it still
  boots, fetches the price, and draws the chart and the demo code
  once the clock syncs). To preview the landscape chart in Wokwi,
  temporarily set `landscape = true` in the sketch before
  `setup()` calls `drawAll()` — do not ship that change in the real
  firmware, which must boot in portrait. Use the real board, or the
  Serial commands, to change accounts.

## Troubleshooting

- **Black screen:** GPIO 15 must be HIGH to power the display — the
  sketch does this in `setup()`. If you still get black, check the
  TFT_eSPI `User_Setup.h` was copied (step 3) and the board settings.
- **"Guru Meditation" / reboot loop:** usually PSRAM not enabled, or
  the wrong flash size. Set PSRAM to OPI and Flash Size to 16MB.
- **Price shows but the chart says "fetching chart...":** the chart
  fetch needs Wi-Fi plus a successful price poll first. Check the
  Serial Monitor — a failed fetch prints why.
- **Touch does nothing:** the touch chip is a CST816 at I2C 0x15
  (a few early boards used a CST328 at 0x1A — the sketch probes both).
  If taps land mirrored, uncomment the flip lines in `touchRead()`.
- **Wrong colours (red/blue swapped):** change `TFT_RGB_ORDER` to
  `TFT_BGR` in `User_Setup.h`.
- **"OFFLINE" in the status bar:** Wi-Fi is down or both price
  sources failed. The last good price stays on screen with its age.
