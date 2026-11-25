// WASM entry point: the SAME real sketch + stubs as the native sim,
// compiled to WebAssembly and driven from JS. The sketch is included
// read-only; nothing in it is modified.
// Data files are embedded at /data (see --embed-file); the HTTP stub
// serves them, so the sketch's "network" reads are the real fetched
// snapshot. JS may overwrite /data/*.json with live fetches before init.
#include <cstdio>
#include <cstdint>
#include <string>
#include <emscripten.h>
#include "sim.h"
#include "TFT_eSPI.h"

// Forward declarations the Arduino IDE normally auto-generates for .ino
// files (the sketch calls these before their definitions).
float rangeChange();
void savePrefs();

#include "/home/hatch/workspace/ps-keychain-firmware/paperstreet-keychain.ino"

extern "C" {

EMSCRIPTEN_KEEPALIVE
void sim_init() {
  g_dataDir = "/data";
  setup();
}

// Advance simulated time by `ms`, calling the sketch's loop().
// Mirrors the native harness's runLoopFor.
EMSCRIPTEN_KEEPALIVE
void sim_step(unsigned long ms) {
  unsigned long start = (unsigned long)simMillis;
  unsigned long target = start + ms;
  int guard = 0;
  while (simMillis < target && guard++ < 100000) loop();
}

// Touch, in DRAWING coords (what the user sees on screen).
EMSCRIPTEN_KEEPALIVE
void sim_touch_down(int dx, int dy) { simSetFinger(true, (int16_t)dx, (int16_t)dy); }
// A drag: same finger, new position — this is what makes a swipe
// reach the firmware's swipe recogniser (dx accumulates from the
// down position). Only called while the pointer is down (see index.html).
EMSCRIPTEN_KEEPALIVE
void sim_touch_move(int dx, int dy) { simSetFinger(true, (int16_t)dx, (int16_t)dy); }
// Lift, at the position the finger left the screen, so the final
// position reaches the firmware (swipe dx is measured to the lift).
EMSCRIPTEN_KEEPALIVE
void sim_touch_up(int dx, int dy) { simSetFinger(false, (int16_t)dx, (int16_t)dy); }

// Framebuffer: RGB565, row stride 320 px, active area
// sim_fb_width() x sim_fb_height() (170x320 portrait, 320x170 landscape).
EMSCRIPTEN_KEEPALIVE
const uint16_t *sim_fb_ptr() { return tft.framebuffer(); }
EMSCRIPTEN_KEEPALIVE
int sim_fb_width() { return tft.width(); }
EMSCRIPTEN_KEEPALIVE
int sim_fb_height() { return tft.height(); }
EMSCRIPTEN_KEEPALIVE
int sim_fb_stride() { return 320; }

// Sketch state for the page status line.
EMSCRIPTEN_KEEPALIVE
int sim_price_cents() { return (int)(priceUSD * 100.0f); }
EMSCRIPTEN_KEEPALIVE
int sim_landscape() { return tft.width() == 320 ? 1 : 0; }
EMSCRIPTEN_KEEPALIVE
int sim_price_ok() { return priceOk ? 1 : 0; }

}  // extern "C"
