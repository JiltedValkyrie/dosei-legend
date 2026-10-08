"""Offline Tektite feet and Keese body/effect points; no runtime skeleton."""
import argparse
from pathlib import Path
from build_field_enemy_anchors import build
from water_temple_sources import SPRITE_SOURCES

ANCHORS = {
    'object_tite': tuple((limb, (2800, -200, 0)) for limb in (8, 13, 18, 23)),
    'object_firefly': tuple((limb, (0, 0, 0)) for limb in (15, 21, 10)),
}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, required=True)
    parser.add_argument('--rom-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=Path('build/oot-core/water_anchors.inc'))
    args = parser.parse_args()
    build(args.oot, args.rom_dir, args.out, anchors=ANCHORS, sources=SPRITE_SOURCES,
          root_offsets={'object_firefly': (0, 2300, 0)})
