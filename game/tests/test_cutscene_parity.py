"""Source-order cue boundaries and actual compact actor animation assets."""
import ctypes
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / 'build/generated'
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')


@unittest.skipUnless(GCC.exists() and (GEN / 'cutscenes.h').exists(), 'host assets required')
class CueRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / 'src/cutscene.c').read_text()
        # navi_orbit() is part of the cue update: the cutscene fairy's path
        # is the cue plus En_Elf's hover around it.
        start = source.index('static void navi_orbit(unsigned int cue_id')
        end = source.index('\nunsigned int cutscene_actor_channels', start)
        # Compile the production function against overlapping synthetic cues.
        harness = '''#include <stdint.h>
#include <math.h>
#include <string.h>
#include "cutscenes.h"
static struct {
    unsigned short frame;
    const cutscene_cue_t *player_cue, *actor_cues[10];
    int32_t actor_pos[10][3], navi_pos[3], navi_velocity[3];
    uint16_t navi_orbit_xz, navi_orbit_y;
} state;
static void kokiri_camera_sincos(uint16_t yaw, int32_t *sine, int32_t *cosine)
{
    double radians = yaw * 6.283185307179586 / 65536.0;
    *sine = (int32_t)(sin(radians) * 65536);
    *cosine = (int32_t)(cos(radians) * 65536);
}
''' + source[start:end] + '''
static cutscene_cue_t cues[] = {
    {0, 10, 20, 100,0,0,200,0,0,0,1},
    {0, 5, 15, 300,0,0,400,0,0,0,2},
    {0, 30, 40, 500,0,0,600,0,0,0,3}
};
void reset(void) { memset(&state,0,sizeof(state)); }
void step(int frame) {
    cutscene_t cs = {0};
    cs.actor_cues = cues; cs.actor_cue_count = 3;
    state.frame = frame; update_cues(&cs);
}
int visible(void) { return state.actor_cues[0] != 0; }
int cue_id(void) { return visible() ? state.actor_cues[0]->id : 0; }
int position(void) { return state.actor_pos[0][0]; }
int navi_height(void) { return state.actor_pos[8][1]; }
void navi_cue(int id) {
    static cutscene_cue_t navi;
    navi = (cutscene_cue_t){0, 0, 400, 0, 50, 110, 0, 50, 110, 0, (unsigned char)id};
    state.actor_cues[8] = &navi;
}
'''
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        path = Path(cls.tmp.name)
        (path / 'test.c').write_text(harness)
        env = dict(os.environ, PATH=str(GCC.parent) + os.pathsep + os.environ.get('PATH', ''))
        subprocess.run([str(GCC), '-shared', '-O2', '-I' + str(GEN),
                        str(path / 'test.c'), '-o', str(path / 'test.dll')],
                       check=True, env=env)
        cls.lib = ctypes.CDLL(str(path / 'test.dll'))

    def setUp(self):
        self.lib.reset()

    def test_start_excluded_end_included_last_source_match_wins(self):
        self.lib.step(5)
        self.assertEqual(self.lib.visible(), 0)
        self.lib.step(6)
        self.assertEqual(self.lib.cue_id(), 2)
        self.lib.step(11)
        self.assertEqual(self.lib.cue_id(), 2)
        self.lib.step(15)
        self.assertEqual(self.lib.cue_id(), 2)
        self.lib.step(16)
        self.assertEqual(self.lib.cue_id(), 1)

    def test_gap_keeps_last_pre_end_position_and_visibility(self):
        for frame in range(20):
            self.lib.step(frame)
        self.assertEqual(self.lib.position(), 190)
        for frame in range(20, 31):
            self.lib.step(frame)
            self.assertEqual(self.lib.visible(), 1)
            self.assertEqual(self.lib.position(), 190)
        self.lib.step(31)
        self.assertEqual(self.lib.position(), 510)

    def test_navi_bobs_while_she_wakes_link(self):
        """Cue id 3 holds one position for 100 frames; En_Elf's state 6 orbit
        is what moves her, and what the source dash cue is timed off."""
        self.lib.navi_cue(3)
        heights = []
        for frame in range(1, 60):
            self.lib.step(frame)
            heights.append(self.lib.navi_height())
        falls = sum(1 for a, b in zip(heights, heights[1:]) if b < a)
        rises = sum(1 for a, b in zip(heights, heights[1:]) if b > a)
        self.assertGreater(falls, 5)
        self.assertGreater(rises, 5)
        # A 0x1000 step per frame is one bob every 16 frames, as in state 6.
        self.assertGreater(max(heights) - min(heights), 10)


@unittest.skipUnless(GCC.exists() and (GEN / 'link_clips.c').exists(), 'host assets required')
class LinkPlayback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / 'src/cutscene.c').read_text()
        start = source.index('static void link_sample(')
        end = source.index('unsigned int cutscene_screen_distance', start)
        harness = """#include <stdbool.h>
#include "cutscenes.h"
#include "link_clips.h"
static struct { unsigned int applied_frame; } state;
static cutscene_cue_t cue;
static const cutscene_cue_t *current_cue(void) { return &cue; }
""" + source[start:end] + """
void sample(int type, int elapsed, int span) {
    cue.clip = type; cue.start = 10; cue.end = 10 + span;
    state.applied_frame = 11 + elapsed;
}
"""
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        path = Path(cls.tmp.name)
        (path / 'test.c').write_text(harness)
        env = dict(os.environ, PATH=str(GCC.parent) + os.pathsep + os.environ.get('PATH', ''))
        subprocess.run([str(GCC), '-shared', '-O2', '-I' + str(GEN),
                        str(path / 'test.c'), str(GEN / 'link_clips.c'),
                        '-o', str(path / 'test.dll')], check=True, env=env)
        cls.lib = ctypes.CDLL(str(path / 'test.dll'))
        import re
        headers = (GEN / 'cutscenes.h').read_text() + (GEN / 'link_clips.h').read_text()
        cls.ids = {name: int(value) for name, value in
                   re.findall(r'((?:CUTSCENE|LINK)_CLIP_\w+)\s*(?:=\s*)?(\d+)', headers)}

    def pose(self, cue, elapsed, span=1000):
        self.lib.sample(self.ids['CUTSCENE_CLIP_' + cue], elapsed, span)
        return (self.lib.cutscene_link_clip(), self.lib.cutscene_link_frame(),
                self.lib.cutscene_link_fraction())

    def test_clip_speed_does_not_depend_on_cue_duration(self):
        self.assertEqual(self.pose('SIT_UP', 30, 100), self.pose('SIT_UP', 30, 400))
        # 30 ticks = source frame 45 = sampled frame 15 at stride three.
        self.assertEqual(self.pose('SIT_UP', 30)[1:], (15, 0))

    def test_roll_and_sit_finish_in_original_wait_loops(self):
        self.assertEqual(self.pose('TURN_OVER', 36)[0], self.ids['LINK_CLIP_TURN_OVER'])
        self.assertEqual(self.pose('TURN_OVER', 37)[0], self.ids['LINK_CLIP_SLEEP_WAIT2'])
        self.assertEqual(self.pose('SIT_UP', 244)[0], self.ids['LINK_CLIP_SIT_WAIT3'])

    def test_sleep_retains_full_eighty_frame_loop(self):
        self.assertGreater(self.pose('SLEEPING', 40)[1], 10)
        self.assertEqual(self.pose('SLEEPING', 54)[1:], (0, 85))


class ActorTracks(unittest.TestCase):
    def test_each_model_has_valid_moving_track_and_matching_topology(self):
        for name in ('GANON', 'ZELDA', 'IMPA', 'HZELDA', 'HGANON'):
            with self.subTest(actor=name):
                path = GEN / (name + '.ANM')
                if not path.exists():
                    self.skipTest('baked actors required')
                raw = path.read_bytes()
                magic, vertices, poses, ticks = struct.unpack_from('>4sIII', raw)
                model = (GEN / (name + '.BIN')).read_bytes()
                self.assertEqual(magic, b'CVA1')
                self.assertEqual(vertices, struct.unpack_from('>I', model, 8)[0])
                self.assertEqual(ticks, 541)
                self.assertGreater(poses, 1)
                self.assertEqual(len(raw), 16 + ticks * 2 + vertices * poses * 6)
                self.assertLess(max(struct.unpack_from('>%dH' % ticks, raw, 16)), poses)

    def test_nightmare_bank_fits_with_resident_ui_and_all_models(self):
        import re
        names = ('GANON', 'ZELDA', 'IMPA', 'HZELDA', 'HGANON', 'BRIDGE', 'CHAINS')
        if not (GEN / 'GANON.BIN').exists():
            self.skipTest('baked actors required')
        texture_bytes = 0
        polygons = 555 + 20  # field and maximum rain count
        for name in names:
            raw = (GEN / (name + '.BIN')).read_bytes()
            texture_bytes += struct.unpack_from('>I', raw, 28)[0]
            polygons += struct.unpack_from('>I', raw, 12)[0] * (2 if name == 'CHAINS' else 1)
        header = (GEN / 'link_scene.h').read_text()
        value = lambda name: int(re.search(r'# define ' + name + r'\s+(\d+)', header).group(1))
        texture_bytes += value('LINK_PIXEL_BYTES') + value('LINK_TILE_COUNT') * 32
        # Exact resident uploads: fairy, grass, rupees, digits, two pickups,
        # three menu sprites, message panel, and both message marks.
        texture_bytes += 512 + 2048 + 1024 + 2560 + 1024 + 6144 + 1024 + 1024
        polygons += value('LINK_POLYGON_COUNT')
        capacity = 0x7fef8 - ((3750 * 32 + 8192 + 255) & ~255)
        self.assertLessEqual(texture_bytes, capacity)
        self.assertLessEqual(polygons, 3750)


if __name__ == '__main__':
    unittest.main()
