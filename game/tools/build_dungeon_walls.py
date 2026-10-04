"""Bg_Ydan_Sp wall webs, full source placement rotation on visuals/collision."""
import math
import build_link_model as link
from build_shop_props import static_mesh

def matrix_yxz(rot):
    sx,cx=math.sin(rot[0]*math.tau/65536),math.cos(rot[0]*math.tau/65536)
    sy,cy=math.sin(rot[1]*math.tau/65536),math.cos(rot[1]*math.tau/65536)
    sz,cz=math.sin(rot[2]*math.tau/65536),math.cos(rot[2]*math.tau/65536)
    return link.matmul(link.matmul(((cy,0,sy),(0,1,0),(-sy,0,cy)),
                                  ((1,0,0),(0,cx,-sx),(0,sx,cx))),
                                  ((cz,-sz,0),(sz,cz,0),(0,0,1)))

def build(oot,rom_dir,out):
    import build_kokiri_scene as source
    import build_actor_manifest as actors
    from build_progression_manifest import room_records
    names=actors.table(oot/'include/tables/actor_table.h','DEFINE_ACTOR')
    segments=source.extract(oot,rom_dir,prefix='ydan')
    data=link.read_object(oot,'object_ydan_objects',rom_dir)
    col=source.collision_header_data(data,0x6050)
    header='/* gDTWebWallCol; Actor YXZ rotation baked before Dyna registration. */\n'
    spawns=[]
    for room in range(12):
        for a in room_records(segments['ydan_room_%d'%room],names,{})['actors']:
            if a['name']!='Bg_Ydan_Sp' or a['params']>>12!=1:continue
            index=len(spawns);matrix=matrix_yxz(a['rotation']);rows=[]
            for p in col['polys']:
                v=[tuple(round(n*.1) for n in link.transform(matrix,(0,0,0),v)) for v in p['vertices']]
                normal=[round(n) for n in link.transform(matrix,(0,0,0),p['normal'])]
                values=[n for point in v for n in point]+normal
                values += [min(point[k] for point in v) for k in range(3)]
                values += [max(point[k] for point in v) for k in range(3)]
                rows.append('{{{'+','.join(map(str,values[:3]))+'},{'+','.join(map(str,values[3:6]))+'},{'+','.join(map(str,values[6:9]))+'}},'+
                            '{'+','.join(map(str,values[9:12]))+'},{'+','.join(map(str,values[12:15]))+'},{'+','.join(map(str,values[15:]))+'}}')
            header+='static const collision_triangle_t wall_tri_%d[]={\n'%index+','.join(rows)+'\n};\n'
            spawns.append((room,*a['position'],a['rotation'][1],a['params']&63,(a['params']>>6)&63))
            static_mesh(oot,rom_dir,'object_ydan_objects','gDTWebWallDL',out/('DTWALL%d.BIN'%index),.1,cutout=True,matrix=matrix)
    header+='static const bg_mesh_t wall_meshes[]={\n'
    header+=',\n'.join('{wall_tri_%d,sizeof(wall_tri_%d)/sizeof(wall_tri_%d[0]),0,0,0,0,0,0,0,0,0}'%(i,i,i) for i in range(len(spawns)))+'\n};\n'
    header+='typedef struct {short room,x,y,z,yaw,flag,burn;} dungeon_wall_spawn;\n'
    header+='static const dungeon_wall_spawn dungeon_walls[]={\n'+',\n'.join('{'+','.join(map(str,row))+'}' for row in spawns)+'\n};\n'
    header+='#define DUNGEON_WALL_COUNT %d\n'%len(spawns)
    (out.parent/'generated/dungeon_wall_data.h').write_text(header)
