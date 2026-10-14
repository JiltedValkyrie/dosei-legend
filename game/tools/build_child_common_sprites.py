#!/usr/bin/env python3
"""Bake all source Hylian model variants with their actual reachable clips."""
import argparse
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
import build_actor_model as actor
import build_link_model as link
import build_npc_sprites as sprite
import child_common_npcs as common
import oot_core_import as imp


class HylianLists(link.LimbLists):
    def __init__(self, recipe):
        super().__init__(b'', b'')
        self.recipe = recipe
        self.material = (255,255,255,255)

    def walk(self, address, transparent=False, depth=0):
        segment = address >> 24
        if segment in (8,9,10):
            if segment in (8,9):
                self.material = self.recipe['colour' + str(segment)]
            elif self.recipe['obj'] == 'object_cne':
                self.material = self.recipe['colour8'] if self.recipe['variant'] == 0 else (255,255,255,0)
            return
        return super().walk(address, transparent, depth)

    def triangle(self, word, transparent):
        count = len(self.faces)
        super().triangle(word, transparent)
        for face in self.faces[count:]:
            if self.material[:3] != (255,255,255):
                face['prim'] = self.material[:3] + (255,)


def bake(oot, rom_dir, work, out, start_index=0, only_objects=None):
    recipes = common.hy_recipes(oot)
    keep = link.read_object(oot, 'gameplay_keep', rom_dir)
    anim_data = link.read_object(oot, 'object_os_anime', rom_dir)
    anim_root = ET.parse(oot / 'assets/xml/objects/object_os_anime.xml')
    anim_offsets = {n.attrib['Name']: int(n.attrib['Offset'], 16) for n in anim_root.iter('Animation')}
    enum, ids = imp.object_ids(oot)
    rows = []
    for obj in common.HY_OBJECTS:
        if only_objects is not None and obj not in only_objects:
            continue
        data = link.read_object(oot, obj, rom_dir)
        xml_path = oot / 'assets/xml/objects' / (obj + '.xml')
        names = {n.attrib['Name']: int(n.attrib['Offset'], 16) for n in ET.parse(xml_path).iter()
                 if 'Name' in n.attrib and 'Offset' in n.attrib and not n.attrib['Offset'].startswith('.')}
        variants = []
        for recipe in [r for r in recipes if r['obj'] == obj]:
            head_data = link.read_object(oot, recipe['head_obj'], rom_dir)
            head_names = {n.attrib['Name']: int(n.attrib['Offset'], 16) for n in
                          ET.parse(oot / 'assets/xml/objects' / (recipe['head_obj'] + '.xml')).iter()
                          if 'Name' in n.attrib and 'Offset' in n.attrib and not n.attrib['Offset'].startswith('.')}
            # Source env-color materials. At this resolution their tint is
            # folded into the primitive multiplier, preserving each costume.
            def colour_dl(colour):
                return struct.pack('>4I', 0xFA000000, int.from_bytes(bytes(colour), 'big'), 0xDF000000, 0)
            segments = {8: colour_dl(recipe['colour8']), 9: colour_dl(recipe['colour9'])}
            if recipe['eye']:
                segments[10] = head_data[head_names[recipe['eye']]:]
            elif obj == 'object_cne':
                segments[10] = colour_dl(recipe['colour8'] if recipe['variant'] == 0 else (255,255,255,0))
            custom = dict(head_data=head_data, head_offset=head_names[recipe['head']],
                          segments=segments, bag=recipe['bag'], walker=lambda: HylianLists(recipe))
            path = work / (obj + '_' + str(recipe['variant']) + '.BIN')
            owners, locals_, limbs, count = sprite.full_skin(oot, rom_dir, obj, data, names[recipe['skeleton']],
                                                           xml_path, keep, path, custom=custom)
            faces, _, _ = sprite.read_model(path, None)
            for name in recipe['clips']:
                offset = anim_offsets[name]
                length = actor.read_animation(anim_data, offset, count, 0)[0]
                samples = min(sprite.GENERIC_POSES, length)
                poses = []
                for i in range(samples):
                    _, root, rotations = actor.read_animation(anim_data, offset, count, i * length // samples)
                    matrices = {j:(m,o) for j,m,o,_ in link.walk_skeleton(limbs, rotations, root)}
                    poses.append([tuple(v*.01 for v in link.transform(*matrices[owner], local))
                                  for owner, local in zip(owners, locals_)])
                order = [min(samples-1, tick*samples//length) for tick in range(length)]
                variants.append((recipe, name, count, faces, poses, order))
        layout = sprite.layout_of([v[4] for v in variants], sprite.GENERIC_HEIGHT)
        for recipe, name, count, faces, poses, order in variants:
            index = (start_index + len(rows)) % 256
            path = out / f'G{ids[obj]:03X}{index:02X}.SPR'
            sprite.write_sprite(faces, poses, order, path, work / (path.stem + '.png'), layout, sprite.GENERIC_POSES)
            rows.append((ids[obj], count, name, index, recipe['skeleton'], recipe['variant']))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, default=imp.OOT_DEFAULT)
    parser.add_argument('--out', type=Path, default=Path('build/child-common-sprites'))
    args = parser.parse_args()
    work = args.out / 'work'
    work.mkdir(parents=True, exist_ok=True)
    rows = bake(args.oot, None, work, args.out)
    (args.out / 'generic_sprites.json').write_text(json.dumps(rows) + '\n')
    print(f'{len(rows)} source Hylian/guest variant clips')


if __name__ == '__main__':
    main()
