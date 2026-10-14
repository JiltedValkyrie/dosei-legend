"""Source effect closure and presentation adapters for the child route packs."""
import re
from pathlib import Path
from field_enemy_sources import replace_body, replace_once

EFFECTS = ('KiraKira', 'Bomb2', 'Blast', 'G_Spk', 'D_Fire', 'G_Ripple',
           'G_Splash', 'Kakera', 'En_Ice', 'Dead_Dd', 'Dead_Ds', 'Ice_Smoke',
           'Bubble', 'Stone1', 'Extra', 'Fcircle', 'Solder_Srch_Ball')
SOURCES = tuple('src/overlays/effects/ovl_Effect_Ss_%s/z_eff_ss_%s.c' % (n, n.lower()) for n in EFFECTS)
CALL = re.compile(r'\b([A-Za-z_]\w*)\s*\(')
FUNCTION = re.compile(r'^[A-Za-z_][\w *]*\s+(\w+)\([^;{}]*\)\s*\{', re.M)


def functions(text):
    return {m[1]: text[m.end():text.index('\n}', m.end())] for m in FUNCTION.finditer(text)}


def effect_table(oot):
    text = (oot/'include/tables/effect_ss_table.h').read_text(encoding='utf-8')
    return dict(re.findall(r'DEFINE_EFFECT_SS\(Effect_Ss_(\w+),\s*(EFFECT_SS_\w+)\)', text))


def scene_effects(oot, actor_names):
    import scene_pack_actors as packs
    import field_enemy_sources as field
    import dodongo_boss_sources as boss
    known = set(EFFECTS) | set(field.EFFECTS) | set(boss.EFFECTS)
    table = effect_table(oot)
    enums = {v: k for k, v in table.items()}
    library = {}
    for rel in ('src/code/z_actor.c', 'src/code/z_effect_soft_sprite_old_init.c'):
        library.update(functions((oot/rel).read_text(encoding='utf-8')))
    texts = [(oot/packs.source(n)).read_text(encoding='utf-8') for n in actor_names]
    # Link's bombs and child projectiles stay resident; their effects belong
    # to the scene's replaceable profile table, including empty enemy rooms.
    for name in ('En_Bom', 'En_Bom_Chu', 'En_Arrow', 'En_Boom'):
        texts.append((oot/packs.source(name)).read_text(encoding='utf-8'))
    texts.append('EffectSsHitMark_SpawnFixedScale(); EffectSsEnFire_SpawnVec3f();')
    # Sprite dismember adapters replace source EnPart meshes with original
    # debris/dust update profiles while retaining the source drop latch.
    if set(actor_names) & {'En_Dodongo', 'En_Dodojr', 'En_Am', 'En_Zf', 'En_Vm', 'En_Sw'}:
        texts.append('EffectSsDeadDb_Spawn(); EffectSsDust_Spawn();')
    todo = list(set(CALL.findall('\n'.join(texts))))
    visited, needed = set(), set()
    while todo:
        name = todo.pop()
        if name in visited:
            continue
        visited.add(name)
        text = library.get(name, '')
        needed.update(enums[t] for t in re.findall(r'\bEFFECT_SS_\w+\b', text) if t in enums)
        todo.extend(set(CALL.findall(text)) - visited)
    unknown = needed - known
    if unknown:
        raise ValueError('Child route needs unimplemented effects: ' + ', '.join(sorted(unknown)))
    return [n for n in table if n in needed]


def profiles(oot, names, symbol):
    table = effect_table(oot)
    result = ['\n/* Source-reachable scene effect profiles. */', '#include "effect.h"']
    result += ['extern EffectSsProfile Effect_Ss_%s_Profile;' % n for n in names]
    result += ['extern "C" const OotActorPackProfile %s[]' % symbol,
               '    __attribute__((section(".pack_effects"), used)) = {']
    result += ['    {%s, (u32)(uintptr_t)&Effect_Ss_%s_Profile},' % (table[n], n) for n in names]
    return '\n'.join(result + ['};', ''])


def adapt(rel, text):
    if rel not in SOURCES:
        return text
    if rel.endswith('z_eff_ss_dead_ds.c'):
        draw = functions(text)['EffectSsDeadDs_Draw']
        start = draw.index('    pos = this->pos;')
        end = draw.index('        this->rTimer++;', start) + len('        this->rTimer++;\n    }')
        contact = ('static void EffectSsDeadDs_SaturnContact(PlayState* play, EffectSs* this) {\n'
                   '    MtxF mf; f32 yIntersect; Vec3f pos; CollisionPoly* groundPoly;\n' +
                   draw[start:end] + '\n}\n\n')
        marker = 'void EffectSsDeadDs_Draw(PlayState* play, u32 index, EffectSs* this) {'
        text = replace_once(text, marker, contact + marker)
        marker = 'void EffectSsDeadDs_Update(PlayState* play, u32 index, EffectSs* this) {'
        text = replace_once(text, marker, marker + '\n    EffectSsDeadDs_SaturnContact(play, this);')
    for name in re.findall(r'^void (EffectSs\w+_Draw\w*)\([^;{}]*\) \{', text, re.M):
        text = replace_body(text, name, '    /* Source updates; bounded Saturn effect snapshot. */')
    if rel.endswith('z_eff_ss_bubble.c'):
        text = replace_once(text,
            'this->gfx = SEGMENTED_TO_VIRTUAL(Rand_ZeroOne() < 0.5f ? gEffBubble1Tex : gEffBubble2Tex);',
            '(void)Rand_ZeroOne(); (void)Rand_ZeroOne(); this->gfx = NULL;')
    # Texture and display-list addresses have no meaning in the host effect
    # view. Keep source object availability checks and every physics update.
    text = re.sub(r'this->gfx = SEGMENTED_TO_VIRTUAL\([^;]+\);', 'this->gfx = NULL;', text)
    text = re.sub(r'Rand_CenteredFloat\((?:65535|65536)\.0f\)',
                  '(Rand_CenteredFloat(32767.0f) * 2)', text)
    if rel.endswith('z_eff_ss_kirakira.c'):
        text = replace_once(text, '(32768.0f / this->rLifespan) * this->life',
                            '(32768 * this->life) / this->rLifespan')
    return text
