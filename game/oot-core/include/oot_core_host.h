/*
 * Saturn host services the oot-core blob calls back into. Shared by C (main
 * loop) and oot-core C++. The blob is self-contained, so every backend call
 * (sound, save-owned state the C side still owns) goes through this table.
 * Phase 1 bridges (oot-core/src/bridge_*.cpp) are null-safe: an unset entry
 * does nothing. See docs/OOT_CORE_PIPELINE_PLAN.md, Phase 1 step 3.
 */
#ifndef OOT_CORE_HOST_H
#define OOT_CORE_HOST_H

typedef struct OotCoreHost {
    /* Decomp sfxId (include/tables/sfx/*.h) at world position, Q0 units. */
    void (*play_sfx)(unsigned short sfx_id, int x, int y, int z);
    /* z_parameter Item_Give: returns ITEM_NONE (0xFF) when given. Owned by the
     * C save until z_parameter is imported. */
    unsigned char (*give_item)(unsigned char item);
    /* z_parameter Health_ChangeBy, amount in 1/16 hearts. Nonzero = alive. */
    int (*health_change)(short amount);
} OotCoreHost;

#endif
