#ifndef DOSEI_HOST_COLD_H
#define DOSEI_HOST_COLD_H
/* Cold const host tables live in the cart HOSTCOLD carve (ram_cart.h): the
 * linker places section .cartd at the carve's cached alias and the build
 * writes it to HOSTCOLD.BIN, loaded once right after the cart is claimed.
 * Only for tables never read before that load. Host tests keep plain data. */
#if defined(__sh__) && !defined(DOSEI_HOST_TEST)
#define HOST_COLD __attribute__((section(".cartd")))
/* Cold load-time code (scene/pause loaders), executed from the cart. Never
 * call it before ram_cart_load_host_cold(); noinline keeps LTO from pulling
 * it back into a work-RAM caller. */
#define HOST_COLD_CODE __attribute__((section(".cartt"), noinline))
#else
#define HOST_COLD
#define HOST_COLD_CODE
#endif
#endif
