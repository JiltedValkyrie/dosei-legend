"""Source M3 pots, small rocks and animated normal treasure chests."""
import argparse
import pathlib
import xml.etree.ElementTree as ET
import build_link_model as link
import build_actor_model as actor
from build_shop_props import static_mesh
from cutscene_animation import write_track

def chest(oot, rom_dir, out):
    data = link.read_object(oot, 'object_box', rom_dir)
    root = ET.parse(oot / 'assets/xml/objects/object_box.xml')
    offsets = {e.attrib['Name']: int(e.attrib['Offset'],16) for e in root.iter()
               if 'Name' in e.attrib and 'Offset' in e.attrib}
    table,count = actor.read_skeleton(data,offsets['gTreasureChestSkel'])
    limbs,_ = actor.read_limbs(data,table,count)
    # EnBox_PostLimbDraw's one-based limbs 1 and 3.
    for limb in limbs: limb['near'] = limb['far'] = 0
    limbs[0]['far'] = limbs[0]['near'] = 0x06000000 | offsets['gTreasureChestChestFrontDL']
    limbs[2]['far'] = limbs[2]['near'] = 0x06000000 | offsets['gTreasureChestChestSideAndLidDL']
    anim=offsets['gTreasureChestAnim_000128'] # child opening
    frames,origin,rot = actor.read_animation(data,anim,count,0)
    placed=list(link.walk_skeleton(limbs,rot,origin))
    poses={i:(m,o) for i,m,o,_ in placed}
    lists=link.LimbLists(b'',b''); lists.segments={6:data}
    lists.matrix_limbs=[i for i,_,_,dl in placed if dl]
    faces=[]
    for i,_,_,dl in placed:
        if not dl: continue
        first=len(lists.faces);lists.current_limb=i;lists.walk(dl)
        for raw in lists.faces[first:]:
            face=dict(raw)
            face['local']=[tuple(v[:3]) for v in face['vertices']]
            face['vertices']=[link.transform(*poses[owner],v[:3])+tuple(v[3:])
                              for v,owner in zip(face['vertices'],face['vertex_limbs'])]
            face['limb']=i;face['full_texture']=True;faces.append(face)
    link.apply_primitive_colour(faces)
    # Large model; runtime scales small type-5 chests by one half.
    faces=link.scale_faces(faces,.01)
    dest=out/'CHEST.BIN'
    _,_,owners,locals_=link.write_model(faces,dest,skinned=True,character=False)
    def track():
        for frame in range(frames):
            _,origin,rot=actor.read_animation(data,anim,count,frame)
            poses={i:(m,o) for i,m,o,_ in link.walk_skeleton(limbs,rot,origin)}
            yield [tuple(v*.01 for v in link.transform(*poses[owner],local))
                   for owner,local in zip(owners,locals_)]
    write_track(dest.with_suffix('.ANM'),track())
    return frames

def dungeon_webs(oot,rom_dir,out):
    import build_kokiri_scene as source
    from build_progression_manifest import room_records
    data=link.read_object(oot,'object_ydan_objects',rom_dir)
    col=source.collision_header_data(data,0x6460) # gDTWebFloorCol
    rows=[]
    for p in col['polys']:
        v=p['vertices']; values=[n for point in v for n in point]+p['normal']
        values += [min(point[k] for point in v) for k in range(3)]
        values += [max(point[k] for point in v) for k in range(3)]
        rows.append('{{{'+','.join(map(str,values[:3]))+'},{'+','.join(map(str,values[3:6]))+'},{'+','.join(map(str,values[6:9]))+'}},'+
                    '{'+','.join(map(str,values[9:12]))+'},{'+','.join(map(str,values[12:15]))+'},{'+','.join(map(str,values[15:]))+'}}')
    segments=source.extract(oot,rom_dir,prefix='ydan'); spawns=[]
    import build_actor_manifest as actors
    names=actors.table(oot/'include/tables/actor_table.h','DEFINE_ACTOR')
    spawns=[]
    for room in range(12):
        for a in room_records(segments['ydan_room_%d'%room],names,{})['actors']:
            if a['name']=='Bg_Ydan_Sp' and a['params']>>12==0:
                spawns.append((room,*a['position'],a['rotation'][1],a['params']&63))
    if not spawns: raise ValueError('Missing original floor webs')
    header='/* Original gDTWebFloorCol and child-day placements; no drops. */\n'
    header+='static const collision_triangle_t dungeon_web_triangles[] = {\n'+',\n'.join(rows)+'\n};\n'
    header+='typedef struct {short room,x,y,z,yaw,flag;} dungeon_web_spawn;\n'
    header+='static const dungeon_web_spawn dungeon_webs[] = {\n'+',\n'.join('{'+','.join(map(str,row))+'}' for row in spawns)+'\n};\n'
    header+='#define DUNGEON_WEB_COUNT %d\n'%len(spawns)
    (out.parent/'generated').mkdir(parents=True,exist_ok=True)
    (out.parent/'generated/dungeon_web_data.h').write_text(header)
    static_mesh(oot,rom_dir,'object_ydan_objects','gDTWebFloorDL',out/'DTWEB.BIN',.1,cutout=True)

def dungeon_torches(oot,rom_dir,out):
    import build_kokiri_scene as source
    from build_progression_manifest import room_records
    import build_actor_manifest as actors
    names=actors.table(oot/'include/tables/actor_table.h','DEFINE_ACTOR')
    segments=source.extract(oot,rom_dir,prefix='ydan')
    rows=[]
    for room in range(12):
        for a in room_records(segments['ydan_room_%d'%room],names,{})['actors']:
            if a['name']=='Obj_Syokudai':
                if a['params']>>12>2: raise ValueError('Unknown torch type')
                rows.append((room,*a['position'],a['rotation'][1],a['params']))
    header='/* Obj_Syokudai child-day spawns. This actor has no drops. */\n'
    header+='typedef struct {short room,x,y,z,yaw;unsigned short params;} dungeon_torch_spawn;\n'
    header+='static const dungeon_torch_spawn dungeon_torches[] = {\n'
    header+=',\n'.join('{'+','.join(map(str,row))+'}' for row in rows)+'\n};\n'
    header+='#define DUNGEON_TORCH_COUNT %d\n'%len(rows)
    (out.parent/'generated/dungeon_torch_data.h').write_text(header)
    for i,symbol in enumerate(('gGoldenTorchDL','gTimedTorchDL','gWoodenTorchDL')):
        static_mesh(oot,rom_dir,'object_syokudai',symbol,out/('DTTORCH%d.BIN'%i),cutout=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--oot',type=pathlib.Path,default=link.OOT_DEFAULT)
    ap.add_argument('--rom-dir',type=pathlib.Path)
    ap.add_argument('--out',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parents[1]/'build/cd')
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    (args.out.parent/'generated').mkdir(parents=True,exist_ok=True)
    static_mesh(args.oot,args.rom_dir,'gameplay_field_keep','gFieldKakeraDL',args.out/'ROCK.BIN',.1)
    static_mesh(args.oot,args.rom_dir,'object_tsubo','object_tsubo_DL_0017C0',args.out/'POT.BIN',.15)
    # EnKanban sDisplayLists order corresponds to bits 0..10.
    for i,offset in enumerate((0xCB0,0xDB8,0xE78,0xF38,0xFF8,0x10B8,0x11C0,0x12C8,0x13D0,0x1488,0x1540)):
        static_mesh(args.oot,args.rom_dir,'object_kanban','object_kanban_DL_%06X'%offset,args.out/('SIGN%d.BIN'%i),.01,setup='object_kanban_DL_000C30')
    static_mesh(args.oot,args.rom_dir,'gameplay_field_keep','gFieldBushDL',args.out/'BUSH.BIN',.4,cutout=True)
    static_mesh(args.oot,args.rom_dir,'object_gs','gGossipStoneDL',args.out/'GOSSIP.BIN',.1,setup='gGossipStoneMaterialDL',extra=('gGossipStoneSquishedDL',))
    static_mesh(args.oot,args.rom_dir,'object_ydan_objects','gDTDungeonDoor1DL',args.out/'DTDOOR.BIN',1.0)
    # Handle doors are static props; rotate the baked leaf at its hinge.
    # No runtime door skeleton or animation payload is needed.
    # Source idle limb 1 rotates -0x4000 about X; the raw leaf is in XZ.
    static_mesh(args.oot,args.rom_dir,'gameplay_field_keep','gFieldDoorLeftDL',args.out/'ENDOOR.BIN',.01,
                matrix=link.rotation_matrix((-0x4000,0,0)))
    from build_tree_mouth import build as build_tree_mouth
    build_tree_mouth(args.oot,args.rom_dir,args.out)
    dungeon_webs(args.oot,args.rom_dir,args.out)
    dungeon_torches(args.oot,args.rom_dir,args.out)
    from build_dungeon_walls import build as walls
    walls(args.oot,args.rom_dir,args.out)
    from build_dungeon_puzzles import build as puzzles
    puzzles(args.oot,args.rom_dir,args.out)
    from build_dungeon_enemies import build as enemies
    enemies(args.oot,args.rom_dir,args.out)
    from build_boss_rewards import build as boss_rewards
    boss_rewards(args.oot,args.rom_dir,args.out)
    frames=chest(args.oot,args.rom_dir,args.out)
    (args.out.parent/'generated').mkdir(parents=True,exist_ok=True)
    (args.out.parent/'generated/world_prop_assets.h').write_text(
        '#define WORLD_CHEST_FRAMES %d\n'%frames)

if __name__=='__main__': main()
