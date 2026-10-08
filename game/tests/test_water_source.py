"""Water Temple uses source-owned water without a second height authority."""
from pathlib import Path
import unittest
import test_graphics_backend as graphics

GAME = Path(__file__).resolve().parents[1]


class SourceWater(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_all_source_boxes_follow_live_heights_and_unbind_before_release(self):
        self.run_c('#include <assert.h>\n#include "' +
                   (GAME.parent/'shared/lib/collision/kokiri_collision.c').as_posix() + '"\n' + r'''
int main(void) {
    bg_waterbox_t original={0,10,0,100,100,BG_WATERBOX_ROOM_ALL<<13};
    bg_waterbox_t source[25]={0};
    bg_mesh_t mesh={0}; mesh.water=&original; mesh.water_count=1;
    int32_t height=0; const bg_waterbox_t *box=0;
    bg_scene_set(&mesh);
    assert(bg_water_set_surface(0,15));
    assert(bg_water_surface(50,50,0,&height,&box) && height==15);
    for(unsigned i=0;i<25;++i) source[i].properties=BG_WATERBOX_DISABLED;
    source[22]=original; source[22].y_surface=80;
    bg_water_bind(source,25);
    assert(bg_water_surface(50,50,0,&height,&box) && height==80 && box==source+22);
    assert(!bg_water_set_surface(0,999)); /* host cannot fight source controller */
    source[22].y_surface=-40;
    assert(bg_water_surface(50,50,0,&height,&box) && height==-40);
    source[22].properties=2u<<13;
    assert(!bg_water_surface(50,50,0,&height,&box));
    assert(bg_water_surface(50,50,2,&height,&box));
    bg_water_bind(0,0); /* before releasing the source scene */
    assert(bg_water_surface(50,50,0,&height,&box) && height==15 && box==&original);
    bg_water_bind(source,25);
    bg_scene_set(&mesh); /* room/scene replacement independently clears borrowing */
    assert(bg_water_surface(50,50,0,&height,&box) && height==10 && box==&original);
    return 0;
}
''')


if __name__ == '__main__': unittest.main()
