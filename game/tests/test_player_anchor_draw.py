"""Keep Player draw gameplay outputs while discarding unused N64 presentation."""
from collections import defaultdict
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_core_bgcheck import compiler_env
from test_graphics_backend import function
from test_fx32 import ROOT, host_flags, importer


class PlayerAnchorDraw(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.folder.cleanup)
        folder = Path(cls.folder.name)
        source = (ROOT / 'tests/fixtures/player_anchor_draw_host.cpp').read_text()
        original = importer.OOT_DEFAULT / 'src/code/z_actor.c'
        real = '\n'.join(function(original, name) for name in
                         ('void ActorShadow_DrawFeet(', 'void Actor_Draw('))
        real = importer.fix_float_literals(real, defaultdict(int))
        production = ROOT / 'oot-core/src/oot_core_draw.cpp'
        optimized = '\n'.join(function(production, name) for name in
                              ('static void PlayerAnchor_Feet(', 'static void PlayerAnchor_Draw('))
        source = source.replace('/* SOURCE_FUNCTIONS */', real)
        source = source.replace('/* PRODUCTION_FUNCTIONS */', optimized)
        path = folder / 'draw.cpp'
        path.write_text(source)
        cls.exe = folder / 'draw'
        compiler, cls.env = compiler_env()
        result = subprocess.run(
            [compiler, *host_flags(), '-fsanitize=undefined', '-fno-sanitize-recover=undefined',
             '-ffunction-sections', '-fdata-sections', str(path),
             str(ROOT / 'oot-core/src/oot_math.cpp'), '-Wl,--gc-sections', '-o', str(cls.exe)],
            env=cls.env, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)

    def probe(self, mode):
        result = subprocess.run([str(self.exe), mode], env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_source_feet_queries_and_contact_flags_exact(self):
        self.probe('feet')

    def test_source_actor_transform_callback_and_gameplay_outputs_exact(self):
        self.probe('wrapper')

    def test_live_player_path_uses_wrapper_and_future_shadow_types_fall_back(self):
        text = function(ROOT / 'oot-core/src/oot_core_draw.cpp', 's32 OotCore_DrawActors(')
        self.assertIn('PlayerAnchor_Draw(play, &player->actor);', text)
        source = (importer.OOT_DEFAULT / 'src/overlays/actors/ovl_player_actor/z_player.c').read_text()
        self.assertEqual(source.count('this->actor.shape.shadowDraw = NULL;'), 1)
        self.assertEqual(source.count('this->actor.shape.shadowDraw = ActorShadow_DrawFeet;'), 1)
