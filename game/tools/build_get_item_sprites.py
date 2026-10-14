"""Bake source Player get-item recipes into complete scene-local SPR2 atlases.

The source GID is the key. Items are loaded before actors/cutscenes, so rewards
and chest CD audio never trigger a mesh or texture read in live playback.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

import build_npc_sprites as sprites
import build_sprite_keys as archives
import scene_pack_actors as packs


def item_table(oot):
    text = (oot / 'src/overlays/actors/ovl_player_actor/z_player.c').read_text(encoding='utf-8')
    start = text.index('static GetItemEntry sGetItemTable[]')
    table = text[start:text.index('\n};', start)]
    rows = re.findall(r'//\s*(GI_\w+)\s*\n\s*GET_ITEM\(\w+,\s*(OBJECT_\w+),\s*(GID_\w+)', table)
    if len(rows) != 123 or table.count('GET_ITEM_NONE') != 2:
        raise ValueError('Source Player get-item table changed: ' + str(len(rows)))
    result = {gi: (obj.lower(), gid) for gi, obj, gid in rows}
    result.update(GI_ICE_TRAP=('gameplay_keep', 'GID_MAX'), GI_TEXT_0=('gameplay_keep', 'GID_MAX'))
    return result


def draw_recipes(oot):
    text = (oot / 'src/code/z_draw.c').read_text(encoding='utf-8')
    ids = dict((name, int(value, 16)) for value, name in re.findall(
        r'/\* (0x[0-9A-F]+) \*/ (GID_\w+)', (oot / 'include/item.h').read_text(encoding='utf-8')))
    table = {gid: (draw, lists) for gid, draw, lists in re.findall(
        r'//\s*(GID_\w+)\s*\n\s*\{\s*(\w+),\s*\{([^{}]*)\}', text)}
    result = {}
    # EnExItem draws the token's object_st recipe directly, outside Player's
    # get-item table (whose token uses object_gi_sutaru). EnGirlA shelves
    # draw their own object/GID rows (sold-out sign, bottled fairy).
    girla = (oot / 'src/overlays/actors/ovl_En_GirlA/z_en_girla.c').read_text(encoding='utf-8')
    shelf = [(obj.lower(), gid) for obj, gid in re.findall(r'\{\s*(OBJECT_\w+),\s*(GID_\w+),', girla)]
    if len(shelf) < 50:
        raise ValueError('Source EnGirlA shelf table changed: ' + str(len(shelf)))
    for obj, gid in (*item_table(oot).values(), ('object_st', 'GID_SKULL_TOKEN_2'), *shelf):
        if gid in result:
            continue
        if gid == 'GID_MAX':  # source ice trap has no get-item mesh
            continue
        draw, words = table[gid]
        lists = tuple(re.findall(r'\b(?:gGi\w+|g\w+DL|object_\w+DL_\w+)\b', words))
        start = text.index('void ' + draw + '(PlayState* play, s16 giDrawId) {')
        body = text[start:text.index('\n}', start)]
        order = [int(n) for n in re.findall(r'(?:sDrawItemTable\[giDrawId\]\.|entry->)dlists\[(\d+)\]', body)]
        if not order or max(order) >= len(lists):
            raise ValueError('Unsupported get-item draw recipe: ' + gid)
        # Runtime zero means no animation; reserve it, matching Player's
        # unk_862 = giDrawId + 1 representation (GID_BOTTLE is zero).
        result[gid] = (ids[gid] + 1, obj, tuple(lists[i] for i in order))
    return result


def scene_items(oot, path, children):
    table = item_table(oot)
    player = (oot / 'src/overlays/actors/ovl_player_actor/z_player.c').read_text(encoding='utf-8')
    exchange = player[player.index('GI_ZELDAS_LETTER,       // EXCH_ITEM_'):]
    exchange = exchange[:exchange.index('\n};')]
    # Carried exchange items remain showable in every room; rewards include
    # actor-local tables and every authored chest across ages/layers.
    names = set(re.findall(r'\bGI_\w+', exchange)) | {'GI_RUPEE_BLUE', 'GI_HEART_CONTAINER', 'GI_HEART_PIECE'}
    direct = set()
    import oot_core_import as imp
    for name in packs.scene_pack(path, children):
        # Scan the compiled adaptation: restricted source cases (for example
        # unadmitted DemoEffect medallion types) cannot show their items.
        stats = dict(macros=0, fxl=0, anon=0, mtxf=0, files=0, written=0, problems=[])
        source = imp.fixup(packs.source(name), (oot / packs.source(name)).read_text(encoding='utf-8'), stats)
        names.update(re.findall(r'\bGI_\w+', source))
        direct.update(re.findall(r'\bGID_\w+', source))
        if name in ('En_G_Switch', 'En_Ex_Ruppy'):
            direct.update('GID_RUPEE_' + colour for colour in ('GREEN', 'BLUE', 'RED', 'PURPLE', 'GOLD'))
    keys = list(table)
    for actors in path.parent.glob('*ActorEntryList.inc.c'):
        for row in re.findall(r'\{\s*ACTOR_EN_BOX,.*?\n\s*\}', actors.read_text(encoding='utf-8'), re.S):
            row = re.sub(r'//[^\n]*', '', row)
            row = re.sub(r'/\*.*?\*/', '', row, flags=re.S)
            value = re.search(r'([^,{}]+),\s*\}$', row)
            if not value:
                raise ValueError('Unparsed chest entry: ' + row)
            params = int(value[1].strip(), 0)
            gi = (params >> 5) & 0x7f
            if gi and gi <= len(keys):
                names.add(keys[gi - 1])
    return ({table[name][1] for name in names if name in table} | direct) - {'GID_MAX'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, required=True)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument('--out', type=Path, default=root / 'build/get-item-sprites')
    parser.add_argument('--cd', type=Path, default=root / 'build/cd')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    args.cd.mkdir(parents=True, exist_ok=True)
    rom = args.oot / 'baseroms/ntsc-1.2'
    keep = sprites.link.read_object(args.oot, 'gameplay_keep', rom)
    recipes = draw_recipes(args.oot)
    sheets = {}
    for gid, (key, obj, lists) in recipes.items():
        dest = args.out / (gid + '.SPR')
        data = sprites.link.read_object(args.oot, obj, rom)
        xml = args.oot / 'assets/xml/objects' / (obj + '.xml')
        digest = hashlib.sha256(data + xml.read_bytes() + repr(lists).encode() +
                                Path(__file__).read_bytes() + Path(sprites.__file__).read_bytes()).hexdigest()
        stamp = dest.with_suffix('.stamp')
        if not (dest.exists() and stamp.exists() and stamp.read_text() == digest):
            binary = args.out / (gid + '.BIN')
            _, local = sprites.static_skin(obj, data, xml, keep, lists, binary)
            faces, _, _ = sprites.read_model(binary, None)
            poses = [[tuple(v * .2 for v in point) for point in local]]
            sprites.write_sprite(faces, poses, [0], dest, dest.with_suffix('.png'),
                                 sprites.layout_of([poses], 28), 1)
            stamp.write_text(digest)
        sheets[gid] = (key, dest.read_bytes())
    import oot_core_import as imp
    import asset_names
    registration = {asset_names.scene_stem(row['index']): row['index']
                    for row in json.loads(imp.SCENE_TABLE_JSON.read_text())['scenes']}
    children = packs.child_spawns(args.oot)
    report = []
    for name, path in imp.registered_scenes(args.oot / 'extracted/ntsc-1.2'):
        gids = scene_items(args.oot, path, children)
        absent = gids - sheets.keys()
        if absent:
            raise ValueError(name + ': missing reward recipes ' + str(absent))
        payload = archives.pack(0, [sheets[gid] for gid in sorted(gids)])
        file = 'I%02X.SP2' % registration[name]
        (args.cd / file).write_bytes(payload)
        report.append(dict(scene=name, file=file, gids=sorted(gids), bytes=len(payload), heap_bytes=len(payload)+20))
    (args.out / 'budget.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Get-item atlases:', len(report), 'scenes;', len(sheets), 'source recipes; peak',
          max(r['bytes'] for r in report), 'bytes')


if __name__ == '__main__':
    main()
