"""Source mountain/city props, triggers and falling-rock sprite adapters."""
from field_enemy_sources import replace_body, replace_once

ACTORS = ('Bg_Spot18_Basket', 'Bg_Spot18_Futa', 'Bg_Spot18_Obj', 'Bg_Spot18_Shutter',
          'Obj_Hamishi', 'Obj_Kibako2', 'En_Okarina_Tag', 'Bg_Spot16_Bombstone',
          'Bg_Bombwall', 'Bg_Spot16_Doughnut', 'En_Encount2', 'En_Fire_Rock',
          'En_Goroiwa', 'Door_Ana', 'En_River_Sound', 'Obj_Makekinsuta', 'Obj_Bean')
SOURCES = tuple('src/overlays/actors/ovl_%s/z_%s.c' % (n, n.lower()) for n in ACTORS)
OBJECTS = ('gameplay_field_keep', 'object_spot18_obj', 'object_kibako2', 'object_spot16_obj',
           'object_efc_doughnut', 'object_efc_star_field', 'object_goroiwa', 'object_mamenoki')
SPRITE_OBJECTS = ('object_efc_star_field',)
NO_MESH = {'En_Okarina_Tag', 'En_Encount2', 'En_Fire_Rock', 'En_River_Sound', 'Obj_Makekinsuta'}
DRAW_SOURCES = [('ACTOR_' + n.upper(), s) for n, s in zip(ACTORS, SOURCES) if n not in NO_MESH]
NPC_SOURCES = [('ACTOR_EN_FIRE_ROCK', SOURCES[ACTORS.index('En_Fire_Rock')])]
STATIC_SPRITES = {'object_efc_star_field': ('object_efc_star_field_DL_000DE0',
                 'object_efc_star_field_DL_000DE0', (('object_efc_star_field_DL_000DE0',),))}
OKARINA_SCRIPTS = ('gWindmillSpinningFasterCs', 'gDoorOfTimeOpeningCs')


def check_okarina_pack(scene_c, actors):
    """Fail the import if a pack scene spawns a script-owning tag type."""
    import re
    if 'En_Okarina_Tag' not in actors:
        return
    for inc in scene_c.parent.glob('*ActorEntryList.inc.c'):
        text = re.sub(r'//[^\n]*|/\*.*?\*/', '', inc.read_text(encoding='utf-8'), flags=re.S)
        for row in re.findall(r'\{\s*ACTOR_EN_OKARINA_TAG,.*?\n\s*\}', text, re.S):
            params = int(re.search(r'([^,{}]+),\s*\}$', row)[1].strip(), 0)
            if (params >> 10) & 0x3F in (2, 4):
                raise ValueError(f'{scene_c.name}: En_Okarina_Tag type needs actor cutscene data')


def adapt(rel, text):
    if rel not in SOURCES:
        return text
    if rel.endswith('z_obj_hamishi.c'):
        text = replace_once(text, 'Rand_ZeroFloat(65536.0f)', '(s32)(Rand_ZeroFloat(32767.0f)) * 2')
    elif rel.endswith('z_obj_bean.c'):
        old = '(s16)(this->stalkSizeMultiplier * 700000.0f)'
        if text.count(old) != 2:
            raise ValueError('Source bean stalk angle changed')
        text = text.replace(old, '(s16)((s32)(this->stalkSizeMultiplier * 10000.0f) * 70)')
    elif rel.endswith('z_en_fire_rock.c'):
        text = replace_body(text, 'EnFireRock_Draw', '    /* Offline falling-rock sprite; source collision stays in Update. */')
    elif rel.endswith('z_en_encount2.c'):
        text = replace_body(text, 'EnEncount2_DrawEffects', '    /* Native weather particle records exported by EffectView. */')
        text = replace_body(text, 'EnEncount2_Draw', '    /* Weather snapshot; no runtime particle mesh. */')
    elif rel.endswith('z_en_okarina_tag.c'):
        # Types 2/4 use actor-local windmill/Door of Time scripts. Those
        # scenes do not admit this actor; check_okarina_pack proves no pack
        # spawns them, so the unreachable references stay weak.
        for name in OKARINA_SCRIPTS:
            text = replace_once(text, 'extern CutsceneData %s[];' % name,
                                'extern CutsceneData %s[] __attribute__((weak));' % name)
    elif rel.endswith('z_en_river_sound.c'):
        # Source audio-only Draw never reaches the mesh shim. Advance its
        # complete source switch after the original position/path Update.
        text = text.replace('void EnRiverSound_Draw(Actor* thisx, PlayState* play)',
                            'void EnRiverSound_SaturnAudio(Actor* thisx, PlayState* play)')
        text = replace_once(text, '/**/ EnRiverSound_Draw,', '/**/ NULL,')
        marker = 'void EnRiverSound_Update(Actor* thisx, PlayState* play) {'
        start = text.index(marker)
        end = text.index('\n}', start)
        text = text[:end] + '\n    if (thisx->update != NULL) EnRiverSound_SaturnAudio(thisx, play);' + text[end:]
    return text
