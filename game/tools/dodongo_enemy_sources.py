"""Dodongo route actors: source gameplay with an offline sprite presentation.

No actor is admitted by this module alone. Scene packs, complete sprite archives
and their memory checks remain the admission boundary. Draw-owned contacts and
status clocks move to Update; original action/drop/shop/paired-enemy code stays.
"""
import re

from field_enemy_sources import replace_body, replace_once

SPRITE_ACTORS = ('En_Dodojr', 'En_Dodongo', 'En_Am', 'En_Zf',
                 'En_Shopnuts', 'En_Dns', 'En_Kakasi2', 'En_Nutsball', 'En_Vm', 'En_Sw', 'En_Si',
                 'En_Wf', 'En_Dekunuts')
SPRITE_OBJECTS = ('object_dodojr', 'object_dodongo', 'object_am', 'object_zf',
                  'object_shopnuts', 'object_ka', 'object_vm', 'object_st', 'object_wf', 'object_dekunuts')
SPRITE_SOURCES = tuple(f'src/overlays/actors/ovl_{n}/z_{n.lower()}.c'
                       for n in SPRITE_ACTORS)
# Boss/reward closure is maintained by dodongo_boss_sources.py.
STATIC_SPRITES = {
    'object_dekunuts': ('gDekuNutsDekuNutDL', 'gDekuNutsDekuNutDL', (('gDekuNutsDekuNutDL',),)),
    'object_st': ('gSkulltulaTokenDL', 'gSkulltulaTokenDL', (('gSkulltulaTokenDL',),)),
    # Child-route shop scrubs spawn NUTSBALL_TYPE_SHOPNUTS (2). Other source
    # nut types need their own archive before admitting their parent actors.
    'object_shopnuts': ('gBusinessScrubDekuNutDL', 'gBusinessScrubDekuNutDL',
                       (('gBusinessScrubDekuNutDL',),)),
}


def _end_update(text, name, code):
    start = text.index(f'void {name}(')
    # Prototypes occur before the source definition.
    start = re.search(r'^void ' + name + r'\([^;{}]*\) \{', text, re.M).end()
    end = text.index('\n}', start)
    return text[:end] + '\n' + code + text[end:]


def _status_helper(text, draw, marker, helper, declaration='', guard=''):
    """Move an intact source status block out of Draw, keeping its timing."""
    start = text.index(marker, text.index('void ' + draw + '('))
    # Find the definition if the first draw occurrence was a prototype.
    definition = re.search(r'^void ' + draw + r'\([^;{}]*\) \{', text, re.M)
    start = text.index(marker, definition.end())
    brace = text.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    body = text[start:end]
    return declaration + f'\nstatic void {helper} {{\n' + guard + body + '\n}\n\n'


def adapt(rel, text):
    if any(rel == p[:-2] + '.h' for p in SPRITE_SOURCES):
        return re.sub(r'Vec3s (jointTable|morphTable)\[[^\]]+\];', r'Vec3s* \1;', text)
    if rel not in SPRITE_SOURCES:
        return text
    text = '#include "dodongo_enemy_sprite.h"\n' + text
    text = text.replace('SkelAnime_InitFlex(', 'OotCore_SpriteInitFlex(')
    text = text.replace('SkelAnime_Init(', 'OotCore_SpriteInit(')
    if rel.endswith('z_en_wf.c'):
        fire = _status_helper(text, 'EnWf_Draw', '        if (this->fireTimer != 0)',
                              'EnWf_SpriteFire(EnWf* this, PlayState* play)')
        for name in ('EnWf_Draw', 'EnWf_PostLimbDraw'):
            text = replace_body(text, name, '    /* Baked sprite; contacts and burn clock run in Update. */')
        text = replace_body(text, 'EnWf_OverrideLimbDraw', '    return false;')
        text = replace_once(text, '    EnWf_UpdateDamage(this, play);',
                            '    DodongoSprite_Wolfos(this);\n    EnWf_UpdateDamage(this, play);')
        text = _end_update(text, 'EnWf_Update', '    EnWf_SpriteFire(this, play);')
        at = text.index('void EnWf_Update(Actor* thisx, PlayState* play) {')
        return text[:at] + fire + text[at:]
    if rel.endswith('z_en_dekunuts.c'):
        text = replace_once(text, '        thisx->flags &= ~(ACTOR_FLAG_ATTENTION_ENABLED | ACTOR_FLAG_HOSTILE);',
                            '        thisx->flags &= ~(ACTOR_FLAG_ATTENTION_ENABLED | ACTOR_FLAG_HOSTILE);\n'
                            '        this->skelAnime.skeleton = (void**)&gDekuNutsSkel;\n'
                            '        this->skelAnime.animation = (AnimationHeader*)gDekuNutsFlowerDL;')
        text = replace_body(text, 'EnDekunuts_Draw', '    /* Baked enemy or flower sprite. */')
        return replace_body(text, 'EnDekunuts_OverrideLimbDraw', '    return false;')
    if rel.endswith('z_en_vm.c'):
        text = replace_body(text, 'EnVm_OverrideLimbDraw', '    return false;')
        for name in ('EnVm_PostLimbDraw', 'EnVm_Draw'):
            text = replace_body(text, name, '    /* Beam/eye contacts run in Update; baked body sprite. */')
        return _end_update(text, 'EnVm_Update', '    DodongoSprite_Beamos(this, play);')
    if rel.endswith('z_en_sw.c'):
        text = text.replace('(Rand_ZeroOne() - 0.5f) * 65536.0f', 'OotRand_CenteredTimes(65536)')
        text = replace_once(text,
                            '            sp2C = 32768.0f / this->skelAnime.endFrame;\n'
                            '            sp2C *= this->skelAnime.curFrame;\n'
                            '            sp2C = Math_SinS(sp2C) * this->unk_420;',
                            '            s32 phase = (s32)((this->skelAnime.curFrame / this->skelAnime.endFrame) * 16384) * 2;\n'
                            '            sp2C = Math_SinS((s16)phase) * this->unk_420;')
        text = replace_body(text, 'EnSw_OverrideLimbDraw', '    return false;')
        text = replace_body(text, 'EnSw_Draw', '    /* Baked normal/gold body; source surface traversal retained. */')
        # Source damage/action consumes last tick contacts, then publishes the
        # next contact positions before collision registration. No draw gate.
        return replace_once(text, '    func_80B0CBE8(this, play);',
                            '    DodongoSprite_Skulltula(this);\n    func_80B0CBE8(this, play);')
    if rel.endswith('z_en_si.c'):
        text = replace_body(text, 'EnSi_Draw', '    /* Baked source token, including hookshot pickup. */')
        return _end_update(text, 'EnSi_Update',
                           '    if (this->actionFunc == func_80AFB950) this->actor.draw = NULL;')
    if rel.endswith('z_en_dodojr.c'):
        # Sentinel exceeds the entire scene; random binang stays a scalar s16.
        text = text.replace('99999.0f', '32767.0f')
        text = text.replace('((Rand_ZeroOne() - 0.5f) * 65536.0f)', 'OotRand_CenteredTimes(65536)')
        text = replace_body(text, 'EnDodojr_OverrideLimbDraw', '    return false;')
        text = replace_body(text, 'EnDodojr_PostLimbDraw', '    /* Offline semantic head point. */')
        text = replace_body(text, 'EnDodojr_Draw', '    /* Baked sprite; visibility follows source action. */')
        return _end_update(text, 'EnDodojr_Update', '''    DodongoSprite_Baby(this);
    if (this->actor.update != NULL) {
        this->actor.draw = (this->actionFunc == EnDodojr_WaitUnderground ||
                            this->actionFunc == EnDodojr_DropItem) ? NULL : EnDodojr_Draw;
    }''')
    if rel.endswith('z_en_dodongo.c'):
        helper = _status_helper(text, 'EnDodongo_Draw', '    if (this->iceTimer != 0) {',
                                'EnDodongo_SpriteIce(EnDodongo* this, PlayState* play)',
                                guard='    s32 index;\n')
        text = replace_once(text, 'void EnDodongo_Update(Actor* thisx, PlayState* play) {',
                            helper + 'void EnDodongo_Update(Actor* thisx, PlayState* play) {')
        text = replace_once(text, '    CollisionCheck_SetOC(play, &play->colChkCtx, &this->bodyCollider.base);',
                            '    DodongoSprite_Dodongo(this);\n'
                            '    CollisionCheck_SetOC(play, &play->colChkCtx, &this->bodyCollider.base);')
        text = _end_update(text, 'EnDodongo_Update', '    EnDodongo_SpriteIce(this, play);')
        for name in ('EnDodongo_UpdateQuad', 'EnDodongo_PostLimbDraw', 'EnDodongo_Draw'):
            text = replace_body(text, name, '    /* Offline contacts and status clocks run in Update. */')
        return replace_body(text, 'EnDodongo_OverrideLimbDraw', '    return false;')
    if rel.endswith('z_en_am.c'):
        offsets_start = text.index('static Vec3f sIcePosOffsets[] = {')
        offsets_end = text.index('};', offsets_start) + 2
        offsets = text[offsets_start:offsets_end]
        text = text[:offsets_start] + text[offsets_end:]
        helper = _status_helper(text, 'EnAm_Draw', '    if (this->iceTimer != 0) {',
                                'EnAm_SpriteIce(EnAm* this, PlayState* play)', offsets,
                                '    Vec3f sp68;\n    s32 index;\n')
        text = replace_once(text, 'void EnAm_Update(Actor* thisx, PlayState* play) {',
                            helper + 'void EnAm_Update(Actor* thisx, PlayState* play) {')
        text = replace_once(text, '    Collider_UpdateCylinder(&this->dyna.actor, &this->hurtCollider);',
                            '    DodongoSprite_Armos(this);\n'
                            '    Collider_UpdateCylinder(&this->dyna.actor, &this->hurtCollider);')
        text = _end_update(text, 'EnAm_Update', '    EnAm_SpriteIce(this, play);')
        for name in ('EnAm_TransformSwordHitbox', 'EnAm_PostLimbDraw', 'EnAm_Draw'):
            text = replace_body(text, name, '    /* Offline sword points; source ice clock runs in Update. */')
        return text
    if rel.endswith('z_en_zf.c'):
        # Platform candidates are at most 585 units apart. Preserve ordering
        # of the two "no platform yet" sentinels within fixed-point range.
        text = text.replace('99998.0f', '32766.0f').replace('99999.0f', '32767.0f')
        helper = _status_helper(text, 'EnZf_Draw', '        if (this->frozenTimer != 0) {',
                                'EnZf_SpriteIce(EnZf* this, PlayState* play)',
                                guard='    Actor* thisx = &this->actor;\n'
                                      '    s32 bodyPartIndex;\n    if (this->alpha != 255) return;\n')
        text = replace_once(text, 'void EnZf_Update(Actor* thisx, PlayState* play) {',
                            helper + 'void EnZf_Update(Actor* thisx, PlayState* play) {')
        text = replace_once(text, '    if ((this->action == ENZF_ACTION_ATTACK) && ((this->skelAnime.curFrame >= 14.0f)) &&',
                            '    DodongoSprite_Lizalfos(this);\n'
                            '    if ((this->action == ENZF_ACTION_ATTACK) && ((this->skelAnime.curFrame >= 14.0f)) &&')
        text = _end_update(text, 'EnZf_Update', '    EnZf_SpriteIce(this, play);')
        # Source's head bearing participates in its idle reaction predicate.
        # Preserve that gameplay scalar; no renderer consumes it or evaluates
        # a head/torso joint. Override itself performs no head tracking.
        text = replace_body(text, 'EnZf_OverrideLimbDraw', '    return false;')
        for name in ('EnZf_PostLimbDraw', 'EnZf_Draw'):
            text = replace_body(text, name, '    /* Offline sword/feet/ice points; source clocks run in Update. */')
        return text
    if rel.endswith('z_en_shopnuts.c'):
        text = replace_body(text, 'EnShopnuts_OverrideLimbDraw', '    return false;')
        for name in ('EnShopnuts_PostLimbDraw', 'EnShopnuts_Draw'):
            text = replace_body(text, name, '    /* Offline sprite; source shot/spawn/collider code is unchanged. */')
        return text
    if rel.endswith('z_en_dns.c'):
        return replace_body(text, 'EnDns_Draw', '    /* Offline sprite; source purchase and reward transactions stay. */')
    if rel.endswith('z_en_nutsball.c'):
        return replace_body(text, 'EnNutsball_Draw', '    /* Baked projectile; source shield reflection and contacts stay. */')
    return replace_body(text, 'func_80A90948', '    /* Offline scarecrow sprite; source song/hook target stays. */')
