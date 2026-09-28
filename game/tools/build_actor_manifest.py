#!/usr/bin/env python
"""M3a actor manifest: EVERY actor of Kokiri Forest and its six interiors.

Reads the US 1.2 scene/room segments for all header layers (main = child
day, then the 0x18 alternate-header list: child night, adult day, adult
night, cutscenes). Nothing is filtered: each record says whether the slice
runtime currently ports that actor (build_actors.py), so an unsupported or
dropped actor is visible instead of silently missing.

Writes docs/M3A_ACTOR_MANIFEST.md. Offline tool; runtime data untouched.
"""
import argparse
import pathlib
import re
import struct
import sys

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parent / 'shared/tools'))
import build_kokiri_scene as source

SCENES = ('spot04', 'link_home', 'kokiri_home', 'kokiri_home3', 'kokiri_home4',
          'kokiri_home5', 'kokiri_shop')
SCENE_NAMES = {
    'spot04': 'Kokiri Forest', 'link_home': "Link's House",
    'kokiri_home': 'Know-It-All Brothers', 'kokiri_home3': 'House of Twins',
    'kokiri_home4': "Mido's House", 'kokiri_home5': "Saria's House",
    'kokiri_shop': 'Kokiri Shop'}
LAYERS = ('child day', 'child night', 'adult day', 'adult night')
# Ported by build_actors.py today (id -> slice note). Item_00 only for rupees.
SUPPORTED = {0x0163: 'NPC stand-in', 0x016D: 'NPC stand-in', 0x0146: 'NPC stand-in',
             0x0125: 'grass', 0x0141: 'sign', 0x000A: 'chest (sword only)',
             0x0112: 'wonder item (rupee modes)', 0x003D: 'shopkeeper',
             0x0130: 'boulder', 0x00C7: 'Karebaba', 0x0015: 'rupee only'}


def enum(path, first):
    """/* 0xNN */ NAME, entries of the enum containing `first`."""
    text = path.read_text()
    start = text.index(first)
    block = text[text.rfind('{', 0, start):text.index('}', start)]
    return {int(v, 16): n for v, n in re.findall(r'/\* 0x([0-9A-F]+) \*/ (\w+)', block)}


# Scenes whose actors build_actors.py loads at runtime today.
LOADED_SCENES = ('spot04', 'kokiri_shop')


def port_note(prefix, aid, var):
    if prefix not in LOADED_SCENES:
        return ''
    if aid == 0x0015 and (var & 0xFF) not in (0, 1):
        return ''                       # only green/blue rupees are emitted
    if aid == 0x000A and ((var >> 5) & 0x7F) != 0x27:
        return ''
    return SUPPORTED.get(aid, '')


def table(path, macro):
    names = {}
    for m in re.finditer(r'/\* 0x([0-9A-F]+) \*/ %s\w*\((\w+)' % macro, path.read_text()):
        names[int(m.group(1), 16)] = m.group(2)
    return names


def header(data, base, seg):
    """Commands of one header starting at `base`, in order."""
    out = []
    for pos in range(base, min(len(data), base + 0x400), 8):
        cmd = data[pos]
        out.append((cmd, data[pos + 1], struct.unpack_from('>I', data, pos + 4)[0]))
        if cmd == 0x14:
            break
    return out


def alt_headers(data, cmds, seg):
    """0x18 list: offsets of layers 1.. (None = not present)."""
    for cmd, _, ptr in cmds:
        if cmd == 0x18:
            base, out = ptr & 0xFFFFFF, []
            for i in range(20):
                if base + 4 * i + 4 > len(data):
                    break
                word = struct.unpack_from('>I', data, base + 4 * i)[0]
                if word and word >> 24 != seg:
                    break
                if word and (word & 0xFFFFFF) >= len(data):
                    break
                out.append(word & 0xFFFFFF if word else None)
            while out and out[-1] is None:
                out.pop()
            return out
    return []


def layer_header(data, cmds, seg, layer):
    """Header used for `layer`, with OoT's fallback (adult night -> adult day,
    any other missing layer -> main header). Returns (base, note)."""
    if layer == 0:
        return 0, ''
    alts = alt_headers(data, cmds, seg)
    if layer - 1 < len(alts) and alts[layer - 1] is not None:
        return alts[layer - 1], ''
    if layer == 3 and len(alts) >= 2 and alts[1] is not None:
        return alts[1], 'falls back to adult day'
    return 0, 'falls back to main header'


GI, ITEM00 = {}, {}


def decode(aid, var, names):
    n = names.get(aid, '')
    if n == 'En_Box':
        gi = (var >> 5) & 0x7F
        return '%s, chest flag 0x%02X, type %d' % (GI.get(gi, 'GI 0x%02X' % gi), var & 0x1F, var >> 12)
    if n == 'En_Item00':
        return '%s, collect flag 0x%02X' % (ITEM00.get(var & 0xFF, 'drop %d' % (var & 0xFF)),
                                             (var >> 8) & 0x3F)
    if n == 'En_Wonder_Item':
        return 'mode %d, drop %d, switch 0x%02X' % (var >> 11, (var >> 6) & 31, var & 0x3F)
    if n == 'En_Ko':
        return 'type %d' % (var & 0xFF)
    if n in ('En_Kusa', 'Obj_Tsubo', 'En_Ishi'):
        return 'var 0x%04X (drop bits need source audit)' % var
    return ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--oot', type=pathlib.Path,
                    default=pathlib.Path('D:/Workspace-Claude/game-decomps/n64/oot'))
    ap.add_argument('--rom-dir', type=pathlib.Path)
    ap.add_argument('--out', type=pathlib.Path, default=HERE / 'docs/M3A_ACTOR_MANIFEST.md')
    args = ap.parse_args()
    actors = table(args.oot / 'include/tables/actor_table.h', 'DEFINE_ACTOR')
    objects = table(args.oot / 'include/tables/object_table.h', 'DEFINE_OBJECT')
    GI.update(enum(args.oot / 'include/item.h', 'GI_SWORD_KOKIRI'))
    ITEM00.update(enum(args.oot / 'include/z_en_item00.h', 'ITEM00_RUPEE_GREEN'))

    lines = ['# M3a actor manifest (generated)', '',
             'Generated by `tools/build_actor_manifest.py` from US 1.2 ROM segments.',
             'All header layers, nothing filtered. "Port" = current slice support',
             '(build_actors.py); blank = NOT ported. Positions are source units.',
             'Cutscene layers (4+) are counted only. Do not edit by hand.', '']
    unsupported = {}
    for prefix in SCENES:
        segs = source.extract(args.oot, args.rom_dir, prefix=prefix)
        scene = segs[prefix + '_scene']
        rooms = sorted((k for k in segs if '_room_' in k), key=lambda k: int(k.rsplit('_', 1)[1]))
        scmds = header(scene, 0, 0x02)
        salts = alt_headers(scene, scmds, 0x02)
        lines += ['## %s (`%s`)' % (SCENE_NAMES[prefix], prefix), '',
                  'Scene alternate headers: %d (%d cutscene layers).' %
                  (len(salts), max(0, len(salts) - 3)), '']
        for layer, lname in enumerate(LAYERS):
            sbase, snote = layer_header(scene, scmds, 0x02, layer)
            cmds = header(scene, sbase, 0x02)
            lines += ['### %s%s' % (lname, ' (%s)' % snote if snote else ''), '']
            for cmd, count, ptr in cmds:
                if cmd == 0x0E:     # transition actors (doors)
                    for i in range(count):
                        fr, fc, br, bc, aid, x, y, z, ry, var = struct.unpack_from(
                            '>bbbbHhhhhH', scene, (ptr & 0xFFFFFF) + 16 * i)
                        aid &= 0xFFF
                        lines.append('- transition %s 0x%04X rooms %d/%d pos (%d,%d,%d) '
                                     'params 0x%04X' % (actors.get(aid, '?'), aid, fr, br,
                                                        x, y, z, var))
                if cmd == 0x0D:
                    lines.append('- scene paths present (0x0D)')
            lines.append('')
            lines += ['| room | actor | id | params | pos | yaw | decoded | port |',
                      '|---|---|---|---|---|---|---|---|']
            objs = []
            for rname in rooms:
                room = segs[rname]
                rcmds = header(room, 0, 0x03)
                rbase, _ = layer_header(room, rcmds, 0x03, layer)
                for cmd, count, ptr in header(room, rbase, 0x03):
                    if cmd == 0x0B:
                        ids = struct.unpack_from('>%dH' % count, room, ptr & 0xFFFFFF)
                        objs.append('%s: %s' % (rname.rsplit('_', 1)[1],
                                                ', '.join(objects.get(o, hex(o)) for o in ids)))
                    if cmd != 0x01:
                        continue
                    for i in range(count):
                        aid, x, y, z, _rx, ry, _rz, var = struct.unpack_from(
                            '>HhhhhhhH', room, (ptr & 0xFFFFFF) + 16 * i)
                        aid &= 0xFFF
                        name = actors.get(aid, '?')
                        port = port_note(prefix, aid, var)
                        if not port and layer == 0:
                            unsupported.setdefault((prefix, name), 0)
                            unsupported[(prefix, name)] += 1
                        lines.append('| %s | %s | 0x%04X | 0x%04X | %d,%d,%d | 0x%04X | %s | %s |'
                                     % (rname.rsplit('_', 1)[1], name, aid, var, x, y, z,
                                        ry & 0xFFFF, decode(aid, var, actors), port))
            lines += ['', 'Objects: ' + ('; '.join(objs) or 'none'), '']
    lines += ['## Child-day actors not ported (M3 must port or record)', '',
              '| scene | actor | count |', '|---|---|---|']
    for (prefix, name), n in sorted(unsupported.items()):
        lines.append('| %s | %s | %d |' % (prefix, name, n))
    args.out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('manifest: %s (%d unsupported child-day actor kinds)' % (args.out, len(unsupported)))


if __name__ == '__main__':
    main()
