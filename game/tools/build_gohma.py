"""Boss_Goma source skeleton and clips, with the NTSC XML's implicit offsets."""
from pathlib import Path
import argparse
import struct
import re
import xml.etree.ElementTree as ET
from build_dungeon_enemies import model
import build_link_model as link
import build_actor_model as actor

CLIPS = ('Stand', 'Hang', 'Walk', 'PrepareEggs', 'Attack', 'RestAfterAttack',
         'RecoverAfterAttack', 'Crash', 'Land', 'Climb', 'Damage', 'Death',
         'PrepareAttack', 'Stunned', 'InitialLanding', 'EyeRoll', 'LayEggs',
         'IdleCrouched', 'WalkCrouched')

def build(oot, rom_dir, out):
    xml = ET.parse(oot/'assets/xml/objects/object_goma.xml')
    # In NTSC the 128x80 IA8 title is immediately followed by 85 Standard
    # limbs, their pointer table, then the 8-byte SkeletonHeader. PAL uses a
    # taller title and must never share these resolved offsets.
    title = next(n for n in xml.iter('Texture') if n.attrib['Name']=='gGohmaTitleCardTex' and n.attrib['Height']=='80')
    count = int(next(xml.iter('LimbTable')).attrib['Count'])
    limbs = int(title.attrib['Offset'],16)+int(title.attrib['Width'])*int(title.attrib['Height'])
    skeleton = limbs+count*12+count*4
    data = link.read_object(oot,'object_goma',rom_dir)
    table, actual_count = struct.unpack_from('>IB',data,skeleton)
    if actual_count != count or table != 0x06000000+limbs+count*12:
        raise ValueError('Gohma NTSC implicit skeleton layout changed')
    walk = next(n for n in xml.iter('Animation') if n.attrib['Name']=='gGohmaWalkCrouchedAnim')
    offsets = {'gGohmaSkel':skeleton, 'gGohmaWalkCrouchedAnim':skeleton+8+int(walk.attrib['Offset'][2:],16)}
    ranges = model(oot,rom_dir,out,'GOHMA','object_goma',.01,
                   tuple('gGohma%sAnim'%c for c in CLIPS),offsets_extra=offsets)
    # Pose-derived source spheres: eye and limb hits must follow the artwork,
    # including ceiling rotation. No guessed large body cylinder.
    source_dir=oot/'src/overlays/actors/ovl_Boss_Goma'
    source=(source_dir/'z_boss_goma.c').read_text()
    enum=(source_dir/'z_boss_goma.h').read_text()
    ids={name:int(index) for index,name in re.findall(r'/\*\s*(\d+)\s*\*/\s*(BOSSGOMA_LIMB_\w+)',enum)}
    colliders=re.findall(r'\{ (BOSSGOMA_LIMB_\w+), \{ \{ (-?\d+), (-?\d+), (-?\d+) \}, (\d+) \}, 100 \}',source)
    if len(colliders)!=13:raise ValueError('Gohma collider count changed')
    limbs_data,_=actor.read_limbs(data,table&0xffffff,count)
    offsets.update({n.attrib['Name']:int(n.attrib['Offset'],16) for n in xml.iter('Animation') if not n.attrib['Offset'].startswith('.')})
    positions=bytearray()
    for name,(_,frames) in zip(CLIPS,ranges):
        for frame in range(frames):
            _,root,rot=actor.read_animation(data,offsets['gGohma%sAnim'%name],count,frame)
            pose={i:(m,o) for i,m,o,_ in link.walk_skeleton(limbs_data,rot,root)}
            for limb,x,y,z,radius in colliders:
                p=link.transform(*pose[ids[limb]],(int(x),int(y),int(z)))
                positions+=struct.pack('>3h',*(round(v*.01) for v in p))
    (out/'GOHMAPOS.BIN').write_bytes(positions)
    header = '/* Boss_Goma original animation ranges. Generated. */\n'
    header += 'static const unsigned short gohma_clips[][2]={'+','.join('{%d,%d}'%p for p in ranges)+'};\n'
    header += 'static const unsigned char gohma_radii[]={'+','.join(c[4] for c in colliders)+'};\n'
    header += '#define GOHMA_POSE_BYTES %d\n'%len(positions)
    (out.parent/'generated/gohma_data.h').write_text(header)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--oot',type=Path,default=Path((__import__('os').environ.get('DOSEI_OOT') or 'D:/Workspace-Claude/game-decomps/n64/oot')))
    ap.add_argument('--out',type=Path,default=Path(__file__).resolve().parents[1]/'build/cd')
    args=ap.parse_args()
    build(args.oot,args.oot/'baseroms/ntsc-1.2',args.out)
