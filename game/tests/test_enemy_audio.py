"""Scene SFX copy maps preserve source ids, quiet tails and both RAM budgets."""
import json
from pathlib import Path
import struct
import sys
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_enemy_audio as enemy
import build_action_audio as audio
import build_enemy_roster as roster


class EnemyAudio(unittest.TestCase):
    def scene(self):
        return {'id': 3, 'prefix': 'test', 'rooms': [
            {'room': 'r0', 'layer': 0, 'sfx_ids': [0x3802, 0x3801]},
            {'room': 'r1', 'layer': 0, 'sfx_ids': [0x3801]}]}

    def test_library_deduplicates_samples_and_room_ids_remain_stable(self):
        pcm = b'\x01\x02\x03'
        blob, report = enemy.library(self.scene(), {0x3801: pcm, 0x3802: pcm}, 100, 100, 8)
        self.assertEqual(blob[:4], b'ESF1')
        self.assertEqual(len(blob), 48)
        self.assertEqual(report['samples'][0]['offset'], report['samples'][1]['offset'])
        room = report['rooms'][0]
        self.assertEqual([r['id'] for r in room['slots']], [0x3801, 0x3802])
        self.assertEqual(room['slots'][0]['sound_offset'], 8)
        self.assertEqual(room['sound_bytes'], 24)
        self.assertEqual(blob[-5:], bytes(5))
        self.assertTrue(all(row['rate'] == 5512.5 for row in report['samples']))
        self.assertIn('0x3801, 3, 40, 8', enemy.room_header(report))

    def test_retained_bank_cost_cannot_disappear(self):
        with self.assertRaisesRegex(ValueError, r'sound RAM.*retained=96'):
            enemy.library(self.scene(), {0x3801: b'abc', 0x3802: b'def'}, 100, 100, 96)

    def test_scene_cart_header_and_alignment_count_toward_limit(self):
        with self.assertRaisesRegex(ValueError, 'exceeds cart reservation'):
            enemy.library(self.scene(), {0x3801: b'abc', 0x3802: b'abc'}, 100, 47, 0)

    def test_missing_sfx_is_named_failure(self):
        with self.assertRaisesRegex(ValueError, 'missing SFX: 0x3802'):
            enemy.library(self.scene(), {0x3801: b'abc'}, 100, 100, 0)

    def test_empty_and_too_long_samples_reject_scsp_length(self):
        for pcm in (b'', bytes(65536)):
            with self.assertRaisesRegex(ValueError, 'empty or over-65535'):
                enemy.append_sample(bytearray(), pcm)

    def test_generated_resident_map_keeps_existing_dispatch_ids(self):
        expected = {0x284E: (1, 'AREA_SFX_CUT', 26), 0x4803: (2, '0', 0),
                    0x4824: (0, 'ACTION_GET_ITEM', 27),
                    0x4829: (0, 'ACTION_CAMERA_ZOOM_DOWN_2', 27),
                    0x480B: (0, 'ACTION_HP_RECOVER', 27),
                    **{sid: (0, 'ACTION_MESSAGE', 27) for sid in (0x4818, 0x482E, 0x4808, 0x4809)}}
        if not roster.imp.OOT_DEFAULT.exists():
            self.skipTest('local decomp required')
        with tempfile.TemporaryDirectory() as folder:
            rows = audio.write_core_sfx_map(roster.imp.OOT_DEFAULT, Path(folder))
            actual = {sid: (kind, slot, channel) for sid, kind, slot, channel, _ in rows}
            self.assertEqual({sid: actual[sid] for sid in expected}, expected)
            self.assertTrue((Path(folder) / 'action_decomp_sfx.h').is_file())

    @unittest.skipUnless(os.name != 'nt' and shutil.which('cc'), 'Linux host compiler required')
    def test_actual_c_dispatch_uses_generated_routes_and_ignores_unknown(self):
        source = (ROOT / 'src/action_audio.c').read_text()
        function = source[source.index('void action_audio_decomp_sfx(unsigned int sfx_id)'):]
        checks = []
        table = roster.sfx_table(roster.imp.OOT_DEFAULT)
        for symbol, kind, slot, channel in audio.CORE_SFX_MAP:
            checks.append('last_kind = -1; action_audio_decomp_sfx(%d); assert(last_kind == %d);' %
                          (table[symbol]['id'], kind))
            if kind != 2:
                checks.append('assert(last_slot == %s && last_channel == %d);' % (slot, channel))
        wrapper = '''#include <assert.h>
#include <stdbool.h>
#include "action_audio_data.h"
#include "action_decomp_sfx.h"
#include "field_audio_data.h"
static bool ready, opening_bank, area_ready, field_bank;
static struct { unsigned link_age; } save_state;
static unsigned item_loop_frames,item_loop_id;
#define ITEM_LOOP_HOLD 10
static unsigned regs[32][32];
#define SLOT(s,o) regs[s][o]
static int last_kind, last_slot, last_channel;
static void play_pcm(unsigned address,unsigned length,unsigned slot,unsigned pitch,unsigned level,bool loop) {}
static void play_sample(unsigned id,unsigned slot,unsigned pitch,unsigned level,bool loop) {
    last_kind=3; last_slot=id; last_channel=slot;
}
static void play(unsigned slot, unsigned channel) { last_kind=0; last_slot=slot; last_channel=channel; }
static void play_area(unsigned slot, unsigned channel) { last_kind=1; last_slot=slot; last_channel=channel; }
static void rupee_start(void) { last_kind=2; }
''' + function + '\nint main(void) {\n' + '\n'.join(checks) + '''
last_kind = -1; action_audio_decomp_sfx(0xFFFF); assert(last_kind == -1);
return 0; }
'''
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            audio.write_core_sfx_map(roster.imp.OOT_DEFAULT, path)
            (path / 'probe.c').write_text(wrapper)
            subprocess.run(['cc', '-std=c99', '-I' + str(path), '-I' + str(ROOT / 'build/generated'),
                            str(path / 'probe.c'), '-o', str(path / 'probe')], check=True, capture_output=True)
            subprocess.run([str(path / 'probe')], check=True)


if __name__ == '__main__':
    unittest.main()
