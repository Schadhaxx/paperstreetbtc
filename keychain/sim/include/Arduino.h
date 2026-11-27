#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <string>
#include <math.h>
#include <time.h>

typedef uint8_t byte;
#ifndef INPUT
#define INPUT 0
#define OUTPUT 1
#define INPUT_PULLUP 2
#endif
#ifndef LOW
#define LOW 0x0
#define HIGH 0x1
#endif

unsigned long millis();
void delay(unsigned long ms);
void pinMode(int pin, int mode);
void digitalWrite(int pin, int val);
int analogReadMilliVolts(int pin);
void configTime(long gmtOffset_sec, int daylightOffset_sec,
                const char *server1, const char *server2 = nullptr,
                const char *server3 = nullptr);
bool getLocalTime(struct tm *info, uint32_t ms = 0);

class String {
  std::string s_;
public:
  String() {}
  String(const char *s) : s_(s ? s : "") {}
  String(const std::string &s) : s_(s) {}
  const char *c_str() const { return s_.c_str(); }
  size_t length() const { return s_.size(); }
  bool isEmpty() const { return s_.empty(); }
};

class SerialClass {
public:
  void begin(unsigned long baud);
  void println(const char *s);
  void println(const String &s);
  void println(int v);
  void println(long v);
  void println(unsigned long v);
  void println(float v);
  void println();
  void print(const char *s);
  void print(const String &s);
  void print(int v);
  void print(long v);
  void print(unsigned long v);
  void print(float v);
  int available();
  int read();
};
extern SerialClass Serial;
