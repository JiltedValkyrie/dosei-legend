/*
 * Player proxy. z_actor and most actors read GET_PLAYER(play) every frame,
 * but Link is still the C player (player_*.c). Until z_player is imported,
 * ACTOR_PLAYER is this stand-in: same profile header as z_player_call.c
 * (id, category, flags, object, sizeof(Player)), with an update that copies
 * C Link's pose in. Everything else in Player stays zero: no state flags,
 * no held/talk/focus actor.
 *
 * Replace by importing z_player_call.c + ovl_player_actor; then delete this
 * file (bridge_tables picks the real Player_Profile up automatically).
 */
#include "oot_prelude.h"
#include "ultra64.h"
#include "actor.h"
#include "player.h"
#include "play_state.h"

/* Set by oot_core_set_player (oot_core_api.cpp), read in update. */
Vec3f gOotCorePlayerPos;
s16 gOotCorePlayerYaw;

/* Child Link eye height used for focus (attention arrows, actor look-at).
 * APPROXIMATE: the real player sets focus from the head limb each frame. */
#define PROXY_FOCUS_HEIGHT 40

static void PlayerProxy_Sync(Actor* thisx) {
    thisx->world.pos = gOotCorePlayerPos;
    thisx->world.rot.y = gOotCorePlayerYaw;
    thisx->shape.rot.y = gOotCorePlayerYaw;
    thisx->focus.pos = gOotCorePlayerPos;
    thisx->focus.pos.y = thisx->focus.pos.y + PROXY_FOCUS_HEIGHT;
    thisx->focus.rot.y = gOotCorePlayerYaw;
}

static void PlayerProxy_Init(Actor* thisx, PlayState* play) {
    gOotCorePlayerPos = thisx->world.pos;
    gOotCorePlayerYaw = thisx->world.rot.y;
    PlayerProxy_Sync(thisx);
}

static void PlayerProxy_Destroy(Actor* thisx, PlayState* play) {
}

static void PlayerProxy_Update(Actor* thisx, PlayState* play) {
    PlayerProxy_Sync(thisx);
}

#define FLAGS                                                                                 \
    (ACTOR_FLAG_ATTENTION_ENABLED | ACTOR_FLAG_HOSTILE | ACTOR_FLAG_UPDATE_CULLING_DISABLED | \
     ACTOR_FLAG_DRAW_CULLING_DISABLED | ACTOR_FLAG_UPDATE_DURING_OCARINA | ACTOR_FLAG_CAN_PRESS_SWITCHES)

/* Draw NULL: the C renderer draws Link. */
ActorProfile Player_Profile = {
    /**/ ACTOR_PLAYER,
    /**/ ACTORCAT_PLAYER,
    /**/ FLAGS,
    /**/ OBJECT_GAMEPLAY_KEEP,
    /**/ sizeof(Player),
    /**/ PlayerProxy_Init,
    /**/ PlayerProxy_Destroy,
    /**/ PlayerProxy_Update,
    /**/ NULL,
};
