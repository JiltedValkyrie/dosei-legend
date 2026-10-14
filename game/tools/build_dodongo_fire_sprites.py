"""Original eight King Dodongo fire textures in a skeleton-free SPR library."""
from pathlib import Path
import xml.etree.ElementTree as ET

from PIL import Image

import build_link_model as link
from build_item_sprites import pack_sprite
from build_dodongo_boss_meshes import OBJECT, source_offset

KEY = 'object_kingdodongo_DL_01D950'
TEXTURES = tuple('object_kingdodongo_Tex_%06X' % n
                 for n in range(0x264E0, 0x2D4E1, 0x1000))


def bake(oot, rom_dir, work, out, start_index=0, only_objects=None):
    if only_objects is not None and OBJECT not in only_objects:
        return []
    from oot_core_import import object_ids
    oid = object_ids(oot)[1][OBJECT]
    root = ET.parse(oot / 'assets/xml/objects' / (OBJECT + '.xml'))
    nodes = {n.attrib['Name']: n for n in root.iter('Texture')}
    data = link.read_object(oot, OBJECT, rom_dir)
    images = []
    for symbol in TEXTURES:
        node = nodes[symbol]
        if (node.attrib['Format'], node.attrib['Width'], node.attrib['Height']) != ('ia8', '64', '64'):
            raise ValueError('King Dodongo source fire texture format changed')
        offset = source_offset(node)
        raw = data[offset:offset+4096]
        if len(raw) != 4096:
            raise ValueError('King Dodongo source fire texture truncated')
        # EnBdfire_DrawFire: prim(255,255,100), env(200,0,0), IA8 lerp.
        image = Image.new('RGBA', (64, 64))
        image.putdata([(200 + 55*(v >> 4)//15, 17*(v >> 4),
                        100*(v >> 4)//15, 17*(v & 15)) for v in raw])
        image = image.resize((32, 32), Image.Resampling.NEAREST)
        images.append([image]*5)  # identical billboard views
    name = 'G%03X%02X.SPR' % (oid, start_index % 256)
    # Source DL spans -31..32; Matrix_Translate adds 11 before its billboard.
    pack_sprite(images, 32, 32, 11.5, 2.0, 11, out/name, work/(Path(name).stem+'_sprites.png'))
    return [(oid, 0, KEY, start_index % 256, KEY, 0)]
