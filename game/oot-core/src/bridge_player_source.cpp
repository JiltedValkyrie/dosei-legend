/*
 * Host glue for the real decomp Player (PLAYER_SOURCE=1, Player migration
 * phase 4/5). z_player_call / z_player_lib / ovl_player_actor own Link's
 * gameplay; this file only connects them to the Saturn host:
 *   - globals the C-side API still writes (oot_core_api.cpp set_player,
 *     set_sword, player_push) stay defined, but the source Player ignores
 *     them: Link's position is the core's, read back through player_view.
 *   - engine services z_player needs that the core does not import
 *     (camera, audio, scene flow, UI), each marked like bridge_play.cpp:
 *       REAL - same body as the decomp.
 *       HOST - Saturn backend through OotCoreHost (the C save stays the one
 *              persistent owner of health, rupees, items, ammo and magic).
 *       STUB - no Saturn equivalent; the comment says what is missing.
 * Replaces bridge_player.cpp (the C Link proxy, PLAYER_SOURCE=0 rollback).
 */
#include "oot_prelude.h"
#include "ultra64.h"
#include "actor.h"
#include "player.h"
#include "play_state.h"
#include "save.h"
#include "camera.h"
#include "audio.h"
#include "sfx.h"
#include "dma.h"
#include "romfile.h"
#include "scene.h"
#include "regs.h"
#include "item.h"
#include "environment.h"
#include "kaleido_manager.h"
#include "lifemeter.h"
#include "map.h"
#include "one_point_cutscene.h"
#include "interface.h"
#include "z_lib.h"
#include "oot_core_host.h"
#include "oot_core_api.h"
#include "overlays/actors/ovl_En_Elf/z_en_elf.h"

extern const OotCoreHost* gOotCoreHost;
extern s16 gOotCoreCamYaw;   /* bridge_play.cpp, set_camera */
extern u32 gOotCoreFlags;    /* oot_core_api.cpp, OOT_CORE_FLAG_* */

/* oot_core_api.cpp still assigns these (host API kept stable); unused here. */
Vec3f gOotCorePlayerPos;
s16 gOotCorePlayerYaw;
s32 gOotCoreSwordActive;
Vec3f gOotCoreSwordBase;
Vec3f gOotCoreSwordTip;
s32 gOotCorePlayerPushX;
s32 gOotCorePlayerPushZ;

/* Room the source Player asked for through a door (-1 none); player_view
 * reports it, the host loads the room bank and answers with set_room. */
s32 gOotCoreRoomRequest = -1;

/* ---- z_camera.c: the Saturn camera (player_camera.c) owns the view ---- */
s16 Camera_GetInputDirYaw(Camera* camera) { /* HOST: C camera facing */
    return gOotCoreCamYaw;
}
s32 Camera_CheckValidMode(Camera* camera, s16 mode) { /* HOST: every mode the Saturn camera can show */
    return mode | 0x80000000;
}
s32 Camera_RequestSetting(Camera* camera, s16 setting) { /* STUB: Saturn camera keeps its own setting */
    return setting | 0x80000000;
}
s32 Camera_SetViewParam(Camera* camera, s32 viewFlag, void* param) { /* STUB */
    return true;
}
s32 Camera_ChangeDoorCam(Camera* camera, Actor* doorActor, s16 bgCamIndex, f32 arg3, s16 timer1, s16 timer2,
                         s16 timer3) { /* STUB: door cameras are the Saturn camera's */
    return 0;
}
void Camera_SetCameraData(Camera* camera, s16 setDataFlags, void* data0, void* data1, s16 data2, s16 data3,
                          s32 data4) { /* STUB */
}
s16 Camera_SetFinishedFlag(Camera* camera) { /* STUB */
    return 0;
}
s16 OnePointCutscene_EndCutscene(PlayState* play, s16 subCamId) { /* STUB: no one-point cameras */
    return CAM_ID_MAIN;
}
/* Play_CamIsNotFixed: prerendered interiors are fixed (host flag). */
int Play_CamIsNotFixed(PlayState* this) { /* HOST */
    return !(gOotCoreFlags & OOT_CORE_FLAG_FIXED_CAMERA);
}

/* ---- audio: sfx through the host bank; sequence control stays host ---- */
static void host_sfx(u16 sfxId, Vec3f* pos) {
    if (gOotCoreHost != NULL && gOotCoreHost->play_sfx != NULL) {
        gOotCoreHost->play_sfx(sfxId, pos ? (s32)pos->x : 0, pos ? (s32)pos->y : 0, pos ? (s32)pos->z : 0);
    }
}
void func_800F4010(Vec3f* pos, u16 sfxId, f32 arg2) { /* HOST: footstep/surface sfx */
    host_sfx(sfxId, pos);
}
void func_800F4138(Vec3f* pos, u16 sfxId, f32 arg2) { /* HOST: pitched sfx */
    host_sfx(sfxId, pos);
}
void func_800F4190(Vec3f* pos, u16 sfxId) { /* HOST */
    host_sfx(sfxId, pos);
}
void func_800F6964(u16 arg0) { /* STUB: sequence fade */
}
void Audio_StopSfxById(u32 sfxId) { /* STUB: host one-shots end on their own */
}
void Audio_SetBaseFilter(u8 filter) { /* STUB */
}
void Audio_SetCodeReverb(s8 reverb) { /* STUB */
}
void Audio_SetSequenceMode(u8 seqMode) { /* STUB: host music owns modes */
}
void Audio_SetBgmEnemyVolume(f32 dist) { /* STUB */
}
void Audio_StopBgmAndFanfare(u16 fadeOutDuration) { /* STUB */
}
void Audio_SetBgmVolumeOnDuringFanfare(void) { /* STUB */
}
void Audio_SetBgmVolumeOffDuringFanfare(void) { /* STUB */
}

/* ---- z_play.c / z_room.c / z_scene.c: the host loads scenes and rooms ---- */
static void Play_SetRespawnData(PlayState* this, s32 respawnMode, s16 entranceIndex, s32 roomIndex,
                                s32 playerParams, Vec3f* pos, s16 yaw) { /* REAL */
    RespawnData* respawnData = &gSaveContext.respawn[respawnMode];

    respawnData->entranceIndex = entranceIndex;
    respawnData->roomIndex = roomIndex;
    respawnData->pos = *pos;
    respawnData->yaw = yaw;
    respawnData->playerParams = playerParams;
    respawnData->tempSwchFlags = this->actorCtx.flags.tempSwch;
    respawnData->tempCollectFlags = this->actorCtx.flags.tempCollect;
}

void Play_SetupRespawnPoint(PlayState* this, s32 respawnMode, s32 playerParams) { /* REAL */
    Player* player = GET_PLAYER(this);

    if ((this->sceneId != SCENE_FAIRYS_FOUNTAIN) && (this->sceneId != SCENE_GROTTOS)) {
        Play_SetRespawnData(this, respawnMode, gSaveContext.save.entranceIndex, this->roomCtx.curRoom.num,
                            playerParams, &player->actor.world.pos, player->actor.shape.rot.y);
    }
}

/* The host's transition_request reads transitionTrigger/nextEntranceIndex. */
void Play_TriggerVoidOut(PlayState* this) { /* REAL */
    gSaveContext.respawn[RESPAWN_MODE_DOWN].tempSwchFlags = this->actorCtx.flags.tempSwch;
    gSaveContext.respawn[RESPAWN_MODE_DOWN].tempCollectFlags = this->actorCtx.flags.tempCollect;
    gSaveContext.respawnFlag = 1;
    this->transitionTrigger = TRANS_TRIGGER_START;
    this->nextEntranceIndex = gSaveContext.respawn[RESPAWN_MODE_DOWN].entranceIndex;
    this->transitionType = TRANS_TYPE_FADE_BLACK;
}

static void Play_LoadToLastEntrance(PlayState* this) { /* REAL (Ganon collapse / Field fence cases omitted) */
    gSaveContext.respawnFlag = -1;
    this->transitionTrigger = TRANS_TRIGGER_START;
    this->nextEntranceIndex = gSaveContext.save.entranceIndex;
    this->transitionType = TRANS_TYPE_FADE_BLACK;
}

void Play_TriggerRespawn(PlayState* this) { /* REAL */
    Play_SetupRespawnPoint(this, RESPAWN_MODE_DOWN, PLAYER_PARAMS(PLAYER_START_MODE_IDLE, PLAYER_START_BG_CAM_DEFAULT));
    Play_LoadToLastEntrance(this);
}

void Scene_SetTransitionForNextEntrance(PlayState* play) { /* STUB: host transition is a black fade */
    play->transitionType = TRANS_TYPE_FADE_BLACK;
}

/* Doors: the host swaps the room bank, then set_room spawns the new room's
 * actors (oot_core_set_room); Room_FinishRoomChange is part of that. */
s32 Room_RequestNewRoom(PlayState* play, RoomContext* roomCtx, s32 roomNum) { /* HOST */
    gOotCoreRoomRequest = roomNum;
    return true;
}
void Room_FinishRoomChange(PlayState* play, RoomContext* roomCtx) { /* HOST: set_room did it */
}
void Map_SavePlayerInitialInfo(PlayState* play) { /* STUB: Saturn minimap needs no entry point */
}
void Environment_WarpSongLeave(PlayState* play) { /* STUB: host warp songs (ocarina) */
}
void Environment_ChangeLightSetting(PlayState* play, u32 lightSetting) { /* STUB: host lighting */
}

/* gEntranceTable: player_frame_decode.cpp (one entry, see there). */
/* Get-item objects: sizes only, DMA below is a no-op (host draws held items). */
RomFile gObjectTable[OBJECT_ID_MAX];

/* ---- Kaleido overlay manager / DMA: Player is resident on Saturn ---- */
void* KaleidoManager_GetRamAddr(void* vram) { /* HOST: no overlays */
    return vram;
}
void KaleidoScopeCall_LoadPlayer(void) { /* HOST: no overlays */
}
s32 DmaMgr_RequestAsync(DmaRequest* req, void* ram, uintptr_t vrom, size_t size, u32 unk5, OSMesgQueue* queue,
                        OSMesg msg) { /* STUB: get-item/title objects are not loaded (osRecvMesg reports done) */
    return 0;
}
void osCreateMesgQueue(OSMesgQueue* mq, OSMesg* msg, s32 count) { /* REAL */
    mq->mtqueue = NULL;
    mq->fullqueue = NULL;
    mq->validCount = 0;
    mq->first = 0;
    mq->msgCount = count;
    mq->msg = msg;
}

/* ---- z_parameter.c / z_lifemeter.c: the C save owns the inventory ---- */
u32 Health_IsCritical(void) { /* REAL */
    s32 criticalHealth;

    if (gSaveContext.save.info.playerData.healthCapacity <= 0x50) {
        criticalHealth = 0x10;
    } else if (gSaveContext.save.info.playerData.healthCapacity <= 0xA0) {
        criticalHealth = 0x18;
    } else if (gSaveContext.save.info.playerData.healthCapacity <= 0xF0) {
        criticalHealth = 0x20;
    } else {
        criticalHealth = 0x2C;
    }
    return (criticalHealth >= gSaveContext.save.info.playerData.health) &&
           (gSaveContext.save.info.playerData.health > 0);
}

void Inventory_ChangeAmmo(s16 item, s16 ammoChange) { /* HOST: C save owns ammo */
    if (gOotCoreHost != NULL && gOotCoreHost->ammo_change != NULL) {
        gOotCoreHost->ammo_change((unsigned char)item, ammoChange);
    }
}

s32 Magic_RequestChange(PlayState* play, s16 amount, s16 type) { /* HOST: health_hud.c owns magic state */
    if (gOotCoreHost == NULL || gOotCoreHost->magic_request == NULL) {
        return false;
    }
    return gOotCoreHost->magic_request(amount, type);
}

void Magic_Fill(PlayState* play) { /* HOST */
    if (gOotCoreHost != NULL && gOotCoreHost->magic_request != NULL) {
        gOotCoreHost->magic_request(0, OOT_CORE_MAGIC_FILL);
    }
}

void func_800849EC(PlayState* play) { /* HOST: Biggoron's sword from the trade quest */
    if (gOotCoreHost != NULL && gOotCoreHost->give_item != NULL) {
        gOotCoreHost->give_item(ITEM_SWORD_BIGGORON);
    }
}

void Inventory_UpdateBottleItem(PlayState* play, u8 item, u8 button) { /* HOST */
    if (gOotCoreHost != NULL && gOotCoreHost->bottle_update != NULL) {
        gOotCoreHost->bottle_update(item, button);
    }
    gSaveContext.save.info.equips.buttonItems[button] = item; /* mirror until the next set_save */
}

s32 Inventory_ConsumeFairy(PlayState* play) { /* HOST */
    if (gOotCoreHost == NULL || gOotCoreHost->bottle_update == NULL) {
        return false;
    }
    return gOotCoreHost->bottle_update(ITEM_BOTTLE_FAIRY, 0xFF) != 0;
}

/* z_parameter.c sExtraItemBases (REAL table). */
static s16 sExtraItemBases[] = {
    ITEM_DEKU_STICK, ITEM_DEKU_STICK, ITEM_DEKU_NUT,   ITEM_DEKU_NUT,   ITEM_BOMB,       ITEM_BOMB,
    ITEM_BOMB,       ITEM_BOMB,       ITEM_BOW,        ITEM_BOW,        ITEM_BOW,        ITEM_DEKU_SEEDS,
    ITEM_BOMBCHU,    ITEM_BOMBCHU,    ITEM_DEKU_STICK, ITEM_DEKU_STICK, ITEM_DEKU_NUT,   ITEM_DEKU_NUT,
};

/* REAL: reads the mirrored inventory (set_save). */
u8 Item_CheckObtainability(u8 item) {
    Inventory* inv = &gSaveContext.save.info.inventory;
    s16 i, slot, temp;

    slot = SLOT(item);
    if (item >= ITEM_DEKU_STICKS_5) {
        slot = SLOT(sExtraItemBases[item - ITEM_DEKU_STICKS_5]);
    }
    if ((item >= ITEM_MEDALLION_FOREST) && (item <= ITEM_MEDALLION_LIGHT)) {
        return ITEM_NONE;
    } else if ((item >= ITEM_KOKIRI_EMERALD) && (item <= ITEM_SKULL_TOKEN)) {
        return ITEM_NONE;
    } else if ((item >= ITEM_SWORD_KOKIRI) && (item <= ITEM_SWORD_BIGGORON)) {
        if (item == ITEM_SWORD_BIGGORON) {
            return ITEM_NONE;
        } else if (CHECK_OWNED_EQUIP(EQUIP_TYPE_SWORD, item - ITEM_SWORD_KOKIRI + EQUIP_INV_SWORD_KOKIRI)) {
            return item;
        } else {
            return ITEM_NONE;
        }
    } else if ((item >= ITEM_SHIELD_DEKU) && (item <= ITEM_SHIELD_MIRROR)) {
        return CHECK_OWNED_EQUIP(EQUIP_TYPE_SHIELD, item - ITEM_SHIELD_DEKU + EQUIP_INV_SHIELD_DEKU) ? item : ITEM_NONE;
    } else if ((item >= ITEM_TUNIC_KOKIRI) && (item <= ITEM_TUNIC_ZORA)) {
        return CHECK_OWNED_EQUIP(EQUIP_TYPE_TUNIC, item - ITEM_TUNIC_KOKIRI + EQUIP_INV_TUNIC_KOKIRI) ? item : ITEM_NONE;
    } else if ((item >= ITEM_BOOTS_KOKIRI) && (item <= ITEM_BOOTS_HOVER)) {
        return CHECK_OWNED_EQUIP(EQUIP_TYPE_BOOTS, item - ITEM_BOOTS_KOKIRI + EQUIP_INV_BOOTS_KOKIRI) ? item : ITEM_NONE;
    } else if ((item == ITEM_DUNGEON_BOSS_KEY) || (item == ITEM_DUNGEON_COMPASS) || (item == ITEM_DUNGEON_MAP) ||
               (item == ITEM_SMALL_KEY) || ((item >= ITEM_SLINGSHOT) && (item <= ITEM_BOMBCHU)) ||
               (item == ITEM_BOMBCHUS_5) || (item == ITEM_BOMBCHUS_20)) {
        return ITEM_NONE;
    } else if ((item == ITEM_QUIVER_30) || (item == ITEM_BOW)) {
        return (CUR_UPG_VALUE(UPG_QUIVER) == 0) ? ITEM_NONE : 0;
    } else if ((item == ITEM_QUIVER_40) || (item == ITEM_QUIVER_50) || (item == ITEM_BULLET_BAG_40) ||
               (item == ITEM_BULLET_BAG_50)) {
        return ITEM_NONE;
    } else if ((item == ITEM_BOMB_BAG_20) || (item == ITEM_BOMB)) {
        return (CUR_UPG_VALUE(UPG_BOMB_BAG) == 0) ? ITEM_NONE : 0;
    } else if (((item >= ITEM_DEKU_STICK_UPGRADE_20) && (item <= ITEM_DEKU_NUT_UPGRADE_40)) ||
               ((item >= ITEM_BOMB_BAG_30) && (item <= ITEM_GIANTS_WALLET)) || (item == ITEM_LONGSHOT)) {
        return ITEM_NONE;
    } else if ((item == ITEM_DEKU_SEEDS) || (item == ITEM_DEKU_SEEDS_30)) {
        return !GET_ITEMGETINF(ITEMGETINF_13) ? ITEM_NONE : ITEM_DEKU_SEEDS;
    } else if ((item == ITEM_MAGIC_BEAN) || (item == ITEM_HEART_PIECE_2) || (item == ITEM_HEART_PIECE) ||
               (item == ITEM_HEART_CONTAINER)) {
        return ITEM_NONE;
    } else if (item == ITEM_RECOVERY_HEART) {
        return ITEM_RECOVERY_HEART;
    } else if ((item == ITEM_MAGIC_JAR_SMALL) || (item == ITEM_MAGIC_JAR_BIG)) {
        return !GET_INFTABLE(INFTABLE_198) ? ITEM_NONE : item;
    } else if (((item >= ITEM_RUPEE_GREEN) && (item <= ITEM_INVALID_8)) || (item == ITEM_BOTTLE_EMPTY)) {
        return ITEM_NONE;
    } else if (((item >= ITEM_BOTTLE_POTION_RED) && (item <= ITEM_BOTTLE_POE)) || (item == ITEM_MILK)) {
        temp = SLOT(item);
        if ((item != ITEM_BOTTLE_MILK_FULL) && (item != ITEM_BOTTLE_RUTOS_LETTER)) {
            if (item == ITEM_MILK) {
                item = ITEM_BOTTLE_MILK_FULL;
                temp = SLOT(item);
            }
            for (i = 0; i < 4; i++) {
                if (inv->items[temp + i] == ITEM_BOTTLE_EMPTY) {
                    return ITEM_NONE;
                }
            }
        } else {
            for (i = 0; i < 4; i++) {
                if (inv->items[temp + i] == ITEM_NONE) {
                    return ITEM_NONE;
                }
            }
        }
    } else if ((item >= ITEM_WEIRD_EGG) && (item <= ITEM_CLAIM_CHECK)) {
        return ITEM_NONE;
    }
    return inv->items[slot];
}

void Interface_SetSubTimerToFinalSecond(PlayState* play) { /* REAL */
    if (gSaveContext.subTimerState != SUBTIMER_STATE_OFF) {
        if (GET_EVENTINF(EVENTINF_MARATHON_ACTIVE)) {
            gSaveContext.subTimerSeconds = MARATHON_TIME_LIMIT - 1;
        } else {
            gSaveContext.subTimerSeconds = 1;
        }
    }
}

void Interface_SetNaviCall(PlayState* play, u16 naviCallState) { /* STUB: navi.c owns Navi's call */
}

/* ---- frame bank failure: a missing clip is a hard error, never a T-pose ---- */
extern "C" void PlayerFrameBank_Fail(int code, unsigned int id, unsigned int frame) {
    if (gOotCoreHost != NULL && gOotCoreHost->fatal != NULL) {
        gOotCoreHost->fatal(0x50464200u | (code & 0xFF), id, frame); /* 'PFB' */
    }
    for (;;) {
    }
}

/* ---- z_play.c func_800BFCB8: floor-aligned matrix (feet shadow) ---- */
#include "bgcheck.h"
f32 func_800BFCB8(PlayState* this, MtxF* mf, Vec3f* pos) { /* REAL (MtxF fields as mf[row][col]) */
    CollisionPoly poly;
    f32 temp1, temp2, temp3;
    f32 floorY = BgCheck_AnyRaycastDown1(&this->colCtx, &poly, pos);
    s32 i, j;

    for (i = 0; i < 4; i++) {
        for (j = 0; j < 4; j++) {
            mf->mf[i][j] = 0.0f;
        }
    }
    mf->mf[3][0] = pos->x;   /* xw */
    mf->mf[3][2] = pos->z;   /* zw */
    mf->mf[3][3] = 1.0f;     /* ww */
    if (floorY > BGCHECK_Y_MIN) {
        f32 nx = COLPOLY_GET_NORMAL(poly.normal.x);
        f32 ny = COLPOLY_GET_NORMAL(poly.normal.y);
        f32 nz = COLPOLY_GET_NORMAL(poly.normal.z);

        temp1 = sqrtf(1.0f - SQ(nx));
        if (temp1 != 0.0f) {
            temp2 = ny * temp1;
            temp3 = -nz * temp1;
        } else {
            temp3 = 0.0f;
            temp2 = 0.0f;
        }
        mf->mf[0][0] = temp1;       /* xx */
        mf->mf[0][1] = -nx * temp2; /* yx */
        mf->mf[0][2] = nx * temp3;  /* zx */
        mf->mf[1][0] = nx;          /* xy */
        mf->mf[1][1] = ny;          /* yy */
        mf->mf[1][2] = nz;          /* zy */
        mf->mf[2][1] = temp3;       /* yz */
        mf->mf[2][2] = temp2;       /* zz */
        mf->mf[3][1] = floorY;      /* yw */
    } else {
        mf->mf[1][1] = 1.0f;        /* yy */
        mf->mf[3][1] = pos->y;      /* yw */
    }
    return floorY;
}

/* ---- host API (oot_core_api.cpp entry table, v28) ---- */
extern PlayState* gOotCorePlay;
extern "C" int PlayerFrameBank_Register(const unsigned char* bank, unsigned int bytes);

int OotCore_PlayerBank(const void* bank, unsigned int bytes) {
    return PlayerFrameBank_Register((const unsigned char*)bank, bytes) > 0;
}

static void vec_out(const Vec3f* v, int* out) {
    out[0] = (int)v->x;
    out[1] = (int)v->y;
    out[2] = (int)v->z;
}

int OotCore_PlayerView(OotCorePlayerView* out) {
    PlayState* play = gOotCorePlay;
    Player* this = play ? GET_PLAYER(play) : NULL;
    s32 i;

    if (this == NULL || out == NULL) {
        return 0;
    }
    out->x = (int)this->actor.world.pos.x;
    out->y = (int)this->actor.world.pos.y;
    out->z = (int)this->actor.world.pos.z;
    out->focus_x = (int)this->actor.focus.pos.x;
    out->focus_y = (int)this->actor.focus.pos.y;
    out->focus_z = (int)this->actor.focus.pos.z;
    out->yaw = this->actor.shape.rot.y;
    out->room_request = (short)gOotCoreRoomRequest;
    gOotCoreRoomRequest = -1;
    out->state1 = this->stateFlags1;
    out->state2 = this->stateFlags2;
    out->state3 = this->stateFlags3;
    if (this->skelAnime.jointTable != NULL) {
        const s16* joints = (const s16*)this->skelAnime.jointTable;
        for (i = 0; i < OOT_CORE_PLAYER_JOINTS; i++) {
            out->joints[i] = joints[i];
        }
    }
    out->left_hand = this->leftHandType;
    out->right_hand = this->rightHandType;
    out->sheath = this->sheathType;
    out->waist = this->modelGroup;
    out->age = (unsigned char)gSaveContext.save.linkAge;
    out->boots = (unsigned char)this->currentBoots;
    out->tunic = (unsigned char)this->currentTunic;
    out->shield = (unsigned char)this->currentShield;
    out->item_action = this->heldItemAction;
    out->held_item = (signed char)this->heldItemId;
    out->weapon_state = (unsigned char)this->meleeWeaponState;
    out->ground = (this->actor.bgCheckFlags & BGCHECKFLAG_GROUND) != 0;
    out->water = (this->actor.bgCheckFlags & BGCHECKFLAG_WATER) != 0;
    out->invincible = this->invincibilityTimer != 0;
    out->hidden = this->actor.draw == NULL;
    out->pad = 0;
    vec_out(&this->meleeWeaponInfo[0].posA, out->blade_tip);
    vec_out(&this->meleeWeaponInfo[0].posB, out->blade_base);
    {
        out->floor_y = (int)this->actor.floorHeight;
        /* Navi = the source En_Elf; same visibility test as EnElf_Draw. */
        EnElf* navi = (EnElf*)this->naviActor;
        out->navi_shown = 0;
        out->navi_colour = 0;
        if (navi != NULL && navi->actor.update != NULL) {
            out->navi[0] = (short)(int)navi->actor.world.pos.x;
            out->navi[1] = (short)(int)navi->actor.world.pos.y;
            out->navi[2] = (short)(int)navi->actor.world.pos.z;
            out->navi_shown = navi->unk_2A8 != 8 && !(navi->fairyFlags & 8) &&
                              !(this->stateFlags1 & PLAYER_STATE1_20);
            if (this->focusActor != NULL) {
                u8 cat = this->focusActor->category;
                out->navi_colour = (cat == ACTORCAT_ENEMY || cat == ACTORCAT_BOSS) ? 2 : 1;
            }
        }
    }
    {
        extern u32 gOotCorePlayerDrawUs;
        out->draw_us = gOotCorePlayerDrawUs;
    }
    return 1;
}

/* One bank frame for the host's own Link poses (C cutscenes, chest/get-item
 * holds): frame clamped to the clip, 0 if the clip is not in the bank. */
extern "C" unsigned int PlayerFrameBank_Count(unsigned int id);
extern "C" int PlayerFrameBank_Load(unsigned int id, unsigned int frame, short* out);
int OotCore_PlayerPose(unsigned int id, unsigned int frame, short* out) {
    unsigned int count = PlayerFrameBank_Count(id);
    if (count == 0 || out == NULL) {
        return 0;
    }
    return PlayerFrameBank_Load(id, frame < count ? frame : count - 1, out) == 0;
}

/* Saturn Y jump (the human's control; not an OoT action): source
 * func_80838940 with the jump clip, from standing/running ground states only.
 * Velocity 8.0 keeps the C jump's 51-unit apex (Actor_UpdatePos x1.5). */
extern LinkAnimationHeader gPlayerAnim_link_normal_jump;
void func_80838940(Player* this, LinkAnimationHeader* anim, f32 arg2, PlayState* play, u16 sfxId);
int OotCore_PlayerJump(void) {
    PlayState* play = gOotCorePlay;
    Player* this = play ? GET_PLAYER(play) : NULL;
    /* Talking, dead, carrying, ledge hang/climb (13/14), airborne (18/19),
     * first person (20), ladder (21), horse (23), water (27), cutscene (29),
     * shield, spin charge: no jump. */
    const u32 busy1 = PLAYER_STATE1_TALKING | PLAYER_STATE1_DEAD | PLAYER_STATE1_CARRYING_ACTOR |
                      PLAYER_STATE1_13 | PLAYER_STATE1_14 | PLAYER_STATE1_18 | PLAYER_STATE1_19 |
                      PLAYER_STATE1_20 | PLAYER_STATE1_21 | PLAYER_STATE1_23 | PLAYER_STATE1_27 |
                      PLAYER_STATE1_29 | PLAYER_STATE1_SHIELDING | PLAYER_STATE1_CHARGING_SPIN_ATTACK;
    if (this == NULL || !(this->actor.bgCheckFlags & BGCHECKFLAG_GROUND) || (this->stateFlags1 & busy1) ||
        Player_InCsMode(play) || this->meleeWeaponState != 0) {
        return 0;
    }
    func_80838940(this, &gPlayerAnim_link_normal_jump, 8.0f, play, NA_SE_VO_LI_AUTO_JUMP);
    return 1;
}

void OotCore_PlayerWarp(int x, int y, int z, short yaw) {
    PlayState* play = gOotCorePlay;
    Player* this = play ? GET_PLAYER(play) : NULL;

    if (this == NULL) {
        return;
    }
    this->actor.world.pos.x = x;
    this->actor.world.pos.y = y;
    this->actor.world.pos.z = z;
    this->actor.prevPos = this->actor.world.pos;
    this->actor.shape.rot.y = this->actor.world.rot.y = this->yaw = yaw;
}

void OotCore_PlayerDamage(int damage) {
    PlayState* play = gOotCorePlay;

    if (play != NULL && GET_PLAYER(play) != NULL && play->damagePlayer != NULL) {
        play->damagePlayer(play, -damage);
    }
}
