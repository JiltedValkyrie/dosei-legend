"""Original nine-part Emerald story scenery and principal source effect meshes."""
from pathlib import Path
import collections,json
import build_cutscenes as cs
import build_hybrid_scene as hybrid
import build_sgl_scene as sgl
import build_room_scene as rooms
import build_opening_banks as opening
import asset_names
from build_shop_props import static_mesh

def emit(oot,rom_dir,out,head,actor,forest,normal):
    rows=[]
    def pack(bank,vertices,faces,tiles,records):
        mesh,pixels,bounds=rooms.pack_room(vertices,faces,tiles,records,normal)
        if len(vertices)>3200 or len(faces)>3000:raise ValueError('Story scenery exceeds geometry reserve')
        (out/asset_names.room_asset(bank,0,'MSH')).write_bytes(mesh)
        (out/asset_names.room_asset(bank,0,'TEX')).write_bytes(pixels)
        rows.append(dict(scene=bank,id=0,vertices=len(vertices),polygons=len(faces),tiles=len(tiles),pixel_bytes=len(pixels),objects=len(bounds)))
    # hiral_demo intentionally has no room geometry; its actors and sky own the shot.
    pack(21,[],[],collections.OrderedDict(),[])
    for bank,prefix in ((23,'spot09'),(25,'spot16')):
        folder=out/('story-'+prefix)
        _,v,f,t=hybrid.convert(oot,head,actor,folder,rom_dir=rom_dir,prefix=prefix,
            room=prefix+'_room_0',layout={},base_tile_limit=32,source_tessellation=True)
        pack(bank,v,f,t,json.loads((folder/'texture_manifest.json').read_text())['faces'])
    for part,bank in ((1,20),(7,26),(9,28)):
        entry=next(e for e in cs.CUTSCENES if e['key']=='EMERALD%d'%part)
        v,f,t=opening.forest_bank(forest,cs.read_cutscene(entry)['track'])
        records=[dict(object=0,indices=x['idx']) for x in f]
        pack(bank,v,f,t,records)
    static_mesh(oot,rom_dir,'object_god_lgt','gGoldenGoddessBodyDL',out/'GODBODY.BIN',.003,flat=True)
    static_mesh(oot,rom_dir,'object_god_lgt','gGoldenGoddessAuraDL',out/'GODAURA.BIN',.1,cutout=True)
    static_mesh(oot,rom_dir,'object_triforce_spot','gTriforceDL',out/'TRIFORCE.BIN',.1,flat=True)
    static_mesh(oot,rom_dir,'object_gi_jewel','gGiKokiriEmeraldGemDL',out/'EMERALD.BIN',.1,extra=('gGiKokiriEmeraldSettingDL',))
    (out/'emerald_story_manifest.json').write_text(json.dumps(rows,indent=2)+'\n')
    return rows
