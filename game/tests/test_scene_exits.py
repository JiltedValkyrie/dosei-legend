"""Source scene exit lists survive import and bind before real Player runs."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from test_fx32 import ROOT, DECOMP, host_flags, compiler_env, importer
from test_graphics_backend import function


class SceneExits(unittest.TestCase):
    def test_retail_exit_lists_survive_every_registered_scene_and_layer(self):
        assets = importer.OOT_DEFAULT / 'extracted/ntsc-1.2'
        count = 0
        for name, path in importer.registered_scenes(assets):
            text = path.read_text()
            body, layers = importer.scene_exits(path, text, assets)
            generated = importer.scene_blob_source(path, assets)
            self.assertIn(body, generated, name)
            self.assertIn('oot_scene_exits, %d' % len(layers), generated, name)
            for symbol, present in layers:
                if symbol:
                    self.assertTrue(present)
                    self.assertIn('s16 ' + symbol + '[', body)
                    count += 1
        self.assertGreater(count, 100)

    def test_absent_empty_and_bad_exit_headers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'test_scene.c'
            text = ('s16 exits[2] = {\n#include "exits.inc.c"\n};\n'
                    'SceneCmd* test_AltHeaders[] = {\n#include "alt.inc.c"\n};')
            path.with_suffix('.inc.c').write_text('SCENE_CMD_EXIT_LIST(exits),')
            (root/'alt.inc.c').write_text(' NULL,\n empty,\n adult,\n')
            (root/'empty.inc.c').write_text('SCENE_CMD_END(),')
            (root/'adult.inc.c').write_text('SCENE_CMD_EXIT_LIST(exits),')
            _, layers = importer.scene_exits(path, text, root)
            self.assertEqual(layers, [('exits', True), (None, False), (None, True), ('exits', True)])
            (root/'adult.inc.c').write_text('SCENE_CMD_EXIT_LIST(missing),')
            with self.assertRaisesRegex(ValueError, 'missing exit definition'):
                importer.scene_exits(path, text, root)

    def test_live_binding_fallbacks_and_real_destinations(self):
        assets = importer.OOT_DEFAULT / 'extracted/ntsc-1.2'
        lists = []
        for scene in ('spot00', 'spot03', 'spot04'):
            path = assets / ('assets/scenes/overworld/%s/%s_scene.c' % (scene, scene))
            body, layers = importer.scene_exits(path, path.read_text(), assets)
            # Inline original numeric retail exit arrays, without scene meshes.
            body = re.sub(r'#include "([^"]+)"', lambda m: (assets/m[1]).read_text(), body)
            body = re.sub(r'\[LENGTH_\w+\]', '[]', body)
            lists.append((body, layers[0][0]))
        binding = function(ROOT/'oot-core/src/oot_core_api.cpp', 'static void load_scene_exits(')
        source = r'''
#include "oot_prelude.h"
#include "play_state.h"
#include "save.h"
#include "scene.h"
#include "oot_scene_blob.h"
#include <assert.h>
SaveContext gSaveContext;
static const OotSceneBlob* sScene;
static unsigned int sExitCount;
''' + '\n'.join(body for body, _ in lists) + binding + function(
            ROOT/'oot-core/src/oot_core_api.cpp', 'unsigned int OotCore_PlayerExitIndex(') + r'''
int main() {
    PlayState play={}; OotSceneBlob scene={}; OotSceneLayer layers[4]={};
    sScene=&scene; scene.exits=layers; scene.num_exit_layers=4;
''' + '\n'.join(f'    layers[{i}].actors={name}; layers[{i}].num_actors=sizeof({name})/sizeof(s16); layers[{i}].present=1;'
                 for i, (_, name) in enumerate(lists)) + r'''
    gSaveContext.sceneLayer=0; load_scene_exits(&play);
    bool ranch=false;
    for(int i=0;i<''' + f'sizeof({lists[0][1]})/sizeof(s16)' + r''';++i)
        ranch |= play.exitList[i]==ENTR_LON_LON_RANCH_0;
    assert(ranch);
    assert(OotCore_PlayerExitIndex(sExitCount)==sExitCount);
    assert(OotCore_PlayerExitIndex(sExitCount+1)==0);
    gSaveContext.sceneLayer=1; load_scene_exits(&play);
    bool domain=false;
    for(int i=0;i<''' + f'sizeof({lists[1][1]})/sizeof(s16)' + r''';++i)
        domain |= play.exitList[i]==ENTR_ZORAS_DOMAIN_0;
    assert(domain);
    gSaveContext.sceneLayer=SCENE_LAYER_ADULT_NIGHT; load_scene_exits(&play);
    bool bridge=false;
    for(int i=0;i<''' + f'sizeof({lists[2][1]})/sizeof(s16)' + r''';++i)
        bridge |= play.exitList[i]==ENTR_LOST_WOODS_9;
    assert(bridge); /* absent adult night falls back to adult day */
    layers[3].present=1; load_scene_exits(&play); assert(!play.exitList);
    assert(OotCore_PlayerExitIndex(1)==0);
    layers[2].present=0; layers[3].present=0; load_scene_exits(&play);
    assert(play.exitList==layers[0].actors);
    sScene=nullptr; load_scene_exits(&play); assert(!play.exitList);
}
'''
        compiler, env = compiler_env()
        with tempfile.TemporaryDirectory() as directory:
            cpp = Path(directory)/'exits.cpp'
            exe = cpp.with_suffix('')
            cpp.write_text(source)
            result = subprocess.run([compiler, *host_flags(), str(cpp), '-o', str(exe)],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(exe)], env=env, check=True)


if __name__ == '__main__': unittest.main()
