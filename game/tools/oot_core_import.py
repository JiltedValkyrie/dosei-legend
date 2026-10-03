#!/usr/bin/env python3
"""Mirror zeldaret/oot decomp sources into game/build/oot-core/ for the SH-2 C++ build.

Only MECHANICAL C-vs-C++ fixups are allowed here, never logic edits:
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
import json
import pathlib
import re
import struct
import sys

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
    # Route step 5, Kokiri Forest batch 1.
    'src/overlays/actors/ovl_En_Md/z_en_md.c',
    'src/overlays/actors/ovl_En_Wonder_Item/z_en_wonder_item.c',
    'src/overlays/actors/ovl_En_Wonder_Talk2/z_en_wonder_talk2.c',
    'src/overlays/actors/ovl_Obj_Mure2/z_obj_mure2.c',
    'src/overlays/actors/ovl_En_Kanban/z_en_kanban.c',
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
    for room in room_files(path):
        rtext = room.read_text(encoding='utf-8')
        includes += [l for l in asset_includes(room, rtext) if l not in includes]
        layers = room_layers(room, rtext, asset_root)
        wanted = {n for n, _ in layers if n}
        body += ''.join('\n' + a.group(0) for a in ROOM_ACTORS.finditer(rtext) if a.group(1) in wanted)
        per_room.append(layers)
    if len(per_room) > 32:
        raise SystemExit(f'{path}: {len(per_room)} rooms > OOT_SCENE_MAX_ROOMS')
    num_layers = max((len(l) for l in per_room), default=1)
    rows = []
    for layers in per_room:
        layers = layers + [(None, False)] * (num_layers - len(layers))
        rows += [f'    {{ {n}, ARRAY_COUNT({n}), 1 }},' if n else f'    {{ 0, 0, {int(p)} }},'
                 for n, p in layers]
    table = ('static const OotSceneLayer oot_scene_layers[] = {\n'
             + ('\n'.join(rows) if rows else '    { 0, 0, 0 },') + '\n};\n')
    path_defs, path_layers = scene_paths(path, text, asset_root)
    body += path_defs
    path_rows = [f'    {{ {n}, 0, 1 }},' if n else f'    {{ 0, 0, {int(p)} }},' for n, p in path_layers]
    table += ('static const OotSceneLayer oot_scene_paths[] = {\n' + '\n'.join(path_rows) + '\n};\n')
    header = ('extern "C" const OotSceneBlob oot_scene_blob'
              ' __attribute__((section(".scene_header"), used)) = {\n'
              f'    &{prefix}_Col, {len(per_room)}, {num_layers}, oot_scene_layers,\n'
              f'    oot_scene_objects, {len(objects)},\n'
              f'    oot_scene_paths, {len(path_layers)},\n}};\n')
    objs = ('static const unsigned short oot_scene_objects[] = { '
            + (', '.join('0x%03X' % o for o in objects) if objects else '0') + ' };\n')
    return ('// Generated by tools/oot_core_import.py from ' + path.name
            + ' (collision + room actor lists, all layers).\n'
            + '\n'.join(includes) + '\n#include "array_count.h"\n#include "oot_scene_blob.h"\n\n'
            + body + '\n' + table + objs + header)


# Decomp objects built as data blobs (<O><id hex>.OOB): what the imported
# actors read from their object segment (skeletons, limbs, animations).
OBJECTS = ['object_os_anime', 'object_km1', 'object_kw1', 'object_fa', 'object_md', 'object_kanban']
# Definitions kept verbatim; everything else (Gfx, Vtx, textures, palettes)
# becomes a one-element placeholder: the draw shim keys on its address.
OBJECT_KEEP_TYPES = {'AnimationHeader', 'JointIndex', 's16', 'StandardLimb', 'LodLimb',
                     'FlexSkeletonHeader', 'SkeletonHeader', 'void*', 'LinkAnimationHeader'}
OBJECT_DEF = re.compile(r'^((?:const )?[A-Za-z_][A-Za-z0-9_]*\*?) ([A-Za-z_][A-Za-z0-9_]*)(\[[^\]]*\])? = \{\n'
                        r'(?:.*?\n)*?\};\n', re.M)


def object_ids(oot):
    """Object enum name -> id, in object_table.h order."""
    text = (oot / 'include' / 'tables' / 'object_table.h').read_text(encoding='utf-8')
    names = re.findall(r'^\s*/\* (0x[0-9A-Fa-f]+) \*/ DEFINE_OBJECT\w*\((\w+), (\w+)\)', text, re.M)
    return {enum: int(i, 16) for i, _sym, enum in names}, {sym: int(i, 16) for i, sym, _e in names}


def object_blob_sources(name, asset_root):
    """(data .cpp, placeholder .cpp) for one object. Data keeps the object's
    own header (limb enums) and the kept definitions verbatim; placeholders
    are in a second unit without the header, so `u64 x[1]` never clashes
    with the header's real array size."""
    path = asset_root / 'assets' / 'objects' / name / (name + '.c')
    text = path.read_text(encoding='utf-8')
    keep, drop = [], []
    for m in OBJECT_DEF.finditer(text):
        typ, sym = m.group(1).replace('const ', ''), m.group(2)
        if typ in OBJECT_KEEP_TYPES:
            keep.append(m.group(0))
        else:
            drop.append(sym)
    includes = asset_includes(path, text)
    data = ('// Generated by tools/oot_core_import.py from ' + path.name + ' (data only).\n'
            + '\n'.join(includes) + '\n\n' + '\n'.join(keep))
    ph = ('// Generated by tools/oot_core_import.py: ' + name + ' display lists and textures,\n'
          '// one word each (draw-shim keys, never read).\n'
          'typedef unsigned long long u64;\n' + ''.join(f'u64 {s}[1];\n' for s in drop))
    return data, ph


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


def fix_float_literals(text, stats):
    out = []
    pos = 0
    skips = sorted([m.span() for m in SKIP_TOKEN.finditer(text)] +
                   [m.span() for m in DIRECTIVE.finditer(text)])

    def wrap(chunk):
        def sub(m):
            stats['fxl'] += 1
            return f'FXL({m.group(0)})'
        return FLOAT_LIT.sub(sub, chunk)
    for start, end in skips:
        if start < pos:
            continue
        out.append(wrap(text[pos:start]))
        out.append(text[start:end])
        pos = end
    out.append(wrap(text[pos:]))
    return ''.join(out)


MACRO_REWRITES = {
    'include/z_math.h': [
        ('#define ABS(x) ((x) >= 0 ? (x) : -(x))', '#define ABS(x) OOT_SEL((x) >= 0, (x), -(x))'),
        ('#define CLAMP(x, min, max) ((x) < (min) ? (min) : (x) > (max) ? (max) : (x))',
         '#define CLAMP(x, min, max) OOT_SEL((x) < (min), (min), OOT_SEL((x) > (max), (max), (x)))'),
        ('#define CLAMP_MAX(x, max) ((x) > (max) ? (max) : (x))', '#define CLAMP_MAX(x, max) OOT_SEL((x) > (max), (max), (x))'),
        ('#define CLAMP_MIN(x, min) ((x) < (min) ? (min) : (x))', '#define CLAMP_MIN(x, min) OOT_SEL((x) < (min), (min), (x))'),
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
    # Weak profiles (bridge_tables.cpp): an actor or effect that is not
    # imported has a NULL profile. Spawning it must fail like an overlay
    # that cannot load, never call through NULL.
    'src/code/z_actor.c': [
        ('''        ACTOR_DEBUG_PRINTF(T("オーバーレイではありません\\n", "Not an overlay\\n"));

        profile = overlayEntry->profile;''',
         '''        ACTOR_DEBUG_PRINTF(T("オーバーレイではありません\\n", "Not an overlay\\n"));

        profile = overlayEntry->profile;
        if (profile == NULL) { /* oot-core: actor not imported */
            return NULL;
        }'''),
    ],
    'src/code/z_effect_soft_sprite.c': [
        ('''                 "EffectSoftSprite2_makeEffect(): Not an overlay.\\n"));
        profile = overlayEntry->profile;''',
         '''                 "EffectSoftSprite2_makeEffect(): Not an overlay.\\n"));
        profile = overlayEntry->profile;
        if (profile == NULL) { /* oot-core: effect not imported */
            return;
        }'''),
    ],
    # English only (gSaveContext.language = LANGUAGE_ENG): the Japanese
    # entry table would be 17 KB of blob for text that is never shown.
    'src/code/z_message.c': [
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


def fix_mtxf(text, stats):
    def sub(m):
        col, row = MTXF_INDEX[m.group(2)]
        stats['mtxf'] += 1
        return f'{m.group(1)}mf[{col}][{row}]'
    return MTXF_ACCESS.sub(sub, text)


def fixup(rel, text, stats):
    if rel == 'include/ultra64/ultratypes.h':
        text, n = MTXF_DECL.subn('typedef union MtxF {\n    MtxF_t mf;\n} MtxF;', text)
        if n != 1:
            stats['problems'].append(f'{rel}: MtxF declaration not found')
    if rel == 'include/ultra64/xstdio.h':
        text, n = re.subn(r'LONG_DOUBLE_TYPE ld;', 'long long ld;', text)
        if n != 1:
            stats['problems'].append(f'{rel}: long double slot not found')
    text = fix_anon_aggregates(rel, text, stats)
    text = fix_macros(rel, text, stats)
    text = fix_float_literals(text, stats)
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


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--oot', type=pathlib.Path, default=OOT_DEFAULT)
    ap.add_argument('--out', type=pathlib.Path, default=OUT_DEFAULT)
    args = ap.parse_args()

    stats = {'macros': 0, 'fxl': 0, 'anon': 0, 'mtxf': 0, 'files': 0, 'written': 0, 'problems': []}
    files = set()
    for tree in HEADER_TREES:
        files.update(p for p in (args.oot / tree).rglob('*.h'))
        files.update(p for p in (args.oot / tree).rglob('*.inc.c'))
    files.update(args.oot / s for s in SOURCES)
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
        data, ph = object_blob_sources(name, asset_root)
        stem = object_stem(oid)
        write_if_changed(args.out / 'objects' / (stem + '.cpp'), data)
        write_if_changed(args.out / 'objects' / (stem + '_ph.cpp'), ph)
        built[oid] = stem
    # The blob's list of data objects: Object_GetSlot returns -1 for one of
    # these when the scene did not load it (real behaviour); any other id is
    # a resident placeholder object (gameplay_keep etc.).
    write_if_changed(args.out / 'objects' / 'oot_objects_built.h',
                     '/* Generated by tools/oot_core_import.py OBJECTS. */\n'
                     'static const s16 sBuiltObjects[] = { '
                     + ', '.join('0x%03X' % i for i in sorted(built)) + ' };\n')
    scenes = []
    for name, scene_c in registered_scenes(asset_root):
        src = args.out / 'scenecol' / (name + '.cpp')
        objs = scene_objects(scene_c, built, enum_ids)
        write_if_changed(src, scene_blob_source(scene_c, asset_root, objs))
        scenes.append(name)
    mk += ['', 'OOT_SCENECOL_NAMES = ' + ' '.join(scenes)]
    mk += ['', 'OOT_OBJECT_NAMES = ' + ' '.join(built[i] for i in sorted(built))]
    write_if_changed(args.out / 'sources.mk', '\n'.join(mk) + '\n\n')
    print('\n'.join(report))
    return 1 if stats['problems'] else 0


if __name__ == '__main__':
    sys.exit(main())
