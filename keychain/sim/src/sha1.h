#pragma once
// SHA-1 (FIPS 180-1) + HMAC-SHA1, small self-contained implementation.
// Used by the mbedtls/md.h stub for the sketch's TOTP codes.
// Verified against RFC 6238 vectors via the sketch's totpCode.
#include <stdint.h>
#include <stddef.h>
#include <string.h>

struct SimSHA1 {
  uint32_t h[5];
  uint64_t len;      // total message length in bytes
  uint8_t buf[64];
  size_t buflen;
};

static inline uint32_t sim_rol32(uint32_t v, int n) { return (v << n) | (v >> (32 - n)); }

static inline void sim_sha1_block(SimSHA1 *c, const uint8_t *p) {
  uint32_t w[80];
  for (int i = 0; i < 16; i++)
    w[i] = ((uint32_t)p[i * 4] << 24) | ((uint32_t)p[i * 4 + 1] << 16) |
           ((uint32_t)p[i * 4 + 2] << 8) | (uint32_t)p[i * 4 + 3];
  for (int i = 16; i < 80; i++) w[i] = sim_rol32(w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16], 1);
  uint32_t a = c->h[0], b = c->h[1], d = c->h[3], e = c->h[4], f, k, t;
  uint32_t cc = c->h[2];
  for (int i = 0; i < 80; i++) {
    if (i < 20)      { f = (b & cc) | ((~b) & d); k = 0x5A827999; }
    else if (i < 40) { f = b ^ cc ^ d;            k = 0x6ED9EBA1; }
    else if (i < 60) { f = (b & cc) | (b & d) | (cc & d); k = 0x8F1BBCDC; }
    else             { f = b ^ cc ^ d;            k = 0xCA62C1D6; }
    t = sim_rol32(a, 5) + f + e + k + w[i];
    e = d; d = cc; cc = sim_rol32(b, 30); b = a; a = t;
  }
  c->h[0] += a; c->h[1] += b; c->h[2] += cc; c->h[3] += d; c->h[4] += e;
}

static inline void sim_sha1_init(SimSHA1 *c) {
  c->h[0] = 0x67452301; c->h[1] = 0xEFCDAB89; c->h[2] = 0x98BADCFE;
  c->h[3] = 0x10325476; c->h[4] = 0xC3D2E1F0;
  c->len = 0; c->buflen = 0;
}

static inline void sim_sha1_update(SimSHA1 *c, const uint8_t *data, size_t len) {
  c->len += len;
  while (len > 0) {
    size_t take = 64 - c->buflen;
    if (take > len) take = len;
    memcpy(c->buf + c->buflen, data, take);
    c->buflen += take; data += take; len -= take;
    if (c->buflen == 64) { sim_sha1_block(c, c->buf); c->buflen = 0; }
  }
}

static inline void sim_sha1_final(SimSHA1 *c, uint8_t out[20]) {
  uint64_t bits = c->len * 8;
  uint8_t pad = 0x80;
  sim_sha1_update(c, &pad, 1);
  uint8_t zero = 0;
  while (c->buflen != 56) sim_sha1_update(c, &zero, 1);
  uint8_t lb[8];
  for (int i = 0; i < 8; i++) lb[i] = (uint8_t)(bits >> (56 - 8 * i));
  // feed length directly (bypass len accounting)
  memcpy(c->buf + c->buflen, lb, 8);
  sim_sha1_block(c, c->buf);
  for (int i = 0; i < 5; i++) {
    out[i * 4] = (uint8_t)(c->h[i] >> 24); out[i * 4 + 1] = (uint8_t)(c->h[i] >> 16);
    out[i * 4 + 2] = (uint8_t)(c->h[i] >> 8); out[i * 4 + 3] = (uint8_t)(c->h[i]);
  }
}

// HMAC-SHA1 (RFC 2104). key may be any length; output is 20 bytes.
static inline void sim_hmac_sha1(const uint8_t *key, size_t keylen,
                                 const uint8_t *msg, size_t msglen,
                                 uint8_t out[20]) {
  uint8_t kbuf[64];
  memset(kbuf, 0, sizeof(kbuf));
  if (keylen > 64) {
    SimSHA1 c; sim_sha1_init(&c); sim_sha1_update(&c, key, keylen);
    sim_sha1_final(&c, kbuf);
  } else {
    memcpy(kbuf, key, keylen);
  }
  uint8_t ipad[64], opad[64];
  for (int i = 0; i < 64; i++) { ipad[i] = kbuf[i] ^ 0x36; opad[i] = kbuf[i] ^ 0x5C; }
  SimSHA1 inner; sim_sha1_init(&inner);
  sim_sha1_update(&inner, ipad, 64);
  sim_sha1_update(&inner, msg, msglen);
  uint8_t ihash[20]; sim_sha1_final(&inner, ihash);
  SimSHA1 outer; sim_sha1_init(&outer);
  sim_sha1_update(&outer, opad, 64);
  sim_sha1_update(&outer, ihash, 20);
  sim_sha1_final(&outer, out);
}
