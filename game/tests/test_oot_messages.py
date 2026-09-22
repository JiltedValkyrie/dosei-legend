"""Check the shared OoT message parser against the real message table.

tools/oot_messages.py is the one place the message format is understood, used
by both build_dialogue.py (the NPC script) and build_cutscenes.py (the
opening's narration). The behaviour worth pinning down is the part that is
easy to get subtly wrong and hard to see afterwards: COLOR() runs inside a
line, the three page endings, and reading a message body to its real end.
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import oot_messages as messages                                 # noqa: E402

OOT = pathlib.Path('D:/Workspace-Claude/game-decomps/n64/oot')
TABLE = OOT / 'extracted/ntsc-1.2/text/message_data.h'


class Parsing(unittest.TestCase):
    """Cases written out by hand, so they do not depend on the decomp."""

    def pages(self, body, **kwargs):
        return messages.parse_pages(body, **kwargs)

    def test_a_plain_line_is_one_default_run(self):
        page, = self.pages('"Hello there"')
        self.assertEqual(page['lines'][0]['runs'],
                         [('Hello there', 'WHITE')])

    def test_colour_splits_a_line_into_runs(self):
        page, = self.pages('"I\'m " COLOR(RED) "Navi " COLOR(DEFAULT) "here"')
        self.assertEqual(page['lines'][0]['runs'],
                         [("I'm ", 'WHITE'), ('Navi ', 'RED'),
                          ('here', 'WHITE')])

    def test_colour_carries_across_a_line_break(self):
        """OoT leaves a colour set until it is changed, including onto the
        next line; resetting per line would turn Navi's speech white."""
        page, = self.pages('COLOR(BLUE) "one\\n" "two"')
        self.assertEqual([run[1] for line in page['lines']
                          for run in line['runs']], ['BLUE', 'BLUE'])

    def test_lightblue_is_navis_colour_and_maps_to_blue(self):
        page, = self.pages('COLOR(LIGHTBLUE) "Navi"')
        self.assertEqual(page['lines'][0]['runs'][0][1], 'BLUE')

    def test_box_break_starts_a_page_that_waits_for_a_button(self):
        first, second = self.pages('"one" BOX_BREAK "two"')
        self.assertEqual(first['advance'], 'button')
        self.assertEqual(messages.plain(first), ['one'])
        self.assertEqual(messages.plain(second), ['two'])

    def test_a_delayed_break_records_its_delay(self):
        first, _ = self.pages('"one" BOX_BREAK_DELAYED(40) "two"')
        self.assertEqual((first['advance'], first['delay']), ('delay', 40))

    def test_fade_records_its_delay_on_the_page_it_ends(self):
        page, = self.pages('"the end" FADE(70)')
        self.assertEqual((page['advance'], page['delay']), ('fade', 70))

    def test_a_delayed_break_is_not_read_as_a_plain_break(self):
        """BOX_BREAK_DELAYED contains BOX_BREAK; matching the shorter one
        first would drop the delay and make the page wait forever."""
        first, _ = self.pages('"one" BOX_BREAK_DELAYED(12) "two"')
        self.assertNotEqual(first['advance'], 'button')

    def test_the_players_name_is_spliced_in(self):
        page, = self.pages('"Hey, " NAME "!"')
        self.assertEqual(messages.plain(page), ['Hey, Link!'])

    def test_shift_indents_the_line_it_precedes(self):
        """SHIFT is how the narration is centred, so the indent has to survive
        trimming rather than being stripped as leading whitespace."""
        # SHIFT is a pixel offset (z_message.c:1485) into a 256-pixel field,
        # scaled here to the box's columns.
        page, = self.pages('SHIFT(128) "centred"', max_columns=40)
        self.assertEqual(page['lines'][0]['indent'], 20)
        self.assertTrue(messages.plain(page)[0].startswith(' ' * 20))
        self.assertEqual(page['lines'][0]['runs'], [('centred', 'WHITE')])

    def test_the_indent_scales_with_the_width_of_the_box(self):
        wide, = self.pages('SHIFT(128) "x"', max_columns=40)
        narrow, = self.pages('SHIFT(128) "x"', max_columns=20)
        self.assertEqual((wide['lines'][0]['indent'],
                          narrow['lines'][0]['indent']), (20, 10))

    def test_an_indent_can_never_push_a_line_off_the_box(self):
        page, = self.pages('SHIFT(255) "x"', max_columns=10)
        self.assertLess(page['lines'][0]['indent'], 10)

    def test_unknown_macros_are_dropped_not_printed(self):
        page, = self.pages('UNSKIPPABLE QUICKTEXT_ENABLE "text" '
                           'QUICKTEXT_DISABLE')
        self.assertEqual(messages.plain(page), ['text'])

    def test_a_missing_translation_yields_nothing(self):
        self.assertEqual(self.pages('/* MISSING */'), [])
        self.assertEqual(self.pages(''), [])

    def test_lines_are_clipped_to_the_box_width(self):
        page, = self.pages('"%s"' % ('x' * 80), max_columns=10)
        self.assertEqual(messages.plain(page), ['x' * 10])

    def test_clipping_counts_the_whole_line_not_each_run(self):
        page, = self.pages('"12345" COLOR(RED) "67890abc"', max_columns=8)
        self.assertEqual(len(messages.plain(page)[0]), 8)

    def test_pages_and_lines_are_capped(self):
        body = ' BOX_BREAK '.join('"page%d"' % i for i in range(20))
        self.assertEqual(len(self.pages(body, max_pages=3)), 3)
        page, = self.pages('"a\\nb\\nc\\nd\\ne"', max_lines=2)
        self.assertEqual(len(page['lines']), 2)

    def test_empty_lines_are_dropped_rather_than_left_blank(self):
        page, = self.pages('"one\\n\\n\\ntwo"')
        self.assertEqual(messages.plain(page), ['one', 'two'])


class MsgGroups(unittest.TestCase):
    def test_a_body_is_read_past_its_own_parenthesised_macros(self):
        """The regex this replaced stopped at the first ')', truncating every
        message whose last macro was FADE(n) or SHIFT(n) -- including the end
        of the opening narration."""
        block = 'DEFINE_MESSAGE(0x1000, T, P,\nMSG(jpn)\n,\nMSG("a" FADE(70))\n)'
        groups = messages.msg_groups(block)
        self.assertEqual(len(groups), 2)
        self.assertIn('FADE(70)', groups[1])

    def test_groups_come_back_in_language_order(self):
        block = 'MSG(one)\n,\nMSG(two)\n,\nMSG(three)'
        self.assertEqual(messages.msg_groups(block), ['one', 'two', 'three'])


@unittest.skipUnless(TABLE.is_file(), 'extracted OoT message table required')
class RealTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.messages = messages.load_messages(OOT)

    def test_the_table_loads_with_its_box_styles(self):
        self.assertGreater(len(self.messages), 1000)
        self.assertEqual(self.messages[0x109D]['box'],
                         'TEXTBOX_TYPE_NONE_BOTTOM')

    def test_the_narration_keeps_its_full_first_line(self):
        """34 columns cut this mid-word; the cutscene layer is wider."""
        page = messages.parse_pages(self.messages[0x109D]['body'])[0]
        self.assertEqual(messages.plain(page),
                         ['In the vast, deep forest of Hyrule...'])

    def test_the_narration_ends_by_fading_not_by_waiting(self):
        pages = messages.parse_pages(self.messages[0x109D]['body'])
        self.assertEqual(pages[0]['advance'], 'delay')
        self.assertEqual(pages[-1]['advance'], 'fade')
        self.assertEqual(pages[-1]['delay'], 70)

    def test_the_deku_tree_speech_colours_the_names(self):
        page = messages.parse_pages(self.messages[0x109A]['body'])[0]
        self.assertEqual(page['lines'][0]['runs'],
                         [('Oh, ', 'WHITE'), ('Navi the fairy', 'BLUE'),
                          ('...', 'WHITE')])

    def test_the_speech_runs_to_all_ten_of_its_pages(self):
        pages = messages.parse_pages(self.messages[0x109A]['body'])
        self.assertEqual(len(pages), 10)
        self.assertIn('I do not have much time left',
                      ' '.join(messages.plain(pages[-2]) +
                               messages.plain(pages[-1])))

    def test_navi_wakes_link_in_her_own_colour(self):
        page = messages.parse_pages(self.messages[0x1000]['body'])[0]
        self.assertEqual(page['lines'][0]['runs'],
                         [('You finally woke up!', 'BLUE')])

    def test_the_whole_table_parses_without_raising(self):
        for text_id, message in self.messages.items():
            messages.parse_pages(message['body'])

    def test_no_parsed_line_carries_a_control_macro(self):
        """A macro leaking into the text would be printed literally."""
        for text_id, message in self.messages.items():
            for page in messages.parse_pages(message['body']):
                for line in messages.plain(page):
                    for macro in ('COLOR(', 'SHIFT(', 'BOX_BREAK', 'FADE('):
                        self.assertNotIn(macro, line, '0x%04X' % text_id)


if __name__ == '__main__':
    unittest.main()
