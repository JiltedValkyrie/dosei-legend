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
#include "array_count.h"
#include "message.h"
#include "message_data_fmt.h"
#include "play_state.h"
#include "player.h"
#include "z_lib.h"
#include "save.h"
#include "effect.h"
#include "overlays/actors/ovl_En_Ko/z_en_ko.h"
#include "overlays/actors/ovl_En_Md/z_en_md.h"
#include "overlays/actors/ovl_En_Kanban/z_en_kanban.h"
#include "oot_sign_visual.h"
#include "oot_core_api.h"
#include "oot_actor_pack.h"
#include "overlays/actors/ovl_En_In/z_en_in.h"
#include "overlays/actors/ovl_En_Ma1/z_en_ma1.h"
#include "overlays/actors/ovl_En_Ma2/z_en_ma2.h"
#include "overlays/actors/ovl_En_Ta/z_en_ta.h"
#include "overlays/actors/ovl_En_Niw/z_en_niw.h"
#include "overlays/actors/ovl_En_Cow/z_en_cow.h"
#include "overlays/actors/ovl_En_Horse_Link_Child/z_en_horse_link_child.h"
#include "overlays/actors/ovl_En_Horse_Normal/z_en_horse_normal.h"
#include "overlays/actors/ovl_En_Skb/z_en_skb.h"
#include "overlays/actors/ovl_En_Peehat/z_en_peehat.h"
#include "overlays/actors/ovl_En_Po_Field/z_en_po_field.h"
#include "overlays/actors/ovl_En_Sb/z_en_sb.h"
#include "overlays/actors/ovl_En_Weiyer/z_en_weiyer.h"
#include "overlays/actors/ovl_En_Tite/z_en_tite.h"
#include "overlays/actors/ovl_En_Firefly/z_en_firefly.h"
#include "overlays/actors/ovl_En_Ny/z_en_ny.h"
#include "assets/objects/object_ny/object_ny.h"
#include "overlays/actors/ovl_En_Go2/z_en_go2.h"
#include "overlays/actors/ovl_En_Du/z_en_du.h"
#include "overlays/actors/ovl_En_Sa/z_en_sa.h"
#include "overlays/actors/ovl_En_Owl/z_en_owl.h"
#include "overlays/actors/ovl_En_Zl4/z_en_zl4.h"
#include "overlays/actors/ovl_Demo_Im/z_demo_im.h"
#include "overlays/actors/ovl_En_Viewer/z_en_viewer.h"
#include "overlays/actors/ovl_En_Heishi2/z_en_heishi2.h"
#include "overlays/actors/ovl_En_Heishi1/z_en_heishi1.h"
#include "overlays/actors/ovl_En_Heishi3/z_en_heishi3.h"
#include "overlays/actors/ovl_En_Daiku_Kakariko/z_en_daiku_kakariko.h"
#include "overlays/actors/ovl_En_Niw_Lady/z_en_niw_lady.h"
#include "overlays/actors/ovl_En_Dodojr/z_en_dodojr.h"
#include "overlays/actors/ovl_En_Dodongo/z_en_dodongo.h"
#include "overlays/actors/ovl_En_Am/z_en_am.h"
#include "overlays/actors/ovl_En_Zf/z_en_zf.h"
#include "overlays/actors/ovl_En_Shopnuts/z_en_shopnuts.h"
#include "overlays/actors/ovl_En_Dns/z_en_dns.h"
#include "overlays/actors/ovl_En_Kakasi2/z_en_kakasi2.h"
#include "overlays/actors/ovl_En_Vm/z_en_vm.h"
#include "overlays/actors/ovl_En_Sw/z_en_sw.h"
#include "overlays/actors/ovl_En_Wf/z_en_wf.h"
#include "overlays/actors/ovl_En_Dekunuts/z_en_dekunuts.h"
#include "assets/objects/object_dekunuts/object_dekunuts.h"
#include "assets/objects/object_st/object_st.h"
#include "overlays/actors/ovl_En_Ossan/z_en_ossan.h"
#include "overlays/actors/ovl_En_GirlA/z_en_girla.h"
#include "child_route_shop_items.h"
#include "child_common_keys.h"
#include "overlays/actors/ovl_En_Ex_Item/z_en_ex_item.h"
#include "overlays/actors/ovl_Item_Etcetera/z_item_etcetera.h"
#include "overlays/actors/ovl_En_Ex_Ruppy/z_en_ex_ruppy.h"
#include "overlays/actors/ovl_En_G_Switch/z_en_g_switch.h"
#include "overlays/actors/ovl_En_Syateki_Man/z_en_syateki_man.h"
#include "overlays/actors/ovl_En_Bom_Bowl_Man/z_en_bom_bowl_man.h"
#include "overlays/actors/ovl_En_Takara_Man/z_en_takara_man.h"
#include "assets/objects/object_skj/object_skj.h"
#include "overlays/actors/ovl_En_Cs/z_en_cs.h"
#include "overlays/actors/ovl_En_Mm/z_en_mm.h"
#include "overlays/actors/ovl_En_Skj/z_en_skj.h"
#include "overlays/actors/ovl_En_Dog/z_en_dog.h"
#include "overlays/actors/ovl_En_Gm/z_en_gm.h"
#include "overlays/actors/ovl_En_Ssh/z_en_ssh.h"
#include "overlays/actors/ovl_En_Sth/z_en_sth.h"
#include "overlays/actors/ovl_En_Tk/z_en_tk.h"
#include "overlays/actors/ovl_En_Hy/z_en_hy.h"
#include "overlays/actors/ovl_En_Heishi4/z_en_heishi4.h"
#include "overlays/actors/ovl_En_Hs2/z_en_hs2.h"
#include "overlays/actors/ovl_En_Ani/z_en_ani.h"
#include "overlays/actors/ovl_En_Tg/z_en_tg.h"
#include "overlays/actors/ovl_En_Toryo/z_en_toryo.h"
#include "overlays/actors/ovl_En_Syateki_Niw/z_en_syateki_niw.h"
#include "overlays/actors/ovl_En_Guest/z_en_guest.h"
#include "oot_core_shop.h"
#include "overlays/actors/ovl_Boss_Dodongo/z_boss_dodongo.h"
#include "overlays/actors/ovl_En_Bdfire/z_en_bdfire.h"
#include "overlays/actors/ovl_En_Fire_Rock/z_en_fire_rock.h"
#include "overlays/actors/ovl_En_Encount2/z_en_encount2.h"
#include "overlays/actors/ovl_Demo_Effect/z_demo_effect.h"
#include "overlays/actors/ovl_Bg_Dy_Yoseizo/z_bg_dy_yoseizo.h"
#include "assets/objects/object_god_lgt/object_god_lgt.h"
#include "assets/objects/object_efc_star_field/object_efc_star_field.h"
#include "assets/objects/object_kingdodongo/object_kingdodongo.h"
#include "assets/objects/object_oF1d_map/object_oF1d_map.h"
#include "assets/objects/object_sd/object_sd.h"
#include "assets/objects/object_shopnuts/object_shopnuts.h"
#include "z_actor_dlftbls.h"

extern u32 gOotCoreFlags; /* oot_core_api.cpp, OOT_CORE_FLAG_* */

extern PlayState* gOotCorePlay; /* oot_core_api.cpp */
extern EffectSsInfo sEffectSsInfo;

int OotCore_ShopView(OotCoreShopView* out) {
    if (!out) return 0;
    *out = {};
    if (!gOotCorePlay) return 0;
    for (Actor* actor = gOotCorePlay->actorCtx.actorLists[ACTORCAT_NPC].head; actor; actor = actor->next) {
        if (actor->id != ACTOR_EN_OSSAN || !actor->update) continue;
        const EnOssan* shop = (const EnOssan*)actor;
        out->flags = OOT_SHOP_OWNED;
        out->state = shop->stateFlag;
        out->face_degrees = (s16)shop->cameraFaceAngle;
        out->cursor_index = shop->cursorIndex;
        out->pulse = (u8)(int)(shop->cursorAnimTween * 255);
        if (GET_PLAYER(gOotCorePlay)->stateFlags2 & PLAYER_STATE2_29) out->flags |= OOT_SHOP_BROWSING;
        if (shop->stateFlag == OSSAN_STATE_FACING_SHOPKEEPER ||
            (shop->stateFlag >= OSSAN_STATE_LOOK_SHELF_LEFT && shop->stateFlag <= OSSAN_STATE_LOOK_SHOPKEEPER))
            out->flags |= OOT_SHOP_CONTROL;
        if (shop->stickLeftPrompt.isEnabled) out->flags |= OOT_SHOP_LEFT;
        if (shop->stickRightPrompt.isEnabled) out->flags |= OOT_SHOP_RIGHT;
        if (shop->drawCursor && shop->cursorIndex < 8 && shop->shelfSlots[shop->cursorIndex]) {
            const Actor* stock = &shop->shelfSlots[shop->cursorIndex]->actor;
            out->flags |= OOT_SHOP_CURSOR;
            out->cursor[0] = (int)stock->world.pos.x;
            out->cursor[1] = (int)(stock->world.pos.y + stock->shape.yOffset * stock->scale.y) + 5;
            out->cursor[2] = (int)stock->world.pos.z;
        }
        return 1;
    }
    return 0;
}

#include "child_route_effect_views.inc"

int OotCore_EffectView(OotCoreEffectView* out, unsigned int capacity, unsigned int* omitted) {
    unsigned int count = 0, dropped = 0;
    if (!out) capacity = 0;
    if (capacity > OOT_CORE_EFFECT_VIEWS_MAX) capacity = OOT_CORE_EFFECT_VIEWS_MAX;
    /* A killed boss has no draw view. The source clear flag still needs to
     * restore the cooled arena when loading a completed boss room. */
    if (gOotCorePlay && gOotCorePlay->sceneId == SCENE_DODONGOS_CAVERN_BOSS) {
        unsigned phase = Flags_GetClear(gOotCorePlay, 1) ? 256 : 0;
        for (Actor* actor = gOotCorePlay->actorCtx.actorLists[ACTORCAT_BOSS].head;
             actor; actor = actor->next)
            if (actor->id == ACTOR_BOSS_DODONGO && actor->update)
                phase = ((BossDodongo*)actor)->saturnLavaPhase;
        if (count == capacity) ++dropped;
        else {
            OotCoreEffectView* row = &out[count++];
            row->x = row->y = row->z = 0;
            for (unsigned j = 0; j < 13; ++j) row->regs[j] = 0;
            row->regs[0] = phase; row->life = 1;
            row->type = OOT_CORE_EFFECT_DODONGO_LAVA;
            row->priority = 0; row->slot = 0xffff;
        }
    }
    /* Prioritize damaging actor-owned flames over decorative particles. */
    if (gOotCorePlay) {
        for (Actor* actor = gOotCorePlay->actorCtx.actorLists[ACTORCAT_ENEMY].head; actor; actor = actor->next) {
            if (actor->id != ACTOR_EN_VM || !actor->update) continue;
            const EnVm* beamos = (const EnVm*)actor;
            if (beamos->unk_260 < 3 || beamos->beamScale.z <= 0) continue;
            if (count == capacity) { ++dropped; continue; }
            OotCoreEffectView* row = &out[count++];
            *row = {};
            row->x = (int)beamos->beamPos1.x; row->y = (int)beamos->beamPos1.y; row->z = (int)beamos->beamPos1.z;
            row->regs[0] = (int)beamos->beamPos3.x; row->regs[1] = (int)beamos->beamPos3.y;
            row->regs[2] = (int)beamos->beamPos3.z; row->regs[3] = 2;
            row->life = 1; row->type = OOT_CORE_EFFECT_BEAMOS_BEAM; row->slot = 0xffff;
        }
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
    if (gOotCorePlay && gOotCorePlay->sceneId == SCENE_DODONGOS_CAVERN_BOSS) {
        for (Actor* actor = gOotCorePlay->actorCtx.actorLists[ACTORCAT_BOSS].head;
             actor; actor = actor->next) {
            if (actor->id != ACTOR_BOSS_DODONGO || !actor->update) continue;
            const BossDodongo* boss = (const BossDodongo*)actor;
            for (unsigned i = 0; i < BOSS_DODONGO_EFFECT_COUNT; ++i) {
                const BossDodongoEffect* effect = &boss->effects[i];
                if (effect->unk_24 != 1 || effect->alpha <= 0) continue;
                if (count == capacity) { ++dropped; continue; }
                OotCoreEffectView* row = &out[count++];
                row->x = (int)effect->unk_00.x; row->y = (int)effect->unk_00.y;
                row->z = (int)effect->unk_00.z;
                for (unsigned j = 0; j < 13; ++j) row->regs[j] = 0;
                row->regs[0] = (int)(effect->unk_2C * 500);
                row->regs[1] = effect->color.r; row->regs[2] = effect->color.g;
                row->regs[3] = effect->color.b; row->regs[4] = effect->alpha;
                row->life = 1; row->type = OOT_CORE_EFFECT_DODONGO_EMBER;
                row->priority = 1; row->slot = i;
            }
        }
    }
    if (gOotCorePlay) {
        for (unsigned cat = 0; cat < ACTORCAT_MAX; ++cat)
        for (Actor* actor = gOotCorePlay->actorCtx.actorLists[cat].head; actor; actor = actor->next) {
            if (actor->id != ACTOR_EN_ENCOUNT2 || !actor->update) continue;
            const EnEncount2* weather = (const EnEncount2*)actor;
            for (unsigned i = 0; i < EN_ENCOUNT2_EFFECT_COUNT; ++i) {
                const EnEncount2Effect* effect = &weather->effects[i];
                if (!effect->isAlive) continue;
                if (count == capacity) { ++dropped; continue; }
                OotCoreEffectView* row = &out[count++];
                *row = {};
                row->x = (int)effect->pos.x; row->y = (int)effect->pos.y; row->z = (int)effect->pos.z;
                row->regs[0] = (int)(effect->scale * 1000);
                row->regs[1] = 255; row->regs[2] = 155; row->regs[3] = 55; row->regs[4] = 255;
                row->life = 1; row->type = OOT_CORE_EFFECT_MOUNTAIN_FRAGMENT;
                row->priority = 2; row->slot = i;
            }
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
    count = ChildRoute_EffectViews(out, capacity, count, &dropped);
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
    /* Original Player_Draw/GetItemImpl gates and hand reference. The full
     * scene reward atlas is already resident; no N64 get-object DMA or
     * runtime item mesh is needed during the chest/get-item CD cue. */
    Player* player = GET_PLAYER(play);
    if (player && player->actor.draw && !(player->stateFlags2 & PLAYER_STATE2_29) && player->unk_862 > 0) {
        extern Vec3f sGetItemRefPos;
        OotCoreNpcView* v = &sNpcView[n++];
        *v = {};
        v->id = ACTOR_PLAYER; v->object = 0xfff;
        v->anim = player->unk_862;
        v->x = (int)(sGetItemRefPos.x + FXL(3.3f) * Math_SinS(player->actor.shape.rot.y));
        v->y = (int)sGetItemRefPos.y + (player->exchangeItemId != EXCH_ITEM_NONE ? 6 : 14);
        v->z = (int)(sGetItemRefPos.z + FXL(3.3f) * Math_CosS(player->actor.shape.rot.y));
        v->yaw = play->gameplayFrames * 1000;
        v->alpha = 255; v->flags = OOT_CORE_VIEW_DRAWN;
        v->scale_x = v->scale_y = 256; /* offline source scale 0.2 */
    }
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
        if (gOotCoreFlags & OOT_CORE_FLAG_NPC_SPRITES) {
            int rows=OotCore_PackNpcView(play,actor,v,NPC_VIEW_MAX-n,&gSaveContext);
            if (rows) { if (rows>0) n+=rows; continue; }
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
