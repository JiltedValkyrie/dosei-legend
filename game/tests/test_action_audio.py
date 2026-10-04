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
    def test_navi_uses_effect_bank_transpose_instead_of_link_voices(self):
        samples = {s['name']: s for s in json.loads((GEN/'action_audio.json').read_text())['samples']}
        # seqplayer.c: (layer transposition << 6) + semitone. CHAN_6520
        # therefore selects effects 104/124, never Link's effects 41/61.
        self.assertEqual(samples['navi_hello']['sample'], 'SAMPLE_0_212')
        self.assertEqual(samples['navi_talk']['sample'], 'SAMPLE_0_213')
        self.assertEqual(samples['hp_recover']['source'], 'CHAN_596D')

    def test_samples_fit_reserved_tail_and_have_silent_guards(self):
        manifest = json.loads((GEN/'action_audio.json').read_text())
        blob = (GEN/'ACTIONS.PCM').read_bytes()
        self.assertEqual(len(blob), manifest['bytes'])
        self.assertLessEqual(manifest['base']+len(blob), 0x80000)
        banks = [ROOT/'levels/kokiri/assets/audio/KOKIRI_PCM.RAW',
                 ROOT.parent/'shared/assets/audio/title/TITLE_PCM.RAW',
                 *(ROOT/'assets/audio/cutscenes').glob('*_PCM.RAW')]
        self.assertGreaterEqual(manifest['base'], 4096 + max(p.stat().st_size for p in banks))
        for sample in manifest['samples']:
            start, length = sample['offset'], sample['length']
            self.assertEqual(start % 2, 0)
            self.assertGreater(length, 0)
            self.assertLess(length, 65536)
            self.assertTrue(any(blob[start:start+length]))
            self.assertEqual(blob[start+length:start+length+4], bytes(4))


    def test_tree_and_boss_select_the_dungeon_bank(self):
        import sys
        sys.path.insert(0,str(ROOT/'tools'))
        from build_scene_table import SCENES
        for name,bank in (('SCENE_DEKU_TREE',2),('SCENE_DEKU_TREE_BOSS',3)):
            self.assertEqual(next(s for s in SCENES if s['scene']==name)['sfx'],bank)

    def test_area_banks_fit_after_core_and_match_header(self):
        manifest = json.loads((GEN/'action_audio.json').read_text())
        self.assertEqual(manifest['area_base'], manifest['base'] + manifest['bytes'])
        self.assertEqual(manifest['area_base'] % 2, 0)
        self.assertEqual(manifest['area_base'] + manifest['area_limit'], 0x80000)
        header = (GEN/'action_audio_data.h').read_text()
        for bank in manifest['area_banks']:
            self.assertLessEqual(bank['bytes'], manifest['area_limit'])
            if bank['file']:
                blob = (GEN/bank['file']).read_bytes()
                self.assertEqual(len(blob), bank['bytes'])
                self.assertIn('"%s"' % bank['file'], header)
                for sample in bank['samples']:
                    start, length = sample['offset'], sample['length']
                    self.assertTrue(any(blob[start:start+length]))
                    self.assertEqual(blob[start+length:start+length+4], bytes(4))
        core = {s['name'] for s in manifest['samples']}
        self.assertNotIn('cut', core)
        self.assertIn('swing', core)


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
#include "player_items.h"
unsigned player_items_events(void) { return 0; }
#include "action_audio_data.h"
#include "opening_audio_data.h"
#include "action_audio.h"
#include "karebaba.h"
#include "game_over.h"
#define MUSIC_SAMPLE_LIMIT 0x50000
static uint32_t baba_ev;
uint32_t karebaba_events(void) { return baba_ev; }
typedef struct { unsigned int size; } jo_file;
static unsigned short regs[32][16];
#define SLOT(s,o) regs[s][(o)/2]
static bool busy;
gameplay_t gameplay;   /* wall_material for the wall-hit pitch */
#define JO_VDP2_TVSTAT 0
static bool jo_core_add_vblank_callback(void (*cb)(void)) { return true; }
static bool music_busy(void) { return busy; }
static bool jo_fs_open(jo_file *f, const char *n) { return false; }
static void jo_fs_close(jo_file *f) {}
static int jo_fs_read_next_bytes(jo_file *f, char *b, unsigned int n) { return -1; }
'''
        wrapper = '''
void set_area(unsigned int bank, bool loaded) { area_bank = bank; area_ready = loaded; }
void reset(void) { memset(regs, 0, sizeof(regs)); ready = true; opening_bank = false; area_bank = 1; area_ready = true; busy = false; voice = 0; rupee_active = false; rupee_clock = rupee_note = 0; sound_refresh = 60; }
void use_opening(void) { opening_bank = true; }
unsigned int reg(unsigned int s, unsigned int o) { return SLOT(s,o); }
void set_busy(bool b) { busy = b; }
void tick(void) { rupee_vblank(); }
void refresh(unsigned int hz) { sound_refresh = hz; }
void set_baba(unsigned int e) { baba_ev = e; gameplay.baba_events = e; }
void set_world(unsigned int e) { gameplay.world_sfx = e; }
unsigned world_pending(void) { return gameplay.world_sfx; }
void set_events2(unsigned int e) { gameplay.events2 = e; }
'''
        env = dict(os.environ, PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH',''))
        output = Path(cls.temp.name)/'audio.dll'
        subprocess.run([str(GCC), '-shared', '-O2', '-I'+str(ROOT/'src'), '-I'+str(GEN),
                        '-x','c','-','-o',str(output)], input=adapter+source+wrapper,
                       text=True, env=env, check=True)
        cls.lib = ctypes.CDLL(str(output))

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def setUp(self):
        self.lib.reset()
        self.lib.set_baba(0)
        self.lib.set_events2(0)

    def keyed(self, slot):
        return self.lib.reg(slot, 0) & 0x1800 == 0x1800

    def test_dungeon_events_play_once_from_tree_bank_without_touching_music(self):
        manifest=json.loads((GEN/'action_audio.json').read_text())
        bank=manifest['area_banks'][2]
        self.assertEqual(bank['file'],'SFXTREE.PCM')
        names=['scrub_up','scrub_down','scrub_throw','scrub_walk','scrub_hit','scrub_faint',
               'foot_switch','deku_hit','deku_dead','skull_hit','skull_dead','larva_hit',
               'larva_dead','gohma_hit','gohma_dead','correct','appear','door_open','door_close','freeze','box_item']
        samples={s['name']:s for s in bank['samples']}
        for i,name in enumerate(names):
            bank=manifest['area_banks'][3 if name.startswith('gohma') else 2]
            samples={s['name']:s for s in bank['samples']}
            self.lib.reset(); self.lib.set_area(3 if name.startswith('gohma') else 2,True)
            self.lib.set_world(1<<i);self.lib.action_audio_events(0)
            slot=30 if i in (15,16) else 26 if i>=17 or i<6 else 27 if i==6 else 28
            self.assertTrue(self.keyed(slot),name)
            self.assertEqual(self.lib.reg(slot,6),samples[name]['length'],name)
            self.assertEqual(self.lib.world_pending(),0)
            for music in range(24): self.assertEqual(self.lib.reg(music,0),0)
            self.lib.reset();self.lib.action_audio_events(0)
            self.assertFalse(self.keyed(slot),name)

    def test_lock_on_plays_human_or_hostile_on_slot_29(self):
        self.lib.action_audio_events(1 << 3)            # GP_EVENT_TARGET_ON
        self.assertTrue(self.keyed(29))
        human = self.lib.reg(29, 2)
        self.lib.reset()
        self.lib.set_events2(16)                         # GP2_EVENT_LOCK_HOSTILE
        self.lib.action_audio_events(1 << 3)
        self.assertNotEqual(human, self.lib.reg(29, 2))  # a different sample

    def test_navi_hello_and_call_use_slot_31_and_call_adds_the_chime(self):
        self.lib.set_events2(1)
        self.lib.action_audio_events(0)
        self.assertTrue(self.keyed(31))
        self.lib.reset()
        self.lib.set_events2(2)
        self.lib.action_audio_events(0)
        self.assertTrue(self.keyed(31) and self.keyed(30))

    def test_heart_recovery_overrides_generic_pickup_and_uses_own_sound(self):
        self.lib.action_audio_events(1)  # generic pickup
        generic = self.lib.reg(27, 2)
        self.lib.reset()
        self.lib.set_events2(1 << 18)
        self.lib.action_audio_events(1)
        self.assertTrue(self.keyed(27))
        self.assertNotEqual(generic, self.lib.reg(27, 2))
        self.assertFalse(self.keyed(25))  # never Link's voice slot

    def test_pickup_sound_is_consumed_once_even_if_actor_events_are_stale(self):
        self.lib.set_baba(64)
        self.lib.action_audio_events(0)
        self.assertTrue(self.keyed(27))
        self.lib.reset()
        self.lib.action_audio_events(0)
        self.assertFalse(self.keyed(27))

    def test_deku_baba_sounds_play_from_the_area_bank(self):
        self.lib.set_baba(4 | 8)                         # DEAD + LAST_DAMAGE
        self.lib.action_audio_events(0)
        self.assertTrue(self.keyed(28) and self.keyed(30))
        self.lib.reset()
        self.lib.set_area(0, True)                       # interior bank: no baba
        self.lib.set_baba(2)
        self.lib.action_audio_events(0)
        self.assertFalse(self.keyed(28))

    def test_swing_plays_blade_and_voice_without_touching_music_slots(self):
        self.lib.action_audio_events(2)
        # Every SFX is stored at half rate (bible rule), so octave 13.
        for slot, octave in ((24,13),(25,13)):
            self.assertEqual(self.lib.reg(slot,0) & 0x1830, 0x1810)
            self.assertEqual(self.lib.reg(slot,16), octave << 11)
            self.assertGreater(self.lib.reg(slot,6), 0)
        for slot in range(24):
            self.assertEqual(self.lib.reg(slot,0), 0)

    def test_cut_and_shield_and_equip_have_separate_routes(self):
        for event, slot in ((4,26),(32,24),(4096,27),(128,27),
                            (1<<14,25),(1<<15,28),(1<<16,28),(1<<17,25),(1<<18,29)):
            self.lib.reset()
            self.lib.action_audio_events(event)
            self.assertTrue(self.lib.reg(slot,0) & 0x800)

    def test_climb_end_voice_plays_at_its_stored_half_rate(self):
        # Roll bonk / climb end: EFFECT_35 is stored at 5512.5 Hz (octave 13).
        self.lib.action_audio_events(1 << 22)
        self.assertEqual(self.lib.reg(25,16), 13 << 11)

    def test_combat_sounds_use_the_forest_bank(self):
        for event, pitch in ((1 << 28, 13 << 11), (1 << 27, 13 << 11),
                             (1 << 29, 13 << 11), (1 << 30, 13 << 11)):
            self.lib.reset()
            self.lib.action_audio_events(event)
            self.assertTrue(self.lib.reg(28,0) & 0x800, hex(event))
            self.assertEqual(self.lib.reg(28,16), pitch)
            self.lib.reset()
            self.lib.set_area(0, True)
            self.lib.action_audio_events(event)
            self.assertEqual(self.lib.reg(28,0), 0)

    def test_cut_uses_area_bank_address_and_is_silent_without_it(self):
        self.lib.action_audio_events(4)
        address = ((self.lib.reg(26,0) & 15) << 16) | self.lib.reg(26,2)
        header = (GEN/'action_audio_data.h').read_text()
        base = int(re.search(r'#define SFX_AREA_BASE (\d+)', header)[1])
        self.assertEqual(address, base)
        for bank, loaded in ((0, True), (1, False)):
            self.lib.reset()
            self.lib.set_area(bank, loaded)
            self.lib.action_audio_events(4)
            self.assertEqual(self.lib.reg(26,0), 0)

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

    def test_voice_rotates_and_music_swap_keeps_resident_effects(self):
        addresses = []
        for _ in range(5):
            self.lib.action_audio_events(2)
            addresses.append(self.lib.reg(25,2))
        self.assertEqual(len(set(addresses[:4])),4)
        self.assertEqual(addresses[0],addresses[4])
        self.lib.reset()
        self.lib.set_busy(True)
        self.lib.action_audio_events(2 | 4 | 32 | 4096)
        for slot in range(24,28): self.assertTrue(self.lib.reg(slot,0) & 0x800)
        for slot in range(24): self.assertEqual(self.lib.reg(slot,0),0)

    def test_opening_loop_uses_reserved_tail_and_stops(self):
        self.lib.use_opening()
        self.lib.set_busy(True)
        self.lib.action_audio_opening_play(8,0,True)
        self.assertEqual(self.lib.reg(24,16),13 << 11)
        self.assertEqual(self.lib.reg(24,0) & 0x1830,0x1830)
        address = ((self.lib.reg(24,0)&15)<<16) | self.lib.reg(24,2)
        self.assertGreaterEqual(address,0x50000)
        self.assertLessEqual(address+self.lib.reg(24,6),0x80000)
        self.lib.action_audio_opening_stop(0)
        self.assertEqual(self.lib.reg(24,12),255)
        self.assertFalse(self.lib.reg(24,0)&0x800)
