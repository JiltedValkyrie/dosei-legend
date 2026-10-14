"""Inactive area score tables release heap without invalidating music readers."""
from pathlib import Path
import re
import unittest

import test_graphics_backend as graphics


ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / 'src/music_area.c'
MUSIC = ROOT.parent / 'shared/lib/music/music.c'


class MusicAreaTrim(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_idle_trim_preserves_current_bank_and_all_switch_phases_keep_pending_tables(self):
        source = AREA.read_text()
        storage = source[source.index('static music_bank_t area_bank'):
                         source.index('static unsigned int be32')]
        phases = re.search(r'enum \{ MUSIC_IDLE[^;]+;', MUSIC.read_text()).group()
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
''' + '#include "%s"\n' % (MUSIC.parent / 'music.h').as_posix() + phases + '\n' + storage + r'''
static const music_bank_t *bank,*incoming;
static const music_bank_t *once_bank,*once_resume;
static unsigned char state;
/* music.c: a bank the player still references (current, incoming, fanfare). */
bool music_bank_referenced(const music_bank_t *candidate)
{return candidate && (candidate==bank || candidate==incoming || candidate==once_bank || candidate==once_resume);}
static music_bank_t static_bank;
static unsigned char allocation[2][128];
static bool live[2];
static unsigned frees;
static void jo_free(void *ptr) {
    assert(state==MUSIC_IDLE);
    for(unsigned k=0;k<2;++k) if(ptr==allocation[k]) {
        assert(live[k] && bank!=&area_bank[k]);
        live[k]=false;
        ++frees;
        return;
    }
    assert(0);
}
''' + graphics.function(MUSIC, 'const music_bank_t *music_current(')
            + graphics.function(MUSIC, 'bool music_busy(')
            + graphics.function(AREA, 'void music_area_trim(') + r'''
static void seed(unsigned current) {
    frees=0;
    for(unsigned k=0;k<2;++k) {
        live[k]=true;
        memset(allocation[k],0x70+k,sizeof allocation[k]);
        area_blob[k]=allocation[k];
        area_seq[k]=40+k;
        area_bank[k]=(music_bank_t){
            .pcm_file="M28.PCM", .level_file="M28.LVL",
            .pcm=(const music_pcm_t *)allocation[k],
            .triggers=(const music_trigger_t *)(allocation[k]+32),
            .trigger_count=8,.frames=120,.loop_frame=10,.voices=4,
            .sample_base=0x1000,.pcm_bytes=4096,.level_bytes=120
        };
    }
    area_slot=1;
    bank=current<2 ? &area_bank[current] : current==2 ? &static_bank : NULL;
}
static void cleared(unsigned k) {
    music_bank_t zero={0};
    assert(!area_blob[k] && area_seq[k]==0xffff && !live[k]);
    assert(!memcmp(&area_bank[k],&zero,sizeof zero));
}
int main(void) {
    for(unsigned current=0;current<4;++current) {
        seed(current);
        state=MUSIC_IDLE;incoming=NULL;
        music_bank_t old[2];memcpy(old,area_bank,sizeof old);
        music_area_trim();
        assert(area_slot==1 && frees==(current<2 ? 1u : 2u));
        for(unsigned k=0;k<2;++k) {
            if(current==k) {
                assert(live[k] && area_blob[k]==allocation[k] && area_seq[k]==40+k);
                assert(!memcmp(&old[k],&area_bank[k],sizeof old[k]));
                assert(((const unsigned char *)music_current()->triggers)[0]==0x70+k);
            } else cleared(k);
        }
        unsigned once=frees;
        music_area_trim();music_area_trim();
        assert(frees==once); /* cleared slots never free twice */
        bank=&static_bank;
        music_area_trim();
        cleared(0);cleared(1);assert(frees==2);
    }
    /* Both outgoing and incoming tables remain referenced through the actual
     * fade-out, streaming swap and fade-in states exposed by music_busy(). */
    unsigned phases[]={MUSIC_FADE_OUT,MUSIC_SWAP,MUSIC_FADE_IN};
    for(unsigned phase=0;phase<3;++phase) for(unsigned current=0;current<4;++current)
        for(unsigned next=0;next<2;++next) {
            seed(current);state=phases[phase];incoming=&area_bank[next];
            music_bank_t old[2];memcpy(old,area_bank,sizeof old);
            music_area_trim();music_area_trim();
            assert(!frees && area_slot==1);
            for(unsigned k=0;k<2;++k) {
                assert(live[k] && area_blob[k]==allocation[k] && area_seq[k]==40+k);
                assert(!memcmp(&old[k],&area_bank[k],sizeof old[k]));
            }
            assert(((const unsigned char *)incoming->triggers)[0]==0x70+next);
        }
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
