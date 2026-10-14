/* Source item identities and draw gates, without runtime item display lists. */
static int ChildMinigame_ItemView(const Actor* actor, const PlayState* play, OotCoreNpcView* v) {
    s32 gid, scale;
    if (actor->id != ACTOR_EN_EX_ITEM && actor->id != ACTOR_ITEM_ETCETERA &&
        actor->id != ACTOR_EN_EX_RUPPY && actor->id != ACTOR_EN_G_SWITCH) return 0;
    if (actor->id == ACTOR_EN_G_SWITCH && ((const EnGSwitch*)actor)->type == ENGSWITCH_ARCHERY_POT) return 0;
    if (!actor->draw) return -1;
    scale = (s32)(actor->scale.x * 1280);
    if (actor->id == ACTOR_EN_EX_ITEM) {
        const EnExItem* item = (const EnExItem*)actor;
        gid = item->giDrawId;
        if (item->type == EXITEM_HEART_PIECE_BOWLING || item->type == EXITEM_HEART_PIECE_COUNTER) gid = GID_HEART_PIECE;
        else if (item->type == EXITEM_SMALL_KEY_CHEST) { gid = GID_SMALL_KEY; scale = 256; }
        else if (item->type >= EXITEM_MAGIC_FIRE && item->type <= EXITEM_MAGIC_DARK) {
            const u8 magic[] = { GID_DINS_FIRE, GID_FARORES_WIND, GID_NAYRUS_LOVE };
            gid = magic[item->type - EXITEM_MAGIC_FIRE];
        }
    } else if (actor->id == ACTOR_ITEM_ETCETERA) {
        if ((actor->params & 0xff) >= ITEM_ETC_RUPEE_GREEN_CHEST_GAME && !play->actorCtx.lensActive) return -1;
        gid = ((const ItemEtcetera*)actor)->giDrawId;
    } else {
        const u8 colours[] = { GID_RUPEE_GREEN, GID_RUPEE_BLUE, GID_RUPEE_RED, GID_RUPEE_PURPLE, GID_RUPEE_GOLD, GID_RUPEE_PURPLE };
        s32 colour;
        if (actor->id == ACTOR_EN_EX_RUPPY) {
            const EnExRuppy* rupee = (const EnExRuppy*)actor;
            if (rupee->invisible) return -1;
            colour = rupee->colorIdx;
        } else {
            const EnGSwitch* target = (const EnGSwitch*)actor;
            if (target->broken || target->type == ENGSWITCH_SILVER_TRACKER) return -1;
            colour = target->colorIdx;
        }
        if ((u32)colour >= ARRAY_COUNT(colours)) return -1;
        gid = colours[colour];
        /* Source target model height1288 vs get-item40. Same visible bounds. */
        scale = (s32)(actor->scale.x * 20608) * 2;
    }
    *v = {};
    v->id = actor->id; v->params = actor->params; v->object = 0xfff;
    v->anim = gid + 1; v->alpha = 255; v->flags = OOT_CORE_VIEW_DRAWN;
    v->x = (s32)actor->world.pos.x;
    v->y = (s32)(actor->world.pos.y + actor->shape.yOffset * actor->scale.y);
    v->z = (s32)actor->world.pos.z; v->yaw = (u16)actor->shape.rot.y;
    v->scale_x = v->scale_y = scale > 0 ? scale : 1;
    return 1;
}
