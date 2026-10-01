"""Original dungeon enemy geometry and source animation tracks.

Uses the existing skeleton reader, vertex ownership and character texture policy.
"""
import struct
import xml.etree.ElementTree as ET
import build_actor_model as actor
import build_link_model as link
from cutscene_animation import write_track

def model(oot,rom_dir,out,stem,obj,scale,clips,expressions=None,displays=None,head_limb=None,offsets_extra=None,cutout=False,skeleton=None,source_texture_dimensions=False):
    path=oot/'assets/xml/objects'/('%s.xml'%obj)
    xml=ET.parse(path);offsets={n.attrib['Name']:int(n.attrib['Offset'],16) for n in xml.iter() if 'Offset' in n.attrib and 'Name' in n.attrib and not n.attrib['Offset'].startswith('.')}
    offsets.update(offsets_extra or {})
    data=link.read_object(oot,obj,rom_dir)
    skel=next((s for s in xml.iter('Skeleton') if skeleton is None or s.attrib['Name']==skeleton),None)
    if skel is None:raise ValueError('%s: missing skeleton %s'%(obj,skeleton))
    assert skel.attrib['LimbType']=='Standard'
    table,count=actor.read_skeleton(data,offsets[skel.attrib['Name']]);limbs,_=actor.read_limbs(data,table,count)
    for index,name in (displays or {}).items():
        limbs[index-1]['near']=limbs[index-1]['far']=0x06000000|offsets[name]
    _,root,rot=actor.read_animation(data,offsets[clips[0]],count,0)
    link.HEAD_LIMB=-1;link.LIMB_NONE=255
    placed=link.walk_skeleton(limbs,rot,root);poses={i:(m,o) for i,m,o,_ in placed}
    lists=link.LimbLists(b'',b'');lists.segments={6:data,8:struct.pack('>II',0xDF000000,0)}
    if source_texture_dimensions:
        lists.texture_dimensions={0x06000000|int(n.attrib['Offset'],16):
            (int(n.attrib['Width']),int(n.attrib['Height'])) for n in xml.iter('Texture')
            if 'Width' in n.attrib and 'Height' in n.attrib}
    for segment,name in (expressions or {}).items():lists.segments[segment]=data[offsets[name]:]
    lists.matrix_limbs=[i for i,_,_,dl in placed if dl]
    before=link.LimbLists.unresolved;faces=[]
    for i,_,_,dl in placed:
        if not dl:continue
        lists.current_limb=i;first=len(lists.faces);lists.walk(dl)
        for f in lists.faces[first:]:
            face=dict(f);face['local']=[tuple(v[:3]) for v in f['vertices']]
            face['vertices']=[link.transform(*poses[owner],v[:3])+tuple(v[3:]) for v,owner in zip(f['vertices'],f['vertex_limbs'])]
            face['limb']=i;faces.append(face)
    if link.LimbLists.unresolved!=before or lists.external_lists:raise ValueError('%s unresolved material'%obj)
    link.character_textures.mark_faces(faces,path,head_limb,expressions or {})
    if cutout:
        for face in faces: face['transparent'] = True
    link.apply_primitive_colour(faces);faces=link.scale_faces(faces,scale)
    dest=out/(stem+'.BIN');_,_,owners,locals_=link.write_model(faces,dest,skinned=True)
    ranges=[];timeline=[]
    for name in clips:
        length,_,_=actor.read_animation(data,offsets[name],count,0)
        ranges.append((len(timeline),length));timeline.extend((offsets[name],f) for f in range(length))
    def track():
        for offset,frame in timeline:
            _,root,rot=actor.read_animation(data,offset,count,frame)
            pose={i:(m,o) for i,m,o,_ in link.walk_skeleton(limbs,rot,root)}
            yield [tuple(v*scale for v in link.transform(*pose[owner],local)) for owner,local in zip(owners,locals_)]
    write_track(dest.with_suffix('.ANM'),track())
    return ranges

def build(oot,rom_dir,out):
    import build_kokiri_scene as source
    import build_actor_manifest as actors
    from build_progression_manifest import room_records
    clips=model(oot,rom_dir,out,'SKULL','object_st',.04,
                ('object_st_Anim_000304','object_st_Anim_0055A8','object_st_Anim_005B98'))
    model(oot,rom_dir,out,'GOLDSK','object_st',.02,('object_st_Anim_000304',),displays={
        23:'object_st_DL_004788',8:'object_st_DL_0046F0',14:'object_st_DL_004658',11:'object_st_DL_0045C0',
        26:'object_st_DL_004820',20:'object_st_DL_0048B8',17:'object_st_DL_004950',29:'object_st_DL_0049E8',
        5:'object_st_DL_003FB0',4:'object_st_DL_0043D8'})
    from build_shop_props import static_mesh
    static_mesh(oot,rom_dir,'object_gi_sutaru','gGiSkulltulaTokenDL',out/'SKTOKEN.BIN',.25)
    baba_clips=model(oot,rom_dir,out,'DHEAD','object_dekubaba',.01,('gDekuBabaFastChompAnim','gDekuBabaPauseChompAnim'))
    hint_clips=model(oot,rom_dir,out,'HINTNUT','object_hintnuts',.01,
        tuple('gHintNuts%sAnim'%s for s in ('Up','LookAround','Stand','Spit','Burrow','Unburrow','Run','Talk','Freeze')),head_limb=3,cutout=True)
    static_mesh(oot,rom_dir,'object_hintnuts','gHintNutsFlowerDL',out/'HINTFLOW.BIN',.01,cutout=True)
    static_mesh(oot,rom_dir,'object_hintnuts','gHintNutsNutDL',out/'HINTBALL.BIN',.01,cutout=True)
    goma_clips=model(oot,rom_dir,out,'GOMALAR','object_gol',.01,
        tuple('gObjectGol%sAnim'%s for s in ('Stand','Running','PrepareJump','JumpHeadbutt','LandFromJump','Damaged','Death','DeadTwitching')))
    static_mesh(oot,rom_dir,'object_gol','gObjectGolEggDL',out/'GOMAEGG.BIN',.01)
    names=actors.table(oot/'include/tables/actor_table.h','DEFINE_ACTOR')
    segments=source.extract(oot,rom_dir,prefix='ydan');rows=[];walls=[];babas=[];hints=[];gomas=[]
    for room in range(12):
        for a in room_records(segments['ydan_room_%d'%room],names,{})['actors']:
            if a['name']=='En_St':rows.append((room,*a['position'],a['rotation'][1],a['params']))
            if a['name']=='En_Sw':walls.append((room,*a['position'],a['rotation'][1],a['params']))
            if a['name']=='En_Hintnuts':hints.append((room,*a['position'],a['rotation'][1],a['params']))
            if a['name']=='En_Goma':gomas.append((room,*a['position'],a['rotation'][1],a['params']))
            if a['name']=='En_Dekubaba':
                if a['params']!=0:raise ValueError('Big Deku Baba requires separate runtime scale')
                babas.append((room,*a['position'],a['rotation'][1],a['params']))
    header='/* En_St source placements and animation ranges. Drop table 14. */\n'
    header+='typedef struct {short room,x,y,z,yaw,params;} skull_spawn;\n'
    header+='static const skull_spawn skull_spawns[]={'+','.join('{'+','.join(map(str,r))+'}' for r in rows)+'};\n'
    header+='static const unsigned short skull_clips[][2]={'+','.join('{%d,%d}'%r for r in clips)+'};\n'
    header+='#define SKULL_SPAWN_COUNT %d\n'%len(rows)
    header+='static const skull_spawn wall_spawns[]={'+','.join('{'+','.join(map(str,r))+'}' for r in walls)+'};\n'
    header+='#define WALL_SKULL_COUNT %d\n'%len(walls)
    header+='static const skull_spawn baba_spawns[]={'+','.join('{'+','.join(map(str,r))+'}' for r in babas)+'};\n'
    header+='static const unsigned short baba_clips[][2]={'+','.join('{%d,%d}'%r for r in baba_clips)+'};\n'
    header+='#define DEKU_BABA_COUNT %d\n'%len(babas)
    header+='static const skull_spawn hint_spawns[]={'+','.join('{'+','.join(map(str,r))+'}' for r in hints)+'};\n'
    header+='static const unsigned short hint_clips[][2]={'+','.join('{%d,%d}'%r for r in hint_clips)+'};\n'
    header+='#define HINT_NUTS_COUNT %d\n'%len(hints)
    header+='static const skull_spawn goma_spawns[]={'+','.join('{'+','.join(map(str,r))+'}' for r in gomas)+'};\n'
    header+='static const unsigned short goma_clips[][2]={'+','.join('{%d,%d}'%r for r in goma_clips)+'};\n'
    header+='#define GOMA_LARVA_COUNT %d\n'%len(gomas)
    (out.parent/'generated/dungeon_enemy_data.h').write_text(header)
