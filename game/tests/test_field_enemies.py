"""Field source-era placement, complete audio admission and bottle rewards."""
import json
import os
from pathlib import Path
import re
import sys
import unittest

import test_graphics_backend as graphics

GAME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GAME / 'tools'))
import oot_core_import as imp
import build_action_audio as audio


class FieldEnemies(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_retail_field_layers_keep_child_and_adult_separate(self):
        root = imp.OOT_DEFAULT / 'extracted' / imp.VERSION
        folder = root / 'assets/scenes/overworld/spot00'
        room = folder / 'spot00_room_0.c'
        layers = imp.room_layers(room, room.read_text(), root)
        main = layers[0][0]
        for index, (name, present) in enumerate(layers):
            if not present:
                # Retail adult-night header is NULL: source explicitly falls
                # back to adult-day before considering the main child header.
                name = layers[2][0] if index == 3 and layers[2][1] else main
            text = (folder / (name + '.inc.c')).read_text() if name else ''
            ids = re.findall(r'\bACTOR_EN_(?:PEEHAT|ENCOUNT1|PO_FIELD|SKB)\b', text)
            if index < 2:
                self.assertEqual(ids.count('ACTOR_EN_PEEHAT'), 7)
                self.assertEqual(ids.count('ACTOR_EN_ENCOUNT1'), 1)
                self.assertNotIn('ACTOR_EN_PO_FIELD', ids)
            elif index < 4:
                self.assertEqual(ids, ['ACTOR_EN_PO_FIELD'] * 10)
            elif present:
                self.assertEqual(ids, [], f'cutscene layer {index}')

    def test_field_sound_banks_fit_and_keep_guard_bytes(self):
        reports = json.loads((GAME / 'build/generated/field_audio.json').read_text())
        header = (GAME / 'build/generated/field_audio_data.h').read_text()
        for age, report in enumerate(reports):
            blob = (GAME / 'build/cd' / report['file']).read_bytes()
            self.assertEqual(len(blob), report['bytes'])
            self.assertLessEqual(len(blob), report['area_limit'])
            body = header.split(f'field_sfx_{age}[] = {{')[1].split('};')[0]
            entries = re.findall(r'\{0x([0-9a-f]+), (\d+), (\d+), (\d+)\}', body)
            self.assertEqual(len(entries), len(report['symbols']))
            for sid, offset, length, octave in entries:
                offset, length = int(offset), int(length)
                self.assertEqual(offset % 2, 0)
                self.assertLessEqual(offset + length + 4, len(blob))
                self.assertTrue(any(blob[offset:offset + length]), sid)
                self.assertEqual(blob[offset + length:offset + length + 4], bytes(4))

    def test_channel_tail_retains_layers_and_rejects_unbounded_cycles(self):
        seq = ('.channel CHAN_A\n/* 0 */ ldlayer 0, LAYER_A\n/* 1 */ rjump CHAN_B\n'
               'CHAN_B:\n/* 2 */ ldlayer 1, LAYER_B\n/* 3 */ end\n')
        expanded = audio.channel_body(seq, 'CHAN_A')
        self.assertIn('LAYER_A', expanded)
        self.assertIn('LAYER_B', expanded)
        cycle = '.channel CHAN_A\n/* 0 */ jump CHAN_A\n'
        with self.assertRaises(audio.Unsupported):
            audio.channel_body(cycle, 'CHAN_A')
        self.assertEqual(audio.channel_body(cycle, 'CHAN_A', once=True).strip(), '')

    def test_poe_capture_only_consumes_an_existing_empty_bottle(self):
        self.run_c('#include <assert.h>\n#include "' +
                   (GAME / 'src/save_state.c').as_posix() + '"\n' + r'''
int main(void) {
    save_new_game();
    for (unsigned i=0;i<4;++i) save_state.bottle_items[i]=0xff;
    assert(!save_item_give(SAVE_ITEM_BOTTLE_POE));
    save_state.bottle_items[1]=0x14;
    assert(save_item_give(SAVE_ITEM_BOTTLE_POE));
    assert(save_state.bottle_items[1]==0x20 && save_state.bottle_items[0]==0xff);
    assert(!save_item_give(SAVE_ITEM_BOTTLE_BIG_POE));
    save_state.bottle_items[3]=0x14;
    assert(save_item_give(SAVE_ITEM_BOTTLE_BIG_POE));
    assert(save_state.bottle_items[3]==0x1e && save_state.bottle_items[1]==0x20);
    return 0;
}
''')

    def test_giant_and_larva_culling_use_scaled_bounds(self):
        self.run_c(r'''
#include <assert.h>
#include <stdint.h>
#define U16(s,o) ((unsigned)((s)[o]<<8 | (s)[(o)+1]))
static int seen_y; static unsigned seen_radius;
static int npc_sprite_in_view(int x,int y,int z,unsigned radius) {
    seen_y=y; seen_radius=radius; return 1;
}
''' + graphics.function(GAME/'src/npc_sprite.c', 'int npc_sprite_visible_scaled(') + r'''
int main(void) {
    unsigned char sheet[32]={0};
    sheet[5]=32; sheet[7]=32; sheet[14]=1; sheet[16]=1;
    assert(npc_sprite_visible_scaled(sheet,0,100,0,256,256));
    assert(seen_y==116 && seen_radius==40);
    assert(npc_sprite_visible_scaled(sheet,0,100,0,512,512));
    assert(seen_y==132 && seen_radius==72);
    assert(npc_sprite_visible_scaled(sheet,0,100,0,128,128));
    assert(seen_y==108 && seen_radius==24);
    assert(!npc_sprite_visible_scaled(sheet,0,100,0,0,256));
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
