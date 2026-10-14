"""Source creation-story actors and bounded presentation adapters.

Gods are offline sprites. Light volumes, the Triforce and scene weather are
environment props. Unrelated adult warp-curve modes are not admitted by this
batch; their Init defaults fail explicitly instead of allocating a skeleton.
"""
import re
from field_enemy_sources import replace_body, replace_once

ACTORS = ('Demo_Effect', 'Demo_Kankyo')
SOURCES = tuple('src/overlays/actors/ovl_%s/z_%s.c' % (n, n.lower()) for n in ACTORS)
OBJECTS = ('object_efc_crystal_light', 'object_efc_fire_ball', 'object_efc_lgt_shower',
           'object_god_lgt', 'object_light_ring', 'object_triforce_spot',
           'object_efc_star_field', 'object_gi_jewel')
SPRITE_OBJECTS = ('object_god_lgt',)
DRAW_SOURCES = [('ACTOR_' + n.upper(), s) for n, s in zip(ACTORS, SOURCES)]
EFFECT_TYPES = ('CRYSTAL_LIGHT', 'FIRE_BALL', 'BLUE_ORB', 'LGT_SHOWER',
                'GOD_LGT_DIN', 'GOD_LGT_NAYRU', 'GOD_LGT_FARORE',
                'LIGHTRING_EXPANDING', 'TRIFORCE_SPOT', 'LIGHTRING_SHRINKING',
                'LIGHTRING_TRIFORCE', 'LIGHT', 'JEWEL_KOKIRI', 'JEWEL_GORON', 'JEWEL_ZORA')
KANKYO_TYPES = ('BLUE_RAIN', 'BLUE_RAIN_2', 'ROCK_1', 'ROCK_2', 'ROCK_3', 'ROCK_4', 'ROCK_5', 'CLOUDS')


def body_span(text, name):
    m = re.search(r'^[\w *]+\b' + re.escape(name) + r'\([^;{}]*\)\s*\{', text, re.M)
    if not m:
        raise ValueError('Missing source function ' + name)
    return m, text.index('\n}', m.end()) + 2


def restrict_switch(text, name, expression, allowed, indent):
    """Keep complete source case bodies at the named switch's own depth."""
    m, end = body_span(text, name)
    start = text.index('switch (' + expression + ') {', m.end(), end)
    stop = text.index('\n' + ' '*(indent-4) + '}', start, end)
    block = text[start:stop]
    labels = list(re.finditer(r'^' + ' '*indent + r'(?:case (\w+)|default):', block, re.M))
    if not labels:
        raise ValueError('Missing source cases ' + name)
    kept = block[:labels[0].start()]
    group = []
    for i, label in enumerate(labels):
        tail = block[label.end():labels[i+1].start() if i+1 < len(labels) else len(block)]
        group.append(label)
        if tail.strip():
            admitted = [entry for entry in group if entry[1] in allowed]
            if admitted:
                kept += '\n'.join(entry[0] for entry in admitted) + tail
            group = []
    kept += '\n' + ' '*indent + 'default:\n' + ' '*(indent+4) + 'ASSERT(0, "unsupported creation actor", __FILE__, __LINE__);\n' + ' '*(indent+4) + 'break;'
    return text[:start] + kept + text[stop:]


def prune_functions(text, roots):
    """Drop unreachable source functions only after bounded Init selection."""
    entries = {}
    for m in re.finditer(r'^[A-Za-z_][\w *]*\s+(\w+)\([^;{}]*\)\s*\{', text, re.M):
        entries[m[1]] = (m.start(), text.index('\n}', m.end()) + 2)
    needed, todo = set(), list(roots)
    while todo:
        name = todo.pop()
        if name in needed:
            continue
        if name not in entries:
            raise ValueError('Missing creation root ' + name)
        needed.add(name)
        a, b = entries[name]
        todo += list((set(re.findall(r'\b\w+\b', text[a:b])) & entries.keys()) - needed)
    for name, (a, b) in sorted(entries.items(), key=lambda x: x[1][0], reverse=True):
        if name not in needed:
            text = text[:a] + text[b:]
    return text


def adapt(rel, text):
    if rel == SOURCES[0]:
        text = replace_once(text, '(360.0f / 65536.0f)', '0.0054931640625f')
        text = restrict_switch(text, 'DemoEffect_Init', 'effectType',
                               {'DEMO_EFFECT_' + n for n in EFFECT_TYPES}, 8)
        text = replace_body(text, 'DemoEffect_Destroy', '    /* Admitted source types own no runtime curve or joints. */')
        # Original Triforce renderer writes alpha into stripped N64 vertices.
        # Source alpha is already in the primitive color; keep that command.
        text = re.sub(r'^    Vtx\* vertices = SEGMENTED_TO_VIRTUAL\(gTriforceVtx\);\n', '', text, flags=re.M)
        text = re.sub(r'^            vertices\[86\].*?\(s8\)this->triforceSpot.lightColumnOpacity;\n', '', text, flags=re.M | re.S)
        m, end = body_span(text, 'DemoEffect_DrawGodLgt')
        draw = text[m.end():end-2]
        audio = draw[draw.index('        if (gSaveContext.save.entranceIndex'):draw.index('        gSPSegment')]
        rotation = draw[draw.index('        this->godLgt.rotation++;'):draw.index('        Matrix_RotateZ')]
        helper = ('void DemoEffect_SaturnGodPresentation(DemoEffect* this, PlayState* play) {\n'
                  '    if (!DemoEffect_CheckForCue(this, play, 2)) {\n' + audio + rotation + '    }\n}\n\n')
        marker = 'void DemoEffect_Update(Actor* thisx, PlayState* play) {'
        text = replace_once(text, marker, helper + marker)
        m, end = body_span(text, 'DemoEffect_Update')
        text = text[:end-2] + ('\n    if (thisx->draw != NULL && (thisx->params & 255) >= DEMO_EFFECT_GOD_LGT_DIN &&\n'
                               '        (thisx->params & 255) <= DEMO_EFFECT_GOD_LGT_FARORE)\n'
                               '        DemoEffect_SaturnGodPresentation(this, play);') + text[end-2:]
        text = replace_body(text, 'DemoEffect_DrawGodLgt', '    /* Offline body/aura sprite; cue/audio/rotation advance in Update. */')
        # Source null child allocation must not dereference a failed parent.
        text = replace_once(text, '&play->actorCtx, &crystalLight->actor, play, ACTOR_DEMO_EFFECT,',
                            '&play->actorCtx, crystalLight ? &crystalLight->actor : NULL, play, ACTOR_DEMO_EFFECT,')
        text = prune_functions(text, ('DemoEffect_Init', 'DemoEffect_Destroy', 'DemoEffect_Update'))
    elif rel == SOURCES[1]:
        text = restrict_switch(text, 'DemoKankyo_Init', 'this->actor.params',
                               {'DEMOKANKYO_' + n for n in KANKYO_TYPES}, 8)
        text = restrict_switch(text, 'DemoKankyo_SetupType', 'this->actor.params',
                               {'DEMOKANKYO_' + n for n in KANKYO_TYPES}, 12)
        text = restrict_switch(text, 'DemoKankyo_Draw', 'this->actor.params',
                               {'DEMOKANKYO_' + n for n in KANKYO_TYPES}, 12)
        text = replace_once(text, '            case DEMOKANKYO_BLUE_RAIN:\n                break;',
                            '            case DEMOKANKYO_BLUE_RAIN:\n            case DEMOKANKYO_BLUE_RAIN_2:\n                break;')
        # Keep every source particle. Decorative copies of each streak are
        # omitted so the full scene stays inside the 96 draw-item budget.
        text = replace_once(text, 'for (j = 0; j < 5; j++)', 'for (j = 0; j < 1; j++)')
        # gEffDustDL is a keep key whose mesh bakes gDust5Tex offline
        # (build_core_meshes); the segment-8 texture word has no reader.
        text = replace_once(text, '        gSPSegment(POLY_XLU_DISP++, 0x08, SEGMENTED_TO_VIRTUAL(gDust5Tex));\n', '')
        text = prune_functions(text, ('DemoKankyo_Init', 'DemoKankyo_Destroy', 'DemoKankyo_Update', 'DemoKankyo_Draw'))
    return text
