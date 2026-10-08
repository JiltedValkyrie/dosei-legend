/*
 * Link's C-button tools on the real decomp actors (En_Arrow, En_Bom,
 * En_Bom_Chu, En_Boom, Arms_Hook). Link is still the C player, so this file
 * plays the z_player side of each item the way the player proxy plays the
 * sword: spawn, aim, release, carry and hookshot flight are reduced to the
 * fields those actors read. APPROXIMATE (Saturn cut): no upper-body item
 * animation, the C side supplies the hand point and the aim.
 *
 * Source refs (z_player.c): arrows 2817/13849 (Actor_SpawnAsChild, unk_A73
 * = 4 on release), explosives sExplosiveInfos + func_8084409C throw
 * (speedXZ + 8, velocity.y 12 standing), boomerang func_808359FC (spawn 10
 * ahead, y + 30, returnTimer 20, BOOMERANG_THROWN), hookshot 2464.
 */
#include "oot_prelude.h"
#include "ultra64.h"
#include "actor.h"
#include "play_state.h"
#include "player.h"
#include "item.h"
#include "z_lib.h"
#include "z_math.h"
#include "collision_check.h"
#include "sfx.h"
#include "animation.h"
#include "camera.h"
#include "oot_core_api.h"
#include "overlays/actors/ovl_En_Arrow/z_en_arrow.h"
#include "overlays/actors/ovl_En_Bom/z_en_bom.h"
#include "overlays/actors/ovl_En_Bom_Chu/z_en_bom_chu.h"
#include "overlays/actors/ovl_En_Boom/z_en_boom.h"
#include "overlays/actors/ovl_Arms_Hook/z_arms_hook.h"

extern PlayState* gOotCorePlay;
void ArmsHook_Wait(ArmsHook* this, PlayState* play);

static OotCoreToolView sViews[OOT_CORE_TOOL_VIEWS_MAX];
static Vec3f sHand;
static Actor* sHeld;      /* bomb/chu over Link's head, parent = player */
static Actor* sHook;      /* live Arms_Hook */
static u8 sLastItem, sLastOk, sDebugHold; /* debug row: last C use */

/* Draw-only symbols of the tool actors: the host draws baked sprites, so
 * these display lists are never sent anywhere (one word each, as keep_ph). */
Gfx gBombCapDL[1], gBombBodyDL[1], gBombchuDL[1], gBoomerangRefDL[1], gEffSparklesDL[1];
Gfx gLinkAdultHookshotTipDL[1], gLinkAdultHookshotChainDL[1];
/* gameplay_keep arrow clips: the sprite keeps only their clock (frames). */
AnimationHeader gArrow1_Anim = { { 5 } };
AnimationHeader gArrow2_Anim = { { 5 } };

s32 Camera_RequestQuake(Camera* camera, s32 unused, s16 y, s32 duration) {
    return 0; /* no camera shake: the C camera owns the view */
}

/* ---- z_player_lib functions the tool actors call --------------------- */
int Player_HoldsHookshot(Player* this) {
    return (this->heldItemAction == PLAYER_IA_HOOKSHOT) || (this->heldItemAction == PLAYER_IA_LONGSHOT);
}
int Player_IsBurningStickInRange(PlayState* play, Vec3f* pos, f32 xzRange, f32 yRange) {
    return false; /* C owns the Deku Stick; its fire reaches bombs via C contacts */
}
int Player_InBlockingCsMode(PlayState* play, Player* this) {
    return false;
}

static s32 count_live(s16 id) {
    s32 n = 0;
    Actor* a;
    for (a = gOotCorePlay->actorCtx.actorLists[ACTORCAT_EXPLOSIVE].head; a != NULL; a = a->next)
        if (a->id == id && a->update != NULL)
            n++;
    return n;
}

static Actor* find_live(s32 category, s16 id) {
    Actor* a;
    for (a = gOotCorePlay->actorCtx.actorLists[category].head; a != NULL; a = a->next)
        if (a->id == id && a->update != NULL)
            return a;
    return NULL;
}

/* io: [0] ItemId, [1..3] origin, [4] yaw, [5] pitch (+ up). */
static int tool_use(const int* io) {
    PlayState* play = gOotCorePlay;
    Player* player = GET_PLAYER(play);
    s16 yaw = (s16)io[4];
    s16 rotX = (s16)-io[5]; /* Actor_SetProjectileSpeed: +rot.x is down */
    Actor* a;

    switch (io[0]) {
        case ITEM_BOW:
        case ITEM_ARROW_FIRE:
        case ITEM_ARROW_ICE:
        case ITEM_ARROW_LIGHT: {
            static const s16 params[4] = { ARROW_NORMAL, ARROW_FIRE, ARROW_ICE, ARROW_LIGHT };
            s32 kind = io[0] == ITEM_BOW ? 0 : io[0] == ITEM_ARROW_FIRE ? 1 : io[0] == ITEM_ARROW_ICE ? 2 : 3;
            if (find_live(ACTORCAT_ITEMACTION, ACTOR_EN_ARROW) != NULL) /* one in flight */
                return 0;
            a = Actor_SpawnAsChild(&play->actorCtx, &player->actor, play, ACTOR_EN_ARROW, io[1], io[2], io[3],
                                   rotX, yaw, 0, params[kind]);
            if (a == NULL)
                return 0;
            a->world.rot.x = a->shape.rot.x = rotX;
            a->parent = NULL;       /* released this step: EnArrow_Shoot */
            player->unk_A73 = 4;
            return 1;
        }
        case ITEM_BOMB:
        case ITEM_BOMBCHU: {
            s16 id = io[0] == ITEM_BOMB ? ACTOR_EN_BOM : ACTOR_EN_BOM_CHU;
            if (sHeld != NULL || count_live(id) >= 3)
                return 0;
            a = Actor_SpawnAsChild(&play->actorCtx, &player->actor, play, id, sHand.x, sHand.y, sHand.z, 0, yaw,
                                   0, 0);
            if (a == NULL)
                return 0;
            sHeld = a;
            player->heldActor = a;
            player->stateFlags1 |= PLAYER_STATE1_CARRYING_ACTOR;
            return 1;
        }
        case ITEM_BOOMERANG: {
            EnBoom* boom;
            if (player->stateFlags1 & PLAYER_STATE1_BOOMERANG_THROWN)
                return 0;
            boom = (EnBoom*)Actor_Spawn(&play->actorCtx, play, ACTOR_EN_BOOM,
                                        io[1] + (Math_SinS(yaw) * 10.0f), player->actor.world.pos.y + 30.0f,
                                        io[3] + (Math_CosS(yaw) * 10.0f), rotX, yaw, 0, 0);
            if (boom == NULL)
                return 0;
            player->boomerangActor = &boom->actor;
            boom->moveTo = player->focusActor;
            boom->returnTimer = 20;
            player->stateFlags1 |= PLAYER_STATE1_BOOMERANG_THROWN;
            player->unk_A73 = 4;
            return 1;
        }
        case ITEM_HOOKSHOT:
        case ITEM_LONGSHOT:
            if (sHook != NULL)
                return 0;
            player->heldItemAction = player->itemAction =
                io[0] == ITEM_HOOKSHOT ? PLAYER_IA_HOOKSHOT : PLAYER_IA_LONGSHOT;
            Math_Vec3f_Copy(&player->unk_3C8, &sHand);
            a = Actor_SpawnAsChild(&play->actorCtx, &player->actor, play, ACTOR_ARMS_HOOK, io[1], io[2], io[3],
                                   rotX, yaw, 0, 0);
            if (a == NULL) {
                player->heldItemAction = player->itemAction = PLAYER_IA_NONE;
                return 0;
            }
            a->world.rot.x = a->shape.rot.x = rotX;
            a->parent = NULL; /* ArmsHook_Wait: shoot this step */
            sHook = a;
            player->heldActor = a;
            return 1;
    }
    return 0;
}

/* func_8084409C: standing throw speedXZ + 8, velocity.y 12; a Bombchu is
 * set down with no speed and drives itself. */
static int tool_throw(void) {
    Player* player = GET_PLAYER(gOotCorePlay);
    Actor* a = sHeld;
    if (a == NULL)
        return 0;
    if (a->update != NULL) {
        a->world.rot.y = player->actor.shape.rot.y;
        if (a->id == ACTOR_EN_BOM_CHU) {
            a->world.pos = player->actor.world.pos;
            a->speed = 0.0f;
            a->velocity.y = 0.0f;
        } else {
            a->speed = 8.0f;
            a->velocity.y = 12.0f;
        }
        a->parent = NULL;
        Actor_PlaySfx(&player->actor, NA_SE_PL_THROW);
    }
    player->actor.child = NULL;
    player->heldActor = NULL;
    player->stateFlags1 &= ~PLAYER_STATE1_CARRYING_ACTOR;
    sHeld = NULL;
    return 1;
}

/* After Actor_UpdateAll: hold bombs, end released tools, report flight. */
void OotCore_ToolStep(PlayState* play) {
    Player* player = GET_PLAYER(play);
    Actor* a;

    if (player == NULL)
        return;
    if (player->unk_A73 != 0)
        player->unk_A73--;
    if (sHeld != NULL) {
        if (sHeld->update == NULL) {
            sHeld = NULL; /* exploded in hand: EnBom_Explode cleared the carry */
        } else {
            sHeld->world.pos = sHand;
            sHeld->world.pos.y += 12.0f;
        }
    }
    if (sHook != NULL && sHook->update == NULL) {
        sHook = NULL;
        player->heldItemAction = player->itemAction = PLAYER_IA_NONE;
        if (player->heldActor != NULL && player->heldActor->update == NULL)
            player->heldActor = NULL;
        player->actor.parent = NULL;
    }
    /* Back in ArmsHook_Wait with a parent: retracted, or Link arrived
     * (ArmsHook_AttachToPlayer). Put the hookshot away. */
    if (sHook != NULL && ((ArmsHook*)sHook)->actionFunc == ArmsHook_Wait && sHook->parent != NULL) {
        Actor_Kill(sHook);
        sHook = NULL;
        player->heldItemAction = player->itemAction = PLAYER_IA_NONE;
        player->heldActor = NULL;
        player->actor.parent = NULL;
    }
    if ((player->stateFlags1 & PLAYER_STATE1_BOOMERANG_THROWN) &&
        find_live(ACTORCAT_ITEMACTION, ACTOR_EN_BOOM) == NULL)
        player->stateFlags1 &= ~PLAYER_STATE1_BOOMERANG_THROWN;
    /* EnBoom_Draw / ArmsHook_Draw place their AT quads; with no actor draw
     * the swept line is last position -> this position. */
    for (a = play->actorCtx.actorLists[ACTORCAT_ITEMACTION].head; a != NULL; a = a->next) {
        if (a->update == NULL)
            continue;
        if (a->id == ACTOR_EN_BOOM)
            Player_UpdateWeaponInfo(play, &((EnBoom*)a)->collider, &((EnBoom*)a)->weaponInfo, &a->world.pos,
                                    &a->prevPos);
        else if (a->id == ACTOR_ARMS_HOOK && ((ArmsHook*)a)->actionFunc != ArmsHook_Wait)
            Player_UpdateWeaponInfo(play, &((ArmsHook*)a)->collider, &((ArmsHook*)a)->weaponInfo,
                                    &a->world.pos, &a->prevPos);
    }
    /* EnBom_Draw's Collider_UpdateSpheres: the host draws tools, so the
     * blast sphere is placed here once it has a radius. */
    for (a = play->actorCtx.actorLists[ACTORCAT_EXPLOSIVE].head; a != NULL; a = a->next)
        if (a->id == ACTOR_EN_BOM && a->update != NULL)
            Collider_UpdateSpheres(0, &((EnBom*)a)->explosionCollider);
}

void OotCore_ToolReset(void) {
    sHeld = sHook = NULL;
}

int OotCore_ToolCommand(unsigned int command, int* io) {
    PlayState* play = gOotCorePlay;
    Player* player;

    if (play == NULL || (player = GET_PLAYER(play)) == NULL)
        return 0;
    switch (command) {
        case OOT_CORE_TOOL_HAND:
            sHand.x = io[0];
            sHand.y = io[1];
            sHand.z = io[2];
            Math_Vec3f_Copy(&player->unk_3C8, &sHand); /* hookshot origin follows the hand */
            return 1;
        case OOT_CORE_TOOL_USE: {
            int ok = tool_use(io);
            sLastItem = (u8)io[0];
            sLastOk = (u8)ok;
            sDebugHold = 60;
            return ok;
        }
        case OOT_CORE_TOOL_THROW:
            return tool_throw();
        case OOT_CORE_TOOL_STATE: {
            int bits = 0;
            if (sHeld != NULL)
                bits |= OOT_CORE_TOOL_HOLDING;
            if (sHook != NULL)
                bits |= OOT_CORE_TOOL_HOOK_OUT;
            if (player->stateFlags1 & PLAYER_STATE1_BOOMERANG_THROWN)
                bits |= OOT_CORE_TOOL_BOOMERANG_OUT;
            /* ArmsHook_PullPlayer: player.parent = hook; velocity is the
             * whole remaining step per source frame (Q8 world units). */
            if (sHook != NULL && player->actor.parent == sHook) {
                bits |= OOT_CORE_TOOL_PULLING;
                io[0] = (s32)(player->actor.velocity.x * 256.0f);
                io[1] = (s32)(player->actor.velocity.y * 256.0f);
                io[2] = (s32)(player->actor.velocity.z * 256.0f);
            }
            return bits;
        }
        case OOT_CORE_TOOL_CANCEL:
            if (sHeld != NULL)
                tool_throw();
            if (sHook != NULL)
                Actor_Kill(sHook);
            return 1;
    }
    return 0;
}

/* Debug row 16 while a tool is live or just used: "T<item>:<ok> a<arrow
 * timer> h<hook timer><S shoot/W wait> c<chu timer><F floor/-> <speed>". */
int OotCore_ToolDebug(char* out) {
    static const char hex[] = "0123456789ABCDEF";
    PlayState* play = gOotCorePlay;
    Actor* a;
    char* p = out;
    if (play == NULL)
        return 0;
    if (sDebugHold != 0)
        sDebugHold--;
    *p++ = 'T';
    *p++ = hex[(sLastItem >> 4) & 15];
    *p++ = hex[sLastItem & 15];
    *p++ = ':';
    *p++ = (char)('0' + sLastOk);
    for (a = play->actorCtx.actorLists[ACTORCAT_ITEMACTION].head; a != NULL; a = a->next) {
        if (a->update == NULL)
            continue;
        if (a->id == ACTOR_EN_ARROW) {
            *p++ = ' '; *p++ = 'a'; *p++ = hex[(((EnArrow*)a)->timer >> 4) & 15]; *p++ = hex[((EnArrow*)a)->timer & 15];
            *p++ = a->init != NULL ? 'I' : a->parent != NULL ? 'H' : 'R';
            sDebugHold = 60;
        } else if (a->id == ACTOR_ARMS_HOOK) {
            *p++ = ' '; *p++ = 'h'; *p++ = hex[((ArmsHook*)a)->timer & 15];
            *p++ = ((ArmsHook*)a)->actionFunc == ArmsHook_Wait ? 'W' : 'S';
            *p++ = a->init != NULL ? 'I' : 'U';
            sDebugHold = 60;
        }
    }
    for (a = play->actorCtx.actorLists[ACTORCAT_EXPLOSIVE].head; a != NULL; a = a->next) {
        if (a->update == NULL)
            continue;
        if (a->id == ACTOR_EN_BOM) {
            /* b<fuse><I init pending|H held|R released><y fraction moving?> */
            *p++ = ' '; *p++ = 'b';
            *p++ = hex[(((EnBom*)a)->timer >> 4) & 15]; *p++ = hex[((EnBom*)a)->timer & 15];
            *p++ = a->init != NULL ? 'I' : a->parent != NULL ? 'H' : 'R';
            *p++ = hex[((s32)a->velocity.y) & 15];
            sDebugHold = 60;
            continue;
        }
        if (a->id != ACTOR_EN_BOM_CHU)
            continue;
        *p++ = ' '; *p++ = 'c';
        *p++ = hex[(((EnBomChu*)a)->timer >> 4) & 15]; *p++ = hex[((EnBomChu*)a)->timer & 15];
        *p++ = a->floorPoly != NULL ? 'F' : '-';
        *p++ = hex[((s32)a->speed) & 15];
        *p++ = a->parent != NULL ? 'H' : 'R';
        sDebugHold = 60;
    }
    *p++ = ' ';
    *p = 0;
    return sDebugHold != 0;
}

int OotCore_ToolView(const OotCoreToolView** out) {
    static const u8 cats[2] = { ACTORCAT_ITEMACTION, ACTORCAT_EXPLOSIVE };
    PlayState* play = gOotCorePlay;
    s32 i, n = 0;
    Actor* a;

    *out = sViews;
    if (play == NULL)
        return 0;
    for (i = 0; i < 2; i++)
        for (a = play->actorCtx.actorLists[cats[i]].head; a != NULL && n < OOT_CORE_TOOL_VIEWS_MAX; a = a->next) {
            OotCoreToolView* v = &sViews[n];
            if (a->update == NULL || (a->id != ACTOR_EN_ARROW && a->id != ACTOR_EN_BOM && a->id != ACTOR_EN_BOM_CHU &&
                                      a->id != ACTOR_EN_BOOM && a->id != ACTOR_ARMS_HOOK))
                continue;
            v->id = a->id;
            v->params = a->params;
            v->x = (s32)a->world.pos.x;
            v->y = (s32)a->world.pos.y;
            v->z = (s32)a->world.pos.z;
            v->attack_id = 0;
            v->previous_x = (s32)a->prevPos.x;
            v->previous_y = (s32)a->prevPos.y;
            v->previous_z = (s32)a->prevPos.z;
            v->damage = 0;
            v->yaw = a->shape.rot.y;
            v->pitch = (s16)-a->shape.rot.x;
            v->held = a->parent == &GET_PLAYER(play)->actor;
            v->radius = 0;
            v->timer = 0;
            v->dmg = 0;
            if (a->id == ACTOR_EN_BOM) {
                EnBom* b = (EnBom*)a;
                v->timer = (u16)b->timer;
                v->flash = (u8)(s32)b->flashIntensity;
                if (a->params == BOMB_EXPLOSION) {
                    v->radius = b->explosionCollider.elements[0].dim.worldSphere.radius;
                    v->dmg = b->explosionCollider.elements[0].base.atDmgInfo.dmgFlags;
                }
            } else if (a->id == ACTOR_EN_ARROW) {
                v->dmg = ((EnArrow*)a)->collider.elem.atDmgInfo.dmgFlags;
                v->pitch = (s16)-a->shape.rot.x;
            } else if (a->id == ACTOR_EN_BOOM) {
                v->dmg = ((EnBoom*)a)->collider.elem.atDmgInfo.dmgFlags;
                v->pitch = 0;
            } else if (a->id == ACTOR_ARMS_HOOK) {
                v->dmg = ((ArmsHook*)a)->collider.elem.atDmgInfo.dmgFlags;
                v->pitch = (s16)-a->shape.rot.x;
            } else if (a->id == ACTOR_EN_BOM_CHU) {
                v->timer = (u16)((EnBomChu*)a)->timer;
            }
            n++;
        }
    return n;
}
