"""Actual cleanup functions against the SDK's non-null free contract."""
from pathlib import Path
import unittest
import test_graphics_backend as graphics

ROOT = Path(__file__).resolve().parents[1]


class SpriteCleanup(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_empty_partial_full_and_repeated_teardown(self):
        self.run_c(r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
typedef int actor_mesh_t;
static unsigned char *saria[4],*owl[2],*ganon,*horse;
static actor_mesh_t *body,*aura,*triforce,*jewel;
static unsigned uploaded,owl_phase,owl_frame,clock_phase,owl_handle;
static unsigned char allocations[8],live[8];
static unsigned freed;
static void jo_free(void *p) {
    assert(p); /* The SDK raises an error here, unlike libc free(NULL). */
    unsigned i=(unsigned)((unsigned char *)p-allocations);
    assert(i<8 && live[i]); live[i]=0; ++freed;
}
static void actor_mesh_free(actor_mesh_t *p) { assert(!p); }
static void *actor_resolve(unsigned h) { return 0; }
static void actor_kill(void *p) {}
''' + graphics.function(ROOT / 'src/story_route.c', 'void story_route_free(')
            + graphics.function(ROOT / 'src/emerald_story.c', 'void emerald_story_free(') + r'''
int main(void) {
    for(unsigned mask=0;mask<256;++mask) {
        freed=0; unsigned expected=0;
        for(unsigned i=0;i<8;++i) {
            live[i]=(mask>>i)&1; expected+=live[i];
            unsigned char *p=live[i]?&allocations[i]:0;
            if(i<4)saria[i]=p;else if(i<6)owl[i-4]=p;
            else if(i==6)ganon=p;else horse=p;
        }
        story_route_free(); emerald_story_free();
        assert(freed==expected);
        story_route_free(); emerald_story_free();
        assert(freed==expected);
        for(unsigned i=0;i<8;++i)assert(!live[i]);
        for(unsigned i=0;i<4;++i)assert(!saria[i]);
        assert(!owl[0] && !owl[1] && !ganon && !horse);
    }
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
