#pragma once
#include <Arduino.h>
#include <stdint.h>
#include <string.h>
#include "FS.h"
#include "fontdata.h"

#ifndef MC_DATUM
#define TL_DATUM 0
#define TC_DATUM 1
#define TR_DATUM 2
#define ML_DATUM 3
#define MC_DATUM 4
#define MR_DATUM 5
#define BL_DATUM 6
#define BC_DATUM 7
#define BR_DATUM 8
#endif

struct fontMetrics {
  int32_t gCount = 0;
  int32_t fontSize = 0;
  int32_t ascent = 0;
  int32_t descent = 0;
  int32_t spaceWidth = 0;
  int32_t yAdvance = 0;
  int32_t maxAscent = 0;
  int32_t maxDescent = 0;
};

struct fontGlyph {
  uint32_t unicode = 0;
  int32_t height = 0;
  int32_t width = 0;
  int32_t gxAdvance = 0;
  int32_t gdY = 0;
  int32_t gdX = 0;
  uint32_t dataPtr = 0;
};

class TFT_eSPI {
public:
  bool fontLoaded = false;
  void init();
  void setRotation(int r);
  int16_t width() const;
  int16_t height() const;
  void fillScreen(uint16_t c);
  void fillRect(int x, int y, int w, int h, uint16_t c);
  void drawRect(int x, int y, int w, int h, uint16_t c);
  void fillRoundRect(int x, int y, int w, int h, int r, uint16_t c);
  void drawRoundRect(int x, int y, int w, int h, int r, uint16_t c);
  void fillSmoothRoundRect(int32_t x, int32_t y, int32_t w, int32_t h,
                           int32_t r, uint16_t color, uint16_t bg);
  void drawLine(int x0, int y0, int x1, int y1, uint16_t c);
  void drawFastVLine(int x, int y, int h, uint16_t c);
  void drawFastHLine(int x, int y, int w, uint16_t c);
  void fillCircle(int x, int y, int r, uint16_t c);
  void drawCircle(int x, int y, int r, uint16_t c);
  void fillTriangle(int x0, int y0, int x1, int y1, int x2, int y2, uint16_t c);
  void drawPixel(int32_t x, int32_t y, uint32_t c);
  uint16_t readPixel(int32_t x, int32_t y);
  void readRect(int32_t x, int32_t y, int32_t w, int32_t h, uint16_t *data);
  void pushImage(int32_t x, int32_t y, int32_t w, int32_t h, uint16_t *data);
  uint16_t color16to24(uint16_t c565);
  uint16_t alphaBlend(uint8_t alpha, uint16_t fgc, uint16_t bgc);
  uint16_t alphaBlend(uint8_t alpha, uint32_t fgc, uint32_t bgc);
  void drawWedgeLine(float ax, float ay, float bx, float by,
                     float ar, float br, uint32_t fg, uint32_t bg);
  void drawWideLine(float ax, float ay, float bx, float by,
                    float wd, uint32_t fg, uint32_t bg);
  void drawWideLine(float ax, float ay, float bx, float by,
                    float wd, uint16_t fg);
  float wedgeLineDistance(float xp, float yp, float x0, float y0,
                          float x1, float y1);
  void setTextFont(int f);
  void setTextColor(uint16_t fg, uint16_t bg);
  void setTextColor(uint16_t fg, uint16_t bg, bool bgfill);
  void setTextDatum(int d);
  void setCursor(int x, int y);
  void loadFont(const char *name, fs::FS &fs);
  void unloadFont();
  int16_t textWidth(const char *s);
  int16_t fontHeight();
  void drawString(const char *s, int x, int y);
  void print(const char *s);
  void print(const String &s);
  void print(int v);
  void print(unsigned long v);
  void print(float v);
  void dumpPPM(const char *path);
  const uint16_t *framebuffer() const { return fb_; }
  uint16_t *framebuffer() { return fb_; }

private:
  void setPixel(int x, int y, uint16_t c);
  const SimFont *curFont() const;
  int32_t readInt32(fs::File &f);
  bool loadMetrics(fs::File &f, bool debug);
  uint16_t getUnicodeIndex(uint16_t unicode, bool *isDigits);
  void drawSmoothGlyph(uint16_t code);
  void drawGlyph(int x, int y, char ch);

  uint16_t fb_[320 * 320]{};
  int rot_ = 0;
  int font_ = 1;
  uint16_t fg_ = 0xFFFF, bg_ = 0;
  bool fillbg_ = false;
  int datum_ = TL_DATUM;
  int cx_ = 0, cy_ = 0;
  int16_t cursorX_ = 0, cursorY_ = 0;
  fontMetrics gFont{};
  fontGlyph *gGlyph = nullptr;
  uint8_t *gBitmap = nullptr;
  int32_t gFontDataPtr = 0;
  int16_t maxAscent_ = 0, maxDescent_ = 0;
};

extern TFT_eSPI tft;
