"""Debug entry provenance must not change the async guard or enter the core."""
import unittest
import test_graphics_backend as graphics
from test_graphics_backend import ROOT, function


class AsyncEntrySite(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_busy_entry_site_and_interval_reset_in_debug_and_clean(self):
        path = ROOT / 'src/oot_core_host.c'
        source = path.read_text()
        begin = source.index('static unsigned int async_violations;')
        end = source.index('#define ASYNC_BUSY()', begin)
        checked = source[begin:end]
        getter = function(path, 'unsigned int oot_core_async_violation_line(void)')
        stats = function(path, 'void oot_core_async_stats(unsigned int out[5])')
        for clean in (False, True):
            with self.subTest(clean=clean):
                self.run_c(('#define DOSEI_CLEAN_TEST 1\n' if clean else '') + r'''
#include <stdint.h>
#include <assert.h>
typedef struct { unsigned marker; } OotCoreEntry;
static const OotCoreEntry core = { 123 };
#define ENTRY_RAW (&core)
static unsigned char async_busy, uncached_async_busy;
#define UNCACHED(v) uncached_##v
static unsigned async_updates=2, async_overlap_us=3, async_join_us=4;
''' + checked + getter + stats + r'''
int main(void) {
    unsigned out[5];
    /* Cached busy must not control either count or provenance. */
    async_busy=1; uncached_async_busy=0;
    assert(ENTRY == &core);
    assert(async_violations==0 && oot_core_async_violation_line()==0);
    async_busy=0; uncached_async_busy=1;
#line 701
    assert(ENTRY == &core);
    assert(async_violations==1);
#ifndef DOSEI_CLEAN_TEST
    assert(oot_core_async_violation_line()==701);
#else
    assert(oot_core_async_violation_line()==0);
#endif
    /* Getter itself is read-only even while the core is running. */
    for(unsigned i=0;i<100;++i) (void)oot_core_async_violation_line();
    assert(async_violations==1);
#line 819
    assert(ENTRY == &core);
    assert(async_violations==2);
#ifndef DOSEI_CLEAN_TEST
    assert(oot_core_async_violation_line()==819);
#endif
    uncached_async_busy=0;
    assert(ENTRY == &core);
    assert(async_violations==2);
    oot_core_async_stats(out);
    assert(out[0]==2 && out[1]==3 && out[2]==4 && out[3]==2 && out[4]==0);
    assert(async_violations==0 && oot_core_async_violation_line()==0);
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
