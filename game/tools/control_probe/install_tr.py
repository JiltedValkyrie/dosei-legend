"""Install the local renderer experiment only into Astra's existing snapshot."""
from pathlib import Path
import shutil
from control import RUN


def main():
    game=RUN/'oot-sat/game'
    backup=RUN/'tr-base-src'
    backup.mkdir(exist_ok=True)
    for name in ('kokiri_sgl.c','main.c'):
        src=game/'src'/name
        if not (backup/name).exists():shutil.copy2(src,backup/name)
    path=game/'src/kokiri_sgl.c'
    s=(backup/path.name).read_text()
    def patch(old,new):
        nonlocal s
        assert s.count(old)==1,(old[:80],s.count(old))
        s=s.replace(old,new)
    patch('#include "control_probe.h"','#include "control_probe.h"\n'
          'static unsigned tr_mode(void);\nstatic unsigned tr_match(unsigned);\n'
          'static bool tr_load(void);\nstatic void tr_draw(unsigned);\nstatic unsigned tr_last_mode;')
    patch('forest_mesh[p + i] = forest_face_flags(p + i);',
          'forest_mesh[p + i] = forest_face_flags(p + i) | tr_match(p + i);')
    patch('    vram_used = required;','    vram_used = required;\n    if (!tr_load()) return false;')
    patch('    unsigned int i, j, visible = forest_polygon_count;',
          '    unsigned int i, j, visible = forest_polygon_count;\n'
          '    if (tr_mode()!=tr_last_mode) { forest_prepared=false; tr_last_mode=tr_mode(); }')
    patch('    for (i = 0; i < forest_tile_count; ++i) tile_depth[i] = 32767;',
          '    for (i = 0; i < forest_tile_count; ++i) tile_depth[i] = 32767;\n'
          '    if (tr_mode()) for (i=0;i<forest_polygon_count;++i) if (forest_mesh[i]>>4) {\n'
          '        unsigned tile=kokiri_pdata.attbl[i].texno-forest_sprite_base;\n'
          '        int depth=32767;\n'
          '        for(j=0;j<4;++j) {int d=forest_depth[kokiri_pdata.pltbl[i].Vertices[j]]; if(d<depth)depth=d;}\n'
          '        if(tile<forest_tile_count && depth<tile_depth[tile])tile_depth[tile]=depth;\n'
          '    }')
    patch('        if (farthest < 0 || nearest > FOREST_FAR',
          '        if ((tr_mode() && (forest_mesh[i]>>4)) || farthest < 0 || nearest > FOREST_FAR')
    patch('            } while (farthest < 0 || nearest > FOREST_FAR',
          '            } while ((tr_mode() && (forest_mesh[visible]>>4)) || farthest < 0 || nearest > FOREST_FAR')
    patch('    control_trace_prepare(visible);','    tr_draw(visible);\n    control_trace_prepare(visible);')
    s+='\n#include "tr_patch.inc"\n'
    path.write_text(s,newline='\n')
    shutil.copy2(Path(__file__).with_name('tr_patch.inc'),game/'src/tr_patch.inc')
    m=(backup/'main.c').read_text().replace(
        '"ASTRA f%u step%u req%u    ",CONTROL->frame,CONTROL->sim_steps,CONTROL->ack',
        '"ASTRA f%u step%u mode%u    ",CONTROL->frame,CONTROL->sim_steps,(CONTROL->hud>>8)&3')
    (game/'src/main.c').write_text(m,newline='\n')
    print('Installed only in',game)


if __name__=='__main__':main()
