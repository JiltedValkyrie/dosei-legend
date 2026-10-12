"""Move cold constant tables out of work RAM (BUG-043).

Writes build/cd/MUSICTRG.BIN (every music bank's trigger table) and
build/cd/TITLEPTH.BIN (the title's eight camera paths). main.c loads both
into the fixed cart carve at boot; the headers still supply counts/layouts.

MUSICTRG.BIN: 'KTRG', u16 BE bank count, u16 BE trigger count per bank, then
  each bank's triggers as the SH-2 music_trigger_t layout (8 bytes, BE):
  u16 frame, u8 slot, u8 sample, u16 pitch, u8 pan, u8 pad.
TITLEPTH.BIN: 'KTPT', u16 BE shot count, u16 BE points per shot, then points
  as title_point_t (5 x s16 BE: x, y, z, yaw, pitch).
"""
import argparse
import re
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
# Bank order is the load order in music_banks.c (music_banks_bind).
BANKS = (
    ('title_triggers', 'TITLE', HERE.parent / 'shared/assets/audio/title/title_score.h'),
    ('kokiri_triggers', 'KOKIRI', HERE / 'levels/kokiri/assets/audio/kokiri_score.h'),
    ('navi_triggers', 'NAVI', HERE / 'assets/audio/cutscenes/navi_score.h'),
    ('deku_tree_triggers', 'DEKU_TREE', HERE / 'assets/audio/cutscenes/deku_tree_score.h'),
    ('nightmare_triggers', 'NIGHTMARE', HERE / 'assets/audio/cutscenes/nightmare_score.h'),
    ('house_triggers', 'HOUSE', HERE / 'build/generated/house_score.h'),
    ('shop_triggers', 'SHOP', HERE / 'build/generated/shop_score.h'),
    ('dungeon_triggers', 'DUNGEON', HERE / 'build/generated/dungeon_score.h'),
    ('woods_triggers', 'WOODS', HERE / 'build/generated/woods_score.h'),
    ('fairy_triggers', 'FAIRY', HERE / 'build/generated/fairy_score.h'),
    ('boss_triggers', 'BOSS', HERE / 'build/generated/boss_score.h'),
    ('bossclear_triggers', 'BOSSCLEAR', HERE / 'build/generated/bossclear_score.h'),
    ('owl_triggers', 'OWL', HERE / 'build/generated/owl_score.h'),
    ('fairyget_triggers', 'FAIRYGET', HERE / 'build/generated/fairyget_score.h'),
    ('field_triggers', 'FIELD', HERE / 'build/generated/field_score.h'),
    ('stone_triggers', 'STONE', HERE / 'build/generated/stone_score.h'),

)
# Must match RAM_CART_MUSICTRG_BYTES / RAM_CART_TITLEPTH_BYTES (ram_cart.h).
MUSICTRG_LIMIT = 0x18000  # MUSICTRG_BYTES (music_banks.h, cart heap); loaded before music starts
TITLEPTH_LIMIT = 0x1800


def rows(text, name):
    m = re.search(r'\b%s\[\]\s*=\s*\{(.*?)\n\};' % re.escape(name), text, re.S)
    if not m:
        raise ValueError('table %s not found' % name)
    return [tuple(int(v) for v in r.split(','))
            for r in re.findall(r'\{\s*([-\d,\s]+?)\s*\}', m.group(1))]


def define(text, name):
    m = re.search(r'#define\s+%s\s+(\d+)' % name, text)
    if not m:
        raise ValueError('#define %s not found' % name)
    return int(m.group(1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cd', type=Path, default=HERE / 'build/cd')
    ap.add_argument('--paths', type=Path, default=HERE / 'build/generated/title_paths.h')
    args = ap.parse_args()
    args.cd.mkdir(parents=True, exist_ok=True)

    tables = []
    for name, prefix, path in BANKS:
        text = path.read_text()
        table = rows(text, name)
        if len(table) != define(text, prefix + '_TRIGGER_COUNT'):
            raise ValueError('%s count mismatch' % name)
        tables.append(table)
    blob = b'KTRG' + struct.pack('>H', len(tables))
    blob += b''.join(struct.pack('>H', len(t)) for t in tables)
    for t in tables:
        for frame, slot, sample, pitch, pan in t:
            blob += struct.pack('>HBBHBx', frame, slot, sample, pitch, pan)
    if len(blob) > MUSICTRG_LIMIT:
        raise ValueError('MUSICTRG.BIN %d B exceeds its cart carve' % len(blob))
    (args.cd / 'MUSICTRG.BIN').write_bytes(blob)

    text = args.paths.read_text()
    shots = define(text, 'TITLE_SHOT_COUNT')
    paths = [rows(text, 'title_path_%d' % i) for i in range(shots)]
    points = len(paths[0])
    if any(len(p) != points for p in paths):
        raise ValueError('title paths differ in length')
    pblob = b'KTPT' + struct.pack('>HH', shots, points)
    for p in paths:
        for point in p:
            pblob += struct.pack('>5h', *point)
    if len(pblob) > TITLEPTH_LIMIT:
        raise ValueError('TITLEPTH.BIN %d B exceeds its cart carve' % len(pblob))
    (args.cd / 'TITLEPTH.BIN').write_bytes(pblob)
    print('cart tables: MUSICTRG.BIN %d B, TITLEPTH.BIN %d B' % (len(blob), len(pblob)))


if __name__ == '__main__':
    main()
