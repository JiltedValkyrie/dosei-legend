"""Water Temple source inventory. Admission waits for complete pack validation."""
import re
from field_enemy_sources import replace_body, replace_once

PROPS = (
    'Bg_Mizu_Water', 'Bg_Mizu_Movebg', 'Bg_Mizu_Bwall', 'Bg_Mizu_Shutter', 'Bg_Mizu_Uzu',
    'Obj_Switch', 'Obj_Hsblock', 'Obj_Blockstop', 'Obj_Roomtimer',
    'En_Siofuki', 'En_Stream', 'En_Trap', 'En_Goroiwa',
    'Obj_Oshihiki', 'Obj_Makeoshihiki', 'Obj_Timeblock', 'Obj_Ice_Poly',
    'En_Box', 'Door_Shutter', 'En_Holl', 'En_Okarina_Tag',
)
ENEMIES = ('En_Firefly', 'En_Ny', 'En_Rr', 'En_Sb', 'En_Tite', 'En_Weiyer', 'En_Torch2')
SUPPORT = ('En_Sw', 'En_Si', 'En_Ru2', 'En_Kakasi2', 'En_Blkobj', 'Elf_Msg', 'Elf_Msg2', 'En_River_Sound')
PROP_SOURCES = [f'src/overlays/actors/ovl_{name}/z_{name.lower()}.c' for name in PROPS]
ENEMY_SOURCES = [f'src/overlays/actors/ovl_{name}/z_{name.lower()}.c' for name in ENEMIES]
SUPPORT_SOURCES = [f'src/overlays/actors/ovl_{name}/z_{name.lower()}.c' for name in SUPPORT]
SOURCE_SCENE = 5
RUNTIME_SCENE = 79
PACK_NAME = 'Z27'

# Conversion is staged separately from actor admission. Draw-owned contacts,
# timers and effects move to Update; sprite views read only source state.
SPRITE_ACTORS = ('En_Sb', 'En_Weiyer', 'En_Tite', 'En_Firefly', 'En_Ny')
SPRITE_OBJECTS = ('object_sb', 'object_ei', 'object_tite', 'object_firefly', 'object_ny')
SPRITE_SOURCES = [f'src/overlays/actors/ovl_{name}/z_{name.lower()}.c' for name in SPRITE_ACTORS]
# Skeleton-less objects: (key skeleton DL, key animation DL, per-variant DLs).
# Spikes variants follow EnNy_Draw: rock, metal, metal with spikes out.
STATIC_SPRITES = {
    'object_ny': ('gEnNyRockBodyDL', 'gEnNySpikeDL',
                  (('gEnNyRockBodyDL',), ('gEnNyMetalBodyDL',), ('gEnNyMetalBodyDL', 'gEnNySpikeDL'))),
}


def adapt(rel, text):
    if any(rel == path[:-2] + '.h' for path in SPRITE_SOURCES):
        return re.sub(r'Vec3s (jointTable|morphTable)\[[^\]]+\];', r'Vec3s* \1;', text)
    if rel not in SPRITE_SOURCES:
        return text
    text = '#include "water_enemy_sprite.h"\n' + text
    text = text.replace('SkelAnime_InitFlex(', 'OotCore_SpriteInitFlex(')
    text = text.replace('SkelAnime_Init(', 'OotCore_SpriteInit(')
    if rel.endswith('z_en_ny.c'):
        # Contact sphere and source fire timing leave Draw for Update. Both
        # draw states keep their own source fire cadence and filter timer.
        def tail(func):
            start = text.index('    if (this->unk_1CA != 0) {', text.index(func))
            return text[start:text.index('\n}', start)]
        alive = tail('void EnNy_Draw(Actor* thisx, PlayState* play) {')
        dying = tail('void EnNy_DrawDeathEffect(Actor* thisx, PlayState* play) {')
        start = text.index('static Vec3f sFireOffsets[] = {')
        offsets = text[start:text.index('};\n', start) + 3]
        text = text.replace(offsets, '')
        helper = (offsets + '\nstatic void EnNy_SpriteEffects(EnNy* this, PlayState* play) {\n'
                  '    WaterSprite_Spikes(this);\n'
                  '    if (this->actor.draw == EnNy_DrawDeathEffect) {\n' + dying + '\n        return;\n    }\n'
                  + alive + '\n}\n\n')
        for marker in ('void EnNy_Update(Actor* thisx, PlayState* play) {',
                       'void EnNy_UpdateDeath(Actor* thisx, PlayState* play) {'):
            if marker == 'void EnNy_Update(Actor* thisx, PlayState* play) {':
                text = replace_once(text, marker, helper + marker)
            start = text.index(marker)
            end = text.index('\n}', start)
            text = text[:end] + '\n    EnNy_SpriteEffects(this, play);' + text[end:]
        # The death branch returns early from Update; run it before leaving.
        text = replace_once(text, '        this->actionFunc = EnNy_SetupDie;\n        return;',
                            '        this->actionFunc = EnNy_SetupDie;\n        EnNy_SpriteEffects(this, play);\n        return;')
        text = replace_body(text, 'EnNy_Draw', '    /* Offline sprite; contacts and fire timing are in Update. */')
        return replace_body(text, 'EnNy_DrawDeathEffect',
                            '    /* Rock fragments not drawn; source death/drop timing is unchanged. */')
    if rel.endswith('z_en_weiyer.c'):
        text = replace_body(text, 'EnWeiyer_Draw', '    /* Baked source clips; cylinder stays in Update. */')
        return replace_body(text, 'EnWeiyer_OverrideLimbDraw', '    return false;')
    if rel.endswith('z_en_firefly.c'):
        # Keep source elemental effects and freeze anchors; replace only the
        # limb matrix reads with offline point samples. Three semantic anchors
        # are updated explicitly, never a runtime skeleton/pose traversal.
        text = text.replace('MtxF mf;', 'Vec3f anchor;')
        text = replace_once(text, '                Matrix_Get(&mf);',
                            '                anchor = WaterSprite_KeeseAnchor(this, limbIndex);')
        text = text.replace('mf.xw', 'anchor.x').replace('mf.yw', 'anchor.y').replace('mf.zw', 'anchor.z')
        text = replace_once(text, '        Matrix_MultVec3f(&D_80A14FC8, bodyPartPos);',
                            '        *bodyPartPos = WaterSprite_KeeseAnchor(this, limbIndex);')
        text = replace_once(text, '        gSPDisplayList((*gfx)++, gKeeseEyesDL);',
                            '        /* Eyes are part of the offline normal-body sprite. */')
        text = replace_body(text, 'EnFirefly_OverrideLimbDraw', '    return false;')
        for name in ('EnFirefly_DrawOpa', 'EnFirefly_DrawXlu'):
            text = replace_body(text, name, '    /* Offline sprite; source lens gate is in the view. */')
        declaration = 'void EnFirefly_PostLimbDraw(PlayState*, s32, Gfx**, Vec3s*, void*, Gfx**);\n'
        text = text.replace('void EnFirefly_Update(Actor* thisx, PlayState* play2) {',
                            declaration + 'void EnFirefly_Update(Actor* thisx, PlayState* play2) {')
        start = text.index('void EnFirefly_Update(Actor* thisx, PlayState* play2) {')
        end = text.index('\n}', start)
        text = text[:end] + '\n' + '\n'.join(
            f'    EnFirefly_PostLimbDraw(play, {limb}, NULL, NULL, this, NULL);'
            for limb in ('KEESE_LIMB_LEFT_WING_END', 'KEESE_LIMB_RIGHT_WING_END_ROOT', 'KEESE_LIMB_BODY')) + text[end:]
        return text
    text = text.replace('BodyBreak_Alloc(', 'FieldSprite_BreakStart(')
    text = text.replace('BodyBreak_SpawnParts(', 'FieldSprite_BreakStep(')
    if rel.endswith('z_en_tite.c'):
        text = replace_body(text, 'EnTite_PostLimbDraw', '    /* Offline feet; bounded source death completion. */')
        start = text.index('    if (this->spawnIceTimer != 0) {', text.index('void EnTite_Draw(Actor* thisx, PlayState* play) {'))
        effects = text[start:text.index('\n}', start)]
        marker = 'void EnTite_Update(Actor* thisx, PlayState* play) {'
        helper = ('static void EnTite_SpriteEffects(EnTite* this, PlayState* play) {\n'
                  '    Actor* thisx = &this->actor;\n' + effects + '\n}\n\n')
        text = replace_once(text, marker, helper + marker)
        text = replace_once(text, '        // If on water, snap feet to surface and spawn ripples',
                            '        WaterSprite_Tektite(this);\n        // If on water, snap feet to surface and spawn ripples')
        end = text.index('\n}', text.index(marker))
        text = text[:end] + '\n    WaterSprite_Tektite(this);\n    EnTite_SpriteEffects(this, play);' + text[end:]
        return replace_body(text, 'EnTite_Draw', '    /* Offline sprite; contacts and ice timing are in Update. */')
    text = replace_body(text, 'EnSb_PostLimbDraw', '    /* Two update ticks complete source death/drop readiness. */')
    # Preserve even the source fire-timer quirk, but advance it in the update
    # phase so camera culling never controls status timing or source effects.
    start = text.index('    if (this->fire != 0) {', text.index('void EnSb_Draw(Actor* thisx, PlayState* play) {'))
    effects = text[start:text.index('\n}', start)]
    marker = 'void EnSb_Update(Actor* thisx, PlayState* play) {'
    helper = ('static void EnSb_SpriteEffects(EnSb* this, PlayState* play) {\n'
              '    Vec3f flamePos;\n    Vec3f* offset;\n    s16 fireDecr;\n' + effects + '\n}\n\n')
    text = replace_once(text, marker, helper + marker)
    update_start = text.index(marker)
    update_end = text.index('\n}', update_start)
    text = text[:update_end] + '\n    EnSb_SpriteEffects(this, play);' + text[update_end:]
    return replace_body(text, 'EnSb_Draw', '    /* Offline sprite; source status/effects run in Update. */')
