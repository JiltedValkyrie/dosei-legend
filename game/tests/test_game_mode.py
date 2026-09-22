"""Drive the real game_mode.c transition table on the host.

game_mode.c replaces the `title_visible`/`file_select_visible` pair demo.c used
to carry. What is worth protecting is not that the enum exists but that the
edges are the ones the game actually takes: the opening cutscene chains four
scenes through CUTSCENE -> LOADING -> CUTSCENE, and nothing else in the game
may take that route. A refused transition must leave the mode alone rather
than half-applying.
"""
import ctypes
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')

TITLE, FILE_SELECT, LOADING, PLAY, PAUSE, DIALOGUE, CUTSCENE, GAME_OVER = range(8)
COUNT = 8

NAMES = {TITLE: 'TITLE', FILE_SELECT: 'FILE_SELECT', LOADING: 'LOADING',
         PLAY: 'PLAY', PAUSE: 'PAUSE', DIALOGUE: 'DIALOGUE',
         CUTSCENE: 'CUTSCENE', GAME_OVER: 'GAME_OVER'}

# The table, written out independently of game_mode.c so a careless edit to one
# has to be made deliberately in the other.
EDGES = {
    TITLE:       {FILE_SELECT},
    FILE_SELECT: {TITLE, LOADING},
    LOADING:     {PLAY, CUTSCENE, FILE_SELECT},
    PLAY:        {PAUSE, DIALOGUE, CUTSCENE, LOADING, GAME_OVER},
    PAUSE:       {PLAY},
    DIALOGUE:    {PLAY},
    CUTSCENE:    {PLAY, LOADING},
    GAME_OVER:   {FILE_SELECT, TITLE},
}


@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class GameMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        output = pathlib.Path(cls.tmp.name) / 'game_mode.dll'
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-o', str(output),
                        '-I' + str(ROOT / 'src'),
                        str(ROOT / 'src/game_mode.c')],
                       check=True, env=env, cwd=str(ROOT))
        cls.lib = ctypes.CDLL(str(output))
        cls.lib.game_mode.restype = ctypes.c_int
        cls.lib.game_mode_can.restype = ctypes.c_bool
        cls.lib.game_mode_set.restype = ctypes.c_bool
        cls.lib.game_mode_owns_pad.restype = ctypes.c_bool
        cls.lib.game_mode_world_steps.restype = ctypes.c_bool
        cls.lib.game_mode_name.restype = ctypes.c_char_p

    def setUp(self):
        self.lib.game_mode_reset()

    def goto(self, *modes):
        """Walk a legal route, asserting each hop is taken."""
        for mode in modes:
            self.assertTrue(self.lib.game_mode_set(mode),
                            'refused hop to ' + NAMES[mode])
        return self.lib.game_mode()

    # ---- the table -----------------------------------------------------

    def test_starts_on_the_title(self):
        self.assertEqual(self.lib.game_mode(), TITLE)

    def test_every_edge_matches_the_table(self):
        for source, targets in EDGES.items():
            for target in range(COUNT):
                self.lib.game_mode_reset()
                # Reach `source` by whatever legal route exists, then test one
                # hop. TITLE is already the start.
                if source != TITLE:
                    self.assertTrue(self.route_to(source),
                                    'no route to ' + NAMES[source])
                expected = target in targets
                self.assertEqual(self.lib.game_mode_can(target), expected,
                                 '%s -> %s' % (NAMES[source], NAMES[target]))

    def route_to(self, target):
        """Breadth-first walk of EDGES, applied for real through game_mode_set."""
        seen, queue = {TITLE: []}, [TITLE]
        while queue:
            node = queue.pop(0)
            if node == target:
                for hop in seen[node]:
                    if not self.lib.game_mode_set(hop):
                        return False
                return self.lib.game_mode() == target
            for nxt in sorted(EDGES[node]):
                if nxt not in seen:
                    seen[nxt] = seen[node] + [nxt]
                    queue.append(nxt)
        return False

    def test_a_mode_is_never_reachable_from_itself(self):
        for mode in range(COUNT):
            self.lib.game_mode_reset()
            if mode != TITLE:
                self.assertTrue(self.route_to(mode))
            self.assertFalse(self.lib.game_mode_can(mode),
                             NAMES[mode] + ' re-entered itself')

    def test_a_refused_transition_changes_nothing(self):
        self.goto(FILE_SELECT)
        self.assertFalse(self.lib.game_mode_set(PLAY))
        self.assertEqual(self.lib.game_mode(), FILE_SELECT)

    def test_out_of_range_is_refused_not_indexed(self):
        for bad in (-1, COUNT, COUNT + 40):
            self.assertFalse(self.lib.game_mode_can(bad))
            self.assertFalse(self.lib.game_mode_set(bad))
        self.assertEqual(self.lib.game_mode(), TITLE)
        self.assertEqual(self.lib.game_mode_name(COUNT), b'?')

    def test_reset_returns_to_the_title_from_anywhere(self):
        self.goto(FILE_SELECT, LOADING, PLAY, GAME_OVER)
        self.lib.game_mode_reset()
        self.assertEqual(self.lib.game_mode(), TITLE)

    # ---- the routes the opening actually takes -------------------------

    def test_new_game_reaches_the_intro_cutscene(self):
        """Title -> file select -> load -> cutscene, not straight to play."""
        self.assertEqual(self.goto(FILE_SELECT, LOADING, CUTSCENE), CUTSCENE)

    def test_the_four_intro_cutscenes_chain_through_loading(self):
        """CS_DESTINATION hands each cutscene to the next scene's cutscene."""
        self.goto(FILE_SELECT, LOADING, CUTSCENE)
        for _ in range(3):                       # sleep -> nightmare -> navi -> wake
            self.goto(LOADING, CUTSCENE)
        # The last one ends with CS_MISC_STOP_CUTSCENE.
        self.assertEqual(self.goto(PLAY), PLAY)

    def test_continue_a_save_goes_straight_to_play(self):
        self.assertEqual(self.goto(FILE_SELECT, LOADING, PLAY), PLAY)

    def test_a_failed_disc_read_falls_back_to_the_file_select(self):
        self.goto(FILE_SELECT, LOADING)
        self.assertEqual(self.goto(FILE_SELECT), FILE_SELECT)

    def test_a_door_reloads_without_passing_through_a_menu(self):
        self.goto(FILE_SELECT, LOADING, PLAY)
        self.assertEqual(self.goto(LOADING, PLAY), PLAY)

    def test_the_title_cannot_be_reached_from_play(self):
        """Start is the pause button once the game has begun, not a way back."""
        self.goto(FILE_SELECT, LOADING, PLAY)
        self.assertFalse(self.lib.game_mode_can(TITLE))
        self.goto(PAUSE)
        self.assertFalse(self.lib.game_mode_can(TITLE))

    # ---- the two derived questions -------------------------------------

    def test_menus_own_the_pad_and_the_world_does_not(self):
        for mode in (FILE_SELECT, PAUSE, DIALOGUE):
            self.lib.game_mode_reset()
            self.route_to(mode)
            self.assertTrue(self.lib.game_mode_owns_pad(), NAMES[mode])

    def test_the_title_and_cutscenes_do_not_use_the_menu_mapping(self):
        """Both take a single raw button, so B must not become 'cancel'."""
        self.assertFalse(self.lib.game_mode_owns_pad())     # title
        self.goto(FILE_SELECT, LOADING, CUTSCENE)
        self.assertFalse(self.lib.game_mode_owns_pad())

    def test_the_world_steps_in_play_and_dialogue_only(self):
        stepping = {PLAY, DIALOGUE}
        for mode in range(COUNT):
            self.lib.game_mode_reset()
            if mode != TITLE:
                self.route_to(mode)
            self.assertEqual(self.lib.game_mode_world_steps(),
                             mode in stepping, NAMES[mode])

    def test_a_cutscene_does_not_step_the_world(self):
        """Its actors come from baked cues; a live step would fight them."""
        self.goto(FILE_SELECT, LOADING, CUTSCENE)
        self.assertFalse(self.lib.game_mode_world_steps())

    def test_names_are_distinct_and_never_null(self):
        seen = {self.lib.game_mode_name(m) for m in range(COUNT)}
        self.assertEqual(len(seen), COUNT)
        self.assertNotIn(None, seen)


if __name__ == '__main__':
    unittest.main()
