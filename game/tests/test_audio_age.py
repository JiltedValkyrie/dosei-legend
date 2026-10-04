"""Age-bank selection and failure behavior without sound hardware."""
from pathlib import Path
import unittest
import test_graphics_backend as graphics

ROOT=Path(__file__).resolve().parents[1]
class AudioAge(unittest.TestCase):
    run_c=graphics.GraphicsBackend.run_c
    def test_scene_age_and_cutscene_restore_select_recordings(self):
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <string.h>
#define SFX_BANK_COUNT 4
#define ACTION_PCM_BYTES 100
#define OPENING_PCM_BYTES 80
static bool opening_bank,ready=true,area_ready=true,fail;
static unsigned action_age=1,area_bank=1,loads,areas,rupee_active,navi_flying;
static struct { unsigned link_age; } save_state={1};
static unsigned slots[32][32];
#define SLOT(s,o) slots[s][o]
static const char *last;
static bool load_pcm(const char *name,unsigned bytes) {
    ++loads;last=name;ready=false;area_ready=false;
    assert(bytes==(!strcmp(name,"OPENING.PCM")?80:100));
    if(fail)return false;
    ready=true;return true;
}
static bool load_area(void) {++areas;area_ready=true;return true;}
''' + graphics.function(ROOT/'src/action_audio.c','bool action_audio_set_area(')
    + graphics.function(ROOT/'src/action_audio.c','bool action_audio_set_opening(') + r'''
int main(void) {
    assert(action_audio_set_area(1) && !loads);
    save_state.link_age=0;
    assert(action_audio_set_area(1) && loads==1 && areas==1 && !strcmp(last,"ADULTACT.PCM"));
    assert(action_audio_set_area(1) && loads==1);
    assert(action_audio_set_opening(true) && !strcmp(last,"OPENING.PCM"));
    assert(action_audio_set_opening(false) && !strcmp(last,"ADULTACT.PCM"));
    save_state.link_age=1;
    assert(action_audio_set_area(1) && !strcmp(last,"ACTIONS.PCM"));
    save_state.link_age=0;fail=true;
    assert(!action_audio_set_area(1) && !ready && action_age==1);
    fail=false;
    assert(action_audio_set_area(1) && ready && action_age==0);
    save_state.link_age=1;
    assert(action_audio_set_opening(false) && !strcmp(last,"ACTIONS.PCM"));
    unsigned before=loads;
    assert(!action_audio_set_area(4) && loads==before);
    return 0;
}
''')
if __name__=='__main__':
    unittest.main()
