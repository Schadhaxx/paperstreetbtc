#pragma once
#include <Arduino.h>
enum { WL_IDLE_STATUS = 0, WL_CONNECTED = 3, WIFI_STA = 1, WIFI_OFF = 0 };
class WiFiClass {
public:
  void mode(int m) { (void)m; }
  void begin(const char *ssid, const char *pass) { (void)ssid; (void)pass; connected_ = true; }
  int status() { return connected_ ? WL_CONNECTED : WL_IDLE_STATUS; }
private:
  bool connected_ = true;  // sim: always associated so stub fetches run
};
extern WiFiClass WiFi;
