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
#include "overlays/actors/ovl_En_Ko/z_en_ko.h"
#include "overlays/actors/ovl_En_Md/z_en_md.h"
#include "overlays/actors/ovl_En_Kanban/z_en_kanban.h"
#include "oot_core_api.h"
#include "overlays/actors/ovl_En_In/z_en_in.h"
#include "overlays/actors/ovl_En_Ma1/z_en_ma1.h"
#include "overlays/actors/ovl_En_Ma2/z_en_ma2.h"
#include "overlays/actors/ovl_En_Ta/z_en_ta.h"
#include "overlays/actors/ovl_En_Niw/z_en_niw.h"
#include "overlays/actors/ovl_En_Cow/z_en_cow.h"

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
        default: return NULL;
    }
}

extern PlayState* gOotCorePlay; /* oot_core_api.cpp */
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

#define NPC_VIEW_MAX 16
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
        /* Rows outlive actors and scenes. Native Kokiri views do not carry a
         * generic sheet key; clear a previous Ranch occupant's metadata. */
        v->object = 0;
        v->limbs = 0;
        v->anim = 0;
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
        } else if ((gOotCoreFlags & OOT_CORE_FLAG_NPC_SPRITES) && (skel = GenericNpc_Skel(actor)) != NULL) {
            /* Generic NPC as a host sprite: object + animation + frame. */
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
            n++;
            continue;
        } else {
            /* Generic skinned NPC: drawn only from captured matrices. */
            unsigned short model;
            const int* mats = OotCore_SkinMats(actor, &v->mat_count, &model);

            if (mats == NULL || model == 0) {
                continue;
            }
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
                    continue; /* flying piece: not drawn yet (APPROXIMATE) */
                }
                return ((EnKanban*)actor)->partFlags;
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

/* "oc t<talk> m<msgMode> x<textId> n<npcs> c<AT>/<AC>/<OC>" for the debug panel. */
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
