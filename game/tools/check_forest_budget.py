"""Check the post-room upload peak, including every loaded forest prop."""
from pathlib import Path
import re
import struct

import vdp1_budget as budget

ROOT = Path(__file__).resolve().parents[1]


def mesh_cost(path):
    data = path.read_bytes()
    magic, _, _, faces, _, records, _, _ = struct.unpack_from('>8I', data)
    if magic != 0x4b465231:
        raise ValueError('Not KFR1: %s' % path)
    # Same identity as upload_actor: offsets AND dimensions, per mesh.
    tiles = {struct.unpack_from('>IIH', data, records + i * 20 + 8)
             for i in range(faces)}
    return (sum(budget.tile_bytes((size >> 8) * 8, size & 255)
                for _, _, size in tiles), len(tiles))


def actor_peak(cd, placements):
    rows = placements.split('const kokiri_npc_t kokiri_npcs')[1].split('};')[0]
    children = []
    for row in re.findall(r'\{([^{}]+)\}', rows):
        values = [v.strip() for v in row.split(',')]
        x, _, z, _, param = (int(v, 0) for v in values[:5])
        kind, _, scene = values[5:]
        if int(scene) != 0 or kind != 'KOKIRI_NPC_CHILD':
            continue
        model = 2 + (param & 255)
        radius = 240 if (param & 255) == 5 else 180
        children.append((x, z, radius, model))
    # Mido can move; Saria is forced visible in her greeting. Count both at
    # every location, regardless of room/presence flags, for a safe upper bound.
    props = ['ROCK', 'POT', 'CHEST', 'BUSH', 'GOSSIP']
    props += ['SIGN%d' % i for i in range(11)]
    fixed = [mesh_cost(cd / (name + '.BIN')) for name in props + ['NPC00', 'NPC01']]
    costs = {m: mesh_cost(cd / ('NPC%02d.BIN' % m)) for _, _, _, m in children}
    # A visibility circle lies inside its box. Every maximal overlapping box
    # set includes a pair of box boundaries; no sampling gaps between points.
    xs = {x + side * r for x, _, r, _ in children for side in (-1, 1)}
    zs = {z + side * r for _, z, r, _ in children for side in (-1, 1)}
    peaks = [sum(c[k] for c in fixed) for k in (0, 1)]
    for x in xs:
        for z in zs:
            visible = {m for nx, nz, r, m in children
                       if abs(nx - x) <= r and abs(nz - z) <= r}
            for k in (0, 1):
                peaks[k] = max(peaks[k], sum(c[k] for c in fixed) +
                               sum(costs[m][k] for m in visible))
    return tuple(peaks)


def check(root=ROOT):
    cd = root / 'build/cd'
    peak = actor_peak(cd, (root / 'build/generated/kokiri_actors.c').read_text())
    mouth = mesh_cost(cd/'TREEMTH.BIN')
    peak = tuple(peak[i]+mouth[i] for i in range(2))
    if peak[0] > budget.FOREST_ACTOR_BYTES or peak[1] > budget.FOREST_ACTOR_SLOTS:
        raise ValueError('Forest actors exceed reservation: %s' % (peak,))
    header = (root / 'build/generated/link_scene.h').read_text()
    value = lambda name: int(re.search(r'#\s*define\s+' + name + r'\s+(\d+)', header)[1])
    link_slots = value('LINK_TILE_COUNT')
    resident = value('LINK_PIXEL_BYTES') + link_slots * 32 + budget.RUNTIME_SPRITE_BYTES
    for path in sorted(cd.glob('S1R*.MSH')):
        _, _, _, tiles, pixels, _, _, _ = struct.unpack_from('>8I', path.read_bytes())
        used = resident + pixels + tiles * 32 + budget.FOREST_ACTOR_BYTES
        slots = 1 + link_slots + budget.RUNTIME_SPRITE_SLOTS + tiles + budget.FOREST_ACTOR_SLOTS
        if used + budget.FOREST_VRAM_MARGIN > budget.VDP1_USER_AREA or slots > budget.MAX_SPRITE_SLOTS:
            raise ValueError('%s: actors included, VRAM %d + %d margin / %d; slots %d / %d' %
                             (path.name, used, budget.FOREST_VRAM_MARGIN,
                              budget.VDP1_USER_AREA, slots, budget.MAX_SPRITE_SLOTS))
        print('%s: actors included, %d B spare; %d sprite slots' %
              (path.name, budget.VDP1_USER_AREA - used, slots))
    print('Forest actor upper bound: %d B, %d slots' % peak)
    # World props remain loaded across Tree room streaming. Count all meshes,
    # including off-room walls/torches: draw visibility does not free their tiles.
    names=['CHEST','DTDOOR','DTWEB']
    costs=[mesh_cost(cd/(name+'.BIN')) for name in names]
    actor_bytes=sum(c[0] for c in costs);actor_slots=sum(c[1] for c in costs)
    for path in sorted(cd.glob('S7R*.MSH')):
        room=int(path.stem[3:],36)
        rows=(root/'build/generated/dungeon_puzzle_data.h').read_text().split('dungeon_puzzles[]={')[1].split('};')[0]
        models=set()
        if room in (3,5):models.add(13)
        by_kind=((0,),(4,5,6),(7,),(9,),(8,),(11,),(10,),(12,))
        for row in re.findall(r'\{([^{}]+)\}',rows):
            values=[int(v) for v in row.split(',')]
            if values[0]==room:models.update(by_kind[values[1]])
        puzzle_cost=[mesh_cost(cd/('DTPZ%02d.BIN'%i)) for i in models]
        gomas=(root/'build/generated/dungeon_enemy_data.h').read_text().split('goma_spawns[]={')[1].split('};')[0]
        if any(int(row.split(',')[0])==room for row in re.findall(r'\{([^{}]+)\}',gomas)):
            puzzle_cost.extend(mesh_cost(cd/(n+'.BIN')) for n in ('GOMALAR','GOMAEGG'))
        hints=(root/'build/generated/dungeon_enemy_data.h').read_text().split('hint_spawns[]={')[1].split('};')[0]
        if any(int(row.split(',')[0])==room for row in re.findall(r'\{([^{}]+)\}',hints)):
            puzzle_cost.extend(mesh_cost(cd/(n+'.BIN')) for n in ('HINTNUT','HINTFLOW','HINTBALL'))
        babas=(root/'build/generated/dungeon_enemy_data.h').read_text().split('baba_spawns[]={')[1].split('};')[0]
        if any(int(row.split(',')[0])==room for row in re.findall(r'\{([^{}]+)\}',babas)):
            puzzle_cost.append(mesh_cost(cd/'DHEAD.BIN'))
        skulls=(root/'build/generated/dungeon_enemy_data.h').read_text().split('skull_spawns[]={')[1].split('};')[0]
        if any(int(row.split(',')[0])==room for row in re.findall(r'\{([^{}]+)\}',skulls)):
            puzzle_cost.append(mesh_cost(cd/'SKULL.BIN'))
        spider_rows=(root/'build/generated/dungeon_enemy_data.h').read_text().split('wall_spawns[]={')[1].split('};')[0]
        spider_types={bool(int(row.split(',')[-1])&0xE000) for row in re.findall(r'\{([^{}]+)\}',spider_rows) if int(row.split(',')[0])==room}
        if True in spider_types:puzzle_cost += [mesh_cost(cd/(n+'.BIN')) for n in ('GOLDSK','SKTOKEN')]
        if False in spider_types and not any(int(row.split(',')[0])==room for row in re.findall(r'\{([^{}]+)\}',skulls)):
            puzzle_cost.append(mesh_cost(cd/'SKULL.BIN'))
        walls=(root/'build/generated/dungeon_wall_data.h').read_text().split('dungeon_walls[]={')[1].split('};')[0]
        for i,row in enumerate(re.findall(r'\{([^{}]+)\}',walls)):
            if int(row.split(',')[0])==room:puzzle_cost.append(mesh_cost(cd/('DTWALL%d.BIN'%i)))
        torches=(root/'build/generated/dungeon_torch_data.h').read_text().split('dungeon_torches[] = {')[1].split('};')[0]
        types={int(row.split(',')[-1])>>12 for row in re.findall(r'\{([^{}]+)\}',torches) if int(row.split(',')[0])==room}
        puzzle_cost += [mesh_cost(cd/('DTTORCH%d.BIN'%i)) for i in types]
        _,_,_,tiles,pixels,_,_,_=struct.unpack_from('>8I',path.read_bytes())
        used=resident+pixels+tiles*32+actor_bytes+sum(c[0] for c in puzzle_cost)
        slots=1+link_slots+budget.RUNTIME_SPRITE_SLOTS+tiles+actor_slots+sum(c[1] for c in puzzle_cost)
        if used>budget.VDP1_USER_AREA or slots>budget.MAX_SPRITE_SLOTS:
            raise ValueError('%s: dungeon props overflow VRAM %d/%d, slots %d/%d'%
                             (path.name,used,budget.VDP1_USER_AREA,slots,budget.MAX_SPRITE_SLOTS))
        print('%s: dungeon props included, %d B spare; %d sprite slots'%
              (path.name,budget.VDP1_USER_AREA-used,slots))
    print('Dungeon prop upload: %d B, %d slots'%(actor_bytes,actor_slots))
    for path in sorted(cd.glob('S9R*.MSH')):
        room=int(path.stem[3:],36)
        names=['DTDOOR'] + (['GOHMA','GOMALAR','GOMAEGG','BOSSHRT','BLUEWARP'] if room==1 else [])
        costs=[mesh_cost(cd/(name+'.BIN')) for name in names]
        _,vertices,polygons,tiles,pixels,_,_,_=struct.unpack_from('>8I',path.read_bytes())
        used=resident+pixels+tiles*32+sum(c[0] for c in costs)
        slots=1+link_slots+budget.RUNTIME_SPRITE_SLOTS+tiles+sum(c[1] for c in costs)
        if used>budget.VDP1_USER_AREA or slots>budget.MAX_SPRITE_SLOTS:
            raise ValueError('%s: boss actors overflow VRAM %d/%d, slots %d/%d'%
                             (path.name,used,budget.VDP1_USER_AREA,slots,budget.MAX_SPRITE_SLOTS))
        print('%s: boss actors included, %d B spare; %d sprite slots'%
              (path.name,budget.VDP1_USER_AREA-used,slots))
        # Three larvae can share uploaded artwork but submit three meshes.
        draw_names=['DTDOOR'] + (['GOHMA','GOMALAR','GOMALAR','GOMALAR','BOSSHRT','BLUEWARP'] if room==1 else [])
        geometry=[struct.unpack_from('>8I',(cd/(name+'.BIN')).read_bytes())[2:4] for name in draw_names]
        vertices+=value('LINK_VERTEX_COUNT')+sum(g[0] for g in geometry)
        polygons+=value('LINK_POLYGON_COUNT')+sum(g[1] for g in geometry)
        if vertices>3200 or polygons>3750:
            raise ValueError('%s: boss geometry exceeds SGL capacity (%d vertices, %d polygons)'%(path.name,vertices,polygons))
        print('%s: conservative room + Link + boss/minions/rewards: %d vertices, %d polygons'%(path.name,vertices,polygons))

    # Cinematic banks retain every texture uploaded during the whole sequence,
    # but only draw the currently selected Saria pose / visible source actors.
    stories=[(8,5,['NPC19','NPC20','NPC21','NPC22'],['NPC20']),
             (10,0,['OWLPERCH','OWLFLY'],['OWLFLY']),
             (20,0,[],[]),(21,0,['GODBODY','GODAURA','TRIFORCE'],['GODBODY']*3+['GODAURA']*3+['TRIFORCE']),
             (23,0,['GODBODY','GODAURA'],['GODBODY']*3+['GODAURA']*3),
             (25,0,['GODBODY','GODAURA'],['GODBODY']*3+['GODAURA']*3),
             (26,0,['GODBODY','GODAURA'],['GODBODY']*3+['GODAURA']*3),
             (28,0,['EMERALD'],['EMERALD'])]
    from asset_names import room_asset
    for scene,room,loaded,drawn in stories:
        path=cd/room_asset(scene,room,'MSH')
        stream=cd/room_asset(scene,room,'STM')
        if not path.exists() and stream.exists():
            # Streamed Field (KRM2): fixed tile pools and the worst resident set.
            blob=stream.read_bytes()
            h=struct.unpack_from('>16I',blob)
            pixels=sum(struct.unpack_from('>2I',blob,64+8*i)[0]*struct.unpack_from('>2I',blob,64+8*i)[1]
                       for i in range(h[5]))
            vertices,polygons,tiles=h[8],h[9],h[6]
        else:
            _,vertices,polygons,tiles,pixels,_,_,_=struct.unpack_from('>8I',path.read_bytes())
        costs=[mesh_cost(cd/(n+'.BIN')) for n in loaded]
        used=resident+pixels+tiles*32+sum(c[0] for c in costs)
        slots=1+link_slots+budget.RUNTIME_SPRITE_SLOTS+tiles+sum(c[1] for c in costs)
        geometry=[struct.unpack_from('>8I',(cd/(n+'.BIN')).read_bytes())[2:4] for n in drawn]
        vertices+=value('LINK_VERTEX_COUNT')+sum(g[0] for g in geometry)
        polygons+=value('LINK_POLYGON_COUNT')+sum(g[1] for g in geometry)
        if used>budget.VDP1_USER_AREA or slots>budget.MAX_SPRITE_SLOTS or vertices>3200 or polygons>3750:
            raise ValueError('%s: story budget overflow: %d bytes, %d slots, %d vertices, %d polygons'%(path.name,used,slots,vertices,polygons))
        print('%s: story + Link: %d B spare; %d slots; %d vertices, %d polygons'%(path.name,budget.VDP1_USER_AREA-used,slots,vertices,polygons))


if __name__ == '__main__':
    check()
