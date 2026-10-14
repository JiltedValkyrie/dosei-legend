"""King Dodongo source adaptation; boss remains gated on complete pack closure.

The real skeleton, limb callback, nineteen spheres, bomb mouth, damage and
cutscene actions stay intact. Only N64 framebuffer texture mutation becomes a
small presentation snapshot consumed by the Saturn room-palette adapter.
"""
import re
from field_enemy_sources import replace_once, replace_body

BOSS_SOURCE = 'src/overlays/actors/ovl_Boss_Dodongo/z_boss_dodongo.c'
BOSS_HEADER = BOSS_SOURCE[:-2] + '.h'
BOSS_DATA = 'src/overlays/actors/ovl_Boss_Dodongo/z_boss_dodongo_data.inc.c'
SUPPORT_ACTORS = ('En_Bdfire', 'Door_Warp1', 'Item_B_Heart')
SUPPORT_SOURCES = tuple('src/overlays/actors/ovl_%s/z_%s.c' % (name, name.lower())
                        for name in SUPPORT_ACTORS)
EFFECTS = ('G_Magma', 'G_Magma2')
EFFECT_SOURCES = tuple('src/overlays/effects/ovl_Effect_Ss_%s/z_eff_ss_%s.c' % (name, name.lower())
                      for name in EFFECTS)
REWARD_OBJECTS = ('OBJECT_WARP1', 'OBJECT_GI_HEARTS')


def adapt(rel, text):
    if rel in EFFECT_SOURCES:
        for name in re.findall(r'^void (EffectSs\w+_Draw)\([^;{}]*\) \{', text, re.M):
            text = replace_body(text, name, '    /* Original update; bounded Saturn effect snapshot. */')
        return text
    if rel == SUPPORT_SOURCES[0]:
        for name in ('EnBdfire_DrawFire', 'EnBdfire_Draw'):
            text = replace_body(text, name, '    /* Eight original fire frames in a baked sprite. */')
        return text
    if rel == SUPPORT_SOURCES[1]:
        marker = 'void DoorWarp1_DrawWarp(DoorWarp1* this, PlayState* play) {'
        helper = '''/* Canonical portal retains the source two-ring height. The baked
 * bottom follows the top width; source trigger/reward timing stays intact. */
static void DoorWarp1_SaturnPortal(DoorWarp1* this, PlayState* play, f32 height) {
    OPEN_DISPS(play->state.gfxCtx, __FILE__, __LINE__);
    Matrix_Push();
    Matrix_Translate(0.0f, -height, 0.0f, MTXMODE_APPLY);
    Matrix_Scale(1.0f, height / 230.0f, 1.0f, MTXMODE_APPLY);
    MATRIX_FINALIZE_AND_LOAD(POLY_XLU_DISP++, play->state.gfxCtx, __FILE__, __LINE__);
    gSPDisplayList(POLY_XLU_DISP++, gWarpPortalDL);
    Matrix_Pop();
    CLOSE_DISPS(play->state.gfxCtx, __FILE__, __LINE__);
}

'''
        text = replace_once(text, marker, helper + marker)
        definition = text.index(marker)
        prefix, body = text[:definition], text[definition:]
        draw = 'gSPDisplayList(POLY_XLU_DISP++, gWarpPortalDL);'
        if body.count(draw) != 2:
            raise ValueError('Source portal layer count changed')
        body = body.replace(draw, 'DoorWarp1_SaturnPortal(this, play, this->unk_194 * 230.0f);', 1)
        body = body.replace(draw, 'DoorWarp1_SaturnPortal(this, play, this->unk_198 * 60.0f);', 1)
        return prefix + body
    if rel == BOSS_HEADER:
        return replace_once(text, '} BossDodongo;',
                            '    /* Saturn presentation only; 0 lava, 256 cooled rock. */\n'
                            '    u16 saturnLavaPhase;\n} BossDodongo;')
    if rel != BOSS_SOURCE:
        return text
    # The N64 overlay advertises the ordinary Dodongo id. N64 dispatch uses
    # its loaded function pointers; Saturn's sprite/model views also use id.
    # Give the boss its actual actor-table identity to avoid a sprite cast.
    text = replace_once(text, 'ActorProfile Boss_Dodongo_Profile = {\n    /**/ ACTOR_EN_DODONGO,',
                        'ActorProfile Boss_Dodongo_Profile = {\n    /**/ ACTOR_BOSS_DODONGO,')
    for name in ('sLavaFloorLavaTex', 'sLavaFloorRockTex'):
        pattern = (r'#define ' + name + r'_WIDTH[^\n]*\n#define ' + name +
                   r'_HEIGHT[^\n]*\nstatic u64 ' + name + r'\[[^\n]*\n.*?\n};\n')
        text, count = re.subn(pattern, '', text, count=1, flags=re.S)
        if count != 1:
            raise ValueError(f'Boss texture definition changed: {name}')
    # The source's texture resampler cannot target a stripped N64 texture
    # placeholder. It has no gameplay effect and no remaining caller.
    match = re.search(r'^void func_808C1554\([^;{}]*\) \{', text, re.M)
    if not match:
        raise ValueError('Boss texture resampler moved')
    end = text.index('\n}', match.end()) + 2
    text = text[:match.start()] + text[end:]
    text = replace_once(text, '    play->specialEffects = this->effects;',
                        '    this->saturnLavaPhase = 0;\n    play->specialEffects = this->effects;')
    text = replace_once(text,
                        '        u16* temp_s1_3 = SEGMENTED_TO_VIRTUAL(gDodongosCavernBossLavaFloorTex);\n'
                        '        u16* temp_s2 = SEGMENTED_TO_VIRTUAL(sLavaFloorRockTex);\n'
                        '        u32 temp_v0;\n',
                        '        this->saturnLavaPhase = 256;\n')
    text = replace_once(text,
                        '        for (i = 0; i < 2048; i++) {\n'
                        '            temp_v0 = i;\n'
                        '            temp_s1_3[temp_v0] = temp_s2[temp_v0];\n'
                        '        }\n', '')
    text = replace_once(text,
                        '        func_808C1554((u16*)gDodongosCavernBossLavaFloorTex, '
                        '(u16*)sLavaFloorLavaTex, this->unk_19E, this->unk_224);',
                        '        /* Room lava is already resident in Saturn VDP1. */')
    text = replace_once(text,
                        '        u16* ptr1 = SEGMENTED_TO_VIRTUAL(sLavaFloorLavaTex);\n'
                        '        u16* ptr2 = SEGMENTED_TO_VIRTUAL(sLavaFloorRockTex);\n'
                        '        s16 i2;\n'
                        '        s16 new_var;\n\n'
                        '        for (i2 = 0; i2 < 20; i2++) {\n'
                        '            new_var = this->unk_1C2 & 0x7FF;\n\n'
                        '            ptr1[new_var] = ptr2[new_var];\n'
                        '            this->unk_1C2 += 37;\n'
                        '        }\n'
                        '        Math_SmoothStepToF(&this->unk_224, 0.0f, 1.0f, 0.01f, 0.0f);',
                        '        Math_SmoothStepToF(&this->unk_224, 0.0f, 1.0f, 0.01f, 0.0f);\n'
                        '        this->saturnLavaPhase = (u16)(s32)((2.0f - this->unk_224) * 128.0f);\n'
                        '        if (this->saturnLavaPhase > 256) this->saturnLavaPhase = 256;')
    text = replace_once(text,
                        '    Matrix_RotateX((this->unk_1C4 / 32768.0f) * 3.14159f, MTXMODE_APPLY);',
                        '    Matrix_RotateZYX(this->unk_1C4, 0, 0, MTXMODE_APPLY);')
    text = replace_body(text, 'BossDodongo_DrawEffects', '    /* Source particle snapshot. */')
    return text
