"""Native Ydan puzzle meshes and collision, including source surface flags.

These actors have no collectible drops (Obj_Switch, Bg_Ydan_Hasi,
Bg_Ydan_Maruta, Obj_Lift). Scale is baked offline, never floating point on SH2.
"""
import math
import xml.etree.ElementTree as ET
import build_link_model as link
from build_shop_props import static_mesh

# Runtime model IDs, shared by generated collision and drawing.
MODELS = (
    ('gameplay_dangeon_keep', 'gFloorSwitch1DL', 'gFloorSwitchCol', (.1, .165, .1), None),
    ('gameplay_dangeon_keep', 'gFloorSwitch1DL', 'gFloorSwitchCol', (.1, .1155, .1), None),
    ('gameplay_dangeon_keep', 'gFloorSwitch1DL', 'gFloorSwitchCol', (.1, .066, .1), None),
    ('gameplay_dangeon_keep', 'gFloorSwitch1DL', 'gFloorSwitchCol', (.1, .0165, .1), None),
    ('gameplay_dangeon_keep', 'gEyeSwitch2DL', None, (.1, .1, .1), 'gEyeSwitchSilverOpenTex'),
    ('gameplay_dangeon_keep', 'gEyeSwitch2DL', None, (.1, .1, .1), 'gEyeSwitchSilverHalfTex'),
    ('gameplay_dangeon_keep', 'gEyeSwitch2DL', None, (.1, .1, .1), 'gEyeSwitchSilverClosedTex'),
    ('object_ydan_objects', 'gDTSlidingPlatformDL', 'gDTSlidingPlatformCol', (.15, .1, .15), None),
    ('object_ydan_objects', 'gDTRisingPlatformsDL', 'gDTRisingPlatformsCol', (.1, .1, .1), None),
    ('object_ydan_objects', 'gDTWaterPlaneDL', None, (.1, .1, .1), None),
    ('object_ydan_objects', 'gDTFallingLadderDL', 'gDTFallingLadderCol', (.1, .1, .1), None),
    ('object_ydan_objects', 'gDTRollingSpikeTrapDL', None, (.1, .1, .1), None),
    ('object_d_lift', 'gCollapsingPlatformDL', 'gCollapsingPlatformCol', (.1, .1, .1), None),
    ('gameplay_dangeon_keep', 'gPushBlockDL', 'gPushBlockCol', (.1, .1, .1), 'gPushBlockSilverTex'),
)

def build(oot, rom_dir, out):
    import build_kokiri_scene as source
    import build_actor_manifest as actors
    from build_progression_manifest import room_records
    header = '/* Generated original Ydan puzzle collision and child-day placements. */\n'
    meshes = []
    for i, (obj, dl, colname, scale, tex) in enumerate(MODELS):
        matrix = tuple(tuple(scale[r] if r == c else 0 for c in range(3)) for r in range(3))
        static_mesh(oot, rom_dir, obj, dl, out/('DTPZ%02d.BIN'%i), matrix=matrix, texture8=tex)
        if not colname:
            meshes.append('{0}'); continue
        xml = ET.parse(oot/'assets/xml/objects'/('%s.xml'%obj))
        offset = next(int(e.attrib['Offset'],16) for e in xml.iter('Collision') if e.attrib['Name']==colname)
        col = source.collision_header_data(link.read_object(oot,obj,rom_dir),offset)
        if i == 13: scale=(1,1,1) # push_block owns its source runtime scale
        rows=[]; info=[]
        for p in col['polys']:
            verts=[tuple(round(v[k]*scale[k]) for k in range(3)) for v in p['vertices']]
            normal=[p['normal'][k]/scale[k] for k in range(3)]
            length=math.sqrt(sum(n*n for n in normal))
            normal=[round(n*16384/length) for n in normal]
            groups=verts+[normal, [min(v[k] for v in verts) for k in range(3)], [max(v[k] for v in verts) for k in range(3)]]
            rows.append('{{'+','.join('{'+','.join(map(str,g))+'}' for g in groups[:3])+'},'+','.join('{'+','.join(map(str,g))+'}' for g in groups[3:])+'}')
            info.append(p['surface'] | p['ignore']<<8 | p['conveyor']<<11)
        header+='static const collision_triangle_t puzzle_tri_%d[]={%s};\n'%(i,','.join(rows))
        header+='static const uint16_t puzzle_info_%d[]={%s};\n'%(i,','.join(map(str,info)))
        header+='static const uint32_t puzzle_surface_%d[]={%s};\n'%(i,','.join('0x%08Xu'%n for pair in col['surfaces'] for n in pair))
        meshes.append('{puzzle_tri_%d,%d,puzzle_info_%d,puzzle_surface_%d,%d,0,0,0,0,0,0}'%(i,len(rows),i,i,len(col['surfaces'])))
    header+='static const bg_mesh_t puzzle_meshes[]={'+','.join(meshes)+'};\n'
    names=actors.table(oot/'include/tables/actor_table.h','DEFINE_ACTOR')
    segments=source.extract(oot,rom_dir,prefix='ydan'); rows=[]
    for room in range(12):
        for a in room_records(segments['ydan_room_%d'%room],names,{})['actors']:
            kind={'Obj_Switch':0,'Bg_Ydan_Hasi':2,'Bg_Ydan_Maruta':5,'Obj_Lift':7}.get(a['name'])
            if kind is None: continue
            if kind==0: kind=1 if a['params']&7==2 else 0
            elif kind==2: kind+=a['params']&255
            elif kind==5: kind+=1 if a['params']>>8 else 0
            rows.append((room,kind,*a['position'],a['rotation'][1],a['params']))
    header+='typedef struct {short room,kind,x,y,z,yaw;uint16_t params;} dungeon_puzzle_spawn;\n'
    header+='static const dungeon_puzzle_spawn dungeon_puzzles[]={'+','.join('{'+','.join(map(str,r))+'}' for r in rows)+'};\n'
    header+='#define DUNGEON_PUZZLE_COUNT %d\n#define DUNGEON_PUZZLE_MODELS %d\n'%(len(rows),len(MODELS))
    (out.parent/'generated').mkdir(parents=True,exist_ok=True)
    (out.parent/'generated/dungeon_puzzle_data.h').write_text(header)
