"""BUG-006: execute the real traversal preflight and ledge selector."""
import ctypes
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')


@unittest.skipUnless(GCC.exists(), 'host compiler required')
class LedgeTalk(unittest.TestCase):
    def test_climb_claims_a_but_open_text_and_invalid_ledge_do_not(self):
        def extract(path, signature):
            text = path.read_text()
            start = text.index(signature)
            return text[start:text.index('\n}', start) + 2]
        preflight = extract(ROOT / 'src/recomp.c', 'static bool ledge_claims_interact(')
        selector = extract(ROOT / 'src/player_bg.c', 'player_ledge_act_t  player_ledge_action(')
        code = '''
#include "player_bg.h"
#include "link_anim_state.h"
#include "gameplay.h"
static player_bg_t link_bg;
static int blocked, link_velocity_y_q8, link_on_ground=1;
static struct { int phase; } link_water, link_lift;
gameplay_t gameplay;
link_state_t link_anim_state(void) { return LINK_STATE_WALK; }
bool gameplay_blocks_world(void) { return blocked; }
''' + selector + '\n' + preflight + '''
int claim(int height_type, int text, int grounded, int moving, int attack,
          int carrying, int dynamic, int delay) {
    gameplay_input_t action = {0};
    action.interact=true; action.moving=moving; action.attack=attack;
    blocked=text; link_on_ground=grounded; link_lift.phase=carrying;
    link_bg.ledge_type=height_type; link_bg.y_dist_to_ledge=35;
    link_bg.wall_hit.bg_id=dynamic ? 0 : BG_SCENE;
    link_bg.touched_flags=dynamic ? BG_WALL_FLAG_6 : 0;
    link_bg.delay_timer=delay;
    return ledge_claims_interact(&action);
}
'''
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            path = Path(directory)
            (path / 'test.c').write_text(code)
            env = dict(os.environ, PATH=str(GCC.parent) + os.pathsep + os.environ.get('PATH', ''))
            subprocess.run([str(GCC), '-shared', '-O2', '-I' + str(ROOT / 'src'),
                            '-I' + str(ROOT.parent / 'shared/lib/collision'),
                            str(path / 'test.c'), '-o', str(path / 'test.dll')], check=True, env=env)
            lib = ctypes.CDLL(str(path / 'test.dll'))
            self.assertEqual(lib.claim(2, 0, 1, 1, 0, 0, 0, 0), 1)
            for args in ((0, 0, 1, 1, 0, 0, 0, 0), (2, 1, 1, 1, 0, 0, 0, 0),
                         (2, 0, 0, 1, 0, 0, 0, 0), (2, 0, 1, 0, 0, 0, 0, 0),
                         (2, 0, 1, 1, 1, 0, 0, 0), (2, 0, 1, 1, 0, 1, 0, 0),
                         (2, 0, 1, 1, 0, 0, 1, 0)):
                self.assertEqual(lib.claim(*args), 0, args)
            self.assertEqual(lib.claim(2, 0, 1, 1, 0, 0, 1, 255), 1)


if __name__ == '__main__':
    unittest.main()
