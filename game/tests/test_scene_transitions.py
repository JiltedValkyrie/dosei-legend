"""Preserve retail transition indices and execute source room-side spawning."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_fx32 import ROOT, DECOMP, host_flags, compiler_env, importer
from test_graphics_backend import function


@unittest.skipUnless(importer.OOT_DEFAULT.exists(), 'local retail assets required')
class TransitionImport(unittest.TestCase):
    def test_water_keeps_all_original_room_sides_and_door_indices(self):
        assets = importer.OOT_DEFAULT / 'extracted/ntsc-1.2'
        path = assets / 'assets/scenes/dungeons/MIZUsin/MIZUsin_scene.c'
        text = path.read_text()
        body, layers = importer.scene_transitions(path, text, assets)
        self.assertEqual(layers, [('MIZUsin_scene_02000078_TransitionActorEntryList', True)])
        self.assertIn('TransitionActorEntry MIZUsin_scene_02000078_TransitionActorEntryList', body)
        self.assertIn('MIZUsin_scene_02000078_TransitionActorEntryList.inc.c', body)
        source = importer.scene_blob_source(path, assets)
        self.assertIn('OOT_SCENE_BLOB_FORMAT, oot_scene_transitions, 1', source)
        self.assertIn(body, source)

    def test_absent_and_empty_headers_stay_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root/'test_scene.c'
            text = ('TransitionActorEntry doors[2] = {\n#include "doors.inc.c"\n};\n'
                    'SceneCmd* test_AltHeaders[] = {\n#include "alt.inc.c"\n};')
            path.with_suffix('.inc.c').write_text('SCENE_CMD_TRANSITION_ACTOR_LIST(ARRAY_COUNT(doors), doors),')
            (root/'alt.inc.c').write_text(' NULL,\n empty,\n adult,\n')
            (root/'empty.inc.c').write_text('SCENE_CMD_END(),')
            (root/'adult.inc.c').write_text('SCENE_CMD_TRANSITION_ACTOR_LIST(ARRAY_COUNT(doors), doors),')
            _, layers = importer.scene_transitions(path, text, root)
            self.assertEqual(layers, [('doors', True), (None, False), (None, True), ('doors', True)])
            (root/'adult.inc.c').write_text('SCENE_CMD_TRANSITION_ACTOR_LIST(1, missing),')
            with self.assertRaisesRegex(ValueError, 'missing transition definition'):
                importer.scene_transitions(path, text, root)


@unittest.skipUnless((DECOMP/'include/ultra64.h').exists() and importer.OOT_DEFAULT.exists(),
                     'local source import required')
class TransitionActions(unittest.TestCase):
    def test_source_spawns_adjacent_rooms_once_and_preserves_parameter_indices(self):
        actor = function(DECOMP/'src/code/z_actor.cpp', 'void Actor_SpawnTransitionActors(')
        bind = function(ROOT/'oot-core/src/oot_core_api.cpp', 'static void load_transition_actors(')
        source = r'''
#include "oot_prelude.h"
#include "play_state.h"
#include "scene.h"
#include "save.h"
#include "z_actor_dlftbls.h"
#include "oot_scene_blob.h"
extern "C" int printf(const char*, ...);
#define CHECK(x) do { if (!(x)) { printf("line %d: %s\n",__LINE__,#x); return 1; } } while(0)
SaveContext gSaveContext;
ActorOverlay gActorOverlayTable[ACTOR_ID_MAX];
static const OotSceneBlob* sScene;
static PlayState play;
static Actor spawned;
static int spawnCount, lastId, lastParams;
Actor* Actor_Spawn(ActorContext*, PlayState*, s16 id, f32, f32, f32, s16, s16, s16, s16 params) {
    ++spawnCount; lastId=id; lastParams=params; return &spawned;
}
/* Scene-pack admission (bridge_actor_pack.cpp): no pack admits doors here; only
 * the Water Temple (exempt) takes source transitions. */
static int OotCore_PackAdmits(int) { return 0; }
''' + actor + '\n' + bind + r'''
int main() {
    TransitionActorEntry entries[3]={};
    for(int i=0;i<3;++i) {
        entries[i].id=ACTOR_DOOR_SHUTTER;
        entries[i].sides[0].room=i;
        entries[i].sides[1].room=i+1;
        entries[i].params=0x42+i;
    }
    OotSceneLayer layers[4]={};
    layers[0].actors=entries; layers[0].num_actors=3; layers[0].present=1;
    layers[2]=layers[0]; layers[1].present=1; /* child night explicitly empty */
    OotSceneBlob scene={}; scene.transitions=layers; scene.num_transition_layers=4;
    sScene=&scene; play.sceneId=SCENE_WATER_TEMPLE;
    gSaveContext.sceneLayer=SCENE_LAYER_ADULT_NIGHT;
    load_transition_actors(&play);
    CHECK(!play.transitionActors.count && entries[0].id>0); /* missing profile cannot consume a door */
    ActorProfile profile={}; gActorOverlayTable[ACTOR_DOOR_SHUTTER].profile=&profile;
    load_transition_actors(&play);
    CHECK(play.transitionActors.list==entries && play.transitionActors.count==3);
    play.roomCtx.curRoom.num=0; play.roomCtx.prevRoom.num=-1;
    Actor_SpawnTransitionActors(&play,&play.actorCtx);
    CHECK(spawnCount==1 && lastId==ACTOR_DOOR_SHUTTER && lastParams==0x42 && entries[0].id<0);
    Actor_SpawnTransitionActors(&play,&play.actorCtx); CHECK(spawnCount==1);
    play.roomCtx.curRoom.num=2; play.roomCtx.prevRoom.num=1;
    Actor_SpawnTransitionActors(&play,&play.actorCtx);
    CHECK(spawnCount==3 && lastParams==((2<<TRANSITION_ACTOR_PARAMS_INDEX_SHIFT)+0x44));
    gSaveContext.sceneLayer=SCENE_LAYER_CHILD_NIGHT;
    load_transition_actors(&play); CHECK(!play.transitionActors.count);
    play.sceneId=SCENE_HYRULE_FIELD; gSaveContext.sceneLayer=0;
    load_transition_actors(&play); CHECK(!play.transitionActors.count);
    return 0;
}
'''
        compiler, env = compiler_env()
        with tempfile.TemporaryDirectory() as directory:
            cpp = Path(directory)/'transitions.cpp'
            exe = cpp.with_suffix('')
            cpp.write_text(source)
            result = subprocess.run([compiler, *host_flags(), str(cpp), '-o', str(exe)],
                                    env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(exe)], env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)


if __name__ == '__main__': unittest.main()
