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
#include "collision_check.h"
#include "z_lib.h"
#include "item.h"
#include "sfx.h"
#include "interface.h"
#include "message.h"
#include "libu64/pad.h"
#include "controller.h"

/* Set by oot_core_set_player (oot_core_api.cpp), read in update. */
Vec3f gOotCorePlayerPos;
s16 gOotCorePlayerYaw;
/* C sword line (oot_core_set_sword): live flag, base and tip in world units. */
s32 gOotCoreSwordActive;
Vec3f gOotCoreSwordBase;
Vec3f gOotCoreSwordTip;

/* OC push the decomp actors gave the player this update (world units,
 * Q0): the C side moves C Link by it (oot_core_api.cpp player_push). */
s32 gOotCorePlayerPushX;
s32 gOotCorePlayerPushZ;

/* z_player.c D_80854624: the player's body cylinder (OC pushes, AC). */
static ColliderCylinderInit sBodyCylinderInit = {
    {
        COL_MATERIAL_HIT5,
        AT_NONE,
        AC_ON | AC_TYPE_ENEMY,
        OC1_ON | OC1_TYPE_ALL,
        OC2_TYPE_PLAYER,
        COLSHAPE_CYLINDER,
    },
    {
        ELEM_MATERIAL_UNK1,
        { 0x00000000, HIT_SPECIAL_EFFECT_NONE, 0x00 },
        { 0xFFCFFFFF, HIT_BACKLASH_NONE, 0x00 },
        ATELEM_NONE,
        ACELEM_ON,
        OCELEM_ON,
    },
    { 12, 60, 0, { 0, 0, 0 } },
};

/* z_player.c D_80854650: the sword quads' collider. */
static ColliderQuadInit sMeleeWeaponQuadInit = {
    {
        COL_MATERIAL_NONE,
        AT_ON | AT_TYPE_PLAYER,
        AC_NONE,
        OC1_NONE,
        OC2_TYPE_PLAYER,
        COLSHAPE_QUAD,
    },
    {
        ELEM_MATERIAL_UNK2,
        { 0x00000100, HIT_SPECIAL_EFFECT_NONE, 0x01 },
        { 0xFFCFFFFF, HIT_BACKLASH_NONE, 0x00 },
        ATELEM_ON | ATELEM_SFX_NORMAL,
        ACELEM_NONE,
        OCELEM_NONE,
    },
    { { { 0.0f, 0.0f, 0.0f }, { 0.0f, 0.0f, 0.0f }, { 0.0f, 0.0f, 0.0f }, { 0.0f, 0.0f, 0.0f } } },
};

/* Copy of z_player_lib.c Player_UpdateWeaponInfo (file not imported yet):
 * the quad sweeps last frame's blade line to this frame's. */
static s32 PlayerProxy_UpdateWeaponInfo(PlayState* play, ColliderQuad* collider, WeaponInfo* weaponInfo,
                                        Vec3f* newPosA, Vec3f* newPosB) {
    if (!weaponInfo->active) {
        if (collider != NULL) {
            Collider_ResetQuadAT(play, &collider->base);
        }
        Math_Vec3f_Copy(&weaponInfo->posA, newPosA);
        Math_Vec3f_Copy(&weaponInfo->posB, newPosB);
        weaponInfo->active = true;
        return true;
    } else if ((weaponInfo->posA.x == newPosA->x) && (weaponInfo->posA.y == newPosA->y) &&
               (weaponInfo->posA.z == newPosA->z) && (weaponInfo->posB.x == newPosB->x) &&
               (weaponInfo->posB.y == newPosB->y) && (weaponInfo->posB.z == newPosB->z)) {
        if (collider != NULL) {
            Collider_ResetQuadAT(play, &collider->base);
        }
        return false;
    } else {
        if (collider != NULL) {
            Collider_SetQuadVertices(collider, newPosB, newPosA, &weaponInfo->posB, &weaponInfo->posA);
            CollisionCheck_SetAT(play, &play->colChkCtx, &collider->base);
        }
        Math_Vec3f_Copy(&weaponInfo->posB, newPosB);
        Math_Vec3f_Copy(&weaponInfo->posA, newPosA);
        weaponInfo->active = true;
        return true;
    }
}

/* Player_UpdateMeleeWeaponInfo for the C sword. APPROXIMATE: the C side
 * gives one blade line, so only quad 0 sweeps (the real player offsets two
 * lines from the left hand). dmgFlags as func_80837948 for a Kokiri Sword
 * slash (func_80837918); jump/spin flags not passed yet. */
static void PlayerProxy_UpdateSword(Player* this, PlayState* play) {
    if (!gOotCoreSwordActive) {
        this->meleeWeaponInfo[1].active = false; /* func_80832318 */
        return;
    }
    this->meleeWeaponQuads[0].elem.atDmgInfo.dmgFlags = DMG_SLASH_KOKIRI;
    this->meleeWeaponQuads[0].elem.atElemFlags = ATELEM_ON | ATELEM_NEAREST;
    PlayerProxy_UpdateWeaponInfo(play, &this->meleeWeaponQuads[0], &this->meleeWeaponInfo[1], &gOotCoreSwordTip,
                                 &gOotCoreSwordBase);
}

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
    Player* this = (Player*)thisx;

    Collider_InitCylinder(play, &this->cylinder);
    Collider_SetCylinder(play, &this->cylinder, thisx, &sBodyCylinderInit);
    thisx->colChkInfo.mass = 50;
    Collider_InitQuad(play, &this->meleeWeaponQuads[0]);
    Collider_SetQuad(play, &this->meleeWeaponQuads[0], thisx, &sMeleeWeaponQuadInit);
    gOotCorePlayerPos = thisx->world.pos;
    gOotCorePlayerYaw = thisx->world.rot.y;
    PlayerProxy_Sync(thisx);
}

static void PlayerProxy_Destroy(Actor* thisx, PlayState* play) {
    Collider_DestroyCylinder(play, &((Player*)thisx)->cylinder);
    Collider_DestroyQuad(play, &((Player*)thisx)->meleeWeaponQuads[0]);
}

/* Player's get-item handling (func_8083E5A8) for the drops En_Item00 offers
 * with Actor_OfferGetItemNearby. APPROXIMATE: given at once, no hold-up
 * animation or first-get text; itemId from z_player sGetItemTable. */
static void PlayerProxy_GetItem(Player* this, PlayState* play) {
    u8 item;

    if (this->getItemId == GI_NONE || this->interactRangeActor == NULL) {
        return;
    }
    switch (this->getItemId) {
        case GI_DEKU_NUTS_5:
            item = ITEM_DEKU_NUTS_5;
            break;
        case GI_DEKU_STICKS_1:
            item = ITEM_DEKU_STICK;
            break;
        case GI_DEKU_SEEDS_5:
            item = ITEM_DEKU_SEEDS;
            break;
        default:
            item = ITEM_NONE; /* not in the C save yet */
            break;
    }
    if (item != ITEM_NONE && Item_Give(play, item) == ITEM_NONE) {
        this->interactRangeActor->parent = &this->actor;
        Audio_PlaySfxGeneral(NA_SE_SY_GET_ITEM, &gSfxDefaultPos, 4, &gSfxDefaultFreqAndVolScale,
                             &gSfxDefaultFreqAndVolScale, &gSfxDefaultReverb);
    }
    this->getItemId = GI_NONE;
    this->interactRangeActor = NULL;
    this->getItemDirection = 0x8000;
}

/* Talking, from z_player.c: Player_ActionHandler_Talk (offer accepted with
 * A), Player_StartTalking + Player_SetupTalk (Message_StartTextbox with the
 * actor's textId), Player_Action_Talk (ends on TEXT_STATE_CLOSING) and the
 * end-of-update offer reset in Player_UpdateCommon. APPROXIMATE: no C-Up /
 * Navi talk, no lock-on or carrying checks, Link is assumed on the ground,
 * no talk animations (the C player owns Link's pose). */
static void PlayerProxy_UpdateTalk(Player* this, PlayState* play) {
    Input* input = &play->state.input[0];

    if (this->stateFlags1 & PLAYER_STATE1_TALKING) {
        if (Message_GetState(&play->msgCtx) == TEXT_STATE_CLOSING) {
            this->actor.flags &= ~ACTOR_FLAG_TALK;
            this->stateFlags1 &= ~(PLAYER_STATE1_TALKING | PLAYER_STATE1_29);
            this->focusActor = NULL;
        }
    } else if (this->talkActor != NULL && CHECK_BTN_ALL(input->press.button, BTN_A)) {
        Actor* actor = this->talkActor;

        actor->flags |= ACTOR_FLAG_TALK;
        this->exchangeItemId = EXCH_ITEM_NONE;
        if (actor->textId != 0xFFFF) {
            this->actor.flags |= ACTOR_FLAG_TALK;
            this->actor.textId = actor->textId;
            this->stateFlags1 |= PLAYER_STATE1_TALKING | PLAYER_STATE1_29;
            if (this->actor.textId != 0) {
                Message_StartTextbox(play, this->actor.textId, actor);
                this->focusActor = actor;
            }
        }
    }
    if (ACTOR_FLAGS_CHECK_ALL(&this->actor, ACTOR_FLAG_TALK)) {
        this->talkActorDistance = 0.0f;
    } else {
        this->talkActor = NULL;
        this->talkActorDistance = MAXFLOAT;
        this->exchangeItemId = EXCH_ITEM_NONE;
    }
}

/* Player_UpdateCommon's OC part: last frame's cylinder was checked at the
 * start of this update (CollisionCheck_OC), so the displacement in
 * colChkInfo is the push from immovable/heavier actors (an En_Ko blocking a
 * path). The real player applies it in Actor_UpdatePos; the C player does. */
static void PlayerProxy_UpdateBody(Player* this, PlayState* play) {
    gOotCorePlayerPushX += (s32)this->actor.colChkInfo.displacement.x;
    gOotCorePlayerPushZ += (s32)this->actor.colChkInfo.displacement.z;
    this->actor.colChkInfo.mass = (this->stateFlags1 & PLAYER_STATE1_29) ? MASS_IMMOVABLE : 50;
    Collider_UpdateCylinder(&this->actor, &this->cylinder);
    CollisionCheck_SetOC(play, &play->colChkCtx, &this->cylinder.base);
}

static void PlayerProxy_Update(Actor* thisx, PlayState* play) {
    PlayerProxy_Sync(thisx);
    PlayerProxy_UpdateBody((Player*)thisx, play);
    PlayerProxy_GetItem((Player*)thisx, play);
    PlayerProxy_UpdateSword((Player*)thisx, play);
    PlayerProxy_UpdateTalk((Player*)thisx, play);
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
