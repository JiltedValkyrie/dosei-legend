"""Exercise the target save carve with nonzero boot RAM and guard bytes."""
from pathlib import Path
import unittest

import test_graphics_backend as graphics

ROOT = Path(__file__).resolve().parents[1]


class SaveLowRam(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_target_save_initializes_and_stays_inside_its_carve(self):
        self.run_c(r'''
#include <assert.h>
#include <string.h>
''' + '#include "' + (ROOT / 'src/ram_low.h').as_posix() + '"\n' + r'''
static unsigned int low[RAM_LOW_BYTES / sizeof(unsigned int)];
#undef RAM_LOW
#define RAM_LOW(offset) ((void *)((unsigned char *)low + (offset)))
#define __sh__ 1
''' + '#include "' + (ROOT / 'src/save_state.c').as_posix() + '"\n' + r'''
int main(void) {
    unsigned i;
    unsigned char *bytes = (unsigned char *)low;
    memset(low, 0xa5, sizeof(low));
    save_new_game();
    assert((void *)&save_state == RAM_LOW(RAM_LOW_SAVE_OFFSET));
    assert(save_state.health == 48 && save_state.quest_items == 0);
    assert(save_state.source_items[23] == 0xff);
    assert(save_state.generic_scene[123].chest == 0);
    save_test_max_gear();
    assert(save_state.health == 320 && save_state.quest_items == 0xffffff);
    save_state.generic_scene[123].chest = 0x80000000u;
    save_new_game();
    assert(save_state.generic_scene[123].chest == 0);
    assert(save_skull_count() == 0 && save_state.source_tokens == 0);
    for (i = 0; i < RAM_LOW_SAVE_OFFSET; ++i) assert(bytes[i] == 0xa5);
    for (i = RAM_LOW_SAVE_OFFSET + sizeof(save_state_t); i < sizeof(low); ++i)
        assert(bytes[i] == 0xa5);
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
