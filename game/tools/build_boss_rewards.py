"""Item_B_Heart and DoorWarp1 idle artwork from the original display lists.

Warp matrices are source world-space matrices, not a Flex skeleton. Transform
on vertex load so the upper ring never changes already loaded lower vertices.
The two-cycle scrolling combiner remains the shared primary-texture bake.
"""
import struct
import xml.etree.ElementTree as ET
import build_link_model as link
from build_shop_props import static_mesh


class WarpLists(link.LimbLists):
    def __init__(self, *args, top_scale=1.84, top_y=69, **kwargs):
        super().__init__(*args, **kwargs)
        self.top_scale, self.top_y = top_scale, top_y

    def matrix(self, word, address):
        if word != 0xDA380003 or address not in (0x0A000000, 0x09000000):
            raise ValueError('Unsupported warp matrix %08x %08x' % (word, address))
        self.current_limb = int(address == 0x09000000)

    def load_vertex(self, index, vertex):
        if self.current_limb is None:
            raise ValueError('Warp vertex loaded before matrix')
        if self.current_limb:
            x, y, z = vertex[:3]
            vertex = (round(x*self.top_scale), round(y+self.top_y), round(z*self.top_scale)) + tuple(vertex[3:])
        super().load_vertex(index, vertex)


def build(oot, rom_dir, out):
    static_mesh(oot, rom_dir, 'object_gi_hearts', 'gGiHeartBorderDL',
                out/'BOSSHRT.BIN', .4, extra=('gGiHeartContainerDL',))
    data = link.read_object(oot, 'object_warp1', rom_dir)
    xml = ET.parse(oot/'assets/xml/objects/object_warp1.xml')
    offset = next(int(n.attrib['Offset'], 16) for n in xml.iter('DList')
                  if n.attrib['Name'] == 'gWarpPortalDL')
    faces = []
    # DoorWarp1_DrawWarp after WarpAppear reaches its idle dimensions.
    for scale, y in ((1.84, 69), (2.624, 18)):
        lists = WarpLists(b'', b'', top_scale=scale, top_y=y)
        lists.segments = {6:data, 8:struct.pack('>II', 0xDF000000, 0)}
        lists.prim = (0, 255, 255, 255)
        lists.walk(0x06000000+offset, transparent=True)
        for face in lists.faces:
            face.update(limb=0, full_texture=True, transparent=True)
        faces.extend(lists.faces)
    link.apply_primitive_colour(faces)
    link.write_model(faces, out/'BLUEWARP.BIN', character=False)
