"""Z + A evade/jump slash is refused only in ROOM_TYPE_INDOORS scenes.

Source: Player_ActionHandler_10 (z_player.c) checks curRoom.type !=
ROOM_TYPE_INDOORS. ntsc-1.2 marks the Kokiri shop and the five Kokiri houses
indoors; the forest, Lost Woods, Hyrule Field, Deku Tree (DUNGEON) and Gohma's
room (BOSS) are not.
"""
import ctypes, os, pathlib, subprocess, tempfile, unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')


@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class SceneRoomType(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        c = pathlib.Path(cls.tmp.name) / 'room.c'
        c.write_text('#include "scene_room_type.h"\n'
                     'int indoors(unsigned s) { return scene_room_indoors(s); }\n')
        dll = c.with_suffix('.dll')
        env = dict(os.environ, PATH=str(GCC.parent) + os.pathsep + os.environ.get('PATH', ''))
        subprocess.run([str(GCC), '-shared', '-O2', '-I' + str(ROOT / 'src'),
                        str(c), '-o', str(dll)], check=True, env=env)
        cls.lib = ctypes.CDLL(str(dll))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_outdoor_and_dungeon_scenes_allow_evades(self):
        for scene in (0, 1, 2, 3, 10):     # forest, woods, tree, Gohma, field
            self.assertFalse(self.lib.indoors(scene), scene)

    def test_houses_and_shop_block_evades(self):
        for scene in (4, 5, 6, 7, 8, 9):
            self.assertTrue(self.lib.indoors(scene), scene)

    def test_demo_gates_evade_on_room_type_not_forest(self):
        text = (ROOT / 'src/demo.c').read_text()
        self.assertIn('!scene_room_indoors(save_state.scene_id) && evade_floor_ok()', text)
        self.assertNotIn('save_state.scene_id == SAVE_SCENE_KOKIRI_FOREST && evade_floor_ok()', text)


if __name__ == '__main__':
    unittest.main()
