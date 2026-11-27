#pragma once
#include <Arduino.h>
#include <string>
#include "WiFiClientSecure.h"

class Stream {
  std::string data_;
  size_t pos_ = 0;
public:
  void setData(const std::string &s) { data_ = s; pos_ = 0; }
  void setData(const char *s) { data_ = s ? s : ""; pos_ = 0; }
  int available() const { return (int)(data_.size() - pos_); }
  int read() {
    if (pos_ >= data_.size()) return -1;
    return (unsigned char)data_[pos_++];
  }
  size_t readBytes(char *buf, size_t n) {
    size_t i = 0;
    while (i < n && pos_ < data_.size()) buf[i++] = data_[pos_++];
    return i;
  }
};

class HTTPClient {
public:
  bool begin(WiFiClientSecure &client, const char *url);
  int GET();
  void end() { url_.clear(); code_ = 0; }
  void setTimeout(int ms) { (void)ms; }
  void setUserAgent(const char *ua) { (void)ua; }
  Stream &getStream() { return stream_; }
public:
  std::string url_;
  int code_ = 0;
  Stream stream_;
};
