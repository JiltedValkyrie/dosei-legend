/*
 * Read-only views of decomp state for the C renderer (route steps 3-4).
 * Nothing here changes game state: the real z_message / actor code owns it.
 *
 * Message: the page z_message has decoded (msgBufDecoded up to textDrawPos,
 * advanced by the real Message_DrawText each frame) is laid out in VDP2
 * character cells with the same control-code walk as Message_DrawText.
 * APPROXIMATE: proportional widths (sFontWidths) become one cell per
 * character, SHIFT is pixels / 8 cells, item icons and the background
 * texture are not drawn.
 */
#include "oot_prelude.h"
#include "ultra64.h"
#include "actor.h"
#include "message.h"
#include "message_data_fmt.h"
#include "play_state.h"
#include "player.h"
#include "save.h"
#include "effect.h"
#include "overlays/actors/ovl_En_Ko/z_en_ko.h"
#include "overlays/actors/ovl_En_Md/z_en_md.h"
#include "overlays/actors/ovl_En_Kanban/z_en_kanban.h"
#include "oot_sign_visual.h"
#include "oot_core_api.h"
#include "overlays/actors/ovl_En_In/z_en_in.h"
#include "overlays/actors/ovl_En_Ma1/z_en_ma1.h"
#include "overlays/actors/ovl_En_Ma2/z_en_ma2.h"
#include "overlays/actors/ovl_En_Ta/z_en_ta.h"
#include "overlays/actors/ovl_En_Niw/z_en_niw.h"
#include "overlays/actors/ovl_En_Cow/z_en_cow.h"
#include "overlays/actors/ovl_En_Skb/z_en_skb.h"
#include "overlays/actors/ovl_En_Peehat/z_en_peehat.h"
#include "overlays/actors/ovl_En_Po_Field/z_en_po_field.h"
#include "overlays/actors/ovl_En_Sb/z_en_sb.h"
#include "overlays/actors/ovl_En_Weiyer/z_en_weiyer.h"
#include "overlays/actors/ovl_En_Tite/z_en_tite.h"
#include "overlays/actors/ovl_En_Firefly/z_en_firefly.h"
#include "overlays/actors/ovl_En_Ny/z_en_ny.h"
#include "assets/objects/object_ny/object_ny.h"
#include "z_actor_dlftbls.h"

extern u32 gOotCoreFlags; /* oot_core_api.cpp, OOT_CORE_FLAG_* */

/* SkelAnime of a generic NPC (oot_core_import GENERIC_NPC_SOURCES) for the
 * sprite path. New generic NPC actor: add its struct here. */
static const SkelAnime* GenericNpc_Skel(Actor* a) {
    switch (a->id) {
        case ACTOR_EN_IN: return &((EnIn*)a)->skelAnime;
        case ACTOR_EN_MA1: return &((EnMa1*)a)->skelAnime;
        case ACTOR_EN_MA2: return &((EnMa2*)a)->skelAnime;
        case ACTOR_EN_TA: return &((EnTa*)a)->skelAnime;
        case ACTOR_EN_NIW: return &((EnNiw*)a)->skelAnime;
        case ACTOR_EN_COW: return &((EnCow*)a)->skelAnime;
        case ACTOR_EN_SKB: return &((EnSkb*)a)->skelAnime;
        case ACTOR_EN_PEEHAT: return &((EnPeehat*)a)->skelAnime;
        case ACTOR_EN_PO_FIELD: return &((EnPoField*)a)->skelAnime;
        case ACTOR_EN_SB: return &((EnSb*)a)->skelAnime;
        case ACTOR_EN_WEIYER: return &((EnWeiyer*)a)->skelAnime;
        case ACTOR_EN_TITE: return &((EnTite*)a)->skelAnime;
        case ACTOR_EN_FIREFLY: return &((EnFirefly*)a)->skelAnime;
        default: return NULL;
    }
}

extern PlayState* gOotCorePlay; /* oot_core_api.cpp */
extern EffectSsInfo sEffectSsInfo;

int OotCore_EffectView(OotCoreEffectView* out, unsigned int capacity, unsigned int* omitted) {
    unsigned int count = 0, dropped = 0;
    if (!out) capacity = 0;
    if (capacity > OOT_CORE_EFFECT_VIEWS_MAX) capacity = OOT_CORE_EFFECT_VIEWS_MAX;
    /* Prioritize damaging actor-owned flames over decorative particles. */
    if (gOotCorePlay) {
        for (unsigned cat = 0; cat < ACTORCAT_MAX; ++cat)
        for (Actor* actor = gOotCorePlay->actorCtx.actorLists[cat].head; actor; actor = actor->next) {
            if (actor->id != ACTOR_EN_PO_FIELD || !actor->update) continue;
            const EnPoField* poe = (const EnPoField*)actor;
            if (!poe->flameTimer || poe->flameScale <= 0) continue;
            if (count == capacity) { ++dropped; continue; }
            OotCoreEffectView* row = &out[count++];
            row->x = (int)poe->flamePosition.x; row->y = (int)poe->flamePosition.y;
            row->z = (int)poe->flamePosition.z;
            for (unsigned j = 0; j < 13; ++j) row->regs[j] = 0;
            row->life = poe->flameTimer; row->type = OOT_CORE_EFFECT_POE_FLAME;
            row->priority = 0; row->slot = 0xffff;
        }
    }
    if (gOotCorePlay && sEffectSsInfo.table) {
        for (unsigned int i = 0; i < sEffectSsInfo.tableSize; ++i) {
            const EffectSs* effect = &sEffectSsInfo.table[i];
            /* DeadSound is update-only and must still execute in source;
             * viewing never plays SFX or advances/despawns an effect. */
            if (effect->life < 0 || !effect->draw || effect->type >= EFFECT_SS_TYPE_MAX) continue;
            if (count == capacity) { ++dropped; continue; }
            OotCoreEffectView* row = &out[count++];
            row->x = (int)effect->pos.x; row->y = (int)effect->pos.y; row->z = (int)effect->pos.z;
            for (unsigned int j = 0; j < 13; ++j) row->regs[j] = effect->regs[j];
            row->life = effect->life; row->type = effect->type;
            row->priority = effect->priority; row->slot = i;
        }
    }
    if (omitted) *omitted = dropped;
    return count;
}

unsigned int OotCore_TalkState(void);
int OotCore_DrawItems(const OotCoreDrawItem** out);
static const OotCoreDrawItem* sItemsView;

static OotCoreMessageView sMsgView;
static u32 sMsgHash;

/* NES extended glyphs (charmap.nes.txt) to ASCII for the VDP2 font. Button
 * icons keep their letter; the Saturn layout keeps A/B for A/B. */
static char MsgView_Glyph(u8 c) {
    if (c >= 0x20 && c < 0x7F) {
        return (char)c;
    }
    switch (c) {
        case 0x9F: return 'A';
        case 0xA0: return 'B';
        case 0xA1: return 'C';
        case 0xA2: return 'L';
        case 0xA3: return 'R';
        case 0xA4: return 'Z';
        case 0xA5: return '^'; /* C-Up */
        case 0xA6: return 'v'; /* C-Down */
        case 0xA7: return '<'; /* C-Left */
        case 0xA8: return '>'; /* C-Right */
        case 0xA9: return '*'; /* triangle */
        case 0xAA: return '+'; /* control stick */
        case 0xAB: return '+'; /* D-pad */
        default:
            /* 0x80..0x9E: accented Latin; show the base letter's slot as '?' */
            return '?';
    }
}

static void MsgView_Layout(PlayState* play) {
    MessageContext* msgCtx = &play->msgCtx;
    OotCoreMessageView* v = &sMsgView;
    u32 hash = 2166136261u;
    s32 row = 0, col = 0;
    u8 colour = 0;
    u16 i, end = msgCtx->textDrawPos;
    s32 r, c;

    for (r = 0; r < OOT_CORE_MSG_ROWS; r++) {
        for (c = 0; c < OOT_CORE_MSG_COLS; c++) {
            v->text[r][c] = ' ';
            v->colour[r][c] = 0;
        }
        v->text[r][OOT_CORE_MSG_COLS] = '\0';
    }
    if (end > sizeof(msgCtx->msgBufDecoded)) {
        end = sizeof(msgCtx->msgBufDecoded);
    }
    for (i = 0; i < end; i++) {
        u8 ch = msgCtx->msgBufDecoded[i];
        switch (ch) {
            case MESSAGE_NEWLINE:
                row++;
                col = 0;
                break;
            case MESSAGE_COLOR:
                colour = msgCtx->msgBufDecoded[++i] & 0xF;
                break;
            case MESSAGE_SHIFT:
                col += msgCtx->msgBufDecoded[++i] / 8;
                break;
            case MESSAGE_TEXT_SPEED:
            case MESSAGE_ITEM_ICON:
                i++;
                break;
            case MESSAGE_SFX:
                i += 2;
                break;
            case MESSAGE_QUICKTEXT_ENABLE:
            case MESSAGE_QUICKTEXT_DISABLE:
            case MESSAGE_AWAIT_BUTTON_PRESS:
            case MESSAGE_UNSKIPPABLE:
            case MESSAGE_TWO_CHOICE:
            case MESSAGE_THREE_CHOICE:
            case MESSAGE_BACKGROUND:
            case MESSAGE_OCARINA:
                break;
            case MESSAGE_BOX_BREAK:
            case MESSAGE_TEXTID:
            case MESSAGE_BOX_BREAK_DELAYED:
            case MESSAGE_FADE:
            case MESSAGE_FADE2:
            case MESSAGE_PERSISTENT:
            case MESSAGE_EVENT:
            case MESSAGE_END:
                i = end; /* page ends here (Message_DrawText returns) */
                break;
            default:
                if (row < OOT_CORE_MSG_ROWS && col < OOT_CORE_MSG_COLS) {
                    v->text[row][col] = MsgView_Glyph(ch);
                    v->colour[row][col] = colour;
                }
                col++;
                break;
        }
    }
    v->rows = (row + 1 > OOT_CORE_MSG_ROWS) ? OOT_CORE_MSG_ROWS : (u8)(row + 1);
    v->choices = (msgCtx->textboxEndType == TEXTBOX_ENDTYPE_2_CHOICE)   ? 2
                 : (msgCtx->textboxEndType == TEXTBOX_ENDTYPE_3_CHOICE) ? 3
                                                                        : 0;
    v->choice = msgCtx->choiceIndex;
    v->prompt = OOT_CORE_MSG_PROMPT_NONE;
    if (msgCtx->msgMode == MSGMODE_TEXT_AWAIT_NEXT || msgCtx->msgMode == MSGMODE_TEXT_AWAIT_INPUT) {
        v->prompt = OOT_CORE_MSG_PROMPT_NEXT;
    } else if (msgCtx->msgMode == MSGMODE_TEXT_DONE && v->choices == 0) {
        v->prompt = (msgCtx->textboxEndType == TEXTBOX_ENDTYPE_DEFAULT) ? OOT_CORE_MSG_PROMPT_END
                    : (msgCtx->textboxEndType == TEXTBOX_ENDTYPE_HAS_NEXT ||
                       msgCtx->textboxEndType == TEXTBOX_ENDTYPE_EVENT)
                        ? OOT_CORE_MSG_PROMPT_NEXT
                        : OOT_CORE_MSG_PROMPT_NONE;
    }
    v->box_pos = msgCtx->textBoxPos;
    for (r = 0; r < OOT_CORE_MSG_ROWS; r++) {
        for (c = 0; c < OOT_CORE_MSG_COLS; c++) {
            hash = (hash ^ (u8)v->text[r][c]) * 16777619u;
            hash = (hash ^ v->colour[r][c]) * 16777619u;
        }
    }
    hash = (hash ^ (u32)(v->prompt | (v->choice << 4) | (v->rows << 8) | (v->box_pos << 12))) * 16777619u;
    if (hash != sMsgHash) {
        sMsgHash = hash;
        v->serial++;
    }
}

/* Ocarina notes use the C prompt; song-result text still comes from source. */
const OotCoreMessageView* OotCore_MessageView(void) {
    PlayState* play = gOotCorePlay;
    u8 mode;

    if (play == NULL) {
        sMsgView.active = false;
        return &sMsgView;
    }
    mode = play->msgCtx.msgMode;
    sMsgView.active = (mode >= MSGMODE_TEXT_BOX_GROWING && mode <= MSGMODE_TEXT_DELAYED_BREAK) ||
                      mode == MSGMODE_TEXT_AWAIT_NEXT || mode == MSGMODE_TEXT_DONE ||
                      mode == MSGMODE_DISPLAY_SONG_PLAYED_TEXT || mode == MSGMODE_SONG_PLAYED_ACT;
    if (sMsgView.active) {
        MsgView_Layout(play);
    }
    return &sMsgView;
}

#define NPC_VIEW_MAX 32
static OotCoreNpcView sNpcView[NPC_VIEW_MAX];
const int* OotCore_SkinMats(Actor* actor, unsigned char* count, unsigned short* model); /* oot_core_draw.cpp */

SkelAnime* OotCore_ActorSkel(Actor* actor) {
    switch (actor->id) {
        case ACTOR_EN_KO:
            return &((EnKo*)actor)->skelAnime;
        case ACTOR_EN_MD:
            return &((EnMd*)actor)->skelAnime;
        default:
            return NULL;
    }
}

/* NPCs whose actor struct the view knows. Others are left to the C game. */
int OotCore_NpcView(const OotCoreNpcView** out) {
    PlayState* play = gOotCorePlay;
    Actor* actor;
    int n = 0;

    *out = sNpcView;
    if (play == NULL) {
        return 0;
    }
    s32 cat;
    for (cat = 0; cat < ACTORCAT_MAX; cat++)
    for (actor = play->actorCtx.actorLists[cat].head; actor != NULL && n < NPC_VIEW_MAX;
         actor = actor->next) {
        OotCoreNpcView* v = &sNpcView[n];

        const NpcInteractInfo* info;
        const SkelAnime* skel;
        s32 alpha;

        if (actor->update == NULL) {
            continue;
        }
        if (actor->id == ACTOR_EN_KO) {
            EnKo* ko = (EnKo*)actor;
            info = &ko->interactInfo;
            skel = &ko->skelAnime;
            alpha = (s32)ko->modelAlpha;
        } else if (actor->id == ACTOR_EN_MD) {
            EnMd* md = (EnMd*)actor;
            info = &md->interactInfo;
            skel = &md->skelAnime;
            alpha = md->alpha;
        } else if ((gOotCoreFlags & OOT_CORE_FLAG_NPC_SPRITES) && actor->id == ACTOR_EN_NY) {
            /* Skeleton-less Spikes: two object DLs key the baked sheet.
             * Variant follows EnNy_Draw: rock, metal, metal + spikes out. */
            const EnNy* ny = (const EnNy*)actor;
            const ActorProfile* profile = gActorOverlayTable[ACTOR_EN_NY].profile;
            unsigned variant = ny->unk_1E0 > 0.25f ? 2 : ny->unk_1D8 > ny->unk_1D4 ? 1 : 0;
            v->tint = 0;
            v->mats = NULL;
            v->mat_count = 0;
            v->skin = 0;
            v->id = actor->id;
            v->params = actor->params;
            v->x = (s32)actor->world.pos.x;
            v->y = (s32)actor->world.pos.y;
            v->z = (s32)actor->world.pos.z;
            v->yaw = (u16)actor->shape.rot.y;
            v->head_x = v->head_y = v->torso_x = v->torso_y = 0;
            v->frame = 0;
            v->alpha = 255;
            /* Death swaps Draw to the rock-fragment effect: no body sprite. */
            v->flags = (actor->draw != NULL && profile && actor->draw == profile->draw) ? OOT_CORE_VIEW_DRAWN : 0;
            v->object = (u16)play->objectCtx.slots[actor->objectSlot].id;
            v->limbs = 0;
            v->anim = (u32)(uintptr_t)gEnNySpikeDL | (variant << 20);
            v->skeleton = (u32)(uintptr_t)gEnNyRockBodyDL;
            v->scale_x = (u16)(int)(actor->scale.x * 25600);
            v->scale_y = (u16)(int)(actor->scale.y * 25600);
            if (actor->colorFilterTimer)
                v->tint = (actor->colorFilterParams & 0x4000) ? 8 : 24;
            n++;
            continue;
        } else if ((gOotCoreFlags & OOT_CORE_FLAG_NPC_SPRITES) && (skel = GenericNpc_Skel(actor)) != NULL) {
            /* Generic NPC as a host sprite: object + animation + frame. */
            v->scale_x = v->scale_y = 256;
            v->tint = 0;
            v->mats = NULL;
            v->mat_count = 0;
            v->skin = 0;
            v->id = actor->id;
            v->params = actor->params;
            v->x = (s32)actor->world.pos.x;
            v->y = (s32)actor->world.pos.y;
            v->z = (s32)actor->world.pos.z;
            v->yaw = (u16)actor->shape.rot.y;
            v->head_x = v->head_y = v->torso_x = v->torso_y = 0;
            v->frame = (u16)(s32)skel->curFrame;
            v->alpha = 255;
            v->flags = (actor->draw != NULL) ? OOT_CORE_VIEW_DRAWN : 0;
            v->object = (u16)play->objectCtx.slots[actor->objectSlot].id;
            v->limbs = skel->limbCount;
            v->anim = (u32)(uintptr_t)skel->animation;
            v->skeleton = (u32)(uintptr_t)skel->skeleton;
            if (actor->id == ACTOR_EN_SKB || actor->id == ACTOR_EN_PEEHAT || actor->id == ACTOR_EN_PO_FIELD ||
                actor->id == ACTOR_EN_SB || actor->id == ACTOR_EN_WEIYER ||
                actor->id == ACTOR_EN_TITE || actor->id == ACTOR_EN_FIREFLY) {
                v->scale_x = (u16)(int)(actor->scale.x * 25600);
                v->scale_y = (u16)(int)(actor->scale.y * 25600);
                v->y += (int)(actor->shape.yOffset * actor->scale.y);
                if (actor->colorFilterTimer)
                    v->tint = (actor->colorFilterParams & 0x4000) ? 8 : 24;
                if (actor->id == ACTOR_EN_WEIYER) v->alpha = actor->shape.shadowAlpha;
                /* Baked sheets: Tektite 1 = blue textures; Keese 0 = normal
                 * body with eyes (ice Keese too), 1 = fire body without eyes. */
                if (actor->id == ACTOR_EN_TITE && actor->params == TEKTITE_BLUE)
                    v->anim |= 1u << 20;
                if (actor->id == ACTOR_EN_FIREFLY) {
                    if (((EnFirefly*)actor)->bodyElementalType != 0) /* source enum NORMAL */
                        v->anim |= 1u << 20;
                    /* Source DrawXlu drops every limb unless the Lens is on. */
                    if ((actor->flags & ACTOR_FLAG_REACT_TO_LENS) && !play->actorCtx.lensActive)
                        v->flags = 0;
                }
                if (actor->id == ACTOR_EN_SKB && (((EnSkb*)actor)->breakFlags & 2))
                    v->anim |= 1u << 20; /* source headless state */
                if (actor->id == ACTOR_EN_PO_FIELD) {
                    EnPoField* poe = (EnPoField*)actor;
                    unsigned variant = actor->params == 1 ? 1 : 0;
                    v->alpha = poe->lightColor.a;
                    if (actor->category == ACTORCAT_MISC) {
                        variant = actor->gravity < 0 ? 2 : actor->params == 1 ? 4 : 3;
                        if (variant == 2) v->alpha = 255;
                    }
                    v->anim |= variant << 20;
                }
            }
            n++;
            continue;
        } else {
            /* Generic skinned NPC: drawn only from captured matrices. */
            unsigned short model;
            unsigned char mat_count;
            const int* mats = OotCore_SkinMats(actor, &mat_count, &model);

            if (mats == NULL || model == 0) {
                continue;
            }
            v->object = 0;
            v->limbs = 0;
            v->anim = 0;
            v->skeleton = 0;
            v->scale_x = v->scale_y = 256;
            v->tint = 0;
            v->mat_count = mat_count;
            v->mats = mats;
            v->skin = model;
            v->id = actor->id;
            v->params = actor->params;
            v->x = (s32)actor->world.pos.x;
            v->y = (s32)actor->world.pos.y;
            v->z = (s32)actor->world.pos.z;
            v->yaw = (u16)actor->shape.rot.y;
            v->head_x = v->head_y = v->torso_x = v->torso_y = 0;
            v->frame = 0;
            v->alpha = 255;
            v->flags = OOT_CORE_VIEW_DRAWN;
            n++;
            continue;
        }
        /* Reject ordinary props before touching the output row. Accepted
         * native NPCs still clear metadata left by a previous scene's sheet. */
        v->object = 0;
        v->limbs = 0;
        v->anim = 0;
        v->skeleton = 0;
        v->scale_x = v->scale_y = 256;
        v->tint = 0;
        v->head_x = info->headRot.x;
        v->head_y = info->headRot.y;
        v->torso_x = info->torsoRot.x;
        v->torso_y = info->torsoRot.y;
        v->frame = (u16)(s32)skel->curFrame;
        v->alpha = (u8)(alpha < 0 ? 0 : alpha > 255 ? 255 : alpha);
        v->id = actor->id;
        v->params = actor->params;
        v->x = (s32)actor->world.pos.x;
        v->y = (s32)actor->world.pos.y;
        v->z = (s32)actor->world.pos.z;
        v->yaw = (u16)actor->shape.rot.y;
        v->flags = (actor->draw != NULL) ? OOT_CORE_VIEW_DRAWN : 0;
        v->mats = OotCore_SkinMats(actor, &v->mat_count, &v->skin);
        v->skin = 0;
        n++;
    }
    return n;
}

int OotCore_PropQuery(short actor_id, int x, int z) {
    PlayState* play = gOotCorePlay;
    Actor* actor;
    s32 i;

    if (play == NULL) {
        return -1;
    }
    for (i = 0; i < ACTORCAT_MAX; i++) {
        for (actor = play->actorCtx.actorLists[i].head; actor != NULL; actor = actor->next) {
            s32 dx, dz;

            if (actor->update == NULL || actor->id != actor_id) {
                continue;
            }
            dx = (s32)actor->home.pos.x - x;
            dz = (s32)actor->home.pos.z - z;
            if (dx * dx + dz * dz > 24 * 24) {
                continue;
            }
            if (actor_id == ACTOR_EN_KANBAN) {
                if (actor->params == ENKANBAN_PIECE) {
                    continue; /* detached signs are not spawned on Saturn */
                }
                EnKanban* sign = (EnKanban*)actor;
                return sign->partFlags == OOT_SIGN_INTACT ? (int)OOT_SIGN_INTACT :
                       sign->cutMarkTimer > 0 ? sign->cutMarkTimer : 0;
            }
            return 0;
        }
    }
    return -1;
}

extern u32 gOotCorePhaseUs[4];
u32 gOotCoreTalkCalls, gOotCoreTalkWhy; /* Actor_OfferTalkExchange (importer hook) */
extern const OotCoreHost* gOotCoreHost;

/* Per actor id update time this step (profiling: debug row 17 shows the
 * three most expensive ids). Reset by OotCore_ProfileReset each step. */
#define PROF_IDS 24
static s16 sProfId[PROF_IDS];
static u32 sProfUs[PROF_IDS];
static u8 sProfCount[PROF_IDS];
static s32 sProfN;

void OotCore_ProfileReset(void) {
    sProfN = 0;
}

void OotCore_ProfiledUpdate(Actor* actor, PlayState* play) {
    u32 t0, us;
    s32 i;

    if (gOotCoreHost == NULL || gOotCoreHost->ticks == NULL) {
        actor->update(actor, play);
        return;
    }
    t0 = gOotCoreHost->ticks();
    actor->update(actor, play);
    us = gOotCoreHost->ticks_to_us(gOotCoreHost->ticks() - t0);
    for (i = 0; i < sProfN && sProfId[i] != actor->id; i++) {
    }
    if (i == sProfN) {
        if (sProfN == PROF_IDS) {
            return;
        }
        sProfId[i] = actor->id;
        sProfUs[i] = 0;
        sProfCount[i] = 0;
        sProfN++;
    }
    sProfUs[i] += us;
    sProfCount[i]++;
}

/* "oc t<talk> m<msgMode> x<textId> n<npcs> c<AT>/<AC>/<OC>" for the debug panel,
 * then (second line) phase times in 0.1 ms: collision, actors, message, draw,
 * and the nearest NPC: distance, talk distance, actor flags low byte. */
int OotCore_ToolDebug(char* out);
const char* OotCore_DebugText2(void) {
    static char sText[64];
    static const char hex[] = "0123456789ABCDEF";
    PlayState* play = gOotCorePlay;
    Player* player;
    Actor* near = NULL;
    Actor* a;
    char* p = sText;
    u32 v;
    s32 k, i;

    if (play == NULL || (player = GET_PLAYER(play)) == NULL) {
        sText[0] = '\0';
        return sText;
    }
    for (a = play->actorCtx.actorLists[ACTORCAT_NPC].head; a != NULL; a = a->next) {
        if (near == NULL || a->xzDistToPlayer < near->xzDistToPlayer) {
            near = a;
        }
    }
#define PUT_DEC(val)                              \
    {                                             \
        char tmp[8];                              \
        s32 nd = 0;                               \
        v = (u32)(val);                           \
        do {                                      \
            tmp[nd++] = (char)('0' + v % 10);     \
            v /= 10;                              \
        } while (v != 0 && nd < 7);               \
        while (nd > 0) {                          \
            *p++ = tmp[--nd];                     \
        }                                         \
    }
    for (i = 0; i < 4; i++) {
        PUT_DEC(gOotCorePhaseUs[i] / 100);
        *p++ = i < 3 ? '/' : ' ';
    }
    /* Live tools replace the profile (bridge_items.cpp OotCore_ToolDebug). */
    if (OotCore_ToolDebug(p)) {
        while (*p != 0) p++;
    } else
    /* Top 3 actor ids by update time: id(hex) x count = 0.1 ms. */
    {
        s32 used[3] = { -1, -1, -1 }, r, best;
        for (r = 0; r < 3; r++) {
            best = -1;
            for (i = 0; i < sProfN; i++) {
                if (i != used[0] && i != used[1] && (best < 0 || sProfUs[i] > sProfUs[best])) {
                    best = i;
                }
            }
            if (best < 0) {
                break;
            }
            used[r] = best;
            v = (u32)sProfId[best];
            for (k = 2; k >= 0; k--) {
                *p++ = hex[(v >> (k * 4)) & 0xF];
            }
            *p++ = 'x';
            PUT_DEC(sProfCount[best]);
            *p++ = '=';
            PUT_DEC(sProfUs[best] / 100);
            *p++ = ' ';
        }
    }
    /* o<offer calls this step>w<last fail reason> */
    *p++ = 'o';
    PUT_DEC(gOotCoreTalkCalls);
    *p++ = 'w';
    PUT_DEC(gOotCoreTalkWhy);
    *p++ = ' ';
    gOotCoreTalkCalls = 0;
    if (near != NULL && p < sText + 40) {
        *p++ = 'd';
        PUT_DEC((s32)near->xzDistToPlayer);
        *p++ = ' ';
        *p++ = 'k';
        PUT_DEC((u32)((s32)player->talkActorDistance > 99999 ? 99999 : (s32)player->talkActorDistance));
        *p++ = ' ';
        *p++ = 'f';
        v = near->flags;
        for (k = 1; k >= 0; k--) {
            *p++ = hex[(v >> (k * 4)) & 0xF];
        }
    }
#undef PUT_DEC
    *p = '\0';
    return sText;
}

#ifdef PLAYER_SOURCE
extern int Player_CanUpdateItems(Player* player);
/* Read only, evaluated by Debug row 21 after the core is joined. Bits mirror
 * the source item gates; no counters or work in the Player update path.
 * 0 CanUpdateItems false; 1 non-Player category; 2 changing held item;
 * 3 item-action mismatch without SHIELDING;
 * 4 no health; 5 scripted CS; 6 Player CS action; 7 shooting gallery;
 * 8 non-main camera; 9 transition; 10 stopped timer;
 * 11 carrying actor or STATE1_29; 12 hookshot child missing;
 * 13 C-left disabled/empty; 14 STATE1_0/dead; 15 swimming (STATE1_27).
 * Zero means these guards allow C-left selection, not proof the current
 * action actually called Player_UpdateUpperBody/Player_UpdateItems. */
static u32 OotCore_ItemGateMask(PlayState* play, Player* player) {
    u32 bits = 0;
    u32 flags = player->stateFlags1;
    if (!Player_CanUpdateItems(player)) bits |= 1u << 0;
    if (player->actor.category != ACTORCAT_PLAYER) bits |= 1u << 1;
    if (flags & PLAYER_STATE1_START_CHANGING_HELD_ITEM) bits |= 1u << 2;
    if (player->heldItemAction != player->itemAction && !(flags & PLAYER_STATE1_SHIELDING)) bits |= 1u << 3;
    if (!gSaveContext.save.info.playerData.health) bits |= 1u << 4;
    if (play->csCtx.state != CS_STATE_IDLE) bits |= 1u << 5;
    if (player->csAction != PLAYER_CSACTION_NONE) bits |= 1u << 6;
    if (play->shootingGalleryStatus != 0) bits |= 1u << 7;
    if (play->activeCamId != CAM_ID_MAIN) bits |= 1u << 8;
    if (play->transitionTrigger == TRANS_TRIGGER_START) bits |= 1u << 9;
    if (gSaveContext.timerState == TIMER_STATE_STOP) bits |= 1u << 10;
    if (flags & (PLAYER_STATE1_CARRYING_ACTOR | PLAYER_STATE1_29)) bits |= 1u << 11;
    if (Player_HoldsHookshot(player) && player->heldActor == NULL) bits |= 1u << 12;
    if (C_BTN_ITEM(0) >= ITEM_NONE_FE) bits |= 1u << 13;
    if (flags & (PLAYER_STATE1_0 | PLAYER_STATE1_DEAD)) bits |= 1u << 14;
    if (flags & PLAYER_STATE1_27) bits |= 1u << 15;
    return bits;
}
#endif

/* Source Player: live item admission, queried only by the Debug overlay. */
const char* OotCore_DebugText(void) {
    static char sText[40];
    static const char hex[] = "0123456789ABCDEF";
    PlayState* play = gOotCorePlay;
    Player* player;
    char* p = sText;
    u32 v;
    s32 k;

    if (play == NULL || (player = GET_PLAYER(play)) == NULL) {
        sText[0] = '\0';
        return sText;
    }
#define PUT_HEX(val, digits)                         \
    v = (u32)(val);                                  \
    for (k = (digits) - 1; k >= 0; k--) {            \
        *p++ = hex[(v >> (k * 4)) & 0xF];            \
    }
    /* Only p is retained. i/g/c/f are live, after the most recent update:
     * held item / held action / current action; gate mask; C-left item/status;
     * stateFlags1. Fits the existing 40-byte buffer, without ABI/BSS growth. */
#ifdef PLAYER_SOURCE
    extern unsigned short gOotCoreInputTrace[6];
    *p++ = 'p'; PUT_HEX(gOotCoreInputTrace[0], 4);
    *p++ = ' '; *p++ = 'i'; PUT_HEX((u8)player->heldItemId, 2);
    *p++ = '/'; PUT_HEX((u8)player->heldItemAction, 2);
    *p++ = '/'; PUT_HEX((u8)player->itemAction, 2);
    *p++ = ' '; *p++ = 'g'; PUT_HEX(OotCore_ItemGateMask(play, player), 4);
    *p++ = ' '; *p++ = 'c'; PUT_HEX(gSaveContext.save.info.equips.buttonItems[1], 2);
    *p++ = '/'; PUT_HEX(gSaveContext.buttonStatus[1], 2);
    *p++ = ' '; *p++ = 'f'; PUT_HEX(player->stateFlags1, 8);
    *p = '\0';
    return sText;
#endif
    *p++ = 't';
    PUT_HEX(OotCore_TalkState(), 1);
    *p++ = ' ';
    *p++ = 'm';
    PUT_HEX(play->msgCtx.msgMode, 2);
    *p++ = ' ';
    *p++ = 'x';
    PUT_HEX(play->msgCtx.textId, 4);
    *p++ = ' ';
    *p++ = 'n';
    PUT_HEX(play->actorCtx.actorLists[ACTORCAT_NPC].length, 2);
    *p++ = ' ';
    *p++ = 'c';
    PUT_HEX(play->colChkCtx.colATCount, 2);
    *p++ = '/';
    PUT_HEX(play->colChkCtx.colACCount, 2);
    *p++ = '/';
    PUT_HEX(play->colChkCtx.colOCCount, 2);
    *p++ = ' ';
    *p++ = 'd';
    PUT_HEX(OotCore_DrawItems(&sItemsView), 2);
#undef PUT_HEX
    *p = '\0';
    return sText;
}

/* Bit 0: the player proxy is in a conversation. Bit 1: a decomp actor
 * offered talk this frame (A would accept it). */
unsigned int OotCore_TalkState(void) {
    PlayState* play = gOotCorePlay;
    Player* player;

    if (play == NULL || (player = GET_PLAYER(play)) == NULL) {
        return 0;
    }
    return (((player->stateFlags1 & PLAYER_STATE1_TALKING) ||
             (player->stateFlags2 & PLAYER_STATE2_USING_OCARINA)) ? 1u : 0u) |
           (player->talkActor != NULL ? 2u : 0u);
}

/* Live DynaPoly actors for the C collision (bg_dyna): untransformed source
 * collision plus the actor transform (DynaPoly_ExpandSRT: scale, shape.rot,
 * world.pos). The C side converts the mesh once per actor. */
int OotCore_DynaView(const OotCoreDynaView** out) {
    static OotCoreDynaView sViews[OOT_CORE_DYNA_VIEWS_MAX];
    int n = 0;
    *out = sViews;
    if (gOotCorePlay == NULL) {
        return 0;
    }
    DynaCollisionContext* dyna = &gOotCorePlay->colCtx.dyna;
    for (s32 i = 0; i < BG_ACTOR_MAX && n < OOT_CORE_DYNA_VIEWS_MAX; i++) {
        if (!(dyna->bgActorFlags[i] & BGACTOR_IN_USE)) {
            continue;
        }
        Actor* actor = dyna->bgActors[i].actor;
        CollisionHeader* col = dyna->bgActors[i].colHeader;
        if (actor == NULL || col == NULL || col->polyList == NULL || col->vtxList == NULL) {
            continue;
        }
        OotCoreDynaView* v = &sViews[n++];
        v->key = (unsigned int)(uintptr_t)actor;
        v->vertices = (const short*)col->vtxList;
        v->polys = (const unsigned short*)col->polyList;
        v->surfaces = (const unsigned int*)col->surfaceTypeList;
        v->num_vertices = col->numVertices;
        v->num_polys = col->numPolygons;
        v->x = (int)actor->world.pos.x;
        v->y = (int)actor->world.pos.y;
        v->z = (int)actor->world.pos.z;
        v->rot_y = (unsigned short)actor->shape.rot.y;
        v->transform = (unsigned char)((DynaPolyActor*)actor)->transformFlags;
        v->enabled = !(dyna->bgActorFlags[i] & BGACTOR_COLLISION_DISABLED);
#if OOT_CORE_HWFLOAT
        v->scale_q16 = (int)(actor->scale.x * 65536.0f);
#else
        v->scale_q16 = actor->scale.x.v;   /* Fx is Q16 storage */
#endif
    }
    return n;
}
