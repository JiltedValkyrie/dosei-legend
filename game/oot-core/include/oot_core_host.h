/*
 * Saturn host services the oot-core blob calls back into. Shared by C (main
 * loop) and oot-core C++. The blob is self-contained, so every backend call
 * (sound, save-owned state the C side still owns) goes through this table.
 * Phase 1 bridges (oot-core/src/bridge_*.cpp) are null-safe: an unset entry
 * does nothing. See docs/OOT_CORE_PIPELINE_PLAN.md, Phase 1 step 3.
 */
#ifndef OOT_CORE_HOST_H
#define OOT_CORE_HOST_H
#include "oot_core_combat.h"

typedef struct OotCoreHost {
    /* Decomp sfxId (include/tables/sfx/<bank>_table.h) at world position, Q0 units. */
    void (*play_sfx)(unsigned short sfx_id, int x, int y, int z);
    /* z_parameter Item_Give: returns ITEM_NONE (0xFF) when given. Owned by the
     * C save until z_parameter is imported. */
    unsigned char (*give_item)(unsigned char item);
    /* z_parameter Health_ChangeBy, amount in 1/16 hearts. Nonzero = alive. */
    int (*health_change)(short amount);
    /* Free-running timer and its conversion to microseconds (profiling). */
    unsigned int (*ticks)(void);
    unsigned int (*ticks_to_us)(unsigned int ticks);
    /* z_parameter Rupees_ChangeBy: add (or spend, negative) rupees. */
    void (*rupees_change)(short amount);
    /* Temporary Player proxy: snapshot once per core step, one accepted hit.
     * Health remains C-owned; the proxy must never also call Health_ChangeBy. */
    void (*player_combat)(OotCoreCombatState* out);
    int (*player_hit)(const OotCorePlayerHit* hit);
    /* Scene loading only. NULL data queries size (0 missing, -1 error).
     * Otherwise read exactly bytes from start; purge SH-2 cache after read. */
    int (*scene_file)(const char* name, void* data, unsigned int bytes);
    /* Scene-only sprite storage: free non-NULL memory, otherwise allocate
     * bytes under the unchanged live-heap admission guard. */
    void* (*sprite_memory)(void* memory, unsigned int bytes);
    /* Real decomp Player (PLAYER_SOURCE=1): the C save stays the one owner
     * of ammo, magic and bottles. z_parameter Inventory_ChangeAmmo (source
     * ItemId, signed change). */
    void (*ammo_change)(unsigned char item, short amount);
    /* Magic_RequestChange (amount, MAGIC_* type; OOT_CORE_MAGIC_FILL = Magic_Fill).
     * Nonzero = accepted. */
    int (*magic_request)(short amount, short type);
    /* Inventory_UpdateBottleItem (item, C button 1..3); button 0xFF with
     * ITEM_BOTTLE_FAIRY = Inventory_ConsumeFairy (nonzero = a fairy was used). */
    int (*bottle_update)(unsigned char item, unsigned char button);
    /* Unrecoverable core error (e.g. missing Player animation clip). */
    void (*fatal)(unsigned int code, unsigned int a, unsigned int b);
    /* Queue on the slave; execute drive/SCSP work only after the master joins. */
    void (*audio_request)(unsigned int command, unsigned int argument);
} OotCoreHost;

#define OOT_CORE_MAGIC_FILL 0x7F
#define OOT_CORE_MAGIC_ACQUIRE 0x7E /* amount = source acquired capacity level */
#define OOT_CORE_DEFENSE_ACQUIRE 0x7D /* source Great Fairy defense reward */

#endif
