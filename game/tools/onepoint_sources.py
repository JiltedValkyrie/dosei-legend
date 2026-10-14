"""Scene-owned OnePoint recipes, extracted verbatim from z_onepointdemo.

Only the reusable interpolation/queue engine stays resident. Each scene pack
contains precisely its admitted source setup cases and their mutable tables.
"""
import re
from owl_sources import function, camera_source

ACTOR_SCRIPTS = {
    'En_Owl': (8700,),
    'En_Du': (3330,),
    'En_Go2': (4190, 4200),
    'Bg_Ddan_Jd': (3060,),
    'Bg_Ddan_Kd': (3050, 1020),
    'Bg_Dodoago': (3380, 3065),
    'Door_Warp1': (9703,),
    'En_Ta': (4175,),
    'En_Niw': (2290,),
    'En_Box': (4500,),
    'Bg_Hidan_Curtain': (3350, 3360),
    'En_Syateki_Man': (8002,),
    'En_Bom_Bowl_Man': (8010,),
    'Bg_Spot18_Basket': (4210, 4220),
    'Bg_Spot18_Shutter': (4221,),
    'Bg_Spot16_Bombstone': (4180,),
    'Obj_Bean': (2210,),
}


def scripts(names, oot=None):
    ids = {script for name in names for script in ACTOR_SCRIPTS.get(name, ())}
    if oot and any('OnePointCutscene_Attention' in (oot / ('src/overlays/actors/ovl_' + name +
                     '/z_' + name.lower() + '.c')).read_text(encoding='utf-8') for name in names):
        ids.add(5010)
    return sorted(ids)


def case(source, ident):
    """Cases in SetInfo are at a unique indentation, including shared labels."""
    labels=list(re.finditer(r'^        (?:case \d+|default):',source,re.M))
    index=next(i for i,m in enumerate(labels) if m.group()==f'        case {ident}:')
    start=labels[index].start()
    while index+1<len(labels):
        end=labels[index+1].start()
        contents=re.sub(r'//[^\n]*','',source[labels[index].end():end]).strip()
        if contents:
            return source[start:end]
        index+=1
    raise ValueError('source OnePoint case has no next label: '+str(ident))


def pack_source(oot, names):
    ids = scripts(names, oot)
    if not ids:
        return ''
    source = (oot / 'src/code/z_onepointdemo.c').read_text(encoding='utf-8')
    chunks = ['/* Exact scene-local OnePoint source setup and keyframe data. */']
    chunks += ['#include "' + header + '"' for header in (
        'play_state.h', 'player.h', 'camera.h', 'one_point_cutscene.h', 'array_count.h',
        'z_lib.h', 'quake.h', 'sfx.h', 'versions.h', 'save.h', 'olib.h', 'letterbox.h',
        'interface.h', 'math.h', 'libc64/math64.h', 'libc64/qrand.h', 'attributes.h',
        'printf.h', 'terminal.h', 'scene.h', 'oot_cutscene_camera.h', 'cutscene_spline.h', 'gfx.h')]
    if 3050 in ids:
        start = source.index('static CutsceneCameraPoint D_8012013C')
        end = source.index('\nstatic CutsceneCameraPoint sCrawlspace', start)
        chunks.append(source[start:end])
        for name in ('OnePointCutscene_Vec3sToVec3f', 'OnePointCutscene_SetCsCamPoints'):
            chunks.append('static ' + function(source, name))
    if 4500 in ids:
        for name in ('OnePointCutscene_AddVecGeoToVec3f', 'OnePointCutscene_RaycastDown'):
            chunks.append('static ' + function(source, name))
    chunks.append('''extern "C" int oot_pack_onepoint_setup(PlayState* play, s16 subCamId,
        s16 csId, Actor* actor, s16 timer) {
    switch (csId) {''')
    chunks += ['        case ' + str(i) + ':' for i in ids]
    chunks.append('''            break;
        default: return false;
    }
    if (!play) return true; /* cold admission query, no mutation */
    Camera* subCam = play->cameraPtrs[subCamId];
    Camera* mainCam = play->cameraPtrs[CAM_ID_MAIN];
    Player* player = GET_PLAYER(play);
    OnePointCsInfo* csInfo = &subCam->paramData.uniq9.csInfo;
    s32 i;
    PosRot spA0, sp8C;
    Vec3f spC0, spB4;
    VecGeo spD0;
    switch (csId) {''')
    for ident in ids:
        if ident == 3065 and 3380 in ids:
            continue
        if ident == 5010:
            start = source.index('        case 5010:')
            end = source.index('        case 9500:', start)
            chunks.append(source[start:end])
        else:
            chunks.append(case(source, ident))
    chunks.append('    }\n    return true;\n}\n')
    chunks.append(camera_source(oot, packed=True, attention=5010 in ids, demo9_enabled=3050 in ids,
                                free2_enabled=bool({4500,4180}&set(ids))))
    return '\n'.join(chunks)


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    from oot_core_import import fix_float_literals
    parser = argparse.ArgumentParser()
    parser.add_argument('--oot', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    text = '#include "oot_prelude.h"\n' + pack_source(args.oot, [*ACTOR_SCRIPTS, 'Obj_Switch'])
    args.out.write_text(fix_float_literals(text, {'fxl': 0}, 'onepoint_fixture'), encoding='utf-8')
