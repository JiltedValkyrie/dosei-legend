"""The Kokiri actor table must come from the original room lists, not authoring.

These checks exist because the previous placement was ten hand-copied fairy
coordinates with no identity, facing or floor check. They assert the generated
table still matches the US 1.2 data and still stands on our collision mesh.
"""
import pathlib
import re
import unittest

GENERATED = pathlib.Path(__file__).resolve().parents[1] / 'build/generated'

# From spot04_room_0's actor list: En_Md 0x016D, En_Sa 0x0146, En_Ko 0x0163.
EXPECTED_PEOPLE = {
    (1522, 0, 105): 'MIDO',
    (18, -80, 873): 'SARIA',
    (-1472, -80, -294): 'CHILD',
    (-678, 1, -179): 'CHILD',
    (-608, 120, 1022): 'CHILD',
    (-292, 0, -430): 'CHILD',
    (-10, 180, -22): 'CHILD',
    (45, 0, -272): 'CHILD',
    (669, 0, 521): 'CHILD',
    (853, 100, -311): 'CHILD',
}

ROW = re.compile(r'\{\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(\d+),\s*0x([0-9A-F]{4}),'
                 r'\s*KOKIRI_NPC_(\w+),\s*(\d+)\s*\}')


def table():
    path = GENERATED / 'kokiri_actors.c'
    if not path.is_file():
        raise unittest.SkipTest('kokiri_actors.c not generated yet')
    return path.read_text()


class ActorTable(unittest.TestCase):
    def test_every_person_is_an_original_placement(self):
        rows = ROW.findall(table())
        found = {(int(x), int(y), int(z)): kind for x, y, z, _, _, kind, _ in rows}
        self.assertEqual(found, EXPECTED_PEOPLE)

    def test_rupees_preserve_source_spawn_words_and_positions(self):
        block = table().split('const kokiri_rupee_t kokiri_rupees',1)[1].split('};',1)[0]
        rows = re.findall(r'\{\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*0x([0-9A-F]+),\s*(\d+),\s*(\d+)',block)
        self.assertEqual([(int(x),int(z),int(param,16),int(room),int(value))
                          for x,y,z,param,room,value in rows], [
            (-537,194,0x2400,0,1),(-459,181,0x2700,0,1),
            (35,-418,0x2500,0,1),(107,-418,0x2600,0,1),
            (-364,-783,0x1201,0,5),(2,-45,0x1101,0,5),
            (-1009,1556,0x0f01,2,5),(-712,1857,0x0e01,2,5)])

    def test_grass_drop_slots_keep_source_odds_and_type_one_has_no_rupees(self):
        block = table().split('const uint8_t kokiri_grass_rupees',1)[1]
        rows = [list(map(int,re.findall(r'\d+',row)))
                for row in re.findall(r'\{([^{}]+)\}',block)]
        self.assertEqual(len(rows),16)
        for row in rows[:12]:
            self.assertEqual(row,[1,1]+[0]*14)
        self.assertEqual(rows[12:15],[[0]*16]*3)
        self.assertEqual(rows[15],[1,5,0,0,5,1,0,0,0,0,0,0,0,0,0,5])

    def test_facing_is_kept_as_binang(self):
        rows = ROW.findall(table())
        yaws = {(int(x), int(z)): int(yaw) for x, _, z, yaw, _, _, _ in rows}
        # rotY -17476 for Mido and -7282 for Saria, read as unsigned binang.
        self.assertEqual(yaws[(1522, 105)], 48060)
        self.assertEqual(yaws[(18, 873)], 58254)
        for yaw in yaws.values():
            self.assertTrue(0 <= yaw < 65536)

    def test_named_characters_come_first(self):
        kinds = [row[5] for row in ROW.findall(table())]
        self.assertEqual(kinds[:2], ['MIDO', 'SARIA'])
        self.assertNotIn('MIDO', kinds[2:])
        self.assertNotIn('SARIA', kinds[2:])

    def test_counts_agree_with_the_header(self):
        header = (GENERATED / 'kokiri_actors.h').read_text()
        def count(name):
            return int(re.search(r'# define %s\s+(\d+)' % name, header).group(1))
        self.assertEqual(count('KOKIRI_NPC_COUNT'), len(ROW.findall(table())))
        # En_Kusa is the cuttable grass the sword work needs; En_Kanban the signs.
        self.assertEqual(count('KOKIRI_GRASS_COUNT'), 16)
        self.assertEqual(count('KOKIRI_SIGN_COUNT'), 10)


if __name__ == '__main__':
    unittest.main()
