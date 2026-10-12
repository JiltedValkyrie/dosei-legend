"""Cold timing history retains exact averages in its bounded Low RAM carve."""
import unittest
import test_graphics_backend as graphics
from test_graphics_backend import ROOT, function


class PerfHistory(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_dirty_boot_reset_and_refresh_windows_preserve_bounds(self):
        path = ROOT/'src/main.c'
        source = path.read_text()
        begin = source.index('unsigned int perf_sub[PS_COUNT];')
        end = source.index('static void perf_sub_init(void)', begin)
        self.run_c(r'''
#include <assert.h>
#include <string.h>
#define __sh__ 1
''' + '#include "' + (ROOT/'src/perf_sub.h').as_posix() + '"\n' + r'''
static unsigned int fake_low[RAM_LOW_BYTES/4];
#undef RAM_LOW
#define RAM_LOW(off) ((void*)((unsigned char*)fake_low+(off)))
''' + source[begin:end] + function(path, 'static void perf_sub_init(void)')
            + function(path, 'void perf_sub_latch(void)')
            + function(path, 'static void perf_sub_average(void)') + r'''
int main(void) {
    memset(fake_low,0xA5,sizeof fake_low);
    memset(perf_sub,0xA5,sizeof perf_sub);
    perf_frames=perf_sum_frames=999;
    perf_sub_init();
    assert(perf_frames==0 && perf_sum_frames==0);
    for(unsigned i=0;i<PS_COUNT;++i)
        assert(!perf_sub[i] && !perf_sub_avg[i] && !perf_sub_sum[i]);
    for(unsigned window=1;window<40;++window) {
        unsigned sums[PS_COUNT]={0};
        for(unsigned frame=0;frame<window;++frame) {
            for(unsigned i=0;i<PS_COUNT;++i) {
                perf_sub[i]=(frame*733+i*23+window)%12345;
                sums[i]+=perf_sub[i];
            }
            perf_sub_latch();
            for(unsigned i=0;i<PS_COUNT;++i) {
                assert(!perf_sub[i] && perf_sub_sum[i]==sums[i]);
            }
        }
        perf_sub_average();
        for(unsigned i=0;i<PS_COUNT;++i)
            assert(perf_sub_avg[i]==sums[i]/window && !perf_sub_sum[i]);
        assert(!perf_sum_frames);
    }
    perf_sub_average(); /* Empty refresh never divides by zero. */
    for(unsigned i=0;i<PS_COUNT;++i) assert(!perf_sub_avg[i]);
    perf_sub_init(); /* A warm restart resets both banks and frame counts. */
    for(unsigned i=0;i<RAM_LOW_PERF_HISTORY_OFFSET/4;++i) assert(fake_low[i]==0xA5A5A5A5u);
    for(unsigned i=RAM_LOW_PERF_HISTORY_OFFSET/4+2*PS_COUNT;i<RAM_LOW_BYTES/4;++i)
        assert(fake_low[i]==0xA5A5A5A5u);
    assert(!perf_frames && !perf_sum_frames);
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
