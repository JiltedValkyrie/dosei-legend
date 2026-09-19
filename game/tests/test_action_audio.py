"""Resident action PCM safety and real C event routing/SCSP register writes."""
import ctypes
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT/'build/generated'
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')


class AudioBank(unittest.TestCase):
    def test_samples_fit_reserved_tail_and_have_silent_guards(self):
        manifest = json.loads((GEN/'action_audio.json').read_text())
        blob = (GEN/'ACTIONS.PCM').read_bytes()
        self.assertEqual(len(blob), manifest['bytes'])
        self.assertLessEqual(manifest['base']+len(blob), 0x80000)
        self.assertGreaterEqual(manifest['base'], 4096+480082)
        for sample in manifest['samples']:
            start, length = sample['offset'], sample['length']
            self.assertEqual(start % 2, 0)
            self.assertGreater(length, 0)
            self.assertLess(length, 65536)
            self.assertTrue(any(blob[start:start+length]))
            self.assertEqual(blob[start+length:start+length+4], bytes(4))


@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class AudioEvents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        source = (ROOT/'src/action_audio.c').read_text()
        source = re.sub(r'^#include .*$', '', source, flags=re.M)
        source = re.sub(r'^#define SLOT.*$', '', source, flags=re.M)
        adapter = '''
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include "gameplay.h"
#include "action_audio_data.h"
#define MUSIC_SAMPLE_LIMIT 0x76400
typedef struct { unsigned int size; } jo_file;
static unsigned short regs[32][16];
#define SLOT(s,o) regs[s][(o)/2]
static bool busy;
#define JO_VDP2_TVSTAT 0
static bool jo_core_add_vblank_callback(void (*cb)(void)) { return true; }
static bool music_busy(void) { return busy; }
static bool jo_fs_open(jo_file *f, const char *n) { return false; }
static void jo_fs_close(jo_file *f) {}
static int jo_fs_read_next_bytes(jo_file *f, char *b, unsigned int n) { return -1; }
'''
        wrapper = '''
void reset(void) { memset(regs, 0, sizeof(regs)); ready = true; busy = false; voice = 0; rupee_active = false; rupee_clock = rupee_note = 0; sound_refresh = 60; }
unsigned int reg(unsigned int s, unsigned int o) { return SLOT(s,o); }
void set_busy(bool b) { busy = b; }
void tick(void) { rupee_vblank(); }
void refresh(unsigned int hz) { sound_refresh = hz; }
'''
        env = dict(os.environ, PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH',''))
        output = Path(cls.temp.name)/'audio.dll'
        subprocess.run([str(GCC), '-shared', '-O2', '-I'+str(ROOT/'src'), '-I'+str(GEN),
                        '-x','c','-','-o',str(output)], input=adapter+source+wrapper,
                       text=True, env=env, check=True)
        cls.lib = ctypes.CDLL(str(output))

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def setUp(self): self.lib.reset()

    def test_swing_plays_blade_and_voice_without_touching_music_slots(self):
        self.lib.action_audio_events(2)
        for slot in (24,25):
            self.assertEqual(self.lib.reg(slot,0) & 0x1830, 0x1810)
            self.assertEqual(self.lib.reg(slot,16), 14 << 11)
            self.assertGreater(self.lib.reg(slot,6), 0)
        for slot in range(24):
            self.assertEqual(self.lib.reg(slot,0), 0)

    def test_cut_and_shield_and_equip_have_separate_routes(self):
        for event, slot in ((4,26),(32,24),(4096,27),(128,27),
                            (1<<14,25),(1<<15,28),(1<<16,28),(1<<17,25),(1<<18,29)):
            self.lib.reset()
            self.lib.action_audio_events(event)
            self.assertTrue(self.lib.reg(slot,0) & 0x800)

    def test_rupee_sound_has_own_slot_even_when_gear_is_collected_too(self):
        self.lib.action_audio_events((1<<18) | 1)
        self.assertTrue(self.lib.reg(29,0) & 0x800)
        self.assertTrue(self.lib.reg(27,0) & 0x800)
        self.assertNotEqual(self.lib.reg(29,2),self.lib.reg(27,2))
        self.lib.reset()
        self.lib.set_busy(True)
        self.lib.action_audio_events(1<<18)
        self.assertEqual(self.lib.reg(29,0),0)

    def test_rupee_plays_three_note_melody_and_stops_at_source_duration(self):
        self.lib.action_audio_events(1<<18)
        first=self.lib.reg(30,16)
        self.assertTrue(self.lib.reg(30,0) & 0x20) # looping real source waveform
        self.assertEqual(self.lib.reg(30,6),64)
        for _ in range(4): self.lib.tick()
        second=self.lib.reg(30,16)
        self.assertNotEqual(first,second)
        for _ in range(4): self.lib.tick()
        self.assertEqual(self.lib.reg(30,16),first)
        for _ in range(15): self.lib.tick()
        self.assertEqual(self.lib.reg(30,12),255)
        self.assertFalse(self.lib.reg(30,0) & 0x800)
        for slot in range(24): self.assertEqual(self.lib.reg(slot,0),0)

    def test_rupee_retrigger_and_pal_clock_cannot_leave_a_looping_note(self):
        self.lib.refresh(50)
        self.lib.action_audio_events(1<<18)
        for _ in range(10): self.lib.tick()
        self.lib.action_audio_events(1<<18)
        for _ in range(18): self.lib.tick()
        self.assertTrue(self.lib.reg(30,0)&0x800)
        self.lib.tick() # ceil(.375 * 50) = 19 frames
        self.assertFalse(self.lib.reg(30,0)&0x800)
        self.lib.action_audio_events(1<<18)
        self.lib.set_busy(True)
        self.lib.tick()
        self.assertEqual(self.lib.reg(30,12),255)
        self.assertFalse(self.lib.reg(30,0)&0x800)

    def test_voice_rotates_and_music_swap_drops_effects(self):
        addresses = []
        for _ in range(5):
            self.lib.action_audio_events(2)
            addresses.append(self.lib.reg(25,2))
        self.assertEqual(len(set(addresses[:4])),4)
        self.assertEqual(addresses[0],addresses[4])
        self.lib.reset()
        self.lib.set_busy(True)
        self.lib.action_audio_events(2 | 4 | 32 | 4096)
        for slot in range(24,28): self.assertEqual(self.lib.reg(slot,0),0)
