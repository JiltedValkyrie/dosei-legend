"""Drive the real message.c against the real baked opening text.

No fixture text: the tables come from build_cutscenes.py, so these check the
player against the words the game will actually say. What matters:

  * the three ways a page ends are all honoured -- the opening narration uses
    a button page, a self-advancing page and a fading page, and getting any of
    them wrong either hangs the cutscene or flashes a line past unread;
  * delayed pages hold until A after their minimum delay, so text stays readable;
  * colour survives as runs within a line, which is what panels 8 and 12 of
    the storyboard show.
"""
import ctypes
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')
GENERATED = ROOT / 'build/generated'

sys.path.insert(0, str(ROOT / 'tools'))
import build_cutscenes as bake                                  # noqa: E402

# Ids the storyboard names.
NARRATION = 0x109D          # "In the vast, deep forest of Hyrule..."
SUMMONING = 0x1099          # "Navi, where art thou?"
DEKU_TREE = 0x109A          # the speech to Navi
NAVI_WAKE = 0x1000          # "You finally woke up!"

BUTTON, DELAY, FADE = 0, 1, 2


@unittest.skipUnless(GCC.is_file(), 'host compiler required')
@unittest.skipUnless((GENERATED / 'cutscenes.c').is_file(),
                     'generated cutscene tables required')
class Message(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        output = pathlib.Path(cls.tmp.name) / 'message.dll'
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-o', str(output),
                        '-I' + str(ROOT / 'src'), '-I' + str(GENERATED),
                        str(ROOT / 'src/message.c'),
                        str(GENERATED / 'cutscenes.c')],
                       check=True, env=env, cwd=str(ROOT))
        cls.lib = ctypes.CDLL(str(output))
        for name in ('message_start', 'message_step', 'message_is_active',
                     'message_finished', 'message_waits_for_button'):
            getattr(cls.lib, name).restype = ctypes.c_bool
        cls.lib.message_run_text.restype = ctypes.c_char_p
        for name in ('message_lines', 'message_line_runs', 'message_run_colour',
                     'message_line_indent', 'message_box', 'message_position'):
            getattr(cls.lib, name).restype = ctypes.c_uint

        # The same tables, read independently, to compare against.
        entries = [dict(entry) for entry in bake.CUTSCENES]
        cls.baked = [bake.read_cutscene(entry) for entry in entries]
        cls.messages = bake.collect_messages(
            cls.baked, bake.oot_messages.load_messages(bake.OOT))
        cls.by_id = {m['id']: m for m in cls.messages}

    def setUp(self):
        self.lib.message_stop()

    # ---- helpers -------------------------------------------------------

    def page_text(self):
        """The page as it will be drawn, indent included -- the renderer
        starts each line at message_line_indent()."""
        lines = []
        for line in range(self.lib.message_lines()):
            runs = [self.lib.message_run_text(line, r).decode()
                    for r in range(self.lib.message_line_runs(line))]
            lines.append(' ' * self.lib.message_line_indent(line) +
                         ''.join(runs))
        return lines

    def page_runs(self, line):
        return [(self.lib.message_run_text(line, r).decode(),
                 self.lib.message_run_colour(line, r))
                for r in range(self.lib.message_line_runs(line))]

    def run_until_done(self, confirm=False, limit=4000):
        """Step until the message ends. Returns the pages seen, in order."""
        seen, ticks = [], 0
        while self.lib.message_is_active() and ticks < limit:
            text = self.page_text()
            if not seen or seen[-1] != text:
                seen.append(text)
            self.lib.message_step(confirm)
            ticks += 1
        self.assertLess(ticks, limit, 'message never ended')
        return seen

    # ---- starting ------------------------------------------------------

    def test_a_real_message_starts(self):
        self.assertTrue(self.lib.message_start(NARRATION))
        self.assertTrue(self.lib.message_is_active())

    def test_a_message_the_opening_never_says_shows_nothing(self):
        """Silence reads as a bug; the wrong line does not."""
        self.assertFalse(self.lib.message_start(0x0001))
        self.assertFalse(self.lib.message_is_active())
        self.assertEqual(self.lib.message_lines(), 0)

    def test_every_message_the_cutscenes_reference_is_present(self):
        for cs in self.baked:
            for item in cs['text']:
                if item['id']:
                    self.assertTrue(self.lib.message_start(item['id']),
                                    'missing 0x%04X' % item['id'])

    def test_stopping_clears_the_screen(self):
        self.lib.message_start(NARRATION)
        self.lib.message_stop()
        self.assertFalse(self.lib.message_is_active())
        self.assertEqual(self.lib.message_lines(), 0)

    # ---- the words -----------------------------------------------------

    def test_the_narration_is_the_line_from_the_storyboard(self):
        self.lib.message_start(NARRATION)
        self.assertEqual(self.page_text(),
                         ['In the vast, deep forest of Hyrule...'])

    def test_navi_is_summoned_in_the_original_words(self):
        """Storyboard panel 7: three staggered lines, centred with SHIFT."""
        self.lib.message_start(SUMMONING)
        self.assertEqual([line.strip() for line in self.page_text()],
                         ['Navi...', 'Navi, where art thou?',
                          'Come hither....'])
        self.assertGreater(self.lib.message_line_indent(0), 0)

    def test_every_page_matches_the_message_table(self):
        for message in self.messages:
            self.lib.message_start(message['id'])
            seen = self.run_until_done(confirm=True)
            expected = [bake.oot_messages.plain(page)
                        for page in message['pages']]
            self.assertEqual(seen, expected, '0x%04X' % message['id'])

    def test_no_line_overflows_the_text_layer(self):
        for message in self.messages:
            self.lib.message_start(message['id'])
            while self.lib.message_is_active():
                for line in self.page_text():
                    self.assertLessEqual(len(line), bake.MESSAGE_COLUMNS)
                self.assertLessEqual(self.lib.message_lines(),
                                     bake.MESSAGE_LINES)
                self.lib.message_step(True)

    # ---- colour --------------------------------------------------------

    def test_navi_introduces_herself_with_her_name_in_red(self):
        """Storyboard panel 12: coloured words inside a coloured line."""
        self.lib.message_start(NAVI_WAKE)
        runs = self.page_runs(1)
        self.assertEqual([text for text, _ in runs],
                         ["I'm ", 'Navi ', 'the fairy!'])
        self.assertNotEqual(runs[0][1], runs[1][1])

    def test_the_deku_tree_names_navi_and_himself_in_colour(self):
        """Storyboard panel 8."""
        self.lib.message_start(DEKU_TREE)
        first = self.page_runs(0)
        self.assertEqual([text for text, _ in first],
                         ['Oh, ', 'Navi the fairy', '...'])
        self.assertEqual(first[0][1], first[2][1])
        self.assertNotEqual(first[0][1], first[1][1])

    def test_an_uncoloured_line_is_a_single_run(self):
        self.lib.message_start(SUMMONING)
        self.assertEqual(self.lib.message_line_runs(0), 1)

    def test_runs_outside_the_page_are_empty_rather_than_garbage(self):
        self.lib.message_start(SUMMONING)
        self.assertEqual(self.lib.message_run_text(99, 0), b'')
        self.assertEqual(self.lib.message_run_text(0, 99), b'')
        self.assertEqual(self.lib.message_line_runs(99), 0)

    # ---- the three ways a page ends ------------------------------------

    def test_a_button_page_waits_forever_without_a_press(self):
        self.lib.message_start(SUMMONING)
        self.assertTrue(self.lib.message_waits_for_button())
        for _ in range(600):
            self.lib.message_step(False)
        self.assertTrue(self.lib.message_is_active())
        self.assertEqual(self.page_text()[0].strip(), 'Navi...')

    def test_a_button_page_turns_on_a_press(self):
        self.lib.message_start(DEKU_TREE)
        first = self.page_text()
        self.lib.message_step(True)
        self.assertNotEqual(self.page_text(), first)

    def test_a_delayed_page_waits_for_a_press_after_its_delay(self):
        """'In the vast, deep forest of Hyrule...' -- BOX_BREAK_DELAYED(40)."""
        page = self.by_id[NARRATION]['pages'][0]
        self.assertEqual(page['advance'], 'delay')
        self.lib.message_start(NARRATION)
        self.assertFalse(self.lib.message_waits_for_button())
        # Before the delay is up the page cannot be turned at all.
        for _ in range(page['delay'] - 1):
            self.lib.message_step(False)
            self.assertFalse(self.lib.message_waits_for_button())
        # The tick that reaches the delay is the one that opens it up.
        self.lib.message_step(False)
        self.assertEqual(self.page_text(),
                         ['In the vast, deep forest of Hyrule...'])
        self.assertTrue(self.lib.message_waits_for_button())
        self.lib.message_step(False)
        self.assertEqual(self.page_text(),
                         ['In the vast, deep forest of Hyrule...'])
        self.lib.message_step(True)
        self.assertNotEqual(self.page_text(),
                            ['In the vast, deep forest of Hyrule...'])

    def test_a_press_cannot_skip_a_timed_page(self):
        """These pages are UNSKIPPABLE in the original."""
        page = self.by_id[NARRATION]['pages'][0]
        self.lib.message_start(NARRATION)
        for _ in range(page['delay'] - 1):
            self.lib.message_step(True)
        self.assertEqual(self.page_text(),
                         ['In the vast, deep forest of Hyrule...'])

    def test_the_last_narration_page_fades_out_on_its_own(self):
        """FADE(70): no press, and the text dims before it goes."""
        message = self.by_id[NARRATION]
        last = message['pages'][-1]
        self.assertEqual(last['advance'], 'fade')
        self.lib.message_start(NARRATION)
        while self.lib.message_lines() and \
                self.page_text() != bake.oot_messages.plain(last):
            self.lib.message_step(True)
        for _ in range(last['delay']):
            self.lib.message_step(False)
        self.assertTrue(self.lib.message_is_active())
        self.lib.message_step(False)
        self.assertGreater(self.fade(), 0, 'text vanished instead of fading')

    def fade(self):
        # Mirror of message_state_t, so the fade byte is read through the
        # declared layout rather than a guessed offset.
        class State(ctypes.Structure):
            _fields_ = [('active', ctypes.c_bool),
                        ('message', ctypes.c_ushort),
                        ('page', ctypes.c_ubyte),
                        ('page_ticks', ctypes.c_ushort),
                        ('finished', ctypes.c_bool),
                        ('fade', ctypes.c_ubyte)]
        return State.in_dll(self.lib, 'message_state').fade

    def test_a_fading_page_eventually_ends_the_message(self):
        self.lib.message_start(NARRATION)
        self.run_until_done(confirm=True)
        self.assertFalse(self.lib.message_is_active())

    def test_the_narration_waits_for_confirmation_between_pages(self):
        self.lib.message_start(NARRATION)
        self.assertEqual(len(self.run_until_done(confirm=True)),
                         len(self.by_id[NARRATION]['pages']))

    # ---- finishing -----------------------------------------------------

    def test_finished_is_raised_once(self):
        self.lib.message_start(SUMMONING)
        while self.lib.message_is_active():
            self.lib.message_step(True)
        self.assertTrue(self.lib.message_finished())
        self.lib.message_step(False)
        self.assertFalse(self.lib.message_finished())

    def test_stepping_a_finished_message_does_nothing(self):
        self.lib.message_start(SUMMONING)
        while self.lib.message_is_active():
            self.lib.message_step(True)
        self.assertFalse(self.lib.message_step(True))
        self.assertEqual(self.lib.message_lines(), 0)

    # ---- box style -----------------------------------------------------

    def test_the_box_style_comes_from_the_original(self):
        styles = {m['id']: (m['box'], m['position']) for m in self.messages}
        self.lib.message_start(SUMMONING)
        self.assertEqual(styles[SUMMONING][0], 'TEXTBOX_TYPE_NONE_NO_SHADOW')
        self.assertEqual(styles[SUMMONING][1], 'TEXTBOX_POS_MIDDLE')
        self.lib.message_start(DEKU_TREE)
        self.assertEqual(styles[DEKU_TREE][0], 'TEXTBOX_TYPE_BLACK')

    def test_the_narration_has_no_box_around_it(self):
        """Storyboard panel 3 is bare text on black."""
        styles = {m['id']: m['box'] for m in self.messages}
        self.assertEqual(styles[NARRATION], 'TEXTBOX_TYPE_NONE_BOTTOM')


if __name__ == '__main__':
    unittest.main()
