/*
** 4 MB RAM expansion cart detection and second-bank registration.
** Contract and rationale are in ram_cart.h.
*/

#include <jo/jo.h>
#include "ram_cart.h"

/* One-shot guard: jo_add_memory_zone() has no way to retract a zone, so adding
** the same bank twice would hand out the same addresses from two free lists. */
static bool     second_bank_claimed = false;

bool            ram_cart_present(void)
{
#ifdef JO_COMPILE_WITH_RAM_CARD_SUPPORT
    return (jo_get_extended_ram_cartridge_type() == CART_32MBits);
#else
    return (false);
#endif
}

bool            ram_cart_claim_second_bank(void)
{
    if (!ram_cart_present())
        return (false);
    if (second_bank_claimed)
        return (true);
    /* jo_core_init() already ran jo_enable_extended_ram_cartridge_support() and
    ** jo_set_a_bus_register() during its own detection, so the bank is
    ** addressable by the time we get here; only the zone is missing. */
    jo_add_memory_zone((unsigned char *)RAM_CART_BANK2_ADDRESS,
                       RAM_CART_BANK2_BYTES);
    second_bank_claimed = true;
    return (true);
}

unsigned int    ram_cart_total_bytes(void)
{
    if (!ram_cart_present())
        return (0);
    /* First bank registered by the SDK, second by us. */
    return (RAM_CART_BANK2_BYTES + (second_bank_claimed
                                    ? RAM_CART_BANK2_BYTES : 0));
}

/*
** END OF FILE
*/
