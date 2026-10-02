/* oot-core: replaces decomp include/libc/assert.h (static_assert is a C++ keyword). */
#ifndef ASSERT_H
#define ASSERT_H

#ifdef OOT_CORE_ASSERTS
void oot_core_assert(const char* msg, const char* file, int line);
#define ASSERT(cond, msg, file, line) ((cond) ? ((void)0) : oot_core_assert(msg, file, line))
#else
#define ASSERT(cond, msg, file, line) ((void)0)
#endif
#define assert(cond) ASSERT(cond, #cond, __FILE__, __LINE__)

#endif
