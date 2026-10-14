"""Source child portal geometry with its two matrix rings baked 230 units apart.

The runtime draw adapter scales the source height and top-ring width. The
bottom shares that width as an explicit inexpensive presentation approximation;
the source range trigger, story flags, rewards and transitions are untouched.
"""
import struct
import xml.etree.ElementTree as ET

import build_link_model as link


class WarpLists(link.LimbLists):
    def matrix(self, word, address):
        if word != 0xDA380003 or address not in (0x09000000, 0x0A000000):
            raise ValueError('source portal matrix changed: %08X %08X' % (word, address))
        self.current_limb = int(address == 0x09000000)

    def load_vertex(self, index, vertex):
        vertex = tuple(vertex[:1]) + (vertex[1] + self.current_limb * 230,) + tuple(vertex[2:])
        super().load_vertex(index, vertex)


def bake(oot, rom_dir, destination):
    obj = 'object_warp1'
    root = ET.parse(oot / 'assets/xml/objects' / (obj + '.xml'))
    node = next(n for n in root.iter('DList') if n.attrib['Name'] == 'gWarpPortalDL')
    lists = WarpLists(b'', b'')
    lists.segments = {6: link.read_object(oot, obj, rom_dir), 8: struct.pack('>II', 0xDF000000, 0)}
    lists.current_limb = 0
    lists.prim = (128, 255, 255, 255)
    before = link.LimbLists.unresolved
    lists.walk(0x06000000 | int(node.attrib['Offset'], 16), transparent=True)
    if link.LimbLists.unresolved != before or len(lists.faces) != 24:
        raise ValueError('source portal incomplete: expected24 triangles')
    for face in lists.faces:
        face['limb'] = 0; face['full_texture'] = True; face['transparent'] = True
    link.apply_primitive_colour(lists.faces)
    points, tiles, _, _ = link.write_model(lists.faces, destination, character=False)
    print('Child source portal: %dvertices,24triangles,%dtiles,%dbytes' %
          (len(points), len(tiles), destination.stat().st_size))
    return dict(vertices=len(points), polygons=24, tiles=len(tiles), bytes=destination.stat().st_size)
