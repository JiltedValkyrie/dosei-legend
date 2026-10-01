/*
** 4 MB RAM expansion cart detection and second-bank registration.
** Contract and rationale are in ram_cart.h.
*/

#include <jo/jo.h>
#include "ram_cart.h"

/* Compile-time layout guard: every fixed carve in address order, no
** overlap, all inside RAM_CART_FIXED_BYTES. Add new carves here. */
#define CARVE_END(n) (n##_OFFSET + n##_BYTES)
typedef char carve_dyna_before_cuttext[CARVE_END(RAM_CART_DYNA) <= RAM_CART_CUTTEXT_OFFSET ? 1 : -1];
typedef char carve_cuttext_before_layout[CARVE_END(RAM_CART_CUTTEXT) <= RAM_CART_TEXT_LAYOUT_OFFSET ? 1 : -1];
typedef char carve_layout_before_cursor[CARVE_END(RAM_CART_TEXT_LAYOUT) <= RAM_CART_CURSOR_OFFSET ? 1 : -1];
typedef char carve_cursor_before_message[CARVE_END(RAM_CART_CURSOR) <= RAM_CART_MESSAGE_LAYOUT_OFFSET ? 1 : -1];
typedef char carve_message_before_contact[CARVE_END(RAM_CART_MESSAGE_LAYOUT) <= RAM_CART_CONTACT_OFFSET ? 1 : -1];
typedef char carve_contact_before_minimap[CARVE_END(RAM_CART_CONTACT) <= RAM_CART_MINIMAP_OFFSET ? 1 : -1];
typedef char carve_minimap_before_fairy[CARVE_END(RAM_CART_MINIMAP) <= RAM_CART_FAIRY_OFFSET ? 1 : -1];
typedef char carve_fairy_before_linkmesh[CARVE_END(RAM_CART_FAIRY) <= RAM_CART_LINKMESH_OFFSET ? 1 : -1];
typedef char carve_linkmesh_before_naviglow[CARVE_END(RAM_CART_LINKMESH) <= RAM_CART_NAVIGLOW_OFFSET ? 1 : -1];
typedef char carve_naviglow_before_dekubaba[CARVE_END(RAM_CART_NAVIGLOW) <= RAM_CART_DEKUBABA_OFFSET ? 1 : -1];
typedef char carve_dekubaba_before_karebaba[CARVE_END(RAM_CART_DEKUBABA) <= RAM_CART_KAREBABA_OFFSET ? 1 : -1];
typedef char carve_karebaba_before_linktex[CARVE_END(RAM_CART_KAREBABA) <= RAM_CART_LINKTEX_OFFSET ? 1 : -1];
typedef char carve_linktex_before_pause[CARVE_END(RAM_CART_LINKTEX) <= RAM_CART_PAUSE_OFFSET ? 1 : -1];
typedef char carve_pause_before_pause_backup[CARVE_END(RAM_CART_PAUSE) <= RAM_CART_PAUSE_BACKUP_OFFSET ? 1 : -1];
typedef char carve_pause_backup_before_titlepth[CARVE_END(RAM_CART_PAUSE_BACKUP) <= RAM_CART_TITLEPTH_OFFSET ? 1 : -1];
typedef char carve_pause_backup_before_skull[CARVE_END(RAM_CART_PAUSE_BACKUP) <= RAM_CART_SKULL_OFFSET ? 1 : -1];
typedef char carve_skull_before_titlepth[CARVE_END(RAM_CART_SKULL) <= RAM_CART_TITLEPTH_OFFSET ? 1 : -1];
typedef char carve_skull_before_wall_skull[CARVE_END(RAM_CART_SKULL) <= RAM_CART_WALL_SKULL_OFFSET ? 1 : -1];
typedef char carve_wall_skull_before_titlepth[CARVE_END(RAM_CART_WALL_SKULL) <= RAM_CART_TITLEPTH_OFFSET ? 1 : -1];
typedef char carve_wall_skull_before_deku_baba[CARVE_END(RAM_CART_WALL_SKULL) <= RAM_CART_DEKU_BABA_OFFSET ? 1 : -1];
typedef char carve_deku_baba_before_titlepth[CARVE_END(RAM_CART_DEKU_BABA) <= RAM_CART_TITLEPTH_OFFSET ? 1 : -1];
typedef char carve_baba_before_hintnuts[CARVE_END(RAM_CART_DEKU_BABA) <= RAM_CART_HINTNUTS_OFFSET ? 1 : -1];
typedef char carve_hintnuts_before_titlepth[CARVE_END(RAM_CART_HINTNUTS) <= RAM_CART_TITLEPTH_OFFSET ? 1 : -1];
typedef char carve_dialogue_before_musictrg[CARVE_END(RAM_CART_DIALOGUE) <= RAM_CART_MUSICTRG_OFFSET ? 1 : -1];
typedef char carve_titlepth_before_dialogue[CARVE_END(RAM_CART_TITLEPTH) <= RAM_CART_DIALOGUE_OFFSET ? 1 : -1];
typedef char carve_musictrg_inside[CARVE_END(RAM_CART_MUSICTRG) <= RAM_CART_FIXED_BYTES ? 1 : -1];

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
                       RAM_CART_BANK2_BYTES - RAM_CART_FIXED_BYTES);
    second_bank_claimed = true;
    return (true);
}

void           *ram_cart_fixed(unsigned int offset, unsigned int bytes)
{
    if (!second_bank_claimed || offset > RAM_CART_FIXED_BYTES ||
        bytes > RAM_CART_FIXED_BYTES - offset)
        return ((void *)0);
    return ((void *)(RAM_CART_FIXED_ADDRESS + offset));
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
