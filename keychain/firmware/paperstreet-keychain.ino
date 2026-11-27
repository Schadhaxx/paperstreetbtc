/*
  PaperStreet Keychain — ESP32 firmware (LilyGo T-Display-S3)
  ============================================================
  A real, ready-to-flash Arduino sketch for the PaperStreet BTC
  keychain. It shows a big live BTC price, the % change for the
  selected range, and a line or candle chart — the same behaviour
  as the PaperStreet keychain web prototype, rewritten in C++ for
  the ESP32-S3. There is no browser on this chip: every pixel is
  drawn by hand with TFT_eSPI, and every number comes from a
  plain HTTPS request parsed with ArduinoJson.

  The chart can also go landscape: tap Rotate on the chart and it
  redraws 320 px wide (turn the device clockwise). There is no tilt
  sensor — rotation is a button tap, and it only ever applies to the
  chart view. Price-only and the Auth screen stay portrait, and the
  device always boots in portrait.

  Look: the screen matches the PaperStreet keychain web prototype —
  the same colours, Outfit / Inter / IBM Plex Mono at the same
  sizes, the same pills, stat tiles and chart weights. The type is
  drawn with TFT_eSPI smooth (anti-aliased) fonts from .vlw files
  in data/ (LittleFS). Upload them with "pio run -t uploadfs" or
  the Arduino IDE's ESP32 Sketch Data Upload. If the font files
  are missing, the sketch still works — it falls back to the
  built-in bitmap fonts (blocky, but readable).

  Hardware: LilyGo T-Display-S3 Touch Edition
    ESP32-S3R8, 170x320 ST7789 TFT (8-bit parallel bus),
    CST816 capacitive touch, USB-C, JST-GH battery connector.

  Libraries (install from the Arduino Library Manager):
    - TFT_eSPI by Bodmer  (display — needs the User_Setup.h
      supplied next to this sketch; it is the library's own
      Setup206 for this exact board)
    - ArduinoJson by Benoit Blanchon, v7

  Board settings (Arduino IDE, Tools menu):
    - Board: "ESP32S3 Dev Module" (or "LilyGo T-Display-S3"
      if you installed LilyGo's board package)
    - USB CDC On Boot: Enabled
    - Flash Size: 16MB
    - PSRAM: "OPI PSRAM" / Enabled  <-- REQUIRED. The daily
      history file is ~135 KB of JSON and is parsed in PSRAM.
    - Partition Scheme: Default
    - Upload Speed: 921600

  Wi-Fi: fill in WIFI_SSID / WIFI_PASS below. If you would
  rather not hard-code a password, use the WiFiManager library
  (tzapu/WiFiManager) — it opens a captive portal on first
  boot so you can pick a network from your phone. The rest of
  this sketch does not depend on it.

  Data (all public, no API key):
    - Price every 60 s: CoinGecko simple price (USD + CAD +
      24h change). Fallback: Coinbase spot price.
    - Chart: Coinbase candles for 1D / 1W / 1M; the
      paperstreetbtc.com daily closes file for 3M and longer.
      Candles are fetched only when the range changes (and
      refreshed when stale), never every minute.
    - The last good price and chart stay on screen if the
      network drops, and the last price is saved to flash
      (Preferences) so the screen is not blank on boot.

  Security notes (read before you build):
    - This sketch never holds a seed or a private key and it
      never signs anything. It only DISPLAYS a price and a
      chart — plus, on the Auth screen, TOTP (2FA) codes.
    - The Auth screen DOES store secrets: your TOTP (2FA)
      secrets are saved in the ESP32's flash (Preferences /
      NVS) so they survive a reboot. This chip has NO secure
      element. Anyone who gets the device and can read its
      flash can extract those secrets. Treat a stolen
      keychain as compromised 2FA: revoke and re-enrol the
      affected accounts. For real use, enable ESP32 flash
      encryption (see README) so the secrets are not sitting
      in plaintext flash. Do not assume the secrets are safe
      because they are "just 2FA" — a TOTP secret is enough
      to generate valid codes for that account.
    - TOTP codes are only correct when the clock is synced.
      The sketch syncs time over NTP on Wi-Fi; if it has no
      Wi-Fi or the clock has not synced yet, the Auth screen
      says so and does not present a code as valid.
    - HTTPS verifies the server's certificate against a baked-in
      bundle of trust roots (ISRG Root X1 for Let's Encrypt,
      DigiCert G2/G3/G5, Google Trust Services R1/R4 — see
      ROOT_CA_BUNDLE above section 11). A fetch whose chain does
      not land on one of those roots fails closed: the last-good
      price stays on screen. The per-host chains are the best
      public information available and are NOT proven against the
      live hosts — confirm them on the board before trusting TLS
      there (see the bundle comment). The sim cannot verify TLS.
*/

#include <Arduino.h>
#include <math.h>        // sinf/cosf for the block-clock ring gauge
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <Wire.h>
#include <time.h>
#include <strings.h>      // strcasecmp (Serial commands)
#include <TFT_eSPI.h>
#include <LittleFS.h>    // smooth .vlw font files live in data/
#include <mbedtls/md.h>   // HMAC-SHA1 for TOTP (bundled with the ESP32 core)
// Arduino's LOW/HIGH macros (esp32-hal-gpio.h: LOW 0x0, HIGH 0x1)
// collide with qrcodegen::QrCode::Ecc::LOW/HIGH, so they are
// undefined for this include and restored right after it. The
// sketch's own uses of LOW/HIGH are all below this point.
#ifdef LOW
#undef LOW
#endif
#ifdef HIGH
#undef HIGH
#endif
#include "qrcodegen.hpp"   // nayuki QR Code generator (MIT) — lib/qrcodegen/
#include <stdlib.h>         // malloc (slide capture buffer, sim + PSRAM fallback)
#ifdef ARDUINO_ARCH_ESP32
#include <esp_heap_caps.h>  // heap_caps_malloc(MALLOC_CAP_SPIRAM) for the slide buffer
#include <esp_sleep.h>      // light sleep while the screen is asleep (R6)
#endif
#define LOW 0x0
#define HIGH 0x1

// Forward declarations: the Arduino IDE auto-generates these, but
// the sim harnesses include this sketch as a .cpp and need them
// spelled out (setF lives in section 10, the cmp helpers in
// section 11 — both are called from earlier code).
void setF(const char *vlw, int fallback);
bool cmpAnyOn();
bool cmpAnyOk();
float cmpPct(int c);
int httpsGet(const char *url, WiFiClientSecure &client, HTTPClient &http,
             int timeoutMs = 5000);

// Compile-time guard: this sketch only works with the ST7789
// 170x320 display on its 8-bit parallel bus. If you see one of
// these errors, the display setup is wrong — Arduino IDE: copy
// User_Setup.h from this folder over the TFT_eSPI library's
// User_Setup.h (see README step 3). PlatformIO: the setup is
// carried by the -D flags in platformio.ini.
#ifndef ST7789_DRIVER
  #error "ST7789 driver not selected — copy User_Setup.h (Arduino IDE) or use platformio.ini (PlatformIO)"
#endif
#ifndef TFT_PARALLEL_8_BIT
  #error "8-bit parallel bus not selected — this board is NOT SPI (see User_Setup.h / platformio.ini)"
#endif
#if !defined(TFT_WIDTH) || TFT_WIDTH != 170 || !defined(TFT_HEIGHT) || TFT_HEIGHT != 320
  #error "Display must be 170x320 (see User_Setup.h / platformio.ini)"
#endif

// ------------------------------------------------------------------
// 1. Wi-Fi — FILL THESE IN (or use WiFiManager, see the header note)
// ------------------------------------------------------------------
const char *WIFI_SSID = "YOUR_WIFI_NAME";
const char *WIFI_PASS = "YOUR_WIFI_PASSWORD";

// ------------------------------------------------------------------
// 2. Data sources (verified live 22 Nov 2026)
// ------------------------------------------------------------------
const char *URL_COINGECKO_PRICE =
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin&vs_currencies=usd,cad&include_24hr_change=true";
const char *URL_COINBASE_SPOT =
    "https://api.coinbase.com/v2/prices/BTC-USD/spot";
const char *URL_COINBASE_CANDLES =
    "https://api.exchange.coinbase.com/products/BTC-USD/candles";
const char *URL_DAILY_FILE =
    "https://paperstreetbtc.com/assets/data/btc-daily.json";
// paperstreetbtc.com daily closes: {"v":..,"source":..,"end":"2026-11-19",
// "d":[["2010-08-18",0.07], ... ]} — ~5,900 entries, ~135 KB.
// Block-clock data (mempool.space) — see fetchClockData().
const char *URL_MEMPOOL_BLOCKS =
    "https://mempool.space/api/blocks";
const char *URL_MEMPOOL_DIFF =
    "https://mempool.space/api/v1/difficulty-adjustment";
const char *URL_MEMPOOL_FEES =
    "https://mempool.space/api/v1/fees/recommended";
const char *URL_MEMPOOL_MEMPOOL =
    "https://mempool.space/api/mempool";
// Comparison overlays — the site's own daily closes, same shape as
// the BTC file above ({"d":[["YYYY-MM-DD",close],...]}).
const char *URL_CMP_FILE[3] = {
  "https://paperstreetbtc.com/assets/data/spx-daily.json",
  "https://paperstreetbtc.com/assets/data/gold-daily.json",
  "https://paperstreetbtc.com/assets/data/mstr-daily.json",
};
const char *CMP_NAME[3] = { "S&P", "GOLD", "MSTR" };
// QR receive addresses — the same hardcoded watch-only strings the
// prototype shows. The keychain holds no keys; these are receive-only.
const char *QR_JADE_ADDR = "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh";
const char *QR_LN_ADDR   = "paperstreet@walletofsatoshi.com";

// ------------------------------------------------------------------
// 3. Board pins (LilyGo T-Display-S3, verified against LilyGo's
//    pin map and the TFT_eSPI Setup206 for this board)
// ------------------------------------------------------------------
#define PIN_POWER  15   // must be HIGH or the display stays dark
#define PIN_BAT_ADC 4   // battery voltage ADC (reads only off USB)
#define TP_SDA 18       // CST816 touch I2C
#define TP_SCL 17
#define TP_INT 16       // touch interrupt (polled here, not used as IRQ)
#define TP_RST 21       // touch reset
#define TP_ADDR 0x15    // CST816 (early boards used a CST328 at 0x1A)

// ------------------------------------------------------------------
// 4. Timing
// ------------------------------------------------------------------
const unsigned long PRICE_POLL_MS   = 60000;   // 60 s, like the prototype
const unsigned long CHART_FRESH_MS  = 15 * 60000; // intraday chart refetch
const unsigned long DAILY_FRESH_MS  = 60 * 60000; // daily-file refetch
const unsigned long BLOCK_POLL_MS   = 10 * 60000; // block height refetch
const unsigned long TOUCH_POLL_MS   = 50;
const unsigned long WIFI_RETRY_MS   = 10000;

// ------------------------------------------------------------------
// 5. Colours — the PaperStreet keychain web prototype's palette,
//    exactly (dark screen bg #05080f, ink #e8eef7, cyan #22d3ee;
//    light bg #f6f8fb, ink #0f172a, cyan #0284c7). The 16-bit
//    values are the hex colours converted with TFT_eSPI's
//    color565(r, g, b) — the raw hex is NOT the right value.
//    C_AREA (the chart area fill) and C_DIMMED (disabled pill
//    text) are blended in applyTheme, so they track the theme.
// ------------------------------------------------------------------
uint16_t C_BG, C_SURFACE, C_TEXT, C_MUTED, C_DIM, C_CYAN, C_GREEN,
         C_RED, C_RED_CNDL, C_ORANGE, C_GRID, C_AREA, C_BTN, C_BTN_ON,
         C_BTN_TXT, C_PILL2, C_ONTXT, C_BORD, C_TILEBD, C_BARBG,
         C_PURP, C_AMBER, C_MSTR, C_DIMMED, C_PRICE, C_GLOW, C_SCRUB, C_RING,
         C_CYAN_DIM, C_GREEN_DIM, C_RED_DIM;
uint16_t CMP_COL[3];  // comparison line colours: SPX purple, GOLD amber, MSTR orange
bool themeDark = true;   // true = dark, false = light

void applyTheme() {
  if (themeDark) {
    C_BG       = 0x0041; // #05080f
    C_SURFACE  = 0x0884; // #0b1120
    C_TEXT     = 0xEF7E; // #e8eef7
    C_MUTED    = 0x9D37; // #9aa6bc
    C_DIM      = 0x530F; // #54637f
    C_CYAN     = 0x269D; // #22d3ee
    C_GREEN    = 0x262B; // #22c55e
    C_RED      = 0xEA28; // #ef4444
    C_RED_CNDL = 0xEA28; // #ef4444 (candles, dark)
    C_ORANGE   = 0xFB82; // #f97316
    C_GRID     = 0x10E6; // #141d31
    C_BTN      = 0x0884; // #0b1120 button bg
    C_BTN_ON   = 0x269D; // active button bg (cyan)
    C_BTN_TXT  = 0x9D37; // inactive pill text (#9aa6bc)
    C_PILL2    = 0x9538; // #93a5c4 secondary pill text (brightened
                         // from #67748e — the old grey-blue read
                         // low-contrast and fuzzy at 6-7 px)
    C_ONTXT    = 0x0126; // #052530 text on a cyan pill
    C_BORD     = 0x1948; // #1d2942 pill border
    C_TILEBD   = 0x1107; // #16203a stat-tile border
    C_BARBG    = 0x1927; // #1a2438 Auth progress-bar track
    C_PURP     = 0xA45F; // #a78bfa Auth avatar / SPX comparison
    C_AMBER    = 0xFDE4; // #fbbf24 Auth avatar / GOLD comparison
    C_MSTR     = 0xFC87; // #fb923c MSTR comparison line + chip dot
    // Chart area fill: the prototype's rgba(34,211,238,.13) over the
    // screen background (tft.alphaBlend(33, C_CYAN, C_BG)).
    C_AREA     = 0x0104;
    // Disabled range pills: the muted colour at 32% over the
    // background (the prototype's opacity .32).
    C_DIMMED   = 0x29C7;
    // The big price: the prototype's digits are pure white #fff
    // (not the #e8eef7 ink), with a cyan glow (text-shadow 0 0 18px
    // rgba(34,211,238,.25)). The TFT cannot blur, so the glow is a
    // 1 px halo of dim cyan behind the price (see drawPriceHalo).
    // NOTE: these are per-channel blends, NOT tft.alphaBlend — the
    // library's packed alphaBlend leaks borrows between the R/B
    // fields and tints a 70% white over near-black greenish.
    C_PRICE    = 0xFFFF; // #ffffff
    C_GLOW     = 0x09C8; // 25% #22d3ee over #05080f
    // Scrub line/dot: the prototype's is white at 0.7 opacity.
    C_SCRUB    = 0xAD96; // 70% white over #05080f
    // End-dot / scrub-dot ring: the prototype strokes it in the
    // screen background colour (dark) — same as C_BG here.
    C_RING     = 0x0041; // #05080f
    // Stale chart colours: the line/candles at 50% toward the
    // background while the selected range's fetch is in flight, so
    // the previous range's shape does not present at full brightness
    // as if it were current (see chartStale()).
    C_CYAN_DIM  = 0x134F; // 50% #22d3ee over #05080f
    C_GREEN_DIM = 0x1326; // 50% #22c55e over #05080f
    C_RED_DIM   = 0x7124; // 50% #ef4444 over #05080f
    CMP_COL[0] = C_PURP; CMP_COL[1] = C_AMBER; CMP_COL[2] = C_MSTR;
  } else {
    C_BG       = 0xF7DF; // #f6f8fb
    C_SURFACE  = 0xFFFF; // #ffffff
    C_TEXT     = 0x08A5; // #0f172a
    C_MUTED    = 0x42AD; // #475569
    C_DIM      = 0x63B1; // #64748b
    C_CYAN     = 0x0438; // #0284c7
    C_GREEN    = 0x1407; // #15803d
    C_RED      = 0xB8E3; // #b91c1c
    C_RED_CNDL = 0xD924; // #dc2626 (candles, light)
    C_ORANGE   = 0xC201; // #c2410c
    C_GRID     = 0xE75E; // #e2e8f0
    C_BTN      = 0xFFFF; // #ffffff button bg
    C_BTN_ON   = 0x0438; // active button bg (cyan)
    C_BTN_TXT  = 0x42AD; // inactive pill text (#475569)
    C_PILL2    = 0x63B1; // #64748b secondary pill text
    C_ONTXT    = 0xFFFF; // #ffffff text on a cyan pill
    C_BORD     = 0xDF1D; // #dbe3ec pill border
    C_TILEBD   = 0xDF1D; // #dbe3ec stat-tile border
    C_BARBG    = 0xE75E; // #e2e8f0 Auth progress-bar track
    C_PURP     = 0xA45F; // #a78bfa
    C_AMBER    = 0xFDE4; // #fbbf24
    C_MSTR     = 0xFC87; // #fb923c MSTR comparison line + chip dot
    C_AREA     = 0xD75E; // cyan 13% over #f6f8fb
    C_DIMMED   = 0xBE19; // muted 32% over #f6f8fb
    // Light mode: the prototype's price is #0f172a with NO glow
    // (text-shadow:none), the scrub line/dot are full #0f172a, and
    // the end-dot ring is pure white #ffffff (not the #f6f8fb bg).
    C_PRICE    = 0x08A5; // #0f172a
    C_GLOW     = 0xF7DF; // unused in light mode (no glow)
    C_SCRUB    = 0x08A5; // #0f172a
    C_RING     = 0xFFFF; // #ffffff
    // Stale chart colours (50% toward the background).
    C_CYAN_DIM  = 0x7DDB; // 50% #0284c7 over #f6f8fb
    C_GREEN_DIM = 0x85D2; // 50% #15803d over #f6f8fb
    C_RED_DIM   = 0xE471; // 50% #dc2626 over #f6f8fb
    CMP_COL[0] = C_PURP; CMP_COL[1] = C_AMBER; CMP_COL[2] = C_MSTR;
  }
}

// Backlight level, hardware part only (R8): 0..100% -> 8-bit PWM duty
// on GPIO 38 (TFT_BL) via ledc, 5 kHz. No-op in the sim — there is no
// backlight hardware there, and brightnessPct is only the stored
// value. Called after tft.init() (see setup) so it takes over from
// TFT_eSPI's own backlight handling.
void applyBrightnessRaw(int pct) {
  if (pct < 0) pct = 0;
  if (pct > 100) pct = 100;
#ifdef ARDUINO_ARCH_ESP32
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(TFT_BL, 5000, 8);
  ledcWrite(TFT_BL, pct * 255 / 100);
#else
  ledcSetup(0, 5000, 8);
  ledcAttachPin(TFT_BL, 0);
  ledcWrite(0, pct * 255 / 100);
#endif
#else
  (void)pct;
#endif
}

// ------------------------------------------------------------------
// 6. Layout — 170 x 320 portrait, content x 8..162 (154 px wide).
//    Phase 1 restack matches the Spaces prototype's row order:
//    status 15, header, big price, change, scrub, chart 154x58,
//    axis, type row, VS chips, range pills (2 rows), stat tiles,
//    page dots. Theme / Price / Auth shortcut pills are gone from
//    this page (swipe + dots are the navigation, as in the prototype).
//    Landscape is a full redraw at 320x170, not a scale-up.
// ------------------------------------------------------------------
#define SW 170
#define SH 320
#define CX0 8            // content left edge
#define CW 154           // content width
#define CX1 162          // content right edge (exclusive)
#define HDR_Y 18         // header (BITCOIN · LIVE PRICE + currency)
#define PRICE_Y 36       // big price, top
#define CHG_Y 67         // change row, top
#define SCRUB_Y 81       // scrub readout row
#define CH_X 35          // chart plot left (27 px gutter for Y labels)
#define CH_Y 96          // chart top
#define CH_W 127         // chart plot width (35..162)
#define CH_H 58          // chart height
#define AXIS_Y 156       // axis labels
#define TYPE_Y 168       // Line/Candles row
#define CMP_Y 186        // VS comparison chips
#define R1_Y 207         // range pills row 1
#define R2_Y 227         // range pills row 2
#define TILE_Y1 249      // stat tiles row 1 (below the ranges)
#define TILE_Y2 277      // stat tiles row 2
#define TILE_H 25
#define CTL_Y 284        // unused on the portrait chart (shortcuts dropped)
#define FOOT_Y 304       // unused on the portrait chart

// Landscape chart view (320 x 170) — setRotation(1). The device has
// no tilt sensor; rotation is a button tap, and it only ever applies
// to the chart view (price-only and Auth stay portrait). The chart
// gets the full 320 px width, so more of the series is visible.
#define LW 320
#define LH 170
#define L_CX0 10
#define L_CW 300
#define L_CX1 310
#define L_HDR_Y 15
#define L_PRICE_Y 32
#define L_SCRUB_Y 58
#define L_CH_X 37
#define L_CH_Y 71
#define L_CH_W 273
#define L_CH_H 66
#define L_AXIS_Y 138
#define L_CTL_Y 150

// Smooth fonts — .vlw files in data/ (LittleFS), generated from
// Outfit (ExtraBold/Bold), Inter (Bold/ExtraBold) and IBM Plex Mono
// (SemiBold/Bold), all OFL-licensed. The name is the file name
// without ".vlw"; the second argument is the built-in font used
// when the .vlw file is missing. See useFont() / setF() below.
#define F_PRICE    "OutfitXB29"   // big price, portrait
#define F_PRICE_PO "OutfitXB30"   // big price, price-only
#define F_PRICE_L  "OutfitXB22"   // big price, landscape
#define F_STAT15   "OutfitB15"    // price-only stat values
#define F_STAT11   "OutfitB11"    // stat tile values
#define F_LABEL9   "OutfitB9"     // Auth issuer / avatar letter
#define F_PILL8    "InterXB8"     // pill labels (8px extra-bold) — heavier/larger
#define F_PILL7    "InterB7"      // pill labels (7px)
#define F_PILL6    "InterB6"      // tiny pill labels (6px)
#define F_MONO8B   "MonoB8"       // change % / status values (bold 8px)
#define F_MONO8    "MonoSB8"      // status bar / scrub / range pills
#define F_MONO7    "MonoSB7"      // axis / notes / per-label
#define F_MONO6    "MonoSB6"      // tile labels / hints
#define F_MONO9B   "MonoB9"       // price-only change (bold 9px)
#define F_CODE13   "MonoB13"      // Auth code in the item card
#define F_CODE19   "MonoB19"      // Auth enlarged code

// ------------------------------------------------------------------
// 7. State
// ------------------------------------------------------------------
TFT_eSPI tft;
Preferences prefs;

float priceUSD  = 0;      // last good spot price, USD
float chg24h    = 0;      // CoinGecko 24h % change (USD)
float fxCAD     = 1.37;   // CAD per 1 USD (live from CoinGecko)
bool  curCAD    = false;  // false = USD (default), true = CAD
bool  priceOk   = false;
bool  wifiOk    = false;
bool  timeOk    = false;  // NTP synced
unsigned long lastPriceMs    = 0;  // last poll attempt
unsigned long lastPriceOkMs  = 0;  // last successful price
unsigned long lastPriceSaveMs = 0; // last NVS save of the price
unsigned long lastWifiTryMs  = 0;
unsigned long lastTouchMs    = 0;
unsigned long lastTapMs      = 0;
int   rangeIdx  = 0;      // 0 = 1D
int   chartType = 0;      // 0 = line, 1 = candles
bool  priceOnly = false;
// Hit box of the LIVE/OFFLINE label, set by drawStatusBar so a tap
// can force a refresh after the label moved to the right (Phase 1).
int16_t liveHitX = 0, liveHitW = 0;

// Block height (mempool.space, polled every 10 min while online).
// 0 = unknown — the stat tiles show "--" until the first fetch.
long blockHeight = 0;
unsigned long lastBlockMs = 0;
time_t lastPriceTime = 0;  // when the shown price was fetched (for "Updated H:MM")

// Drag-scrub: finger down in the chart area and moved. scrubIdx is
// the series index under the finger, or -1 when not scrubbing.
// scrubCand is the candle index in candle mode (-1 in line mode):
// the dot snaps to the candle centre instead of landing between
// buckets.
int scrubIdx = -1;
int scrubCand = -1;
bool scrubbing = false;

// --- Sleep / wake (R6) ---
// screenAsleep: the veil is showing, the backlight is at 6%, no
// fetches run, and the loop only polls touch. Set by a long-press
// (see handleTouch); cleared by any later touch (see wakeUp).
// sleepIgnoreLift: the finger that put the device to sleep is still
// down — it must not wake the device the moment it is noticed.
// wakeSwallow: the finger that woke the device must not also fire
// as a tap / swipe when it lifts.
bool screenAsleep = false;
bool sleepIgnoreLift = false;
bool wakeSwallow = false;
unsigned long downAtMs = 0;   // when the current finger went down
// longPressArmed: the finger has been held still (>= 1200 ms, < 8 px,
// not in the chart, not on a pill) on empty background. Sleep fires
// on the lift (see handleTouch) — a drag after the hold clears it,
// so a slow swipe can never be hijacked into sleep (Pass 5 finding 5).
bool longPressArmed = false;

// --- Brightness (R8) ---
// Backlight level, 45..100% (the prototype's slider range), persisted
// in NVS. While asleep the backlight is forced to 6% (not stored).
int brightnessPct = 100;

// --- Fetch state (R9) ---
// fetching: a network fetch is in flight right now — the loop is
// blocked in it, so taps cannot be seen until it returns. The scrub
// row says "Fetching…" while it is set (see drawFetchingNote).
// cmpPending: bitmask of comparison assets still to (re)fetch — one
// asset per loop pass, so a chip toggle never blocks on three daily
// files at once (see fetchOneCmpAsset).
bool fetching = false;
unsigned long fetchStartMs = 0;
int cmpPending = 0;

// --- Manual refresh (R7) ---
// Set when the LIVE indicator is tapped; the next loop pass runs the
// price poll immediately instead of waiting for the 60 s timer.
bool manualRefresh = false;

// --- Auth (TOTP) mode ---
// Which screen is showing: the price/chart screen or the Auth
// (TOTP authenticator) screen. See the Auth section after hitTest().
const int MODE_PRICE = 0;
const int MODE_AUTH  = 1;
const int MODE_CLOCK = 2;   // block clock app (R1)
const int MODE_QR    = 3;   // QR receive app (R2)
int appMode = MODE_PRICE;

// --- Block clock (R1) ---
// Last block timestamp (epoch seconds, mempool.space /api/blocks),
// difficulty progress %, fastest fee (sat/vB), mempool size (MB).
// -1 / 0 = unknown until the first fetch.
long  lastBlockTs = 0;
float diffProgress = -1;
float feeFastest = -1;
long  mempoolMB = -1;
unsigned long lastClockFetchMs = 0;
int  clockFocus = 0;              // 0 = block, 1 = sats, 2 = halving
unsigned long lastClockRotateMs = 0;
unsigned long lastClockDynMs = 0;   // per-second dynamic text redraw
unsigned long lastClockRingMs = 0;  // ring redraw (every 30 s)

// --- QR receive (R2) ---
int  qrPage = 0;        // 0 = Jade (on-chain), 1 = Lightning
bool qrFlipped = false; // true = full-address text instead of the QR

// --- Comparison overlays (R3) ---
// One aligned series per asset: cClose[c][i] is that asset's close
// stepped to the BTC point i (forward-filled daily closes), so the
// three lines share the BTC x positions. Rebased to 100 at i=0.
// (cClose lives with the chart series below — it needs MAXP.)
bool  cmpOn[3] = {false, false, false};
bool  cmpOk[3] = {false, false, false};
int   cmpRange = -1;              // range the cached series belongs to
unsigned long cmpFetchedMs = 0;   // last (re)fetch of any asset

// --- Authenticator list (R5) ---
bool authHideCodes = false;      // session-only privacy toggle

// Landscape chart view (see section 10). true while the chart is
// shown rotated. It is a sub-state of MODE_PRICE only — the Auth
// screen and price-only mode are always portrait. It is NOT saved
// to NVS: the device always boots in portrait. setRotation(1)
// reads upright when the device is turned clockwise (ST7789 MADCTL
// = MX|MV — see the note in touchRead()).
bool landscape = false;
int curRot = 0;  // rotation actually programmed into the display

// --- Swipe navigation (R4) ---
// Six pages on a horizontal track, in the prototype's order:
//   0 chart -> 1 price-only -> 2 block clock -> 3 Jade QR
//   -> 4 Lightning QR -> 5 Authenticator -> wraps to 0.
// QR DECISION: split into two swipe pages, not one. The prototype
// has two separate QR pages (Jade, Lightning) and the spatial model
// ("two swipes left from the chart is the Jade QR") only works if
// they are two places on the track. The Jade|Lightning seg pill
// stays as a shortcut between them. The firmware's qrPage state
// already distinguishes the two, so a swipe page IS a qrPage.
// Forward declarations: the helpers these functions call live in
// later sections (fillPillSolid: section 10, drawAll: section 10,
// fetchClockData: block clock, authRefresh: Auth, savePrefs: prefs).
void fillPillSolid(int16_t x, int16_t y, int16_t w, int16_t h, int16_t r,
                   uint16_t fill, uint16_t behind);
void drawAll();
bool fetchClockData();
bool authRefresh();
void savePrefs();
bool touchRead(int16_t &x, int16_t &y);  // defined in the touch section below; goToPage (slide abort) needs it first
const int PAGE_CHART = 0, PAGE_PRICE = 1, PAGE_CLOCK = 2;
const int PAGE_QR_JADE = 3, PAGE_QR_LN = 4, PAGE_AUTH = 5;
const int NPAGES = 6;
#define DOTS_CY 317   // page-dot centre row (bottom strip, y 315-319)

// Which track page the current state is.
int curPage() {
  if (appMode == MODE_CLOCK) return PAGE_CLOCK;
  if (appMode == MODE_QR) return qrPage == 0 ? PAGE_QR_JADE : PAGE_QR_LN;
  if (appMode == MODE_AUTH) return PAGE_AUTH;
  return priceOnly ? PAGE_PRICE : PAGE_CHART;
}

// Enter page p without drawing. The side effects mirror the nav
// pills exactly: entering the clock restarts its 12 s auto-rotate
// (the mempool feeds refresh on the loop's 5-min slot, never
// synchronously on entry — Pass 5 finding 3); entering a QR page shows
// the QR (not the flipped address); entering Auth refreshes the
// codes. priceOnly is persisted, as the Price pill does.
void setPageState(int p) {
  bool wasPriceOnly = priceOnly;
  switch (p) {
    case PAGE_CHART: appMode = MODE_PRICE; priceOnly = false; break;
    case PAGE_PRICE: appMode = MODE_PRICE; priceOnly = true; break;
    case PAGE_CLOCK:
      appMode = MODE_CLOCK;
      lastClockRotateMs = millis();
      // NO synchronous fetch here (Pass 5 finding 3): fetchClockData
      // is four sequential HTTPS calls at 5 s timeout each, so the
      // old entry fetch could freeze the UI for ~20 s offline before
      // the clock even drew — and on every re-entry while all four
      // failed, because lastClockFetchMs only moved on success. The
      // loop's 5-min clock slot fetches on the next pass instead (it
      // fires at once when lastClockFetchMs == 0), and the page draws
      // last-good data meanwhile.
      break;
    case PAGE_QR_JADE: appMode = MODE_QR; qrPage = 0; qrFlipped = false; break;
    case PAGE_QR_LN:  appMode = MODE_QR; qrPage = 1; qrFlipped = false; break;
    default: appMode = MODE_AUTH; authRefresh(); break;
  }
  if ((p == PAGE_CHART || p == PAGE_PRICE) && priceOnly != wasPriceOnly)
    savePrefs();
}

// Slide animation. Both pages are captured once into PSRAM
// buffers (2 x 170x320x2 = ~218 KB; PSRAM is 8 MB) and each
// frame composites them as a moving track — the outgoing page
// and the incoming page slide together, like the prototype's
// `translateX` on `.track`. 0.34 s, cubic-bezier(.32,.72,.28,1),
// time-driven: a slow frame stretches the slide instead of
// dropping the landing. Pages are not redrawn every frame.
// If either buffer cannot be allocated, or the screen is
// landscape, the page change is instant instead.
uint16_t *slideBuf = nullptr;    // outgoing page
uint16_t *slideBufIn = nullptr;  // incoming page

static uint16_t *slideAllocOne() {
#ifdef ARDUINO_ARCH_ESP32
  uint16_t *p = (uint16_t *)heap_caps_malloc(
      (size_t)SW * SH * sizeof(uint16_t), MALLOC_CAP_SPIRAM);
  if (!p) p = (uint16_t *)malloc((size_t)SW * SH * sizeof(uint16_t));
  return p;
#else
  return (uint16_t *)malloc((size_t)SW * SH * sizeof(uint16_t));
#endif
}

bool slideBufAlloc() {
  if (slideBuf && slideBufIn) return true;
  if (!slideBuf) slideBuf = slideAllocOne();
  if (!slideBufIn) slideBufIn = slideAllocOne();
  return slideBuf && slideBufIn;
}

// Prototype track easing: cubic-bezier(.32, .72, .28, 1).
// x(t) is solved with a few Newton steps, then y(t) is the
// progress. Close to the CSS curve, not a rewrite of it.
static float slideBezierX(float t) {
  float u = 1.0f - t;
  return 3.0f * u * u * t * 0.32f + 3.0f * u * t * t * 0.28f + t * t * t;
}
static float slideBezierY(float t) {
  float u = 1.0f - t;
  return 3.0f * u * u * t * 0.72f + 3.0f * u * t * t * 1.00f + t * t * t;
}
static float slideEase(float e) {
  if (e <= 0) return 0;
  if (e >= 1) return 1;
  float t = e;
  for (int i = 0; i < 8; i++) {
    float u = 1.0f - t;
    float x = slideBezierX(t);
    // d/dt of the cubic X
    float dx = 3.0f * u * u * 0.32f + 6.0f * u * t * (0.28f - 0.32f) + 3.0f * t * t * (1.0f - 0.28f);
    if (dx < 1e-6f && dx > -1e-6f) break;
    t -= (x - e) / dx;
    if (t < 0) t = 0;
    if (t > 1) t = 1;
  }
  return slideBezierY(t);
}

// One slide frame: both captured pages move as a track.
// dir +1: swipe left (next page) — outgoing exits left,
// incoming enters from the right. dir -1: the other way.
// dx is how far the track has travelled, 0..SW.
void slideFrame(int16_t dx, int dir) {
  if (!slideBuf || !slideBufIn) return;
  if (dx < 0) dx = 0;
  if (dx > SW) dx = SW;
  int16_t outW = SW - dx;
  int16_t inW = dx;
  if (dir > 0) {
    for (int16_t y = 0; y < SH; y++) {
      if (outW > 0)
        tft.pushImage(0, y, outW, 1, slideBuf + (size_t)y * SW + dx);
      if (inW > 0)
        tft.pushImage(outW, y, inW, 1, slideBufIn + (size_t)y * SW);
    }
  } else {
    for (int16_t y = 0; y < SH; y++) {
      if (inW > 0)
        tft.pushImage(0, y, inW, 1, slideBufIn + (size_t)y * SW + outW);
      if (outW > 0)
        tft.pushImage(inW, y, outW, 1, slideBuf + (size_t)y * SW);
    }
  }
}

// Go to track page p, sliding in the shortest direction around the
// track (wrap-aware: Auth -> chart slides forward, chart -> Auth
// slides back). A call for the page already showing just redraws.
void goToPage(int p) {
  if (p < 0 || p >= NPAGES) return;
  int from = curPage();
  if (p == from) { drawAll(); return; }
  int fwd = (p - from + NPAGES) % NPAGES;
  int dir = (fwd <= NPAGES / 2) ? 1 : -1;
  bool canSlide = !landscape && slideBufAlloc();
  if (canSlide) tft.readRect(0, 0, SW, SH, slideBuf);
  setPageState(p);
  if (!canSlide) { drawAll(); return; }
  drawAll();
  tft.readRect(0, 0, SW, SH, slideBufIn);
  // The screen now shows the incoming page; paint frame 0 (full
  // outgoing) before the clock starts so the incoming page does
  // not flash, then run the 0.34 s track slide.
  slideFrame(0, dir);
  unsigned long t0 = millis();
  while (true) {
    unsigned long el = millis() - t0;
    if (el >= 340) break;
    // A tap that starts mid-slide aborts the slide (Pass 5 finding 4):
    // the slide used to swallow every tap for its whole 340 ms. The
    // tap itself is handled by the next loop pass's handleTouch — the
    // finger is still down (or freshly down) when this returns.
    int16_t tx, ty;
    if (touchRead(tx, ty)) break;
    float f = slideEase((float)el / 340.0f);
    slideFrame((int16_t)(f * SW + 0.5f), dir);
    delay(17);
  }
  drawAll();  // land clean: no strip left over
}

// Six page dots, bottom strip (y 315-319), on every portrait page.
// The active dot widens to a 10 px capsule and turns cyan. The
// strip was reclaimed by slimming the chart control row (16 -> 14
// px) and moving the VS chip row up (y 303 -> 300, h 14 -> 13);
// every other page already had the strip free below its nav row /
// hint. Landscape shows no dots: it is a rotated chart view, not a
// track page, and its control row already runs to y 166 of 170.
void drawPageDots() {
  if (landscape) return;
  int cur = curPage();
  for (int i = 0; i < NPAGES; i++) {
    int16_t cx = 58 + i * 11;  // 58..113, centred on 85
    if (i == cur) fillPillSolid(cx - 5, DOTS_CY - 2, 10, 4, 2, C_CYAN, C_BG);
    else tft.fillCircle(cx, DOTS_CY, 2, C_DIM);
  }
}

// ==================================================================
// Sleep / wake (R6) — BEST EFFORT, HARDWARE-UNVERIFIED.
// ------------------------------------------------------------------
// What this build does:
//   * Long-press (hold 1200 ms, barely moved, then lift) on empty
//     background puts the device to sleep from any page. Sleep fires
//     on the LIFT, not while the finger is down (Pass 5 finding 5):
//     a user who pauses ~800 ms before swiping used to be put to
//     sleep mid-gesture; now a drag after the hold cancels the sleep
//     and the swipe goes through, while a deliberate hold-and-lift
//     still sleeps. The veil says SCREEN ASLEEP /
//     TAP TO WAKE, the backlight drops to 6% (the prototype dims to
//     ~6% — the veil stays readable), all fetches stop, and the loop
//     only polls touch.
//   * Wake is any fresh touch. The waking touch is swallowed — it
//     wakes and does nothing else.
//   * On the ESP32 the CPU light-sleeps in 50 ms slices between
//     touch polls (esp_light_sleep_start with a timer wakeup, in
//     loop()). That is the wake path: light sleep + touch polling.
// What is NOT done, and why:
//   * Deep sleep with a GPIO wake on the CST816 interrupt pin
//     (GPIO 16) is unverified on this board — whether GPIO 16 can
//     wake the ESP32-S3 from deep sleep, and whether the CST816 INT
//     line is even routed to wake it, has not been proven on
//     hardware. Deep sleep would also drop Wi-Fi and RAM state, so
//     waking would mean a full re-association before the next price
//     poll. Light sleep keeps Wi-Fi and RAM; the saving is the
//     backlight + display + no fetches, which is most of the draw on
//     this board. Prove the GPIO-16 deep-sleep path on the board
//     before switching to it. HARDWARE-UNVERIFIED.
//   * ST7789 sleep (SLPIN) is deliberately NOT used: it blanks the
//     display, so the wake veil could not be seen while asleep. The
//     prototype's sleep is a dim-to-6% veil, not a blank screen, and
//     this build matches the prototype. If true backlight-off is
//     wanted later, the veil goes with it — that is a product call,
//     not a bug.
//   * Wi-Fi stays connected while asleep (light sleep). A wake after
//     a long sleep may still need a re-association before the next
//     poll succeeds; the last-good price stays on screen meanwhile.
//   * The veil text is ASCII only on purpose: the smooth fonts carry
//     ASCII printable (plus '·' in Mono) — the prototype's '₿' glyph
//     (U+20BF) is not in any .vlw charset and would render blank.
// ==================================================================

// Backlight level with the sleep override: 6% while asleep.
void applyBrightness() {
  applyBrightnessRaw(screenAsleep ? 6 : brightnessPct);
}

// The wake veil: a crescent moon, SCREEN ASLEEP / TAP TO WAKE,
// centred for the current rotation. Drawn with the normal drawing
// calls, so it renders in the sim too.
void drawSleepVeil() {
  int16_t W = tft.width(), H = tft.height();
  tft.fillScreen(C_BG);
  // Crescent moon: a filled circle with a background-coloured circle
  // cut out of it, upper-centre.
  int16_t cx = W / 2, cy = H / 2 - 56;
  tft.fillCircle(cx, cy, 16, C_MUTED);
  tft.fillCircle(cx + 7, cy - 4, 14, C_BG);
  setF(F_LABEL9, 2);
  tft.setTextColor(C_TEXT, C_BG);
  const char *l1 = "SCREEN ASLEEP";
  int16_t w = tft.textWidth(l1);
  tft.setCursor((W - w) / 2, H / 2 - 22);
  tft.print(l1);
  setF(F_MONO8, 2);
  tft.setTextColor(C_MUTED, C_BG);
  const char *l2 = "TAP TO WAKE";
  w = tft.textWidth(l2);
  tft.setCursor((W - w) / 2, H / 2 + 2);
  tft.print(l2);
  // A thin cyan rule under the text, like the price-only rule.
  tft.fillRect(W / 2 - 18, H / 2 + 20, 36, 2, C_CYAN);
}

void enterSleep() {
  if (screenAsleep) return;
  screenAsleep = true;
  scrubbing = false; scrubIdx = -1; scrubCand = -1;
  drawSleepVeil();
  applyBrightnessRaw(6);
  Serial.println("sleep: screen asleep (light sleep, touch poll)");
}

void wakeUp() {
  if (!screenAsleep) return;
  screenAsleep = false;
  applyBrightness();
  drawAll();
  Serial.println("wake: screen awake");
}


// Up to 4 TOTP accounts, stored in NVS (see savePrefs/loadPrefs).
// The demo account is the public RFC 6238 test secret, NOT a real
// account; delete it over Serial once a real account is added.
const int MAXAUTH = 4;
const int AUTH_LABEL_LEN = 21;   // 20 chars + NUL
const int AUTH_SEC_LEN = 65;     // 64 chars + NUL
const char *AUTH_DEMO_LABEL = "Demo";
const char *AUTH_DEMO_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ";
struct AuthAcct { char label[AUTH_LABEL_LEN]; char secret[AUTH_SEC_LEN]; };
AuthAcct authAccts[MAXAUTH];
int  nAuth = 0;
int  authIdx = 0;
bool authSeeded = false;         // true once the demo account was seeded
uint32_t authWindow = 0;         // TOTP 30 s window the shown code is for
char authCode[8] = "";           // current 6-digit code + NUL
char authCodes[MAXAUTH][8];      // per-account codes for the window (R5 list)
unsigned long lastAuthSecMs = 0; // last once-a-second Auth refresh

// Chart series (thinned to <= MAXP points, oldest -> newest)
const int MAXP = 100;
float    sClose[MAXP];
float    sOpen[MAXP], sHigh[MAXP], sLow[MAXP];
uint32_t sTime[MAXP];          // epoch seconds (intraday ranges)
char     sDate[MAXP][11];      // "YYYY-MM-DD" (daily-file ranges)
bool     sHasOHLC = false;     // true when real O/H/L/C is stored
bool     sIsDaily = false;     // true when the series is daily closes
int      sN = 0;
float    cClose[3][MAXP];      // comparison closes, aligned to sClose[i]
unsigned long chartFetchedMs = 0;
int      chartRange = -1;      // which range the cached chart belongs to

// Candles built from the series for candle mode (max 52 buckets).
// si is the series index of the candle's close — the scrub logic
// snaps to it in candle mode, so the dot sits on a candle centre.
struct Candle { float o, h, l, c; uint32_t t; int si; };
Candle dispCand[52];
int    dispCandN = 0;

// ------------------------------------------------------------------
// 8. Ranges — mirrors the web prototype exactly
//    gran = Coinbase candle granularity in seconds (0 = daily file)
//    spanSec = window in seconds (0 = special: YTD / MAX)
//    candleTarget = candles to draw in candle mode (0 = line only)
// ------------------------------------------------------------------
struct RangeDef {
  const char *key;    // "1D"
  const char *span;   // label shown next to the % change
  int   gran;
  long  spanSec;
  int   candleTarget;
};
const RangeDef RANGES[] = {
  { "1D",  "24h", 900,    86400,     24 },
  { "1W",  "7d",  3600,   604800,    28 },
  { "1M",  "30d", 21600,  2592000,   30 },
  { "3M",  "3mo", 0,      7776000,   45 },
  { "6M",  "6mo", 0,      15552000,  52 },
  { "YTD", "YTD", 0,      0,         52 },
  { "1Y",  "1y",  0,      31536000,  52 },
  { "5Y",  "5y",  0,      157680000,  0 },
  { "MAX", "Max", 0,      0,         0 },
};
const int NRANGES = 9;
// 1D candles are 900 s (15 min) — the old "24 x 1h" was wrong (R11).
const char *CANDLE_LABEL[] = {
  "24 x 15m", "28 x 6h", "30 daily", "45 candles",
  "52 weekly", "52 weekly", "52 weekly", "", ""
};

// Halving: next halving at block 1,050,000; epochs are 210,000 blocks.
// (Prototype: blocks-to-go = 1,050,000 - height; % of epoch =
// (height % 210,000) / 210,000. The "~ APR 2028" date is the
// prototype's own estimate, kept as a static string.)
const long HALVING_BLOCK = 1050000;
const long HALVING_EPOCH = 210000;

// ==================================================================
// 9. Formatting helpers (no String class in the hot path — the
//    ESP32 heap fragments badly with repeated String use)
// ==================================================================

// "$60,603" — rounds to whole dollars, thousands separators.
// Every write is guarded: a caller with a small buffer gets a
// truncated number, never an overflow.
void fmtMoney(float usd, char *out, size_t n) {
  if (n == 0) return;
  float v = curCAD ? usd * fxCAD : usd;
  long whole = (long)(v + 0.5f);
  char tmp[20];
  snprintf(tmp, sizeof(tmp), "%ld", whole);
  int len = strlen(tmp), o = 0;
  if (o < (int)n - 1) out[o++] = '$';
  for (int i = 0; i < len; i++) {
    if (i > 0 && (len - i) % 3 == 0 && o < (int)n - 1) out[o++] = ',';
    if (o < (int)n - 1) out[o++] = tmp[i];
  }
  out[o] = 0;
}

// "+0.89%" / "-1.23%" for a % change value.
void fmtPct(float pct, char *out, size_t n) {
  snprintf(out, n, "%s%.2f%%", pct >= 0 ? "+" : "", pct);
}

// "1,650" sats per dollar at the display price.
long satsPerDollar() {
  float v = curCAD ? priceUSD * fxCAD : priceUSD;
  if (v <= 0) return 0;
  return (long)(100000000.0f / v + 0.5f);
}

// "13:42" local time (Eastern, via NTP) or "--:--" if not synced.
void fmtClock(char *out, size_t n) {
  struct tm t;
  if (!getLocalTime(&t, 0)) { snprintf(out, n, "--:--"); return; }
  strftime(out, n, "%H:%M", &t);
}

// "Nov 19" from a "YYYY-MM-DD" string.
void fmtMD(const char *ymd, char *out, size_t n) {
  static const char *MON[] = {"Jan","Feb","Mar","Apr","May","Jun",
                              "Jul","Aug","Sep","Oct","Nov","Dec"};
  int y, m, d;
  if (sscanf(ymd, "%d-%d-%d", &y, &m, &d) != 3 || m < 1 || m > 12) {
    snprintf(out, n, "%s", ymd); return;
  }
  snprintf(out, n, "%s %d", MON[m - 1], d);
}

// "14:30" from an epoch (UTC — the chart is drawn in UTC, same as
// the site's candles, so the labels never jump with time zones).
void fmtHM(uint32_t epoch, char *out, size_t n) {
  time_t t = (time_t)epoch;
  struct tm tmv;
  gmtime_r(&t, &tmv);
  strftime(out, n, "%H:%M", &tmv);
}

// "12a" / "6p" — the axis labels for intraday ranges (12-hour clock,
// no leading zero, no space, no minutes).
void fmt12h(uint32_t epoch, char *out, size_t n) {
  time_t t = (time_t)epoch;
  struct tm tmv;
  gmtime_r(&t, &tmv);
  int h = tmv.tm_hour % 12;
  if (h == 0) h = 12;
  snprintf(out, n, "%d%s", h, tmv.tm_hour < 12 ? "a" : "p");
}

// "Nov 20" from an epoch (UTC — the chart is drawn in UTC, same as
// the site's candles, so the labels never jump with time zones).
void fmtMDEpoch(uint32_t epoch, char *out, size_t n) {
  static const char *MON[] = {"Jan","Feb","Mar","Apr","May","Jun",
                              "Jul","Aug","Sep","Oct","Nov","Dec"};
  time_t t = (time_t)epoch;
  struct tm tmv;
  gmtime_r(&t, &tmv);
  snprintf(out, n, "%s %d", MON[tmv.tm_mon], tmv.tm_mday);
}

// "4:30p" — the scrub readout time (the prototype shows the minutes
// when scrubbing; the axis labels stay hour-only).
void fmtHM12(uint32_t epoch, char *out, size_t n) {
  time_t t = (time_t)epoch;
  struct tm tmv;
  gmtime_r(&t, &tmv);
  int h = tmv.tm_hour % 12;
  if (h == 0) h = 12;
  snprintf(out, n, "%d:%02d%s", h, tmv.tm_min, tmv.tm_hour < 12 ? "a" : "p");
}

// Do the X labels (and the scrub readout date) use dates instead of
// hours? Daily series always do; intraday series do once the window
// spans a week or more — the prototype labels 1W/1M/3M with dates,
// and the firmware's hour labels on 1W/1M repeat ("12p/12a") on the
// 6h candles. Decided from the data, not the range, so the daily
// fallback (Coinbase daily candles for 3M/6M/YTD/1Y, sIsDaily=false)
// still gets dates.
bool axisUseDates() {
  if (sIsDaily) return true;
  if (sN < 2 || sTime[0] == 0 || sTime[sN - 1] <= sTime[0]) return false;
  return (sTime[sN - 1] - sTime[0]) >= 7UL * 86400UL;
}

// "$62.6k" — the Y-axis labels on the chart (one decimal, k for
// thousands; whole dollars below $1,000).
void fmtK(float v, char *out, size_t n) {
  if (v >= 1000) snprintf(out, n, "$%.1fk", v / 1000.0f);
  else snprintf(out, n, "$%.0f", v);
}

// "5:15 PM" — when the shown price was fetched, 12-hour clock, or
// "--:--" when no price has been fetched yet.
void fmtUpdated(char *out, size_t n) {
  if (lastPriceTime <= 0) { snprintf(out, n, "--:--"); return; }
  struct tm t;
  localtime_r(&lastPriceTime, &t);
  char b[16];
  strftime(b, sizeof(b), "%I:%M %p", &t);
  const char *s = b;
  if (s[0] == '0') s++;  // "05:15 PM" -> "5:15 PM"
  snprintf(out, n, "%s", s);
}

// "2.38%" — a % change with no sign (the ▲/▼ triangle next to it
// shows the direction, as in the prototype).
void fmtPctAbs(float pct, char *out, size_t n) {
  snprintf(out, n, "%.2f%%", pct < 0 ? -pct : pct);
}

// "+2.3%" — signed (comparison chips have no triangle). One decimal
// below 10%, none at or above it — the VS row is at its width limit,
// and the decimal adds nothing at that size ("+17.5%" -> "+17%").
// A trailing ".0" is stripped ("+2.0%" -> "+2%", "+0.0%" -> "+0%").
// The sign was missing for negatives ("-44.5%" printed as "44.5%",
// a loss reading as a gain) — fixed here. (Finding 8.)
void fmtPct1(float pct, char *out, size_t n) {
  float a = pct < 0 ? -pct : pct;
  const char *sgn = pct < 0 ? "-" : "+";
  if (a >= 10.0f) {
    snprintf(out, n, "%s%.0f%%", sgn, a);
    return;
  }
  snprintf(out, n, "%s%.1f%%", sgn, a);
  size_t l = strlen(out);
  // Strip ".0", both characters: removing only the '0' left a
  // dangling '.' ("+0.%" — visible on the VS chips until this fix).
  if (l >= 4 && out[l - 2] == '0' && out[l - 1] == '%' && out[l - 3] == '.') {
    out[l - 3] = '%'; out[l - 2] = 0;
  }
}

// "4:32:08 PM" — 12-hour clock with seconds, Eastern, or "--:--"
// if not synced. Sunil chose 12-hour for the block-clock time.
void fmtClock12(char *out, size_t n) {
  struct tm t;
  if (!getLocalTime(&t, 0)) { snprintf(out, n, "--:--"); return; }
  char b[20];
  strftime(b, sizeof(b), "%I:%M:%S %p", &t);
  const char *s = b;
  if (s[0] == '0') s++;
  snprintf(out, n, "%s", s);
}

// "Tue, Nov 24, 2026 · Ottawa" — date line for the block clock.
void fmtDateLine(char *out, size_t n) {
  struct tm t;
  if (!getLocalTime(&t, 0)) { snprintf(out, n, "--"); return; }
  char b[32];
  strftime(b, sizeof(b), "%a, %b %d, %Y", &t);
  snprintf(out, n, "%s · Ottawa", b);
}

// "4 min 12 s" / "42 s" — time since the last block.
void fmtAgo(long secs, char *out, size_t n) {
  if (secs < 0) secs = 0;
  if (secs < 60) snprintf(out, n, "%ld s", secs);
  else snprintf(out, n, "%ld min %02ld s", secs / 60, secs % 60);
}

// Word-wrap helper: draw `s` in `vlw` at (x, y), wrapping on spaces
// to width `w`, `lh` px per line. Returns the y just past the last line.
int16_t drawWrapped(const char *s, int16_t x, int16_t y, int16_t w,
                    int16_t lh, const char *vlw, int fb, uint16_t col,
                    uint16_t bg) {
  char buf[160];
  snprintf(buf, sizeof(buf), "%s", s);
  setF(vlw, fb);
  tft.setTextColor(col, bg);
  int16_t cy = y;
  char *lineStart = buf;
  char *p = buf;
  // Walk word by word; `p` scans ahead to the next space.
  while (*lineStart) {
    // Find the longest prefix of the remaining text that fits.
    char *lastSpace = nullptr;
    char *q = lineStart;
    int16_t best = 0;
    while (1) {
      char *sp = strchr(q, ' ');
      int16_t len = sp ? (int16_t)(sp - lineStart) : (int16_t)strlen(lineStart);
      char save = lineStart[len];
      lineStart[len] = 0;
      int16_t tw = tft.textWidth(lineStart);
      lineStart[len] = save;
      if (tw > w) break;
      best = len;
      if (!sp) { q = nullptr; break; }
      lastSpace = sp;
      q = sp + 1;
    }
    int16_t take = best;
    if (take == 0) {
      // One word wider than the box (e.g. a 42-char address with no
      // spaces): break mid-word at the widest fitting prefix instead
      // of printing the whole word past the edge.
      int16_t wl = (int16_t)strlen(lineStart);
      take = 0;
      for (int16_t k = 1; k <= wl; k++) {
        char save2 = lineStart[k];
        lineStart[k] = 0;
        int16_t tw2 = tft.textWidth(lineStart);
        lineStart[k] = save2;
        if (tw2 > w) break;
        take = k;
      }
      if (take == 0) take = 1;
    }
    char save = lineStart[take];
    lineStart[take] = 0;
    tft.setCursor(x, cy);
    tft.print(lineStart);
    lineStart[take] = save;
    cy += lh;
    lineStart += take;
    while (*lineStart == ' ') lineStart++;
    (void)lastSpace; (void)p;
  }
  return cy;
}

// "977,242" — thousands separators for a long value.
void fmtComma(long v, char *out, size_t n) {
  char tmp[24];
  snprintf(tmp, sizeof(tmp), "%ld", v);
  int len = strlen(tmp), o = 0;
  for (int i = 0; i < len && o < (int)n - 1; i++) {
    if (i > 0 && (len - i) % 3 == 0) out[o++] = ',';
    out[o++] = tmp[i];
  }
  out[o] = 0;
}

// "123 456" — a TOTP code with a space in the middle, as the
// prototype shows it.
void fmtCodeSpaced(const char *code, char *out, size_t n) {
  if (!code || strlen(code) < 6) { snprintf(out, n, "--- ---"); return; }
  snprintf(out, n, "%.3s %.3s", code, code + 3);
}

// Battery: the T-Display-S3 reads the cell on GPIO 4 through a
// divider; ~3.0 V is empty, ~4.2 V is full. Only meaningful off
// USB power — on USB it reads low, so we show "USB" instead.
int batteryPct() {
  int mv = analogReadMilliVolts(PIN_BAT_ADC) * 2;  // divider x2
  if (mv < 3000) return -1;                        // on USB / no cell
  if (mv > 4200) mv = 4200;
  return (mv - 3000) * 100 / 1200;
}

// ==================================================================
// 10. Drawing
// ==================================================================

// Button rects — computed once per draw so hit-testing matches.
// (Declared up here because the pill helpers below register into it.)
struct Btn { int16_t x, y, w, h; int id; };
Btn btns[32];
int nBtns = 0;

// ------------------------------------------------------------------
// Smooth fonts — loaded from LittleFS (.vlw files in data/).
// useFont() caches the currently loaded font, so a redraw only
// re-loads when the font actually changes. If LittleFS or a file
// is missing, the matching built-in font is used instead, so the
// device still works (with the old blocky look) rather than going
// blank. Returns true when the smooth font is active.
// ------------------------------------------------------------------
bool fontsOk = false;
const char *curFontName = nullptr;
const char *failedFontName = nullptr;  // a .vlw that failed to load

bool useFont(const char *vlw, int fallback) {
  if (fontsOk && vlw && curFontName && strcmp(vlw, curFontName) == 0 &&
      tft.fontLoaded) return true;
  // A missing .vlw file used to be re-opened on every text draw
  // (a LittleFS open per draw, forever). Remember the failure and
  // go straight to the built-in font instead.
  if (fontsOk && vlw &&
      !(failedFontName && strcmp(vlw, failedFontName) == 0)) {
    tft.loadFont(vlw, LittleFS);
    if (tft.fontLoaded) { curFontName = vlw; return true; }
    failedFontName = vlw;  // vlw is a string literal — static storage
  }
  curFontName = nullptr;
  tft.setTextFont(fallback);
  return false;
}
// setF: pick the smooth font, or the built-in fallback id.
void setF(const char *vlw, int fallback) { useFont(vlw, fallback); }

// Smooth pills — the plain fillRoundRect/drawRoundRect pair leaves
// stair-stepped edges that read rough at 3x (Sunil: "the toggles
// look jagged"). TFT_eSPI's fillSmoothRoundRect anti-aliases the
// curve, but it blends each edge pixel against the `bg` colour
// passed in — so a bordered pill is drawn as two layered smooth
// fills: a border-coloured shell, then the fill inset by 1 px,
// each blended against the colour actually behind it. That keeps
// both the outer and the inner edge clean (a single outline call
// cannot blend both sides right). Needs TFT_eSPI >= 2.4.
void fillPill(int16_t x, int16_t y, int16_t w, int16_t h, int16_t r,
              uint16_t fill, uint16_t bord, uint16_t behind) {
  tft.fillSmoothRoundRect(x, y, w, h, r, bord, behind);
  int16_t r2 = r - 1; if (r2 < 0) r2 = 0;
  tft.fillSmoothRoundRect(x + 1, y + 1, w - 2, h - 2, r2, fill, bord);
}
// A solid pill (no border): one smooth fill.
void fillPillSolid(int16_t x, int16_t y, int16_t w, int16_t h, int16_t r,
                   uint16_t fill, uint16_t behind) {
  tft.fillSmoothRoundRect(x, y, w, h, r, fill, behind);
}

// A pill button: rounded rect, 1px border, centred label in a
// smooth font. `on` = active (cyan fill, dark text). Radius 5 for
// the range pills, h/2 for segmented/control pills (pass r).
void drawButton(int16_t x, int16_t y, int16_t w, int16_t h,
                const char *label, bool on, int16_t r,
                const char *vlw, int fb) {
  uint16_t bg = on ? C_BTN_ON : C_BTN;
  uint16_t fg = on ? C_ONTXT : C_BTN_TXT;
  if (on) fillPillSolid(x, y, w, h, r, C_BTN_ON, C_BG);
  else    fillPill(x, y, w, h, r, C_BTN, C_BORD, C_BG);
  setF(vlw, fb);
  tft.setTextColor(fg, bg);
  tft.setTextDatum(MC_DATUM);
  tft.drawString(label, x + w / 2, y + h / 2);
  tft.setTextDatum(TL_DATUM);
}

// Width of a segmented pill (two options + padding), for centring.
int16_t segPillWidth(const char *a, const char *b, const char *vlw) {
  setF(vlw, 2);
  return tft.textWidth(a) + 6 + 1 + tft.textWidth(b) + 6 + 2;
}

// Segmented pill (e.g. USD|CAD, Line|Cndl, Dark|Light): one bordered
// container with two options; the active option is a filled capsule.
// Registers the two hit zones in btns[] with ids idA/idB.
// Returns the total width, so the caller can place the next pill.
int16_t drawSegPill(int16_t x, int16_t y, int16_t h, const char *a,
                    const char *b, bool aOn, int idA, int idB,
                    const char *vlw) {
  setF(vlw, 2);
  int16_t wa = tft.textWidth(a) + 6, wb = tft.textWidth(b) + 6;
  int16_t w = wa + wb + 3;
  int16_t r = h / 2;
  // Layered smooth fills (see fillPill): the border shell, then the
  // container fill, then the active capsule — each blended against
  // the colour behind it, so the toggle's curves are clean at 3x.
  fillPill(x, y, w, h, r, C_BTN, C_BORD, C_BG);
  int16_t ax = aOn ? x + 1 : x + wa + 2;
  int16_t aw = aOn ? wa : wb;
  fillPillSolid(ax, y + 1, aw, h - 2, (h - 2) / 2, C_BTN_ON, C_BTN);
  tft.setTextDatum(MC_DATUM);
  tft.setTextColor(aOn ? C_ONTXT : C_PILL2, aOn ? C_BTN_ON : C_BTN);
  tft.drawString(a, x + 1 + wa / 2, y + h / 2);
  tft.setTextColor(!aOn ? C_ONTXT : C_PILL2, !aOn ? C_BTN_ON : C_BTN);
  tft.drawString(b, x + wa + 2 + wb / 2, y + h / 2);
  tft.setTextDatum(TL_DATUM);
  btns[nBtns++] = {(int16_t)(x + 1), (int16_t)(y + 1), wa, (int16_t)(h - 2), (int16_t)idA};
  btns[nBtns++] = {(int16_t)(x + wa + 2), (int16_t)(y + 1), wb, (int16_t)(h - 2), (int16_t)idB};
  return w;
}

// A single-option pill (Price, Auth, Portrait, Rotate): width from
// the label + 6 px padding each side. Returns the total width.
int16_t drawSinglePill(int16_t x, int16_t y, int16_t h,
                       const char *label, bool on, int id,
                       const char *vlw) {
  setF(vlw, 2);
  int16_t w = tft.textWidth(label) + 12;
  drawButton(x, y, w, h, label, on, h / 2, vlw, 2);
  btns[nBtns++] = {x, y, w, h, (int16_t)id};
  return w;
}

void drawStatusBar(int16_t barH, bool small) {
  // Width from the display, not the SW constant, so the bar spans
  // the full 320 px in landscape too.
  // Prototype arrangement: clock on the left, battery on the right.
  // LIVE/OFFLINE is kept as a firmware gain, on the right of the clock
  // cluster's counterpart — just left of the battery.
  tft.fillRect(0, 0, tft.width(), barH, C_BG);
  int16_t ty = small ? 1 : 3;   // text top (15 px bar / 13 px bar)
  char clk[8];
  fmtClock(clk, sizeof(clk));
  setF(small ? F_MONO7 : F_MONO8, 2);
  tft.setTextColor(C_MUTED, C_BG);
  tft.setCursor(8, ty);
  tft.print(clk);
  // right side: LIVE/OFFLINE + battery
  int bat = batteryPct();
  char batTxt[12];
  if (bat >= 0) snprintf(batTxt, sizeof(batTxt), "%d%%", bat);
  else          snprintf(batTxt, sizeof(batTxt), "USB");
  setF(small ? F_MONO7 : F_MONO8, 2);
  int16_t bw = tft.textWidth(batTxt);
  int16_t batX = tft.width() - bw - 8;
  tft.setTextColor(C_MUTED, C_BG);
  tft.setCursor(batX, ty);
  tft.print(batTxt);
  int16_t iconX = batX;
  if (bat >= 0) {
    iconX = batX - 19;
    tft.drawRect(iconX, barH / 2 - 3, 15, 7, C_DIM);
    tft.fillRect(iconX + 15, barH / 2 - 1, 2, 3, C_DIM);
    int16_t fw = 13 * bat / 100;
    if (fw > 0) tft.fillRect(iconX + 1, barH / 2 - 2, fw, 5, C_GREEN);
  }
  const char *live = priceOk ? "LIVE" : "OFFLINE";
  setF(small ? F_MONO7 : F_MONO8B, 2);
  int16_t lw = tft.textWidth(live);
  int16_t lx = iconX - 6 - lw;
  uint16_t dot = priceOk ? C_GREEN : C_RED;
  tft.fillCircle(lx - 6, barH / 2, 2, dot);
  tft.setTextColor(priceOk ? C_GREEN : C_RED, C_BG);
  tft.setCursor(lx, ty);
  tft.print(live);
  liveHitX = lx - 10;
  liveHitW = (int16_t)(lw + 14);
}

// Header: "BITCOIN · LIVE PRICE" + the block height on the left,
// the USD $|CAD $ segmented pill on the right — the prototype's
// p-head. The middot is drawn in Mono (it is not in the Inter vlw
// charset). Registers the pill zones (ids 16/17).
void drawHeader() {
  setF(F_PILL6, 1);
  tft.setTextColor(C_MUTED, C_BG);
  tft.setCursor(CX0, HDR_Y);
  tft.print("BITCOIN");
  int16_t x = CX0 + tft.textWidth("BITCOIN");
  // Middot is in the Mono vlw charset, not Inter.
  const char mid[] = " \xC2\xB7 ";
  setF(F_MONO6, 1);
  tft.setCursor(x, HDR_Y + 1);
  tft.print(mid);
  x += tft.textWidth(mid);
  setF(F_PILL6, 1);
  tft.setTextColor(C_MUTED, C_BG);
  tft.setCursor(x, HDR_Y);
  tft.print("LIVE PRICE");
  char blk[24];
  if (blockHeight > 0) {
    char hb[16];
    fmtComma(blockHeight, hb, sizeof(hb));
    snprintf(blk, sizeof(blk), "BLOCK %s", hb);
  } else {
    snprintf(blk, sizeof(blk), "BLOCK --");
  }
  setF(F_MONO7, 2);
  tft.setTextColor(C_PILL2, C_BG);
  tft.setCursor(CX0, HDR_Y + 10);
  tft.print(blk);
  int16_t pw = segPillWidth("USD $", "CAD $", F_PILL6);
  drawSegPill(CX1 - pw, HDR_Y, 14, "USD $", "CAD $", !curCAD, 16, 17, F_PILL6);
}

void drawPriceHalo(int16_t x, int16_t y, const char *buf) {
  if (!themeDark) return;
  tft.setTextColor(C_GLOW, C_BG);
  tft.setCursor(x - 1, y); tft.print(buf);
  tft.setCursor(x + 1, y); tft.print(buf);
  tft.setCursor(x, y - 1); tft.print(buf);
  tft.setCursor(x, y + 1); tft.print(buf);
}

// Big price: "$" in cyan, digits in pure white (the prototype's
// #fff, not the #e8eef7 ink), Outfit ExtraBold 29 px, with the glow
// halo behind it (see drawPriceHalo).
void drawPrice() {
  char buf[20];
  fmtMoney(priceUSD, buf, sizeof(buf));
  setF(F_PRICE, 6);
  drawPriceHalo(CX0, PRICE_Y, buf);
  tft.setTextColor(C_CYAN, C_BG);
  tft.setCursor(CX0, PRICE_Y);
  tft.print("$");
  int16_t dw = tft.textWidth("$");
  tft.setTextColor(C_PRICE, C_BG);
  tft.setCursor(CX0 + dw, PRICE_Y);
  tft.print(buf + 1);   // buf starts with '$'
  // Prototype: tapping the big price toggles USD/CAD (id 27).
  btns[nBtns++] = {CX0, PRICE_Y, (int16_t)tft.textWidth(buf), 30, 27};
}

float rangeChange() {
  if (sN < 2 || sClose[0] <= 0) return chg24h;
  return (sClose[sN - 1] / sClose[0] - 1.0f) * 100.0f;
}

// True while the screen shows a different range's data than the
// one selected — the draw right after a range tap (before the
// fetch lands), at boot before the first fetch, and after a failed
// fetch. The tiles / % / scrub row use it to say so instead of
// presenting stale numbers as current.
bool chartStale() { return chartRange != rangeIdx; }

void drawChangeRow() {
  float chg = rangeChange();
  char cb[16];
  fmtPctAbs(chg, cb, sizeof(cb));   // no sign — the triangle shows direction
  // Direction triangle (drawn as a shape — the fonts have no ▲/▼).
  // Dimmed while stale: the % belongs to the previous range until
  // the fetch lands.
  int16_t tx = CX0, ty = CHG_Y + 2;
  uint16_t col = chartStale() ? C_DIMMED : (chg >= 0 ? C_GREEN : C_RED);
  if (chg >= 0) tft.fillTriangle(tx, ty + 4, tx + 5, ty + 4, tx + 2, ty, col);
  else          tft.fillTriangle(tx, ty, tx + 5, ty, tx + 2, ty + 4, col);
  // % value (Mono bold 8px)
  setF(F_MONO8B, 4);
  tft.setTextColor(col, C_BG);
  tft.setCursor(tx + 8, CHG_Y);
  tft.print(cb);
  // "· 24h · Updated 5:15 PM" (Mono 7px, muted) — its x is measured
  // from the % text, so the two can never run into each other.
  int16_t x = tx + 8 + tft.textWidth(cb) + 4;
  char per[40];
  char upd[16];
  fmtUpdated(upd, sizeof(upd));
  snprintf(per, sizeof(per), "· %s · Updated %s", RANGES[rangeIdx].span, upd);
  setF(F_MONO7, 2);
  tft.setTextColor(C_MUTED, C_BG);
  tft.setCursor(x, CHG_Y + 1);
  tft.print(per);
}

// One stat tile: surface fill, 1px border, radius 7, small label
// on top and an Outfit 11px value below. dimValue greys the value
// (used for the HIGH/LOW tiles while the chart is stale — the
// number belongs to the previous range until the fetch lands).
// `vlw`/`fb` override the value font: the block-clock tiles need
// Mono for values with letters ("12 sat/vB", "16.5k / 165k") —
// OutfitB11's vlw charset is "$0123456789,." only, so letters
// would render blank there.
void drawStatTile(int16_t x, int16_t y, int16_t w, int16_t h,
                  const char *label, const char *value, bool dimValue = false,
                  const char *vlw = F_STAT11, int fb = 4) {
  fillPill(x, y, w, h, 7, C_SURFACE, C_TILEBD, C_BG);
  setF(F_MONO6, 1);
  tft.setTextColor(C_PILL2, C_SURFACE);
  tft.setCursor(x + 7, y + 4);
  tft.print(label);
  setF(vlw, fb);
  tft.setTextColor(dimValue ? C_DIMMED : C_TEXT, C_SURFACE);
  tft.setCursor(x + 7, y + 12);
  tft.print(value);
}

// Forward: the chart min/max (defined with the chart geometry
// below) are shown in the stat tiles, which are drawn first.
float chartMin();
float chartMax();

// Stat grid: SATS PER DOLLAR | BLOCK HEIGHT, then <SPAN> HIGH | LOW.
void drawStatGrid() {
  char sats[16], blk[16], hi[20], lo[20], labHi[16], labLo[16], spanUp[8];
  fmtComma(satsPerDollar(), sats, sizeof(sats));
  if (blockHeight > 0) fmtComma(blockHeight, blk, sizeof(blk));
  else snprintf(blk, sizeof(blk), "--");
  fmtMoney(chartMax(), hi, sizeof(hi));
  fmtMoney(chartMin(), lo, sizeof(lo));
  // span label upper-cased ("24h" -> "24H")
  int i = 0;
  for (const char *p = RANGES[rangeIdx].span; *p && i < 6; p++, i++)
    spanUp[i] = (*p >= 'a' && *p <= 'z') ? *p - 32 : *p;
  spanUp[i] = 0;
  snprintf(labHi, sizeof(labHi), "%s HIGH", spanUp);
  snprintf(labLo, sizeof(labLo), "%s LOW", spanUp);
  drawStatTile(CX0, TILE_Y1, 75, TILE_H, "SATS PER DOLLAR", sats);
  drawStatTile(86, TILE_Y1, 76, TILE_H, "BLOCK HEIGHT", blk);
  // HIGH/LOW belong to the cached chart — dim them while the
  // selected range's fetch is still in flight (see chartStale()).
  // SATS and BLOCK are live and stay bright.
  drawStatTile(CX0, TILE_Y2, 75, TILE_H, labHi, hi, chartStale());
  drawStatTile(86, TILE_Y2, 76, TILE_H, labLo, lo, chartStale());
}

// Scrub readout row (Mono 8px, cyan): "Drag chart to scrub" by
// default; while scrubbing, price + date on the left and the % vs
// the range start on the right (R11 — the prototype's reference, not
// vs the last close). Uses the current orientation's
// geometry, so the same code serves portrait and landscape.
void drawScrubRow() {
  int16_t x0 = landscape ? L_CX0 : CX0;
  int16_t y0 = landscape ? L_SCRUB_Y : SCRUB_Y;
  int16_t w0 = landscape ? L_CW : CW;
  tft.fillRect(x0, y0, w0, 13, C_BG);
  setF(F_MONO8, 2);
  if (scrubIdx < 0 || scrubIdx >= sN) {
    // Not scrubbing: the hint — or "Fetching…" while a fetch is in
    // flight (R9), or "Updating…" while the selected range's fetch
    // is still in flight (see chartStale()).
    if (fetching) {
      tft.setTextColor(C_MUTED, C_BG);
      tft.setCursor(x0, y0);
      // ASCII "..." — the U+2026 ellipsis glyph is not in the .vlw
      // fonts, so it rendered as nothing ("Fetching" with no dots).
      tft.print("Fetching...");
    } else if (chartStale()) {
      tft.setTextColor(C_MUTED, C_BG);
      tft.setCursor(x0, y0);
      tft.print("Updating...");
    } else {
      tft.setTextColor(C_CYAN, C_BG);
      tft.setCursor(x0, y0);
      tft.print("Drag chart to scrub");
    }
  } else {
    char left[48], dstr[24], right[16];
    if (sIsDaily) fmtMD(sDate[scrubIdx], dstr, sizeof(dstr));
    else if (axisUseDates()) {
      // "Nov 20 4:30p" — the prototype's 1W scrub readout (date +
      // time), instead of the bare hour the firmware used to show.
      char d[8];
      fmtMDEpoch(sTime[scrubIdx], d, sizeof(d));
      char h[8];
      fmtHM12(sTime[scrubIdx], h, sizeof(h));
      snprintf(dstr, sizeof(dstr), "%s %s", d, h);
    }
    else fmtHM12(sTime[scrubIdx], dstr, sizeof(dstr));
    char pr[20];
    fmtMoney(sClose[scrubIdx], pr, sizeof(pr));
    snprintf(left, sizeof(left), "%s · %s", pr, dstr);
    // % vs the RANGE START (R11): the scrubbed point's return over
    // the range, as in the prototype — not vs the last close.
    float base = sClose[0];
    float pc = base > 0 ? (sClose[scrubIdx] / base - 1.0f) * 100.0f : 0;
    fmtPct(pc, right, sizeof(right));
    tft.setTextColor(C_CYAN, C_BG);
    tft.setCursor(x0, y0);
    tft.print(left);
    setF(F_MONO8B, 4);
    tft.setTextColor(pc >= 0 ? C_GREEN : C_RED, C_BG);
    int16_t rw = tft.textWidth(right);
    tft.setCursor(x0 + w0 - rw, y0);
    tft.print(right);
  }
  // "Rotate" button, right-aligned in this row just above the
  // chart: it used to overlay the chart's top-right corner and
  // cover the live edge. Portrait only (landscape has Portrait in
  // its control row), and hidden while scrubbing — the scrub
  // readout uses the row's right side then. This row is redrawn on
  // scrub start, move and end, so the pill comes back on lift.
  // Drawn here (after the chart — drawAll runs the chart area
  // before this row) so the chart's top fill cannot erase it.
  if (!landscape && sN >= 2 && scrubIdx < 0) {
    setF(F_PILL8, 2);
    int16_t pw = tft.textWidth("Rotate") + 12;
    drawSinglePill(x0 + w0 - pw, y0, 13, "Rotate", false, 15, F_PILL8);
  }
  // Landscape theme control (R8): the landscape control row is full
  // (9 ranges + Line/Cndl + Portrait), so the theme toggle lives here
  // in the scrub row — the same row the portrait Rotate pill uses,
  // and the same row the portrait theme pill does NOT use. One pill
  // showing the theme a tap will switch TO (id 23 = Dark, id 24 =
  // Light, the same ids as the portrait Dark|Light seg pill).
  // LAYOUT DECISION: shrinking the 9 landscape range pills to make
  // room in the control row was rejected — "MAX" already fills its
  // 17 px pill at Mono 9px bold, and a second control row does not
  // fit in 170 px of height. The scrub row's right end is free in
  // landscape (the readout is left-aligned, the pill hides while
  // scrubbing), so the toggle goes there instead.
  if (landscape && scrubIdx < 0) {
    setF(F_PILL8, 2);
    const char *lbl = themeDark ? "Light" : "Dark";
    int16_t pw = tft.textWidth(lbl) + 12;
    drawSinglePill(x0 + w0 - pw, y0, 13, lbl, false, themeDark ? 24 : 23, F_PILL8);
  }
}

// "Fetching…" note (R9): painted immediately, BEFORE a blocking fetch
// starts, so the user sees why taps stall. Chart page: into the scrub
// row. Price-only: centred on the hint line (redrawn by the next
// drawAll). Other pages: nothing — their fetches are short and their
// next drawAll lands right after.
void drawFetchingNote() {
  if (appMode != MODE_PRICE) return;
  if (priceOnly) {
    setF(F_MONO6, 1);
    tft.setTextColor(C_MUTED, C_BG);
    const char *s = "Fetching...";  // ASCII "...", see drawScrubRow
    int16_t w = tft.textWidth(s);
    tft.setCursor((SW - w) / 2, 298);
    tft.print(s);
    return;
  }
  int16_t x0 = landscape ? L_CX0 : CX0;
  int16_t y0 = landscape ? L_SCRUB_Y : SCRUB_Y;
  int16_t w0 = landscape ? L_CW : CW;
  tft.fillRect(x0, y0, w0, 13, C_BG);
  setF(F_MONO8, 2);
  tft.setTextColor(C_MUTED, C_BG);
  tft.setCursor(x0, y0);
  tft.print("Fetching...");  // ASCII "...", see drawScrubRow
}

// FetchGuard (R9): marks a fetch in flight and paints the "Fetching…"
// note on entry; clears the flag on exit (every return goes through
// the destructor). One guard per fetch function — never nested, or the
// inner destructor would clear the flag while the outer fetch still
// runs. Defined here (after drawFetchingNote) so the block-clock
// fetch below can use it too.
struct FetchGuard {
  FetchGuard() { fetching = true; fetchStartMs = millis(); drawFetchingNote(); }
  ~FetchGuard() { fetching = false; }
};

// Chart geometry — the drawing functions below read these globals,
// not the CH_* constants, so the same chart code draws in portrait
// (170x320) and in landscape (320x170). drawChartArea() sets the
// portrait geometry, drawChartAreaL() sets the landscape geometry.
// They default to portrait, so the chart is correct even if a caller
// forgets to set them.
int16_t gCH_X = CH_X, gCH_W = CH_W, gCH_Y = CH_Y, gCH_H = CH_H,
        gAX_Y = AXIS_Y;
void setChartGeom(int16_t x, int16_t y, int16_t w, int16_t h,
                  int16_t ax) {
  gCH_X = x; gCH_Y = y; gCH_W = w; gCH_H = h; gAX_Y = ax;
}

// Comparison plot state, set by drawChartBody on every draw:
// gCmpActive = comparisons are actually plotted (line mode, chips
// on, aligned series cached for this range); gPlotLo/gPlotHi = the
// padded plot range in plot units; gRebLo/gRebHi = the unpadded
// rebased extremes (for the true high/low Y labels).
bool  gCmpActive = false;
float gPlotLo = 0, gPlotHi = 0, gRebLo = 0, gRebHi = 0;

// Plot-unit value: rebased to 100 at the range start while
// comparisons are active, otherwise the raw BTC $ value. The
// rebase is linear, so it commutes with the area-fill interpolation.
// NOTE: each series rebases against ITS OWN range-start value —
// BTC against sClose[0], a comparison against cClose[c][0].
// Dividing a comparison by the BTC start price would squash it to
// a flat line near zero (SPX ~7700 vs BTC ~62000).
float plotVal(float v) {
  if (gCmpActive && sClose[0] > 0) return v / sClose[0] * 100.0f;
  return v;
}
float plotValCmp(int c, float v) {
  if (gCmpActive && cClose[c][0] > 0) return v / cClose[c][0] * 100.0f;
  return v;
}

// Chart geometry helpers
float chartMin() {
  float m = sClose[0];
  if (chartType == 1 && dispCandN > 0) {
    m = dispCand[0].l;
    for (int i = 1; i < dispCandN; i++) if (dispCand[i].l < m) m = dispCand[i].l;
  } else {
    for (int i = 1; i < sN; i++) if (sClose[i] < m) m = sClose[i];
  }
  return m;
}
float chartMax() {
  float m = sClose[0];
  if (chartType == 1 && dispCandN > 0) {
    m = dispCand[0].h;
    for (int i = 1; i < dispCandN; i++) if (dispCand[i].h > m) m = dispCand[i].h;
  } else {
    for (int i = 1; i < sN; i++) if (sClose[i] > m) m = sClose[i];
  }
  return m;
}
int16_t chartX(int i, int n) {
  if (n <= 1) return gCH_X;
  return gCH_X + (int16_t)((long)i * (gCH_W - 1) / (n - 1));
}
int16_t chartY(float v, float lo, float hi) {
  if (hi <= lo) hi = lo + 1;
  float f = (v - lo) / (hi - lo);
  if (f < 0) f = 0; if (f > 1) f = 1;
  // The prototype insets the plot 4 px from the top and bottom of
  // the chart box (PAD=4 in its SVG), so the line never touches the
  // edges — without the inset the highest and lowest points draw on
  // the very edge of the box. (The area fill below still runs to
  // the bottom edge, as in the prototype.)
  return gCH_Y + gCH_H - 5 - (int16_t)(f * (gCH_H - 9));
}

void drawChartLine(float lo, float hi) {
  // area fill: one vertical line per PIXEL column, with the top
  // interpolated between the two nearest points. The old code drew
  // one line per data point, and with ~100 points over 127 px some
  // columns got no line at all — which read as a comb/barcode
  // texture under the line (worst in light mode). Per-column
  // interpolation makes the wash smooth, like the prototype's SVG
  // area path. The fill still runs to the bottom edge, as there.
  // (The fill is 13% cyan either way — too faint to need dimming
  // while stale; the line and candles carry the stale signal.)
  for (int16_t px = 0; px < gCH_W; px++) {
    float fi = (float)px * (sN - 1) / (gCH_W - 1);
    int i0 = (int)fi; if (i0 > sN - 2) i0 = sN - 2;
    float frac = fi - i0;
    float v = sClose[i0] + (sClose[i0 + 1] - sClose[i0]) * frac;
    int16_t x = gCH_X + px;
    int16_t y = chartY(plotVal(v), lo, hi);
    tft.drawFastVLine(x, y, gCH_Y + gCH_H - y, C_AREA);
  }
  // grid: 3 faint lines at 1/4, 1/2, 3/4 of the chart height
  for (int g = 1; g <= 3; g++) {
    int16_t gy = gCH_Y + gCH_H * g / 4;
    tft.drawFastHLine(gCH_X, gy, gCH_W, C_GRID);
  }
  // polyline: anti-aliased 1.6 px, cyan (the prototype's line is
  // always cyan — direction shows in the % text, not the line).
  // Dimmed while stale: the line is the previous range's data until
  // the fetch lands (see chartStale()).
  uint16_t lineCol = chartStale() ? C_CYAN_DIM : C_CYAN;
  for (int i = 1; i < sN; i++) {
    tft.drawWideLine(chartX(i - 1, sN), chartY(plotVal(sClose[i - 1]), lo, hi),
                     chartX(i, sN),     chartY(plotVal(sClose[i]), lo, hi),
                     1.6f, lineCol);
  }
  // last-point dot (the live spot): cyan fill, ring (see C_RING)
  int16_t lx = chartX(sN - 1, sN), ly = chartY(plotVal(sClose[sN - 1]), lo, hi);
  tft.fillCircle(lx, ly, 3, lineCol);
  tft.drawCircle(lx, ly, 3, C_RING);
}

// Comparison lines (R3): one coloured line + end dot per active
// asset, rebased to 100 at the range start like the BTC line.
// Dimmed to grey while the chart is stale (see chartStale()).
void drawCmpLines(float lo, float hi) {
  for (int c = 0; c < 3; c++) {
    if (!cmpOn[c] || !cmpOk[c]) continue;
    uint16_t col = chartStale() ? C_DIM : CMP_COL[c];
    for (int i = 1; i < sN; i++) {
      tft.drawWideLine(chartX(i - 1, sN), chartY(plotValCmp(c, cClose[c][i - 1]), lo, hi),
                       chartX(i, sN),     chartY(plotValCmp(c, cClose[c][i]), lo, hi),
                       1.1f, col);
    }
    int16_t lx = chartX(sN - 1, sN), ly = chartY(plotValCmp(c, cClose[c][sN - 1]), lo, hi);
    tft.fillCircle(lx, ly, 2, col);
    tft.drawCircle(lx, ly, 2, C_RING);
  }
}

// Build the display candles from the series (mirrors the prototype's
// buildCandles: bucket the points, open = first close in the bucket,
// close = last, high/low = bucket extremes; intraday ranges use the
// real Coinbase highs/lows where we stored them).
void buildCandles() {
  dispCandN = 0;
  int target = RANGES[rangeIdx].candleTarget;
  if (chartType != 1 || target == 0 || sN < 2) return;
  int n = target < sN ? target : sN;
  int bucket = (sN + n - 1) / n;  // ceil
  for (int b = 0; b < sN && dispCandN < 52; b += bucket) {
    int e = b + bucket; if (e > sN) e = sN;
    float o = sClose[b], c = sClose[e - 1];
    float h = o, l = o;
    for (int i = b; i < e; i++) {
      if (sClose[i] > h) h = sClose[i];
      if (sClose[i] < l) l = sClose[i];
    }
    if (sHasOHLC) {  // real intraday highs/lows from Coinbase
      o = sOpen[b]; c = sClose[e - 1];
      for (int i = b; i < e; i++) {
        if (sHigh[i] > h) h = sHigh[i];
        if (sLow[i]  < l) l = sLow[i];
      }
    }
    dispCand[dispCandN].o = o; dispCand[dispCandN].h = h;
    dispCand[dispCandN].l = l; dispCand[dispCandN].c = c;
    dispCand[dispCandN].t = sTime[b];
    dispCand[dispCandN].si = e - 1;  // series index of this close
    dispCandN++;
  }
}

void drawChartCandles(float lo, float hi) {
  // grid: 3 faint lines at 1/4, 1/2, 3/4 of the chart height
  for (int g = 1; g <= 3; g++) {
    int16_t gy = gCH_Y + gCH_H * g / 4;
    tft.drawFastHLine(gCH_X, gy, gCH_W, C_GRID);
  }
  if (dispCandN < 1) return;
  float slot = (float)gCH_W / dispCandN;
  float bwf = slot * 0.62f;
  if (bwf < 1.2f) bwf = 1.2f;
  if (bwf > 5) bwf = 5;
  int bw = (int)(bwf + 0.5f);
  if (bw < 1) bw = 1;
  // Dimmed while stale: the candles are the previous range's data
  // until the fetch lands (see chartStale()).
  uint16_t upCol = chartStale() ? C_GREEN_DIM : C_GREEN;
  uint16_t dnCol = chartStale() ? C_RED_DIM : C_RED_CNDL;
  for (int i = 0; i < dispCandN; i++) {
    int16_t xc = gCH_X + (int16_t)((long)i * gCH_W / dispCandN) + (int16_t)(slot / 2);
    float o = dispCand[i].o, h = dispCand[i].h,
          l = dispCand[i].l, c = dispCand[i].c;
    uint16_t col = (c >= o) ? upCol : dnCol;
    int16_t yH = chartY(h, lo, hi), yL = chartY(l, lo, hi);
    int16_t yO = chartY(o, lo, hi), yC = chartY(c, lo, hi);
    tft.drawFastVLine(xc, yH, yL - yH + 1, col);            // wick, 1 px
    int16_t top = yO < yC ? yO : yC, bot = yO < yC ? yC : yO;
    if (bot - top < 1) bot = top + 1;
    tft.fillRect(xc - bw / 2, top, bw, bot - top, col);      // body
  }
  // No end dot in candle mode: the prototype hides #endDot there,
  // and the last candle's close already marks the live spot — the
  // dot floated orphaned at the right edge. (The scrub dot is
  // separate and still shows while scrubbing.)
}

void drawYLabels(float lo, float hi) {
  setF(F_MONO6, 1);
  // Dimmed while stale: the labels belong to the previous range's
  // data until the fetch lands (see chartStale()).
  tft.setTextColor(chartStale() ? C_DIMMED : C_PILL2, C_BG);
  // Axis units: normally BTC $ (fmtK). With comparisons active the
  // plot is rebased (100 = the range-start BTC price), so the labels
  // read in rebased units — converting them back to BTC $ made the
  // axis claim BTC had hit a comparison's extreme ($134.7k on the
  // axis while the HIGH tile said $96,929). (Finding 4.)
  auto fmtAxis = [](float plotV, char *a, size_t n) {
    if (gCmpActive) {
      if (plotV >= 100.0f || plotV <= -100.0f) snprintf(a, n, "%.0f", plotV);
      else snprintf(a, n, "%.1f", plotV);
    } else {
      fmtK(plotV, a, n);
    }
  };
  // The true extremes first: the top gridline is skipped when the
  // max label crowds it (see below), so its position is needed
  // before the gridline loop runs.
  // Label the true high at its plotted height, mirroring the low
  // label below: the three quarter-gridline labels never name the
  // extremes, so without this the top label understates the HIGH
  // tile (1Y: $89.2k on the axis vs $96,929 in the tile).
  float mx = gCmpActive ? gRebHi : chartMax();
  int16_t xy = chartY(mx, lo, hi);
  float mn = gCmpActive ? gRebLo : chartMin();
  int16_t my = chartY(mn, lo, hi);
  char a[16];
  for (int g = 1; g <= 3; g++) {
    float v = hi - (hi - lo) * g / 4;
    int16_t gy = gCH_Y + gCH_H * g / 4;
    // Finding 9: the max label crowds the top gridline label
    // ($96.9k over $89.0k on 1Y, ~10 px apart) — skip the top
    // gridline when the max label sits within 12 px of it.
    if (g == 1 && xy - gy < 12 && gy - xy < 12) continue;
    // Pass 5 finding 10: mirror the top rule at the bottom — the
    // low label sits 2 px below the bottom gridline label on 1Y.
    // Skip the bottom gridline when the low label is within 8 px.
    if (g == 3 && my - gy < 8 && gy - my < 8) continue;
    fmtAxis(v, a, sizeof(a));
    int16_t w = tft.textWidth(a);
    tft.setCursor(gCH_X - 3 - w, gy - 3);
    tft.print(a);
  }
  fmtAxis(mx, a, sizeof(a));
  int16_t xw = tft.textWidth(a);
  tft.setCursor(gCH_X - 3 - xw, xy - 3);
  tft.print(a);
  // Label the true low at its plotted height. The padded axis puts
  // the low ~7% of the plot height above the bottom edge, and the
  // three quarter gridlines never name it — on 1W the $55k dip had
  // no tick at all (lowest was $57.3k). Positioned at
  // chartY(chartMin()) so the label sits exactly on the level it
  // names; it stays clear of the lowest gridline label (the min
  // sits ~6-7% up from the bottom, the gridline label ~25% up).
  fmtAxis(mn, a, sizeof(a));
  int16_t mw = tft.textWidth(a);
  tft.setCursor(gCH_X - 3 - mw, my - 3);
  tft.print(a);
}

void drawAxisLabels() {
  if (sN < 2) return;
  setF(F_MONO7, 2);
  tft.setTextColor(C_DIM, C_BG);
  // 5 labels across the plot: 0%, 25%, 50%, 75%, and "Now" at the
  // live edge. Intraday ranges show the hour ("12a"/"6p"), daily
  // ranges show the date ("Nov 19").
  for (int k = 0; k < 5; k++) {
    int idx = (k == 4) ? sN - 1 : (int)((long)k * (sN - 1) / 4);
    char a[16];
    if (k == 4) snprintf(a, sizeof(a), "Now");
    else if (sIsDaily) fmtMD(sDate[idx], a, sizeof(a));
    else if (axisUseDates()) fmtMDEpoch(sTime[idx], a, sizeof(a));
    else fmt12h(sTime[idx], a, sizeof(a));
    int16_t x = chartX(idx, sN);
    int16_t w = tft.textWidth(a);
    int16_t lx;
    // Every label is centred on its data point — including the
    // first: left-aligning it ran "Nov 23" into "Feb 19" on the
    // narrow portrait chart (27 px labels on 32 px spacing). The
    // axis row is empty left of the plot, so centring the first
    // label costs nothing. The last stays right-aligned so it
    // never runs past the screen edge.
    if (k == 4) lx = gCH_X + gCH_W - w;
    else lx = x - w / 2;
    tft.setCursor(lx, gAX_Y);
    tft.print(a);
  }
}

// Scrub overlay on the chart: a 1px vertical line through the
// scrub point and a dot with a background-colour ring. In candle
// mode the dot snaps to the candle centre, at its close (see
// scrubCand) — the series index alone would land it between
// buckets.
void drawScrubOverlay() {
  if (scrubIdx < 0 || scrubIdx >= sN) return;
  // The padded plot range, as computed by drawChartBody: in
  // rebased mode (comparisons on) the scrub dot plots the rebased
  // BTC value, not the raw $ value.
  float lo, hi;
  if (gCmpActive) { lo = gPlotLo; hi = gPlotHi; }
  else {
    lo = chartMin(); hi = chartMax();
    float pad = (hi - lo) * (chartType == 1 ? 0.07f : 0.08f);
    if (pad <= 0) pad = hi * 0.001f;
    lo -= pad; hi += pad;
  }
  int16_t x, y;
  if (scrubCand >= 0 && scrubCand < dispCandN) {
    float slot = (float)gCH_W / dispCandN;
    x = gCH_X + (int16_t)((long)scrubCand * gCH_W / dispCandN) + (int16_t)(slot / 2);
    y = chartY(dispCand[scrubCand].c, lo, hi);
  } else {
    x = chartX(scrubIdx, sN);
    y = chartY(plotVal(sClose[scrubIdx]), lo, hi);
  }
  // Scrub line/dot: the prototype's is white at 0.7 opacity
  // (C_SCRUB), with the background-colour ring on the dot.
  tft.drawFastVLine(x, gCH_Y, gCH_H, C_SCRUB);
  tft.fillCircle(x, y, 3, C_SCRUB);
  tft.drawCircle(x, y, 3, C_RING);
}

// Shared chart body: fills the chart rect, draws the line or the
// candles and the axis labels, using the geometry set by
// setChartGeom(). Both orientations use it, so the chart is the
// same data drawn wider in landscape.
void drawChartBody() {
  // Exactly the chart rect + the axis row: the old code filled 4 px
  // above the chart and 4 px below it, which erased the bottom 3 px
  // of the Rotate pill in the scrub row (and the top of the axis
  // labels) — every caller had to redraw the scrub row afterwards
  // to repair it. The chart's own pixels all live inside this rect
  // (chartY clamps), so nothing is lost by filling exactly it.
  tft.fillRect(0, gCH_Y, tft.width(), gCH_H, C_BG);
  tft.fillRect(0, gAX_Y, tft.width(), 9, C_BG);
  gCmpActive = false;
  if (sN < 2) {
    setF(F_MONO8, 2);
    tft.setTextColor(C_MUTED, C_BG);
    tft.setCursor(8, gCH_Y + gCH_H / 2 - 6);
    tft.print(chartRange < 0 ? "fetching chart..." : "chart offline");
    return;
  }
  float lo, hi;
  // Comparisons (R3): in line mode, with chips on and an aligned
  // series cached for this range, the plot is rebased to 100 at the
  // range start — BTC + every active comparison share one scale,
  // and the Y labels read in rebased units (see drawYLabels).
  // 1D is excluded (Finding 5): daily closes stepped to intraday
  // points are constant across a 1D window, so every comparison
  // plots flat at 100 and every chip reads +0%.
  if (chartType == 0 && rangeIdx != 0 && cmpAnyOn() && cmpAnyOk() &&
      cmpRange == rangeIdx && sClose[0] > 0) {
    gCmpActive = true;
    gRebLo = 1e9f; gRebHi = -1e9f;
    for (int i = 0; i < sN; i++) {
      float v = plotVal(sClose[i]);
      if (v < gRebLo) gRebLo = v;
      if (v > gRebHi) gRebHi = v;
      for (int c = 0; c < 3; c++) if (cmpOn[c] && cmpOk[c]) {
        float cv = plotValCmp(c, cClose[c][i]);
        if (cv < gRebLo) gRebLo = cv;
        if (cv > gRebHi) gRebHi = cv;
      }
    }
    lo = gRebLo; hi = gRebHi;
  } else {
    lo = chartMin(); hi = chartMax();
  }
  float pad = (hi - lo) * (chartType == 1 ? 0.07f : 0.08f);
  if (pad <= 0) pad = hi * 0.001f;
  lo -= pad; hi += pad;
  gPlotLo = lo; gPlotHi = hi;
  if (chartType == 1) { buildCandles(); drawChartCandles(lo, hi); }
  else                { drawChartLine(lo, hi); if (gCmpActive) drawCmpLines(lo, hi); }
  drawYLabels(lo, hi);
  drawAxisLabels();
  drawScrubOverlay();
}

// Portrait chart area (170x320).
void drawChartArea() {
  setChartGeom(CH_X, CH_Y, CH_W, CH_H, AXIS_Y);
  drawChartBody();
}

// Landscape chart area (320x170) — the full-width chart.
void drawChartAreaL() {
  setChartGeom(L_CH_X, L_CH_Y, L_CH_W, L_CH_H, L_AXIS_Y);
  drawChartBody();
}

// One range pill (Mono 9px bold — the 8px semibold read soft at 3x).
// In candle mode the 5Y/MAX pills are disabled (opacity .32, struck
// candles do not exist there — same as the prototype.
void drawRangePill(int16_t x, int16_t y, int16_t w, int16_t h, int i) {
  bool on = (rangeIdx == i);
  bool disabled = (chartType == 1 && RANGES[i].candleTarget == 0);
  uint16_t bg = on ? C_BTN_ON : C_BTN;
  uint16_t fg = disabled ? C_DIMMED : (on ? C_ONTXT : C_BTN_TXT);
  uint16_t bord = disabled ? C_TILEBD : C_BORD;
  if (on) fillPillSolid(x, y, w, h, 5, C_BTN_ON, C_BG);
  else    fillPill(x, y, w, h, 5, C_BTN, bord, C_BG);
  setF(F_MONO9B, 2);
  tft.setTextColor(fg, bg);
  tft.setTextDatum(MC_DATUM);
  tft.drawString(RANGES[i].key, x + w / 2, y + h / 2);
  tft.setTextDatum(TL_DATUM);
  if (disabled) {
    int16_t tw = tft.textWidth(RANGES[i].key);
    tft.drawFastHLine(x + (w - tw) / 2, y + h / 2, tw, fg);
  }
  // Pass 5 finding 9: the visual pill is only 17 px tall — ~2.3 mm
  // on the real 1.9" panel, far below a fingertip. The HIT box is
  // bigger than the visual pill (21 px tall, 2 px wider): it expands
  // into the dead space above row 1 / below row 2, never into the
  // other row, and 1 px into each 3 px side gap. The visual pill is
  // unchanged; a near-miss tap now lands instead of missing.
  int16_t hx = x - 1, hw = w + 2, hy, hh = 21;
  if (y == R1_Y) hy = y - 4;
  else if (y == R2_Y) hy = y;
  else hy = y - 2;
  btns[nBtns++] = {hx, hy, hw, hh, (int16_t)i};
}

void drawRangeButtons() {
  // row 1: 1D 1W 1M 3M 6M — 5 pills, 28 px, gap 3, start x=9
  int16_t w1 = 28, gap = 3, x = 9;
  for (int i = 0; i < 5; i++) {
    drawRangePill(x, R1_Y, w1, 17, i);
    x += w1 + gap;
  }
  // row 2: YTD 1Y 5Y MAX — 4 pills, 36 px, gap 3, start x=8
  int16_t w2 = 36;
  x = 8;
  for (int i = 5; i < 9; i++) {
    drawRangePill(x, R2_Y, w2, 17, i);
    x += w2 + gap;
  }
  // (The "Rotate" button used to be overlaid on the chart's
  // top-right corner here; it now lives in the scrub row above
  // the chart — see drawScrubRow — so nothing covers the plot.)
}

// "CHART" label + Line|Candles segmented pill + the candle note.
// The pill says the full "Candles" like the prototype (not "Cndl");
// the note drops the redundant type word, so it reads just the
// bucket ("28 × 6h") or "all ranges" in line mode.
void drawTypeRow() {
  setF(F_MONO6, 1);
  tft.setTextColor(C_PILL2, C_BG);
  tft.setCursor(CX0, TYPE_Y + 4);
  tft.print("CHART");
  drawSegPill(CX0 + 26, TYPE_Y, 14, "Line", "Candles", chartType == 0, 18, 19, F_PILL8);
  char note[24];
  if (chartType == 1 && RANGES[rangeIdx].candleTarget > 0)
    snprintf(note, sizeof(note), "%s", CANDLE_LABEL[rangeIdx]);
  else
    snprintf(note, sizeof(note), "all ranges");
  setF(F_MONO7, 2);
  tft.setTextColor(C_PILL2, C_BG);
  int16_t w = tft.textWidth(note);
  tft.setCursor(CX1 - w, TYPE_Y + 3);
  tft.print(note);
}

// Control row: Dark|Light segmented pill, then Price and Auth pills.
// Slimmed to 14 px (was 16) to help reclaim the bottom strip for the
// page dots — the VS chip row moved up 3 px to y 300 below it.
void drawControlRow() {
  int16_t x = CX0;
  x += drawSegPill(x, CTL_Y, 14, "Dark", "Light", themeDark, 23, 24, F_PILL8) + 4;
  x += drawSinglePill(x, CTL_Y, 14, "Price", priceOnly, 13, F_PILL8) + 4;
  drawSinglePill(x, CTL_Y, 14, "Auth", false, 14, F_PILL8);
}

// VS comparison chip row (R3), in the reclaimed footer row (y 300,
// h 13 — moved up from y 303 / h 14 when the page dots took the
// bottom strip; the control row above slimmed 16 -> 14 px to make
// room). LAYOUT DECISION: the chart page had no spare vertical
// room — the range rows, type row and control row all sit at fixed
// Y positions the sim tests tap by coordinate — so the chips take
// the footer row and the "CoinGecko · Coinbase" footer is gone
// from the portrait chart page (it now lives nowhere on-device).
// Each chip always shows that asset's % for the range, on or off
// ("--" while its file has not landed). In candle mode the row is
// disabled (greyed, untappable — comparisons are line-only, like
// the prototype). Landscape has no chip row: its control row is
// already full; lines toggled in portrait persist when rotated.
void drawCmpRow() {
  // 1D: comparisons are meaningless here (see drawChartBody) — the
  // row is hidden, not just disabled, so no flat lines or "+0%"
  // chips are ever shown for the day. Chip state is kept, so
  // switching back to another range restores the row.
  if (rangeIdx == 0) return;
  bool disabled = (chartType == 1);
  char pctTxt[3][12];
  for (int c = 0; c < 3; c++) {
    if (cmpOk[c] && cmpRange == rangeIdx) fmtPct1(cmpPct(c), pctTxt[c], sizeof(pctTxt[c]));
    else snprintf(pctTxt[c], sizeof(pctTxt[c]), "--");
  }
  setF(F_MONO6, 1);
  int16_t vsW = tft.textWidth("VS");
  int16_t chipW[3];
  for (int c = 0; c < 3; c++) {
    char label[24];
    snprintf(label, sizeof(label), "%s %s", CMP_NAME[c], pctTxt[c]);
    chipW[c] = tft.textWidth(label) + 13;  // dot + gap + padding
  }
  int16_t total = vsW + 4;
  for (int c = 0; c < 3; c++) total += chipW[c] + 3;
  total -= 3;
  bool showVS = (total <= CW);
  int16_t x = CX0;
  if (showVS) {
    tft.setTextColor(C_PILL2, C_BG);
    tft.setCursor(x, CMP_Y + 4);
    tft.print("VS");
    x += vsW + 4;
  }
  for (int c = 0; c < 3; c++) {
    char label[24];
    snprintf(label, sizeof(label), "%s %s", CMP_NAME[c], pctTxt[c]);
    bool on = cmpOn[c] && !disabled;
    uint16_t bord = disabled ? C_TILEBD : (on ? CMP_COL[c] : C_BORD);
    uint16_t fg = disabled ? C_DIMMED : (on ? CMP_COL[c] : C_BTN_TXT);
    fillPill(x, CMP_Y, chipW[c], 13, 7, C_BTN, bord, C_BG);
    tft.fillCircle(x + 6, CMP_Y + 7, 2, disabled ? C_DIM : CMP_COL[c]);
    setF(F_MONO6, 1);
    tft.setTextColor(fg, C_BTN);
    tft.setCursor(x + 10, CMP_Y + 4);
    tft.print(label);
    if (!disabled) btns[nBtns++] = {x, CMP_Y, chipW[c], 13, (int16_t)(43 + c)};
    x += chipW[c] + 3;
  }
}

// Price-only screen: the prototype's calm centred view — label,
// block, big price, always-24h change, two stats, currency pill,
// and a swipe hint. No HIGH/LOW, no Updated, no brightness stepper.
// Swipe (not tap) goes back to the chart, as the hint says.
// Tapping the big price toggles USD/CAD, same as the chart page.
#define PO_LABEL_Y 22
#define PO_BLOCK_Y 32
#define PO_PRICE_Y 52
#define PO_CHG_Y   90
#define PO_RULE_Y  112
#define PO_STAT_Y  130
#define PO_CUR_Y   214
#define PO_HINT_Y  298

void drawPriceOnlyStats(int16_t y) {
  char satsVal[16], blkVal[16];
  long s = satsPerDollar();
  if (s > 0) fmtComma(s, satsVal, sizeof(satsVal));
  else snprintf(satsVal, sizeof(satsVal), "--");
  if (blockHeight > 0) fmtComma(blockHeight, blkVal, sizeof(blkVal));
  else snprintf(blkVal, sizeof(blkVal), "--");
  const char *labels[2] = {"SATS PER DOLLAR", "BLOCK HEIGHT"};
  for (int k = 0; k < 2; k++) {
    setF(F_MONO6, 1);
    tft.setTextColor(C_PILL2, C_BG);
    int16_t w = tft.textWidth(labels[k]);
    tft.setCursor((SW - w) / 2, y);
    tft.print(labels[k]);
    tft.setTextColor(C_TEXT, C_BG);
    if (k == 0) {
      // "1,677" + a muted "sats", as in the prototype.
      setF(F_STAT15, 4);
      int16_t nw = tft.textWidth(satsVal);
      setF(F_MONO7, 2);
      int16_t sw = tft.textWidth(" sats");
      int16_t x = (SW - (nw + sw)) / 2;
      setF(F_STAT15, 4);
      tft.setCursor(x, y + 8);
      tft.print(satsVal);
      setF(F_MONO7, 2);
      tft.setTextColor(C_MUTED, C_BG);
      tft.setCursor(x + nw, y + 13);
      tft.print(" sats");
    } else {
      // OutfitB15 now includes '#', so "#977,390" matches the prototype.
      setF(F_STAT15, 4);
      char shown[20];
      snprintf(shown, sizeof(shown), "#%s", blkVal);
      int16_t nw = tft.textWidth(shown);
      tft.setCursor((SW - nw) / 2, y + 8);
      tft.print(shown);
    }
    y += 36;
  }
}

void drawPriceOnly() {
  nBtns = 0;
  // "BITCOIN · LIVE PRICE" — middot is in the Mono vlw charset, not Inter.
  const char mid[] = " \xC2\xB7 ";
  setF(F_PILL6, 1);
  int16_t wBitcoin = tft.textWidth("BITCOIN");
  int16_t wLive = tft.textWidth("LIVE PRICE");
  setF(F_MONO6, 1);
  int16_t wMid = tft.textWidth(mid);
  int16_t x = (SW - (wBitcoin + wMid + wLive)) / 2;
  setF(F_PILL6, 1);
  tft.setTextColor(C_MUTED, C_BG);
  tft.setCursor(x, PO_LABEL_Y);
  tft.print("BITCOIN");
  setF(F_MONO6, 1);
  tft.setCursor(x + wBitcoin, PO_LABEL_Y + 1);
  tft.print(mid);
  setF(F_PILL6, 1);
  tft.setCursor(x + wBitcoin + wMid, PO_LABEL_Y);
  tft.print("LIVE PRICE");
  char blk[24];
  if (blockHeight > 0) {
    char hb[16];
    fmtComma(blockHeight, hb, sizeof(hb));
    snprintf(blk, sizeof(blk), "BLOCK %s", hb);
  } else {
    snprintf(blk, sizeof(blk), "BLOCK --");
  }
  setF(F_MONO6, 1);
  tft.setTextColor(C_PILL2, C_BG);
  int16_t w = tft.textWidth(blk);
  tft.setCursor((SW - w) / 2, PO_BLOCK_Y);
  tft.print(blk);
  // big price, centred, "$" cyan, digits white, glow halo
  char buf[20];
  fmtMoney(priceUSD, buf, sizeof(buf));
  setF(F_PRICE_PO, 6);
  int16_t pw = tft.textWidth(buf);
  int16_t px = (SW - pw) / 2;
  drawPriceHalo(px, PO_PRICE_Y, buf);
  tft.setTextColor(C_CYAN, C_BG);
  tft.setCursor(px, PO_PRICE_Y);
  tft.print("$");
  tft.setTextColor(C_PRICE, C_BG);
  tft.setCursor(px + tft.textWidth("$"), PO_PRICE_Y);
  tft.print(buf + 1);
  btns[nBtns++] = {px, PO_PRICE_Y, pw, 32, 27};  // tap price: toggle currency
  // change row, always the 24h move (Sunil: "Yes, show the 24h change")
  float chg = chg24h;
  char cb[16];
  fmtPctAbs(chg, cb, sizeof(cb));
  const char *per = "\xC2\xB7 24h";
  setF(F_MONO9B, 4);
  int16_t cw = tft.textWidth(cb);
  setF(F_MONO7, 2);
  int16_t pw2 = tft.textWidth(per);
  int16_t total = 5 + 3 + cw + 4 + pw2;
  x = (SW - total) / 2;
  uint16_t col = (!priceOk) ? C_DIMMED : (chg >= 0 ? C_GREEN : C_RED);
  if (chg >= 0) tft.fillTriangle(x, PO_CHG_Y + 4, x + 5, PO_CHG_Y + 4, x + 2, PO_CHG_Y, col);
  else          tft.fillTriangle(x, PO_CHG_Y, x + 5, PO_CHG_Y, x + 2, PO_CHG_Y + 4, col);
  setF(F_MONO9B, 4);
  tft.setTextColor(col, C_BG);
  tft.setCursor(x + 8, PO_CHG_Y);
  tft.print(cb);
  setF(F_MONO7, 2);
  tft.setTextColor(C_MUTED, C_BG);
  tft.setCursor(x + 8 + cw + 4, PO_CHG_Y + 1);
  tft.print(per);
  // rule: 36x2 cyan, centred, with a 1 px dim-cyan halo
  fillPillSolid((SW - 36) / 2, PO_RULE_Y, 36, 4, 2, C_GLOW, C_BG);
  tft.fillRect((SW - 36) / 2, PO_RULE_Y + 1, 36, 2, C_CYAN);
  drawPriceOnlyStats(PO_STAT_Y);
  // currency pill, centred — "USD $" / "CAD $", same as the chart page
  int16_t cyw = segPillWidth("USD $", "CAD $", F_PILL6);
  drawSegPill((SW - cyw) / 2, PO_CUR_Y, 14, "USD $", "CAD $", !curCAD, 16, 17, F_PILL6);
  setF(F_MONO6, 1);
  tft.setTextColor(C_DIM, C_BG);
  const char *hint = "NOTHING BUT THE PRICE \xC2\xB7 SWIPE FOR THE CHART";
  // The prototype uses an em dash; Inter/Mono vlw is ASCII + middot only.
  w = tft.textWidth(hint);
  tft.setCursor((SW - w) / 2, PO_HINT_Y);
  tft.print(hint);
  drawPageDots();
}

// ==================================================================
// Block clock (R1) — the prototype's page 2, as a device app.
// Three focus views auto-rotating every 12 s (tap the dots to jump,
// which restarts the timer): block height + 10-minute ring, sats per
// dollar, next halving. Below: a 2x2 stat grid, the big ET clock and
// a date line. Data is all mempool.space (see fetchClockData).
// Layout (170x320): title 24, focus card 40-172, dots 178, stat
// grid 192-247, big clock 252, date 278, nav row 294-310.
// ==================================================================

// --- Block clock layout ---
#define CK_TITLE_Y 24
#define CK_CARD_Y  40
#define CK_CARD_H  132
#define CK_DOTS_Y  178
#define CK_GRID_Y  192
#define CK_GRID_H  25
#define CK_CLOCK_Y 266
#define CK_DATE_Y  294

// Ring gauge: a track circle plus a filled arc from the top,
// clockwise, `frac` of the way round. Per-pixel annulus fill (Pass 5
// finding 1): the old 1-degree radial strokes left ~8% holes — each
// stroke is a Bresenham line from radius 17 to 22 whose integer-
// truncated endpoints repeat for consecutive angles, so distinct
// lines sit 2-3 deg apart and the 1 px paths never overlap (the
// 2-degree step was worse at 13.4%; 5 concentric drawCircles still
// leave 9.6%). Filling every pixel whose centre lies in the annulus
// (16.5 <= r < 22.5 for rIn 17 / rOut 22) and whose angle is inside
// the arc leaves 0 holes (verified by simulation + framebuffer
// sampling). Cost ~2,100 px, once per 30 s redraw.
// Angles: 0 = top, clockwise. Uses atan2f, so <math.h> via Arduino.h.
void drawRingGauge(int16_t cx, int16_t cy, int16_t rOut, int16_t rIn,
                   float frac, uint16_t fg, uint16_t track) {
  if (frac < 0) frac = 0;
  if (frac > 1) frac = 1;
  float arc = frac * 360.0f;
  float rLo = (float)rIn - 0.5f, rHi = (float)rOut + 0.5f;
  float rLo2 = rLo * rLo, rHi2 = rHi * rHi;
  for (int16_t y = cy - rOut - 1; y <= cy + rOut + 1; y++) {
    for (int16_t x = cx - rOut - 1; x <= cx + rOut + 1; x++) {
      float dx = (float)(x - cx), dy = (float)(y - cy);
      float d2 = dx * dx + dy * dy;
      if (d2 < rLo2 || d2 >= rHi2) continue;
      // Angle from the top, clockwise, in degrees.
      float a = atan2f(dx, -dy) * 57.2957795f;
      if (a < 0) a += 360.0f;
      tft.drawPixel(x, y, (a < arc) ? fg : track);
    }
  }
}

// The ring alone (its bbox), for the 30 s redraw in drawClockDynamic.
void drawClockRing() {
  if (clockFocus != 0) return;
  tft.fillRect(14, 104, 50, 50, C_SURFACE);
  float frac = 0;
  if (timeOk && lastBlockTs > 0) {
    long secs = (long)(time(nullptr) - lastBlockTs);
    frac = secs / 600.0f;  // toward a 10-minute target
  }
  drawRingGauge(38, 128, 22, 17, frac, C_CYAN, C_BARBG);
}

// The "X min SS s ago" line (focus 0, right of the ring).
void drawClockAgo() {
  tft.fillRect(68, 104, 94, 12, C_SURFACE);
  char ago[16];
  if (timeOk && lastBlockTs > 0) {
    fmtAgo((long)(time(nullptr) - lastBlockTs), ago, sizeof(ago));
  } else {
    snprintf(ago, sizeof(ago), "--");
  }
  char line[24];
  snprintf(line, sizeof(line), "%s ago", ago);
  setF(F_MONO8B, 2);
  tft.setTextColor(C_TEXT, C_SURFACE);
  tft.setCursor(68, 106);
  tft.print(line);
}

// Big ET clock, centred: Outfit 22 px digits with a hand-drawn
// colon (':' is not in the Outfit vlw charset — PRICE only — so
// the two dots are fillCircles), then " PM · ET" in Mono bold 8.
// Falls back to "--:--" in Mono when the clock is not synced.
void drawClockBig() {
  tft.fillRect(0, CK_CLOCK_Y, SW, 26, C_BG);
  char clk[20];
  fmtClock12(clk, sizeof(clk));
  if (clk[0] == '-') {
    setF(F_MONO8B, 2);
    tft.setTextColor(C_MUTED, C_BG);
    int16_t w = tft.textWidth("--:--");
    tft.setCursor((SW - w) / 2, CK_CLOCK_Y + 7);
    tft.print("--:--");
    return;
  }
  // "4:32:08 PM" -> hour, min, sec, "PM".
  int hour = 0, min = 0, sec = 0;
  char ap[4] = "";
  sscanf(clk, "%d:%d:%d %3s", &hour, &min, &sec, ap);
  char hs[4], ms[4], ss[4];
  snprintf(hs, sizeof(hs), "%d", hour);
  snprintf(ms, sizeof(ms), "%02d", min);
  snprintf(ss, sizeof(ss), "%02d", sec);
  char sufFull[12];
  snprintf(sufFull, sizeof(sufFull), "%s ET", ap);
  setF(F_PRICE_L, 4);
  int16_t hw = tft.textWidth(hs);
  int16_t mw = tft.textWidth(ms);
  int16_t swd = tft.textWidth(ss);
  setF(F_MONO8B, 2);
  int16_t suw = tft.textWidth(sufFull);
  const int16_t gap = 6;  // digit group + colon-dot column
  int16_t total = hw + gap + mw + gap + swd + 4 + suw;
  int16_t x = (SW - total) / 2;
  setF(F_PRICE_L, 4);
  tft.setTextColor(C_TEXT, C_BG);
  tft.setCursor(x, CK_CLOCK_Y);
  tft.print(hs);
  tft.fillCircle(x + hw + 3, CK_CLOCK_Y + 8, 2, C_TEXT);
  tft.fillCircle(x + hw + 3, CK_CLOCK_Y + 15, 2, C_TEXT);
  tft.setCursor(x + hw + gap, CK_CLOCK_Y);
  tft.print(ms);
  tft.fillCircle(x + hw + gap + mw + 3, CK_CLOCK_Y + 8, 2, C_TEXT);
  tft.fillCircle(x + hw + gap + mw + 3, CK_CLOCK_Y + 15, 2, C_TEXT);
  tft.setCursor(x + hw + gap + mw + gap, CK_CLOCK_Y);
  tft.print(ss);
  setF(F_MONO8B, 2);
  tft.setTextColor(C_MUTED, C_BG);
  tft.setCursor(x + hw + gap + mw + gap + swd + 4, CK_CLOCK_Y + 8);
  tft.print(sufFull);
}

// Date line under the big clock: "Tue, Nov 24, 2026 · Ottawa".
void drawClockDate() {
  tft.fillRect(0, CK_DATE_Y, SW, 10, C_BG);
  char d[40];
  fmtDateLine(d, sizeof(d));
  setF(F_MONO7, 2);
  tft.setTextColor(C_MUTED, C_BG);
  int16_t w = tft.textWidth(d);
  tft.setCursor((SW - w) / 2, CK_DATE_Y);
  tft.print(d);
}

// One focus view inside the card (the card bg is drawn by the caller).
void drawClockFocus() {
  // Focus 1 (sats) and 2 (halving) end ~40 px above the card bottom
  // while focus 0 fills the card — their content is shifted down
  // 18 px so the block sits centred in the 132 px card. Focus 0
  // stays put: its ring is drawn at fixed coords by drawClockRing.
  // (Finding 11.)
  int16_t cy = CK_CARD_Y + ((clockFocus == 0) ? 0 : 18);
  if (clockFocus == 0) {
    // (0) Block height + 10-minute ring.
    setF(F_MONO6, 1);
    tft.setTextColor(C_PILL2, C_SURFACE);
    tft.setCursor(16, cy + 8);
    tft.print("NOW MINING · BLOCK HEIGHT");
    char hb[16];
    if (blockHeight > 0) fmtComma(blockHeight, hb, sizeof(hb));
    else snprintf(hb, sizeof(hb), "--");
    setF(F_PRICE, 6);
    tft.setTextColor(C_TEXT, C_SURFACE);
    tft.setCursor(16, cy + 18);
    tft.print("#");
    tft.print(hb);
    drawClockRing();
    drawClockAgo();
    drawWrapped("Since the last block. The ring fills toward a "
                "10-minute target.", 68, cy + 80, 86, 9,
                F_MONO7, 2, C_MUTED, C_SURFACE);
  } else if (clockFocus == 1) {
    // (1) Sats per dollar.
    setF(F_MONO6, 1);
    tft.setTextColor(C_PILL2, C_SURFACE);
    tft.setCursor(16, cy + 8);
    tft.print("SATS PER DOLLAR");
    char sats[16];
    fmtComma(satsPerDollar(), sats, sizeof(sats));
    setF(F_PRICE, 6);
    tft.setTextColor(C_CYAN, C_SURFACE);
    tft.setCursor(16, cy + 18);
    tft.print(satsPerDollar() > 0 ? sats : "--");
    drawWrapped("One dollar buys this many satoshis right now. "
                "When the price falls, this number climbs.",
                16, cy + 60, 138, 10, F_MONO7, 2, C_MUTED, C_SURFACE);
  } else {
    // (2) Next halving.
    setF(F_MONO6, 1);
    tft.setTextColor(C_PILL2, C_SURFACE);
    tft.setCursor(16, cy + 6);
    tft.print("NEXT HALVING");
    // The prototype is one line ("NEXT HALVING · THE CLOCK INSIDE
    // THE CLOCK") but that does not fit the 138 px card at Mono 6,
    // so the tag sits on the line under the label.
    tft.setCursor(16, cy + 14);
    tft.print("Â· THE CLOCK INSIDE THE CLOCK");
    char toGo[16];
    long left = (blockHeight > 0) ? (HALVING_BLOCK - blockHeight) : -1;
    if (left >= 0) fmtComma(left, toGo, sizeof(toGo));
    else snprintf(toGo, sizeof(toGo), "--");
    setF(F_PRICE, 6);
    tft.setTextColor(C_TEXT, C_SURFACE);
    tft.setCursor(16, cy + 24);
    tft.print(toGo);
    setF(F_MONO7, 2);
    tft.setTextColor(C_MUTED, C_SURFACE);
    tft.setCursor(16, cy + 56);
    tft.print("blocks to go, to block 1,050,000");
    // Progress bar: % of the epoch.
    float pct = 0;
    if (blockHeight > 0) pct = (float)(blockHeight % HALVING_EPOCH) / HALVING_EPOCH * 100.0f;
    int16_t bx = 16, bw = SW - 32;
    fillPillSolid(bx, cy + 72, bw, 5, 2, C_BARBG, C_SURFACE);
    int frac = (int)(pct * bw / 100.0f);
    if (frac > 0) fillPillSolid(bx, cy + 72, frac, 5, 2, C_CYAN, C_BARBG);
    char pl[24];
    snprintf(pl, sizeof(pl), "%.1f%% OF THE EPOCH", pct);
    setF(F_MONO7, 2);
    tft.setTextColor(C_MUTED, C_SURFACE);
    tft.setCursor(16, cy + 82);
    tft.print(pl);
    const char *eta = "~ APR 2028";
    int16_t ew = tft.textWidth(eta);
    tft.setCursor(CX1 - ew, cy + 82);
    tft.print(eta);
  }
}

// Per-second dynamic redraw while the clock screen is showing: the
// "ago" line, the big clock + date, and the ring every 30 s. Only
// the small text areas are repainted — no full-screen flicker.
void drawClockDynamic() {
  unsigned long now = millis();
  if (clockFocus == 0) {
    drawClockAgo();
    if (now - lastClockRingMs >= 30000) {
      lastClockRingMs = now;
      drawClockRing();
    }
  }
  drawClockBig();
  drawClockDate();
}

void drawClockAll() {
  nBtns = 0;
  applyTheme();
  tft.fillScreen(C_BG);
  drawStatusBar(15, false);
  // title + green LIVE · AUTO (a live-dot, not a cyan pill)
  setF(F_MONO8B, 2);
  tft.setTextColor(C_TEXT, C_BG);
  tft.setCursor(8, CK_TITLE_Y);
  tft.print("BLOCK CLOCK");
  const char live[] = "LIVE \xC2\xB7 AUTO";
  setF(F_MONO6, 1);
  int16_t lw = tft.textWidth(live);
  int16_t lx = CX1 - lw;
  tft.fillCircle(lx - 7, CK_TITLE_Y + 3, 2, C_GREEN);
  tft.setTextColor(C_GREEN, C_BG);
  tft.setCursor(lx, CK_TITLE_Y + 1);
  tft.print(live);
  // focus card
  fillPill(8, CK_CARD_Y, 154, CK_CARD_H, 7, C_SURFACE, C_TILEBD, C_BG);
  drawClockFocus();
  // capsule dots, left-aligned like the prototype: inactive 16x6,
  // active 26x6, 4 px gaps. Hit box is taller than the 6 px visual.
  {
    int16_t x = 8;
    for (int f = 0; f < 3; f++) {
      bool on = (clockFocus == f);
      int16_t w = on ? 26 : 16;
      fillPillSolid(x, CK_DOTS_Y, w, 6, 3, on ? C_CYAN : C_DIM, C_BG);
      btns[nBtns++] = {x, (int16_t)(CK_DOTS_Y - 5), w, 16, (int16_t)(30 + f)};
      x += w + 4;
    }
  }
  // 2x2 stat grid
  char satsX[24], diffV[12], feeV[16], memV[12];
  long sats = satsPerDollar();
  if (sats > 0) {
    char a[12], b[12];
    fmtComma(sats * 10, a, sizeof(a));
    fmtComma(sats * 100, b, sizeof(b));
    snprintf(satsX, sizeof(satsX), "%s / %s", a, b);
  } else {
    snprintf(satsX, sizeof(satsX), "--");
  }
  if (diffProgress >= 0) snprintf(diffV, sizeof(diffV), "%.1f%%", diffProgress);
  else snprintf(diffV, sizeof(diffV), "--");
  if (feeFastest >= 0) snprintf(feeV, sizeof(feeV), "%.0f sat/vB", feeFastest);
  else snprintf(feeV, sizeof(feeV), "--");
  if (mempoolMB >= 0) snprintf(memV, sizeof(memV), "%ld MB", mempoolMB);
  else snprintf(memV, sizeof(memV), "--");
  // Full figures in Mono 6 — "16,770 / 167,700" fits the 75 px tile;
  // Mono 8 did not, which is why the old draw used the k-form.
  drawStatTile(8, CK_GRID_Y, 75, CK_GRID_H, "SATS PER $10 / $100", satsX,
               false, F_MONO6, 1);
  drawStatTile(87, CK_GRID_Y, 76, CK_GRID_H, "DIFFICULTY ADJ", diffV,
               false, F_MONO8, 2);
  drawStatTile(8, CK_GRID_Y + CK_GRID_H + 5, 75, CK_GRID_H, "FEES · FASTEST", feeV,
               false, F_MONO8, 2);
  drawStatTile(87, CK_GRID_Y + CK_GRID_H + 5, 76, CK_GRID_H, "MEMPOOL", memV,
               false, F_MONO8, 2);
  // big 12-hour ET clock + date line
  drawClockBig();
  drawClockDate();
  drawPageDots();
}

// Fetch all four block-clock feeds from mempool.space. Each is a
// small JSON object (except /api/blocks, the latest 10 blocks —
// only rows[0] is read). Returns true if anything landed; failures
// keep the last good values on screen.
bool fetchClockData() {
  FetchGuard guard;
  bool any = false;
  WiFiClientSecure client;
  HTTPClient http;
  int code = httpsGet(URL_MEMPOOL_BLOCKS, client, http);
  if (code == 200) {
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, http.getStream());
    if (!err) {
      JsonArray rows = doc.as<JsonArray>();
      if (rows.size() > 0) {
        long ts = rows[0]["timestamp"];
        long h = rows[0]["height"];
        if (ts > 0) { lastBlockTs = ts; any = true; }
        if (h > 0) blockHeight = h;
      }
    }
  }
  http.end();
  code = httpsGet(URL_MEMPOOL_DIFF, client, http);
  if (code == 200) {
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, http.getStream());
    if (!err) {
      float p = doc["progressPercent"];
      if (p >= 0) { diffProgress = p; any = true; }
    }
  }
  http.end();
  code = httpsGet(URL_MEMPOOL_FEES, client, http);
  if (code == 200) {
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, http.getStream());
    if (!err) {
      float f = doc["fastestFee"];
      if (f >= 0) { feeFastest = f; any = true; }
    }
  }
  http.end();
  code = httpsGet(URL_MEMPOOL_MEMPOOL, client, http);
  if (code == 200) {
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, http.getStream());
    if (!err) {
      long vs = doc["vsize"];
      if (vs >= 0) { mempoolMB = vs / 1000000; any = true; }
    }
  }
  http.end();
  if (any) lastClockFetchMs = millis();
  return any;
}

// ==================================================================
// QR receive (R2) — Jade (on-chain) + Lightning, one screen each.
// Unlike the prototype, whose QRs are decorative pseudo-random
// grids, these are REAL scannable QRs from the nayuki qrcodegen
// library (ECC Medium, byte mode), encoding the same hardcoded
// watch-only strings the prototype shows. Tap the QR card to flip
// to the full address + the watch-only warning; tap anywhere to
// flip back. The QR card stays white in both themes — a QR must be
// dark modules on a light background to scan.
// Layout: title 24, Jade|Lightning seg 42, QR card 62-210 (148 px),
// address 216-234, note 238, nav row 294-310.
// ==================================================================

// Draw a real QR for `text`, centred in a cardS x cardS white card
// at (cardX, cardY). Module 4 px + 4-module quiet zone: a v3 code
// (29 modules, the bc1q address) fills the 148 px card exactly;
// smaller versions centre inside it.
void drawQRCode(const char *text, int16_t cardX, int16_t cardY,
                int16_t cardS) {
  qrcodegen::QrCode qr =
      qrcodegen::QrCode::encodeText(text, qrcodegen::QrCode::Ecc::MEDIUM);
  int n = qr.getSize();
  const int px = 4, quiet = 4;
  int total = (n + 2 * quiet) * px;
  int16_t ox = cardX + (cardS - total) / 2;
  int16_t oy = cardY + (cardS - total) / 2;
  for (int y = 0; y < n; y++) {
    for (int x = 0; x < n; x++) {
      if (qr.getModule(x, y))
        tft.fillRect(ox + (x + quiet) * px, oy + (y + quiet) * px,
                     px, px, 0x0000);
    }
  }
}

// Coloured 15x15 badge: green "J" for Jade, amber lightning for LN.
// The lightning mark is drawn (the fonts have no ϟ glyph).
void drawQRBadge(int16_t x, int16_t y, bool jade) {
  const uint16_t jadeCol = 0x36D3;  // #34d399
  const uint16_t ink = 0x0862;      // #0b0f16
  fillPillSolid(x, y, 15, 15, 4, jade ? jadeCol : C_AMBER, C_BG);
  if (jade) {
    setF(F_LABEL9, 4);
    tft.setTextColor(ink, jadeCol);
    tft.setTextDatum(MC_DATUM);
    tft.drawString("J", x + 7, y + 8);
    tft.setTextDatum(TL_DATUM);
  } else {
    // Compact bolt inside the 15 px badge.
    tft.fillTriangle(x + 8, y + 2, x + 4, y + 8, x + 8, y + 8, ink);
    tft.fillTriangle(x + 6, y + 7, x + 10, y + 7, x + 6, y + 13, ink);
  }
}

void drawQRAll() {
  nBtns = 0;
  applyTheme();
  tft.fillScreen(C_BG);
  drawStatusBar(15, false);
  bool jade = (qrPage == 0);
  const char *addr = jade ? QR_JADE_ADDR : QR_LN_ADDR;
  // header: coloured badge + title + right-aligned subtitle
  drawQRBadge(8, 20, jade);
  setF(F_MONO8B, 2);
  tft.setTextColor(C_TEXT, C_BG);
  tft.setCursor(28, 23);
  tft.print(jade ? "JADE" : "LIGHTNING");
  setF(F_MONO6, 1);
  tft.setTextColor(C_MUTED, C_BG);
  const char *sub = jade ? "ON-CHAIN \xC2\xB7 RECEIVE" : "RECEIVE";
  int16_t sw = tft.textWidth(sub);
  tft.setCursor(CX1 - sw, 24);
  tft.print(sub);

  if (!qrFlipped) {
    // QR card stays 148 px (4 px modules + quiet zone) so the
    // encoded grid is unchanged. With the Jade|Lightning pill gone,
    // the card starts higher, closer to the prototype's 9 px gap.
    const int16_t cardY = 42;
    fillPill(11, cardY, 148, 148, 7, 0xFFFF, C_TILEBD, C_BG);
    drawQRCode(addr, 11, cardY, 148);
    btns[nBtns++] = {11, cardY, 148, 148, 41};  // tap QR card to flip
    setF(F_MONO7, 2);
    tft.setTextColor(C_MUTED, C_BG);
    if (jade) {
      char l1[24], l2[24];
      snprintf(l1, sizeof(l1), "%.21s", addr);
      snprintf(l2, sizeof(l2), "%s", addr + 21);
      int16_t w = tft.textWidth(l1);
      tft.setCursor((SW - w) / 2, 200);
      tft.print(l1);
      w = tft.textWidth(l2);
      tft.setCursor((SW - w) / 2, 209);
      tft.print(l2);
    } else {
      int16_t w = tft.textWidth(addr);
      tft.setCursor((SW - w) / 2, 204);
      tft.print(addr);
    }
    setF(F_MONO6, 1);
    tft.setTextColor(C_DIM, C_BG);
    const char *note = jade ? "TAP QR FOR FULL ADDRESS" : "TAP QR FOR DETAILS";
    int16_t w = tft.textWidth(note);
    tft.setCursor((SW - w) / 2, 222);
    tft.print(note);
  } else {
    // Flipped: a single address + warning card from below the header
    // down to just above the page dots, so there is no empty band.
    // Warning is amber, like the prototype. Encode path is unused
    // here — the strings and ECC are unchanged.
    // Compact card hugging the address + warning, like the prototype's
    // .qr-full. A full-height card left a cavernous empty body; the
    // page background below the card is the same calm gap the
    // unflipped view already has. Height covers two address lines,
    // the wrapped warning (~4 lines) and padding.
    const int16_t cardY = 42, cardH = 118;
    fillPill(8, cardY, 154, cardH, 7, C_SURFACE, C_TILEBD, C_BG);
    char a1[24], a2[24];
    if (jade) {
      snprintf(a1, sizeof(a1), "%.21s", addr);
      snprintf(a2, sizeof(a2), "%s", addr + 21);
    } else {
      const char *at = strchr(addr, '@');
      size_t n1 = at ? (size_t)(at - addr) + 1 : strlen(addr);
      snprintf(a1, sizeof(a1), "%.*s", (int)n1, addr);
      snprintf(a2, sizeof(a2), "%s", addr + n1);
    }
    setF(F_MONO8, 2);
    tft.setTextColor(C_TEXT, C_SURFACE);
    tft.setCursor(16, cardY + 12);
    tft.print(a1);
    tft.setCursor(16, cardY + 26);
    tft.print(a2);
    const char *warn = jade
        ? "Receive only. This is a watch-only address - the keychain "
          "holds no keys and can never sign or send."
        : "Lightning address - anyone can pay it, nothing on the "
          "device can spend from it. Amounts are set by the sender.";
    drawWrapped(warn, 16, cardY + 48, 138, 10, F_MONO7, 2, C_AMBER, C_SURFACE);
    setF(F_MONO6, 1);
    tft.setTextColor(C_DIM, C_BG);
    const char *note = "TAP ANYWHERE TO GO BACK";
    int16_t w = tft.textWidth(note);
    tft.setCursor((SW - w) / 2, cardY + cardH + 10);
    tft.print(note);
  }
  drawPageDots();
}


// ==================================================================
// Landscape chart view (320x170) — setRotation(1)
// ------------------------------------------------------------------
// The device has no tilt sensor, so rotation is a button tap: the
// "Rotate" button on the portrait chart turns it landscape, and the
// "Portrait" button on the landscape control row turns it back.
// Only the chart view goes landscape — price-only and the Auth
// screen stay portrait, and the device always boots in portrait.
// setRotation(1) reads upright when the device is turned clockwise
// (ST7789 MADCTL = MX|MV — see the note in touchRead()). The range
// and chart type are kept when rotating; nothing is reset.
// ==================================================================

// Landscape header: "BTC" + block height on the left, the USD|CAD
// segmented pill on the right (ids 16/17, same as portrait).
void drawHeaderL() {
  setF(F_PILL8, 2);
  tft.setTextColor(C_MUTED, C_BG);
  tft.setCursor(L_CX0, L_HDR_Y);
  tft.print("BTC");
  int16_t bw = tft.textWidth("BTC");
  char blk[24];
  if (blockHeight > 0) {
    char hb[16];
    fmtComma(blockHeight, hb, sizeof(hb));
    snprintf(blk, sizeof(blk), "BLOCK %s", hb);
  } else {
    snprintf(blk, sizeof(blk), "BLOCK --");
  }
  setF(F_MONO7, 2);
  tft.setTextColor(C_PILL2, C_BG);
  tft.setCursor(L_CX0 + bw + 5, L_HDR_Y + 1);
  tft.print(blk);
  int16_t pw = segPillWidth("USD", "CAD", F_PILL8);
  drawSegPill(L_CX1 - pw, L_HDR_Y, 14, "USD", "CAD", !curCAD, 16, 17, F_PILL8);
}

// Landscape price row: price (Outfit 22px) on the left, % change
// right-aligned. The range span is skipped — the highlighted range
// button already shows the range.
void drawPriceL() {
  char buf[20];
  fmtMoney(priceUSD, buf, sizeof(buf));
  setF(F_PRICE_L, 4);
  drawPriceHalo(L_CX0, L_PRICE_Y, buf);
  tft.setTextColor(C_CYAN, C_BG);
  tft.setCursor(L_CX0, L_PRICE_Y);
  tft.print("$");
  int16_t dw = tft.textWidth("$");
  tft.setTextColor(C_PRICE, C_BG);
  tft.setCursor(L_CX0 + dw, L_PRICE_Y);
  tft.print(buf + 1);
  // % change, right-aligned in the row (triangle + %, vertically
  // centred on the 22 px price)
  float chg = rangeChange();
  char cb[16];
  fmtPctAbs(chg, cb, sizeof(cb));
  setF(F_MONO8B, 4);
  // Stale-dimmed like portrait (R11): the % belongs to the previous
  // range until the fetch lands.
  uint16_t col = chartStale() ? C_DIMMED : (chg >= 0 ? C_GREEN : C_RED);
  int16_t w = tft.textWidth(cb);
  int16_t tx = L_CX1 - w - 8;
  if (chg >= 0) tft.fillTriangle(tx, L_PRICE_Y + 11, tx + 5, L_PRICE_Y + 11, tx + 2, L_PRICE_Y + 7, col);
  else          tft.fillTriangle(tx, L_PRICE_Y + 7, tx + 5, L_PRICE_Y + 7, tx + 2, L_PRICE_Y + 11, col);
  tft.setTextColor(col, C_BG);
  tft.setCursor(tx + 8, L_PRICE_Y + 7);
  tft.print(cb);
}

// Landscape buttons: all 9 ranges in one row, then the type pill
// and Portrait. No theme pill here — the ranges needed the width
// ("MAX" overflowed its 14 px pill with the theme pill in the row),
// and the prototype's landscape has no on-device theme pill either;
// the theme toggles in portrait. No Auth button here — Auth stays
// portrait (tap Portrait, then Auth). No Price-only button either —
// landscape IS the chart view. id 15 ("Portrait") is the same
// Rotate toggle as in portrait.
void drawLandscapeButtons() {
  setF(F_PILL8, 2);
  int16_t typeW = tft.textWidth("Line") + tft.textWidth("Cndl") + 15;
  int16_t portW = tft.textWidth("Portrait") + 12;
  int16_t avail = (L_CX1 - L_CX0) - (typeW + portW + 4);
  int16_t rw = (avail - 8 * 2) / 9;   // 9 ranges, 2 px gaps
  int16_t x = L_CX0;
  for (int i = 0; i < NRANGES; i++) {
    bool on = (rangeIdx == i);
    bool disabled = (chartType == 1 && RANGES[i].candleTarget == 0);
    uint16_t bg = on ? C_BTN_ON : C_BTN;
    uint16_t fg = disabled ? C_DIMMED : (on ? C_ONTXT : C_BTN_TXT);
    uint16_t bord = disabled ? C_TILEBD : C_BORD;
    if (on) fillPillSolid(x, L_CTL_Y, rw, 16, 5, C_BTN_ON, C_BG);
    else    fillPill(x, L_CTL_Y, rw, 16, 5, C_BTN, bord, C_BG);
    // Landscape range pills: Mono 9px bold, same as portrait — the
    // 7px semibold read soft at 3x. "MAX" is 15 px in a 17 px pill.
    setF(F_MONO9B, 2);
    tft.setTextColor(fg, bg);
    tft.setTextDatum(MC_DATUM);
    tft.drawString(RANGES[i].key, x + rw / 2, L_CTL_Y + 8);
    tft.setTextDatum(TL_DATUM);
    if (disabled) {
      int16_t tw = tft.textWidth(RANGES[i].key);
      tft.drawFastHLine(x + (rw - tw) / 2, L_CTL_Y + 8, tw, fg);
    }
    btns[nBtns++] = {x, L_CTL_Y, rw, 16, (int16_t)i};
    x += rw + 2;
  }
  x += 2;   // group gap
  x += drawSegPill(x, L_CTL_Y, 16, "Line", "Cndl", chartType == 0, 18, 19, F_PILL8) + 2;
  drawSinglePill(x, L_CTL_Y, 16, "Portrait", false, 15, F_PILL8);
}

void drawLandscapeAll() {
  nBtns = 0;
  applyTheme();
  tft.fillScreen(C_BG);
  drawStatusBar(13, true);
  drawHeaderL();
  drawPriceL();
  drawScrubRow();
  drawChartAreaL();
  drawLandscapeButtons();
}

// Forward: the Auth screen is defined in the Auth section (after
// hitTest), but drawAll() dispatches to it. Same for the block clock
// (R1) and QR (R2) screens, defined after drawPriceOnly().
void drawAuthAll();
void drawClockAll();
void drawQRAll();

// Program a display rotation only when it actually changes, so a
// redraw does not keep re-sending the MADCTL command.
void setRotationIf(int r) {
  if (r != curRot) { tft.setRotation(r); curRot = r; }
}

// The single redraw entry point. It sets the rotation first, so
// every caller (taps, price polls, chart fetches, Serial commands)
// gets the right orientation: Auth and the price screen are always
// portrait, the chart goes landscape only while `landscape` is set.
void drawAll() {
  // Asleep: the veil is the whole screen — nothing else draws.
  if (screenAsleep) { nBtns = 0; drawSleepVeil(); return; }
  // Rebuild the display candles FIRST: in candle mode the stat tiles
  // (drawStatGrid / drawPriceOnlyStats / drawLandscapeAll) and the
  // chart axis (drawChartBody's lo/hi) read chartMin()/chartMax(),
  // which scan dispCand — so dispCand must already reflect the
  // current series or the tiles/axis lag one draw behind a range
  // change (buildCandles used to run only inside drawChartBody,
  // after lo/hi were computed). buildCandles() is pure series math
  // (no TFT, no geometry), idempotent, and a no-op outside candle
  // mode or before the first fetch, so it is safe to call here.
  if (chartType == 1) buildCandles();
  if (appMode == MODE_AUTH) {
    setRotationIf(0);
    drawAuthAll();
    return;
  }
  if (appMode == MODE_CLOCK) {
    setRotationIf(0);
    drawClockAll();
    return;
  }
  if (appMode == MODE_QR) {
    setRotationIf(0);
    drawQRAll();
    return;
  }
  if (landscape) {
    setRotationIf(1);
    drawLandscapeAll();
    return;
  }
  setRotationIf(0);
  nBtns = 0;
  applyTheme();
  tft.fillScreen(C_BG);
  drawStatusBar(15, false);
  if (priceOnly) { drawPriceOnly(); return; }
  drawHeader();
  drawPrice();
  drawChangeRow();
  drawScrubRow();
  drawChartArea();
  drawTypeRow();
  drawCmpRow();
  drawRangeButtons();
  drawStatGrid();
  drawPageDots();
}

// Hit-test a tap against the buttons drawn by drawRangeButtons()
// (price screen) or drawAuthButtons() (Auth screen).
// Returns the button id, or -1. Also returns -2 for a tap inside
// the chart area (used to leave price-only mode) — price screen only.
int hitTest(int16_t x, int16_t y) {
  for (int i = 0; i < nBtns; i++) {
    if (x >= btns[i].x && x < btns[i].x + btns[i].w &&
        y >= btns[i].y && y < btns[i].y + btns[i].h)
      return btns[i].id;
  }
  if (appMode != MODE_PRICE) return -1;
  // Chart-area tap (scrub / no-op). Price-only no longer exits on
  // a tap — the prototype's way back is a swipe (see the hint).
  if (!priceOnly && x >= gCH_X && x < gCH_X + gCH_W &&
      y >= gCH_Y && y < gCH_Y + gCH_H) return -2;
  return -1;
}

// ==================================================================
// Auth — TOTP authenticator (RFC 6238), 6-digit codes, 30 s period
// ------------------------------------------------------------------
// The keychain is a personal authenticator: it shows time-based
// one-time passwords for the accounts stored in NVS. A code is
// only shown when the clock is synced (NTP); until then the screen
// says so and shows dashes, never a code presented as valid.
//
// SECURITY: the TOTP secrets live in the ESP32's flash (NVS).
// This chip has no secure element. Anyone who can read the flash
// can extract the secrets, so a stolen keychain means those 2FA
// accounts must be treated as compromised (revoke / re-enrol).
// For real use, enable ESP32 flash encryption — see README.
// The sketch still never holds a seed or a private key.
// ==================================================================

// Base32 (RFC 4648) decode: accepts upper/lowercase, ignores spaces
// and '=' padding. Returns bytes written, or -1 on bad input.
int b32decode(const char *in, uint8_t *out, size_t outCap) {
  int bits = 0;
  uint32_t acc = 0;
  size_t n = 0;
  for (const char *p = in; *p; p++) {
    char c = *p;
    if (c == ' ' || c == '\t' || c == '=') continue;
    int v;
    if (c >= 'A' && c <= 'Z') v = c - 'A';
    else if (c >= 'a' && c <= 'z') v = c - 'a';
    else if (c >= '2' && c <= '7') v = c - '2' + 26;
    else return -1;
    acc = (acc << 5) | (uint32_t)v;
    bits += 5;
    if (bits >= 8) {
      bits -= 8;
      if (n >= outCap) return -1;
      out[n++] = (uint8_t)(acc >> bits);
      acc &= (bits > 0) ? ((1u << bits) - 1) : 0;
    }
  }
  // Leftover bits are padding and must be zero in a well-formed
  // base32 string (length 2, 4, 5, 7 or 8 mod 8 — never 1, 3, 6).
  if (bits > 0 && acc != 0) return -1;
  return (int)n;
}

// Validate a base32 secret. Returns the decoded byte count, or -1.
// Requires only A-Z / 2-7 (any case, spaces and '=' ignored), a
// valid base32 length, and at least 10 decoded bytes (80 bits).
int b32valid(const char *s) {
  size_t len = 0;
  for (const char *p = s; *p; p++) {
    char c = *p;
    if (c == ' ' || c == '\t' || c == '=') continue;
    if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
          (c >= '2' && c <= '7'))) return -1;
    len++;
  }
  if (len == 0) return -1;
  size_t m = len % 8;
  if (m == 1 || m == 3 || m == 6) return -1;
  uint8_t buf[48];
  int n = b32decode(s, buf, sizeof(buf));
  if (n < 10) return -1;
  return n;
}

// Compute the 6-digit TOTP for a base32 secret at a unix time.
// counter = floor(time / 30); HMAC-SHA1(secret, counter as 8-byte
// big-endian); dynamic truncation; mod 1,000,000, zero-padded.
// Returns true and fills `out` ("123456") on success.
// Verified against the RFC 6238 test vectors (see README).
bool totpCode(const char *b32secret, time_t t, char *out) {
  uint8_t key[48];
  int klen = b32decode(b32secret, key, sizeof(key));
  if (klen <= 0) return false;
  uint64_t counter = (uint64_t)t / 30;
  uint8_t msg[8];
  for (int i = 7; i >= 0; i--) { msg[i] = (uint8_t)(counter & 0xFF); counter >>= 8; }
  uint8_t hash[20];
  mbedtls_md_context_t ctx;
  mbedtls_md_init(&ctx);
  const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA1);
  bool ok = false;
  if (info && mbedtls_md_setup(&ctx, info, 1) == 0 &&
      mbedtls_md_hmac_starts(&ctx, key, (size_t)klen) == 0 &&
      mbedtls_md_hmac_update(&ctx, msg, sizeof(msg)) == 0 &&
      mbedtls_md_hmac_finish(&ctx, hash) == 0) {
    int off = hash[19] & 0x0F;
    uint32_t v = ((uint32_t)(hash[off] & 0x7F) << 24) |
                 ((uint32_t)hash[off + 1] << 16) |
                 ((uint32_t)hash[off + 2] << 8) |
                 ((uint32_t)hash[off + 3]);
    v %= 1000000;
    snprintf(out, 7, "%06lu", (unsigned long)v);
    ok = true;
  }
  mbedtls_md_free(&ctx);
  return ok;
}

// Current 30 s TOTP window, or 0 when the clock is not synced yet.
uint32_t totpWindow() {
  if (!timeOk) return 0;
  time_t now = time(nullptr);
  if (now < 1700000000L) return 0;
  return (uint32_t)(now / 30);
}

// Recompute the shown codes for ALL accounts + the current window
// (the list view shows every code at once). Returns true when at
// least one valid code is showing. authCode mirrors the selected
// account's code, as before.
bool authRefresh() {
  for (int i = 0; i < MAXAUTH; i++) authCodes[i][0] = 0;
  if (nAuth == 0 || authIdx < 0 || authIdx >= nAuth) {
    authCode[0] = 0; authWindow = 0; return false;
  }
  if (!timeOk) { authCode[0] = 0; authWindow = 0; return false; }
  time_t now = time(nullptr);
  authWindow = (uint32_t)(now / 30);
  bool ok = false;
  for (int i = 0; i < nAuth; i++) {
    if (totpCode(authAccts[i].secret, now, authCodes[i])) ok = true;
    else authCodes[i][0] = 0;
  }
  strncpy(authCode, authCodes[authIdx], sizeof(authCode) - 1);
  authCode[sizeof(authCode) - 1] = 0;
  return ok;
}

// Is the shown account the shipped demo (public RFC 6238 test secret)?
bool authIsDemo() {
  if (nAuth == 0 || authIdx < 0 || authIdx >= nAuth) return false;
  return strcmp(authAccts[authIdx].secret, AUTH_DEMO_SECRET) == 0;
}

// --- Auth screen layout (170x320) ---
// List view (R5): title 24, timer 44, bar 58, list rows 68-200
// (up to 4 rows, 30 px + 4 px gap), enlarged code box 204-248,
// nav row 258-282, hint 292-313. The old one-account pager
// (Prev/Next buttons) is gone — the list is the primary view now;
// tapping a row selects it for the enlarged box. The numbers above
// are the 4-account geometry; short lists are centred (see
// authShift), so the full layout is pixel-identical.
#define AU_TITLE_Y 20
#define AU_TIMER_Y 36
#define AU_BAR_Y   48
#define AU_BAR_H   4
#define AU_LIST_Y  56
#define AU_ROW_H   44
#define AU_ROW_GAP 5
#define AU_CODE_H  38

// Short lists (Finding 6): with 1 account ~100 px of dead black sat
// between the list and the code box. The block (list + box + nav +
// hint) is therefore compacted to its content height and centred in
// the space the full layout occupies: the shift is (4-n)*34/2, zero
// for 4 accounts. The timer/bar above the list and the dots below
// the hint stay fixed.
// Pass 5 finding 11: the centred 1-account block was still ~40%
// empty black, split above and below it. Short lists now also grow
// the code box (+10 px per missing account: 74 px for 1 account)
// and the shift accounts for it, so the dead space shrinks and
// splits evenly — and the taller box carries a "Codes refresh every
// 30 s" line under the code (see drawAuthCodeText).
static int16_t authCodeH() {
  int n = nAuth > 0 ? nAuth : 1;
  return AU_CODE_H + (n < 4 ? (4 - n) * 10 : 0);
}
static int16_t authShift() {
  int n = nAuth > 0 ? nAuth : 1;
  return (int16_t)(((4 - n) * (AU_ROW_H + AU_ROW_GAP) -
                    (authCodeH() - AU_CODE_H)) / 2);
}
static int16_t authListY() { return AU_LIST_Y + authShift(); }
static int16_t authCodeY() {
  int n = nAuth > 0 ? nAuth : 1;
  return authListY() + n * AU_ROW_H + (n - 1) * AU_ROW_GAP + 4;
}
static int16_t authHintY() { return authCodeY() + authCodeH() + 6; }

// Six dots for a hidden code (the MonoB13/19 vlw charsets are
// digits-only, so a "••• •••" string would render blank — the dots
// are drawn as filled circles instead). x = left edge of the first
// dot, y = vertical centre.
void drawHiddenDots(int16_t x, int16_t y, int16_t r, int16_t step,
                    int16_t gap) {
  for (int i = 0; i < 6; i++) {
    int16_t dx = x + i * step + (i >= 3 ? gap : 0);
    tft.fillCircle(dx, y, r, C_TEXT);
  }
}

// The 6-digit codes, in two places: each list row (right side) and
// the enlarged code box below. Shows dashes when there is no
// account or no time sync, so a stale/wrong code is never
// presented; shows six dots when codes are hidden (see
// drawHiddenDots). Only the code areas are redrawn (no full-screen
// flicker) — drawAuthAll draws the rows and the box, this fills the
// codes in. Called on the 30 s rollover by loop().
void drawAuthCodeText() {
  for (int i = 0; i < nAuth; i++) {
    int16_t ry = authListY() + i * (AU_ROW_H + AU_ROW_GAP);
    tft.fillRect(90, ry + 8, 66, AU_ROW_H - 16, C_SURFACE);
    if (authHideCodes) {
      drawHiddenDots(112, ry + AU_ROW_H / 2, 2, 7, 11);
    } else {
      char spaced[8];
      if (timeOk && authCodes[i][0]) fmtCodeSpaced(authCodes[i], spaced, sizeof(spaced));
      else snprintf(spaced, sizeof(spaced), "--- ---");
      setF(F_CODE13, 2);
      tft.setTextColor(C_TEXT, C_SURFACE);
      int16_t w = tft.textWidth(spaced);
      tft.setCursor(155 - w, ry + (AU_ROW_H - 13) / 2);
      tft.print(spaced);
    }
  }
  // enlarged code box (Mono bold 19px, cyan). On short lists the box
  // is taller (see authCodeH) — the code is centred in it, and a
  // "Codes refresh every 30 s" line fills the extra room (Pass 5
  // finding 11). The detail is drawn here, with the code, so the
  // 30 s rollover redraw (which calls this, not drawAuthAll) keeps it.
  int16_t codeShift = (authCodeH() - AU_CODE_H) / 2;
  tft.fillRect(CX0 + 8, authCodeY() + 16 + codeShift, 140, 22, C_SURFACE);
  if (authHideCodes) {
    drawHiddenDots(50, authCodeY() + 25 + codeShift, 3, 10, 16);
  } else {
    char spaced[8];
    if (nAuth > 0 && timeOk && authCode[0]) fmtCodeSpaced(authCode, spaced, sizeof(spaced));
    else snprintf(spaced, sizeof(spaced), "--- ---");
    setF(F_CODE19, 2);
    tft.setTextColor(C_CYAN, C_SURFACE);
    tft.setCursor(16, authCodeY() + 16 + codeShift);
    tft.print(spaced);
  }
  if (codeShift > 0) {
    setF(F_MONO7, 2);
    tft.setTextColor(C_MUTED, C_SURFACE);
    tft.setCursor(16, authCodeY() + 16 + codeShift + 26);
    tft.print("Codes refresh every 30 s");
  }
}

// Seconds left in this 30 s window + a thin progress bar.
void drawAuthCountdown() {
  tft.fillRect(0, AU_TIMER_Y - 2, SW, 14, C_BG);
  char num[8];
  int left = 0;
  if (!timeOk) {
    snprintf(num, sizeof(num), "--s");
  } else {
    time_t now = time(nullptr);
    left = 30 - (int)(now % 30);
    if (left <= 0) left = 30;
    if (left > 30) left = 30;
    snprintf(num, sizeof(num), "%ds", left);
  }
  setF(F_MONO6, 1);
  tft.setTextColor(C_MUTED, C_BG);
  tft.setCursor(8, AU_TIMER_Y);
  tft.print("NEW CODES IN");
  setF(F_MONO8B, 2);
  tft.setTextColor(C_CYAN, C_BG);
  int16_t nw = tft.textWidth(num);
  tft.setCursor(CX1 - nw, AU_TIMER_Y - 1);
  tft.print(num);
  int16_t bx = 8, bw = SW - 16;
  fillPillSolid(bx, AU_BAR_Y, bw, AU_BAR_H, 2, C_BARBG, C_BG);
  int frac = timeOk ? (left * bw / 30) : 0;
  if (frac > 0) fillPillSolid(bx, AU_BAR_Y, frac, AU_BAR_H, 2, C_CYAN, C_BARBG);
}

// Nav row: back to the Price screen + the other two apps
// (Clock, QR). (nBtns is reset by drawAuthAll, not here — this only
// appends.) The old < Prev / Next > pager is gone with the list view.
void drawAuthButtons() {
  // Chart / Clock / QR / Price shortcut pills were dropped (Phase 2).
  // Swipe and the page dots are the way off this screen. The Price
  // button's old "goes to the chart" nit is gone with the button.
}

void drawAuthAll() {
  nBtns = 0;
  applyTheme();
  tft.fillScreen(C_BG);
  drawStatusBar(15, false);
  // title + TOTP tag + HIDE CODES / SHOW CODES (prototype wording)
  setF(F_PILL6, 1);
  tft.setTextColor(C_TEXT, C_BG);
  tft.setCursor(8, AU_TITLE_Y);
  tft.print("AUTHENTICATOR");
  int16_t tw = tft.textWidth("AUTHENTICATOR");
  tft.setTextColor(C_CYAN, C_BG);
  tft.setCursor(8 + tw + 5, AU_TITLE_Y);
  tft.print("TOTP");
  // Inter vlw has no space glyph, so the two words are drawn with a
  // manual gap. InterB7's 'S' also sits on its advance, unlike the
  // 6 px cut which left a hole before the last letter.
  setF(F_PILL7, 1);
  const char *hideW1 = authHideCodes ? "SHOW" : "HIDE";
  const char *hideW2 = "CODES";
  int16_t gap = 3;
  int16_t hideW = tft.textWidth(hideW1) + gap + tft.textWidth(hideW2) + 16;
  int16_t hideX = CX1 - hideW;
  int16_t hideY = AU_TITLE_Y - 2;
  uint16_t hideBg = authHideCodes ? C_BTN_ON : C_BTN;
  uint16_t hideFg = authHideCodes ? C_ONTXT : C_BTN_TXT;
  if (authHideCodes) fillPillSolid(hideX, hideY, hideW, 16, 8, C_BTN_ON, C_BG);
  else               fillPill(hideX, hideY, hideW, 16, 8, C_BTN, C_BORD, C_BG);
  tft.setTextColor(hideFg, hideBg);
  tft.setTextDatum(TL_DATUM);
  int16_t tx = hideX + 8;
  tft.setCursor(tx, hideY + 4);
  tft.print(hideW1);
  tx += tft.textWidth(hideW1) + gap;
  tft.setCursor(tx, hideY + 4);
  tft.print(hideW2);
  btns[nBtns++] = {hideX, hideY, hideW, 16, 53};
  uint16_t avBg[4] = {C_CYAN, C_PURP, C_AMBER, C_GREEN};
  uint16_t avTx[4] = {C_ONTXT, 0x18C5, 0x28E0, 0x0162};
  if (nAuth > 0) {
    for (int i = 0; i < nAuth; i++) {
      int16_t ry = authListY() + i * (AU_ROW_H + AU_ROW_GAP);
      const char *label = authAccts[i].label;
      bool sel = (i == authIdx);
      fillPill(8, ry, 154, AU_ROW_H, 7, C_SURFACE, sel ? C_CYAN : C_TILEBD, C_BG);
      int ai = i % 4;
      tft.fillCircle(24, ry + AU_ROW_H / 2, 12, avBg[ai]);
      setF(F_LABEL9, 4);
      tft.setTextColor(avTx[ai], avBg[ai]);
      tft.setTextDatum(MC_DATUM);
      char init[2] = {label[0] ? label[0] : '?', 0};
      tft.drawString(init, 24, ry + AU_ROW_H / 2);
      tft.setTextDatum(TL_DATUM);
      char lab[21];
      snprintf(lab, sizeof(lab), "%s", label);
      setF(F_LABEL9, 4);
      while (tft.textWidth(lab) > 58 && strlen(lab) > 1)
        lab[strlen(lab) - 1] = 0;
      tft.setTextColor(C_TEXT, C_SURFACE);
      // Issuer only: firmware accounts store a label, not a separate
      // account subline, so we do not invent "personal login". The
      // row is 44 px like the prototype; the issuer is vertically
      // centred.
      tft.setCursor(42, ry + (AU_ROW_H - 9) / 2);
      tft.print(lab);
      btns[nBtns++] = {8, ry, 154, AU_ROW_H, (int16_t)(60 + i)};
    }
  } else {
    fillPill(8, authListY(), 154, AU_ROW_H, 7, C_SURFACE, C_TILEBD, C_BG);
    setF(F_LABEL9, 4);
    tft.setTextColor(C_TEXT, C_SURFACE);
    tft.setCursor(42, authListY() + (AU_ROW_H - 9) / 2);
    tft.print("No accounts");
  }
  // enlarged code box
  fillPill(8, authCodeY(), 154, authCodeH(), 7, C_SURFACE, C_TILEBD, C_BG);
  setF(F_MONO6, 1);
  tft.setTextColor(C_PILL2, C_SURFACE);
  tft.setCursor(16, authCodeY() + 6);
  if (authHideCodes) {
    tft.print("CODES HIDDEN - TAP SHOW CODES");
  } else if (nAuth > 0) {
    // "{NAME} · TAP AN ACCOUNT TO ENLARGE"
    const char mid[] = " \xC2\xB7 ";
    char cap[48];
    char name[16];
    snprintf(name, sizeof(name), "%s", authAccts[authIdx].label);
    // Uppercase for the prototype's voice; truncate to fit.
    for (char *q = name; *q; q++) if (*q >= 'a' && *q <= 'z') *q -= 32;
    snprintf(cap, sizeof(cap), "%s%sTAP AN ACCOUNT TO ENLARGE", name, mid);
    while (tft.textWidth(cap) > 138 && strlen(name) > 3) {
      name[strlen(name) - 1] = 0;
      snprintf(cap, sizeof(cap), "%s%sTAP AN ACCOUNT TO ENLARGE", name, mid);
    }
    tft.print(cap);
  } else {
    tft.print("TAP AN ACCOUNT TO ENLARGE");
  }
  drawAuthCodeText();
  drawAuthCountdown();
  drawAuthButtons();
  setF(F_MONO6, 1);
  if (!timeOk) {
    tft.setTextColor(C_RED, C_BG);
    tft.setCursor(8, authHintY());
    tft.print("waiting for time sync");
    tft.setCursor(8, authHintY() + 10);
    tft.print("codes may be wrong");
  } else if (authIsDemo()) {
    tft.setTextColor(C_ORANGE, C_BG);
    tft.setCursor(8, authHintY());
    tft.print("DEMO CODES - SIMULATION ONLY");
  } else {
    tft.setTextColor(C_MUTED, C_BG);
    tft.setCursor(8, authHintY());
    tft.print("Add via USB: ADD <label> <secret>");
  }
  drawPageDots();
}


// --- Serial provisioning (USB) ---
// Commands (one per line, case-insensitive):
//   HELP                        — this list
//   ADD <label> <base32secret>  — add an account (max 4)
//   LIST                        — list accounts (secret: first 4 chars only)
//   DEL <index>                 — delete one account
//   CLEAR                       — delete all accounts
// The full TOTP secret is NEVER printed to Serial.
void serialHelp() {
  Serial.println("Auth (TOTP) over USB Serial:");
  Serial.println("  ADD <label> <base32secret>  add an account (max 4)");
  Serial.println("  LIST                        list accounts");
  Serial.println("  DEL <index>                 delete one account");
  Serial.println("  CLEAR                       delete all accounts");
  Serial.println("  HELP                        this list");
}

void serialList() {
  if (nAuth == 0) { Serial.println("No accounts"); return; }
  for (int i = 0; i < nAuth; i++) {
    char first4[5];
    strncpy(first4, authAccts[i].secret, 4);
    first4[4] = 0;
    Serial.print(i); Serial.print("  ");
    Serial.print(authAccts[i].label);
    Serial.print("  "); Serial.print(first4); Serial.print("...");
    if (strcmp(authAccts[i].secret, AUTH_DEMO_SECRET) == 0)
      Serial.print("  (DEMO)");
    Serial.println();
  }
}

char serialBuf[128];
int serialLen = 0;

void serialCommand(char *line) {
  while (*line == ' ' || *line == '\t') line++;
  if (*line == 0) return;
  char *cmd = strtok(line, " \t");
  if (!cmd) return;
  if (strcasecmp(cmd, "HELP") == 0) { serialHelp(); return; }
  if (strcasecmp(cmd, "LIST") == 0) { serialList(); return; }
  if (strcasecmp(cmd, "CLEAR") == 0) {
    nAuth = 0; authIdx = 0; authWindow = 0; authCode[0] = 0;
    savePrefs();
    Serial.println("OK all accounts deleted");
    drawAll();
    return;
  }
  if (strcasecmp(cmd, "ADD") == 0) {
    char *label = strtok(nullptr, " \t");
    char *secret = strtok(nullptr, " \t");
    if (!label || !secret) {
      Serial.println("ERR usage: ADD <label> <base32secret>");
      return;
    }
    if (strlen(label) > 20) { Serial.println("ERR label too long (max 20)"); return; }
    if (strlen(secret) > 64) { Serial.println("ERR secret too long (max 64)"); return; }
    if (nAuth >= MAXAUTH) { Serial.println("ERR account list full (max 4)"); return; }
    if (b32valid(secret) < 0) {
      Serial.println("ERR invalid base32 secret (A-Z, 2-7 only)");
      return;
    }
    strncpy(authAccts[nAuth].label, label, AUTH_LABEL_LEN - 1);
    authAccts[nAuth].label[AUTH_LABEL_LEN - 1] = 0;
    strncpy(authAccts[nAuth].secret, secret, AUTH_SEC_LEN - 1);
    authAccts[nAuth].secret[AUTH_SEC_LEN - 1] = 0;
    authIdx = nAuth;
    nAuth++;
    savePrefs();
    authRefresh();
    Serial.print("OK added "); Serial.println(label);
    drawAll();
    return;
  }
  if (strcasecmp(cmd, "DEL") == 0) {
    char *idxs = strtok(nullptr, " \t");
    if (!idxs) { Serial.println("ERR usage: DEL <index>"); return; }
    // atoi("abc") is 0 — a non-numeric index would silently delete
    // account 0. Require all digits.
    for (const char *p = idxs; *p; p++) {
      if (*p < '0' || *p > '9') {
        Serial.println("ERR index must be a number");
        return;
      }
    }
    int idx = atoi(idxs);
    if (idx < 0 || idx >= nAuth) { Serial.println("ERR index out of range"); return; }
    Serial.print("OK deleted "); Serial.println(authAccts[idx].label);
    for (int i = idx; i < nAuth - 1; i++) authAccts[i] = authAccts[i + 1];
    nAuth--;
    if (authIdx >= nAuth) authIdx = nAuth > 0 ? nAuth - 1 : 0;
    authWindow = 0; authCode[0] = 0;
    savePrefs();
    authRefresh();
    drawAll();
    return;
  }
  Serial.println("ERR unknown command (HELP for a list)");
}

void handleSerial() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (serialLen > 0) {
        serialBuf[serialLen] = 0;
        serialCommand(serialBuf);
        serialLen = 0;
      }
    } else if (serialLen < (int)sizeof(serialBuf) - 1) {
      serialBuf[serialLen++] = c;
    }
  }
}

// --- TLS trust roots (R7) ---
// The server certificate on every HTTPS fetch is verified against
// this bundle (WiFiClientSecure::setCACert in httpsGet) instead of
// the old setInsecure(). A fetch whose chain does not land on one
// of these roots fails CLOSED: the last-good price stays on screen
// and the fetch is retried later — a spoofed price is never drawn.
//   ISRG Root X1 ............ Let's Encrypt: mempool.space, and
//                             paperstreetbtc.com (GitHub Pages uses
//                             Let's Encrypt for custom domains).
//   DigiCert Global G2/G3 ... Coinbase (api.coinbase.com,
//                             api.exchange.coinbase.com).
//   DigiCert TLS G5 RSA/ECC . DigiCert's default issuance root
//                             since 12 Nov 2026 — new Coinbase
//                             certificates chain here, not to G2/G3.
//   GTS Root R1/R4 .......... Google Trust Services: CoinGecko
//                             sits behind Cloudflare, whose current
//                             edge certificates chain to GTS.
// WHY A BUNDLE, NOT JUST ISRG X1: the gap analysis names ISRG
// Root X1, but only the Let's Encrypt hosts chain to it. An
// ISRG-only pin would have broken the two price sources
// (Coinbase = DigiCert, CoinGecko = Cloudflare/GTS) on hardware.
// The per-host chains above are the best public information
// available here — they are NOT proven against the live hosts,
// and hosts re-issue. TLS-VERIFICATION HARDWARE-UNVERIFIED:
// before trusting this on the board, confirm each host's chain
// lands on one of these roots (openssl s_client -connect) and
// add that host's root if it does not. A root that expires or
// a host that moves roots breaks that host's fetch (fail-closed,
// never fail-open). The sim cannot verify TLS at all — its
// WiFiClientSecure stub no-ops setCACert (see sim include/).
// Fingerprints (SHA-256, verified against the system store when
// this bundle was baked in):
//   ISRG Root X1 (Let's Encrypt): 96:BC:EC:06:26:49:76:F3:74:60:77:9A:CF:28:C5:A7:CF:E8:A3:C0:AA:E1:1A:8F:FC:EE:05:C0:BD:DF:08:C6
//   DigiCert Global Root G2: CB:3C:CB:B7:60:31:E5:E0:13:8F:8D:D3:9A:23:F9:DE:47:FF:C3:5E:43:C1:14:4C:EA:27:D4:6A:5A:B1:CB:5F
//   DigiCert Global Root G3: 31:AD:66:48:F8:10:41:38:C7:38:F3:9E:A4:32:01:33:39:3E:3A:18:CC:02:29:6E:F9:7C:2A:C9:EF:67:31:D0
//   DigiCert TLS RSA4096 Root G5: 37:1A:00:DC:05:33:B3:72:1A:7E:EB:40:E8:41:9E:70:79:9D:2B:0A:0F:2C:1D:80:69:31:65:F7:CE:C4:AD:75
//   DigiCert TLS ECC P384 Root G5: 01:8E:13:F0:77:25:32:CF:80:9B:D1:B1:72:81:86:72:83:FC:48:C6:E1:3B:E9:C6:98:12:85:4A:49:0C:1B:05
//   Google Trust Services Root R1: D9:47:43:2A:BD:E7:B7:FA:90:FC:2E:6B:59:10:1B:12:80:E0:E1:C7:E4:E4:0F:A3:C6:88:7F:FF:57:A7:F4:CF
//   Google Trust Services Root R4: 34:9D:FA:40:58:C5:E2:63:12:3B:39:8A:E7:95:57:3C:4E:13:13:C8:3F:E6:8F:93:55:6C:D5:E8:03:1B:3C:7D
// Regenerate from /etc/ssl/certs/<name>.pem if a root rotates.
static const char ROOT_CA_BUNDLE[] =
  "-----BEGIN CERTIFICATE-----\n"
  "MIIFazCCA1OgAwIBAgIRAIIQz7DSQONZRGPgu2OCiwAwDQYJKoZIhvcNAQELBQAw\n"
  "TzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2Vh\n"
  "cmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwHhcNMTUwNjA0MTEwNDM4\n"
  "WhcNMzUwNjA0MTEwNDM4WjBPMQswCQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJu\n"
  "ZXQgU2VjdXJpdHkgUmVzZWFyY2ggR3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBY\n"
  "MTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAK3oJHP0FDfzm54rVygc\n"
  "h77ct984kIxuPOZXoHj3dcKi/vVqbvYATyjb3miGbESTtrFj/RQSa78f0uoxmyF+\n"
  "0TM8ukj13Xnfs7j/EvEhmkvBioZxaUpmZmyPfjxwv60pIgbz5MDmgK7iS4+3mX6U\n"
  "A5/TR5d8mUgjU+g4rk8Kb4Mu0UlXjIB0ttov0DiNewNwIRt18jA8+o+u3dpjq+sW\n"
  "T8KOEUt+zwvo/7V3LvSye0rgTBIlDHCNAymg4VMk7BPZ7hm/ELNKjD+Jo2FR3qyH\n"
  "B5T0Y3HsLuJvW5iB4YlcNHlsdu87kGJ55tukmi8mxdAQ4Q7e2RCOFvu396j3x+UC\n"
  "B5iPNgiV5+I3lg02dZ77DnKxHZu8A/lJBdiB3QW0KtZB6awBdpUKD9jf1b0SHzUv\n"
  "KBds0pjBqAlkd25HN7rOrFleaJ1/ctaJxQZBKT5ZPt0m9STJEadao0xAH0ahmbWn\n"
  "OlFuhjuefXKnEgV4We0+UXgVCwOPjdAvBbI+e0ocS3MFEvzG6uBQE3xDk3SzynTn\n"
  "jh8BCNAw1FtxNrQHusEwMFxIt4I7mKZ9YIqioymCzLq9gwQbooMDQaHWBfEbwrbw\n"
  "qHyGO0aoSCqI3Haadr8faqU9GY/rOPNk3sgrDQoo//fb4hVC1CLQJ13hef4Y53CI\n"
  "rU7m2Ys6xt0nUW7/vGT1M0NPAgMBAAGjQjBAMA4GA1UdDwEB/wQEAwIBBjAPBgNV\n"
  "HRMBAf8EBTADAQH/MB0GA1UdDgQWBBR5tFnme7bl5AFzgAiIyBpY9umbbjANBgkq\n"
  "hkiG9w0BAQsFAAOCAgEAVR9YqbyyqFDQDLHYGmkgJykIrGF1XIpu+ILlaS/V9lZL\n"
  "ubhzEFnTIZd+50xx+7LSYK05qAvqFyFWhfFQDlnrzuBZ6brJFe+GnY+EgPbk6ZGQ\n"
  "3BebYhtF8GaV0nxvwuo77x/Py9auJ/GpsMiu/X1+mvoiBOv/2X/qkSsisRcOj/KK\n"
  "NFtY2PwByVS5uCbMiogziUwthDyC3+6WVwW6LLv3xLfHTjuCvjHIInNzktHCgKQ5\n"
  "ORAzI4JMPJ+GslWYHb4phowim57iaztXOoJwTdwJx4nLCgdNbOhdjsnvzqvHu7Ur\n"
  "TkXWStAmzOVyyghqpZXjFaH3pO3JLF+l+/+sKAIuvtd7u+Nxe5AW0wdeRlN8NwdC\n"
  "jNPElpzVmbUq4JUagEiuTDkHzsxHpFKVK7q4+63SM1N95R1NbdWhscdCb+ZAJzVc\n"
  "oyi3B43njTOQ5yOf+1CceWxG1bQVs5ZufpsMljq4Ui0/1lvh+wjChP4kqKOJ2qxq\n"
  "4RgqsahDYVvTH9w7jXbyLeiNdd8XM2w9U/t7y0Ff/9yi0GE44Za4rF2LN9d11TPA\n"
  "mRGunUHBcnWEvgJBQl9nJEiU0Zsnvgc/ubhPgXRR4Xq37Z0j4r7g1SgEEzwxA57d\n"
  "emyPxgcYxn/eR44/KJ4EBs+lVDR3veyJm+kXQ99b21/+jh5Xos1AnX5iItreGCc=\n"
  "-----END CERTIFICATE-----\n"
  "-----BEGIN CERTIFICATE-----\n"
  "MIIDjjCCAnagAwIBAgIQAzrx5qcRqaC7KGSxHQn65TANBgkqhkiG9w0BAQsFADBh\n"
  "MQswCQYDVQQGEwJVUzEVMBMGA1UEChMMRGlnaUNlcnQgSW5jMRkwFwYDVQQLExB3\n"
  "d3cuZGlnaWNlcnQuY29tMSAwHgYDVQQDExdEaWdpQ2VydCBHbG9iYWwgUm9vdCBH\n"
  "MjAeFw0xMzA4MDExMjAwMDBaFw0zODAxMTUxMjAwMDBaMGExCzAJBgNVBAYTAlVT\n"
  "MRUwEwYDVQQKEwxEaWdpQ2VydCBJbmMxGTAXBgNVBAsTEHd3dy5kaWdpY2VydC5j\n"
  "b20xIDAeBgNVBAMTF0RpZ2lDZXJ0IEdsb2JhbCBSb290IEcyMIIBIjANBgkqhkiG\n"
  "9w0BAQEFAAOCAQ8AMIIBCgKCAQEAuzfNNNx7a8myaJCtSnX/RrohCgiN9RlUyfuI\n"
  "2/Ou8jqJkTx65qsGGmvPrC3oXgkkRLpimn7Wo6h+4FR1IAWsULecYxpsMNzaHxmx\n"
  "1x7e/dfgy5SDN67sH0NO3Xss0r0upS/kqbitOtSZpLYl6ZtrAGCSYP9PIUkY92eQ\n"
  "q2EGnI/yuum06ZIya7XzV+hdG82MHauVBJVJ8zUtluNJbd134/tJS7SsVQepj5Wz\n"
  "tCO7TG1F8PapspUwtP1MVYwnSlcUfIKdzXOS0xZKBgyMUNGPHgm+F6HmIcr9g+UQ\n"
  "vIOlCsRnKPZzFBQ9RnbDhxSJITRNrw9FDKZJobq7nMWxM4MphQIDAQABo0IwQDAP\n"
  "BgNVHRMBAf8EBTADAQH/MA4GA1UdDwEB/wQEAwIBhjAdBgNVHQ4EFgQUTiJUIBiV\n"
  "5uNu5g/6+rkS7QYXjzkwDQYJKoZIhvcNAQELBQADggEBAGBnKJRvDkhj6zHd6mcY\n"
  "1Yl9PMWLSn/pvtsrF9+wX3N3KjITOYFnQoQj8kVnNeyIv/iPsGEMNKSuIEyExtv4\n"
  "NeF22d+mQrvHRAiGfzZ0JFrabA0UWTW98kndth/Jsw1HKj2ZL7tcu7XUIOGZX1NG\n"
  "Fdtom/DzMNU+MeKNhJ7jitralj41E6Vf8PlwUHBHQRFXGU7Aj64GxJUTFy8bJZ91\n"
  "8rGOmaFvE7FBcf6IKshPECBV1/MUReXgRPTqh5Uykw7+U0b6LJ3/iyK5S9kJRaTe\n"
  "pLiaWN0bfVKfjllDiIGknibVb63dDcY3fe0Dkhvld1927jyNxF1WW6LZZm6zNTfl\n"
  "MrY=\n"
  "-----END CERTIFICATE-----\n"
  "-----BEGIN CERTIFICATE-----\n"
  "MIICPzCCAcWgAwIBAgIQBVVWvPJepDU1w6QP1atFcjAKBggqhkjOPQQDAzBhMQsw\n"
  "CQYDVQQGEwJVUzEVMBMGA1UEChMMRGlnaUNlcnQgSW5jMRkwFwYDVQQLExB3d3cu\n"
  "ZGlnaWNlcnQuY29tMSAwHgYDVQQDExdEaWdpQ2VydCBHbG9iYWwgUm9vdCBHMzAe\n"
  "Fw0xMzA4MDExMjAwMDBaFw0zODAxMTUxMjAwMDBaMGExCzAJBgNVBAYTAlVTMRUw\n"
  "EwYDVQQKEwxEaWdpQ2VydCBJbmMxGTAXBgNVBAsTEHd3dy5kaWdpY2VydC5jb20x\n"
  "IDAeBgNVBAMTF0RpZ2lDZXJ0IEdsb2JhbCBSb290IEczMHYwEAYHKoZIzj0CAQYF\n"
  "K4EEACIDYgAE3afZu4q4C/sLfyHS8L6+c/MzXRq8NOrexpu80JX28MzQC7phW1FG\n"
  "fp4tn+6OYwwX7Adw9c+ELkCDnOg/QW07rdOkFFk2eJ0DQ+4QE2xy3q6Ip6FrtUPO\n"
  "Z9wj/wMco+I+o0IwQDAPBgNVHRMBAf8EBTADAQH/MA4GA1UdDwEB/wQEAwIBhjAd\n"
  "BgNVHQ4EFgQUs9tIpPmhxdiuNkHMEWNpYim8S8YwCgYIKoZIzj0EAwMDaAAwZQIx\n"
  "AK288mw/EkrRLTnDCgmXc/SINoyIJ7vmiI1Qhadj+Z4y3maTD/HMsQmP3Wyr+mt/\n"
  "oAIwOWZbwmSNuJ5Q3KjVSaLtx9zRSX8XAbjIho9OjIgrqJqpisXRAL34VOKa5Vt8\n"
  "sycX\n"
  "-----END CERTIFICATE-----\n"
  "-----BEGIN CERTIFICATE-----\n"
  "MIIFZjCCA06gAwIBAgIQCPm0eKj6ftpqMzeJ3nzPijANBgkqhkiG9w0BAQwFADBN\n"
  "MQswCQYDVQQGEwJVUzEXMBUGA1UEChMORGlnaUNlcnQsIEluYy4xJTAjBgNVBAMT\n"
  "HERpZ2lDZXJ0IFRMUyBSU0E0MDk2IFJvb3QgRzUwHhcNMjEwMTE1MDAwMDAwWhcN\n"
  "NDYwMTE0MjM1OTU5WjBNMQswCQYDVQQGEwJVUzEXMBUGA1UEChMORGlnaUNlcnQs\n"
  "IEluYy4xJTAjBgNVBAMTHERpZ2lDZXJ0IFRMUyBSU0E0MDk2IFJvb3QgRzUwggIi\n"
  "MA0GCSqGSIb3DQEBAQUAA4ICDwAwggIKAoICAQCz0PTJeRGd/fxmgefM1eS87IE+\n"
  "ajWOLrfn3q/5B03PMJ3qCQuZvWxX2hhKuHisOjmopkisLnLlvevxGs3npAOpPxG0\n"
  "2C+JFvuUAT27L/gTBaF4HI4o4EXgg/RZG5Wzrn4DReW+wkL+7vI8toUTmDKdFqgp\n"
  "wgscONyfMXdcvyej/Cestyu9dJsXLfKB2l2w4SMXPohKEiPQ6s+d3gMXsUJKoBZM\n"
  "pG2T6T867jp8nVid9E6P/DsjyG244gXazOvswzH016cpVIDPRFtMbzCe88zdH5RD\n"
  "nU1/cHAN1DrRN/BsnZvAFJNY781BOHW8EwOVfH/jXOnVDdXifBBiqmvwPXbzP6Po\n"
  "sMH976pXTayGpxi0KcEsDr9kvimM2AItzVwv8n/vFfQMFawKsPHTDU9qTXeXAaDx\n"
  "Zre3zu/O7Oyldcqs4+Fj97ihBMi8ez9dLRYiVu1ISf6nL3kwJZu6ay0/nTvEF+cd\n"
  "Lvvyz6b84xQslpghjLSR6Rlgg/IwKwZzUNWYOwbpx4oMYIwo+FKbbuH2TbsGJJvX\n"
  "KyY//SovcfXWJL5/MZ4PbeiPT02jP/816t9JXkGPhvnxd3lLG7SjXi/7RgLQZhNe\n"
  "XoVPzthwiHvOAbWWl9fNff2C+MIkwcoBOU+NosEUQB+cZtUMCUbW8tDRSHZWOkPL\n"
  "tgoRObqME2wGtZ7P6wIDAQABo0IwQDAdBgNVHQ4EFgQUUTMc7TZArxfTJc1paPKv\n"
  "TiM+s0EwDgYDVR0PAQH/BAQDAgGGMA8GA1UdEwEB/wQFMAMBAf8wDQYJKoZIhvcN\n"
  "AQEMBQADggIBAGCmr1tfV9qJ20tQqcQjNSH/0GEwhJG3PxDPJY7Jv0Y02cEhJhxw\n"
  "GXIeo8mH/qlDZJY6yFMECrZBu8RHANmfGBg7sg7zNOok992vIGCukihfNudd5N7H\n"
  "PNtQOa27PShNlnx2xlv0wdsUpasZYgcYQF+Xkdycx6u1UQ3maVNVzDl92sURVXLF\n"
  "O4uJ+DQtpBflF+aZfTCIITfNMBc9uPK8qHWgQ9w+iUuQrm0D4ByjoJYJu32jtyoQ\n"
  "REtGBzRj7TG5BO6jm5qu5jF49OokYTurWGT/u4cnYiWB39yhL/btp/96j1EuMPik\n"
  "AdKFOV8BmZZvWltwGUb+hmA+rYAQCd05JS9Yf7vSdPD3Rh9GOUrYU9DzLjtxpdRv\n"
  "/PNn5AeP3SYZ4Y1b+qOTEZvpyDrDVWiakuFSdjjo4bq9+0/V77PnSIMx8IIh47a+\n"
  "p6tv75/fTM8BuGJqIz3nCU2AG3swpMPdB380vqQmsvZB6Akd4yCYqjdP//fx4ilw\n"
  "MUc/dNAUFvohigLVigmUdy7yWSiLfFCSCmZ4OIN1xLVaqBHG5cGdZlXPU8Sv13WF\n"
  "qUITVuwhd4GTWgzqltlJyqEI8pc7bZsEGCREjnwB8twl2F6GmrE52/WRMmrRpnCK\n"
  "ovfepEWFJqgejF0pW8hL2JpqA15w8oVPbEtoL8pU9ozaMv7Da4M/OMZ+\n"
  "-----END CERTIFICATE-----\n"
  "-----BEGIN CERTIFICATE-----\n"
  "MIICGTCCAZ+gAwIBAgIQCeCTZaz32ci5PhwLBCou8zAKBggqhkjOPQQDAzBOMQsw\n"
  "CQYDVQQGEwJVUzEXMBUGA1UEChMORGlnaUNlcnQsIEluYy4xJjAkBgNVBAMTHURp\n"
  "Z2lDZXJ0IFRMUyBFQ0MgUDM4NCBSb290IEc1MB4XDTIxMDExNTAwMDAwMFoXDTQ2\n"
  "MDExNDIzNTk1OVowTjELMAkGA1UEBhMCVVMxFzAVBgNVBAoTDkRpZ2lDZXJ0LCBJ\n"
  "bmMuMSYwJAYDVQQDEx1EaWdpQ2VydCBUTFMgRUNDIFAzODQgUm9vdCBHNTB2MBAG\n"
  "ByqGSM49AgEGBSuBBAAiA2IABMFEoc8Rl1Ca3iOCNQfN0MsYndLxf3c1TzvdlHJS\n"
  "7cI7+Oz6e2tYIOyZrsn8aLN1udsJ7MgT9U7GCh1mMEy7H0cKPGEQQil8pQgO4CLp\n"
  "0zVozptjn4S1mU1YoI71VOeVyaNCMEAwHQYDVR0OBBYEFMFRRVBZqz7nLFr6ICIS\n"
  "B4CIfBFqMA4GA1UdDwEB/wQEAwIBhjAPBgNVHRMBAf8EBTADAQH/MAoGCCqGSM49\n"
  "BAMDA2gAMGUCMQCJao1H5+z8blUD2WdsJk6Dxv3J+ysTvLd6jLRl0mlpYxNjOyZQ\n"
  "LgGheQaRnUi/wr4CMEfDFXuxoJGZSZOoPHzoRgaLLPIxAJSdYsiJvRmEFOml+wG4\n"
  "DXZDjC5Ty3zfDBeWUA==\n"
  "-----END CERTIFICATE-----\n"
  "-----BEGIN CERTIFICATE-----\n"
  "MIIFVzCCAz+gAwIBAgINAgPlk28xsBNJiGuiFzANBgkqhkiG9w0BAQwFADBHMQsw\n"
  "CQYDVQQGEwJVUzEiMCAGA1UEChMZR29vZ2xlIFRydXN0IFNlcnZpY2VzIExMQzEU\n"
  "MBIGA1UEAxMLR1RTIFJvb3QgUjEwHhcNMTYwNjIyMDAwMDAwWhcNMzYwNjIyMDAw\n"
  "MDAwWjBHMQswCQYDVQQGEwJVUzEiMCAGA1UEChMZR29vZ2xlIFRydXN0IFNlcnZp\n"
  "Y2VzIExMQzEUMBIGA1UEAxMLR1RTIFJvb3QgUjEwggIiMA0GCSqGSIb3DQEBAQUA\n"
  "A4ICDwAwggIKAoICAQC2EQKLHuOhd5s73L+UPreVp0A8of2C+X0yBoJx9vaMf/vo\n"
  "27xqLpeXo4xL+Sv2sfnOhB2x+cWX3u+58qPpvBKJXqeqUqv4IyfLpLGcY9vXmX7w\n"
  "Cl7raKb0xlpHDU0QM+NOsROjyBhsS+z8CZDfnWQpJSMHobTSPS5g4M/SCYe7zUjw\n"
  "TcLCeoiKu7rPWRnWr4+wB7CeMfGCwcDfLqZtbBkOtdh+JhpFAz2weaSUKK0Pfybl\n"
  "qAj+lug8aJRT7oM6iCsVlgmy4HqMLnXWnOunVmSPlk9orj2XwoSPwLxAwAtcvfaH\n"
  "szVsrBhQf4TgTM2S0yDpM7xSma8ytSmzJSq0SPly4cpk9+aCEI3oncKKiPo4Zor8\n"
  "Y/kB+Xj9e1x3+naH+uzfsQ55lVe0vSbv1gHR6xYKu44LtcXFilWr06zqkUspzBmk\n"
  "MiVOKvFlRNACzqrOSbTqn3yDsEB750Orp2yjj32JgfpMpf/VjsPOS+C12LOORc92\n"
  "wO1AK/1TD7Cn1TsNsYqiA94xrcx36m97PtbfkSIS5r762DL8EGMUUXLeXdYWk70p\n"
  "aDPvOmbsB4om3xPXV2V4J95eSRQAogB/mqghtqmxlbCluQ0WEdrHbEg8QOB+DVrN\n"
  "VjzRlwW5y0vtOUucxD/SVRNuJLDWcfr0wbrM7Rv1/oFB2ACYPTrIrnqYNxgFlQID\n"
  "AQABo0IwQDAOBgNVHQ8BAf8EBAMCAYYwDwYDVR0TAQH/BAUwAwEB/zAdBgNVHQ4E\n"
  "FgQU5K8rJnEaK0gnhS9SZizv8IkTcT4wDQYJKoZIhvcNAQEMBQADggIBAJ+qQibb\n"
  "C5u+/x6Wki4+omVKapi6Ist9wTrYggoGxval3sBOh2Z5ofmmWJyq+bXmYOfg6LEe\n"
  "QkEzCzc9zolwFcq1JKjPa7XSQCGYzyI0zzvFIoTgxQ6KfF2I5DUkzps+GlQebtuy\n"
  "h6f88/qBVRRiClmpIgUxPoLW7ttXNLwzldMXG+gnoot7TiYaelpkttGsN/H9oPM4\n"
  "7HLwEXWdyzRSjeZ2axfG34arJ45JK3VmgRAhpuo+9K4l/3wV3s6MJT/KYnAK9y8J\n"
  "ZgfIPxz88NtFMN9iiMG1D53Dn0reWVlHxYciNuaCp+0KueIHoI17eko8cdLiA6Ef\n"
  "MgfdG+RCzgwARWGAtQsgWSl4vflVy2PFPEz0tv/bal8xa5meLMFrUKTX5hgUvYU/\n"
  "Z6tGn6D/Qqc6f1zLXbBwHSs09dR2CQzreExZBfMzQsNhFRAbd03OIozUhfJFfbdT\n"
  "6u9AWpQKXCBfTkBdYiJ23//OYb2MI3jSNwLgjt7RETeJ9r/tSQdirpLsQBqvFAnZ\n"
  "0E6yove+7u7Y/9waLd64NnHi/Hm3lCXRSHNboTXns5lndcEZOitHTtNCjv0xyBZm\n"
  "2tIMPNuzjsmhDYAPexZ3FL//2wmUspO8IFgV6dtxQ/PeEMMA3KgqlbbC1j+Qa3bb\n"
  "bP6MvPJwNQzcmRk13NfIRmPVNnGuV/u3gm3c\n"
  "-----END CERTIFICATE-----\n"
  "-----BEGIN CERTIFICATE-----\n"
  "MIICCTCCAY6gAwIBAgINAgPlwGjvYxqccpBQUjAKBggqhkjOPQQDAzBHMQswCQYD\n"
  "VQQGEwJVUzEiMCAGA1UEChMZR29vZ2xlIFRydXN0IFNlcnZpY2VzIExMQzEUMBIG\n"
  "A1UEAxMLR1RTIFJvb3QgUjQwHhcNMTYwNjIyMDAwMDAwWhcNMzYwNjIyMDAwMDAw\n"
  "WjBHMQswCQYDVQQGEwJVUzEiMCAGA1UEChMZR29vZ2xlIFRydXN0IFNlcnZpY2Vz\n"
  "IExMQzEUMBIGA1UEAxMLR1RTIFJvb3QgUjQwdjAQBgcqhkjOPQIBBgUrgQQAIgNi\n"
  "AATzdHOnaItgrkO4NcWBMHtLSZ37wWHO5t5GvWvVYRg1rkDdc/eJkTBa6zzuhXyi\n"
  "QHY7qca4R9gq55KRanPpsXI5nymfopjTX15YhmUPoYRlBtHci8nHc8iMai/lxKvR\n"
  "HYqjQjBAMA4GA1UdDwEB/wQEAwIBhjAPBgNVHRMBAf8EBTADAQH/MB0GA1UdDgQW\n"
  "BBSATNbrdP9JNqPV2Py1PsVq8JQdjDAKBggqhkjOPQQDAwNpADBmAjEA6ED/g94D\n"
  "9J+uHXqnLrmvT/aDHQ4thQEd0dlq7A/Cr8deVl5c1RxYIigL9zC2L7F8AjEA8GE8\n"
  "p/SgguMh1YQdc4acLa/KNJvxn7kjNuK8YAOdgLOaVsjh4rsUecrNIdSUtUlD\n"
  "-----END CERTIFICATE-----";


// ==================================================================
// 11. Network — Wi-Fi, price, candles, daily history
// ==================================================================

void wifiConnect() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  // Non-blocking on purpose: the loop keeps the screen alive and
  // retries every WIFI_RETRY_MS while the chip associates.
}

// Open an HTTPS GET; returns the HTTP status (200 = success).
// The caller MUST call http.end() when done (even on failure).
// TLS on this chip takes a few seconds for the handshake — normal.
//   Certificate: verified against ROOT_CA_BUNDLE (setCACert) —
//   never setInsecure(). A chain that does not land on a bundled
//   root fails the handshake, so the fetch fails closed and the
//   last-good price stays on screen. NOTE: mbedTLS checks the cert
//   dates against the system clock, so a fetch before NTP has synced
//   fails validation and is retried after the clock is up.
//   timeoutMs is 5 s for small JSON, 10 s for the big daily files
//   (fetchDailyFile / fetchCmpAsset pass 10000).
int httpsGet(const char *url, WiFiClientSecure &client, HTTPClient &http,
             int timeoutMs) {
  client.setCACert(ROOT_CA_BUNDLE);
  client.setTimeout(timeoutMs);
  http.setTimeout(timeoutMs);
  http.setUserAgent("PaperStreet-Keychain/1.0");
  if (!http.begin(client, url)) return -1;
  return http.GET();
}

// Block height from mempool.space (plain number, no JSON). Shown
// in the header and the stat tiles; 0 = unknown. Polled every
// 10 min while online — blocks only arrive every ~10 min anyway.
bool fetchBlockHeight() {
  FetchGuard guard;
  WiFiClientSecure client;
  HTTPClient http;
  int code = httpsGet("https://mempool.space/api/blocks/tip/height",
                      client, http);
  if (code != 200) { http.end(); return false; }
  char body[16];
  Stream &s = http.getStream();
  int i = 0;
  while (s.available() > 0 && i < 15) {
    int c = s.read();
    if (c < 0) break;
    body[i++] = (char)c;
  }
  body[i] = 0;
  http.end();
  long h = atol(body);
  if (h <= 0) return false;
  blockHeight = h;
  return true;
}

void savePrefs() {
  prefs.begin("pskey", false);
  prefs.putFloat("price", priceUSD);
  prefs.putFloat("chg24", chg24h);
  prefs.putFloat("fx", fxCAD);
  prefs.putBool("cad", curCAD);
  prefs.putBool("dark", themeDark);
  prefs.putInt("bright", brightnessPct);
  prefs.putInt("range", rangeIdx);
  prefs.putInt("ctype", chartType);
  prefs.putBool("ponly", priceOnly);
  // Comparison chips (R3) — which overlays are on survives reboot.
  prefs.putBool("cmp0", cmpOn[0]);
  prefs.putBool("cmp1", cmpOn[1]);
  prefs.putBool("cmp2", cmpOn[2]);
  // Auth accounts (TOTP secrets — see the security notes in the header)
  prefs.putInt("nauth", nAuth);
  prefs.putInt("aidx", authIdx);
  prefs.putBool("aseed", authSeeded);
  for (int i = 0; i < MAXAUTH; i++) {
    char kl[8], ks[8];
    snprintf(kl, sizeof(kl), "albl%d", i);
    snprintf(ks, sizeof(ks), "asec%d", i);
    prefs.putString(kl, authAccts[i].label);
    prefs.putString(ks, authAccts[i].secret);
  }
  prefs.end();
}

// Persist the last-good price, but at most every 10 min: the price
// poll succeeds every 60 s, and writing NVS on every poll wears the
// flash for no benefit — the saved price only matters across
// reboots. User actions (taps) still save immediately via
// savePrefs().
void savePricePrefs() {
  unsigned long now = millis();
  if (lastPriceSaveMs != 0 && now - lastPriceSaveMs < 600000UL) return;
  lastPriceSaveMs = now;
  savePrefs();
}

void loadPrefs() {
  prefs.begin("pskey", true);
  priceUSD  = prefs.getFloat("price", 0);
  chg24h    = prefs.getFloat("chg24", 0);
  fxCAD     = prefs.getFloat("fx", 1.37f);
  if (fxCAD <= 0) fxCAD = 1.37f;
  curCAD    = prefs.getBool("cad", false);
  themeDark = prefs.getBool("dark", true);
  brightnessPct = prefs.getInt("bright", 100);
  if (brightnessPct < 45 || brightnessPct > 100) brightnessPct = 100;
  rangeIdx  = prefs.getInt("range", 0);
  chartType = prefs.getInt("ctype", 0);
  priceOnly = prefs.getBool("ponly", false);
  cmpOn[0]  = prefs.getBool("cmp0", false);
  cmpOn[1]  = prefs.getBool("cmp1", false);
  cmpOn[2]  = prefs.getBool("cmp2", false);
  if (rangeIdx < 0 || rangeIdx >= NRANGES) rangeIdx = 0;
  if (chartType < 0 || chartType > 1) chartType = 0;
  priceOk = (priceUSD > 0);
  // Auth accounts
  nAuth = prefs.getInt("nauth", 0);
  if (nAuth < 0 || nAuth > MAXAUTH) nAuth = 0;
  authIdx = prefs.getInt("aidx", 0);
  authSeeded = prefs.getBool("aseed", false);
  for (int i = 0; i < MAXAUTH; i++) {
    char kl[8], ks[8];
    snprintf(kl, sizeof(kl), "albl%d", i);
    snprintf(ks, sizeof(ks), "asec%d", i);
    String l = prefs.getString(kl, "");
    String s = prefs.getString(ks, "");
    strncpy(authAccts[i].label, l.c_str(), AUTH_LABEL_LEN - 1);
    authAccts[i].label[AUTH_LABEL_LEN - 1] = 0;
    strncpy(authAccts[i].secret, s.c_str(), AUTH_SEC_LEN - 1);
    authAccts[i].secret[AUTH_SEC_LEN - 1] = 0;
  }
  if (nAuth == 0) authIdx = 0;
  else if (authIdx < 0 || authIdx >= nAuth) authIdx = 0;
  prefs.end();
}

// Sanity gate (R7): a price more than 12% away from the last good
// price is a lone wild tick (or a spoofed feed) — never draw it.
// With no last good price yet there is nothing to gate against.
bool priceSane(float usd) {
  if (usd <= 0) return false;
  if (priceUSD <= 0) return true;
  float d = (usd - priceUSD) / priceUSD;
  if (d < 0) d = -d;
  return d <= 0.12f;
}

// Price, every 60 s (R7): CoinGecko AND Coinbase spot are BOTH
// fetched now, and cross-checked — Coinbase used to be only the
// fallback. A tick is trusted if the two sources land within 1.5%
// of each other, or if it is within 12% of the last good price
// (the prototype's rule); a lone wild tick is never drawn. When the
// sources disagree by more than 1.5%, the one within 12% of the
// last good price wins; if both are sane but disagree, the one
// closer to the last good price wins; if neither is sane, both are
// rejected and the last good price stays on screen. CoinGecko still
// supplies CAD + the 24h change when it is the winner; when
// Coinbase wins, the change and FX keep their last good values.
// Cost: one extra HTTPS handshake per minute (see R9 — the stall
// this adds is bounded by the 5 s timeout and the one-fetch-per-
// loop rule). Returns true on a fresh price.
bool fetchPrice() {
  FetchGuard guard;
  WiFiClientSecure client;
  HTTPClient http;
  float cgUsd = 0, cgCad = 0, cgChg = 0;
  bool cgOk = false;
  float cbUsd = 0;
  bool cbOk = false;
  int code = httpsGet(URL_COINGECKO_PRICE, client, http);
  if (code == 200) {
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, http.getStream());
    http.end();
    if (!err) {
      float usd = doc["bitcoin"]["usd"];
      float cad = doc["bitcoin"]["cad"];
      float ch  = doc["bitcoin"]["usd_24h_change"];
      if (usd > 0) { cgUsd = usd; cgCad = cad; cgChg = ch; cgOk = true; }
    }
  } else {
    http.end();
  }
  code = httpsGet(URL_COINBASE_SPOT, client, http);
  if (code == 200) {
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, http.getStream());
    http.end();
    if (!err) {
      const char *amt = doc["data"]["amount"];
      float usd = amt ? atof(amt) : 0;
      if (usd > 0) { cbUsd = usd; cbOk = true; }
    }
  } else {
    http.end();
  }
  float use = 0;
  bool useCg = false;
  if (cgOk && cbOk) {
    float diff = cgUsd - cbUsd;
    if (diff < 0) diff = -diff;
    if (diff / cbUsd <= 0.015f) { use = cgUsd; useCg = true; }
    else {
      bool cgSane = priceSane(cgUsd), cbSane = priceSane(cbUsd);
      if (cgSane && !cbSane) { use = cgUsd; useCg = true; }
      else if (cbSane && !cgSane) { use = cbUsd; }
      else if (cgSane && cbSane) {
        float dc = cgUsd - priceUSD; if (dc < 0) dc = -dc;
        float db = cbUsd - priceUSD; if (db < 0) db = -db;
        if (dc <= db) { use = cgUsd; useCg = true; }
        else use = cbUsd;
      } else {
        Serial.println("price: both sources failed the sanity gate — keeping last good");
        return false;
      }
      Serial.println("price: sources disagree >1.5% — took the sane one");
    }
  } else if (cgOk) {
    if (!priceSane(cgUsd)) { Serial.println("price: CoinGecko failed the sanity gate"); return false; }
    use = cgUsd; useCg = true;
  } else if (cbOk) {
    if (!priceSane(cbUsd)) { Serial.println("price: Coinbase failed the sanity gate"); return false; }
    use = cbUsd;
  } else {
    return false;  // keep the last good price on screen
  }
  priceUSD = use;
  if (useCg) {
    chg24h = cgChg;
    if (cgCad > 0) { fxCAD = cgCad / cgUsd; }  // (Pass 5 finding 12: priceCAD was written here but never read — dropped; display converts USD->CAD via fxCAD at draw time.)
  }
  priceOk = true; lastPriceOkMs = millis();
  if (timeOk) lastPriceTime = time(nullptr);
  savePricePrefs();
  return true;
}

// Temporary parse buffers — global, NOT stack: 200 rows is ~5 KB
// and the Arduino loop task only has an 8 KB stack.
const int MAXROWS = 200;
float    tmpC[MAXROWS], tmpO[MAXROWS], tmpH[MAXROWS], tmpL[MAXROWS];
uint32_t tmpT[MAXROWS];

// Thin src arrays (ascending time) into the global series, keeping
// at most MAXP points and ALWAYS the newest point (the live edge).
// OHLC arrays are thinned with the same stride; pass nullptrs when
// there is no OHLC (daily closes).
int thinInto(const float *c, const float *o, const float *h,
             const float *l, const uint32_t *t, int n) {
  if (n <= MAXP) {
    for (int i = 0; i < n; i++) {
      sClose[i] = c[i]; sTime[i] = t[i];
      if (o) { sOpen[i] = o[i]; sHigh[i] = h[i]; sLow[i] = l[i]; }
    }
    return n;
  }
  int stride = (n + MAXP - 1) / MAXP;  // ceil
  int m = 0;
  for (int i = 0; i < n - 1 && m < MAXP - 1; i += stride) {
    sClose[m] = c[i]; sTime[m] = t[i];
    if (o) { sOpen[m] = o[i]; sHigh[m] = h[i]; sLow[m] = l[i]; }
    m++;
  }
  // last slot is always the newest point
  sClose[m] = c[n - 1]; sTime[m] = t[n - 1];
  if (o) { sOpen[m] = o[n - 1]; sHigh[m] = h[n - 1]; sLow[m] = l[n - 1]; }
  return m + 1;
}

// Coinbase candles for 1D / 1W / 1M. Rows arrive newest-first; we
// keep the newest `spanSec/gran` rows and store them oldest-first.
// With the clock synced we ask for exactly the window; without it
// (NTP not up yet) Coinbase returns the newest ~350 candles and we
// take the tail for our window — no clock needed.
bool fetchCoinbaseCandles(int gran, long spanSec) {
  char url[256];
  if (timeOk) {
    time_t now = time(nullptr);
    time_t start = now - spanSec;
    char sStart[32], sEnd[32];
    struct tm tmv;
    gmtime_r(&start, &tmv);
    strftime(sStart, sizeof(sStart), "%Y-%m-%dT%H:%M:%SZ", &tmv);
    gmtime_r(&now, &tmv);
    strftime(sEnd, sizeof(sEnd), "%Y-%m-%dT%H:%M:%SZ", &tmv);
    snprintf(url, sizeof(url), "%s?granularity=%d&start=%s&end=%s",
             URL_COINBASE_CANDLES, gran, sStart, sEnd);
  } else {
    snprintf(url, sizeof(url), "%s?granularity=%d",
             URL_COINBASE_CANDLES, gran);
  }
  WiFiClientSecure client;
  HTTPClient http;
  int code = httpsGet(url, client, http);
  if (code != 200) { http.end(); return false; }
  // The response streams straight into the parser — it is never
  // held as one big string. 1W is the largest: 168 rows, ~10 KB.
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, http.getStream());
  http.end();
  if (err) return false;
  JsonArray rows = doc.as<JsonArray>();
  int total = rows.size();
  if (total < 2) return false;
  int want = (int)(spanSec / gran) + 1;
  int take = total < want ? total : want;  // newest `take` rows
  int n = 0;
  for (int i = take - 1; i >= 0 && n < MAXROWS; i--) {
    JsonArray r = rows[i].as<JsonArray>();
    // A malformed row (short array, or a zero/negative field from a
    // partial response) must not poison the series: a zero close
    // would drag chartMin to 0 and collapse the chart. A real
    // Coinbase candle always has all-positive OHLC.
    if (r.size() < 6) continue;
    long t = (long)r[0];
    float lo = r[1], hi = r[2], op = r[3], cl = r[4];
    if (t <= 0 || lo <= 0 || hi <= 0 || op <= 0 || cl <= 0) continue;
    tmpT[n] = (uint32_t)t;
    tmpL[n] = lo; tmpH[n] = hi; tmpO[n] = op; tmpC[n] = cl;
    n++;
  }
  if (n < 2) return false;
  sN = thinInto(tmpC, tmpO, tmpH, tmpL, tmpT, n);
  sIsDaily = false;
  sHasOHLC = true;
  for (int i = 0; i < sN; i++) sDate[i][0] = 0;
  return true;
}

// Daily closes from the PaperStreet site file, for 3M and longer.
// The file is ~135 KB / ~5,900 entries, so it is parsed with a
// filter (only the "d" array is kept) into a document that lives
// in PSRAM — this is why the board setting "PSRAM: OPI PSRAM"
// is required. After parsing we thin to <= MAXP points and the
// document is freed.
bool fetchDailyFile(int ridx) {
  WiFiClientSecure client;
  HTTPClient http;
  int code = httpsGet(URL_DAILY_FILE, client, http, 10000);
  if (code != 200) { http.end(); return false; }
  JsonDocument filter;
  filter["d"] = true;  // drop the file's metadata keys
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, http.getStream(),
                                             DeserializationOption::Filter(filter));
  http.end();
  if (err) return false;
  JsonArray d = doc["d"];
  int total = d.size();
  if (total < 2) return false;
  // Slice the window for this range (entries are oldest-first).
  int first = 0, last = total - 1;
  if (ridx == 3)      first = total > 90   ? total - 90   : 0;  // 3M
  else if (ridx == 4) first = total > 180  ? total - 180  : 0;  // 6M
  else if (ridx == 5) {  // YTD: from Jan 1 of the last entry's year
    const char *endDate = d[total - 1][0];
    if (endDate) {
      char ytdStart[11];
      snprintf(ytdStart, sizeof(ytdStart), "%.4s-01-01", endDate);
      first = 0;
      while (first < total) {
        const char *dt = d[first][0];
        if (dt && strcmp(dt, ytdStart) >= 0) break;
        first++;
      }
    } else {
      first = total > 365 ? total - 365 : 0;  // no date: fall back to 1Y
    }
  }
  else if (ridx == 6) first = total > 365  ? total - 365  : 0;  // 1Y
  else if (ridx == 7) first = total > 1826 ? total - 1826 : 0;  // 5Y
  // MAX (8): first = 0, every entry.
  int count = last - first + 1;
  if (count < 2) return false;
  // Pick evenly spaced entries, always including the last one.
  int stride = (count + MAXP - 1) / MAXP;  // ceil
  int idx[MAXP];
  int m = 0;
  for (int i = first; i <= last && m < MAXP - 1; i += stride) idx[m++] = i;
  if (m == 0 || idx[m - 1] != last) idx[m++] = last;
  sN = 0;
  for (int j = 0; j < m; j++) {
    JsonArray e = d[idx[j]].as<JsonArray>();
    const char *dt = e[0];
    float cl = e[1];
    if (!dt || cl <= 0) continue;
    sClose[sN] = cl;
    sTime[sN] = 0;
    snprintf(sDate[sN], sizeof(sDate[sN]), "%s", dt);
    sN++;
  }
  if (sN < 2) return false;
  sIsDaily = true;
  sHasOHLC = false;
  return true;
}

// Fetch (or refresh) the chart for a range. Candles come only on a
// range change or when the cache is stale — never every minute.
bool fetchChart(int ridx) {
  FetchGuard guard;
  bool ok = false;
  if (RANGES[ridx].gran > 0) {
    ok = fetchCoinbaseCandles(RANGES[ridx].gran, RANGES[ridx].spanSec);
  } else {
    ok = fetchDailyFile(ridx);
    if (!ok && ridx >= 3 && ridx <= 6) {
      // Degraded fallback: Coinbase daily candles cover 3M/6M/YTD/1Y
      // in one request (<= 365 rows). 5Y/MAX have no honest fallback
      // — keep the last chart and stay offline instead of showing
      // a misleading 300-day window as "5Y".
      long span = RANGES[ridx].spanSec;
      if (ridx == 5) span = 31536000;  // YTD: a 1y window as fallback
      ok = fetchCoinbaseCandles(86400, span);
    }
  }
  if (ok && sN > 0) {
    // The last point is the live spot, as in the prototype.
    if (priceUSD > 0) {
      sClose[sN - 1] = priceUSD;
      if (sHasOHLC && sLow[sN - 1] > priceUSD) sLow[sN - 1] = priceUSD;
      if (sHasOHLC && sHigh[sN - 1] < priceUSD) sHigh[sN - 1] = priceUSD;
    }
    chartFetchedMs = millis();
    chartRange = ridx;
  }
  return ok;
}

// ==================================================================
// Comparison overlays (R3) — SPX / GOLD / MSTR, line mode only.
// Each asset's daily closes come from the site's own *-daily.json
// (same shape as the BTC file) and are stepped to the BTC points:
// for each BTC point, the asset's latest close on or before that
// point's date (forward-filled across weekends / file lag). All
// lines are rebased to 100 at the range start so they share one
// scale; the Y labels convert back to BTC $ (see drawChartBody).
// ==================================================================

bool cmpAnyOn() { return cmpOn[0] || cmpOn[1] || cmpOn[2]; }
bool cmpAnyOk() { return cmpOk[0] || cmpOk[1] || cmpOk[2]; }

// % change of one comparison asset over the plotted range.
float cmpPct(int c) {
  if (!cmpOk[c] || sN < 2 || cClose[c][0] <= 0) return 0;
  return (cClose[c][sN - 1] / cClose[c][0] - 1.0f) * 100.0f;
}

// The date a BTC point steps to, "YYYY-MM-DD" (UTC, like the chart).
void cmpTargetDate(int i, char *out, size_t n) {
  if (sIsDaily) { snprintf(out, n, "%s", sDate[i]); return; }
  time_t t = (time_t)sTime[i];
  struct tm tmv;
  gmtime_r(&t, &tmv);
  strftime(out, n, "%Y-%m-%d", &tmv);
}

// Fetch one asset's daily file and align it to the BTC points.
// Returns true when every plotted point has a positive close.
bool fetchCmpAsset(int c) {
  if (sN < 2) return false;
  WiFiClientSecure client;
  HTTPClient http;
  int code = httpsGet(URL_CMP_FILE[c], client, http, 10000);
  if (code != 200) { http.end(); return false; }
  JsonDocument filter;
  filter["d"] = true;  // drop the file's metadata keys
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, http.getStream(),
                                             DeserializationOption::Filter(filter));
  http.end();
  if (err) return false;
  JsonArray d = doc["d"];
  int total = d.size();
  if (total < 2) return false;
  // Slice the window for this range (entries are oldest-first).
  // Daily ranges mirror fetchDailyFile's windows; intraday ranges
  // take the last (span days + 5) entries — a daily close only
  // moves once a day, so a few days cover a 1D/1W/1M window.
  int first = 0, last = total - 1;
  int ridx = rangeIdx;
  if (RANGES[ridx].gran > 0) {
    int days = (int)(RANGES[ridx].spanSec / 86400) + 5;
    first = total > days ? total - days : 0;
  } else if (ridx == 3)      first = total > 90   ? total - 90   : 0;  // 3M
  else if (ridx == 4) first = total > 180  ? total - 180  : 0;  // 6M
  else if (ridx == 5) {  // YTD: from Jan 1 of the last entry's year
    const char *endDate = d[total - 1][0];
    if (endDate) {
      char ytdStart[11];
      snprintf(ytdStart, sizeof(ytdStart), "%.4s-01-01", endDate);
      first = 0;
      while (first < total) {
        const char *dt = d[first][0];
        if (dt && strcmp(dt, ytdStart) >= 0) break;
        first++;
      }
    } else {
      first = total > 365 ? total - 365 : 0;
    }
  }
  else if (ridx == 6) first = total > 365  ? total - 365  : 0;  // 1Y
  else if (ridx == 7) first = total > 1826 ? total - 1826 : 0;  // 5Y
  // MAX (8): first = 0, every entry.
  // Align: one pass over the asset entries, forward-filling each
  // BTC point with the latest close on or before its date.
  int bi = 0;
  float lastClose = -1;
  char tgt[11];
  for (int j = first; j <= last && bi < sN; j++) {
    JsonArray e = d[j].as<JsonArray>();
    const char *dt = e[0];
    float cl = e[1];
    if (!dt || cl <= 0) continue;
    while (bi < sN) {
      cmpTargetDate(bi, tgt, sizeof(tgt));
      if (strcmp(tgt, dt) < 0) {
        cClose[c][bi] = (lastClose > 0) ? lastClose : cl;
        bi++;
      } else break;
    }
    lastClose = cl;
  }
  while (bi < sN) { cClose[c][bi] = lastClose > 0 ? lastClose : 0; bi++; }
  for (int i = 0; i < sN; i++) if (cClose[c][i] <= 0) return false;
  return true;
}

// Fetch ONE pending comparison asset (R9). The loop calls this at most
// once per pass, so turning on chips — or landing a new chart with
// chips on — never blocks on three daily files back-to-back. Called
// for the asset whose bit is set in cmpPending (set by a chip toggle
// in onTap, or by the loop after a chart fetch lands).
void fetchOneCmpAsset() {
  if (sN < 2) { cmpPending = 0; return; }
  for (int c = 0; c < 3; c++) {
    if (!(cmpPending & (1 << c))) continue;
    cmpPending &= ~(1 << c);
    {
      FetchGuard guard;
      cmpOk[c] = fetchCmpAsset(c);
      cmpRange = rangeIdx;
      cmpFetchedMs = millis();
    }  // Guard destructs here: fetching is false again.
    // Redraw AFTER the guard clears, matching the price/chart
    // branches (their drawAll runs after their fetch returns).
    // The old code drew while the guard was alive, so the redraw
    // painted "Fetching..." into the scrub row — and nothing
    // redrew after the guard cleared, so the hint lied for up to
    // a minute. (Finding 2.)
    if (appMode == MODE_PRICE) drawAll();
    return;
  }
}

// ==================================================================
// 12. Touch (CST816, raw I2C — no extra library needed)
//    Registers: 0x02 = touch-point count, 0x03/0x04 = X, 0x05/0x06 = Y.
// ==================================================================
uint8_t tpAddr = TP_ADDR;

void touchReset() {
  pinMode(TP_RST, OUTPUT);
  digitalWrite(TP_RST, LOW);
  delay(10);
  digitalWrite(TP_RST, HIGH);
  delay(50);
}

void touchBegin() {
  Wire.begin(TP_SDA, TP_SCL);
  touchReset();
  // Probe for the touch chip: 0x15 is the CST816; a few early
  // boards shipped a CST328 at 0x1A instead.
  Wire.beginTransmission(TP_ADDR);
  if (Wire.endTransmission() == 0) { tpAddr = TP_ADDR; return; }
  Wire.beginTransmission(0x1A);
  if (Wire.endTransmission() == 0) tpAddr = 0x1A;
}

bool touchRead(int16_t &x, int16_t &y) {
  Wire.beginTransmission(tpAddr);
  Wire.write(0x02);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(tpAddr, (uint8_t)7) < 7) return false;
  uint8_t b[7];
  for (int i = 0; i < 7; i++) b[i] = Wire.read();
  if ((b[0] & 0x0F) < 1) return false;  // no finger down
  x = ((b[1] & 0x0F) << 8) | b[2];
  y = ((b[3] & 0x0F) << 8) | b[4];
  // The CST816 reports in the panel's native orientation. If taps
  // land mirrored on your board, uncomment one of these:
  // x = SW - 1 - x;
  // y = SH - 1 - y;
  if (landscape) {
    // The display is rotated 90 deg clockwise (setRotation 1).
    // The touch chip still reports native panel coordinates
    // (x: 0..169 across the short edge, y: 0..319 down the long
    // edge), so remap to the rotated drawing space. Derived from
    // the ST7789 MADCTL for rotation 1 (MX|MV, TFT_eSPI's
    // ST7789_Rotation.h): a drawing point (dx, dy) lights up the
    // panel at (dy, 319-dx), so a touch at panel (tx, ty) is
    // drawing (319-ty, tx). If taps land mirrored on the real
    // board, the rotation is the other way — use setRotation(3)
    // and the remap (dx = ty, dy = 169-tx) instead. This is the
    // one thing that must be checked on the real board.
    int16_t dx = SH - 1 - y;
    int16_t dy = x;
    x = dx; y = dy;
    if (x < 0 || x >= SH || y < 0 || y >= SW) return false;
  } else {
    if (x < 0 || x >= SW || y < 0 || y >= SH) return false;
  }
  return true;
}

// ==================================================================
// 13. Tap handling + main loop
// ==================================================================

// A tap is a finger-down followed by a lift; the tap point is
// where the finger went down.
bool touchDown = false;
bool downInChart = false;  // the finger went down inside the chart
bool downOnPill = false;   // the finger went down on a button (pill, chip, dot)
int16_t downX = 0, downY = 0;
int16_t lastTX = 0, lastTY = 0;  // last seen finger position while down
unsigned long lastChartTryMs = 0;

void onTap(int16_t x, int16_t y) {
  // LIVE tap = manual refresh (R7/R12): any page. Forces the price
  // poll on the next loop pass and paints "Fetching…" at once, so the
  // tap gets visible feedback. Offline, there is nothing to fetch.
  // Geometry, not a registered button — the status bar is also drawn
  // standalone (Auth countdown), where btns[] is not reset, so it
  // cannot register a button id there.
  {
    int16_t barH = landscape ? 13 : 15;
    if (y >= 0 && y < barH && liveHitW > 0 &&
        x >= liveHitX && x < liveHitX + liveHitW) {
      if (wifiOk) {
        manualRefresh = true;
        lastPriceMs = millis() - PRICE_POLL_MS;
        drawFetchingNote();
      }
      return;
    }
  }
  int id = hitTest(x, y);
  // --- Block clock screen ---
  if (appMode == MODE_CLOCK) {
    if (id >= 30 && id <= 32) {  // focus dots: jump + restart the timer
      clockFocus = id - 30;
      lastClockRotateMs = millis();
      drawAll();
      return;
    }
    if (id == 33) { goToPage(PAGE_CHART); return; }  // Chart
    if (id == 34) { goToPage(qrPage == 0 ? PAGE_QR_JADE : PAGE_QR_LN); return; }  // QR (keeps Jade/Lightning)
    if (id == 35) { goToPage(PAGE_AUTH); return; }
    return;  // taps elsewhere on the clock screen do nothing
  }
  // --- QR screen ---
  if (appMode == MODE_QR) {
    if (id == 36) { goToPage(PAGE_CHART); return; }  // Chart
    if (id == 37) { goToPage(PAGE_CLOCK); return; }  // Clock
    if (id == 38) { goToPage(PAGE_AUTH); return; }
    if (id == 39) { goToPage(PAGE_QR_JADE); return; }
    if (id == 40) { goToPage(PAGE_QR_LN); return; }
    if (id == 41) { qrFlipped = !qrFlipped; drawAll(); return; }  // tap QR card
    if (id < 0 && qrFlipped) { qrFlipped = false; drawAll(); return; }  // tap anywhere: back
    return;
  }
  // --- Auth screen ---
  if (appMode == MODE_AUTH) {
    if (id >= 60 && id < 60 + MAXAUTH) {  // tap a row: select it
      int i = id - 60;
      if (i < nAuth) {
        authIdx = i;
        authRefresh();
        drawAll();
      }
      return;
    }
    if (id == 53) {        // HIDE / SHOW codes
      authHideCodes = !authHideCodes;
      drawAll();
      return;
    }
    if (id == 22) {        // Price (back to the price screen)
      goToPage(PAGE_CHART);
      return;
    }
    if (id == 51) {        // Clock
      goToPage(PAGE_CLOCK);
      return;
    }
    if (id == 52) {        // QR (keeps Jade/Lightning)
      goToPage(qrPage == 0 ? PAGE_QR_JADE : PAGE_QR_LN);
      return;
    }
    return;  // taps elsewhere on the Auth screen do nothing
  }
  // --- Price screen ---
  if (id == -2) {  // tap on the chart area (price-only is swipe-back)
    return;
  }
  if (id < 0) return;
  if (id < NRANGES) {
    // Disabled pills (5Y/MAX in candle mode) do nothing (R11) — the
    // prototype's disabled button cannot be tapped. Without this the
    // tap changed the range and forced line mode.
    if (chartType == 1 && RANGES[id].candleTarget == 0) return;
    if (id != rangeIdx) {
      rangeIdx = id;
      // Candles do not exist on 5Y/MAX — drop back to the line.
      if (RANGES[rangeIdx].candleTarget == 0) chartType = 0;
      savePrefs(); drawAll();
    }
  } else if (id == 13) {        // Price-only page (swipe track page 1)
    goToPage(priceOnly ? PAGE_CHART : PAGE_PRICE);
  } else if (id == 14) {        // Auth
    goToPage(PAGE_AUTH);
  } else if (id == 15) {        // Rotate — toggle landscape chart
    // The same id is the "Rotate" button in portrait and the
    // "Portrait" button in landscape. Range and chart type are
    // kept; nothing is reset. Deliberately NOT saved to NVS —
    // the device always boots in portrait. Landscape forces the
    // chart page (R4); rotating back to portrait returns to the
    // chart page, not the previous page.
    landscape = !landscape;
    if (landscape) { appMode = MODE_PRICE; priceOnly = false; }
    drawAll();
  } else if (id == 16) {        // USD
    if (curCAD) { curCAD = false; savePrefs(); drawAll(); }
  } else if (id == 17) {        // CAD
    if (!curCAD) { curCAD = true; savePrefs(); drawAll(); }
  } else if (id == 27) {        // big-price tap: toggle currency (prototype)
    curCAD = !curCAD; savePrefs(); drawAll();
  } else if (id == 18) {        // Line
    if (chartType != 0) { chartType = 0; savePrefs(); drawAll(); }
  } else if (id == 19) {        // Candles
    // Candles do not exist on 5Y/MAX — stay on the line there.
    if (chartType != 1 && RANGES[rangeIdx].candleTarget > 0) {
      chartType = 1; savePrefs(); drawAll();
    }
  } else if (id >= 43 && id <= 45) {  // comparison chips (R3)
    int c = id - 43;
    cmpOn[c] = !cmpOn[c];
    savePrefs();
    // Turning a chip on queues ONE asset fetch (R9) — the loop fetches
    // it on the next pass instead of blocking the tap on three daily
    // files. Until it lands the chip shows "--" (cmpOk is false).
    cmpOk[c] = false;
    if (cmpOn[c]) cmpPending |= (1 << c);
    drawAll();
  } else if (id == 23) {        // Dark
    if (!themeDark) { themeDark = true; savePrefs(); drawAll(); }
  } else if (id == 24) {        // Light
    if (themeDark) { themeDark = false; savePrefs(); drawAll(); }
  } else if (id == 25) {        // Brightness down (R8, price-only page)
    if (brightnessPct > 45) {
      brightnessPct -= 5;
      if (brightnessPct < 45) brightnessPct = 45;
      applyBrightness(); savePrefs(); drawAll();
    }
  } else if (id == 26) {        // Brightness up (R8, price-only page)
    if (brightnessPct < 100) {
      brightnessPct += 5;
      if (brightnessPct > 100) brightnessPct = 100;
      applyBrightness(); savePrefs(); drawAll();
    }
  }
}

void handleTouch() {
  int16_t x, y;
  bool t = touchRead(x, y);
  // --- Asleep (R6): any fresh touch wakes; the waking touch does
  // nothing else. The finger that put the device to sleep is still
  // down until it lifts — it must not wake it straight back up.
  if (screenAsleep) {
    if (t) {
      if (sleepIgnoreLift) { touchDown = true; }
      else if (!touchDown) { touchDown = true; wakeSwallow = true; wakeUp(); }
    } else {
      touchDown = false;
      sleepIgnoreLift = false;
    }
    return;
  }
  if (t && !touchDown) {
    touchDown = true; downX = x; downY = y; scrubbing = false;
    downAtMs = millis();
    longPressArmed = false;
    lastTX = x; lastTY = y;
    // A scrub only starts from a finger-down INSIDE the chart: a
    // drag that starts on a pill and slides into the chart is not a
    // scrub (downInChart is false). It CAN still swipe, though —
    // the old code suppressed any swipe starting on a button, which
    // made the QR pages nearly unswipeable (the QR card is a 148x148
    // button covering 87% of the width) and let a 100 px drag from
    // a pill fire the pill. (Pass 5 finding 2.)
    downInChart = (appMode == MODE_PRICE && !priceOnly && sN >= 2 &&
                   x >= gCH_X && x < gCH_X + gCH_W &&
                   y >= gCH_Y && y < gCH_Y + gCH_H);
    // downOnPill no longer gates the swipe (see above) — it only
    // keeps a pill hold from arming long-press sleep.
    downOnPill = (hitTest(x, y) >= 0);
  } else if (t && touchDown) {
    lastTX = x; lastTY = y;
    // Long-press sleep (R6, Pass 5 finding 5): ARMED after a 1200 ms
    // hold, barely moved, not in the chart (that is a scrub hold)
    // and not on a pill — but sleep only fires on the LIFT (see the
    // lift branch). A drag after the hold clears the arm, so a user
    // who pauses before swiping pages instead of sleeping.
    if (!downInChart && !downOnPill &&
        millis() - downAtMs >= 1200 &&
        abs(x - downX) < 8 && abs(y - downY) < 8) {
      longPressArmed = true;
    } else if (abs(x - downX) >= 8 || abs(y - downY) >= 8) {
      longPressArmed = false;
    }
    // Finger still down: if it moves inside the chart area, that
    // is a drag-scrub, not a tap. A tap without movement keeps the
    // old tap behaviour.
    if (downInChart && appMode == MODE_PRICE && !priceOnly && sN >= 2 &&
        abs(x - downX) > 3 &&
        y >= gCH_Y && y < gCH_Y + gCH_H &&
        x >= gCH_X && x < gCH_X + gCH_W) {
      scrubbing = true;
      int idx;
      if (chartType == 1 && dispCandN > 0) {
        // Candle mode: snap to the candle under the finger, so the
        // dot sits on a candle centre and the readout is that
        // candle's close (see scrubCand / drawScrubOverlay).
        int ci = (int)((long)(x - gCH_X) * dispCandN / gCH_W);
        if (ci < 0) ci = 0;
        if (ci > dispCandN - 1) ci = dispCandN - 1;
        scrubCand = ci;
        idx = dispCand[ci].si;
      } else {
        scrubCand = -1;
        idx = (int)((long)(x - gCH_X) * (sN - 1) / (gCH_W - 1));
      }
      if (idx < 0) idx = 0;
      if (idx > sN - 1) idx = sN - 1;
      if (idx != scrubIdx) {
        scrubIdx = idx;
        drawChartBody();
        drawScrubRow();
      }
    }
  } else if (!t && touchDown) {
    // The finger that woke the device: swallow its lift, so waking
    // never also fires as a tap or a swipe.
    if (wakeSwallow) { wakeSwallow = false; touchDown = false; return; }
    touchDown = false;
    // A scrub ends when the finger lifts — clear it and redraw.
    if (scrubbing) {
      scrubbing = false; scrubIdx = -1; scrubCand = -1;
      drawChartBody();
      drawScrubRow();
      return;
    }
    // Swipe (R4, Pass 5 finding 2): a horizontal-dominant drag that
    // started on empty background — not in the chart (that is a
    // scrub). It MAY start on a button now: the prototype's swipe
    // check only excludes scrubbing, and suppressing pill-start
    // swipes made the QR pages nearly unswipeable. Fires past 34 px
    // of horizontal travel, only when horizontal travel is >= 1.4x
    // the vertical (the prototype's rule), so a vertical drag never
    // changes page. Swipe left = next page, right = previous; the
    // track wraps around. Checked before the tap debounce and
    // before onTap, so a swipe never also fires as a tap. No swipe
    // in landscape: the rotated chart is not a track page.
    // lastTapMs is NOT set on a swipe (Pass 5 finding 4): the old
    // code left a ~500 ms dead window after every page change.
    if (!landscape && !downInChart) {
      int16_t dx = lastTX - downX, dy = lastTY - downY;
      int16_t adx = dx < 0 ? -dx : dx, ady = dy < 0 ? -dy : dy;
      if (adx >= 34 && adx * 10 >= ady * 14) {
        goToPage(dx < 0 ? (curPage() + 1) % NPAGES
                        : (curPage() + NPAGES - 1) % NPAGES);
        return;
      }
    }
    // Long-press sleep, fired on the lift (Pass 5 finding 5): the
    // hold was armed while the finger was down and never dragged
    // away, so this lift is a deliberate hold-and-release, not a
    // tap or a swipe. The lift is swallowed, not read as a tap.
    {
      int16_t mdx = lastTX - downX, mdy = lastTY - downY;
      int16_t madx = mdx < 0 ? -mdx : mdx, mady = mdy < 0 ? -mdy : mdy;
      if (longPressArmed && madx < 10 && mady < 10) {
        longPressArmed = false;
        enterSleep();
        sleepIgnoreLift = true;
        touchDown = false;
        return;
      }
      longPressArmed = false;
    }
    // A tap is a NEAR-STATIONARY lift (Pass 5 finding 2): the old
    // code fired the button on any lift after a down on it, so a
    // 100 px drag starting on a range pill still selected that
    // range. A lift that moved >= 10 px is a drag that was neither
    // a scrub nor a swipe — it fires nothing.
    {
      int16_t mdx = lastTX - downX, mdy = lastTY - downY;
      int16_t madx = mdx < 0 ? -mdx : mdx, mady = mdy < 0 ? -mdy : mdy;
      if (madx >= 10 || mady >= 10) return;
    }
    if (millis() - lastTapMs < 30) return;  // debounce (was 150 ms — Pass 5 finding 4: fast taps were eaten)
    lastTapMs = millis();
    onTap(downX, downY);
  }
}

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("\nPaperStreet keychain — starting");

  // GPIO 15 powers the display and the touch chip. Without this
  // line the screen stays black even though the sketch runs.
  pinMode(PIN_POWER, OUTPUT);
  digitalWrite(PIN_POWER, HIGH);
  delay(100);

  loadPrefs();
  if (!authSeeded) {
    // First boot: seed the public RFC 6238 demo account (test secret,
    // not a real account). It is labelled DEMO on screen; delete it
    // over Serial once a real account is added.
    strncpy(authAccts[0].label, AUTH_DEMO_LABEL, AUTH_LABEL_LEN - 1);
    authAccts[0].label[AUTH_LABEL_LEN - 1] = 0;
    strncpy(authAccts[0].secret, AUTH_DEMO_SECRET, AUTH_SEC_LEN - 1);
    authAccts[0].secret[AUTH_SEC_LEN - 1] = 0;
    nAuth = 1; authIdx = 0; authSeeded = true;
    savePrefs();
    Serial.println("Auth: seeded demo account (RFC 6238 test secret)");
  }
  applyTheme();
  tft.init();
  tft.setRotation(0);  // portrait, 170 wide x 320 tall
  curRot = 0;          // the device always boots in portrait
  applyBrightness();   // backlight PWM to the stored level (R8)
  // Smooth fonts live on LittleFS (data/ — upload with
  // "pio run -t uploadfs"). If the mount fails, format once; if
  // there are still no font files, useFont() falls back to the
  // built-in bitmap fonts and the device still works.
  fontsOk = LittleFS.begin();
  if (!fontsOk) fontsOk = LittleFS.begin(true);
  if (!fontsOk) Serial.println("LittleFS mount failed — using built-in fonts");
  tft.fillScreen(C_BG);
  tft.setTextFont(2);
  tft.setTextColor(C_TEXT, C_BG);
  tft.setCursor(8, 140);
  tft.print("PaperStreet keychain");
  tft.setTextColor(C_MUTED, C_BG);
  tft.setCursor(8, 158);
  tft.print("connecting to Wi-Fi...");

  touchBegin();

  // Clock: NTP, Eastern time (America/Toronto). Non-blocking —
  // the display works before the clock syncs, and the chart fetch
  // has a no-clock fallback (see fetchCoinbaseCandles).
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  setenv("TZ", "EST5EDT,M3.2.0,M11.1.0", 1);
  tzset();

  wifiConnect();

  // Draw the last-good price immediately so the screen is never
  // blank, then let the loop do the first fetch right away.
  drawAll();
  lastPriceMs = millis() - PRICE_POLL_MS;
  lastBlockMs = millis() - BLOCK_POLL_MS;
  lastChartTryMs = millis() - 30000;
  serialHelp();
  Serial.println("setup done");
}

// True when the chart for the selected range should be (re)fetched
// now (R9): the range changed, or the cache is stale and the 30 s
// retry throttle has elapsed. Failed fetches retry at most every
// 30 s (never a tight loop).
bool chartFetchDue(unsigned long now) {
  if (chartRange != rangeIdx) return true;
  unsigned long fresh = RANGES[rangeIdx].gran > 0
                          ? CHART_FRESH_MS : DAILY_FRESH_MS;
  return (now - chartFetchedMs > fresh) &&
         (now - lastChartTryMs > 30000);
}

void loop() {
  unsigned long now = millis();

  // --- Asleep (R6): nothing fetches, nothing redraws except the
  // veil. The loop only polls touch. On the ESP32 the CPU light-
  // sleeps 50 ms at a time between polls (timer wakeup); the touch
  // poll itself is the wake path — see enterSleep(). On wake the
  // price poll below fires at once (its timer has long expired), so
  // the screen refreshes with a fresh price.
#ifdef ARDUINO_ARCH_ESP32
  if (screenAsleep) {
    esp_sleep_enable_timer_wakeup(50 * 1000);
    esp_light_sleep_start();
    if (millis() - lastTouchMs >= TOUCH_POLL_MS) {
      lastTouchMs = millis();
      handleTouch();
    }
    return;
  }
#else
  if (screenAsleep) {
    if (millis() - lastTouchMs >= TOUCH_POLL_MS) {
      lastTouchMs = millis();
      handleTouch();
    }
    delay(20);
    return;
  }
#endif

  // --- Auth first: refresh the TOTP code when the 30 s window rolls
  // over, and update the countdown + status bar once a second. It
  // runs BEFORE the network polls below on purpose — a price/chart
  // fetch blocks the loop for seconds (HTTPS handshake), and a
  // window rollover during a fetch must not leave the old code
  // showing as valid. Only the code / countdown areas are redrawn
  // (no full-screen flicker). ---
  if (appMode == MODE_AUTH) {
    uint32_t w = totpWindow();
    if (w != 0 && w != authWindow) {
      authRefresh();
      drawAuthCodeText();
      drawAuthCountdown();
      drawStatusBar(15, false);
      lastAuthSecMs = now;
    } else if (now - lastAuthSecMs >= 1000) {
      lastAuthSecMs = now;
      drawAuthCountdown();
      drawStatusBar(15, false);
    }
  }

  // --- Block clock: auto-rotate the focus every 12 s, redraw the
  // dynamic text once a second. The mempool feed refresh (every
  // 5 min while the screen is showing) is one of the network chain's
  // one-fetch-per-pass slots below (R9), not a second fetch here.
  if (appMode == MODE_CLOCK) {
    if (now - lastClockRotateMs >= 12000) {
      lastClockRotateMs = now;
      clockFocus = (clockFocus + 1) % 3;
      drawAll();
    } else if (now - lastClockDynMs >= 1000) {
      lastClockDynMs = now;
      drawClockDynamic();
    }
  }

  // --- Wi-Fi: reconnect in the background, never block the UI ---
  if (WiFi.status() != WL_CONNECTED) {
    wifiOk = false;
    if (now - lastWifiTryMs > WIFI_RETRY_MS) {
      lastWifiTryMs = now;
      Serial.println("Wi-Fi lost — reconnecting");
      wifiConnect();
    }
  } else {
    wifiOk = true;
  }

  // --- Clock: NTP is async; flag it once the epoch looks real ---
  if (!timeOk && time(nullptr) > 1700000000L) timeOk = true;

  // --- Network: ONE fetch per loop pass (R9). The Arduino HTTP
  // client is synchronous, so each fetch blocks touch for the whole
  // TLS handshake + transfer (2-5 s). Firing price + chart + block
  // in one pass stacked those stalls back-to-back; one pass now does
  // at most one fetch, and the next pass (20 ms later) does the next
  // one. Priority: price, chart, block height, clock feeds, one
  // comparison asset. The "Fetching…" note (see FetchGuard) says so
  // while any of them runs. THE FULL FIX — fetches on the second
  // core, or an async client — was NOT done: every fetch writes the
  // shared series / price globals that the draw code reads with no
  // locking, so a fetch task would race the UI task and corrupt the
  // chart. That is a real piece of work (a fetch task + a handoff
  // queue + locking), not a tweak. What this step does instead is
  // the bounded mitigation: shorter timeouts (5 s small / 10 s big,
  // see httpsGet), one fetch per pass, one comparison asset per
  // pass, and an honest on-screen "Fetching…" state. What remains:
  // a tap that both begins AND ends inside a stall is still lost —
  // the CST816 latches no taps, so the loop cannot recover a touch
  // it never saw; the user can see Fetching… and tap again.
  if (wifiOk && now - lastPriceMs >= PRICE_POLL_MS) {
    lastPriceMs = now;
    manualRefresh = false;
    if (fetchPrice()) {
      Serial.print("price $"); Serial.println(priceUSD);
      // The clock screen shows sats, so a fresh price redraws it too.
      if (appMode == MODE_PRICE || appMode == MODE_CLOCK) drawAll();
    } else {
      // Redraw on failure too (Pass 5 finding 6): the FetchGuard
      // painted "Fetching..." on entry and cleared `fetching` on
      // exit, so only a redraw after the guard clears puts the
      // hint back — without it the scrub row lied for up to 60 s
      // (up to ~5 min in a sustained outage). Same for the chart
      // and block branches below; the comparison path was fixed
      // the same way in Pass 3.
      if (appMode == MODE_PRICE || appMode == MODE_CLOCK) drawAll();
    }
  } else if (wifiOk && priceOk && chartFetchDue(now)) {
    lastChartTryMs = now;
    if (fetchChart(rangeIdx)) {
      Serial.print("chart "); Serial.println(RANGES[rangeIdx].key);
      // Comparisons (R3): queue a re-align after a new chart lands
      // for a new range, or when the hourly refresh is due — one
      // asset per loop pass (see fetchOneCmpAsset). Queued assets
      // are marked not-ok until their own fetch lands, so a new
      // range never plots an old range's comparison line.
      if (cmpAnyOn() && (cmpRange != rangeIdx ||
                         now - cmpFetchedMs > 3600000UL)) {
        for (int c = 0; c < 3; c++) if (cmpOn[c]) {
          cmpPending |= (1 << c);
          cmpOk[c] = false;
        }
      }
      if (appMode == MODE_PRICE) drawAll();
    } else {
      Serial.println("chart fetch failed — keeping last chart");
      // Redraw on failure too (Pass 5 finding 6): clears a stale
      // "Fetching..." note, as in the price branch above.
      if (appMode == MODE_PRICE) drawAll();
    }
  } else if (wifiOk && now - lastBlockMs >= BLOCK_POLL_MS) {
    lastBlockMs = now;
    if (fetchBlockHeight()) {
      Serial.print("block "); Serial.println(blockHeight);
      if (appMode == MODE_PRICE || appMode == MODE_CLOCK) drawAll();
    } else {
      Serial.println("block fetch failed — keeping last height");
      // Redraw on failure too (Pass 5 finding 6): clears a stale
      // "Fetching..." note, as in the price branch above.
      if (appMode == MODE_PRICE || appMode == MODE_CLOCK) drawAll();
    }
  } else if (appMode == MODE_CLOCK && wifiOk &&
             (lastClockFetchMs == 0 || now - lastClockFetchMs >= 300000UL)) {
    lastClockFetchMs = now;  // set before the (blocking) fetch: no tight retry
    fetchClockData();
    drawAll();  // also on failure (Pass 5 finding 6): the redraw lands after the guard clears
  } else if (cmpPending != 0 && wifiOk) {
    fetchOneCmpAsset();
  }

  // --- Serial: USB provisioning for Auth accounts (ADD / LIST / DEL) ---
  handleSerial();

  // --- Touch ---
  if (now - lastTouchMs >= TOUCH_POLL_MS) {
    lastTouchMs = now;
    handleTouch();
  }

  delay(20);
}
