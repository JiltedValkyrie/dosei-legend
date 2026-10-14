"""Bake all implemented Dodongo-route sprite clips before scene admission."""
import argparse
from pathlib import Path

from build_npc_sprites import bake_generic
from dodongo_enemy_sources import SPRITE_OBJECTS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, required=True)
    parser.add_argument('--rom-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=Path('build/dodongo-route/sprites'))
    args = parser.parse_args()
    for directory in (args.out, args.out / 'work', args.out / 'sheets'):
        directory.mkdir(parents=True, exist_ok=True)
    bake_generic(args.oot, args.rom_dir, args.out / 'work', args.out / 'sheets', args.out,
                 only_objects=SPRITE_OBJECTS)


if __name__ == '__main__':
    main()
