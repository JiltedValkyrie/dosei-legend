"""Hyrule Field source actors and explicit sprite-backend substitutions.

These actors belong to a scene pack, never the resident SOURCES list.
Original actions, damage tables, spawn conditions and rewards stay in source.
"""
import re

ACTORS = ('En_Encount1', 'En_Skb', 'En_Peehat', 'En_Po_Field')
SOURCES = [f'src/overlays/actors/ovl_{name}/z_{name.lower()}.c' for name in ACTORS]
OBJECTS = ('object_skb', 'object_peehat', 'object_po_field')
EFFECTS = ('Dust', 'Hahen', 'En_Fire', 'Dead_Db', 'Dead_Sound', 'HitMark')
EFFECT_SOURCES = [f'src/overlays/effects/ovl_Effect_Ss_{name}/z_eff_ss_{name.lower()}.c' for name in EFFECTS]


def replace_body(text, name, body):
    """Replace a top-level source definition; fail if the expected hook moved."""
    pattern = re.compile(r'^(?:void|s32|Gfx\*) ' + re.escape(name) + r'\([^;{}]*\) \{', re.M)
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ValueError(f'{name}: expected one source definition, found {len(matches)}')
    start = matches[0].end()
    end = text.index('\n}', start)
    return text[:start] + '\n' + body + text[end:]


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'Field source hook changed: {old[:100]}')
    return text.replace(old, new)


def adapt(rel, text):
    if rel in EFFECT_SOURCES:
        for name in re.findall(r'^void (EffectSs\w+_Draw\w*)\([^;{}]*\) \{', text, re.M):
            text = replace_body(text, name, '    /* Source update; Saturn particle presentation. */')
        return text
    if any(rel == path[:-2] + '.h' for path in SOURCES[1:]):
        return re.sub(r'Vec3s (jointTable|morphTable)\[\d+\];', r'Vec3s* \1;', text)
    if rel not in SOURCES:
        return text
    if rel.endswith('z_en_encount1.c'):
        return text
    text = '#include "field_enemy_sprite.h"\n' + text
    text = text.replace('SkelAnime_Init(', 'OotCore_SpriteInit(')
    if rel.endswith('z_en_skb.c'):
        for name in ('EnSkb_Draw', 'EnSkb_PostLimbDraw'):
            text = replace_body(text, name, '    /* Offline sprites; gameplay anchors run in Update. */')
        text = replace_body(text, 'EnSkb_OverrideLimbDraw', '    return false;')
        text = text.replace('BodyBreak_Alloc(', 'FieldSprite_BreakStart(')
        text = text.replace('BodyBreak_SpawnParts(', 'FieldSprite_BreakStep(')
        text = replace_once(text, '    if (this->setColliderAT) {',
                            '    FieldSprite_Stalchild(this);\n    if (this->setColliderAT) {')
    elif rel.endswith('z_en_peehat.c'):
        for name in ('EnPeehat_Draw', 'EnPeehat_PostLimbDraw'):
            text = replace_body(text, name, '    /* Offline sprites; gameplay anchors run in Update. */')
        text = replace_body(text, 'EnPeehat_OverrideLimbDraw', '    return false;')
        text = replace_once(text, '    // if PEAHAT_TYPE_GROUNDED\n    if (thisx->params < 0) {',
                            '    FieldSprite_Peahat(this);\n    // if PEAHAT_TYPE_GROUNDED\n    if (thisx->params < 0) {')
    else:
        for name in ('EnPoField_Draw', 'EnPoField_DrawSoul', 'EnPoField_DrawFlame', 'EnPoField_PostLimDraw2'):
            text = replace_body(text, name, '    /* Offline sprite presentation. */')
        text = replace_body(text, 'EnPoField_OverrideLimbDraw2', '    return false;')
        text = replace_once(text, '        func_80AD6330(this);\n        Collider_UpdateCylinder',
                            '        func_80AD6330(this);\n'
                            '        FieldSprite_Poe(this, this->actionFunc == EnPoField_Death && this->actionTimer == 27);\n'
                            '        Collider_UpdateCylinder')
        text = text.replace('static MtxF sLimb7Mtx;', '/* Lantern anchor replaces the draw matrix. */')
    return text
