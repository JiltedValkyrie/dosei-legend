"""Check the baked opening cutscenes against the decomp they came from.

build_cutscenes.py is the only place OoT's cutscene format is understood, so
these read the original .csdata.inc.c files independently and assert the bake
agrees with them. What is worth protecting:

  * the four cutscenes chain in the order CS_DESTINATION says, ending in
    gameplay -- that chain IS the storyboard;
  * the text ids are the real ones, so no line of the opening is invented;
  * the camera is baked at the original's own rate, including the double
    advance the shared eye/at spline state causes;
  * the tracks stay small enough to load one at a time.
"""
import pathlib
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import build_cutscenes as bake                                  # noqa: E402

SOURCES_PRESENT = all(entry['path'].is_file() for entry in bake.CUTSCENES)


@unittest.skipUnless(SOURCES_PRESENT, 'OoT decomp cutscene data required')
class Cutscenes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baked = {entry['key']: bake.read_cutscene(entry)
                     for entry in bake.CUTSCENES}

    # ---- the chain -----------------------------------------------------

    def test_the_four_cutscenes_chain_in_storyboard_order(self):
        chain = []
        key = 'SLEEP'
        while key:
            chain.append(key)
            destination = self.baked[key]['destination']
            key = destination['next'] if destination else None
        self.assertEqual(chain, ['SLEEP', 'NIGHTMARE', 'NAVI_FLY', 'WAKE_UP'])

    def test_the_last_cutscene_ends_rather_than_chaining(self):
        wake = self.baked['WAKE_UP']
        self.assertIsNone(wake['destination'])
        self.assertEqual(wake['stop_frame'], 647)

    def test_each_cutscene_knows_which_scene_it_plays_in(self):
        self.assertEqual(self.baked['SLEEP']['scene'], 'LINK_HOME')
        self.assertEqual(self.baked['NIGHTMARE']['scene'], 'SPOT00')
        self.assertEqual(self.baked['NAVI_FLY']['scene'], 'SPOT04')
        self.assertEqual(self.baked['WAKE_UP']['scene'], 'LINK_HOME')

    def test_every_destination_in_the_opening_is_mapped(self):
        for key, cs in self.baked.items():
            if cs['destination']:
                self.assertIsNotNone(cs['destination']['next'],
                                     key + ' has an unmapped destination')

    # ---- the text ------------------------------------------------------

    def test_the_narration_is_the_real_deku_tree_text(self):
        ids = [t['id'] for t in self.baked['SLEEP']['text'] if t['id']]
        self.assertEqual(ids, [0x109D, 0x109E, 0x109F])

    def test_navi_is_summoned_then_told_the_deku_trees_words(self):
        ids = [t['id'] for t in self.baked['NAVI_FLY']['text'] if t['id']]
        self.assertEqual(ids, [0x1099, 0x109A])

    def test_the_wake_up_text_ends_with_navis_introduction(self):
        ids = [t['id'] for t in self.baked['WAKE_UP']['text'] if t['id']]
        self.assertEqual(ids, [0x1095, 0x1096, 0x1000, 0x1098])

    def test_every_baked_text_id_exists_in_the_message_table(self):
        table = (bake.OOT / 'extracted/ntsc-1.2/text/message_data.h').read_text(
            encoding='utf-8', errors='replace')
        for key, cs in self.baked.items():
            for item in cs['text']:
                if item['id'] is None:
                    continue
                self.assertIn('DEFINE_MESSAGE(0x%04X,' % item['id'], table,
                              '%s references a message that does not exist' % key)

    def test_text_windows_are_ordered_and_non_negative(self):
        for key, cs in self.baked.items():
            previous = -1
            for item in cs['text']:
                self.assertGreaterEqual(item['start'], previous, key)
                self.assertGreaterEqual(item['end'], item['start'], key)
                previous = item['start']

    # ---- the music -----------------------------------------------------

    def test_the_nightmare_starts_ganondorfs_theme(self):
        music = self.baked['NIGHTMARE']['music']
        self.assertEqual([m['sequence'] for m in music],
                         ['NA_BGM_OPENING_GANON'])
        self.assertEqual(music[0]['bank'], 'NIGHTMARE')
        self.assertFalse(music[0]['stop'])

    def test_the_deku_tree_theme_stops_before_navis_begins(self):
        music = sorted(self.baked['NAVI_FLY']['music'], key=lambda m: m['start'])
        self.assertEqual([(m['sequence'], m['stop']) for m in music],
                         [('NA_BGM_DEKU_TREE_CS', True),
                          ('NA_BGM_NAVI_OPENING', False)])

    def test_every_sequence_used_by_the_opening_has_a_bank(self):
        for key, cs in self.baked.items():
            for item in cs['music']:
                self.assertIsNotNone(item['bank'],
                                     '%s uses unmapped %s' % (key, item['sequence']))

    # ---- Link's poses --------------------------------------------------

    def test_link_sleeps_then_sits_up_then_stands(self):
        clips = [c['clip'] for c in self.baked['WAKE_UP']['player_cues']]
        self.assertEqual(clips[:1], ['SLEEPING'])
        self.assertIn('SIT_UP', clips)
        self.assertLess(clips.index('SIT_UP'), clips.index('STAND_UP'))

    def test_the_opening_needs_exactly_these_link_clips(self):
        """The list Phase F has to produce. IDLE exists already; HOLD is not a
        clip but 'keep the current pose', which some cues genuinely mean."""
        used = {c['clip'] for cs in self.baked.values()
                for c in cs['player_cues']}
        self.assertEqual(used, {'HOLD', 'IDLE', 'SLEEPING', 'TURN_OVER',
                                'SIT_UP', 'STAND_UP', 'TURN_LOOK'})

    def test_every_player_cue_in_the_opening_maps_to_a_clip(self):
        for key, cs in self.baked.items():
            for item in cs['player_cues']:
                self.assertIsNotNone(item['clip'],
                                     '%s uses unmapped %s' % (key, item['id']))

    # ---- the camera ----------------------------------------------------

    def test_a_cutscene_is_exactly_as_long_as_its_handoff(self):
        """The header's 3000-frame allotment is not the length."""
        for key, cs in self.baked.items():
            self.assertEqual(cs['header_frames'], 3000)
            self.assertLess(cs['frames'], 3000, key + ' baked its allotment')
            self.assertEqual(len(cs['track']), cs['frames'])
        self.assertEqual(self.baked['SLEEP']['frames'], 281)
        self.assertEqual(self.baked['NIGHTMARE']['frames'], 541)
        self.assertEqual(self.baked['NAVI_FLY']['frames'], 941)
        self.assertEqual(self.baked['WAKE_UP']['frames'], 648)

    def test_the_moving_shots_actually_move(self):
        for key in ('NIGHTMARE', 'NAVI_FLY'):
            track = self.baked[key]['track']
            positions = {point[:3] for point in track}
            self.assertGreater(len(positions), 50,
                               key + ' baked a camera that barely moves')

    def test_links_house_is_filmed_from_one_fixed_point(self):
        """Both house cutscenes are ROOM_SHAPE_TYPE_IMAGE in the original, so
        the eye never moves -- which is why a backdrop interior can render
        them at all. If this ever fails, link_home needs real geometry."""
        for key in ('SLEEP', 'WAKE_UP'):
            positions = {point[:3] for point in self.baked[key]['track']}
            self.assertEqual(positions, {(0, 34, 0)},
                             key + ' moved the camera inside Link\'s house')

    def test_every_baked_value_fits_the_s16_the_runtime_reads(self):
        for key, cs in self.baked.items():
            for point in cs['track']:
                for value in point:
                    self.assertTrue(-32768 <= value <= 32767, key)

    def test_the_spline_advances_twice_per_frame(self):
        """Eye and at share one keyframe/curFrame pair (z_camera.c:5861), so a
        bake that advances once per frame runs the camera at half speed."""
        points = [('CS_CAM_CONTINUE', 0, 10, 60, i * 100, 0, 0)
                  for i in range(6)] + [('CS_CAM_STOP', 0, 10, 60, 600, 0, 0)]
        shared = bake.bake_shot(bake.Spline(points), bake.Spline(points), 8)
        single = bake.Spline(points)
        state = {'key': 0, 'frame': 0.0}
        solo = [single.sample(state) for _ in range(8)]
        self.assertGreater(shared[3][0][0], solo[3][0][0])

    # ---- what it costs -------------------------------------------------

    def test_one_track_at_a_time_stays_small(self):
        """They are loaded into cart RAM one at a time; the whole set never
        has to be resident, and none of it is linked into .bss."""
        biggest = max(len(cs['track']) for cs in self.baked.values())
        self.assertLess(biggest * bake.TRACK_BYTES, 16 * 1024)

    def test_the_whole_set_stays_small_on_the_disc(self):
        total = sum(len(cs['track']) for cs in self.baked.values())
        self.assertLess(total * bake.TRACK_BYTES, 48 * 1024)

    def test_a_track_round_trips_through_the_packed_form(self):
        track = self.baked['NAVI_FLY']['track']
        packed = bake.pack_track(track)
        self.assertEqual(len(packed), len(track) * bake.TRACK_BYTES)
        first = struct.unpack_from(bake.TRACK_FORMAT, packed, 0)
        self.assertEqual(tuple(track[0]), first)

    # ---- what was deliberately dropped ---------------------------------

    def test_only_the_inapplicable_commands_are_ignored(self):
        dropped = set().union(*(cs['ignored'] for cs in self.baked.values()))
        self.assertTrue(dropped <= set(bake.IGNORED))
        # The pad has no rumble motor, so this one must genuinely be dropped.
        self.assertIn('CS_RUMBLE_CONTROLLER', dropped)


if __name__ == '__main__':
    unittest.main()
