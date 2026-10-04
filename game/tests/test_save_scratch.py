"""Execute SH-2 save scratch branches in bounded host-mapped low RAM."""
from pathlib import Path
import unittest
import test_graphics_backend as graphics

ROOT = Path(__file__).resolve().parents[1]


class SaveScratch(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_write_summary_and_live_state_use_separate_bounded_carves(self):
        self.run_c(r'''
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#include <string.h>
#define __sh__ 1
''' + '#include "' + (ROOT / 'src/save_file.h').as_posix() + '"\n' + r'''
static union { uint32_t align;unsigned char bytes[RAM_LOW_BYTES]; } mapped;
#undef RAM_LOW
#define RAM_LOW(n) ((void *)(mapped.bytes+(n)))
''' + '#include "' + (ROOT / 'src/save_state.c').as_posix() + '"\n'
            + '#include "' + (ROOT / 'src/save_file.c').as_posix() + '"\n' + r'''
#define DEVICE 0
static bool device_ready=true;
static int last_error;
static char slot_name[SAVE_FILE_SLOTS][8]={"DOSEI0","DOSEI1","DOSEI2"};
static char slot_comment[]="DOSEI LEG";
static unsigned char expected[SAVE_FILE_BYTES],after[SAVE_FILE_BYTES];
static unsigned writes;
static int save_backup_status(void) { return 0; }
static bool jo_backup_save_file_contents(int device,char *name,char *comment,void *block,unsigned bytes) {
    save_file_summary summary;
    assert(block==RAM_LOW(RAM_LOW_SAVE_IO_OFFSET));
    assert(bytes==SAVE_FILE_BYTES && !memcmp(block,expected,bytes));
    /* Exercise nested summary work while the write buffer is still owned.
     * The production BIOS call is synchronous; distinct carves also ensure
     * no future summary refresh can destroy the packed input mid-write. */
    assert(save_file_read_summary(&summary,block,bytes)==SAVE_FILE_OK);
    assert(summary.present && summary.hearts==20 && summary.rupees==500 && summary.has_emerald);
    assert(!memcmp(block,expected,bytes));
    ++writes;return true;
}
''' + graphics.function(ROOT / 'src/save_device.c', 'bool                save_device_write(') + r'''
int main(void) {
    save_file_summary summary;
    assert(RAM_LOW_SAVE_OFFSET+RAM_LOW_SAVE_BYTES<=RAM_LOW_SAVE_IO_OFFSET);
    assert(RAM_LOW_SAVE_IO_OFFSET+RAM_LOW_SAVE_IO_BYTES<=RAM_LOW_SAVE_SUMMARY_OFFSET);
    assert(RAM_LOW_SAVE_SUMMARY_OFFSET+RAM_LOW_SAVE_SUMMARY_BYTES<=RAM_LOW_GOMA_OFFSET);
    memset(mapped.bytes,0xa5,sizeof(mapped.bytes));
    save_new_game();save_test_max_gear();save_file_pack(&save_state,expected);
    assert(save_device_write(2) && writes==1);
    save_file_pack(&save_state,after);
    assert(!memcmp(after,expected,sizeof(after)));
    assert(mapped.bytes[RAM_LOW_SAVE_IO_OFFSET+SAVE_FILE_BYTES]==0xa5);
    assert(mapped.bytes[RAM_LOW_SAVE_SUMMARY_OFFSET+sizeof(save_state_t)]==0xa5);
    assert(mapped.bytes[RAM_LOW_SAVE_OFFSET+sizeof(save_state_t)]==0xa5);
    assert(mapped.bytes[RAM_LOW_GOMA_OFFSET]==0xa5);
    assert(save_file_read_summary(&summary,0,0)==SAVE_FILE_EMPTY && !summary.present);
    save_file_pack(&save_state,after);
    assert(!memcmp(after,expected,sizeof(after)));
    assert(!save_device_write(SAVE_FILE_SLOTS) && writes==1);
    device_ready=false;assert(!save_device_write(0) && writes==1);
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
