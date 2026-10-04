"""Production cutscene lifecycle loads character sprites and retains bank slots."""
from pathlib import Path
import unittest
from test_graphics_backend import GraphicsBackend, function

ROOT = Path(__file__).resolve().parents[1]


class SpriteCast(unittest.TestCase):
    run_c = GraphicsBackend.run_c

    def test_no_character_mesh_load_and_no_visibility_reuploads(self):
        source = ROOT / 'src/cutscene_actor.c'
        self.run_c(r'''
#include <stdbool.h>
#include <stdint.h>
#include <assert.h>
#include <string.h>
#define CUTSCENE_ACTOR_COUNT 8
#define CUTSCENE_ACTOR_BRIDGE 5
#define CUTSCENE_ACTOR_GATE_FIRE 7
typedef struct { struct { int nbPoint,nbPolygon; } pdata; } cutscene_actor_t;
typedef struct { int slot; } npc_sprite_inst_t;
static const char *ACTOR_FILES[8]={"GANON.SPR","ZELDA.SPR","IMPA.SPR","HZELDA.SPR","HGANON.SPR","BRIDGE.BIN","CHAINS.BIN","GATEFIRE.BIN"};
static cutscene_actor_t actors[8];
static unsigned char sheets[5],live[5],*actor_sprites[5];
static npc_sprite_inst_t actor_sprite_inst[5];
static bool actors_ready;
static unsigned resident_mask,resident_generation,generation=1;
static unsigned reads,mesh_reads,resets,uploads,frees,errors;
static int hidden,fail;
static void asset_loading(const char *name) {}
static unsigned char *npc_sprite_load(const char *name) {
    unsigned i=reads++%5;
    assert(strstr(name,".SPR") && !live[i]); live[i]=1; return &sheets[i];
}
static bool load_actor(cutscene_actor_t *actor,const char *name,bool animated) {
    assert(!animated && strstr(name,".BIN")); ++mesh_reads;
    actor->pdata.nbPoint=4; actor->pdata.nbPolygon=32; return true;
}
static void free_actor(cutscene_actor_t *actor) {}
static void jo_free(void *p) {
    assert(p);
    for(unsigned i=0;i<5;++i)if(p==&sheets[i]) {
        assert(live[i]);live[i]=0;++frees;return;
    }
    assert(0);
}
static bool cutscene_hides_scene(void) { return hidden; }
static unsigned kokiri_actor_bank_generation(void) { return generation; }
static void kokiri_cutscene_tiles_reset(void) { ++resets; }
static bool npc_sprite_upload(const unsigned char *p,npc_sprite_inst_t *inst) { ++uploads;return !fail; }
static bool upload_actor(cutscene_actor_t *actor) { ++uploads;return !fail; }
static void jo_core_error(const char *f,...) { ++errors; }
void cutscene_actors_free(void);
''' + function(source, 'bool cutscene_actors_load(')
            + function(source, 'void cutscene_actors_free(')
            + function(source, 'void cutscene_actors_prepare(') + r'''
int main(void) {
    cutscene_actors_free(); cutscene_actors_free(); assert(frees==0);
    assert(cutscene_actors_load()); assert(reads==5 && mesh_reads==3);
    assert(cutscene_actors_load()); assert(reads==5);
    cutscene_actors_prepare(); assert(resets==1 && uploads==8);
    for(int i=0;i<100;++i)cutscene_actors_prepare();
    assert(resets==1 && uploads==8);
    ++generation; hidden=1; cutscene_actors_prepare(); assert(resets==1);
    hidden=0; fail=1; cutscene_actors_prepare(); assert(errors==1 && resident_mask==0);
    fail=0; cutscene_actors_prepare(); assert(resets==3 && resident_mask==255);
    cutscene_actors_free(); assert(frees==5 && !actors_ready && !resident_mask);
    cutscene_actors_free(); assert(frees==5);
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
