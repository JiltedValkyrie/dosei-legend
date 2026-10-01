import pathlib
import struct
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
import build_progression_manifest as manifest


class ParserTests(unittest.TestCase):
    def test_rejects_truncated_unterminated_header(self):
        for data in (b'\x01', bytes(16)):
            with self.assertRaises(ValueError):
                list(manifest.commands(data, 3))

    def test_rejects_wrong_segment_and_truncated_list(self):
        for pointer, count in ((0x02000000, 1), (0x03000004, 2)):
            with self.assertRaises(ValueError):
                manifest.records(bytes(8), pointer, count, '>I', 3)

    def test_preserves_spawn_actor_id_flags_rotation_and_params(self):
        data = struct.pack('>BBHI', 1, 1, 0, 0x03000010) + bytes([0x14]) + bytes(7)
        data += struct.pack('>HhhhhhhH', 0xA035, 1, -2, 3, -4, -32768, 6, 0x8102)
        actor = manifest.room_records(data, {0x35: 'Example'}, {})['actors'][0]
        self.assertEqual(actor['id'], 0x35)
        self.assertEqual(actor['raw_id'], 0xA035)
        self.assertEqual(actor['rotation'], [-4, -32768, 6])
        self.assertEqual(actor['params'], 0x8102)


OOT = pathlib.Path('D:/Workspace-Claude/game-decomps/n64/oot')


@unittest.skipUnless(OOT.is_dir(), 'local original source required')
class SourceGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        names = manifest.actors.table(OOT / 'include/tables/actor_table.h', 'DEFINE_ACTOR')
        objects = manifest.actors.table(OOT / 'include/tables/object_table.h', 'DEFINE_OBJECT')
        entrances = manifest.scenes.entrance_table(OOT)
        cls.graph = {p: manifest.scene_manifest(p, manifest.scenes.source.extract(OOT, prefix=p),
                     names, objects, entrances) for p in manifest.SPECS}

    def test_field_source_graph_preserves_return_and_all_owls(self):
        names=manifest.actors.table(OOT/'include/tables/actor_table.h','DEFINE_ACTOR')
        objects=manifest.actors.table(OOT/'include/tables/object_table.h','DEFINE_OBJECT')
        field=manifest.scene_manifest('spot00',manifest.scenes.source.extract(OOT,prefix='spot00'),
            names,objects,manifest.scenes.entrance_table(OOT),('SCENE_HYRULE_FIELD',1))
        self.assertEqual(field['collision']['triangles'],1579)
        self.assertEqual(len(field['rooms']),1)
        self.assertEqual(len(field['exits']),15)
        return_exit=next(e for e in field['exits'] if e['scene']=='SCENE_LOST_WOODS')
        self.assertEqual((return_exit['slot'],return_exit['spawn']),(4,8))
        owls=[a for a in field['rooms'][0]['actors'] if a['name']=='En_Owl']
        self.assertEqual([a['params'] for a in owls],[0x4c,0xff,0x13f,0x14b])
        self.assertEqual(owls[0]['position'],[4284,182,7877])
        self.assertNotIn('spot00',manifest.SPECS) # audit must not alter existing bake selection

    def test_all_rooms_and_upper_room_ids(self):
        self.assertEqual([len(self.graph[p]['rooms']) for p in manifest.SPECS], [12, 2, 10])
        self.assertEqual(self.graph['ydan']['rooms'][-1]['id'], 11)

    def test_boss_spawn_is_room_one_not_zero(self):
        self.assertEqual(self.graph['ydan_boss']['spawns'][0]['room'], 1)
        self.assertEqual(self.graph['ydan']['spawns'][1]['room'], 9)

    def test_dungeon_shutters_are_not_tunnels(self):
        transitions = self.graph['ydan']['transitions']
        self.assertEqual(sum(t['actor'] == 'Door_Shutter' for t in transitions), 9)
        self.assertEqual([t['kind'] for t in transitions if t['actor'] == 'En_Holl'], [2, 2, 4])

    def test_child_woods_has_no_mido_and_preserves_wrong_exits(self):
        woods = self.graph['spot10']
        self.assertFalse(any(a['name'] == 'En_Md' for r in woods['rooms'] for a in r['actors']))
        self.assertEqual(woods['spawns'][9]['room'], 5)
        self.assertEqual([e['spawn'] for e in woods['exits'] if e['scene'] == 'SCENE_LOST_WOODS'], [0, 2, 3, 4])
        self.assertTrue(any(e['scene'] == 'SCENE_SACRED_FOREST_MEADOW' for e in woods['exits']))


if __name__ == '__main__':
    unittest.main()
