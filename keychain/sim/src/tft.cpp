// TFT_eSPI stub: draws into a 320x320 RGB565 framebuffer.
//
// The smooth-font code (loadFont/loadMetrics/drawGlyph/textWidth/
// drawString/write, alphaBlend, drawWideLine/drawWedgeLine) is a
// faithful port of TFT_eSPI's Smooth_font.cpp and Smooth_font.h,
// with setWindow/pushColor replaced by direct setPixel calls
// (pixel-identical: the window only batches pixels, it does not
// change them). Bitmap fonts (fontdata.h) stay as the fallback when
// no smooth font is loaded — exactly like the real library, where
// a loaded smooth font overrides textfont.
//
// Glyph bitmaps are 1 byte/px alpha starting at 24+28*gCount in the
// .vlw file; the space U+0020 is NOT in the table and is handled
// via spaceWidth=(ascent+descent)*2/7.
#include "TFT_eSPI.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>

void TFT_eSPI::init() { memset(fb_, 0, sizeof(fb_)); rot_ = 0; }
void TFT_eSPI::setRotation(int r) { rot_ = r & 3; }
int16_t TFT_eSPI::width() const { return (rot_ & 1) ? 320 : 170; }
int16_t TFT_eSPI::height() const { return (rot_ & 1) ? 170 : 320; }

void TFT_eSPI::setPixel(int x, int y, uint16_t c) {
  if (x < 0 || y < 0 || x >= width() || y >= height()) return;
  fb_[y * 320 + x] = c;
}

void TFT_eSPI::fillScreen(uint16_t c) { fillRect(0, 0, width(), height(), c); }

void TFT_eSPI::fillRect(int x, int y, int w, int h, uint16_t c) {
  if (w <= 0 || h <= 0) return;
  int x0 = x < 0 ? 0 : x, y0 = y < 0 ? 0 : y;
  int x1 = x + w > width() ? width() : x + w;
  int y1 = y + h > height() ? height() : y + h;
  for (int yy = y0; yy < y1; yy++)
    for (int xx = x0; xx < x1; xx++)
      fb_[yy * 320 + xx] = c;
}

void TFT_eSPI::drawRect(int x, int y, int w, int h, uint16_t c) {
  drawFastHLine(x, y, w, c);
  drawFastHLine(x, y + h - 1, w, c);
  drawFastVLine(x, y, h, c);
  drawFastVLine(x + w - 1, y, h, c);
}

void TFT_eSPI::fillRoundRect(int x, int y, int w, int h, int r, uint16_t c) {
  if (r <= 0) { fillRect(x, y, w, h, c); return; }
  fillRect(x + r, y, w - 2 * r, h, c);
  fillRect(x, y + r, w, h - 2 * r, c);
  fillCircle(x + r, y + r, r, c);
  fillCircle(x + w - r - 1, y + r, r, c);
  fillCircle(x + r, y + h - r - 1, r, c);
  fillCircle(x + w - r - 1, y + h - r - 1, r, c);
}

void TFT_eSPI::drawRoundRect(int x, int y, int w, int h, int r, uint16_t c) {
  if (r <= 0) { drawRect(x, y, w, h, c); return; }
  drawFastHLine(x + r, y, w - 2 * r, c);
  drawFastHLine(x + r, y + h - 1, w - 2 * r, c);
  drawFastVLine(x, y + r, h - 2 * r, c);
  drawFastVLine(x + w - 1, y + r, h - 2 * r, c);
  // corner arcs (quarter circles)
  for (int i = 0; i <= r; i++) {
    int dx = (int)sqrt((double)(r * r - i * i));
    setPixel(x + r - dx, y + r - i, c);
    setPixel(x + w - r - 1 + dx, y + r - i, c);
    setPixel(x + r - dx, y + h - r - 1 + i, c);
    setPixel(x + w - r - 1 + dx, y + h - r - 1 + i, c);
  }
}

// Anti-aliased filled rounded rect — a faithful port of TFT_eSPI's
// fillSmoothRoundRect (same signature, same rule: edge pixels blend
// the fill colour over the `bg` colour passed in; the display is
// never read back, so a wrong `bg` shows a halo on real hardware
// exactly as it does here). Coverage comes from the signed distance
// to the rounded-rect edge (iq's sdRoundBox), so the curve gets a
// 1 px ramp — the same soft edge the real library draws.
void TFT_eSPI::fillSmoothRoundRect(int32_t x, int32_t y, int32_t w, int32_t h,
                                   int32_t r, uint16_t color, uint16_t bg) {
  if (w <= 0 || h <= 0) return;
  if (r < 0) r = 0;
  int32_t rmax = (w < h ? w : h) / 2;
  if (r > rmax) r = rmax;
  if (r == 0) { fillRect(x, y, w, h, color); return; }
  float cx = x + w / 2.0f, cy = y + h / 2.0f;
  float hx = w / 2.0f - r, hy = h / 2.0f - r;
  for (int32_t yy = y; yy < y + h; yy++) {
    for (int32_t xx = x; xx < x + w; xx++) {
      float qx = fabsf((float)xx + 0.5f - cx) - hx;
      float qy = fabsf((float)yy + 0.5f - cy) - hy;
      float ox = qx > 0 ? qx : 0, oy = qy > 0 ? qy : 0;
      float inside = qx > qy ? (qx < 0 ? qx : 0) : (qy < 0 ? qy : 0);
      float d = sqrtf(ox * ox + oy * oy) + inside - r;
      float cov = 0.5f - d;
      if (cov <= 0) continue;
      if (cov >= 1) setPixel(xx, yy, color);
      else setPixel(xx, yy, alphaBlend((uint8_t)(cov * 255.0f), color, bg));
    }
  }
}

void TFT_eSPI::drawLine(int x0, int y0, int x1, int y1, uint16_t c) {
  int dx = abs(x1 - x0), sx = x0 < x1 ? 1 : -1;
  int dy = -abs(y1 - y0), sy = y0 < y1 ? 1 : -1;
  int err = dx + dy;
  for (;;) {
    setPixel(x0, y0, c);
    if (x0 == x1 && y0 == y1) break;
    int e2 = 2 * err;
    if (e2 >= dy) { err += dy; x0 += sx; }
    if (e2 <= dx) { err += dx; y0 += sy; }
  }
}

void TFT_eSPI::drawFastVLine(int x, int y, int h, uint16_t c) {
  for (int i = 0; i < h; i++) setPixel(x, y + i, c);
}
void TFT_eSPI::drawFastHLine(int x, int y, int w, uint16_t c) {
  for (int i = 0; i < w; i++) setPixel(x + i, y, c);
}

void TFT_eSPI::fillCircle(int x, int y, int r, uint16_t c) {
  if (r < 0) return;
  for (int dy = -r; dy <= r; dy++) {
    int dx = (int)sqrt((double)(r * r - dy * dy));
    drawFastHLine(x - dx, y + dy, 2 * dx + 1, c);
  }
}

void TFT_eSPI::drawCircle(int x, int y, int r, uint16_t c) {
  if (r < 0) return;
  int xx = 0, yy = r, d = 3 - 2 * r;
  while (yy >= xx) {
    setPixel(x + xx, y + yy, c); setPixel(x - xx, y + yy, c);
    setPixel(x + xx, y - yy, c); setPixel(x - xx, y - yy, c);
    setPixel(x + yy, y + xx, c); setPixel(x - yy, y + xx, c);
    setPixel(x + yy, y - xx, c); setPixel(x - yy, y - xx, c);
    if (d < 0) d += 4 * xx + 6;
    else { d += 4 * (xx - yy) + 10; yy--; }
    xx++;
  }
}

void TFT_eSPI::fillTriangle(int x0, int y0, int x1, int y1,
                            int x2, int y2, uint16_t c) {
  // sort vertices by y
  if (y0 > y1) { int t = y0; y0 = y1; y1 = t; t = x0; x0 = x1; x1 = t; }
  if (y1 > y2) { int t = y1; y1 = y2; y2 = t; t = x1; x1 = x2; x2 = t; }
  if (y0 > y1) { int t = y0; y0 = y1; y1 = t; t = x0; x0 = x1; x1 = t; }
  int totalHeight = y2 - y0;
  if (totalHeight == 0) return;
  for (int i = 0; i < totalHeight; i++) {
    bool secondHalf = i > y1 - y0 || y1 == y0;
    int segmentHeight = secondHalf ? y2 - y1 : y1 - y0;
    if (segmentHeight == 0) continue;
    float alpha = (float)i / totalHeight;
    float beta = (float)(i - (secondHalf ? y1 - y0 : 0)) / segmentHeight;
    int ax = x0 + (int)((x2 - x0) * alpha);
    int bx = secondHalf ? x1 + (int)((x2 - x1) * beta)
                        : x0 + (int)((x1 - x0) * beta);
    if (ax > bx) { int t = ax; ax = bx; bx = t; }
    drawFastHLine(ax, y0 + i, bx - ax + 1, c);
  }
}

void TFT_eSPI::drawPixel(int32_t x, int32_t y, uint32_t c) {
  setPixel((int)x, (int)y, (uint16_t)c);
}

uint16_t TFT_eSPI::readPixel(int32_t x, int32_t y) {
  if (x < 0 || y < 0 || x >= width() || y >= height()) return 0;
  return fb_[y * 320 + x];
}

// Block read/write (faithful to the real TFT_eSPI: the block is
// row-major with stride w, in drawing coordinates, clipped to the
// screen — the same window the real library sets before the burst
// transfer). Used by the swipe slide animation (readRect captures
// the outgoing page, pushImage pushes its remaining strip).
void TFT_eSPI::readRect(int32_t x, int32_t y, int32_t w, int32_t h, uint16_t *data) {
  for (int32_t j = 0; j < h; j++)
    for (int32_t i = 0; i < w; i++)
      data[j * w + i] = readPixel(x + i, y + j);
}

void TFT_eSPI::pushImage(int32_t x, int32_t y, int32_t w, int32_t h, uint16_t *data) {
  for (int32_t j = 0; j < h; j++)
    for (int32_t i = 0; i < w; i++)
      setPixel((int)(x + i), (int)(y + j), data[j * w + i]);
}

uint16_t TFT_eSPI::color16to24(uint16_t c565) {
  return (uint16_t)(((c565 >> 11) & 31) * 255 / 31) << 16 |
         (uint16_t)(((c565 >> 5) & 63) * 255 / 63) << 8 |
         (uint16_t)((c565 & 31) * 255 / 31);
}

// --- alpha blending (exact TFT_eSPI formula) ---
uint16_t TFT_eSPI::alphaBlend(uint8_t alpha, uint16_t fgc, uint16_t bgc) {
  uint16_t rxb = bgc & 0xF81F;
  rxb += ((fgc & 0xF81F) - rxb) * (alpha >> 2) >> 6;
  uint16_t xgx = bgc & 0x07E0;
  xgx += ((fgc & 0x07E0) - xgx) * alpha >> 8;
  return (rxb & 0xF81F) | (xgx & 0x07E0);
}
uint16_t TFT_eSPI::alphaBlend(uint8_t alpha, uint32_t fgc, uint32_t bgc) {
  // 24-bit overload (used by the wide-line code when a colour is
  // passed as 0xRRGGBB)
  uint8_t fr = (fgc >> 16) & 0xFF, fg = (fgc >> 8) & 0xFF, fb = fgc & 0xFF;
  uint8_t br = (bgc >> 16) & 0xFF, bg = (bgc >> 8) & 0xFF, bb = bgc & 0xFF;
  uint8_t r = br + (fr - br) * alpha / 255;
  uint8_t g = bg + (fg - bg) * alpha / 255;
  uint8_t b = bb + (fb - bb) * alpha / 255;
  return (uint16_t)(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3));
}

// --- anti-aliased wide line (port of TFT_eSPI's drawWideLine /
// drawWedgeLine / wedgeLineDistance, exact thresholds and math) ---
float TFT_eSPI::wedgeLineDistance(float xp, float yp, float x0, float y0,
                                  float x1, float y1) {
  float dx = x1 - x0, dy = y1 - y0;
  float len = sqrt(dx * dx + dy * dy);
  if (len == 0) return sqrt((xp - x0) * (xp - x0) + (yp - y0) * (yp - y0));
  float t = ((xp - x0) * dx + (yp - y0) * dy) / (len * len);
  if (t < 0) t = 0; if (t > 1) t = 1;
  float px = x0 + t * dx, py = y0 + t * dy;
  return sqrt((xp - px) * (xp - px) + (yp - py) * (yp - py));
}

void TFT_eSPI::drawWedgeLine(float ax, float ay, float bx, float by,
                             float ar, float aw, uint32_t fg, uint32_t bg) {
  const float Lo = 1.0f / 32.0f, Hi = 1.0f - Lo;
  const float PixelAlphaGain = 255.0f;
  float dx = bx - ax, dy = by - ay;
  float len = sqrt(dx * dx + dy * dy);
  if (len == 0) return;
  float invLen = 1.0f / len;
  // scan the bounding box, two passes (down from ys, up from ys-1)
  float minx = fminf(ax, bx) - aw - 1, maxx = fmaxf(ax, bx) + aw + 1;
  float miny = fminf(ay, by) - aw - 1, maxy = fmaxf(ay, by) + aw + 1;
  for (int yy = (int)floorf(miny); yy <= (int)ceilf(maxy); yy++) {
    for (int xx = (int)floorf(minx); xx <= (int)ceilf(maxx); xx++) {
      float dist = wedgeLineDistance((float)xx + 0.5f, (float)yy + 0.5f,
                                     ax, ay, bx, by);
      float h = 0;
      if (dist < ar) h = 1.0f;
      else if (dist < aw) h = (aw - dist) / (aw - ar);
      if (h <= 0) continue;
      // the wedge tapers from ar at the start to aw at the end
      float t = ((xx + 0.5f - ax) * dx + (yy + 0.5f - ay) * dy) * invLen * invLen;
      if (t < 0) t = 0; if (t > 1) t = 1;
      float hw = ar + (aw - ar) * t;
      float d = dist;
      float alpha = 0;
      if (d <= hw - 0.5f) alpha = 1.0f;
      else if (d < hw + 0.5f) alpha = hw + 0.5f - d;
      if (alpha <= 0) continue;
      if (alpha < Lo) alpha = 0;
      else if (alpha > Hi) alpha = 1.0f;
      uint8_t a = (uint8_t)(alpha * PixelAlphaGain);
      if (a == 0) continue;
      if (a == 255) {
        setPixel(xx, yy, (uint16_t)fg);
      } else {
        uint16_t bgc = (bg == 0x00FFFFFF) ? readPixel(xx, yy) : (uint16_t)bg;
        setPixel(xx, yy, alphaBlend(a, (uint16_t)fg, bgc));
      }
    }
  }
}

void TFT_eSPI::drawWideLine(float ax, float ay, float bx, float by,
                            float wd, uint32_t fg, uint32_t bg) {
  if (wd <= 0) return;
  float ar = wd / 2.0f;
  drawWedgeLine(ax, ay, bx, by, ar, ar, fg, bg);
}

void TFT_eSPI::drawWideLine(float ax, float ay, float bx, float by,
                            float wd, uint16_t fg) {
  drawWideLine(ax, ay, bx, by, wd, (uint32_t)fg, 0x00FFFFFF);
}

// --- bitmap text (fallback when no smooth font is loaded) ---
const SimFont *TFT_eSPI::curFont() const {
  switch (font_) {
    case 1: return &simFont1;
    case 2: return &simFont2;
    case 4: return &simFont4;
    case 6: return &simFont6;
    default: return &simFont1;
  }
}

void TFT_eSPI::setTextFont(int f) {
  if (fontLoaded) unloadFont();
  font_ = f;
}
void TFT_eSPI::setTextColor(uint16_t fg, uint16_t bg) { fg_ = fg; bg_ = bg; fillbg_ = false; }
void TFT_eSPI::setTextColor(uint16_t fg, uint16_t bg, bool bgfill) { fg_ = fg; bg_ = bg; fillbg_ = bgfill; }
void TFT_eSPI::setTextDatum(int d) { datum_ = d; }
void TFT_eSPI::setCursor(int x, int y) { cx_ = x; cy_ = y; cursorX_ = (int16_t)x; cursorY_ = (int16_t)y; }

int32_t TFT_eSPI::readInt32(fs::File &f) {
  uint8_t b[4];
  if (f.read(b, 4) != 4) return 0;
  return (int32_t)((uint32_t)b[0] << 24 | (uint32_t)b[1] << 16 |
                   (uint32_t)b[2] << 8 | (uint32_t)b[3]);
}

bool TFT_eSPI::loadMetrics(fs::File &f, bool debug) {
  (void)debug;
  if (gGlyph) { free(gGlyph); gGlyph = nullptr; }
  if (gBitmap) { free(gBitmap); gBitmap = nullptr; }
  gFont.gCount = readInt32(f);
  int32_t version = readInt32(f);
  (void)version;
  gFont.fontSize = readInt32(f);
  int32_t mboxY = readInt32(f);
  (void)mboxY;
  gFont.ascent = readInt32(f);
  gFont.descent = readInt32(f);
  gFont.spaceWidth = (gFont.ascent + gFont.descent) * 2 / 7;
  gFont.yAdvance = gFont.maxAscent + gFont.maxDescent;
  if (gFont.gCount <= 0) return false;
  gGlyph = (fontGlyph *)malloc(sizeof(fontGlyph) * (size_t)gFont.gCount);
  if (!gGlyph) return false;
  int32_t maxDescent = 0, maxAscent = 0;
  for (int32_t i = 0; i < gFont.gCount; i++) {
    gGlyph[i].unicode = (uint32_t)readInt32(f);
    gGlyph[i].height = readInt32(f);
    gGlyph[i].width = readInt32(f);
    gGlyph[i].gxAdvance = readInt32(f);
    gGlyph[i].gdY = readInt32(f);
    gGlyph[i].gdX = readInt32(f);
    readInt32(f);  // padding
    if (gGlyph[i].gdY > maxAscent) maxAscent = gGlyph[i].gdY;
    int32_t desc = gGlyph[i].height - gGlyph[i].gdY;
    if (desc > maxDescent) maxDescent = desc;
  }
  maxAscent_ = (int16_t)maxAscent;
  maxDescent_ = (int16_t)maxDescent;
  gFont.yAdvance = maxAscent + maxDescent;
  // bitmaps: 1 byte/px alpha, starting at 24+28*gCount
  size_t total = 0;
  for (int32_t i = 0; i < gFont.gCount; i++)
    total += (size_t)gGlyph[i].width * (size_t)gGlyph[i].height;
  gBitmap = (uint8_t *)malloc(total > 0 ? total : 1);
  if (!gBitmap) return false;
  uint32_t ptr = 0;
  for (int32_t i = 0; i < gFont.gCount; i++) {
    gGlyph[i].dataPtr = ptr;
    size_t n = (size_t)gGlyph[i].width * (size_t)gGlyph[i].height;
    if (n > 0) {
      if (f.read(gBitmap + ptr, n) != n) { /* short file: pad with 0 */ }
      ptr += (uint32_t)n;
    }
  }
  gFontDataPtr = (int32_t)ptr;
  return true;
}

void TFT_eSPI::loadFont(const char *name, fs::FS &fs) {
  if (fontLoaded) unloadFont();
  if (!name) return;
  std::string path = std::string(name) + ".vlw";
  fs::File f = fs.open(path.c_str());
  if (!f) {
    fprintf(stderr, "[sim] font file %s not found\n", path.c_str());
    return;
  }
  if (loadMetrics(f, false)) fontLoaded = true;
  f.close();
}

void TFT_eSPI::unloadFont() {
  if (gGlyph) { free(gGlyph); gGlyph = nullptr; }
  if (gBitmap) { free(gBitmap); gBitmap = nullptr; }
  fontLoaded = false;
  memset(&gFont, 0, sizeof(gFont));
}

uint16_t TFT_eSPI::getUnicodeIndex(uint16_t unicode, bool *isDigits) {
  *isDigits = false;
  if (unicode >= '0' && unicode <= '9') *isDigits = true;
  for (int32_t i = 0; i < gFont.gCount; i++) {
    if (gGlyph[i].unicode == unicode) return (uint16_t)i;
  }
  return 0xFFFF;
}

void TFT_eSPI::drawSmoothGlyph(uint16_t code) {
  if (!fontLoaded) return;
  bool isDigits = false;
  uint16_t index = getUnicodeIndex(code, &isDigits);
  if (code == 0x20) {
    cursorX_ += gFont.spaceWidth;
    return;
  }
  if (index == 0xFFFF) {
    cursorX_ += gFont.spaceWidth + 1;
    return;
  }
  const fontGlyph &g = gGlyph[index];
  int16_t cy = cursorY_ + maxAscent_ - (int16_t)g.gdY;
  int16_t cx = cursorX_ + (int16_t)g.gdX;
  for (int32_t y = 0; y < g.height; y++) {
    for (int32_t x = 0; x < g.width; x++) {
      uint8_t pixel = gBitmap[g.dataPtr + (uint32_t)y * (uint32_t)g.width + (uint32_t)x];
      if (pixel == 0xFF) {
        setPixel(cx + x, cy + y, fg_);
      } else if (pixel > 0) {
        uint16_t bgc = readPixel(cx + x, cy + y);
        setPixel(cx + x, cy + y, alphaBlend(pixel, fg_, bgc));
      } else if (fillbg_) {
        setPixel(cx + x, cy + y, bg_);
      }
    }
  }
  cursorX_ += (int16_t)g.gxAdvance;
}

int16_t TFT_eSPI::textWidth(const char *s) {
  if (fontLoaded) {
    int32_t total = 0;
    int n = (int)strlen(s);
    for (int i = 0; i < n; i++) {
      uint16_t code = (uint8_t)s[i];
      if (code == 0x20) { total += gFont.spaceWidth; continue; }
      bool isDigits = false;
      uint16_t index = getUnicodeIndex(code, &isDigits);
      if (index == 0xFFFF) { total += gFont.spaceWidth + 1; continue; }
      const fontGlyph &g = gGlyph[index];
      if (i == n - 1) total += g.gdX + g.width;
      else total += g.gxAdvance;
      if (i == 0 && g.gdX < 0) total -= g.gdX;
    }
    return (int16_t)total;
  }
  const SimFont *f = curFont();
  int w = 0;
  for (const char *p = s; *p; p++) {
    unsigned char ch = (unsigned char)*p;
    if (ch < 32 || ch > 126) ch = 32;
    w += f->glyphs[ch - 32].adv;
  }
  return (int16_t)w;
}

int16_t TFT_eSPI::fontHeight() {
  if (fontLoaded) return (int16_t)gFont.yAdvance;
  return (int16_t)curFont()->cell_h;
}

void TFT_eSPI::drawGlyph(int x, int y, char ch) {
  const SimFont *f = curFont();
  unsigned char c = (unsigned char)ch;
  if (c < 32 || c > 126) c = 32;
  const SimGlyph &g = f->glyphs[c - 32];
  int adv = g.adv, cell_h = f->cell_h;
  for (int row = 0; row < cell_h; row++) {
    for (int col = 0; col < adv; col++) {
      size_t bit = (size_t)g.off + (size_t)row * adv + col;
      if ((f->bits[bit >> 3] >> (7 - (bit & 7))) & 1)
        setPixel(x + col, y + row, fg_);
    }
  }
}

void TFT_eSPI::drawString(const char *s, int x, int y) {
  if (fontLoaded) {
    int16_t w = textWidth(s);
    int16_t h = fontHeight();
    int16_t x0 = (int16_t)x, y0 = (int16_t)y;
    if (datum_ == MC_DATUM) { x0 = (int16_t)x - w / 2; y0 = (int16_t)y - h / 2; }
    // cursorY_ is the TOP of the text; drawSmoothGlyph adds
    // maxAscent (baseline = top + maxAscent) when placing glyphs.
    cursorX_ = x0; cursorY_ = y0;
    // background fill (only when bgfill is on)
    if (fillbg_) fillRect(x0, y0, w, h, bg_);
    for (const char *p = s; *p; p++) drawSmoothGlyph((uint16_t)(uint8_t)*p);
    return;
  }
  const SimFont *f = curFont();
  int16_t w = textWidth(s);
  int x0 = x, y0 = y;
  if (datum_ == MC_DATUM) { x0 = x - w / 2; y0 = y - f->cell_h / 2; }
  fillRect(x0, y0, w, f->cell_h, bg_);
  int cx = x0;
  for (const char *p = s; *p; p++) {
    drawGlyph(cx, y0, *p);
    unsigned char ch = (unsigned char)*p;
    if (ch < 32 || ch > 126) ch = 32;
    cx += f->glyphs[ch - 32].adv;
  }
}

void TFT_eSPI::print(const char *s) {
  if (fontLoaded) {
    // cursor is the TOP of the text (as set by setCursor);
    // drawSmoothGlyph adds maxAscent when placing glyphs.
    cursorX_ = cx_; cursorY_ = cy_;
    for (const char *p = s; *p; p++) drawSmoothGlyph((uint16_t)(uint8_t)*p);
    cx_ = cursorX_;
    return;
  }
  const SimFont *f = curFont();
  int16_t w = textWidth(s);
  fillRect(cx_, cy_, w, f->cell_h, bg_);
  int x = cx_;
  for (const char *p = s; *p; p++) {
    drawGlyph(x, cy_, *p);
    unsigned char ch = (unsigned char)*p;
    if (ch < 32 || ch > 126) ch = 32;
    x += f->glyphs[ch - 32].adv;
  }
  cx_ += w;
}
void TFT_eSPI::print(const String &s) { print(s.c_str()); }
void TFT_eSPI::print(int v) { char b[16]; snprintf(b, sizeof(b), "%d", v); print(b); }
void TFT_eSPI::print(unsigned long v) { char b[24]; snprintf(b, sizeof(b), "%lu", v); print(b); }
void TFT_eSPI::print(float v) { char b[24]; snprintf(b, sizeof(b), "%f", (double)v); print(b); }

void TFT_eSPI::dumpPPM(const char *path) {
  FILE *f = fopen(path, "wb");
  if (!f) { fprintf(stderr, "[sim] cannot write frame %s\n", path); return; }
  int w = width(), h = height();
  fprintf(f, "P6\n%d %d\n255\n", w, h);
  for (int y = 0; y < h; y++) {
    for (int x = 0; x < w; x++) {
      uint16_t v = fb_[y * 320 + x];
      uint8_t px[3];
      px[0] = (uint8_t)(((v >> 11) & 31) * 255 / 31);
      px[1] = (uint8_t)(((v >> 5) & 63) * 255 / 63);
      px[2] = (uint8_t)((v & 31) * 255 / 31);
      fwrite(px, 1, 3, f);
    }
  }
  fclose(f);
}
