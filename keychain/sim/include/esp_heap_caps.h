#pragma once
#include <stdlib.h>
#ifndef MALLOC_CAP_SPIRAM
#define MALLOC_CAP_SPIRAM 0
#endif
inline void *heap_caps_malloc(size_t n, int caps) { (void)caps; return malloc(n); }
