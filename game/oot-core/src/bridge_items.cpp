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
#include "overlays/actors/ovl_Arrow_Fire/z_arrow_fire.h"
#include "overlays/actors/ovl_Arrow_Ice/z_arrow_ice.h"
#include "overlays/actors/ovl_Arrow_Light/z_arrow_light.h"

extern PlayState* gOotCorePlay;
void ArmsHook_Wait(ArmsHook* this, PlayState* play);
void ArmsHook_Shoot(ArmsHook* this, PlayState* play);
void EnArrow_Fly(EnArrow* this, PlayState* play);
void Actor_UpdateFlaggedAudio(Actor* actor);

static OotCoreToolView sViews[OOT_CORE_TOOL_VIEWS_MAX];
static Vec3f sHand;
static Actor* sHeld;      /* bomb/chu over Link's head, parent = player */
static Actor* sHook;      /* live Arms_Hook */
static u8 sLastItem, sLastOk, sDebugHold; /* debug row: last C use */
static struct { Actor* actor; u16 serial; } sToolIds[16];
static u16 sToolSerial;
static const u8 sToolCats[] = { ACTORCAT_ITEMACTION, ACTORCAT_EXPLOSIVE, ACTORCAT_MISC };

static bool tool_live_pointer(const Actor* candidate) {
    if (!candidate || !gOotCorePlay) return false;
    for (int i = 0; i < 3; ++i)
        for (Actor* a = gOotCorePlay->actorCtx.actorLists[sToolCats[i]].head; a; a = a->next)
            if (a == candidate && a->update) return true;
    return false;
}

static u16 tool_identity(Actor* actor, bool spawned) {
    int slot = -1;
    for (int i = 0; i < 16; ++i) {
        if (sToolIds[i].actor == actor) {
            if (!spawned) return sToolIds[i].serial;
            slot = i; break; /* allocator reused an address: new attack */
        }
        if (slot < 0 && !tool_live_pointer(sToolIds[i].actor)) slot = i;
    }
    if (slot < 0) return 0; /* current tool bounds cannot fill sixteen rows */
    if (++sToolSerial == 0) ++sToolSerial;
    sToolIds[slot].actor = actor;
    return sToolIds[slot].serial = sToolSerial;
}

/* Draw-only symbols of the tool actors: the host draws baked sprites, so
 * these display lists are never sent anywhere (one word each, as keep_ph). */
Gfx gBombCapDL[1], gBombBodyDL[1], gBombchuDL[1], gBoomerangRefDL[1], gEffSparklesDL[1];
#ifndef PLAYER_SOURCE /* object_link_boy placeholders own them with the real Player */
Gfx gLinkAdultHookshotTipDL[1], gLinkAdultHookshotChainDL[1];
#endif
/* gameplay_keep arrow clips: the sprite keeps only their clock (frames). */
AnimationHeader gArrow1_Anim = { { 5 } };
AnimationHeader gArrow2_Anim = { { 5 } };

s32 Camera_RequestQuake(Camera* camera, s32 unused, s16 y, s32 duration) {
    return 0; /* no camera shake: the C camera owns the view */
}

/* ---- z_player_lib functions the tool actors call --------------------- */
#ifndef PLAYER_SOURCE   /* real z_player_lib owns these with the source Player */
int Player_HoldsHookshot(Player* this) {
    return (this->heldItemAction == PLAYER_IA_HOOKSHOT) || (this->heldItemAction == PLAYER_IA_LONGSHOT);
}
int Player_IsBurningStickInRange(PlayState* play, Vec3f* pos, f32 xzRange, f32 yRange) {
    return false; /* C owns the Deku Stick; its fire reaches bombs via C contacts */
}
int Player_InBlockingCsMode(PlayState* play, Player* this) {
    return false;
}
#endif

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

/* Every admitted tool needs a host sprite/view slot, including stuck arrows.
 * A lodged arrow must not lock the bow until its sixty-frame decay ends. */
static bool tool_has_room(void) {
    int count = 0;
    for (int i = 0; i < 3; ++i)
        for (Actor* a = gOotCorePlay->actorCtx.actorLists[sToolCats[i]].head; a; a = a->next)
            if (a->update && (a->id == ACTOR_EN_ARROW || a->id == ACTOR_ARMS_HOOK ||
                a->id == ACTOR_EN_BOOM || a->id == ACTOR_EN_BOM || a->id == ACTOR_EN_BOM_CHU))
                ++count;
    return count < OOT_CORE_TOOL_VIEWS_MAX;
}

/* Draw-free tool anchors. Local source coordinates are scaled by .01, then
 * rotated with the projectile. Keeping a finite width is essential: feeding
 * current/previous center points makes a zero-area AT quad along straight shots. */
static Vec3f tool_point(Actor* actor, int y, int z) {
    f32 sx = Math_SinS(actor->world.rot.x), cx = Math_CosS(actor->world.rot.x);
    f32 sy = Math_SinS(actor->world.rot.y), cy = Math_CosS(actor->world.rot.y);
    f32 forward = sx * y + cx * z;
    Vec3f p = actor->world.pos;
    p.x += sy * forward;
    p.y += cx * y - sx * z;
    p.z += cy * forward;
    return p;
}

static void tool_quad(PlayState* play, Actor* actor, ColliderQuad* collider, WeaponInfo* weapon,
                      int width, int forward) {
    Vec3f a = tool_point(actor, width, forward);
    Vec3f b = tool_point(actor, -width, forward);
    Player_UpdateWeaponInfo(play, collider, weapon, &a, &b);
}

static void tool_clear_hook(Player* player) {
    if (player->heldActor == sHook) player->heldActor = NULL;
    if (player->actor.child == sHook) player->actor.child = NULL;
    if (player->actor.parent == sHook) player->actor.parent = NULL;
    sHook = NULL;
    player->heldItemAction = player->itemAction = PLAYER_IA_NONE;
}

/* io: [0] ItemId, [1..3] origin, [4] yaw, [5] pitch (+ up). */
static int tool_use(const int* io) {
    PlayState* play = gOotCorePlay;
    Player* player = GET_PLAYER(play);
    s16 yaw = (s16)io[4];
    s16 rotX = (s16)-io[5]; /* Actor_SetProjectileSpeed: +rot.x is down */
    Actor* a;

    if (!tool_has_room()) return 0;

    switch (io[0]) {
        case ITEM_BOW:
        case ITEM_ARROW_FIRE:
        case ITEM_ARROW_ICE:
        case ITEM_ARROW_LIGHT: {
            static const s16 params[4] = { ARROW_NORMAL, ARROW_FIRE, ARROW_ICE, ARROW_LIGHT };
            s32 kind = io[0] == ITEM_BOW ? 0 : io[0] == ITEM_ARROW_FIRE ? 1 : io[0] == ITEM_ARROW_ICE ? 2 : 3;
            a = Actor_SpawnAsChild(&play->actorCtx, &player->actor, play, ACTOR_EN_ARROW, io[1], io[2], io[3],
                                   rotX, yaw, 0, params[kind]);
            if (a == NULL)
                return 0;
            a->world.rot.x = a->shape.rot.x = rotX;
            a->parent = NULL;       /* released this step: EnArrow_Shoot */
            player->actor.child = NULL;
            tool_identity(a, true);
            player->unk_A73 = 4;
            return 1;
        }
        case ITEM_SLINGSHOT:
            a = Actor_SpawnAsChild(&play->actorCtx, &player->actor, play, ACTOR_EN_ARROW, io[1], io[2], io[3],
                                   rotX, yaw, 0, ARROW_SEED);
            if (a == NULL) return 0;
            a->parent = NULL;
            player->actor.child = NULL;
            player->unk_A73 = 4;
            tool_identity(a, true);
            return 1;
        case ITEM_BOMB:
        case ITEM_BOMBCHU: {
            s16 id = io[0] == ITEM_BOMB ? ACTOR_EN_BOM : ACTOR_EN_BOM_CHU;
            if (sHeld != NULL || count_live(ACTOR_EN_BOM) + count_live(ACTOR_EN_BOM_CHU) >= 3)
                return 0;
            a = Actor_SpawnAsChild(&play->actorCtx, &player->actor, play, id, sHand.x, sHand.y, sHand.z, 0, yaw,
                                   0, 0);
            if (a == NULL)
                return 0;
            sHeld = a;
            tool_identity(a, true);
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
            tool_identity(&boom->actor, true);
            boom->moveTo = player->focusActor;
            boom->returnTimer = 20;
            player->stateFlags1 |= PLAYER_STATE1_BOOMERANG_THROWN;
            player->unk_A73 = 4;
            Actor_PlaySfx(&player->actor, NA_SE_IT_BOOMERANG_THROW); /* Player's throw */
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
            if (a->init == NULL) {
                /* ArmsHook_Draw writes the flight tip. Prime both endpoints
                 * before the first source line test, away from world origin. */
                ((ArmsHook*)a)->unk_1E8 = ((ArmsHook*)a)->unk_1F4 = tool_point(a, 0, 9);
            }
            tool_identity(a, true);
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
    if (!tool_live_pointer(a))
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
#ifndef PLAYER_SOURCE
    /* Proxy-era release/carry timers must not run a second time on the real
     * Player. Its Update owns unk_A73, heldActor and returning hook state. */
    bool pendingArrow = false;
    for (a = play->actorCtx.actorLists[ACTORCAT_ITEMACTION].head; a; a = a->next)
        if (a->id == ACTOR_EN_ARROW && a->update && (a->init != NULL || ((EnArrow*)a)->timer == 0))
            pendingArrow = true;
    if (pendingArrow) player->unk_A73 = 4; /* deferred object init must not eat release */
    else if (player->unk_A73 != 0) player->unk_A73--;
    if (sHeld != NULL) {
        if (!tool_live_pointer(sHeld)) {
            if (player->heldActor == sHeld) player->heldActor = NULL;
            if (player->actor.child == sHeld) player->actor.child = NULL;
            player->stateFlags1 &= ~PLAYER_STATE1_CARRYING_ACTOR;
            sHeld = NULL; /* exploded in hand: EnBom_Explode cleared the carry */
        } else {
            sHeld->world.pos = sHand;
            sHeld->world.pos.y += 12.0f;
        }
    }
    if (sHook != NULL && !tool_live_pointer(sHook)) tool_clear_hook(player);
    /* Back in ArmsHook_Wait with a parent: retracted, or Link arrived
     * (ArmsHook_AttachToPlayer). Put the hookshot away. */
    if (sHook != NULL && sHook->init == NULL && ((ArmsHook*)sHook)->actionFunc == ArmsHook_Wait && sHook->parent != NULL) {
        Actor_Kill(sHook);
        tool_clear_hook(player);
    }
    if ((player->stateFlags1 & PLAYER_STATE1_BOOMERANG_THROWN) &&
        find_live(ACTORCAT_MISC, ACTOR_EN_BOOM) == NULL)
        player->stateFlags1 &= ~PLAYER_STATE1_BOOMERANG_THROWN;
#endif
    /* Actor_DrawAll's Actor_UpdateFlaggedAudio: held tool sounds (hookshot
     * chain on Player, boomerang flight, Bombchu motor) need it to play. */
    if (player->actor.sfx != 0) Actor_UpdateFlaggedAudio(&player->actor);
    for (int cat = 0; cat < 3; ++cat)
        for (a = play->actorCtx.actorLists[sToolCats[cat]].head; a != NULL; a = a->next)
            if (a->update != NULL && a->sfx != 0) Actor_UpdateFlaggedAudio(a);
    /* Preserve the gameplay side effects of source Draw without meshes. */
    for (int cat = 0; cat < 3; ++cat)
    for (a = play->actorCtx.actorLists[sToolCats[cat]].head; a != NULL; a = a->next) {
        if (a->update == NULL || a->init != NULL)
            continue;
        if (a->id == ACTOR_EN_ARROW) {
            EnArrow* arrow = (EnArrow*)a;
            arrow->unk_21C = tool_point(a, 0, -3);
            if (arrow->actionFunc == EnArrow_Fly && a->params <= ARROW_SEED && arrow->hitActor == NULL)
                tool_quad(play, a, &arrow->collider, &arrow->weaponInfo, 4, 15);
            else arrow->weaponInfo.active = false;
        } else if (a->id == ACTOR_EN_BOOM) {
            /* Source half span is 9.6 units; round to ten for the sprite. */
            tool_quad(play, a, &((EnBoom*)a)->collider, &((EnBoom*)a)->weaponInfo, 10, 0);
        } else if (a->id == ACTOR_ARMS_HOOK) {
            ArmsHook* hook = (ArmsHook*)a;
            bool flying = hook->actionFunc == ArmsHook_Shoot && hook->timer > 0;
            hook->unk_1E8 = tool_point(a, 0, flying ? 9 : 0);
            if (hook->actionFunc == ArmsHook_Wait) hook->unk_1F4 = hook->unk_1E8;
            if (flying) tool_quad(play, a, &hook->collider, &hook->weaponInfo, 5, 12);
            else hook->weaponInfo.active = false;
        }
    }
    /* EnBom_Draw updates the body center only. Once it explodes, that center
     * remains fixed even if Player still carries the actor; EnBom_Explode owns
     * the growing radius. No unrelated renderer matrix or radius reset. */
    for (a = play->actorCtx.actorLists[ACTORCAT_EXPLOSIVE].head; a != NULL; a = a->next)
        if (a->id == ACTOR_EN_BOM && a->update != NULL && a->init == NULL && a->params == BOMB_BODY) {
            Vec3s* center = &((EnBom*)a)->explosionCollider.elements[0].dim.worldSphere.center;
            center->x = (s16)a->world.pos.x;
            center->y = (s16)a->world.pos.y;
            center->z = (s16)a->world.pos.z;
        }
}

void OotCore_ToolReset(void) {
    sHeld = sHook = NULL;
    for (int i = 0; i < 16; ++i) sToolIds[i].actor = NULL;
}

int OotCore_ToolCommand(unsigned int command, int* io) {
    PlayState* play = gOotCorePlay;
    Player* player;

    if (play == NULL || (player = GET_PLAYER(play)) == NULL)
        return 0;
#ifdef PLAYER_SOURCE
    if (command >= OOT_CORE_TOOL_CARRY_OFFER && command <= OOT_CORE_TOOL_CARRY_CANCEL) {
        extern int OotCore_CarryCommand(PlayState*, unsigned int, int*);
        return OotCore_CarryCommand(play, command, io);
    }
#endif
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
            extern u8 gOotCoreMagicReset;
            int bits = 0;
            if (gOotCoreMagicReset) {
                bits |= OOT_CORE_TOOL_MAGIC_RESET;
                gOotCoreMagicReset = 0;
            }
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
            /* Arrow*_Draw's full-screen hit fill, prim (rgb * k, alpha 150 * k)
             * over the scene, as a VDP2 colour-offset per channel in io[3..5]
             * (approximate: blended against mid grey). Strongest arrow wins. */
            io[3] = io[4] = io[5] = 0;
            for (Actor* m = play->actorCtx.actorLists[ACTORCAT_ITEMACTION].head; m != NULL; m = m->next) {
                static const u8 prim[3][3] = { { 40, 0, 0 }, { 0, 10, 50 }, { 30, 40, 0 } };
                s32 e, k, c;
                if (m->update == NULL) continue;
                if (m->id == ACTOR_ARROW_FIRE) { e = 0; k = (s32)(((ArrowFire*)m)->unk_15C * 256.0f); }
                else if (m->id == ACTOR_ARROW_ICE) { e = 1; k = (s32)(((ArrowIce*)m)->unk_164 * 256.0f); }
                else if (m->id == ACTOR_ARROW_LIGHT) { e = 2; k = (s32)(((ArrowLight*)m)->unk_164 * 256.0f); }
                else continue;
                if (k <= 0) continue;
                if (k > 256) k = 256;
                for (c = 0; c < 3; ++c) {
                    s32 offset = (prim[e][c] * k / 256 - 128) * (150 * k / 255) / 256;
                    if (offset < io[3 + c]) io[3 + c] = offset;
                }
            }
            return bits;
        }
        case OOT_CORE_TOOL_CANCEL:
            if (sHeld != NULL)
                tool_throw();
            if (tool_live_pointer(sHook))
                Actor_Kill(sHook);
            if (sHook != NULL) tool_clear_hook(player);
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
    PlayState* play = gOotCorePlay;
    s32 i, n = 0;
    Actor* a;

    *out = sViews;
    if (play == NULL)
        return 0;
    for (i = 0; i < 3; i++)
        for (a = play->actorCtx.actorLists[sToolCats[i]].head; a != NULL && n < OOT_CORE_TOOL_VIEWS_MAX; a = a->next) {
            OotCoreToolView* v = &sViews[n];
            if (a->update == NULL || (a->id != ACTOR_EN_ARROW && a->id != ACTOR_EN_BOM && a->id != ACTOR_EN_BOM_CHU &&
                                      a->id != ACTOR_EN_BOOM && a->id != ACTOR_ARMS_HOOK &&
                                      a->id != ACTOR_ARROW_FIRE && a->id != ACTOR_ARROW_ICE &&
                                      a->id != ACTOR_ARROW_LIGHT))
                continue;
            v->id = a->id;
            v->attack_id = tool_identity(a, false);
            v->params = a->params;
            v->x = (s32)a->world.pos.x;
            v->y = (s32)a->world.pos.y;
            v->z = (s32)a->world.pos.z;
            v->previous_x = (s32)a->prevPos.x;
            v->previous_y = (s32)a->prevPos.y;
            v->previous_z = (s32)a->prevPos.z;
            v->yaw = a->shape.rot.y;
            v->pitch = (s16)-a->shape.rot.x;
            /* Flying hooks retain their parent in ArmsHook_Shoot. That link
             * is ownership, not held state; host collision must see flight. */
            v->held = a->id != ACTOR_ARMS_HOOK && a->parent == &GET_PLAYER(play)->actor;
            v->radius = 0;
            v->timer = 0;
            v->dmg = 0;
            v->damage = 0;
            if (a->id == ACTOR_EN_BOM) {
                EnBom* b = (EnBom*)a;
                v->timer = (u16)b->timer;
                v->flash = (u8)(s32)b->flashIntensity;
                if (a->params == BOMB_EXPLOSION) {
                    /* The source retains parent until the blast finishes;
                     * its live explosion must still hit host-side victims. */
                    v->held = 0;
                    const Vec3s* center = &b->explosionCollider.elements[0].dim.worldSphere.center;
                    v->x = v->previous_x = center->x;
                    v->y = v->previous_y = center->y;
                    v->z = v->previous_z = center->z;
                    v->radius = b->explosionCollider.elements[0].dim.worldSphere.radius;
                    v->dmg = b->explosionCollider.elements[0].base.atDmgInfo.dmgFlags;
                    v->damage = b->explosionCollider.elements[0].base.atDmgInfo.damage;
                }
            } else if (a->id == ACTOR_EN_ARROW) {
                EnArrow* arrow = (EnArrow*)a;
                if (a->init == NULL && arrow->actionFunc == EnArrow_Fly && arrow->hitActor == NULL) {
                    v->dmg = arrow->collider.elem.atDmgInfo.dmgFlags;
                    v->damage = arrow->collider.elem.atDmgInfo.damage;
                }
                v->pitch = (s16)-a->shape.rot.x;
            } else if (a->id == ACTOR_EN_BOOM) {
                v->dmg = ((EnBoom*)a)->collider.elem.atDmgInfo.dmgFlags;
                v->damage = ((EnBoom*)a)->collider.elem.atDmgInfo.damage;
                v->pitch = 0;
            } else if (a->id == ACTOR_ARMS_HOOK) {
                ArmsHook* hook = (ArmsHook*)a;
                if (a->init == NULL && hook->actionFunc == ArmsHook_Shoot && hook->timer > 0) {
                    v->dmg = hook->collider.elem.atDmgInfo.dmgFlags;
                    v->damage = hook->collider.elem.atDmgInfo.damage;
                }
                v->pitch = (s16)-a->shape.rot.x;
            } else if (a->id == ACTOR_EN_BOM_CHU) {
                v->timer = (u16)((EnBomChu*)a)->timer;
            } else if (a->id == ACTOR_ARROW_FIRE || a->id == ACTOR_ARROW_ICE || a->id == ACTOR_ARROW_LIGHT) {
                /* Presentation only (no AT): params = element, timer = the
                 * Arrow*_Hit countdown (0 in charge/flight), flash = alpha. */
                v->params = a->id == ACTOR_ARROW_FIRE ? 0 : a->id == ACTOR_ARROW_ICE ? 1 : 2;
                v->timer = a->id == ACTOR_ARROW_FIRE ? ((ArrowFire*)a)->timer
                         : a->id == ACTOR_ARROW_ICE ? ((ArrowIce*)a)->timer : ((ArrowLight*)a)->timer;
                v->flash = a->id == ACTOR_ARROW_FIRE ? ((ArrowFire*)a)->alpha
                         : a->id == ACTOR_ARROW_ICE ? ((ArrowIce*)a)->alpha : ((ArrowLight*)a)->alpha;
                v->held = 0;
            }
            n++;
        }
    return n;
}
