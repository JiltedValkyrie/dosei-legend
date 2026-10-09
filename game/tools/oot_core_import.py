#!/usr/bin/env python3
"""Mirror zeldaret/oot decomp sources into game/build/oot-core/ for the SH-2 C++ build.

Mechanical C-vs-C++ fixups and explicit Saturn backend substitutions:
  * Sprite NPCs (human directive 2026-10-03): clock-only animation; no poses,
    skeleton allocation, head tracking or joint-driven fidget/stagger.
  * MtxF anonymous-struct fields (.xx etc.) -> .mf[col][row]; GCC forbids
    members with constructors (Fx) in anonymous aggregates.
  * xstdio.h `long double` printf slot -> long long (no long double type).
  * `typedef union X { struct {...}; s32 _words[N]; } X;` -> plain struct
    (_words is never read by game code; same anonymous-aggregate rule).
  * CamParamData's anonymous door struct/union get names; the six
    `paramData.<member>` accesses are rewritten to match.
  * MIN/MAX/ABS/CLAMP* macro bodies -> OOT_SEL (mixed int/Fx ternary).
  * Floating literals -> FXL(lit). Otherwise `s16 * 0.5f` is evaluated in
    hardware float (soft-float on SH-2) because neither operand is Fx.
Keyword renames and float->Fx live in game/oot-core/include/oot_prelude.h.
Anything the fixups cannot handle must be listed in the import report, not
hand-patched in the generated tree.
"""
import argparse
import hashlib
import json
import pathlib
import re
import struct
import sys
import field_enemy_sources
import water_temple_sources
from environment_source import (clock_source, room_clock_source, room_time,
                                room_behavior, sun_song_source, destination_layer_source,
                                transition_clock_source, clock_events_source, player_clock_gate_source)
from environment_selection_source import sky_settings, retained_weather_source
from environment_sequence_source import sound_settings, sequence_source

OOT_DEFAULT = pathlib.Path((__import__('os').environ.get('DOSEI_OOT') or 'D:/Workspace-Claude/game-decomps/n64/oot'))
VERSION = 'ntsc-1.2'
GAME = pathlib.Path(__file__).resolve().parents[1]
OUT_DEFAULT = GAME / 'build' / 'oot-core'

# Phase 0 slice. Paths relative to the decomp root.
SOURCES = [
    'src/code/z_lib.c',
    'src/code/sys_math.c',
    'src/code/sys_math_atan.c',
    'src/code/sys_math3d.c',
    'src/libc64/math64.c',
    'src/libultra/gu/sins.c',
    'src/libultra/gu/coss.c',
    'src/code/z_actor.c',
    'src/code/z_collision_check.c',
    'src/code/z_en_item00.c',
    'src/code/z_bgcheck.c',
    'src/overlays/actors/ovl_En_Kusa/z_en_kusa.c',
    # Phase 1 batch 1: leaf systems the actor/collision link needs.
    'src/code/sys_matrix.c',
    'src/code/z_skin_matrix.c',
    'src/code/TwoHeadArena.c',
    'src/code/z_lights.c',
    'src/code/z_eff_ss_dead.c',
    'src/code/z_bg_collect.c',
    'src/code/z_bg_item.c',
    'src/code/z_inventory.c',
    'src/code/z_rcp.c',
    'src/libultra/gu/lookathil.c',
    'src/code/z_effect.c',
    'src/code/z_effect_soft_sprite.c',
    'src/code/z_effect_soft_sprite_old_init.c',
    # batch 2
    'src/code/z_eff_blure.c',
    'src/code/z_eff_spark.c',
    'src/code/z_eff_shield_particle.c',
    'src/libultra/gu/mtxutil.c',
    'src/code/z_malloc.c',
    'src/libc64/__osMalloc_n64.c',
    # Route step 3-5: NPC skeleton/animation, message logic, first NPC.
    'src/code/z_skelanime.c',
    'src/code/z_message.c',
    'src/code/z_kanfont.c',
    'src/overlays/actors/ovl_En_Ko/z_en_ko.c',
    'src/code/z_face_reaction.c',
    'src/code/z_path.c',
    'src/code/gfxalloc.c',
    'src/code/z_memory_utils.c',
    'src/code/z_construct.c',  # Message_Init, Regs_InitData
    'src/code/z_collision_btltbls.c',  # DamageTable_Get
    # Route step 5, Kokiri Forest batch 1.
    'src/overlays/actors/ovl_En_Md/z_en_md.c',
    'src/overlays/actors/ovl_En_Wonder_Item/z_en_wonder_item.c',
    'src/overlays/actors/ovl_En_Wonder_Talk2/z_en_wonder_talk2.c',
    'src/overlays/actors/ovl_Obj_Mure2/z_obj_mure2.c',
    'src/overlays/actors/ovl_En_Kanban/z_en_kanban.c',
    # Link's C-button tools (bridge_items.cpp plays Player's side; the host
    # draws baked ITM*.SPR sprites, so no tool draw function runs).
    'src/overlays/actors/ovl_En_Arrow/z_en_arrow.c',
    'src/overlays/actors/ovl_En_Bom/z_en_bom.c',
    'src/overlays/actors/ovl_En_Bom_Chu/z_en_bom_chu.c',
    'src/overlays/actors/ovl_En_Boom/z_en_boom.c',
    'src/overlays/actors/ovl_Arms_Hook/z_arms_hook.c',
    # EnArrow's elemental children (fire/ice/light): source gameplay and SFX;
    # their mesh/textures stay offline, the host draws baked ITMMAG glows.
    'src/overlays/actors/ovl_Arrow_Fire/z_arrow_fire.c',
    'src/overlays/actors/ovl_Arrow_Ice/z_arrow_ice.c',
    'src/overlays/actors/ovl_Arrow_Light/z_arrow_light.c',
]
COL_HEADER = re.compile(r'^CollisionHeader (\w+)_Col = \{$', re.M)
COL_ARRAY = re.compile(r'^\w+ (\w+)\[\] = \{\n#include "[^"]+"\n\};\n', re.M)


ROOM_ACTORS = re.compile(r'^ActorEntry (\w+)\[\w+\] = \{\n#include "[^"]+"\n\};\n', re.M)
ALT_TABLE = re.compile(r'^SceneCmd\* (\w+_AltHeaders)\[\] = \{\n#include "([^"]+)"\n\};', re.M)
# Registered runtime scenes (build_scene_table.py): one blob per scene index.
SCENE_TABLE_JSON = GAME / 'build' / 'generated' / 'scene_table.json'


def asset_includes(path, text):
    """#include lines of an extracted asset .c, minus .inc.c bodies. The
    file's own header is included by bare name (same directory); the
    generated file lives elsewhere, so give it the asset-root path."""
    own_dir = path.parent.as_posix().split('/extracted/')[-1].split('/', 1)[-1]
    return [re.sub(r'#include "([^"/]+)"', lambda m: f'#include "{own_dir}/{m.group(1)}"'
                   if (path.parent / m.group(1)).exists() else m.group(0), l)
            for l in text.splitlines() if l.startswith('#include') and '.inc.c' not in l]


def room_files(scene_path):
    stem = scene_path.name[:-len('_scene.c')]
    rooms = []
    while (scene_path.parent / f'{stem}_room_{len(rooms)}.c').exists():
        rooms.append(scene_path.parent / f'{stem}_room_{len(rooms)}.c')
    return rooms


def room_layers(room, rtext, asset_root):
    """Per scene layer: (actor list name or None, present). Layer 0 is the
    main header. Layer L >= 1 is AltHeaders[L - 1]: NULL there means the
    layer is absent (runtime falls back like Scene_CommandAlternateHeaderList);
    a header with no ACTOR_LIST command is present with no actors."""
    lists = [a.group(1) for a in ROOM_ACTORS.finditer(rtext)]
    main = [n for n in lists if 'AltHeaders' not in n]
    if len(main) > 1:
        raise SystemExit(f'{room}: {len(main)} main-header ActorEntryLists')
    layers = [(main[0] if main else None, True)]
    alt = ALT_TABLE.search(rtext)
    if alt:
        entries = re.findall(r'^\s*(\w+),', (asset_root / alt.group(2)).read_text(encoding='utf-8'), re.M)
        for cmds in entries:
            if cmds == 'NULL':
                layers.append((None, False))
            else:
                found = [n for n in lists if n.startswith(cmds + '_')]
                layers.append((found[0] if found else None, True))
    return layers


SCENE_PATH_DEF = re.compile(r'^(Path|Vec3s) (\w+)\[\w*\] = \{\n#include "[^"]+"\n\};\n', re.M)
SCENE_PATH_CMD = re.compile(r'SCENE_CMD_PATH_LIST\((\w+)\)')


def scene_paths(path, text, asset_root):
    """Scene_CommandPathList per scene layer: every Path array of the scene
    .c with its point arrays (verbatim), and for layer 0 (main header) and
    each AltHeaders entry the path list its commands name. A NULL alt
    header is absent (runtime falls back like Scene_CommandAlternateHeaderList);
    a header without SCENE_CMD_PATH_LIST is present with no paths."""
    defs = [(m.group(1), m.group(2), m.group(0)) for m in SCENE_PATH_DEF.finditer(text)]
    paths = [n for t, n, _ in defs if t == 'Path']
    body = ''.join('\n' + src for t, n, src in defs
                   if t == 'Path' or any(n.startswith(p + '_') for p in paths))
    stem = path.name[:-len('.c')]
    main_inc = path.parent / f'{stem}.inc.c'
    def cmd_path(inc):
        found = SCENE_PATH_CMD.search(inc.read_text(encoding='utf-8')) if inc.exists() else None
        return found.group(1) if found else None
    layers = [(cmd_path(main_inc), True)]
    alt = ALT_TABLE.search(text)
    if alt:
        for cmds in re.findall(r'^\s*(\w+),', (asset_root / alt.group(2)).read_text(encoding='utf-8'), re.M):
            if cmds == 'NULL':
                layers.append((None, False))
            else:
                layers.append((cmd_path(path.parent / f'{cmds}.inc.c'), True))
    return body, layers


def scene_transitions(path, text, asset_root):
    """Retain original door indices, sides and params, including absent layers."""
    definition = re.compile(r'^TransitionActorEntry (\w+)\[\w*\] = \{\n#include "[^"]+"\n\};\n', re.M)
    definitions = {m.group(1): m.group(0) for m in definition.finditer(text)}
    headers = [path.with_suffix('.inc.c')]
    alt = ALT_TABLE.search(text)
    if alt:
        headers += [None if n == 'NULL' else path.parent / (n + '.inc.c')
                    for n in re.findall(r'^\s*(\w+),',
                                        (asset_root / alt.group(2)).read_text(encoding='utf-8'), re.M)]
    layers = []
    for header in headers:
        if header is None:
            layers.append((None, False))
            continue
        source = header.read_text(encoding='utf-8') if header.exists() else ''
        commands = re.findall(r'SCENE_CMD_TRANSITION_ACTOR_LIST\([^\n]*,\s*(\w+)\s*\)', source)
        if len(commands) > 1:
            raise ValueError(f'{header}: multiple transition actor lists')
        name = commands[0] if commands else None
        if name and name not in definitions:
            raise ValueError(f'{header}: missing transition definition {name}')
        layers.append((name, True))
    wanted = {name for name, _ in layers if name}
    return ''.join('\n' + body for name, body in definitions.items() if name in wanted), layers


def scene_blob_source(path, asset_root, objects=()):
    """Cut a scene .c down to its collision (CollisionHeader + every array
    named with its prefix: BgCam, SurfaceTypes, PolyList, VtxList,
    WaterBoxes) and each room .c down to its ActorEntryLists for every scene
    layer (main header + AltHeaders: child/adult day/night, cutscene setups).
    Verbatim slices of the extracted files, no edits. OotSceneBlob
    (oot_scene_blob.h) goes in .scene_header at the blob's load address."""
    text = path.read_text(encoding='utf-8')
    m = COL_HEADER.search(text)
    if not m:
        raise SystemExit(f'{path}: no CollisionHeader')
    prefix = m.group(1)
    includes = asset_includes(path, text)
    arrays = [a.group(0) for a in COL_ARRAY.finditer(text) if a.group(1).startswith(prefix + '_')]
    end = text.index('};\n', m.end()) + 3
    body = '\n'.join(arrays) + '\n' + text[m.start():end]
    per_room = []
    oot = asset_root.parent.parent
    for room in room_files(path):
        rtext = room.read_text(encoding='utf-8')
        includes += [l for l in asset_includes(room, rtext) if l not in includes]
        layers = room_layers(room, rtext, asset_root)
        wanted = {n for n, _ in layers if n}
        body += ''.join('\n' + a.group(0) for a in ROOM_ACTORS.finditer(rtext) if a.group(1) in wanted)
        # Same header/layer ordering as the actor list. Time is a room command.
        time_paths = [room.with_suffix('.inc.c')]
        alt = ALT_TABLE.search(rtext)
        if alt:
            time_paths += [None if n == 'NULL' else room.parent / (n + '.inc.c')
                           for n in re.findall(r'^\s*(\w+),',
                               (asset_root / alt.group(2)).read_text(encoding='utf-8'), re.M)]
        if len(time_paths) != len(layers):
            raise ValueError(f'{room}: actor/time layer count differs')
        per_room.append([(n, p, (room_time(t) if t else (0,0,0)) +
                         room_behavior(t, oot) + sky_settings(t, oot) + sound_settings(t, oot))
                         for (n,p),t in zip(layers,time_paths)])
    if len(per_room) > 32:
        raise SystemExit(f'{path}: {len(per_room)} rooms > OOT_SCENE_MAX_ROOMS')
    num_layers = max((len(l) for l in per_room), default=1)
    rows = []
    for layers in per_room:
        layers = layers + [(None, False, (0,)*12)] * (num_layers - len(layers))
        for n, p, metadata in layers:
            actors = f'{n}, ARRAY_COUNT({n})' if n else '0, 0'
            rows.append(f'    {{ {actors}, {int(p)}, ' + ', '.join(map(str,metadata)) + ' },')
    table = ('static const OotSceneLayer oot_scene_layers[] = {\n'
             + ('\n'.join(rows) if rows else '    { 0, 0, 0 },') + '\n};\n')
    path_defs, path_layers = scene_paths(path, text, asset_root)
    body += path_defs
    scene_headers = [path.with_suffix('.inc.c')]
    alt = ALT_TABLE.search(text)
    if alt:
        scene_headers += [None if n == 'NULL' else path.parent/(n+'.inc.c')
                          for n in re.findall(r'^\s*(\w+),',
                              (asset_root/alt.group(2)).read_text(encoding='utf-8'), re.M)]
    if len(scene_headers) != len(path_layers):
        raise ValueError(f'{path}: scene sky/path layer count differs')
    path_rows = [f'    {{ {n or "0"}, ' + (f'sizeof({n}) / sizeof({n}[0])' if n else '0') +
                 f', {int(p)}, 0, 0, 0, 0, 0, ' +
                 ', '.join(map(str,sky_settings(header,oot)+sound_settings(header,oot))) + ' },'
                 for (n,p),header in zip(path_layers,scene_headers)]
    table += ('static const OotSceneLayer oot_scene_paths[] = {\n' + '\n'.join(path_rows) + '\n};\n')
    transition_defs, transition_layers = scene_transitions(path, text, asset_root)
    body += transition_defs
    transition_rows = [f'    {{ {n}, ARRAY_COUNT({n}), {int(p)} }},' if n else
                       f'    {{ 0, 0, {int(p)} }},' for n, p in transition_layers]
    table += ('static const OotSceneLayer oot_scene_transitions[] = {\n' +
              '\n'.join(transition_rows) + '\n};\n')
    header = ('extern "C" const OotSceneBlob oot_scene_blob'
              ' __attribute__((section(".scene_header"), used)) = {\n'
              f'    &{prefix}_Col, {len(per_room)}, {num_layers}, oot_scene_layers,\n'
              f'    oot_scene_objects, {len(objects)},\n'
              f'    oot_scene_paths, {len(path_layers)},\n'
              f'    OOT_SCENE_BLOB_FORMAT, oot_scene_transitions, {len(transition_layers)},\n}};\n')
    objs = ('static const unsigned short oot_scene_objects[] = { '
            + (', '.join('0x%03X' % o for o in objects) if objects else '0') + ' };\n')
    return ('// Generated by tools/oot_core_import.py from ' + path.name
            + ' (collision + room actor lists, all layers).\n'
            + '\n'.join(includes) + '\n#include "array_count.h"\n#include "oot_scene_blob.h"\n\n'
            + body + '\n' + table + objs + header)


# gameplay_keep / field keep / not-built object symbols the imported code
# references. Decomp code only takes their addresses; each is one zero word
# in section .keep_ph, in this order: the Phase 2 draw shim keys a DL by its
# index (oot_core_draw.cpp), and keep_ph.txt names each index for the mesh
# tool. Append only (indices of existing names must not move).
KEEP_PLACEHOLDERS = [
    'gCircleShadowDL',
    'gCuttableShrubStalkDL',
    'gCuttableShrubTipDL',
    'gDropArrows1Tex',
    'gDropArrows2Tex',
    'gDropArrows3Tex',
    'gDropBombTex',
    'gDropDekuNutTex',
    'gDropDekuSeedsTex',
    'gDropDekuStickTex',
    'gDropKeySmallTex',
    'gDropMagicLargeTex',
    'gDropMagicSmallTex',
    'gDropRecoveryHeartTex',
    'gEffFlash1DL',
    'gFieldBushDL',
    'gGlowCircleDL',
    'gGlowCircleTextureLoadDL',
    'gHeartContainerInteriorDL',
    'gHeartPieceExteriorDL',
    'gHeartPieceInteriorDL',
    'gItemDropDL',
    'gLensOfTruthMaskTex',
    'gRupeeBlueTex',
    'gRupeeDL',
    'gRupeeGreenTex',
    'gRupeeOrangeTex',
    'gRupeePinkTex',
    'gRupeeRedTex',
    'gUnknownCircle6Tex',
    'gUnknownEffBlureTex',
    'object_kusa_DL_000140',
    'object_kusa_DL_0002E0',
    'gOcarinaBtnIconATex',
    'gOcarinaBtnIconCDownTex',
    'gOcarinaBtnIconCLeftTex',
    'gOcarinaBtnIconCRightTex',
    'gOcarinaBtnIconCUpTex',
    'gOcarinaTrebleClefTex',
    'gSignRectangularDL',
    # Phase 2 generic-draw batch 1
    'gPotDL',
    'gPotFragmentDL',
    'gFieldKakeraDL',
    'gSilverRockDL',
    'gSilverRockFragmentsDL',
    'gEffFire1DL',
    'gHanaDL',
    'gSmallWoodenBoxDL',
    'gSmallWoodenBoxFragmentDL',
    # Field particle profiles retain opaque symbol identities, never meshes.
    'gEffEnemyDeathFlameDL', 'gEffFragments1DL', 'gEffFragments2DL', 'gEffDustDL',
    'gEffHitMarkDL',
]


def keep_ph_source():
    lines = ['// Generated by tools/oot_core_import.py KEEP_PLACEHOLDERS. Do not edit.',
             '// C++ namespace-scope variables are not mangled: u64[1] satisfies any',
             '// extern Gfx[] / u64[] declaration at link time.',
             'typedef unsigned long long u64;']
    lines += [f'u64 {n}[1] __attribute__((section(".keep_ph")));' for n in KEEP_PLACEHOLDERS]
    return '\n'.join(lines) + '\n'


# Decomp objects built as data blobs (<O><id hex>.OOB): what the imported
# actors read from their object segment (skeletons, limbs, animations).
OBJECTS = ['object_os_anime', 'object_km1', 'object_kw1', 'object_fa', 'object_md', 'object_kanban',
           'object_tsubo', 'object_gs', 'object_wood02', 'object_syokudai',
           'object_in', 'object_ma1', 'object_ma2', 'object_ta', 'object_niw', 'object_cow',
           # Kakariko buildings (Bg_Spot01_Objects2): mesh + DynaPoly collision.
           'object_spot01_matoya', 'object_spot01_matoyab']
OBJECTS += list(field_enemy_sources.OBJECTS)
OBJECTS += list(water_temple_sources.SPRITE_OBJECTS)
# Definitions kept verbatim; everything else (Gfx, Vtx, textures, palettes)
# becomes a one-element placeholder: the draw shim keys on its address.
OBJECT_KEEP_TYPES = {'AnimationHeader', 'JointIndex', 's16', 'StandardLimb', 'LodLimb',
                     'FlexSkeletonHeader', 'SkeletonHeader', 'void*', 'LinkAnimationHeader',
                     # DynaPoly collision (Bg actors): host bg_dyna reads it.
                     'CollisionHeader', 'CollisionPoly', 'SurfaceType', 'Vec3s', 'BgCamInfo',
                     'WaterBox'}
OBJECT_DEF = re.compile(r'^((?:const )?[A-Za-z_][A-Za-z0-9_]*\*?) ([A-Za-z_][A-Za-z0-9_]*)(\[[^\]]*\])? = \{\n'
                        r'(?:.*?\n)*?\};\n', re.M)


# Imported actors drawn through the Phase 2 shim (oot_core_draw.cpp) rather
# than a C renderer. Their DLs need meshes (tools/build_core_meshes.py). They
# spawn only in generic scenes (not the 11 slice scenes, whose C copies stay).
GENERIC_DRAW_SOURCES = [
    ('ACTOR_OBJ_TSUBO', 'src/overlays/actors/ovl_Obj_Tsubo/z_obj_tsubo.c'),
    # En_Ishi left out: 38 KB of blob (Fx code) and rocks need lifting,
    # which the player proxy cannot do yet.
    ('ACTOR_EN_GS', 'src/overlays/actors/ovl_En_Gs/z_en_gs.c'),
    ('ACTOR_OBJ_HANA', 'src/overlays/actors/ovl_Obj_Hana/z_obj_hana.c'),
    ('ACTOR_EN_WOOD02', 'src/overlays/actors/ovl_En_Wood02/z_en_wood02.c'),
    ('ACTOR_OBJ_SYOKUDAI', 'src/overlays/actors/ovl_Obj_Syokudai/z_obj_syokudai.c'),
    ('ACTOR_OBJ_KIBAKO', 'src/overlays/actors/ovl_Obj_Kibako/z_obj_kibako.c'),
    # Kakariko shooting gallery / construction site / posters: building
    # visuals + DynaPoly collision only (human GO 2026-10-06). Its daytime
    # En_Daiku_Kakariko child is not imported, so that spawn simply fails.
    ('ACTOR_BG_SPOT01_OBJECTS2', 'src/overlays/actors/ovl_Bg_Spot01_Objects2/z_bg_spot01_objects2.c'),
]
GENERIC_DRAW = [a for a, _ in GENERIC_DRAW_SOURCES]
# NPCs the decomp owns in generic scenes (no C copy there): spawned there,
# drawn by the skinned NPC path (tools/build_core_skins.py).
GENERIC_NPC_SOURCES = [
    ('ACTOR_EN_IN', 'src/overlays/actors/ovl_En_In/z_en_in.c'),
    ('ACTOR_EN_MA1', 'src/overlays/actors/ovl_En_Ma1/z_en_ma1.c'),
    ('ACTOR_EN_MA2', 'src/overlays/actors/ovl_En_Ma2/z_en_ma2.c'),
    ('ACTOR_EN_TA', 'src/overlays/actors/ovl_En_Ta/z_en_ta.c'),
    ('ACTOR_EN_NIW', 'src/overlays/actors/ovl_En_Niw/z_en_niw.c'),
    ('ACTOR_EN_COW', 'src/overlays/actors/ovl_En_Cow/z_en_cow.c'),
]
SOURCES += [s for _, s in GENERIC_NPC_SOURCES]
SOURCES += [s for _, s in GENERIC_DRAW_SOURCES]


def object_ids(oot):
    """Object enum name -> id, in object_table.h order."""
    text = (oot / 'include' / 'tables' / 'object_table.h').read_text(encoding='utf-8')
    names = re.findall(r'^\s*/\* (0x[0-9A-Fa-f]+) \*/ DEFINE_OBJECT\w*\((\w+), (\w+)\)', text, re.M)
    return {enum: int(i, 16) for i, _sym, enum in names}, {sym: int(i, 16) for i, sym, _e in names}


SPRITE_OBJECTS = {'object_in', 'object_ma1', 'object_ma2', 'object_ta', 'object_niw', 'object_cow'}
SPRITE_OBJECTS.update(field_enemy_sources.OBJECTS)
SPRITE_OBJECTS.update(water_temple_sources.SPRITE_OBJECTS)


def sprite_animation_header(sym, definition, asset_root):
    """Keep only the action clock length; no frame/joint/pose data on disc."""
    for include in re.findall(r'#include "([^"]+)"', definition):
        definition = definition.replace('#include "' + include + '"',
                                        (asset_root / include).read_text(encoding='utf-8'))
    definition = re.sub(r'//[^\n]*|/\*.*?\*/', '', definition, flags=re.S)
    match = re.search(r'=\s*\{\s*\{\s*(\d+)\s*,?', definition)
    if not match:
        raise ValueError('missing animation frameCount: ' + sym)
    return 'AnimationHeader %s = { { %s }, NULL, NULL, 0 };' % (sym, match[1])


def object_blob_sources(name, asset_root):
    """(data .cpp, placeholder .cpp) for one object. Data keeps the object's
    own header (limb enums) and the kept definitions verbatim; placeholders
    are in a second unit without the header, so `u64 x[1]` never clashes
    with the header's real array size."""
    path = asset_root / 'assets' / 'objects' / name / (name + '.c')
    if path.exists():
        parts = [(path, path.read_text(encoding='utf-8'), asset_includes)]
    else:
        # Hand-split objects live in the decomp's own assets/objects/<name>/*.c
        # (they still include the extracted .inc.c bodies).
        root = asset_root.parents[1] / 'assets' / 'objects' / name
        own = f'assets/objects/{name}'
        def root_includes(p, t):
            return [re.sub(r'#include "([^"/]+)"', lambda m: f'#include "{own}/{m.group(1)}"'
                           if (root / m.group(1)).exists() else m.group(0), l)
                    for l in t.splitlines() if l.startswith('#include') and '.inc.c' not in l]
        parts = [(p, p.read_text(encoding='utf-8'), root_includes) for p in sorted(root.glob('*.c'))]
        if not parts:
            raise SystemExit(f'object {name}: no source in {path.parent} or {root}')
    keep, drop, includes, drop_types = [], [], [], {}
    for p, text, inc in parts:
        for m in OBJECT_DEF.finditer(text):
            typ, sym = m.group(1).replace('const ', ''), m.group(2)
            if name in SPRITE_OBJECTS and typ == 'AnimationHeader':
                keep.append(sprite_animation_header(sym, m.group(0), asset_root))
            elif name not in SPRITE_OBJECTS and typ in OBJECT_KEEP_TYPES:
                keep.append(m.group(0))
            else:
                drop.append(sym)
                drop_types[sym] = typ
        includes += [l for l in inc(p, text) if l not in includes]
    # Some object headers miss DLs their own limbs name (object_ta): declare
    # every dropped symbol the headers do not mention, with its own type.
    headers = ''
    for h in list(path.parent.glob('*.h')) + list((asset_root.parents[1] / 'assets' / 'objects' / name).glob('*.h')):
        headers += h.read_text(encoding='utf-8', errors='replace')
    decls = ''.join(f'extern {drop_types[s]} {s}[];\n' for s in drop
                    if not re.search(r'\b' + re.escape(s) + r'\b', headers))
    data = ('// Generated by tools/oot_core_import.py from ' + path.name + ' (data only).\n'
            + '\n'.join(includes) + '\n' + decls + '\n' + '\n'.join(keep))
    ph = ('// Generated by tools/oot_core_import.py: ' + name + ' display lists and textures,\n'
          '// one word each (draw-shim keys, never read). Header first, then the\n'
          '// placeholders in this order (index = position, see <stem>_ph.txt).\n'
          'typedef unsigned long long u64;\n'
          'extern "C" const unsigned int oot_object_head[2] __attribute__((section(".ph_head"), used)) = '
          '{ 0x4F4F4231u, %du };\n' % len(drop)
          + ''.join(f'u64 {s}[1] __attribute__((section(".ph")));\n' for s in drop))
    return data, ph, drop


def scene_objects(scene_c, built_ids, enum_ids):
    """Built objects any room/layer of the scene lists (Scene_CommandObjectList)."""
    stem = scene_c.name[:-len('_scene.c')]
    found = set()
    for f in scene_c.parent.glob(stem + '_room_*ObjectList.inc.c'):
        for enum in re.findall(r'\b(OBJECT_\w+)', f.read_text(encoding='utf-8')):
            oid = enum_ids.get(enum)
            if oid in built_ids:
                found.add(oid)
    return sorted(found)


def object_stem(oid):
    return 'O%03X' % oid


def registered_scenes(asset_root):
    """(blob stem, scene .c) for every runtime scene, by scene index."""
    if not SCENE_TABLE_JSON.exists():
        raise SystemExit(f'{SCENE_TABLE_JSON} missing: run the full build first')
    sys.path.insert(0, str(GAME / 'tools'))
    import asset_names
    out = []
    for s in json.loads(SCENE_TABLE_JSON.read_text())['scenes']:
        found = list((asset_root / 'assets/scenes').glob('*/%s/%s_scene.c' % (s['prefix'], s['prefix'])))
        if found:
            out.append((asset_names.scene_stem(s['index']), found[0]))
    return out


# Whole trees mirrored for headers.
HEADER_TREES = ['include', 'src']

MTXF_FIELDS = ['xx', 'yx', 'zx', 'wx', 'xy', 'yy', 'zy', 'wy',
               'xz', 'yz', 'zz', 'wz', 'xw', 'yw', 'zw', 'ww']
MTXF_INDEX = {name: (i // 4, i % 4) for i, name in enumerate(MTXF_FIELDS)}
MTXF_ACCESS = re.compile(r'(\.|->)\s*(' + '|'.join(MTXF_FIELDS) + r')\b')
MTXF_DECL = re.compile(
    r'typedef union MtxF \{\s*MtxF_t mf;\s*struct \{.*?\};\s*\} MtxF;', re.S)


WORDS_UNION = re.compile(
    r'typedef union (\w+) \{\s*struct \{(.*?)\};\s*s32 _words\[\w+\];\s*\} \1;', re.S)
CAM_DOOR_DECL = re.compile(
    r'struct \{\s*(/\* 0x0 \*/ DoorParams doorParams;)\s*(/\* 0xC \*/) union \{(.*?)\};\s*\};', re.S)
CAM_DOOR_ACCESS = re.compile(r'\bparamData\.(doorParams|uniq0|uniq3|spec9)\b')


def fix_anon_aggregates(rel, text, stats):
    def words(m):
        stats['anon'] += 1
        return f'typedef struct {m.group(1)} {{{m.group(2)}}} {m.group(1)};'
    text = WORDS_UNION.sub(words, text)
    if rel == 'include/camera.h':
        text, n = CAM_DOOR_DECL.subn(
            lambda m: ('struct {\n        ' + m.group(1) + '\n        ' + m.group(2) +
                       ' union {' + m.group(3) + '} u;\n    } door;'), text)
        if n != 1:
            stats['problems'].append(f'{rel}: CamParamData door struct not found')
        stats['anon'] += n

    def access(m):
        stats['anon'] += 1
        member = m.group(1)
        return 'paramData.door.' + (member if member == 'doorParams' else 'u.' + member)
    return CAM_DOOR_ACCESS.sub(access, text)


FLOAT_LIT = re.compile(
    r'(?<![\w.])(?:\d+\.\d*|\.\d+|\d+(?=[eE]))(?:[eE][+-]?\d+)?[fFlL]?(?![\w.])')
SKIP_TOKEN = re.compile(r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|//[^\n]*|/\*.*?\*/', re.S)
DIRECTIVE = re.compile(r'^[ \t]*#[ \t]*(include|pragma|line|error|warning)\b[^\n]*$', re.M)


# Q16.16 Fx (Wave 0) saturates at +/-32767.99998. Source literals past that
# are listed in import_report.txt for the range audit (each needs a bounded
# helper or a source-backed reason the saturated value is harmless).
FX_LIMIT = 32768.0


def fix_float_literals(text, stats, rel=''):
    out = []
    pos = 0
    skips = sorted([m.span() for m in SKIP_TOKEN.finditer(text)] +
                   [m.span() for m in DIRECTIVE.finditer(text)])

    def wrap(chunk):
        def sub(m):
            stats['fxl'] += 1
            lit = m.group(0)
            if rel.endswith('.c') and not rel.endswith('.inc.c'):
                try:
                    value = abs(float(lit.rstrip('fFlL')))
                except ValueError:
                    value = 0.0
                if value >= FX_LIMIT:
                    stats.setdefault('fx_range', []).append(f'{rel}: {lit}')
            return f'FXL({lit})'
        return FLOAT_LIT.sub(sub, chunk)
    for start, end in skips:
        if start < pos:
            continue
        out.append(wrap(text[pos:start]))
        out.append(text[start:end])
        pos = end
    out.append(wrap(text[pos:]))
    return ''.join(out)


# Q16.16 Fx (Wave 0): random binangle ranges such as Rand_ZeroOne() * 65534.0f
# or Rand_CenteredFloat(0x10000) saturate at 32767 and halve the angle range.
# Rewrite them to 32-bit integer helpers (oot_rand.cpp) that consume the same
# single Rand_Next() draw, so the RNG sequence is unchanged.
RAND_RANGE = re.compile(
    r'Rand_ZeroOne\(\)\s*\*\s*(0x[0-9A-Fa-f]+|\d+(?:\.\d*)?f?)(?![\w.])'
    r'|Rand_(ZeroFloat|CenteredFloat)\(\s*(0x[0-9A-Fa-f]+|\d+(?:\.\d*)?f?)\s*\)')


def fix_rand_ranges(rel, text, stats):
    if not rel.endswith('.c') or rel.endswith('.inc.c'):
        return text

    def number(lit):
        if lit.lower().startswith('0x'):
            return int(lit, 16)
        return float(lit.rstrip('fF'))

    def sub(m):
        lit = m.group(1) or m.group(3)
        value = number(lit)
        if value < FX_LIMIT or value != int(value) or value > 0x20000:
            return m.group(0)
        stats['macros'] += 1
        helper = 'OotRand_CenteredTimes' if m.group(2) == 'CenteredFloat' else 'OotRand_ZeroOneTimes'
        return f'{helper}({int(value)})'
    return RAND_RANGE.sub(sub, text)


# Q16.16 Fx (Wave 0): sys_math3d 2D cross products of coordinates (triangle
# point tests, determinants) overflow 32767; route them to the bounded
# shared-shift helpers in oot_math.cpp (fx_sq.h). Float build: same formula.
CROSS_PRODUCT = re.compile(r'\(\(([^()]+)\) \* \(([^()]+)\)\) - \(\(([^()]+)\) \* \(([^()]+)\)\)')


# Q16.16 Fx (Wave 0): every decomp `f32 <name>Sq` (field, local, parameter,
# return, pointer) holds a squared distance. Retype it to FxSq (fx_sq.h) so
# it keeps scaled terms and converts to plain Fx only explicitly.
STORED_SQUARE = re.compile(r'\bf32(\s*\*?\s*)(\w*Sq)\b')


def fix_stored_squares(rel, text, stats):
    if not (rel.endswith('.h') or (rel.endswith('.c') and not rel.endswith('.inc.c'))):
        return text
    text, n = STORED_SQUARE.subn(lambda m: 'FxSq' + m.group(1) + m.group(2), text)
    stats['macros'] += n
    stats['stored_squares'] = stats.get('stored_squares', 0) + n
    return text


def fix_cross_products(rel, text, stats):
    if rel != 'src/code/sys_math3d.c':
        return text
    text, n = CROSS_PRODUCT.subn(lambda m: 'OotFx_Det2(%s, %s, %s, %s)' % m.groups(), text)
    if n != 12:
        stats['problems'].append(f'{rel}: expected 12 cross products, found {n}')
    stats['macros'] += n
    return text


MACRO_REWRITES = {
    'include/z_math.h': [
        ('#define ABS(x) ((x) >= 0 ? (x) : -(x))', '#define ABS(x) OOT_SEL((x) >= 0, (x), -(x))'),
        ('#define CLAMP(x, min, max) ((x) < (min) ? (min) : (x) > (max) ? (max) : (x))',
         '#define CLAMP(x, min, max) OOT_SEL((x) < (min), (min), OOT_SEL((x) > (max), (max), (x)))'),
        ('#define CLAMP_MAX(x, max) ((x) > (max) ? (max) : (x))', '#define CLAMP_MAX(x, max) OOT_SEL((x) > (max), (max), (x))'),
        ('#define CLAMP_MIN(x, min) ((x) < (min) ? (min) : (x))', '#define CLAMP_MIN(x, min) OOT_SEL((x) < (min), (min), (x))'),
        # 32-bit Fx (Wave 0): squares stay pending terms (fx_sq.h) so hypot
        # and square comparisons scale instead of saturating past 181 units.
        ('#define SQ(x) ((x)*(x))', '#define SQ(x) OOT_SQ(x)'),
        ('#define IS_ZERO(f) (fabsf(f) < 0.008f)', '#define IS_ZERO(f) OOT_IS_ZERO(f)'),
        # Binangle conversions wrap through s32 -> s16 on N64; Fx saturates.
        ('#define DEG_TO_BINANG(degrees) (s16)TRUNCF_BINANG((degrees) * (0x8000 / 180.0f))',
         '#define DEG_TO_BINANG(degrees) OotFx_ScaleWrap16((degrees), 0xB60B61u)'),
        ('#define RAD_TO_BINANG(radians) (s16)TRUNCF_BINANG((radians) * (0x8000 / M_PI))',
         '#define RAD_TO_BINANG(radians) OotFx_ScaleWrap16((radians), 0x28BE60DCu)'),
        ('#define SQXZ(vec) ((vec).x * (vec).x + (vec).z * (vec).z)',
         '#define SQXZ(vec) (SQ((vec).x) + SQ((vec).z))'),
        ('#define SQXYZ(vec) ((vec).x * (vec).x + (vec).y * (vec).y + (vec).z * (vec).z)',
         '#define SQXYZ(vec) (SQ((vec).x) + SQ((vec).y) + SQ((vec).z))'),
    ],
    'include/ultra64/gbi.h': [
        ('#define MAX(a, b) ((a) > (b) ? (a) : (b))', '#define MAX(a, b) OOT_SEL((a) > (b), (a), (b))'),
        ('#define MIN(a, b) ((a) < (b) ? (a) : (b))', '#define MIN(a, b) OOT_SEL((a) < (b), (a), (b))'),
    ],
    # Saturn has no KSEG0: cart/work-RAM pointers are physical. gSegments[2]
    # = 0x02000000 keeps cart pointers identity (oot_core_api.cpp).
    'include/segmented_address.h': [
        ('#define SEGMENTED_TO_VIRTUAL(addr) (void*)(gSegments[SEGMENT_NUMBER(addr)] + SEGMENT_OFFSET(addr) + K0BASE)',
         '#define SEGMENTED_TO_VIRTUAL(addr) (void*)(gSegments[SEGMENT_NUMBER(addr)] + SEGMENT_OFFSET(addr))'),
    ],
    'include/ultra64/convert.h': [
        ('#define OS_K0_TO_PHYSICAL(x)    (u32)(((char*)(x)-0x80000000))', '#define OS_K0_TO_PHYSICAL(x)    (u32)(uintptr_t)(x)'),
        ('#define OS_PHYSICAL_TO_K0(x)    (void*)(((u32)(x)+0x80000000))', '#define OS_PHYSICAL_TO_K0(x)    (void*)(uintptr_t)(x)'),
    ],
    # 3.4e38 overflows Fx (Q39.24, ~5.5e11): Player talkActorDistance =
    # MAXFLOAT made every talk offer fail its distance test.
    'include/libc/math.h': [
        ('#define MAXFLOAT 3.40282347e+38f', '#define MAXFLOAT 1.0e11f'),
    ],
    # Fx keeps 16 fraction bits: a tiny reciprocal (1/|n| ~ 1e-4) loses
    # ~6%. Divide by the magnitude instead (same math, exact enough).
    'src/code/sys_math3d.c': [
        ('    return sqrt(Math3D_Vec3fMagnitudeSq(vec));',
         '    return sqrtf(SQXYZ(*vec)); /* Fx32: scaled hypot, no stored square */'),
        ('    perpendicularRatio = (((x0 - x1) * xDiff) + (y0 - y1) * yDiff) / distSq;',
         '    perpendicularRatio = OotFx_DotRatio2(x0 - x1, y0 - y1, xDiff, yDiff); /* Fx32 range */'),
        # Fx32: 3D cross product with one shared shift (dynamic poly normals).
        ('''    ret->x = (a->y * b->z) - (a->z * b->y);
    ret->y = (a->z * b->x) - (a->x * b->z);
    ret->z = (a->x * b->y) - (a->y * b->x);''',
         '''    OotFx_Cross3(a->x, a->y, a->z, b->x, b->y, b->z, &ret->x, &ret->y, &ret->z); /* Fx32 */'''),
        # Fx32: a sign test, not a product (tiny distances underflow to 0).
        ('    if ((pointADist * pointBDist) > 0.0f) {',
         '    if (((pointADist > 0.0f) && (pointBDist > 0.0f)) || ((pointADist < 0.0f) && (pointBDist < 0.0f))) {'),
        # Fx32: projection ratios (a . d) / |d|^2 with coordinate-sized terms.
        ('''    t = (((pos->x - line->point.x) * line->dir.x) + ((pos->y - line->point.y) * line->dir.y) +
         ((pos->z - line->point.z) * line->dir.z)) /
        dirVectorLengthSq;''',
         '''    t = OotFx_DotRatio3(pos->x - line->point.x, pos->y - line->point.y, pos->z - line->point.z,
                        line->dir.x, line->dir.y, line->dir.z); /* Fx32 range */'''),
        ('''    temp_f0_2 = ((((sphere->center.x - line->a.x) * lineDiff.x) + ((sphere->center.y - line->a.y) * lineDiff.y)) +
                 ((sphere->center.z - line->a.z) * lineDiff.z)) /
                lineLenSq;''',
         '''    temp_f0_2 = OotFx_DotRatio3(sphere->center.x - line->a.x, sphere->center.y - line->a.y,
                                sphere->center.z - line->a.z, lineDiff.x, lineDiff.y, lineDiff.z); /* Fx32 */'''),
        # Fx32: the XZ side quadratic squares squared coordinates; bounded roots.
        ('''    radSqDiff = SQXZ(cylToPtA) - cylRadiusSq;
    if (!IS_ZERO(2.0f * SQXZ(ptAToPtB))) {
        dot2AB = 2.0f * DOTXZ(ptAToPtB, cylToPtA);
        if (SQ(dot2AB) < 4.0f * SQXZ(ptAToPtB) * radSqDiff) {
            // Line's closest xz-approach is outside cylinder. No intersections.
            return 0;
        }
        if (SQ(dot2AB) - (4.0f * SQXZ(ptAToPtB) * radSqDiff) > zero) {
            sideIntA = sideIntB = 1;
        } else {
            // Line is tangent in xz-plane. At most 1 side intersection.
            sideIntA = 1;
            sideIntB = 0;
        }
        distCent2 = sqrtf(SQ(dot2AB) - (4.0f * SQXZ(ptAToPtB) * radSqDiff));
        if (sideIntA == 1) {
            // fraction of length along AB for side intersection closer to A
            fracA = (distCent2 - dot2AB) / (2.0f * SQXZ(ptAToPtB));
        }
        if (sideIntB == 1) {
            // fraction of length along AB for side intersection closer to B
            fracB = (-dot2AB - distCent2) / (2.0f * SQXZ(ptAToPtB));
        }
''',
         '''    radSqDiff = OotFx_RadSqDiffXZ(cylToPtA.x, cylToPtA.z, cyl->radius); /* Fx32 */
    if (!IS_ZERO(2.0f * SQXZ(ptAToPtB))) {
        /* Fx32: same roots from closest approach and half chord. */
        s32 sides = OotFx_LineVsCircleXZ(cylToPtA.x, cylToPtA.z, ptAToPtB.x, ptAToPtB.z, cyl->radius,
                                         &fracA, &fracB);
        if (sides == 0) {
            // Line's closest xz-approach is outside cylinder. No intersections.
            return 0;
        }
        sideIntA = 1;
        sideIntB = sides == 2;
'''),
        ('''        normMagInv = 1.0f / normMagnitude;
        *nx = normal.x * normMagInv;
        *ny = normal.y * normMagInv;
        *nz = normal.z * normMagInv;''',
         '''        *nx = normal.x / normMagnitude;
        *ny = normal.y / normMagnitude;
        *nz = normal.z / normMagnitude;'''),
        ('''    compAAlongB = ((lineAx * lineBx) + (lineAy * lineBy) + (lineAz * lineBz)) * scaleB;''',
         '''    compAAlongB = ((lineAx * lineBx) + (lineAy * lineBy) + (lineAz * lineBz)) / sqMag;'''),
        ('''                    (lineBz * (lineAPointA->z - lineBPointA->z))) *
                   scaleB;''',
         '''                    (lineBz * (lineAPointA->z - lineBPointA->z))) /
                   sqMag;'''),
    ],
    # Weak profiles (bridge_tables.cpp): an actor or effect that is not
    # imported has a NULL profile. Spawning it must fail like an overlay
    # that cannot load, never call through NULL.
    'src/code/z_actor.c': [
        ('    overlayEntry = &gActorOverlayTable[actorId];',
         '    if (actorId < 0 || actorId >= ACTOR_ID_MAX) return NULL;\n'
         '    overlayEntry = &gActorOverlayTable[actorId];'),
        ('    ZELDA_ARENA_FREE(actor, "../z_actor.c", 7242);',
         '    ZELDA_ARENA_FREE(actor, "../z_actor.c", 7242);\n'
         '    /* Internal Saturn pack profiles share the source client count. */\n'
         '    if (overlayEntry->vramStart == NULL && (u8)overlayEntry->numLoaded != 0)\n'
         '        overlayEntry->numLoaded--;'),
        # Fx32: the stored square scales by (1 - 0.8 w) instead of subtracting.
        ('''            adjDistSq =
                actor->xyzDistToPlayerSq - actor->xyzDistToPlayerSq * 0.8f * ((0x4000 - yawTempAbs) * (1.0f / 0x8000));''',
         '''            adjDistSq = actor->xyzDistToPlayerSq * (1.0f - 0.8f * ((0x4000 - yawTempAbs) * (1.0f / 0x8000)));'''),
        ('''        ACTOR_DEBUG_PRINTF(T("オーバーレイではありません\\n", "Not an overlay\\n"));

        profile = overlayEntry->profile;''',
         '''        ACTOR_DEBUG_PRINTF(T("オーバーレイではありません\\n", "Not an overlay\\n"));

        profile = overlayEntry->profile;
        if (profile == NULL) { /* oot-core: actor not imported */
            return NULL;
        }'''),
        # Talk diagnostics (oot_core_views.cpp row 17): why the last talk
        # offer failed. 1 player busy, 2 height, 3 talk distance, 4 range.
        ('''    if ((player->actor.flags & ACTOR_FLAG_TALK) || ((exchangeItemId != EXCH_ITEM_NONE) && Player_InCsMode(play)) ||
        (!actor->isLockedOn &&
         ((fabsf(actor->yDistToPlayer) > yRange) || (actor->xzDistToPlayer > player->talkActorDistance) ||
          (actor->xzDistToPlayer > xzRange)))) {
        return false;
    }''',
         '''    gOotCoreTalkCalls++;
    gOotCoreTalkWhy = (player->actor.flags & ACTOR_FLAG_TALK) ? 1
                      : actor->isLockedOn ? 0
                      : (fabsf(actor->yDistToPlayer) > yRange) ? 2
                      : (actor->xzDistToPlayer > player->talkActorDistance) ? 3
                      : (actor->xzDistToPlayer > xzRange) ? 4 : 0;
    if ((player->actor.flags & ACTOR_FLAG_TALK) || ((exchangeItemId != EXCH_ITEM_NONE) && Player_InCsMode(play)) ||
        (!actor->isLockedOn &&
         ((fabsf(actor->yDistToPlayer) > yRange) || (actor->xzDistToPlayer > player->talkActorDistance) ||
          (actor->xzDistToPlayer > xzRange)))) {
        return false;
    }'''),
        ('s32 Actor_OfferTalkExchange(Actor* actor, PlayState* play, f32 xzRange, f32 yRange, u32 exchangeItemId) {',
         'extern u32 gOotCoreTalkCalls, gOotCoreTalkWhy;\n'
         's32 Actor_OfferTalkExchange(Actor* actor, PlayState* play, f32 xzRange, f32 yRange, u32 exchangeItemId) {'),
        # Npc_UpdateTalking's on-screen test needs play->viewProjectionMtxF,
        # which the C camera never supplies (all decomp NPCs read offscreen
        # and never offered talk). Use the C camera yaw instead.
        ('''    Actor_GetScreenPos(play, actor, &x, &y);
    if ((x < 0) || (x > SCREEN_WIDTH) || (y < 0) || (y > SCREEN_HEIGHT)) {
        // Actor is offscreen
        return false;
    }''',
         '''    (void)x; (void)y;
    if (!OotCore_ActorInCameraView(play, actor)) {
        return false; /* oot-core: C camera view, not viewProjectionMtxF */
    }'''),
        ('s32 Npc_UpdateTalking(PlayState* play, Actor* actor, s16* talkState, f32 interactRange, NpcGetTextIdFunc getTextId,',
         's32 OotCore_ActorInCameraView(PlayState* play, Actor* actor);\n'
         's32 Npc_UpdateTalking(PlayState* play, Actor* actor, s16* talkState, f32 interactRange, NpcGetTextIdFunc getTextId,'),
        # Profiling hook (oot_core_views.cpp): time per actor update.
        ('                    actor->update(actor, play);',
         '                    OotCore_ProfiledUpdate(actor, play);'),
        ('void Actor_UpdateAll(PlayState* play, ActorContext* actorCtx) {',
         'void OotCore_ProfiledUpdate(Actor* actor, PlayState* play);\n'
         'void Actor_UpdateAll(PlayState* play, ActorContext* actorCtx) {'),
    ],
    # Arrow: baked sprite, so its skeleton keeps only the animation clock.
    'src/overlays/actors/ovl_En_Arrow/z_en_arrow.c': [
        ('#include "z_en_arrow.h"', '#include "z_en_arrow.h"\n#include "sprite_actor.h"'),
        ('SkelAnime_Init(play, &this->skelAnime, &gArrowSkel, &gArrow2_Anim, NULL, NULL, 0);',
         'OotCore_SpriteInitFlex(play, &this->skelAnime, NULL, &gArrow2_Anim, NULL, NULL, 0); /* oot-core */'),
        # At R_UPDATE_RATE=3 an arrow travels 225 units per source frame;
        # both its squared step and carry projection can exceed Q16.16.
        # Keep the source sign/minimum-step guards and project using the
        # existing scaled dot ratio, never a saturated stored square.
        ('''    temp_f12 = ((this->actor.world.pos.x - this->hitActor->world.pos.x) * posDiffLastFrame.x) +
               ((this->actor.world.pos.y - this->hitActor->world.pos.y) * posDiffLastFrame.y) +
               ((this->actor.world.pos.z - this->hitActor->world.pos.z) * posDiffLastFrame.z);

    if (!(temp_f12 < 0.0f)) {
        scale = Math3D_Vec3fMagnitudeSq(&posDiffLastFrame);

        if (!(scale < 1.0f)) {
            scale = temp_f12 / scale;''',
         '''    temp_f12 = OotFx_DotRatio3(this->actor.world.pos.x - this->hitActor->world.pos.x,
                                    this->actor.world.pos.y - this->hitActor->world.pos.y,
                                    this->actor.world.pos.z - this->hitActor->world.pos.z,
                                    posDiffLastFrame.x, posDiffLastFrame.y, posDiffLastFrame.z);

    if (!(temp_f12 < 0.0f)) {
        if (!(Math3D_Vec3fMagnitudeSq(&posDiffLastFrame) < 1.0f)) {
            scale = temp_f12; /* Fx32: dot / squared step, without saturation */'''),
    ],
    # Fx32: the same XZ side quadratic as Math3D_CylVsLineSeg.
    'src/code/z_collision_check.c': [
        ('''    radSqDiff = SQXZ(actorToItem) - SQ(radius);
    if (!IS_ZERO(SQXZ(itemStep))) {
        actorDotItemXZ = (2.0f * itemStep.x * actorToItem.x) + (2.0f * itemStep.z * actorToItem.z);
        if (SQ(actorDotItemXZ) < (4.0f * SQXZ(itemStep) * radSqDiff)) {
            return 0;
        }
        if (SQ(actorDotItemXZ) - (4.0f * SQXZ(itemStep) * radSqDiff) > zero) {
            intersect1 = intersect2 = true;
        } else {
            intersect1 = true;
            intersect2 = false;
        }
        closeDist = sqrtf(SQ(actorDotItemXZ) - (4.0f * SQXZ(itemStep) * radSqDiff));
        if (intersect1 == true) {
            frac1 = (closeDist - actorDotItemXZ) / (2.0f * SQXZ(itemStep));
        }
        if (intersect2 == true) {
            frac2 = (-actorDotItemXZ - closeDist) / (2.0f * SQXZ(itemStep));
        }
''',
         '''    radSqDiff = OotFx_RadSqDiffXZ(actorToItem.x, actorToItem.z, radius); /* Fx32 */
    if (!IS_ZERO(SQXZ(itemStep))) {
        /* Fx32: same roots from closest approach and half chord. */
        s32 sides = OotFx_LineVsCircleXZ(actorToItem.x, actorToItem.z, itemStep.x, itemStep.z, radius,
                                         &frac1, &frac2);
        if (sides == 0) {
            return 0;
        }
        intersect1 = true;
        intersect2 = sides == 2;
'''),
    ],
    'src/code/z_effect_soft_sprite.c': [
        ('    overlayEntry = &gEffectSsOverlayTable[type];',
         '    if (type < 0 || type >= EFFECT_SS_TYPE_MAX || sEffectSsInfo.tableSize <= 0) return;\n'
         '    overlayEntry = &gEffectSsOverlayTable[type];'),
        ('''                 "EffectSoftSprite2_makeEffect(): Not an overlay.\\n"));
        profile = overlayEntry->profile;''',
         '''                 "EffectSoftSprite2_makeEffect(): Not an overlay.\\n"));
        profile = overlayEntry->profile;
        if (profile == NULL) { /* oot-core: effect not imported */
            return;
        }'''),
    ],
    # Fx32 range audit (import_report FX RANGE): 65536.0f saturates, so these
    # constants must be single literals / wrapping binangle conversions.
    'src/code/sys_matrix.c': [
        ('* (1 / 65536.0f);', '* 1.52587890625e-05f; /* Fx32: 1 / 65536 as one literal */'),
    ],
    'src/overlays/actors/ovl_En_Md/z_en_md.c': [
        ('Math_FAtan2F(pathDiffX, pathDiffZ) * (65536.0f / (2 * M_PI))',
         'RAD_TO_BINANG(Math_FAtan2F(pathDiffX, pathDiffZ)) /* Fx32 */'),
    ],
    # Fx32: 1 / subdivLength (~1/750 in Field) is ~87 raw in Q16, 0.5% off:
    # position -> subdivision lookup drifted ~30 units from the registered
    # boundaries and lost floors there. Divide by the length instead.
    'src/code/z_bgcheck.c': [
        ('* colCtx->subdivLengthInv.x', '/ colCtx->subdivLength.x'),
        ('* colCtx->subdivLengthInv.y', '/ colCtx->subdivLength.y'),
        ('* colCtx->subdivLengthInv.z', '/ colCtx->subdivLength.z'),
        # Fx32: raw s16 normal (+-32767) x world position saturates before
        # the trailing * COLPOLY_NORMAL_FRAC: plane distances were garbage,
        # so line tests (LineVsPoly) almost never hit and point-plane
        # distances were wrong. Scale each component first (Claude
        # 2026-10-06; found by oot-core/tests/run_bg_port_probe.sh).
        ('(poly->normal.x * point->x + poly->normal.y * point->y + poly->normal.z * point->z) * COLPOLY_NORMAL_FRAC',
         '(COLPOLY_GET_NORMAL(poly->normal.x) * point->x + COLPOLY_GET_NORMAL(poly->normal.y) * point->y + '
         'COLPOLY_GET_NORMAL(poly->normal.z) * point->z)'),
        ('(poly->normal.x * posA->x + poly->normal.y * posA->y + poly->normal.z * posA->z) * COLPOLY_NORMAL_FRAC',
         '(COLPOLY_GET_NORMAL(poly->normal.x) * posA->x + COLPOLY_GET_NORMAL(poly->normal.y) * posA->y + '
         'COLPOLY_GET_NORMAL(poly->normal.z) * posA->z)'),
        # Fx32: the dyna bounding-sphere centre summed every transformed
        # vertex in Fx: 18 vertices at y 2500 already exceed Q16.16 and the
        # centre saturated (y 2500 -> 1819), so floors/walls of larger dyna
        # meshes went missing. Sum the stored integer vertices in s32 and
        # divide once (Claude 2026-10-06; oot-core/tests/bg_shim_scenario).
        ('    newCenterPoint.x = newCenterPoint.y = newCenterPoint.z = 0.0f;',
         '    newCenterPoint.x = newCenterPoint.y = newCenterPoint.z = 0.0f;\n'
         '    s32 centerSum[3] = { 0, 0, 0 }; /* Fx32: integer sum */'),
        ('        newCenterPoint.x += vtxT.x;\n'
         '        newCenterPoint.y += vtxT.y;\n'
         '        newCenterPoint.z += vtxT.z;',
         '        centerSum[0] += dyna->vtxList[*vtxStartIndex + i].x;\n'
         '        centerSum[1] += dyna->vtxList[*vtxStartIndex + i].y;\n'
         '        centerSum[2] += dyna->vtxList[*vtxStartIndex + i].z;'),
        ('    newCenterPoint.x *= numVtxInverse;\n'
         '    newCenterPoint.y *= numVtxInverse;\n'
         '    newCenterPoint.z *= numVtxInverse;',
         '    newCenterPoint.x = centerSum[0] / (s32)pbgdata->numVertices;\n'
         '    newCenterPoint.y = centerSum[1] / (s32)pbgdata->numVertices;\n'
         '    newCenterPoint.z = centerSum[2] / (s32)pbgdata->numVertices;'),
        # Fx32: dyna normals multiplied by 1 / |n|; for long edges that
        # reciprocal is a few raw units and truncates ~10% (flat 200-unit
        # floor got normal.y 0.906, dist -2719 at y 3000). Divide instead.
        ('            newNormal.x *= (1.0f / newNormMagnitude);\n'
         '            newNormal.y *= (1.0f / newNormMagnitude);\n'
         '            newNormal.z *= (1.0f / newNormMagnitude);',
         '            newNormal.x = newNormal.x / newNormMagnitude;\n'
         '            newNormal.y = newNormal.y / newNormMagnitude;\n'
         '            newNormal.z = newNormal.z / newNormMagnitude;'),
        ('(poly->normal.x * posB->x + poly->normal.y * posB->y + poly->normal.z * posB->z) * COLPOLY_NORMAL_FRAC',
         '(COLPOLY_GET_NORMAL(poly->normal.x) * posB->x + COLPOLY_GET_NORMAL(poly->normal.y) * posB->y + '
         'COLPOLY_GET_NORMAL(poly->normal.z) * posB->z)'),
    ],
    # Fx32: 1.0f / SHT_MAX is not a folded constant in Fx (a runtime divide
    # per use) and truncates to 2 raw; OOT_Q15_NORMAL rounds with shifts.
    'include/bgcheck.h': [
        ('#define COLPOLY_GET_NORMAL(n) ((n)*COLPOLY_NORMAL_FRAC)',
         '#define COLPOLY_GET_NORMAL(n) OOT_Q15_NORMAL(n)'),
    ],
    # Fx32: angle * (0x7FFF / M_PI) past pi wraps on N64 (s16 store).
    'src/code/sys_math.c': [
        ('    return sins((s16)(angle * (0x7FFF / M_PI))) * SHT_MINV;',
         '    return sins(OotFx_ScaleWrap16(angle, 0x28BE0F5Fu)) * SHT_MINV;'),
        ('    return coss((s16)(angle * (0x7FFF / M_PI))) * SHT_MINV;',
         '    return coss(OotFx_ScaleWrap16(angle, 0x28BE0F5Fu)) * SHT_MINV;'),
    ],
    # English only (gSaveContext.language = LANGUAGE_ENG): the Japanese
    # entry table would be 17 KB of blob for text that is never shown.
    'src/code/z_message.c': [
        ('CHECK_BTN_ALL(input->press.button, BTN_B) && !msgCtx->textUnskippable',
         'CHECK_BTN_ANY(input->press.button, BTN_A | BTN_B) /* fill current page only */'),

        ('player->naviActor->flags |= ACTOR_FLAG_TALK_OFFER_AUTO_ACCEPTED;',
         'if (player->naviActor != NULL) player->naviActor->flags |= ACTOR_FLAG_TALK_OFFER_AUTO_ACCEPTED; /* C Navi */'),
        ('''    /* Present */ DEFINE_MESSAGE_JPN(textId, type, yPos, jpnMessage, nesMessage, gerMessage, fraMessage)
#include "assets/text/message_data.h"''',
         '''    /* Present */ DEFINE_MESSAGE_JPN(textId, type, yPos, jpnMessage, nesMessage, gerMessage, fraMessage)
/* oot-core: Japanese table left empty (English only) */'''),
    ],
}


def fix_macros(rel, text, stats):
    for old, new in MACRO_REWRITES.get(rel, []):
        if old not in text:
            stats['problems'].append(f'{rel}: macro not found: {old}')
            continue
        text = text.replace(old, new)
        stats['macros'] += 1
    return text


def fix_sprite_actors(rel, text, stats):
    """Keep NPC action/talk/collision logic; remove invisible pose work."""
    generic = rel in {path for _, path in GENERIC_NPC_SOURCES}
    if not generic and rel != 'src/code/z_skelanime.c':
        return text

    def replace(old, new):
        nonlocal text
        if text.count(old) != 1:
            stats['problems'].append(f'{rel}: sprite hook not unique: {old}')
        else:
            text = text.replace(old, new)
            stats['macros'] += 1

    text = '#include "sprite_actor.h"\n' + text
    if generic:
        text = text.replace('SkelAnime_InitFlex(', 'OotCore_SpriteInitFlex(')
        text = text.replace('SkelAnime_Init(', 'OotCore_SpriteInit(')
        for name in ('EnIn_UpdateTracking', 'EnIn_Fidget', 'EnMa1_UpdateTracking', 'EnMa2_UpdateTracking'):
            pattern = r'(void ' + name + r'\([^;{}]*\) \{)'
            text = re.sub(pattern, r'\1\n    return; /* baked sprite has no head or torso */', text)
        if rel.endswith('z_en_in.c'):
            replace('void EnIn_Stagger(SkelAnime* skelAnime, EnIn* this, PlayState* play) {',
                    'void EnIn_Stagger(SkelAnime* skelAnime, EnIn* this, PlayState* play) {\n'
                    '    return; /* sprite has no root joint or skeletal motion */')
        if rel.endswith('z_en_cow.c'):
            replace('    if ((thisx->xzDistToPlayer < 150.0f) &&',
                    '    return; /* action/collision ran; no sprite head tracking */\n'
                    '    if ((thisx->xzDistToPlayer < 150.0f) &&')
        if rel.endswith('z_en_niw.c'):
            replace('void func_80AB5BF8(EnNiw* this, PlayState* play, s16 arg2) {',
                    '''void func_80AB5BF8(EnNiw* this, PlayState* play, s16 arg2) {
    /* Preserve the source's cosmetic clocks and random calls, without doing
     * any wing/head pose work for the baked sprite. Action timers 3+ remain
     * in the original action/update functions below. */
    if (this->timer1 == 0) {
        this->unk_298++;
        this->timer1 = 3;
        if (!(this->unk_298 & 1) && arg2 == 0)
            this->timer1 = Rand_ZeroFloat(30.0f);
    }
    if (this->timer2 == 0) {
        this->unk_29C = (this->unk_29C + 1) & 1;
        switch (arg2) {
            case 1: this->timer2 = 3; break;
            case 2: case 3: this->timer2 = 2; break;
            case 4: this->timer1 = 5; break;
            case 5: this->timer2 = 5; break;
        }
    }
    return; /* remaining source fields feed only EnNiw_OverrideLimbDraw */''')
        if rel.endswith('z_en_ta.c'):
            replace('    if (this->stateFlags & TALON_STATE_FLAG_TRACKING_PLAYER) {',
                    '    if (!OotCore_IsSprite(&this->skelAnime)) {\n'
                    '    if (this->stateFlags & TALON_STATE_FLAG_TRACKING_PLAYER) {')
            replace('    this->stateFlags &= ~(TALON_STATE_FLAG_TRACKING_PLAYER | TALON_STATE_FLAG_SUPPRESS_BLINK);',
                    '    } /* no head/torso tracking for sprites */\n'
                    '    this->stateFlags &= ~(TALON_STATE_FLAG_TRACKING_PLAYER | TALON_STATE_FLAG_SUPPRESS_BLINK);')
    else:
        replace('s32 SkelAnime_Update(SkelAnime* skelAnime) {',
                's32 SkelAnime_Update(SkelAnime* skelAnime) {\n'
                '    if (OotCore_IsSprite(skelAnime)) return OotCore_SpriteUpdate(skelAnime);')
        replace('                          u8 mode, f32 morphFrames, s8 taper) {',
                '                          u8 mode, f32 morphFrames, s8 taper) {\n'
                '    if (OotCore_IsSprite(skelAnime)) {\n'
                '        OotCore_SpriteChange(skelAnime, animation, playSpeed, startFrame, endFrame, mode);\n'
                '        return;\n    }')
        replace('void SkelAnime_Free(SkelAnime* skelAnime, PlayState* play) {',
                'void SkelAnime_Free(SkelAnime* skelAnime, PlayState* play) {\n'
                '    if (OotCore_IsSprite(skelAnime)) return;')
    return text


def fix_bgcheck_bounds(rel, text, stats):
    """Cheap conservative rejects; retain source collision/contact behavior."""
    if rel != 'src/code/z_bgcheck.c':
        return text
    text = '#include "bgcheck.h"\n#include "bgcheck_bounds.h"\n' + text

    def insert_at_body(name, line):
        nonlocal text
        pattern = r'(s32 ' + re.escape(name) + r'\([^{};]*\) \{)'
        text, count = re.subn(pattern, lambda m: m[1] + '\n' + line, text)
        if count != 1:
            stats['problems'].append(f'{rel}: bounds hook not unique: {name}')
        else:
            stats['macros'] += 1

    for name in ('CollisionPoly_CheckYIntersectApprox1', 'CollisionPoly_CheckYIntersect'):
        insert_at_body(name,
                      '    if (!OotCore_BgPolyNear(poly, vtxList, x, 0, z, chkDist, 5)) return false;')
    for name, coordinates, axes in (
            ('CollisionPoly_CheckXIntersectApprox', '0, y, z', 6),
            ('CollisionPoly_CheckZIntersectApprox', 'x, y, 0', 3)):
        insert_at_body(name,
                      f'    if (!OotCore_BgPolyNear(poly, vtxList, {coordinates}, 1, {axes})) return false;')

    # Both static-wall passes previously took sqrt before even checking the
    # plane distance or exclusion flags. Skip far triangles first and defer
    # sqrt until the source distance check has accepted a nearby candidate.
    first = text.index('s32 BgCheck_SphVsStaticWall(')
    last = text.index('\ns32 BgCheck_CheckStaticCeiling(', first)
    wall = text[first:last]
    old = '        nx = COLPOLY_GET_NORMAL(curPoly->normal.x);'
    new = '''        if (COLPOLY_VTX_CHECK_FLAGS_ANY(curPoly->flags_vIA, xpFlags) ||
            !OotCore_BgPolyNear(curPoly, vtxList, resultPos.x, pos->y, resultPos.z, radius, 7)) {
            if (curNode->next == SS_NULL) break;
            curNode = &colCtx->polyNodes.tbl[curNode->next];
            continue;
        }
''' + old
    if wall.count(old) != 2 or wall.count('        normalXZ = sqrtf(SQ(nx) + SQ(nz));\n') != 2:
        stats['problems'].append(f'{rel}: static-wall bounds hooks changed')
    else:
        wall = wall.replace(old, new)
        wall = wall.replace('        normalXZ = sqrtf(SQ(nx) + SQ(nz));\n', '')
        wall = wall.replace('        ASSERT(!IS_ZERO(normalXZ),',
                            '        normalXZ = sqrtf(SQ(nx) + SQ(nz));\n'
                            '        ASSERT(!IS_ZERO(normalXZ),')
        text = text[:first] + wall + text[last:]
        stats['macros'] += 2
    return text


def fix_mtxf(text, stats):
    def sub(m):
        col, row = MTXF_INDEX[m.group(2)]
        stats['mtxf'] += 1
        return f'{m.group(1)}mf[{col}][{row}]'
    return MTXF_ACCESS.sub(sub, text)


# Arrow_Fire/Ice/Light: Draw only renders (scrolling mesh + hit screen tint),
# so it and its overlay gfx (textures exist only as PNG here) are compiled
# out; the profile has no draw. Gameplay, timers and SFX stay source.
for _kind, _file, _line in (('Fire', 'fire', 682), ('Ice', 'ice', 676), ('Light', 'light', 664)):
    _model = '#include "assets/overlays/ovl_Arrow_%s/sModelDL.inc.c"\n};' % _kind
    _close = '    CLOSE_DISPS(play->state.gfxCtx, "../z_arrow_%s.c", %d);\n}' % (_file, _line)
    # The definition only; the forward declaration must stay visible.
    _draw = 'void Arrow%s_Draw(Actor* thisx, PlayState* %s) {' % (_kind, 'play2' if _kind == 'Fire' else 'play')
    MACRO_REWRITES['src/overlays/actors/ovl_Arrow_%s/z_arrow_%s.c' % (_kind, _file)] = [
        ('#define s1Tex_WIDTH 32', '#if 0 /* oot-core: draw-free, host sprite */\n#define s1Tex_WIDTH 32'),
        (_model, _model + '\n#endif'),
        ('    /**/ Arrow%s_Draw,' % _kind, '    /**/ NULL, /* oot-core: host draws ITMMAG */'),
        (_draw, '#if 0 /* oot-core */\n' + _draw),
        (_close, _close + '\n#endif /* oot-core */'),
    ]

# Saturn pose pass (Player migration, 2026-10-06): the Saturn renderer draws
# Link, but SkelAnime_DrawFlexLod + override/post-limb draw still run so limb
# matrices and every gameplay anchor (bodyPartsPos, weapon tips, held actor,
# sGetItemRefPos, feet) keep source timing. Only pure presentation is cut:
# fog flicker, lights, the STATE2_26 mirror copy (the normal pass runs last and
# owns the anchors), ice fragment, get-item model, masks/bunny ears, hover
# circle, eye/mouth/tunic segments, gauntlet/boot/bracelet DLs. Whole-function
# swaps keyed by the source span hash: a decomp change fails the import.
PLAYER_POSE_SPLIT = {
    'src/code/z_player_lib.c': [
        ('Player_DrawImpl', '6cc9cb1bfbd431f3', '''\
void Player_DrawImpl(PlayState* play, void** skeleton, Vec3s* jointTable, s32 dListCount, s32 lod, s32 tunic, s32 boots,
                     s32 face, OverrideLimbDrawOpa overrideLimbDraw, PostLimbDrawOpa postLimbDraw, void* data) {
    /* Saturn pose pass: face indices stay in jointTable[22] for the renderer. */
    sDListsLodOffset = lod * 2;
    SkelAnime_DrawFlexLod(play, skeleton, jointTable, dListCount, overrideLimbDraw, postLimbDraw, data, lod);
}
'''),
    ],
    'src/overlays/actors/ovl_player_actor/z_player.c': [
        ('Player_DrawGameplay', '7fd9cb1b0ce20562', '''\
void Player_DrawGameplay(PlayState* play, Player* this, s32 lod, Gfx* cullDList, OverrideLimbDrawOpa overrideLimbDraw) {
    /* Saturn pose pass: masks, bunny ears and hover circle are presentation. */
    Player_DrawImpl(play, this->skelAnime.skeleton, this->skelAnime.jointTable, this->skelAnime.dListCount, lod,
                    this->currentTunic, this->currentBoots, this->actor.shape.face, overrideLimbDraw,
                    Player_PostLimbDrawGameplay, this);
}
'''),
        ('Player_Draw', '6d78a878de6bda5d', '''\
void Player_Draw(Actor* thisx, PlayState* play2) {
    PlayState* play = play2;
    Player* this = (Player*)thisx;

    /* Saturn pose pass: source lod/override choice, one normal-pass walk. */
    if (!(this->stateFlags2 & PLAYER_STATE2_29)) {
        OverrideLimbDrawOpa overrideLimbDraw = Player_OverrideLimbDrawGameplayDefault;
        s32 lod;

        if ((this->csAction != PLAYER_CSACTION_NONE) || (this->actor.projectedPos.z < 160.0f)) {
            lod = 0;
        } else {
            lod = 1;
        }

        if (this->invincibilityTimer > 0) {
            this->damageFlickerAnimCounter += CLAMP(50 - this->invincibilityTimer, 8, 40);
        }

        if (this->unk_6AD != 0) {
            Vec3f projectedHeadPos;

            SkinMatrix_Vec3fMtxFMultXYZ(&play->viewProjectionMtxF, &this->actor.focus.pos, &projectedHeadPos);
            if (projectedHeadPos.z < -4.0f) {
                overrideLimbDraw = Player_OverrideLimbDrawGameplayFirstPerson;
            }
        } else if (this->stateFlags2 & PLAYER_STATE2_CRAWLING) {
            if (this->actor.projectedPos.z < 0.0f) {
                overrideLimbDraw = Player_OverrideLimbDrawGameplayCrawling;
            }
        }

        Player_DrawGameplay(play, this, lod, NULL, overrideLimbDraw);
    }
}
'''),
    ],
}


def fix_player_pose_split(rel, text, stats):
    for name, digest, body in PLAYER_POSE_SPLIT.get(rel, ()):
        head = f'\nvoid {name}('
        if text.count(head) != 1:
            raise ValueError(f'{rel}: Player pose split anchor changed: {name}')
        start = text.index(head) + 1
        end = text.index('\n}\n', start) + 3
        if hashlib.sha256(text[start:end].encode()).hexdigest()[:16] != digest:
            raise ValueError(f'{rel}: Player pose split source changed: {name}')
        text = text[:start] + body + text[end:]
        stats['player_pose_split'] = stats.get('player_pose_split', 0) + 1
    return text


def fix_player_migration(rel, text, stats):
    """Player-only Fx repairs; live SOURCES does not yet select this overlay."""
    if rel == 'src/code/z_player_lib.c':
        replacements = [
            # Hookshot/longshot reticle reach 38600/77600 is local units under
            # Link's 0.01 matrix: past Q16.16. Transform a 1000-unit local step
            # and extend it in world space (386/776 world units fit).
            ('    D_801260C8.z = arg2;\n    Matrix_MultVec3f(&D_801260C8, &sp80);\n',
             '    D_801260C8.z = 1000.0f;\n    Matrix_MultVec3f(&D_801260C8, &sp80);\n'
             '    sp80.x = sp8C.x + (sp80.x - sp8C.x) * arg2;\n'
             '    sp80.y = sp8C.y + (sp80.y - sp8C.y) * arg2;\n'
             '    sp80.z = sp8C.z + (sp80.z - sp8C.z) * arg2;\n'),
            ('? 38600.0f : 77600.0f', '? 38.6f : 77.6f'),
        ]
    elif rel == 'src/overlays/actors/ovl_player_actor/z_player.c':
        replacements = [
        # |s16 diff| / 32768 is exactly |diff| * 2 raw Q16.16 (32768 -> 1.0).
        ('temp = fabsf(sp1C) / 32768.0f;',
         'temp = Fx::raw((s32)ABS((s32)(s16)(arg2 - this->actor.shape.rot.y)) * 2);'),
        ('PLAYER_BODYPART_MAX - 0.1f', '(s32)PLAYER_BODYPART_MAX - 0.1f'),
        # Store the rumble accumulator in units /256. Only this function uses
        # unk_6A0 in source. Distance/16 is squared AFTER scaling, so neither
        # the square nor the threshold needs an out-of-range Fx conversion.
        ('f32 temp = 200000.0f - (this->closestSecretDistSq * 5.0f);',
         'f32 distance = sqrtf(this->closestSecretDistSq) / 16;\n'
         '        f32 temp = 781.25f - (SQ(distance) * 5.0f);'),
        ('this->unk_6A0 > 4000000.0f', 'this->unk_6A0 > 15625.0f'),
        ]
    else:
        return text
    for old, new in replacements:
        if text.count(old) != 1:
            raise ValueError(f'{rel}: Player migration patch anchor changed: {old}')
        text = text.replace(old, new)
    stats['player_migration'] = stats.get('player_migration', 0) + len(replacements)
    return text


def fixup(rel, text, stats):
    text = field_enemy_sources.adapt(rel, text)
    text = water_temple_sources.adapt(rel, text)
    if rel == 'include/ultra64/ultratypes.h':
        text, n = MTXF_DECL.subn('typedef union MtxF {\n    MtxF_t mf;\n} MtxF;', text)
        if n != 1:
            stats['problems'].append(f'{rel}: MtxF declaration not found')
    if rel == 'include/ultra64/xstdio.h':
        text, n = re.subn(r'LONG_DOUBLE_TYPE ld;', 'long long ld;', text)
        if n != 1:
            stats['problems'].append(f'{rel}: long double slot not found')
    text = fix_player_pose_split(rel, text, stats)  # raw source span hashes
    text = fix_anon_aggregates(rel, text, stats)
    text = fix_macros(rel, text, stats)
    text = fix_sprite_actors(rel, text, stats)
    text = fix_bgcheck_bounds(rel, text, stats)
    text = fix_rand_ranges(rel, text, stats)
    text = fix_cross_products(rel, text, stats)
    text = fix_player_migration(rel, text, stats)
    text = fix_stored_squares(rel, text, stats)
    text = fix_float_literals(text, stats, rel)
    return fix_mtxf(text, stats)


MESSAGE_SEG = 0x07000000
STAFF_DUMMY = 0x09000000


def message_symbols(oot):
    """Linker assignments for every _message_0xNNNN_nes symbol, taken from the
    ROM's own sNesMessageEntryTable in `code` (8-byte entries: u16 textId,
    u8 typePos, pad, segment address 0x07xxxxxx, ends with 0xFFFF). z_message
    only uses differences of these, so the absolute segment values work as
    offsets into nes_message_data_static. Staff (credits) symbols are dummies."""
    code = (oot / 'extracted' / VERSION / 'baserom' / 'code').read_bytes()
    table = None
    for off in range(0, len(code) - 16, 4):
        a = struct.unpack_from('>HBBI', code, off)
        b = struct.unpack_from('>HBBI', code, off + 8)
        if a[0] == 1 and b[0] == 2 and a[3] == MESSAGE_SEG and (b[3] >> 24) == 7:
            table = off
            break
    if table is None:
        raise SystemExit('ROM message table not found in baserom/code')
    entries = {}
    off = table
    while True:
        tid, _tp, _pad, seg = struct.unpack_from('>HBBI', code, off)
        entries[tid] = seg
        off += 8
        if tid == 0xFFFF:
            break
    # The build header (assets/text) adds 0xFFFC/0xFFFD after the extracted list.
    msg_h = (oot / 'extracted' / VERSION / 'text' / 'message_data.h').read_text(encoding='utf-8') +         (oot / 'assets' / 'text' / 'message_data.h').read_text(encoding='utf-8')
    staff_h = (oot / 'extracted' / VERSION / 'text' / 'message_data_staff.h').read_text(encoding='utf-8')
    lines = ['/* Generated by tools/oot_core_import.py from the ROM message table. */']
    missing = []
    for m in re.finditer(r'^DEFINE_MESSAGE(_NES|_JPN|_FFFC)?\((0x[0-9A-Fa-f]{4})', msg_h, re.M):
        kind, tid = m.group(1) or '', int(m.group(2), 16)
        name = '0x%04X' % tid
        if kind in ('', '_NES'):
            if tid in entries:
                lines.append(f'__message_{name}_nes = 0x{entries[tid]:08X};')
            else:
                missing.append(name)
        if kind in ('', '_JPN', '_FFFC'):
            lines.append(f'__message_{name}_jpn = 0x08000000;')
    for m in re.finditer(r'^DEFINE_MESSAGE\((0x[0-9A-Fa-f]{4})', staff_h, re.M):
        lines.append('__message_0x%04X_staff = 0x%08X;' % (int(m.group(1), 16), STAFF_DUMMY))
    return '\n'.join(lines) + '\n', missing


def write_if_changed(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding='utf-8', errors='replace') == text:
        return False
    path.write_text(text, encoding='utf-8')
    return True


def ocarina_restrictions_source(oot):
    """Original interface restrictions; no Saturn scene-number assumptions."""
    text = (oot / 'src/code/z_parameter.c').read_text(encoding='utf-8')
    body = text.split('static RestrictionFlags sRestrictionFlags[] = {', 1)[1].split('};', 1)[0]
    rows = re.findall(r'\{\s*(SCENE_\w+|0xFF),\s*0x[0-9A-F]+,\s*(0x[0-9A-F]+),\s*(0x[0-9A-F]+)\s*\}', body)
    if not rows or rows[-1][0] != '0xFF':
        raise ValueError('Source song restriction table changed')
    return ''.join('    {%s,%s,%s},\n' % row for row in rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--oot', type=pathlib.Path, default=OOT_DEFAULT)
    ap.add_argument('--out', type=pathlib.Path, default=OUT_DEFAULT)
    args = ap.parse_args()
    write_if_changed(args.out / 'environment_clock.inc',
                     clock_source(args.oot) + room_clock_source(args.oot) +
                     sun_song_source(args.oot) + destination_layer_source(args.oot) +
                     transition_clock_source(args.oot) + retained_weather_source(args.oot) +
                     sequence_source(args.oot) + clock_events_source(args.oot))
    write_if_changed(args.out / 'environment_player_gate.inc', player_clock_gate_source(args.oot))
    write_if_changed(args.out / 'ocarina_restrictions.inc', ocarina_restrictions_source(args.oot))

    stats = {'macros': 0, 'fxl': 0, 'anon': 0, 'mtxf': 0, 'files': 0, 'written': 0, 'problems': []}
    files = set()
    for tree in HEADER_TREES:
        files.update(p for p in (args.oot / tree).rglob('*.h'))
        files.update(p for p in (args.oot / tree).rglob('*.inc.c'))
    files.update(args.oot / s for s in SOURCES)
    files.update(args.oot / s for s in field_enemy_sources.SOURCES)
    files.update(args.oot / s for s in field_enemy_sources.EFFECT_SOURCES)
    files.update(args.oot / s for s in water_temple_sources.SPRITE_SOURCES)
    asset_root = args.oot / 'extracted' / VERSION
    for f in sorted(files):
        rel = f.relative_to(args.oot).as_posix()
        text = f.read_text(encoding='utf-8', errors='replace')
        text = fixup(rel, text, stats)
        dest = args.out / 'decomp' / rel
        if dest.suffix == '.c' and not rel.endswith('.inc.c'):
            dest = dest.with_suffix('.cpp')
        stats['files'] += 1
        stats['written'] += write_if_changed(dest, text)
    for s in SOURCES:
        if not (args.oot / s).exists():
            stats['problems'].append(f'missing source {s}')

    report = [
        f'oot-core import ({VERSION})',
        f'decomp: {args.oot}',
        f'assets: {asset_root} (included in place, not copied)',
        f'files: {stats["files"]}, rewritten: {stats["written"]}',
        f'MtxF field rewrites: {stats["mtxf"]}',
        f'anonymous aggregate rewrites: {stats["anon"]}',
        f'float literals wrapped: {stats["fxl"]}',
        'NOTE: ROM data holding IEEE floats (e.g. CutsceneCameraPoint.viewAngle)'
        ' must be converted to Fx offline before use.',
        'sources: ' + ', '.join(SOURCES),
    ] + [f'PROBLEM: {p}' for p in stats['problems']]
    fx_range = stats.get('fx_range', [])
    report.append(f'Fx range audit: {len(fx_range)} source literals >= {FX_LIMIT:.0f} saturate in Q16.16')
    report += [f'  FX RANGE: {r}' for r in fx_range]
    syms, missing = message_symbols(args.oot)
    write_if_changed(args.out / 'msg_syms.ld', syms)
    report.append(f'message symbols: {syms.count(chr(10)) - 1}, NES ids not in ROM table: {len(missing)}'
                  + (' (' + ' '.join(missing[:20]) + ')' if missing else ''))
    write_if_changed(args.out / 'import_report.txt', '\n'.join(report) + '\n')
    # The makefile includes this list, so SOURCES is the one place to add a file.
    mk = ['# Generated by tools/oot_core_import.py from SOURCES. Do not edit.',
          'OOT_CORE_DECOMP_SRCS = \\']
    mk += ['\t$(OOT_CORE_D)/' + str(pathlib.PurePosixPath(s).with_suffix('.cpp')) + ' \\'
           for s in SOURCES]
    enum_ids, sym_ids = object_ids(args.oot)
    built = {}
    for name in OBJECTS:
        oid = sym_ids[name]
        data, ph, drop = object_blob_sources(name, asset_root)
        stem = object_stem(oid)
        write_if_changed(args.out / 'objects' / (stem + '.cpp'), data)
        write_if_changed(args.out / 'objects' / (stem + '_ph.cpp'), ph)
        write_if_changed(args.out / 'objects' / (stem + '_ph.txt'), name + '\n' + '\n'.join(drop) + '\n')
        built[oid] = stem
    # The blob's list of data objects: Object_GetSlot returns -1 for one of
    # these when the scene did not load it (real behaviour); any other id is
    # a resident placeholder object (gameplay_keep etc.).
    write_if_changed(args.out / 'objects' / 'oot_objects_built.h',
                     '/* Generated by tools/oot_core_import.py OBJECTS. */\n'
                     'static const s16 sBuiltObjects[] = { '
                     + ', '.join('0x%03X' % i for i in sorted(built)) + ' };\n')
    write_if_changed(args.out / 'keep_ph.cpp', keep_ph_source())
    write_if_changed(args.out / 'keep_ph.txt', '\n'.join(KEEP_PLACEHOLDERS) + '\n')
    # Actor ids drawn by the Phase 2 shim (first entry -1: never empty).
    write_if_changed(args.out / 'generic_draw_ids.h',
                     '/* Generated by tools/oot_core_import.py GENERIC_DRAW. */\n-1,\n'
                     + ''.join(f'{a},\n' for a in GENERIC_DRAW))
    write_if_changed(args.out / 'generic_npc_ids.h',
                     '/* Generated by tools/oot_core_import.py GENERIC_NPC_SOURCES. */\n-1,\n'
                     + ''.join(f'{a},\n' for a, _ in GENERIC_NPC_SOURCES))
    scenes = []
    for name, scene_c in registered_scenes(asset_root):
        src = args.out / 'scenecol' / (name + '.cpp')
        objs = scene_objects(scene_c, built, enum_ids)
        text = scene_blob_source(scene_c, asset_root, objs)
        if scene_c.stem == 'spot00_scene':
            # Local Field retopology: PolyList/VtxList match SA.COL exactly.
            sys.path.insert(0, str(GAME / 'tools'))
            from field_retopo import scenecol_patch, record
            from layout_variants import build_document
            document = build_document()
            for old, new in scenecol_patch(scene_c, args.out / 'scenecol', document).items():
                if old not in text:
                    raise SystemExit(f'{scene_c}: {old} not in the scene blob')
                text = text.replace(old, new)
            record('ooc', document)
        write_if_changed(src, text)
        scenes.append(name)
    mk += ['', 'OOT_SCENECOL_NAMES = ' + ' '.join(scenes)]
    mk += ['', 'OOT_OBJECT_NAMES = ' + ' '.join(built[i] for i in sorted(built))]
    mk += ['', 'OOT_FIELD_ENEMY_SRCS = ' + ' '.join(
        '$(OOT_CORE_D)/' + str(pathlib.PurePosixPath(s).with_suffix('.cpp'))
        for s in field_enemy_sources.SOURCES + field_enemy_sources.EFFECT_SOURCES)]
    write_if_changed(args.out / 'sources.mk', '\n'.join(mk) + '\n\n')
    print('\n'.join(report))
    return 1 if stats['problems'] else 0


if __name__ == '__main__':
    sys.exit(main())
