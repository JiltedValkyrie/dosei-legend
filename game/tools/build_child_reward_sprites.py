"""Offline token-family faces/dances and tiny gameplay contact summaries."""
import csv
import re
import struct
import xml.etree.ElementTree as ET
import build_actor_model as actor
import build_link_model as link
import build_npc_sprites as sprite
import oot_core_import as imp
from build_child_common_sprites import HylianLists


def names(oot, obj):
    return {e.attrib['Name']: int(e.attrib['Offset'], 16) for e in
            ET.parse(oot / 'assets/xml/objects' / (obj + '.xml')).iter()
            if 'Name' in e.attrib and 'Offset' in e.attrib and not e.attrib['Offset'].startswith('.')}


def anchors(oot, rom_dir=None):
    lines = ['/* Offline semantic contacts/facing only; no joint pose tracks. */']
    for obj, skel, clips, point, tag in (
        ('object_tk','gDampeSkel',('gDampeRestAnim','gDampeWalkAnim','gDampeDigAnim'),None,'sDampeJawYaw'),
        ('object_ssh','object_ssh_Skel_0052E0',('object_ssh_Anim_000304','object_ssh_Anim_0055F8','object_ssh_Anim_005BE8'),(0,-240,0),'sCursedFamilyContact')):
        data=link.read_object(oot,obj,rom_dir); keys=names(oot,obj)
        table,count=actor.read_skeleton(data,keys[skel]);limbs,_=actor.read_limbs(data,table,count)
        lines.append('static const s16 '+tag+'[][4]'+('[3]' if point else '')+' = {')
        for clip in clips:
            length=actor.read_animation(data,keys[clip],count,0)[0];values=[]
            for i in range(4):
                _,root,rotation=actor.read_animation(data,keys[clip],count,i*length//4)
                if point:
                    poses={j:(m,o) for j,m,o,_ in link.walk_skeleton(limbs,rotation,root)}
                    values.append('{ %d, %d, %d }'%tuple(round(v) for v in link.transform(*poses[0],point)))
                else:
                    yaw=(rotation[14][1]+rotation[15][1]+32768)%65536-32768
                    values.append(str(yaw))
            lines.append('    { '+', '.join(values)+' }, /* '+clip+' */')
        lines.append('};')
    return '\n'.join(lines)+'\n'


def overlay(oot, rom_dir=None):
    data=bytearray(link.read_object(oot,'ovl_En_Sth',rom_dir))
    with (oot/'baseroms/ntsc-1.2/segments.csv').open() as f:
        base=int(next(r['VRAM start'] for r in csv.DictReader(f) if r['Name']=='ovl_En_Sth'),16)
    # The source overlay points within its loaded VRAM span. Rebase only actual
    # in-span words to segment6; these bytes are offline inputs, never payloads.
    for at in range(0,len(data)-3,4):
        value=struct.unpack_from('>I',data,at)[0]
        if base<=value<base+len(data):struct.pack_into('>I',data,at,0x06000000+value-base)
    config=(oot/'baseroms/ntsc-1.2/config.yml').read_text()
    start=int(re.search(r'name: overlays/ovl_En_Sth.*?start_offset: (0x[0-9A-Fa-f]+)',config,re.S)[1],16)
    keys={e.attrib['Name']:start+int(e.attrib['Offset'],16) for e in ET.parse(oot/'assets/xml/overlays/ovl_En_Sth.xml').iter()
          if 'Name' in e.attrib and 'Offset' in e.attrib}
    return bytes(data),keys


def bake(oot, rom_dir, work, out, start_index=0, only_objects=None):
    head,keys=overlay(oot,rom_dir);keep=link.read_object(oot,'gameplay_keep',rom_dir)
    colours=((190,110,0),(0,180,110),(0,255,80),(255,160,60),(190,230,250),(240,230,120))
    rows=[]
    for obj in ('object_ahg','object_boj'):
        if only_objects is not None and obj not in only_objects:continue
        data=link.read_object(oot,obj,rom_dir);body=names(oot,obj);oid=imp.object_ids(oot)[1][obj]
        skel='gHylianMan1Skel' if obj=='object_ahg' else 'gHylianMan2Skel';clips=[]
        for params in ((0,) if obj=='object_ahg' else range(1,6)):
            recipe=dict(obj=obj,variant=params,colour8=colours[params]+(255,),colour9=((190,110,0) if params==0 else (90,110,130))+(255,))
            custom=dict(head_data=head,head_offset=keys['D_80B0A050'],walker=lambda: HylianLists(recipe),
                        extra_lists={14:(0x06000000|keys['D_80B0A3C0'],)} if params else {})
            path=work/(obj+'_token_'+str(params)+'.BIN')
            owners,local,limbs,count=sprite.full_skin(oot,rom_dir,obj,data,body[skel],oot/'assets/xml/objects'/(obj+'.xml'),keep,path,custom=custom)
            faces,_,_=sprite.read_model(path,None);anim=keys['sParentDanceAnim' if params==0 else 'sChildDanceAnim']
            length=actor.read_animation(head,anim,count,0)[0];poses=[]
            for frame in range(sprite.GENERIC_POSES):
                _,root,rot=actor.read_animation(head,anim,count,frame*length//sprite.GENERIC_POSES)
                matrices={j:(m,o) for j,m,o,_ in link.walk_skeleton(limbs,rot,root)}
                poses.append([tuple(v*.01 for v in link.transform(*matrices[owner],p)) for owner,p in zip(owners,local)])
            clips.append((params,count,faces,poses,[min(sprite.GENERIC_POSES-1,t*sprite.GENERIC_POSES//length) for t in range(length)]))
        layout=sprite.layout_of([r[3] for r in clips],sprite.GENERIC_HEIGHT)
        for params,count,faces,poses,order in clips:
            idx=(start_index+len(rows))%256;path=out/f'G{oid:03X}{idx:02X}.SPR'
            sprite.write_sprite(faces,poses,order,path,work/(path.stem+'.png'),layout,sprite.GENERIC_POSES)
            # Overlay dance clock is local data; the stable body symbol and
            # variant8..13 identify it across separately linked scene packs.
            rows.append((oid,count,skel,idx,skel,8+params))
    return rows
