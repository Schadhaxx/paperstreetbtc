// mbedtls/md.h stub implementation (HMAC-SHA1 only).
#include "mbedtls/md.h"
#include "../src/sha1.h"
#include <string.h>

static mbedtls_md_info_t sha1_info = { MBEDTLS_MD_SHA1 };

extern "C" {
const mbedtls_md_info_t *mbedtls_md_info_from_type(int md_type) {
  return md_type == MBEDTLS_MD_SHA1 ? &sha1_info : nullptr;
}
void mbedtls_md_init(mbedtls_md_context_t *ctx) { memset(ctx, 0, sizeof(*ctx)); }
int mbedtls_md_setup(mbedtls_md_context_t *ctx, const mbedtls_md_info_t *md_info, int hmac) {
  if (!md_info || md_info->type != MBEDTLS_MD_SHA1) return -1;
  ctx->info = md_info; ctx->hmac = hmac; ctx->msglen = 0; ctx->keylen = 0;
  return 0;
}
int mbedtls_md_hmac_starts(mbedtls_md_context_t *ctx, const unsigned char *key, size_t keylen) {
  if (!ctx->hmac || keylen > sizeof(ctx->key)) return -1;
  memcpy(ctx->key, key, keylen); ctx->keylen = keylen; ctx->msglen = 0;
  return 0;
}
int mbedtls_md_hmac_update(mbedtls_md_context_t *ctx, const unsigned char *input, size_t ilen) {
  if (ctx->msglen + ilen > sizeof(ctx->msg)) return -1;
  memcpy(ctx->msg + ctx->msglen, input, ilen); ctx->msglen += ilen;
  return 0;
}
int mbedtls_md_hmac_finish(mbedtls_md_context_t *ctx, unsigned char *output) {
  sim_hmac_sha1(ctx->key, ctx->keylen, ctx->msg, ctx->msglen, output);
  return 0;
}
void mbedtls_md_free(mbedtls_md_context_t *ctx) { (void)ctx; }
}  // extern "C"
