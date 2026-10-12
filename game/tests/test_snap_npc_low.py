"""NPC draw snapshot lives in its bounded Low RAM carve, master-only."""
import re
import unittest
import test_graphics_backend as graphics
from test_graphics_backend import ROOT


class SnapNpcLow(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_carve_bounds_and_layout(self):
        self.run_c(r'''
#include <assert.h>
''' + '#include "' + (ROOT/'src/ram_low.h').as_posix() + '"\n' + r'''
int main(void) {
    assert(RAM_LOW_SNAP_NPC_OFFSET % 16 == 0);
    assert(RAM_LOW_PERF_HISTORY_OFFSET + RAM_LOW_PERF_HISTORY_BYTES <= RAM_LOW_SNAP_NPC_OFFSET);
    assert(RAM_LOW_SNAP_NPC_OFFSET + RAM_LOW_SNAP_NPC_BYTES <= RAM_LOW_BYTES);
    assert(RAM_LOW_USED_BYTES == RAM_LOW_SNAP_NPC_OFFSET + RAM_LOW_SNAP_NPC_BYTES);
    assert(RAM_LOW_SNAP_NPC_BYTES >= 32 * 56);
    return 0;
}
''')

    def test_only_kick_snapshot_writes_rows(self):
        source = (ROOT/'src/oot_core_host.c').read_text()
        self.assertIn('#define snap_npc ((OotCoreNpcView *)RAM_LOW(RAM_LOW_SNAP_NPC_OFFSET))', source)
        self.assertIn('sizeof(OotCoreNpcView) * SNAP_NPC_MAX', source)
        writes = re.findall(r'snap_npc\[[^\]]*\]\s*=', source)
        self.assertEqual(writes, ['snap_npc[i] ='])
        self.assertIn('for (i = 0; i < snap_npc_n; ++i) snap_npc[i] = nv[i];', source)
        self.assertIn('*out = snap_npc; return playing ? snap_npc_n : 0;', source)

    def test_view_and_tool_snapshots_share_master_only_carve(self):
        source = (ROOT/'src/oot_core_host.c').read_text()
        self.assertIn('RAM_LOW(RAM_LOW_SNAP_VIEW_OFFSET))', source)
        self.assertIn('typedef char snap_view_fits[', source)
        # Only snapshot_views (master, before the kick) writes the rows.
        self.assertEqual(re.findall(r'snap_tools\[[^\]]*\]\s*=', source), ['snap_tools[i] ='])
        self.assertEqual(source.count('ENTRY_RAW->actor_view('), 2)
        self.run_c(r'''
#include <assert.h>
''' + '#include "' + (ROOT/'src/ram_low.h').as_posix() + '"\n' + r'''
int main(void) {
    assert(RAM_LOW_FOREST_MESH_OFFSET + RAM_LOW_FOREST_MESH_BYTES <= RAM_LOW_SNAP_VIEW_OFFSET);
    assert(RAM_LOW_SNAP_VIEW_OFFSET + RAM_LOW_SNAP_VIEW_BYTES <= RAM_LOW_ROOM_OBJECTS_OFFSET);
    assert(RAM_LOW_SNAP_VIEW_BYTES >= 2 * 24 * 20 + 8 * 52);
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
