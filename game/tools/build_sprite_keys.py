"""Link sprite keys and pack all clips of each skeleton into one SPR2 file.

SPR2 big endian: magic, u16 version=2, u16 clip count, u32 skeleton key,
u32 file bytes; then {u32 animation key, offset, bytes} per clip. Zero-filled
gaps align each clip's pixels to 16 bytes relative to the archive; clip bodies
retain the validated SPR1 layout. No runtime pose data.
"""
import argparse
import json
from pathlib import Path
import re
import struct


def linked_symbols(symbols):
    return {name.lstrip('_'): int(address, 16) for name, address in
            re.findall(r'(\w+)\s*=\s*0x([\da-fA-F]+);', symbols)}


def key(addresses, name):
    address = addresses[name]
    if address >> 24 != 6:
        raise ValueError('sprite symbol outside object segment: ' + name)
    return address & 0xFFFFFF


def groups(rows, symbols):
    addresses = linked_symbols(symbols)
    result = {}
    for row in rows:
        oid, limbs, animation, file, skeleton = row[:5]
        variant = row[5] if len(row) > 5 else 0
        animation_key = key(addresses, animation)
        if not 0 <= variant < 16 or animation_key >= 0x100000:
            raise ValueError('sprite variant/key exceeds reserved bits')
        identity = (oid, key(addresses, skeleton))
        result.setdefault(identity, []).append((animation_key | (variant << 20), file, animation))
    return result


def resolve(rows, symbols):
    lines = ['/* Generated linked object/skeleton identities; no limb-count matching. */']
    # Standalone legacy resolver remains useful for old offline manifests.
    if rows and len(rows[0]) == 4:
        addresses = linked_symbols(symbols)
        for oid, limbs, name, file in rows:
            lines.append('    { 0x%03X, %d, 0x%06X, 0x%02X }, /* %s */' %
                         (oid, limbs, key(addresses, name), file, name))
        return '\n'.join(lines) + '\n'
    for index, ((oid, skeleton), clips) in enumerate(groups(rows, symbols).items()):
        lines.append('    { 0x%03X, 0x%06X, 0x%02X }, /* %d clips */' %
                     (oid, skeleton, index, len(clips)))
    return '\n'.join(lines) + '\n'


def pack(skeleton, clips):
    if not clips or len(clips) > 256 or not 0 <= skeleton <= 0xFFFFFF:
        raise ValueError('invalid sprite archive identity/count')
    keys = [animation for animation, _ in clips]
    if len(set(keys)) != len(keys):
        raise ValueError('duplicate animation key')
    cursor = 16 + len(clips) * 12
    entries, payload = bytearray(), bytearray()
    for animation, sheet in clips:
        if not 0 <= animation <= 0xFFFFFF or not valid_sheet(sheet):
            raise ValueError('invalid sprite clip')
        ticks = struct.unpack_from('>H', sheet, 12)[0]
        pixels = 52 + ((ticks * 2 + 3) & ~3)
        padding = (-(cursor + pixels)) & 15
        payload.extend(bytes(padding))
        cursor += padding
        entries.extend(struct.pack('>III', animation, cursor, len(sheet)))
        payload.extend(sheet)
        cursor += len(sheet)
    return struct.pack('>4sHHII', b'SPR2', 2, len(clips), skeleton, cursor) + entries + payload


def valid_sheet(sheet):
    if len(sheet) < 52 or sheet[:4] != b'SPR1':
        return False
    width, height, dirs, poses, ticks, centre, texel, focus = struct.unpack_from('>8H', sheet, 4)
    if not (0 < width <= 256 and width % 8 == 0 and 0 < height <= 255 and
            dirs == 5 and 0 < poses <= 256 and ticks and texel):
        return False
    base = 52 + ((ticks * 2 + 3) & ~3)
    if base + width * height // 2 * poses * dirs != len(sheet):
        return False
    return all(pose < poses for pose in struct.unpack_from('>%dH' % ticks, sheet, 52))


def write_archives(rows, symbols, sheets, out):
    total = 0
    libraries = []
    for index, ((oid, skeleton), clips) in enumerate(groups(rows, symbols).items()):
        if index > 255:
            raise ValueError('sprite archive file index exceeds runtime byte')
        data = pack(skeleton, [(animation, (sheets / ('G%03X%02X.SPR' % (oid, file))).read_bytes())
                               for animation, file, _ in clips])
        name = 'G%03X%02X.SP2' % (oid, index)
        (out / name).write_bytes(data)
        print('%s: %d clips, %d bytes' % (name, len(clips), len(data)))
        total += len(data)
        libraries.append({'object': oid, 'skeleton': skeleton, 'file': name,
                          # NUL byte plus aligned allocation's raw-pointer slot
                          # and worst-case padding (SH-2 pointers are 4 bytes).
                          'clips': len(clips), 'bytes': len(data), 'heap_bytes': len(data)+20})
    print('SPR2 libraries: %d bytes total; scene admission also checks the live heap' % total)
    return libraries


def scene_costs(libraries, folder, rewards=()):
    result = []
    for path in sorted(folder.glob('*.cpp')):
        text = path.read_text(encoding='utf-8')
        match = re.search(r'oot_scene_objects\[\]\s*=\s*\{([^}]*)\}', text)
        if not match:
            continue
        objects = {int(n, 0) for n in re.findall(r'0x[\da-fA-F]+|\b\d+\b', match[1])}
        own = [lib for lib in libraries if lib['object'] in objects]
        extra = next((row for row in rewards if row['scene'] == path.stem), None)
        if own or extra:
            result.append({'scene': path.stem, 'libraries': [lib['file'] for lib in own],
                           'reward_library': extra['file'] if extra else None,
                           'reward_heap_bytes': extra['heap_bytes'] if extra else 0,
                           'preload_scratch_bytes': (len(libraries) + 1) * 4 + 20,
                           'heap_bytes': sum(lib['heap_bytes'] for lib in own) +
                               (extra['heap_bytes'] if extra else 0) + (len(libraries) + 1) * 4 + 20})
    return result


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('rows', type=Path)
    ap.add_argument('symbols', type=Path)
    ap.add_argument('out', type=Path)
    ap.add_argument('--sheets', type=Path)
    ap.add_argument('--archives', type=Path)
    ap.add_argument('--scenes', type=Path)
    ap.add_argument('--rewards', type=Path, default=Path(__file__).resolve().parents[1]/'build/get-item-sprites/budget.json')
    args = ap.parse_args()
    rows = json.loads(args.rows.read_text())
    symbols = args.symbols.read_text()
    if args.sheets:
        libraries = write_archives(rows, symbols, args.sheets, args.archives or args.sheets)
        if args.scenes:
            rewards = json.loads(args.rewards.read_text()) if args.rewards.exists() else ()
            scenes = scene_costs(libraries, args.scenes, rewards)
            report = {'libraries': libraries, 'scenes': scenes,
                      'runtime_heap_guard_percent': 85, 'runtime_accepted': False}
            args.out.with_suffix('.budget.json').write_text(json.dumps(report, indent=2)+'\n')
            if scenes:
                peak = max(scenes, key=lambda scene: scene['heap_bytes'])
                print('Peak scene %s: %d sprite heap bytes (+ allocator overhead)' %
                      (peak['scene'], peak['heap_bytes']))
    args.out.write_text(resolve(rows, symbols))
