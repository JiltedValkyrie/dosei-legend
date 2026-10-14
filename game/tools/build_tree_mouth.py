"""Bg_Treemouth original display list and collision; this actor has no drops."""
from pathlib import Path
import xml.etree.ElementTree as ET
import build_link_model as link
from build_shop_props import static_mesh

def build(oot,rom_dir,out):
    import build_kokiri_scene as source
    data=link.read_object(oot,'object_spot04_objects',rom_dir)
    root=ET.parse(oot/'assets/xml/objects/object_spot04_objects.xml')
    offset=next(int(e.attrib['Offset'],16) for e in root.iter() if e.attrib.get('Name')=='gDekuTreeMouthCol')
    col=source.collision_header_data(data,offset)
    rows=[]
    for p in col['polys']:
        v=p['vertices']
        groups=list(v)+[p['normal'],[min(q[k] for q in v) for k in range(3)], [max(q[k] for q in v) for k in range(3)]]
        vec=lambda q:'{'+','.join(map(str,q))+'}'
        rows.append('{{'+','.join(vec(q) for q in groups[:3])+'},'+','.join(vec(q) for q in groups[3:])+'}')
    (out.parent/'generated/tree_mouth_data.h').write_text('/* Original gDekuTreeMouthCol. */\n#include "host_cold.h"\nHOST_COLD static const collision_triangle_t tree_mouth_triangles[]={\n'+',\n'.join(rows)+'\n};\n')
    static_mesh(oot,rom_dir,'object_spot04_objects','gDekuTreeMouthDL',out/'TREEMTH.BIN',1.0)
