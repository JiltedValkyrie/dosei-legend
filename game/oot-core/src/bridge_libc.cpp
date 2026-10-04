/*
 * Minimal libc for the oot-core blob. It links with -nostdlib, so nothing
 * from newlib/Jo is reachable: these are the only C runtime calls the decomp
 * makes. abort() comes from GCC's __builtin_trap/unreachable lowering.
 */
/* No decomp headers: libc/string.h gives memcpy C++ linkage, but GCC calls
 * the C symbol for struct copies. */
typedef unsigned int size_t;
typedef unsigned char u8;

extern "C" void* memcpy(void* dst, const void* src, size_t n) {
    u8* d = (u8*)dst;
    const u8* s = (const u8*)src;
    while (n--) {
        *d++ = *s++;
    }
    return dst;
}

extern "C" void* memset(void* dst, int c, size_t n) {
    u8* d = (u8*)dst;
    while (n--) {
        *d++ = (u8)c;
    }
    return dst;
}

/* ultra64/libc.h declares bzero with C++ linkage (no extern "C" block). */
void bzero(void* s, unsigned int n) {
    memset(s, 0, n);
}

extern "C" void abort(void) {
    for (;;) {
    }
}
