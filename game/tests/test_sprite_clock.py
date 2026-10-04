"""Clock-only NPC animation keeps action timing without touching a skeleton."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
import test_graphics_backend as graphics

ROOT = Path(__file__).resolve().parents[1]


class SpriteClock(unittest.TestCase):
    def test_clock_modes_and_poisoned_skeleton(self):
        bridge = ROOT / 'oot-core/src/bridge_npc.cpp'
        source = r'''
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#define assert(c) do { if(!(c)) { fprintf(stderr,"failed line %d: %s\n",__LINE__,#c); exit(1); } } while(0)
''' + '#include "' + (ROOT / 'oot-core/include/fx.h').as_posix() + '"\n' + r'''
typedef Fx f32; typedef int32_t s32; typedef uint8_t u8;
typedef struct { int16_t x,y,z; } Vec3s;
struct PlayState {}; struct FlexSkeletonHeader {};
struct AnimationHeader { struct { int16_t frameCount; } common; };
enum { ANIMMODE_LOOP, ANIMMODE_LOOP_INTERP, ANIMMODE_ONCE, ANIMMODE_ONCE_INTERP,
       ANIMMODE_LOOP_PARTIAL, ANIMMODE_LOOP_PARTIAL_INTERP };
struct SkelAnime {
    u8 initFlags,limbCount,dListCount,mode; void **skeleton; void *animation;
    f32 startFrame,endFrame,animLength,curFrame,playSpeed,morphWeight,morphRate;
    Vec3s *jointTable,*morphTable;
    union { s32 (*normal)(SkelAnime*); } update;
};
#define SEGMENTED_TO_VIRTUAL(a) (a)
''' + '\n'.join(graphics.function(bridge, marker) for marker in (
            'static s32 sprite_q8(', 'static f32 sprite_frame(',
            'void OotCore_SpriteChange(', 'void OotCore_SpriteInitFlex(',
            's32 OotCore_SpriteUpdate(')) + r'''
int main() {
    AnimationHeader anim={{10}};
    SkelAnime s={};
    OotCore_SpriteInitFlex(nullptr,&s,(FlexSkeletonHeader*)1,&anim,(Vec3s*)1,(Vec3s*)1,0);
    assert(!s.skeleton && !s.jointTable && !s.morphTable && !s.update.normal);
    assert(s.initFlags==0x53 && !s.limbCount);
    for(int n=0;n<10;++n) assert(!OotCore_SpriteUpdate(&s));
    assert(sprite_q8(s.curFrame)==0);
    OotCore_SpriteChange(&s,&anim,sprite_frame(384),sprite_frame(0),sprite_frame(9*256),ANIMMODE_ONCE);
    for(int n=0;n<6;++n) assert(!OotCore_SpriteUpdate(&s));
    assert(sprite_q8(s.curFrame)==9*256 && OotCore_SpriteUpdate(&s));
    OotCore_SpriteChange(&s,&anim,sprite_frame(-256),sprite_frame(9*256),sprite_frame(0),ANIMMODE_ONCE);
    for(int n=0;n<9;++n) assert(!OotCore_SpriteUpdate(&s));
    assert(sprite_q8(s.curFrame)==0 && OotCore_SpriteUpdate(&s));
    OotCore_SpriteChange(&s,&anim,sprite_frame(-128),sprite_frame(0),sprite_frame(0),ANIMMODE_LOOP);
    assert(!OotCore_SpriteUpdate(&s) && sprite_q8(s.curFrame)==9*256+128);
    OotCore_SpriteChange(&s,&anim,sprite_frame(256),sprite_frame(2*256),sprite_frame(5*256),ANIMMODE_LOOP_PARTIAL);
    s.curFrame=sprite_frame(4*256);
    assert(!OotCore_SpriteUpdate(&s) && sprite_q8(s.curFrame)==2*256);
    s.playSpeed=sprite_frame(0);
    for(int n=0;n<50;++n) assert(!OotCore_SpriteUpdate(&s));
    assert(sprite_q8(s.curFrame)==2*256);
    assert(!s.skeleton && !s.jointTable && !s.morphTable);
}
'''
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            (p / 'test.cpp').write_text(source)
            compiler = Path(graphics.GCC).with_name('g++.exe' if os.name == 'nt' else 'g++')
            env = dict(os.environ)
            env['PATH'] = str(compiler.parent) + os.pathsep + env.get('PATH', '')
            subprocess.run([str(compiler), '-std=c++17', '-O2', str(p / 'test.cpp'),
                            '-o', str(p / 'test.exe')], check=True, env=env)
            subprocess.run([str(p / 'test.exe')], check=True, env=env)


if __name__ == '__main__':
    unittest.main()
