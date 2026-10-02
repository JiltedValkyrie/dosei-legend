"""Bake En_Owl's two original skeletons for the M7 budget/actor work.

Assets alone do not install the actor, dialogue, head tracking or departure.
En_Owl has no enemy drops. Source scale is 25/1000; eye segment is 8.
"""
import argparse
import hashlib
import json
from pathlib import Path

from build_dungeon_enemies import model
import build_sgl_scene as sgl

MODELS = (
    ('OWLPERCH', 'gOwlPerchingSkel', ('gOwlPerchAnim',)),
    ('OWLFLY', 'gOwlFlyingSkel', ('gOwlUnfoldWingsAnim', 'gOwlTakeoffAnim',
                               'gOwlFlyAnim', 'gOwlGlideAnim')),
)


def build(oot, rom_dir, out):
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for stem, skeleton, clips in MODELS:
        ranges = model(oot, rom_dir, out, stem, 'object_owl', .025, clips,
            expressions={8: 'gObjOwlEyeOpenTex'}, head_limb=2,
            skeleton=skeleton, source_texture_dimensions=True)
        data, header, vertices, faces = sgl.read_scene(out / (stem + '.BIN'))
        tiles = sgl.collect_tiles(data, header, faces)
        sizes = [(t['width'], t['height']) for t in tiles.values()]
        rows.append(dict(stem=stem, skeleton=skeleton, clips=dict(zip(clips, ranges)),
            vertices=len(vertices), polygons=len(faces), tiles=sizes,
            texture_bytes=sum((w*h//2+7)//8*8+32 for w,h in sizes),
            model_sha256=hashlib.sha256(data).hexdigest(),
            animation_sha256=hashlib.sha256((out/(stem+'.ANM')).read_bytes()).hexdigest()))
    source = oot/'src/overlays/actors/ovl_En_Owl/z_en_owl.c'
    result = dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        scale=.025, models=rows, runtime_registered=False,
        limitations=['Open eye frame only; blinking/head tracking need runtime actor.',
                     'Both models reserved resident; only one drawn at a time.',
                     'No talk/departure/camera implementation implied by asset bake.'])
    (out/'owl_manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot',type=Path,default=Path((__import__('os').environ.get('DOSEI_OOT') or 'D:/Workspace-Claude/game-decomps/n64/oot')))
    parser.add_argument('--rom-dir',type=Path)
    parser.add_argument('--out',type=Path,default=Path(__file__).resolve().parents[1]/'build/field-preflight/owl')
    args=parser.parse_args()
    print(json.dumps(build(args.oot,args.rom_dir,args.out),indent=2))
