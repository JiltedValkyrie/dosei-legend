#ifndef DOSEI_RAM_CART_H
#define DOSEI_RAM_CART_H
#include <stdbool.h>

/*
** The 4 MB (32 Mbit) RAM expansion cart is a hard requirement, not an optional
** speed-up: the scene, actor and cutscene data for the three areas does not fit
** in the 2 MB of work RAM once SGL's work area and VDP1 staging are subtracted.
**
** Two jobs here:
**
**   1. Refuse to run without the cart, with a message on screen. Silently
**      running with half the memory would fail later as an unexplained
**      allocation failure somewhere far from the cause.
**   2. Claim the SECOND half of the cart. jo_init_memory() in the SDK
**      (joengine/jo_engine/core.c) registers only 0x200000 at 0x22400000 for
**      CART_32MBits and never touches the bank at 0x22600000, so half the cart
**      is invisible to jo_malloc() unless we add it ourselves.
**
** jo_core_init() must have run first: the SDK does its own cart detection and
** A-bus setup there, and this builds on it rather than repeating it.
*/

/* Second 2 MB bank of the 32 Mbit cart, the one the SDK leaves unregistered. */
#define RAM_CART_BANK2_ADDRESS  0x22600000u
#define RAM_CART_BANK2_BYTES    0x200000u

/* The top of bank 2 is kept OUT of jo_malloc for fixed runtime pools (actor
** pool first). A fixed carve keeps these off the 56 KB work-RAM malloc arena,
** which jo_malloc would otherwise fill first. */
#define RAM_CART_FIXED_BYTES    0x4000u
#define RAM_CART_FIXED_ADDRESS  (RAM_CART_BANK2_ADDRESS + RAM_CART_BANK2_BYTES - RAM_CART_FIXED_BYTES)

/* Fixed carve for the actor pool (actor_sys_bytes() must fit). */
#define RAM_CART_ACTOR_POOL_OFFSET  0u
#define RAM_CART_ACTOR_POOL_BYTES   0x2000u

/* Pointer into the fixed carve, or 0 when no cart / out of range. */
void   *ram_cart_fixed(unsigned int offset, unsigned int bytes);

/* True when a 32 Mbit cart is present. Cheap; reads the cart id byte. */
bool    ram_cart_present(void);

/* Register the second bank with jo_malloc(). Returns false when no 32 Mbit cart
** is fitted, in which case nothing was added and the caller must not continue.
** Safe to call once only; calling twice would double-register the bank. */
bool    ram_cart_claim_second_bank(void);

/* Bytes of cart RAM this build expects to be usable, for diagnostics. */
unsigned int    ram_cart_total_bytes(void);

#endif
