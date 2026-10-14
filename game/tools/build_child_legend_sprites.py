"""Source Golden Goddess body/aura, baked offline with three source palettes."""
import math
from pathlib import Path

OBJECT = 'object_god_lgt'
KEY = 'gGoldenGoddessBodyDL'
COLORS = ((255, 170, 255, 255), (170, 255, 255, 255), (170, 255, 170, 255))


def bake(oot, rom_dir, work, out, start_index=0, only_objects=None):
    if only_objects is not None and OBJECT not in only_objects:
        return []
    import build_npc_sprites as sprites
    import build_link_model as link
    from oot_core_import import object_ids
    oid = object_ids(oot)[1][OBJECT]
    data = link.read_object(oot, OBJECT, rom_dir)
    keep = link.read_object(oot, 'gameplay_keep', rom_dir)
    xml = oot/'assets/xml/objects'/ (OBJECT+'.xml')
    path = work/'GOD_BODY.BIN'
    _, body = sprites.static_skin(OBJECT, data, xml, keep, (KEY,), path)
    body_faces, _, _ = sprites.read_model(path, None)
    poses = []
    for phase in range(121):
        s,c = math.sin(math.radians(phase*3)), math.cos(math.radians(phase*3))
        pose = []
        for x,y,z in body:
            # Source actor matrix * Rz(phase*3) * Rx(90) * T(0,-140,0) * S(.03).
            x,y,z = x*.03, -z*.03, y*.03-140
            pose.append(((x*c-y*s)*.1, (x*s+y*c)*.1, z*.1))
        poses.append(pose)
    entries = [(KEY,0,body_faces,poses,48)]
    # A separate cel preserves the body's detail when the long aura points
    # sideways; one enormous shared cel otherwise reduces the god to4pixels.
    for variant, color in enumerate(COLORS):
        key='gGoldenGoddessAuraDL'
        path = work/('GOD_AURA%d.BIN'%variant)
        _, aura = sprites.static_skin(OBJECT, data, xml, keep, (key,), path, prim=color)
        faces, _, _ = sprites.read_model(path, None)
        entries.append((key,variant,faces,[[tuple(v*.1 for v in p) for p in aura]],32))
    rows = []
    for offset,(key,variant,faces,poses,height) in enumerate(entries):
        index=(start_index+offset)%256
        layout=list(sprites.layout_of([poses],height))
        if layout[0]>128:
            texel=layout[2]*layout[0]/128
            ymin=min(p[1] for pose in poses for p in pose)
            ymax=max(p[1] for pose in poses for p in pose)
            layout=[128,math.ceil((ymax-ymin)/texel)+2,texel,(ymin+ymax)/2,ymax]
        dest=out/('G%03X%02X.SPR'%(oid,index))
        sprites.write_sprite(faces, poses, list(range(len(poses))), dest,
                             work/(dest.stem+'_sprites.png'), layout, 8)
        rows.append((oid,0,key,index,key,variant))
    return rows
