#pragma once
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
enum { MBEDTLS_MD_SHA1 = 1 };
typedef struct { int type; } mbedtls_md_info_t;
typedef struct {
  const mbedtls_md_info_t *info;
  int hmac;
  unsigned char key[128];
  size_t keylen;
  unsigned char msg[256];
  size_t msglen;
} mbedtls_md_context_t;
const mbedtls_md_info_t *mbedtls_md_info_from_type(int md_type);
void mbedtls_md_init(mbedtls_md_context_t *ctx);
int mbedtls_md_setup(mbedtls_md_context_t *ctx, const mbedtls_md_info_t *md_info, int hmac);
int mbedtls_md_hmac_starts(mbedtls_md_context_t *ctx, const unsigned char *key, size_t keylen);
int mbedtls_md_hmac_update(mbedtls_md_context_t *ctx, const unsigned char *input, size_t ilen);
int mbedtls_md_hmac_finish(mbedtls_md_context_t *ctx, unsigned char *output);
void mbedtls_md_free(mbedtls_md_context_t *ctx);
#ifdef __cplusplus
}
#endif
