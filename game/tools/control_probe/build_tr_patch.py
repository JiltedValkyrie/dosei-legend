"""Bake only the ten selected P3 children into immutable texture pyramids.

Consume the preserved STM, never the ROM/material converter. Every new texel
is an index from the existing parent; CLUT, alpha and all other assets stay put.
Each P3 child has at most 16 visible leaves, 160 commands for the local patch.
Extra levels are used only to resolve cells crossing the near/guard boundary.
"""
import hashlib
import json
from pathlib import Path
import struct
from control import ROOT, RUN, PARENT_POINTS


def main():
    game = RUN / 'oot-sat/game'
    blob = (game / 'build/cd/SAR0.STM').read_bytes()
    h = struct.unpack_from('>16I', blob)
    assert h[0] == 0x4b524d32 and h[1] == 1 and h[7] == len(blob)
    ta = 64 + h[5]*8
    pa = ta + h[3]*48
    records = []
    pixels = bytearray()
    # Scan every LOD/piece too: runtime tags use exact corners, so a duplicate
    # elsewhere must fail the bake instead of silently widening the patch.
    for piece in range(h[2]):
        row = struct.unpack_from('>6i8HII',blob,pa+piece*48)
        np,nf,start = row[8],row[9],row[14]
        points = [struct.unpack_from('>3i',blob,start+i*12) for i in range(np)]
        for face in range(nf):
            ids=struct.unpack_from('>4H',blob,start+np*12+face*20+12)
            world=[(points[i][0]//65536,-points[i][1]//65536,points[i][2]//65536) for i in ids]
            parent=[s for s,allowed in PARENT_POINTS.items() if set(world)<=allowed]
            if len(parent)!=1:continue
            assert piece in (33,34), ('unexpected matching piece',piece,face)
            assert world[2]==world[3] and len(set(world))==3
            normal=struct.unpack_from('>3i',blob,start+np*12+face*20)
            attr=struct.unpack_from('>BB5H',blob,start+np*12+nf*20+face*12)
            assert normal[1]<0 and attr[0]==0 and attr[1]==0x66
            assert attr[3]==0x88 and attr[6]==2, ('unsupported material',attr)
            tile=attr[2]
            w,ht,offset,length,_,_=struct.unpack_from('>HHIIHH',blob,ta+tile*16)
            source=blob[h[12]+offset:h[12]+offset+length]
            assert w in (32,64) and ht in (32,64) and len(source)==w*ht//2
            def sample(x,y):
                n=y*w+x
                return (source[n//2] >> (0 if n&1 else 4))&15
            offsets=[]
            for n in (1,2,4,8,16):
                tw,th=max(8,w//n),ht//n
                for cy in range(n):
                    for cx in range(n):
                        offsets.append(len(pixels))
                        indices=[]
                        for y in range(th):
                            for x in range(tw):
                                sx=round((cx+x/(tw-1))*(w-1)/n)
                                sy=round((cy+y/(th-1))*(ht-1)/n)
                                indices.append(sample(sx,sy))
                        pixels.extend((indices[i]<<4)|indices[i+1] for i in range(0,len(indices),2))
            records.append(dict(piece=piece,face=face,source=parent[0],world=world,
                                tile=tile,width=w,height=ht,offsets=offsets,
                                parent_sha256=hashlib.sha256(source).hexdigest()))
    assert len(records)==10
    assert len({tuple(map(tuple,r['world'])) for r in records})==10
    assert {s:sum(r['source']==s for r in records) for s in PARENT_POINTS}=={746:4,738:2,745:2,613:2}
    assert len(pixels)<524288 and all(o%8==0 for r in records for o in r['offsets'])
    report=json.loads((game/'build/generated/field_stream_report.json').read_text())
    assert report['vram_total']+len(pixels)<=report['vram_limit']
    assert report['worst']['polys']+report['actor_polygons']+150<2456
    (RUN/'verification/tr-assets.json').write_text(json.dumps(dict(
        stm_sha256=hashlib.sha256(blob).hexdigest(),extra_vram=len(pixels),
        max_extra_commands=150,extra_sprite_slots=0,levels=[1,2,4,8,16],faces=records),indent=2))
    lines=['/* Generated from the frozen Field STM; positions use SGL Y-down. */',
           '#define TR_PATCH_FACES 10',f'#define TR_PATCH_BYTES {len(pixels)}u',
           'typedef struct { short world[4][3]; unsigned short offset[5]; unsigned char width,height; } tr_asset;',
           'static const tr_asset tr_assets[TR_PATCH_FACES] = {']
    for r in records:
        pts=','.join('{%d,%d,%d}'%(x,-y,z) for x,y,z in r['world'])
        lines.append('    {{'+pts+'},{'+','.join(str(r['offsets'][x]//8) for x in (0,1,5,21,85))+'},%d,%d},'%(r['width'],r['height']))
    lines+=['};','']
    (game/'src/tr_patch_data.h').write_text('\n'.join(lines))
    (game/'build/cd/TRPATCH.TEX').write_bytes(pixels)
    print(f'Ten local P3 faces; {len(pixels)} extra VRAM bytes; <=160 commands; zero sprite slots')


if __name__=='__main__':main()
