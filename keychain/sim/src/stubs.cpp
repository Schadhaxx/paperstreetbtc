// Stub implementations: sim clock, pins, Serial, WiFi, HTTP, Preferences, Wire.
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <LittleFS.h>
#include <Wire.h>
#include <stdio.h>
#include <stdlib.h>
#include <string>

uint64_t simMillis = 0;
std::string g_dataDir = "data";
bool simFingerDown = false;
int16_t simFingerDX = 0, simFingerDY = 0;

void simSetFinger(bool down, int16_t dx, int16_t dy) {
  simFingerDown = down; simFingerDX = dx; simFingerDY = dy;
}

unsigned long millis() { return (unsigned long)simMillis; }
void delay(unsigned long ms) { simMillis += ms; }
void pinMode(int pin, int mode) { (void)pin; (void)mode; }
void digitalWrite(int pin, int val) { (void)pin; (void)val; }
int analogReadMilliVolts(int pin) { (void)pin; return 0; }  // USB power -> shows "USB"

// --- Serial ---
SerialClass Serial;
LittleFSClass LittleFS;
void SerialClass::begin(unsigned long baud) { (void)baud; }
void SerialClass::println(const char *s) { fprintf(stderr, "%s\n", s ? s : ""); }
void SerialClass::println(const String &s) { fprintf(stderr, "%s\n", s.c_str()); }
void SerialClass::println(int v) { fprintf(stderr, "%d\n", v); }
void SerialClass::println(long v) { fprintf(stderr, "%ld\n", v); }
void SerialClass::println(unsigned long v) { fprintf(stderr, "%lu\n", v); }
void SerialClass::println(float v) { fprintf(stderr, "%f\n", (double)v); }
void SerialClass::println() { fprintf(stderr, "\n"); }
void SerialClass::print(const char *s) { fprintf(stderr, "%s", s ? s : ""); }
void SerialClass::print(const String &s) { fprintf(stderr, "%s", s.c_str()); }
void SerialClass::print(int v) { fprintf(stderr, "%d", v); }
void SerialClass::print(long v) { fprintf(stderr, "%ld", v); }
void SerialClass::print(unsigned long v) { fprintf(stderr, "%lu", v); }
void SerialClass::print(float v) { fprintf(stderr, "%f", (double)v); }
int SerialClass::available() { return 0; }
int SerialClass::read() { return -1; }

// --- ESP32 time helpers ---
void configTime(long gmtOffset_sec, int daylightOffset_sec,
                const char *server1, const char *server2,
                const char *server3) {
  (void)gmtOffset_sec; (void)daylightOffset_sec;
  (void)server1; (void)server2; (void)server3;
  tzset();
}
bool getLocalTime(struct tm *info, uint32_t ms) {
  (void)ms;
  time_t t = time(nullptr);
  if (t < 1700000000L) return false;
  return localtime_r(&t, info) != nullptr;
}

// --- WiFi ---
WiFiClass WiFi;

// --- HTTP: serve a real data file by URL ---
static bool readFile(const std::string &path, std::string &out) {
  FILE *f = fopen(path.c_str(), "rb");
  if (!f) return false;
  fseek(f, 0, SEEK_END);
  long n = ftell(f);
  fseek(f, 0, SEEK_SET);
  out.resize(n > 0 ? (size_t)n : 0);
  if (n > 0) (void)fread(&out[0], 1, (size_t)n, f);
  fclose(f);
  return true;
}

bool HTTPClient::begin(WiFiClientSecure &client, const char *url) {
  (void)client;
  url_ = url ? url : "";
  std::string file;
  if (url_.find("api.coingecko.com") != std::string::npos) {
    file = "coingecko.json";
  } else if (url_.find("api.coinbase.com/v2/prices") != std::string::npos) {
    file = "coinbase-spot.json";
  } else if (url_.find("api.exchange.coinbase.com") != std::string::npos) {
    size_t p = url_.find("granularity=");
    if (p == std::string::npos) return false;
    int gran = atoi(url_.c_str() + p + 12);
    char nb[32];
    snprintf(nb, sizeof(nb), "candles-%d.json", gran);
    file = nb;
  } else if (url_.find("paperstreetbtc.com/assets/data/") != std::string::npos) {
    // btc/spx/gold/mstr-daily.json — the file name is the URL basename.
    size_t p = url_.rfind('/');
    if (p == std::string::npos) return false;
    file = url_.substr(p + 1);
  } else if (url_.find("mempool.space/api/blocks/tip/height") != std::string::npos) {
    file = "block-height.txt";
  } else if (url_.find("mempool.space/api/blocks") != std::string::npos) {
    // /api/blocks: synthesised with a FRESH timestamp (now - 252 s),
    // so the block clock's "X min SS s ago" reads live in the sim.
    // The height comes from the (page-refreshed) block-height.txt.
    // If the file is missing or unparseable the height is 0, NOT a
    // hardcoded fallback (Pass 5 finding 7): the old 977242 fallback
    // was a real-looking but stale height the clock then held until
    // its next fetch, and 0 makes the firmware show "--" instead of
    // a wrong number. (Checked before the /api/v1/... branches below;
    // tip/height is checked first because it also contains "api/blocks".)
    long height = 0;
    std::string heightText;
    if (readFile(g_dataDir + "/block-height.txt", heightText)) {
      char *end = nullptr;
      long parsed = strtol(heightText.c_str(), &end, 10);
      if (end != heightText.c_str() && parsed > 900000 && parsed < 1100000)
        height = parsed;
    }
    char buf[256];
    time_t now = time(nullptr);
    snprintf(buf, sizeof(buf),
             "[{\"height\":%ld,\"timestamp\":%ld,\"tx_count\":3120,"
             "\"size\":1234567,\"weight\":4938264}]",
             height, (long)(now - 252));
    stream_.setData(buf);
    code_ = 200;
    return true;
  } else if (url_.find("mempool.space/api/v1/difficulty-adjustment") != std::string::npos) {
    file = "difficulty-adjustment.json";
  } else if (url_.find("mempool.space/api/v1/fees/recommended") != std::string::npos) {
    file = "fees-recommended.json";
  } else if (url_.find("mempool.space/api/mempool") != std::string::npos) {
    file = "mempool.json";
  } else {
    return false;
  }
  std::string content;
  if (!readFile(g_dataDir + "/" + file, content)) {
    fprintf(stderr, "[sim] HTTP stub: missing data file %s for %s\n",
            file.c_str(), url_.c_str());
    return false;
  }
  stream_.setData(content);
  code_ = 200;
  return true;
}
int HTTPClient::GET() { return code_; }

// --- Preferences ---
void Preferences::putFloat(const char *k, float v) {
  char b[32]; snprintf(b, sizeof(b), "%.9g", (double)v); kv_[k] = b;
}
void Preferences::putBool(const char *k, bool v) { kv_[k] = v ? "1" : "0"; }
void Preferences::putInt(const char *k, int v) {
  char b[32]; snprintf(b, sizeof(b), "%d", v); kv_[k] = b;
}
void Preferences::putString(const char *k, const char *v) { kv_[k] = v ? v : ""; }
float Preferences::getFloat(const char *k, float def) {
  auto it = kv_.find(k); return it == kv_.end() ? def : (float)atof(it->second.c_str());
}
bool Preferences::getBool(const char *k, bool def) {
  auto it = kv_.find(k); return it == kv_.end() ? def : (it->second == "1");
}
int Preferences::getInt(const char *k, int def) {
  auto it = kv_.find(k); return it == kv_.end() ? def : atoi(it->second.c_str());
}
String Preferences::getString(const char *k, const char *def) {
  auto it = kv_.find(k); return it == kv_.end() ? String(def) : String(it->second.c_str());
}

// --- Wire (CST816 touch) ---
TwoWire Wire;
extern bool landscape;  // sketch global: true while the chart is rotated

uint8_t TwoWire::endTransmission(bool stop) { (void)stop; return 0; }  // chip present

int TwoWire::requestFrom(uint8_t addr, uint8_t qty) {
  (void)addr;
  if (reg_ != 0x02 || qty < 7) { buflen_ = 0; bufpos_ = 0; return 0; }
  // drawing coords -> native panel coords (inverse of sketch touchRead)
  int16_t nx, ny;
  if (landscape) { nx = simFingerDY; ny = 319 - simFingerDX; }
  else           { nx = simFingerDX; ny = simFingerDY; }
  buf_[0] = simFingerDown ? 1 : 0;
  buf_[1] = (uint8_t)((nx >> 8) & 0x0F);
  buf_[2] = (uint8_t)(nx & 0xFF);
  buf_[3] = (uint8_t)((ny >> 8) & 0x0F);
  buf_[4] = (uint8_t)(ny & 0xFF);
  buf_[5] = 0; buf_[6] = 0;
  buflen_ = 7; bufpos_ = 0;
  return 7;
}
int TwoWire::read() {
  if (bufpos_ < buflen_) return buf_[bufpos_++];
  return -1;
}
