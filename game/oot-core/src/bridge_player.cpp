/*
 * Player proxy. z_actor and most actors read GET_PLAYER(play) every frame,
 * but Link is still the C player (player_*.c). Until z_player is imported,
 * ACTOR_PLAYER is this stand-in: same profile header as z_player_call.c
 * (id, category, flags, object, sizeof(Player)), with an update that copies
 * C Link's pose in, source combat colliders and the existing item/talk
 * handshakes. C remains the health/movement owner until real Player cutover.
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
#include "save.h"
#include "bgcheck_bounds.h"
#include "oot_core_host.h"

extern const OotCoreHost* gOotCoreHost;
static OotCoreCombatState sCombat;
static u16 sSwordSwing;

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
static u8 sSariaSongTalk;

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

/* z_player_lib.c Player_UpdateWeaponInfo (file not imported yet; also used
 * by the tool actors, bridge_items.cpp):
 * the quad sweeps last frame's blade line to this frame's. */
u8 Player_UpdateWeaponInfo(PlayState* play, ColliderQuad* collider, WeaponInfo* weaponInfo,
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
        /* Saturn: C poses Link once per drawn frame, so catch-up steps see
         * the same blade. The real code drops AT here; that lost every
         * other hit below 30 fps. Keep the last swept quad live instead. */
        if (collider != NULL) {
            CollisionCheck_SetAT(play, &play->colChkCtx, &collider->base);
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
 * lines from the left hand). The host snapshot supplies source sword/stick
 * damage flags, including jump and spin attacks. */
static void PlayerProxy_UpdateSword(Player* this, PlayState* play) {
    WeaponInfo* w = &this->meleeWeaponInfo[1];
    this->meleeWeaponState = gOotCoreSwordActive ? 1 : 0;
    if (!gOotCoreSwordActive) {
        w->active = false; /* func_80832318 */
        return;
    }
    if (sSwordSwing != sCombat.swing) {
        w->active = false;
        sSwordSwing = sCombat.swing;
    }
    /* func_80837918 sword rows: Kokiri 1, Master 2, Biggoron 4. */
    if (!LINK_IS_ADULT) {
        this->meleeWeaponQuads[0].elem.atDmgInfo.dmgFlags = DMG_SLASH_KOKIRI;
        this->meleeWeaponQuads[0].elem.atDmgInfo.damage = 1;
    } else if (CUR_EQUIP_VALUE(EQUIP_TYPE_SWORD) == EQUIP_VALUE_SWORD_BIGGORON) {
        this->meleeWeaponQuads[0].elem.atDmgInfo.dmgFlags = DMG_SLASH_GIANT;
        this->meleeWeaponQuads[0].elem.atDmgInfo.damage = 4;
    } else {
        this->meleeWeaponQuads[0].elem.atDmgInfo.dmgFlags = DMG_SLASH_MASTER;
        this->meleeWeaponQuads[0].elem.atDmgInfo.damage = 2;
    }
    if (sCombat.damage_flags) {
        this->meleeWeaponQuads[0].elem.atDmgInfo.dmgFlags = sCombat.damage_flags;
        this->meleeWeaponQuads[0].elem.atDmgInfo.damage = sCombat.damage;
    }
    this->meleeWeaponQuads[0].elem.atElemFlags = ATELEM_ON | ATELEM_NEAREST;
    if (!w->active) {
        /* Saturn: the real first frame only primes (no AT). The decomp runs
         * 2 of 3 C steps in a short C swing, so that lost the slash start.
         * Like the C blade capsule (radius GP_BLADE_RADIUS 4), hit with the
         * blade itself, 8 units tall. Never sweep from the idle pose: that
         * is the sheath on Link's back (cut grass behind, 2026-10-03). */
        ColliderQuad* q = &this->meleeWeaponQuads[0];
        Vec3f a = gOotCoreSwordTip, b = gOotCoreSwordBase, c = gOotCoreSwordTip, d = gOotCoreSwordBase;
        a.y += 4;
        b.y += 4;
        c.y -= 4;
        d.y -= 4;
        Collider_ResetQuadAT(play, &q->base); /* new swing: clear hit list */
        Collider_SetQuadVertices(q, &b, &a, &d, &c);
        CollisionCheck_SetAT(play, &play->colChkCtx, &q->base);
        Math_Vec3f_Copy(&w->posA, &gOotCoreSwordTip);
        Math_Vec3f_Copy(&w->posB, &gOotCoreSwordBase);
        w->active = true;
        return;
    }
    Player_UpdateWeaponInfo(play, &this->meleeWeaponQuads[0], w, &gOotCoreSwordTip, &gOotCoreSwordBase);
}

/* Player_GetHeight's age-dependent eye height for actor attention. The real
 * player sets focus from the head limb; this proxy uses an integer anchor. */

static void PlayerProxy_Sync(Actor* thisx) {
    thisx->world.pos = gOotCorePlayerPos;
    thisx->world.rot.y = gOotCorePlayerYaw;
    thisx->shape.rot.y = gOotCorePlayerYaw;
    thisx->focus.pos = gOotCorePlayerPos;
    thisx->focus.pos.y = thisx->focus.pos.y + (LINK_IS_ADULT ? 68 : 44);
    thisx->focus.rot.y = gOotCorePlayerYaw;
    /* Floor switches, currents and actors read the equipped boots. */
    ((Player*)thisx)->currentBoots = (s8)(CUR_EQUIP_VALUE(EQUIP_TYPE_BOOTS) - 1);
    sCombat = {};
    if (gOotCoreHost && gOotCoreHost->player_combat) gOotCoreHost->player_combat(&sCombat);
    Player* player = (Player*)thisx;
    player->invincibilityTimer = (sCombat.flags & OOT_COMBAT_INTANGIBLE) ? 1 :
        (sCombat.flags & OOT_COMBAT_DODGE) ? -1 : 0;
    player->currentShield = sCombat.shield;
    if (sCombat.flags & OOT_COMBAT_SHIELD) player->stateFlags1 |= PLAYER_STATE1_SHIELDING;
    else player->stateFlags1 &= ~PLAYER_STATE1_SHIELDING;
}

static void PlayerProxy_Init(Actor* thisx, PlayState* play) {
    Player* this = (Player*)thisx;
    sSariaSongTalk = 0;
    sSwordSwing = 0;
    /* Player_Init: thisx->room = -1. Otherwise func_80031B14 deletes Player
     * on the first room change and every tool/talk loses GET_PLAYER. */
    thisx->room = -1;

    Collider_InitCylinder(play, &this->cylinder);
    Collider_SetCylinder(play, &this->cylinder, thisx, &sBodyCylinderInit);
    thisx->colChkInfo.mass = 50;
    Collider_InitQuad(play, &this->meleeWeaponQuads[0]);
    Collider_SetQuad(play, &this->meleeWeaponQuads[0], thisx, &sMeleeWeaponQuadInit);
    Collider_InitQuad(play, &this->shieldQuad);
    Collider_SetQuad(play, &this->shieldQuad, thisx, &sMeleeWeaponQuadInit);
    this->shieldQuad.base.atFlags = AT_ON | AT_TYPE_PLAYER;
    this->shieldQuad.base.colMaterial = COL_MATERIAL_METAL;
    this->shieldQuad.base.acFlags = AC_ON | AC_HARD | AC_TYPE_ENEMY;
    this->shieldQuad.elem.atElemFlags = ATELEM_ON | ATELEM_SFX_NORMAL;
    this->shieldQuad.elem.atDmgInfo.dmgFlags = DMG_SHIELD;
    this->shieldQuad.elem.atDmgInfo.damage = 0;
    this->shieldQuad.elem.acElemFlags = ACELEM_ON;
    this->shieldQuad.elem.acDmgInfo.dmgFlags = 0xDFCFFFFF;
    gOotCorePlayerPos = thisx->world.pos;
    gOotCorePlayerYaw = thisx->world.rot.y;
    PlayerProxy_Sync(thisx);
}

static void PlayerProxy_Destroy(Actor* thisx, PlayState* play) {
    Collider_DestroyCylinder(play, &((Player*)thisx)->cylinder);
    Collider_DestroyQuad(play, &((Player*)thisx)->meleeWeaponQuads[0]);
    Collider_DestroyQuad(play, &((Player*)thisx)->shieldQuad);
}

/* Player's get-item handling (func_8083E5A8) for the drops En_Item00 offers
 * with Actor_OfferGetItemNearby, and Ranch milk rewards. APPROXIMATE: given
 * at once without Link's hold-up animation. Ranch rewards retain the source
 * textbox/parent handshake; itemId/textId come from z_player sGetItemTable. */
static void PlayerProxy_GetItem(Player* this, PlayState* play) {
    u8 item;
    u16 textId = 0;

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
        case GI_BOTTLE_MILK_FULL:
            item = ITEM_BOTTLE_MILK_FULL;
            textId = 0x98; /* z_player.c sGetItemTable */
            break;
        case GI_MILK:
            item = ITEM_MILK;
            textId = 0x98;
            break;
        default:
            item = ITEM_NONE; /* not in the C save yet */
            break;
    }
    if (item != ITEM_NONE && Item_Give(play, item) == ITEM_NONE) {
        this->interactRangeActor->parent = &this->actor;
        Audio_PlaySfxGeneral(NA_SE_SY_GET_ITEM, &gSfxDefaultPos, 4, &gSfxDefaultFreqAndVolScale,
                             &gSfxDefaultFreqAndVolScale, &gSfxDefaultReverb);
        if (textId) {
            /* Talon/cow action code waits for the reward textbox to close
             * after observing Actor_HasParent; a silent grant strands it. */
            this->actor.flags |= ACTOR_FLAG_TALK;
            this->stateFlags1 |= PLAYER_STATE1_TALKING | PLAYER_STATE1_29;
            Message_StartTextbox(play, textId, this->interactRangeActor);
        }
    }
    this->getItemId = GI_NONE;
    this->interactRangeActor = NULL;
    this->getItemDirection = 0x8000;
}

/* z_elf_message.c sChild/AdultSariaQuestHints, with the same ordered checks.
 * Nearby Saria uses bounded integer distance instead of a float square root. */
static u16 PlayerProxy_SariaHint(PlayState* play) {
    if (!LINK_IS_ADULT) {
        Player* player = GET_PLAYER(play);
        for (Actor* actor=play->actorCtx.actorLists[ACTORCAT_NPC].head;actor;actor=actor->next) {
            if (actor->id == ACTOR_EN_SA) {
                s32 x=OotCore_BgInt(actor->world.pos.x)-OotCore_BgInt(player->actor.world.pos.x);
                s32 y=OotCore_BgInt(actor->world.pos.y)-OotCore_BgInt(player->actor.world.pos.y);
                s32 z=OotCore_BgInt(actor->world.pos.z)-OotCore_BgInt(player->actor.world.pos.z);
                if (x>=-800 && x<=800 && y>=-800 && y<=800 && z>=-800 && z<=800 &&
                    x*x+y*y+z*z<=800*800) return 0x160;
            }
        }
        if (CUR_UPG_VALUE(UPG_STRENGTH) == 0) return GET_EVENTCHKINF(EVENTCHKINF_37) ? 0x164 : 0x161;
        if (!GET_EVENTCHKINF(EVENTCHKINF_25)) return 0x162;
        if (!GET_EVENTCHKINF(EVENTCHKINF_37)) return 0x163;
        if (!GET_EVENTCHKINF(EVENTCHKINF_43)) return 0x165;
        if (!CHECK_QUEST_ITEM(QUEST_MEDALLION_FOREST) || !CHECK_QUEST_ITEM(QUEST_MEDALLION_FIRE) ||
            !CHECK_QUEST_ITEM(QUEST_MEDALLION_WATER)) return 0x166;
        if (!CHECK_QUEST_ITEM(QUEST_SONG_STORMS)) return 0x167;
        if (!CHECK_QUEST_ITEM(QUEST_MEDALLION_SPIRIT) || !CHECK_QUEST_ITEM(QUEST_MEDALLION_SHADOW)) return 0x168;
        return 0x169;
    }
    if (!CHECK_QUEST_ITEM(QUEST_MEDALLION_FOREST)) return 0x16a;
    if (!CHECK_QUEST_ITEM(QUEST_MEDALLION_FIRE) || !CHECK_QUEST_ITEM(QUEST_MEDALLION_WATER)) return 0x16b;
    if (!CHECK_QUEST_ITEM(QUEST_MEDALLION_SPIRIT) || !CHECK_QUEST_ITEM(QUEST_MEDALLION_SHADOW)) return 0x16c;
    return 0x16d;
}

/* En_Elf func_80A052F4/5208/5188/5114/5040 dialogue callbacks. C owns Navi's
 * sprite; only the original talk state machine runs here, with no actor mesh. */
static void PlayerProxy_SariaSongTalk(PlayState* play) {
    unsigned state=Message_GetState(&play->msgCtx);
    if (!sSariaSongTalk || (state != TEXT_STATE_CHOICE && state != TEXT_STATE_EVENT) ||
        !Message_ShouldAdvance(play)) return;
    if (state == TEXT_STATE_CHOICE) {
        if (sSariaSongTalk == 1) {
            play->msgCtx.unk_E3F2 = 0xff;
            if (play->msgCtx.choiceIndex == 0) {
                Message_ContinueTextbox(play,0xe2);sSariaSongTalk=2;
            } else { Message_ContinueTextbox(play,0xe1);sSariaSongTalk=5; }
        } else if (sSariaSongTalk == 4 || sSariaSongTalk == 5) {
            if (play->msgCtx.choiceIndex == 0) {
                /* Source OOC scenes currently have no Navi quest script.
                 * QuestHint_GetNaviTextId then returns zero: EnElf uses 15F. */
                Message_ContinueTextbox(play,sSariaSongTalk==4 ? PlayerProxy_SariaHint(play) : 0x15f);
                sSariaSongTalk=sSariaSongTalk==4 ? 3 : 0;
            } else { Message_CloseTextbox(play);sSariaSongTalk=0; }
        }
    } else if (state == TEXT_STATE_EVENT) {
        if (sSariaSongTalk == 2) {
            Message_ContinueTextbox(play,PlayerProxy_SariaHint(play));sSariaSongTalk=3;
        } else if (sSariaSongTalk == 3) {
            Message_ContinueTextbox(play,0xe3);sSariaSongTalk=4;
        }
    }
}

/* Source offer acceptance, talk start/end and Player_UpdateCommon offer reset.
 * The C player still owns C-Up Navi, carrying/lock checks and talk poses;
 * source Saria-song follow-up delegates to the callbacks above. */
static void PlayerProxy_UpdateTalk(Player* this, PlayState* play) {
    Input* input = &play->state.input[0];

    if (this->stateFlags2 & PLAYER_STATE2_USING_OCARINA) return;
    if (this->naviTextId < 0 && this->naviActor == NULL && play->msgCtx.msgMode == MSGMODE_NONE) {
        sSariaSongTalk = this->naviTextId == -0xe0 ? 1 : 0;
        Message_StartTextbox(play, -this->naviTextId, NULL);
        this->naviTextId = 0;
        this->stateFlags1 |= PLAYER_STATE1_TALKING;
    }

    if (this->stateFlags1 & PLAYER_STATE1_TALKING) {
        PlayerProxy_SariaSongTalk(play);
        if (Message_GetState(&play->msgCtx) == TEXT_STATE_CLOSING) {
            sSariaSongTalk = 0;
            this->actor.flags &= ~ACTOR_FLAG_TALK;
            this->stateFlags1 &= ~(PLAYER_STATE1_TALKING | PLAYER_STATE1_29);
            this->focusActor = NULL;
        }
    } else if (this->talkActor != NULL &&
               (CHECK_BTN_ALL(input->press.button, BTN_A) ||
                (this->talkActor->flags & ACTOR_FLAG_TALK_OFFER_AUTO_ACCEPTED))) {
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
static void PlayerProxy_ReceiveHit(Player* this, PlayState* play) {
    OotCorePlayerHit hit = {};
    bool ready = false;
    if (!(sCombat.flags & OOT_COMBAT_DISABLED) && this->knockbackType != PLAYER_KNOCKBACK_NONE &&
        (this->knockbackType >= PLAYER_KNOCKBACK_LARGE || !(sCombat.flags & OOT_COMBAT_INTANGIBLE))) {
        int speed = OotCore_BgInt(this->knockbackSpeed);
        if (speed < 0) speed = 0;
        if (speed > 64) speed = 64;
        hit.speed_q16 = speed * 65536;
        hit.yaw = this->knockbackRot;
        unsigned int damage = this->actor.colChkInfo.damage + this->knockbackDamage;
        hit.damage = (sCombat.flags & (OOT_COMBAT_INTANGIBLE | OOT_COMBAT_DODGE)) ? 0 :
            damage > 255 ? 255 : damage;
        if (this->knockbackType >= PLAYER_KNOCKBACK_LARGE) hit.flags |= OOT_HIT_LARGE;
        hit.effect = this->knockbackType == PLAYER_KNOCKBACK_LARGE_ELECTRIFIED ?
            HIT_SPECIAL_EFFECT_ELECTRIC : HIT_SPECIAL_EFFECT_NONE;
        ready = true;
    } else if (this->shieldQuad.base.acFlags & AC_BOUNCED) {
        hit.flags = OOT_HIT_GUARD;
        ready = true;
    } else if (!(sCombat.flags & (OOT_COMBAT_INTANGIBLE | OOT_COMBAT_DISABLED))) {
        if ((this->cylinder.base.acFlags & AC_HIT) && this->cylinder.base.ac) {
            hit.speed_q16 = 4 * 65536;
            hit.yaw = Actor_WorldYawTowardActor(this->cylinder.base.ac, &this->actor);
            hit.damage = this->actor.colChkInfo.damage;
            hit.effect = this->actor.colChkInfo.acHitSpecialEffect;
            if (hit.effect == HIT_SPECIAL_EFFECT_KNOCKBACK) hit.flags |= OOT_HIT_LARGE;
            ready = true;
        }
    }
    if (ready && gOotCoreHost && gOotCoreHost->player_hit && gOotCoreHost->player_hit(&hit) &&
        !(hit.flags & OOT_HIT_GUARD)) sCombat.flags |= OOT_COMBAT_INTANGIBLE;
    /* Results belong to one 20 Hz step, including skipped host frames. */
    this->knockbackType = PLAYER_KNOCKBACK_NONE;
    this->knockbackDamage = 0;
    Collider_ResetCylinderAC(play, &this->cylinder.base);
    Collider_ResetQuadAC(play, &this->shieldQuad.base);
}

static void PlayerProxy_UpdateShield(Player* this, PlayState* play) {
    if (!(sCombat.flags & OOT_COMBAT_SHIELD) || (sCombat.flags & OOT_COMBAT_DISABLED)) return;
    /* Semantic shield plane, matching the C forward guard volume. No pose
     * evaluation in the proxy; real Player will replace this approximation. */
    f32 sine = Math_SinS(this->actor.shape.rot.y), cosine = Math_CosS(this->actor.shape.rot.y);
    Vec3f a = this->actor.world.pos, b, c, d;
    a.x += sine * 18; a.z += cosine * 18;
    /* Nutsball/Okuta obtain reflection yaw from shieldMf, then add 0x8000.
     * Its local +Z therefore points into this planar shield: the source
     * conversion sends a bounced projectile outward along Link's facing.
     * This semantic transform shares the C guard plane; no pose evaluation. */
    MtxF* shield = &this->shieldMf;
    for (s32 i = 0; i < 4; ++i)
        for (s32 j = 0; j < 4; ++j) shield->mf[i][j] = 0;
    shield->mf[0][0] = shield->mf[2][2] = -cosine;
    shield->mf[0][2] = sine;
    shield->mf[2][0] = -sine;
    shield->mf[1][1] = shield->mf[3][3] = 1;
    shield->mf[3][0] = a.x;
    shield->mf[3][1] = a.y;
    shield->mf[3][2] = a.z;
    b = c = d = a;
    a.x += cosine * 20; a.z -= sine * 20; a.y += LINK_IS_ADULT ? 70 : 55;
    b.x -= cosine * 20; b.z += sine * 20; b.y = a.y;
    c.x += cosine * 20; c.z -= sine * 20;
    d.x -= cosine * 20; d.z += sine * 20;
    Collider_SetQuadVertices(&this->shieldQuad, &a, &b, &c, &d);
    this->shieldQuad.base.colMaterial = this->currentShield == PLAYER_SHIELD_DEKU ?
        COL_MATERIAL_WOOD : COL_MATERIAL_METAL;
    CollisionCheck_SetAC(play, &play->colChkCtx, &this->shieldQuad.base);
    CollisionCheck_SetAT(play, &play->colChkCtx, &this->shieldQuad.base);
}

static void PlayerProxy_UpdateBody(Player* this, PlayState* play) {
    PlayerProxy_ReceiveHit(this, play);
    gOotCorePlayerPushX += (s32)this->actor.colChkInfo.displacement.x;
    gOotCorePlayerPushZ += (s32)this->actor.colChkInfo.displacement.z;
    this->actor.colChkInfo.mass = (this->stateFlags1 & PLAYER_STATE1_29) ? MASS_IMMOVABLE : 50;
    /* Source body cylinder reaches the posed head plus ten. Keep the existing
     * child bound and use Adult Link's 68-unit head anchor plus ten. */
    this->cylinder.dim.height = LINK_IS_ADULT ? 78 : 60;
    Collider_UpdateCylinder(&this->actor, &this->cylinder);
    CollisionCheck_SetOC(play, &play->colChkCtx, &this->cylinder.base);
    if (!(sCombat.flags & (OOT_COMBAT_INTANGIBLE | OOT_COMBAT_DISABLED)))
        CollisionCheck_SetAC(play, &play->colChkCtx, &this->cylinder.base);
    PlayerProxy_UpdateShield(this, play);
}

static void PlayerProxy_Update(Actor* thisx, PlayState* play) {
    PlayerProxy_Sync(thisx);
    if (play->sceneId == SCENE_HYRULE_FIELD) {
        /* Source En_Encount1 excludes roads, air, dynamic floors and water.
         * Read the shared source collision world without moving host Link. */
        Player* player = (Player*)thisx;
        Vec3f probe = thisx->world.pos;
        s32 bgId = BGCHECK_SCENE;
        WaterBox* water;
        f32 waterY = thisx->world.pos.y;
        probe.y += 50;
        thisx->floorHeight = BgCheck_EntityRaycastDown4(&play->colCtx, &thisx->floorPoly,
                                                       &bgId, thisx, &probe);
        thisx->floorBgId = bgId;
        thisx->bgCheckFlags &= ~(BGCHECKFLAG_GROUND | BGCHECKFLAG_WATER);
        if (thisx->floorPoly && thisx->world.pos.y >= thisx->floorHeight - 3 &&
            thisx->world.pos.y <= thisx->floorHeight + 3)
            thisx->bgCheckFlags |= BGCHECKFLAG_GROUND;
        player->floorSfxOffset = thisx->floorPoly ?
            SurfaceType_GetSfxOffset(&play->colCtx, thisx->floorPoly, bgId) : SURFACE_SFX_OFFSET_DIRT;
        thisx->depthInWater = BGCHECK_Y_MIN;
        if (BgCheck_GetWaterSurface(play, &play->colCtx, probe.x, probe.z, &waterY, &water)) {
            thisx->depthInWater = waterY - thisx->world.pos.y;
            if (thisx->depthInWater >= 0) thisx->bgCheckFlags |= BGCHECKFLAG_WATER;
        }
    }
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
