"""Opening-specific scenery residency and the text/NONE cue boundary."""
import ctypes
import os
import pathlib
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GEN = ROOT / 'build/generated'
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')
sys.path.insert(0, str(ROOT / 'tools'))
import build_opening_banks as opening
from build_room_scene import pack_room
from build_sgl_scene import face_normal


class OpeningBanks(unittest.TestCase):
    def test_far_face_is_flat_and_owns_no_texture(self):
        vertices = [(-20, 0, 300), (20, 0, 300), (0, 40, 300),
                    (-20, 0, 1800), (20, 0, 1800), (0, 40, 1800)]
        faces = [dict(idx=(0, 1, 2, 2), tex_off=0, cull=False, mesh=False),
                 dict(idx=(3, 4, 5, 5), tex_off=1, cull=False, mesh=False)]
        tiles = {i: dict(index=i, width=8, height=8, pixels=bytes([0x11] * 32),
                         clut=(0,) + (0xFFFF,) * 15) for i in range(2)}
        points, result, resident = opening.forest_bank(
            [(vertices, faces, tiles)], [(0, 0, 0, 0, 0, 0, 240)])
        self.assertEqual(len(result), 2)
        self.assertNotIn('colour', result[0])
        self.assertEqual(result[1]['colour'], opening.FOG_COLOUR)
        self.assertEqual(len(resident), 1)
        records = [dict(object=0, indices=f['idx']) for f in result]
        mesh, pixels, _ = pack_room(points, result, resident, records, face_normal)
        self.assertEqual(len(pixels), 32)
        self.assertEqual(len(mesh), 32 + len(points)*12 + 2*32 + 44 + 4 + 24)
        attr = 32 + len(points)*12 + 2*20
        self.assertEqual(struct.unpack_from('>H', mesh, attr + 10)[0], 2)
        self.assertEqual(struct.unpack_from('>H', mesh, attr + 22)[0], 4)

    def test_later_near_view_keeps_required_tile(self):
        points = [(-20, 0, 1800), (20, 0, 1800), (0, 40, 1800)]
        face = dict(idx=(0, 1, 2, 2), tex_off=0, cull=False, mesh=False)
        tile = dict(index=0, width=8, height=8, pixels=bytes(32), clut=(0,) * 16)
        _, faces, tiles = opening.forest_bank([(points, [face], {0: tile})],
             [(0, 0, 0, 0, 0, 0, 240), (0, 0, 900, 0, 0, 0, 240)])
        self.assertNotIn('colour', faces[0])
        self.assertEqual(len(tiles), 1)


@unittest.skipUnless(GCC.exists() and (GEN / 'cutscenes.c').exists(), 'host assets required')
class TextCueBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / 'src/cutscene.c').read_text()
        function = source[source.index('static void step_events('):
                          source.index('static void update_cues(const cutscene_t *cs);')]
        fade_function = source[source.index('static void update_fade('):
                               source.index('static void apply_camera(')]
        harness = '''#include "message.h"
#include "song_ids.h"
typedef int music_bank_t;
static music_bank_t fake_bank;
static int busy, starts;
static const music_bank_t *bank_for_cutscene(unsigned int id) { return &fake_bank; }
static const music_bank_t *music_current(void) { return 0; }
static int music_busy(void) { return busy; }
static void music_silence(int n) {}
static bool music_fade_to(const music_bank_t *b, int n) { ++starts; return true; }
static const music_bank_t *music_song_bank(oot_song_t song) { return &fake_bank; }
static void music_once(const music_bank_t *b, const music_bank_t *next) {}
#define CUTSCENE_FADE_FRAMES 10
static struct { unsigned short frame; unsigned char id, text_cursor, music_cursor;
                short text_hold_end; unsigned char fade_alpha, fade_colour; } state;
''' + function + fade_function + '''
int fade_at(int frame) {
    state.frame=frame; update_fade(&cutscenes[CUTSCENE_NAVI_FLY]);
    return state.fade_alpha;
}
static const cutscene_text_t text[] = {{0x1099,50,60}, {0,60,120}, {0x109A,120,150}};
void reset(void) { state.text_cursor=state.music_cursor=0; message_stop(); }
void step(int frame, int confirm) {
    cutscene_t cs = {0}; cs.text=text; cs.text_count=3;
    state.frame=frame; step_events(&cs, confirm);
}
int cursor(void) { return state.text_cursor; }
int music_step(int is_busy) {
    static const cutscene_music_t cue[] = {{CUTSCENE_BANK_NIGHTMARE,0,330}};
    cutscene_t cs = {0}; cs.music=cue; cs.music_count=1;
    busy=is_busy; state.frame=330; step_events(&cs, 0);
    return starts;
}
'''
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        path = pathlib.Path(cls.tmp.name)
        (path / 'test.c').write_text(harness)
        env = dict(os.environ, PATH=str(GCC.parent) + os.pathsep + os.environ.get('PATH', ''))
        subprocess.run([str(GCC), '-shared', '-O2', '-I' + str(GEN),
                        '-I' + str(ROOT / 'src'), str(path / 'test.c'),
                        str(ROOT / 'src/message.c'), str(ROOT / 'src/text_pool.c'),
                        str(ROOT / 'src/ui_preferences.c'),
                        '-I' + str(ROOT.parent / 'shared/lib/camera'),
                        '-I' + str(ROOT.parent / 'shared/lib/collision'),
                        str(GEN / 'cutscenes.c'),
                        '-o', str(path / 'test.dll')], check=True, env=env)
        cls.lib = ctypes.CDLL(str(path / 'test.dll'))
        cls.lib.message_is_active.restype = ctypes.c_bool

    def test_none_cue_at_hold_end_does_not_erase_unread_speech(self):
        self.lib.reset()
        self.lib.step(50, 0)
        for _ in range(600):
            self.lib.step(60, 0)
        self.assertTrue(self.lib.message_is_active())
        self.assertEqual(self.lib.cursor(), 1)
        for _ in range(100):
            self.lib.step(60, 1)
            if not self.lib.message_is_active():
                break
        self.assertFalse(self.lib.message_is_active())
        self.lib.step(60, 0)
        self.assertEqual(self.lib.cursor(), 2)
        self.lib.step(120, 0)
        self.assertTrue(self.lib.message_is_active())
        self.assertEqual(self.lib.cursor(), 3)

    def test_transition_trigger_keeps_deku_tree_visible(self):
        for frame in (0, 60, 70, 80, 120, 131, 150, 194):
            self.assertEqual(self.lib.fade_at(frame), 0, frame)
        self.assertEqual(self.lib.fade_at(198), 255)
        self.assertEqual(self.lib.fade_at(216), 0)

    def test_music_cue_retries_after_previous_fade(self):
        self.lib.reset()
        self.assertEqual(self.lib.music_step(1), 0)
        self.assertEqual(self.lib.music_step(0), 1)
        self.assertEqual(self.lib.music_step(0), 1)
