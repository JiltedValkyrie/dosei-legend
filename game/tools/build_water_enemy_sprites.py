"""Bake converted Water Temple enemies in isolation before pack admission."""
import argparse
from pathlib import Path
from build_npc_sprites import bake_generic
from water_temple_sources import SPRITE_OBJECTS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, required=True)
    parser.add_argument('--rom-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=Path('build/water-temple/sprites'))
    args = parser.parse_args()
    for folder in (args.out, args.out/'work', args.out/'sheets'):
        folder.mkdir(parents=True, exist_ok=True)
    bake_generic(args.oot, args.rom_dir, args.out/'work', args.out/'sheets', args.out,
                 only_objects=SPRITE_OBJECTS)


if __name__ == '__main__': main()
