"""Bake courtyard Zelda, Impa and the source Ganondorf window sequence."""
import argparse
import json
from pathlib import Path
import build_npc_sprites as sprites
import courtyard_sources

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot',type=Path,required=True)
    parser.add_argument('--out',type=Path,default=Path('build/child-route-courtyard'))
    args=parser.parse_args()
    work,out=args.out/'sprite-work',args.out/'sprites'
    work.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
    sprites.bake_generic(args.oot,args.oot/'baseroms/ntsc-1.2',work,out,args.out,
                         only_objects=courtyard_sources.OBJECTS,extra_sources=courtyard_sources.SOURCES,
                         extra_objects=courtyard_sources.OBJECTS)
    rows=json.loads((args.out/'generic_sprites.json').read_text())
    files={out/('G%03X%02X.SPR'%(row[0],row[3])) for row in rows}
    print('courtyard sprites:',len(rows),'keys,',len(files),'sheets,',sum(p.stat().st_size for p in files),'bytes')

if __name__=='__main__':main()
