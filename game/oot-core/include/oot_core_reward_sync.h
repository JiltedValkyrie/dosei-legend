#ifndef OOT_CORE_REWARD_SYNC_H
#define OOT_CORE_REWARD_SYNC_H
/* Source Fairy flags must reach the save owner before the next input mirror.
 * z_parameter's health refill advances at the source update rate. */
static void OotCore_CommitRewards(const OotCoreSave* input, const OotCoreHost* host) {
    SavePlayerData* pd = &gSaveContext.save.info.playerData;
    unsigned level = pd->isDoubleMagicAcquired ? 2 : pd->isMagicAcquired ? 1 : 0;
    if (host && host->magic_request) {
        if (level > input->magic_level)
            host->magic_request(level, OOT_CORE_MAGIC_ACQUIRE);
        if (pd->isDoubleDefenseAcquired && !input->double_defense)
            host->magic_request(1, OOT_CORE_DEFENSE_ACQUIRE);
    }
    if (gSaveContext.healthAccumulator && host && host->health_change) {
        gSaveContext.healthAccumulator -= 4;
        pd->health += 4;
        host->health_change(4);
        if ((pd->health & 15) < 4 && host->play_sfx)
            host->play_sfx(NA_SE_SY_HP_RECOVER, 0, 0, 0);
        if (pd->health >= pd->healthCapacity) {
            pd->health = pd->healthCapacity;
            gSaveContext.healthAccumulator = 0;
        }
    }
}
#endif
