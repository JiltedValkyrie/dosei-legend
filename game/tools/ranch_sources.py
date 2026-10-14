"""Source Ranch horses and main minigame timer, with sprite presentation only."""
import re
from field_enemy_sources import replace_body, replace_once
from child_route_npcs import append_update

ACTORS = ('En_Horse_Link_Child', 'En_Horse_Normal')
SOURCES = [f'src/overlays/actors/ovl_{name}/z_{name.lower()}.c' for name in ACTORS]
OBJECTS = ('object_horse_link_child', 'object_horse_normal')
NPC_SOURCES = [('ACTOR_' + name.upper(), source) for name, source in zip(ACTORS, SOURCES)]
EXISTING_NPCS = ('En_In', 'En_Ma1', 'En_Ma2', 'En_Ta', 'En_Niw', 'En_Cow')
EXISTING_SOURCES = [f'src/overlays/actors/ovl_{name}/z_{name.lower()}.c' for name in EXISTING_NPCS]


def adapt(rel, text):
    if rel in [p[:-2] + '.h' for p in EXISTING_SOURCES]:
        return re.sub(r'Vec3s (jointTable|morphTable)\[[^\]]+\];', r'Vec3s* \1;', text)
    if rel in EXISTING_SOURCES:
        for name in re.findall(r'^void (En(?:In|Ma1|Ma2|Ta|Niw|Cow)_(?:Draw\w*|PostLimbDraw))\([^;{}]*\) \{', text, re.M):
            text = replace_body(text, name, '    /* Offline sprite; source update owns focus and effect clocks. */')
        for name in re.findall(r'^s32 (En(?:In|Ma1|Ma2|Ta|Niw|Cow)_OverrideLimbDraw)\([^;{}]*\) \{', text, re.M):
            text = replace_body(text, name, '    return 0; /* No runtime character pose. */')
        actor = EXISTING_NPCS[EXISTING_SOURCES.index(rel)].replace('_', '')
        height = {'EnIn': 60, 'EnMa1': 42, 'EnMa2': 60, 'EnTa': 55, 'EnCow': 50}.get(actor)
        if height:
            # Cow's existing no-head-work adapter returns before Update ends.
            marker = f'    {actor}* this = ({actor}*)thisx;'
            start = re.search(r'void ' + actor + r'_Update\(Actor\* thisx, PlayState\* play2?\) \{', text).start()
            at = text.index(marker, start) + len(marker)
            text = text[:at] + f'\n    Actor_SetFocus(&this->actor, {height}.0f);' + text[at:]
        if actor in ('EnMa1', 'EnMa2'):
            text = append_update(text, actor + '_Update',
                '    Audio_UpdateMalonSinging(Math_Vec3f_DistXZ(&this->actor.world.pos, &GET_ACTIVE_CAM(play)->eye),\n'
                '                             NA_BGM_LONLON);')
        return text
    if rel in [p[:-2] + '.h' for p in SOURCES]:
        text = text.replace('#include "skin.h"', '#include "skin.h"\n#include "ranch_horse_sprite.h"')
        text = replace_once(text, 'Skin skin;', 'RanchHorseSprite skin;')
        if rel.endswith('z_en_horse_normal.h'):
            text = replace_once(text, '} EnHorseNormal;',
                '    Vec3f spriteClonePos;\n    s16 spriteCloneYaw;\n    u8 spriteCloneEnabled;\n} EnHorseNormal;')
        return text
    if rel not in SOURCES:
        return text
    child = rel == SOURCES[0]
    prefix = 'EnHorseLinkChild' if child else 'EnHorseNormal'
    text = text.replace('Skin_Init(', 'RanchSprite_Init(').replace('Skin_Free(', 'RanchSprite_Free(')
    text = text.replace('ActorShadow_DrawHorse', 'ActorShadow_DrawCircle')
    text = replace_body(text, prefix + '_PostDraw', '    /* Head overlap runs in Update using a bounded source anchor. */')
    if child:
        text = replace_body(text, prefix + '_OverrideLimbDraw', '    return 1; /* Eyes are baked offline. */')
    else:
        # The source Draw also registers a second horse and its collision.
        # Retain the exact authored placements and audio events in Update.
        draw = text[text.index('void EnHorseNormal_Draw(Actor* thisx, PlayState* play2) {'):]
        placements = draw[draw.index('        if (play->sceneId == SCENE_STABLE) {'):
                          draw.index('        func_80A6CC88(play, this, &clonePos);')]
        helper = '''
void func_80A6CC88(PlayState* play, EnHorseNormal* this, Vec3f* arg2);
static void RanchSprite_Clone(EnHorseNormal* this, PlayState* play) {
    this->spriteCloneEnabled = this->action == HORSE_WAIT_CLONE;
    if (!this->spriteCloneEnabled) return;
    Vec3f clonePos = { 0.0f, 0.0f, 0.0f };
    s16 cloneRotY = 0;
''' + placements + '''
    this->spriteClonePos = clonePos;
    this->spriteCloneYaw = cloneRotY;
    this->cloneCollider.dim.pos.x = clonePos.x;
    this->cloneCollider.dim.pos.y = clonePos.y;
    this->cloneCollider.dim.pos.z = clonePos.z;
    CollisionCheck_SetOC(play, &play->colChkCtx, &this->cloneCollider.base);
    func_80A6CC88(play, this, &clonePos);
}
'''
        text = replace_once(text, 'void EnHorseNormal_Update(Actor* thisx, PlayState* play) {',
                            helper + '\nvoid EnHorseNormal_Update(Actor* thisx, PlayState* play) {')
        text = replace_once(text,
            '    SkinMatrix_Vec3fMtxFMultXYZW(&play->viewProjectionMtxF, arg2, &this->unk_1E8, &wDest);',
            '    /* Saturn audio consumes actor-relative positions, without a skin matrix. */\n'
            '    this->unk_1E8.x = arg2->x - GET_PLAYER(play)->actor.world.pos.x;\n'
            '    this->unk_1E8.y = arg2->y - GET_PLAYER(play)->actor.world.pos.y;\n'
            '    this->unk_1E8.z = arg2->z - GET_PLAYER(play)->actor.world.pos.z;')
        text = '#include "player.h"\n' + text
    text = replace_body(text, prefix + '_Draw', '    /* Offline sprite; source actions and contacts run in Update. */')
    extra = '' if child else '    func_80A6C8E0(this, play);\n    RanchSprite_Clone(this, play);\n'
    return append_update(text, prefix + '_Update', extra +
        f'    RanchSprite_Head(play, &this->actor, &this->skin.skelAnime, &this->headCollider, '
        f'this->animationIdx, {1 if child else 0});')


def timer_source(oot):
    """Extract the original main timer, including message/pause/cutscene gates.

    Retail draws drove this clock; the core calls it once per 20 Hz update.
    Subtimer/trade-spoil processing remains a separate migration requirement.
    """
    text = (oot / 'src/code/z_parameter.c').read_text(encoding='utf-8')
    start = text.index('void Interface_SetTimer(s16 seconds) {')
    setter = text[start:text.index('\n}', start) + 2]
    start = text.index('        if (!IS_PAUSED(&play->pauseCtx) && (play->gameOverCtx.state == GAMEOVER_INACTIVE) &&')
    end = text.index('                default: // TIMER_STATE_OFF', start)
    body = text[start:end] + '                default: break;\n            }\n        }'
    # Only the unused private sub-clock variables are omitted. Saved handoff
    # states/coordinates remain source-owned; no sub-timer is claimed here.
    body = body.replace('                        sSubTimerStateTimer = 20;\n', '')
    body = body.replace('                        sSubTimerNextSecondTimer = 20;\n', '')
    body = body.replace('sTimerDigits[4]', 'previousOnesDigit')
    return '''/* Generated from source z_parameter.c by ranch_sources.timer_source.
 * Source main timer only; called at the source 20 Hz cadence, never render FPS.
 */
#include "oot_prelude.h"
#include "play_state.h"
#include "player.h"
#include "save.h"
#include "sfx.h"
#include "audio.h"
#include "interface.h"
#include "attributes.h"
#include "oot_core_timer.h"
static s16 sEnvHazardActive;
static s16 sTimerStateTimer;
static s16 sTimerNextSecondTimer;
''' + setter + '''

void OotCore_UpdateRouteTimer(PlayState* play) {
    MessageContext* msgCtx = &play->msgCtx;
    Player* player = GET_PLAYER(play);
    s16 svar1;
    s16 timerId;
    s16 previousOnesDigit = gSaveContext.timerSeconds % 10;
''' + body + '''
}

void OotCore_TimerView(OotCoreTimerView* out) {
    if (!out) return;
    out->state = gSaveContext.timerState;
    out->reserved = 0;
    out->seconds = gSaveContext.timerSeconds;
    out->x = gSaveContext.timerX[TIMER_ID_MAIN];
    out->y = gSaveContext.timerY[TIMER_ID_MAIN];
}
'''
