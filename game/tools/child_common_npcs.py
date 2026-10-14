"""Child Market/Kakariko NPC actions with baked character presentation."""
import re
from field_enemy_sources import replace_body, replace_once
from child_route_npcs import append_update

ACTORS = ('En_Hy', 'En_Heishi4', 'En_Hs2', 'En_Ani', 'En_Tg', 'En_Toryo', 'En_Syateki_Niw', 'En_Guest')
SOURCES = [f'src/overlays/actors/ovl_{name}/z_{name.lower()}.c' for name in ACTORS]
HY_OBJECTS = ('object_aob', 'object_ahg', 'object_bob', 'object_boj', 'object_bba', 'object_bji', 'object_cne', 'object_cob')
OBJECTS = HY_OBJECTS + ('object_os_anime', 'object_sd', 'object_hs', 'object_ani', 'object_mu', 'object_toryo', 'object_niw')
NPC_SOURCES = [('ACTOR_' + name.upper(), source) for name, source in zip(ACTORS, SOURCES)]
# Actual child day/night rooms and guest house. Other actors retain their own
# pending admission; this list does not assert all content in a scene is done.
SOURCE_SCENES = ('market_day', 'market_night', 'market_alley', 'market_alley_n', 'entra', 'entra_n',
                 'miharigoya', 'kakariko', 'kakariko3')


def adapt(rel, text):
    if rel in [p[:-2] + '.h' for p in SOURCES]:
        return re.sub(r'Vec3s (jointTable|morphTable)\[[^\]]+\];', r'Vec3s* \1;', text)
    if rel not in SOURCES:
        return text
    text = '#include "child_route_npc_sprite.h"\n' + text
    text = text.replace('SkelAnime_InitFlex(', 'OotCore_SpriteInitFlex(').replace('SkelAnime_Init(', 'OotCore_SpriteInit(')
    text = text.replace('Npc_TrackPoint(', 'ChildRouteSprite_TrackBody(')
    text = re.sub(r'Actor_TrackPlayer\([^;]+;', '/* No head/torso pose tracking. */', text)
    text = re.sub(r'Actor_UpdateFidgetTables\([^;]+;', '/* Limb fidgets are baked offline. */', text)
    text = re.sub(r'Math_SmoothStepToS\(&this->(?:headRot|torsoRot|unk_29C|unk_2A2)\.[^;]+;',
                  '/* No head/torso pose interpolation. */', text)
    for name in re.findall(r'^void (\w*(?:Draw\w*|PostLimbDraw))\([^;{}]*\) \{', text, re.M):
        text = replace_body(text, name, '    /* Sprite presentation; original actions run in Update. */')
    for name in re.findall(r'^s32 (\w*OverrideLimbDraw)\([^;{}]*\) \{', text, re.M):
        text = replace_body(text, name, '    return 0; /* No runtime character pose. */')
    if rel.endswith('z_en_hy.c'):
        text = append_update(text, 'EnHy_Update', '    Actor_SetFocus(&this->actor, this->collider.dim.height);')
    elif rel.endswith('z_en_hs2.c'):
        text = append_update(text, 'EnHs2_Update', '    Actor_SetFocus(&this->actor, 45.0f);')
    elif rel.endswith('z_en_ani.c'):
        text = append_update(text, 'EnAni_Update', '    Actor_SetFocus(&this->actor, 55.0f);')
    elif rel.endswith('z_en_tg.c'):
        text = append_update(text, 'EnTg_Update', '    Actor_SetFocus(&this->actor, 55.0f);')
    elif rel.endswith('z_en_toryo.c'):
        text = append_update(text, 'EnToryo_Update', '    Actor_SetFocus(&this->actor, 60.0f);')
    elif rel.endswith('z_en_syateki_niw.c'):
        # Preserve source peck/flap timers and random calls; only their final
        # wing/head interpolation was a pose operation.
        text = re.sub(r'Math_ApproachF\(&this->(?:headRot|leftWingRot|rightWingRot)\.[^;]+;',
                      '/* Baked wing/head poses. */', text)
        text = append_update(text, 'EnSyatekiNiw_Update',
            '    this->actor.draw = this->actionFunc == EnSyatekiNiw_SetupRemove ? NULL : EnSyatekiNiw_Draw;')
    return text


def hy_recipes(oot):
    """Parse actual source model/head/color/initial-animation choices."""
    text = (oot / SOURCES[0]).read_text(encoding='utf-8')
    heads = dict((a, (b.lower(), c, d)) for a, b, c, d in re.findall(
        r'/\* (ENHY_HEAD_\w+) \*/ \{ (OBJECT_\w+), (\w+), (\w+) \}', text))
    skels = dict((a, (b.lower(), c)) for a, b, c in re.findall(
        r'/\* (ENHY_SKEL_\w+) \*/ \{ (OBJECT_\w+), &(\w+) \}', text))
    animations = dict((int(a), b) for a, b in re.findall(r'/\* ENHY_ANIM_(\d+) \*/ \{ &(\w+),', text))
    section = re.search(r'sModelInfo\[\] = \{(.*?)\n\};', text, re.S)[1]
    pattern = (r'/\* (ENHY_TYPE_\w+) \*/\s*\{\s*(ENHY_HEAD_\w+),\s*(ENHY_SKEL_\w+),\s*'
               r'\{ ([\d, ]+) \},\s*(ENHY_SKEL_\w+),\s*\{ ([\d, ]+) \},\s*ENHY_ANIM_(\d+),\s*\}')
    rows, counts = [], {}
    for kind, upper, low, colour8, lower, colour9, animation in re.findall(pattern, section):
        head_obj, head, eyes = heads[upper]
        obj, skeleton = skels[lower]
        if skels[low][0] != obj:
            raise ValueError(f'{kind}: split-body object unsupported')
        eye = None if eyes == 'NULL' else re.search(re.escape(eyes) + r'\[\] = \{\s*(\w+)', text)[1]
        variant = counts.get(obj, 0)
        counts[obj] = variant + 1
        clips = [animations[int(animation)]]
        extra = {0:(24,25,26), 5:(23,), 7:(7,)}.get(len(rows), ())
        clips += [animations[a] for a in extra]
        rows.append(dict(kind=kind, obj=obj, skeleton=skeleton, head_obj=head_obj, head=head, eye=eye,
                         colour8=tuple(map(int, colour8.split(','))), colour9=tuple(map(int, colour9.split(','))),
                         variant=variant, clips=list(dict.fromkeys(clips)), bag=len(rows)==3))
    if len(rows) != 21:
        raise ValueError(f'Expected21 Hylian source recipes, found{len(rows)}')
    rows.append(dict(kind='EN_GUEST', obj='object_boj', skeleton='gHylianMan2Skel', head_obj='object_boj',
                     head='gHylianMan2BeardedHeadDL', eye='gHylianMan2MustachedEyeOpenTex',
                     colour8=(255,255,255,255), colour9=(160,60,220,255), variant=counts['object_boj'],
                     clips=['gObjOsAnim_42AC'], bag=False))
    return rows


def keys_header(oot):
    rows = hy_recipes(oot)
    return ('/* Generated from source EnHy model variants; EnGuest shares the man2 archive. */\n'
            'static const unsigned char sChildHylianVariants[21] = { ' +
            ', '.join(str(r['variant']) for r in rows[:-1]) + ' };\n'
            '#define CHILD_GUEST_VARIANT ' + str(rows[-1]['variant']) + '\n')
