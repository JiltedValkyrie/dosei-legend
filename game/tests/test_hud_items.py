"""Render real source inventory icons through the production C HUD composer."""
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import unittest

import test_graphics_backend as graphics

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(os.environ.get('DOSEI_HUD_ASSETS', ROOT / 'build'))
CD = ASSETS / 'cd'
GENERATED = ASSETS / 'generated'


def defines(path):
    return {key: int(value) for key, value in
            re.findall(r'#define (\w+) (\d+)u?\b', path.read_text())}


@unittest.skipUnless((CD / 'PAUSEINV.BIN').exists(), 'baked source icon atlas required')
class HudItems(unittest.TestCase):
    def test_every_inventory_slot_and_bottle_change_draws_actual_item(self):
        defs = defines(GENERATED / 'gameplay_hud_data.h')
        icondefs = defines(GENERATED / 'pause_inventory_data.h')
        header = (GENERATED / 'gameplay_hud_data.h').read_text()
        palette = [int(x) for x in re.search(r'hud_palette\[16\] = \{([^}]+)', header)[1].split(',')]
        buttons = (CD / 'BUTTONS.BIN').read_bytes()
        names = list(struct.unpack('>%dH' % ((CD / 'BUTTONS.MAP').stat().st_size // 2),
                                   (CD / 'BUTTONS.MAP').read_bytes()))
        icons = (CD / 'PAUSEINV.BIN').read_bytes()
        self.assertLessEqual(len(names) * 2, 0x3800)
        self.assertLessEqual(0x12000 + len(icons), 0x20000)
        source = r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#ifdef _WIN32
#include <io.h>
#include <fcntl.h>
#endif
#define assert(c) do { if(!(c)) { fprintf(stderr,"line %d: %s\n",__LINE__,#c); exit(1); } } while(0)
''' + '\n'.join('#include "' + str(p.as_posix()) + '"' for p in (
            ROOT / 'src/save_state.h', GENERATED / 'gameplay_hud_data.h',
            GENERATED / 'pause_inventory_data.h')) + r'''
static unsigned short ram[0x10000];
#define MINIMAP_VRAM_MAP ((uintptr_t)ram)
#define MINIMAP_VRAM_CELLS ((uintptr_t)ram+0x2000u)
#define HUD_VRAM_CELLS ((uintptr_t)ram+0x4000u)
#define HUD_NAMES (ram+0x8000u/2)
#define HUD_ITEM_CELLS (ram+0xB800u/2)
#define HUD_ITEM_BANK_WORDS 1024u
#define HUD_ICON_ATLAS (ram+0x12000u/2)
static uint32_t hud_items_key=~0u,hud_actions_key=~0u;
static unsigned hud_item_front;
static unsigned short cram_ram[2048];
#define JO_VDP2_CRAM ((uintptr_t)cram_ram)
static unsigned char hud_item_palette[2][HUD_ITEM_COUNT];
static int hud_variant=-1;
static bool overhead, first_person, interior;
static bool player_camera_orbit_active(void) { return overhead; }
static bool recomp_first_person(void) { return first_person; }
static bool scene_flow_is_interior(void) { return interior; }
save_state_t save_state;
static bool jo_is_pad1_available(void) { return true; }
static bool jo_is_input_analog(int pad) { return false; }
static unsigned ui_labels(void) { return 0; }
''' + '\n'.join(graphics.function(ROOT / 'src/save_state.c', marker) for marker in (
            'unsigned save_inventory_item(', 'unsigned save_c_item_for_slot(',
            'bool save_inventory_slot_usable(', 'unsigned save_c_item_inventory_slot(')) + '\n' + '\n'.join(
            graphics.function(ROOT / 'src/minimap.c', marker) + suffix for marker, suffix in (
                ('static unsigned hud_icon_colour(', ''), ('static void hud_item_pixel(', ''),
                ('static const unsigned char hud_item_at', ';'),
                ('typedef struct {\n    const volatile', ' hud_item_art_t;'),
                ('static unsigned hud_source_index(', ''), ('static unsigned hud_item_rgb(', ''),
                ('static unsigned hud_rgb_distance(', ''), ('static unsigned hud_overlap(', ''),
                ('static void hud_items_compose(', ''), ('static void hud_visibility(', ''))) + '\n'
        source += 'static const unsigned short button_data[]={' + ','.join(
            map(str, struct.unpack('>%dH' % (len(buttons) // 2), buttons))) + '};\n'
        source += 'static const unsigned short name_data[]={' + ','.join(map(str, names)) + '};\n'
        source += 'static const unsigned char icon_data[]={' + ','.join(map(str, icons)) + '};\n'
        items = [0, 1, 2, 3, 4, 5, 6, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19,
                 20, 21, 22, 23, 55, 43]
        source += 'static const unsigned char inventory[24]={' + ','.join(map(str, items)) + '};\n'
        source += r'''
static void dump(void) {
    volatile unsigned short *cells=HUD_ITEM_CELLS+hud_item_front*2u*HUD_ITEM_BANK_WORDS;
    fwrite((const void *)cells,sizeof(short),HUD_ITEM_COUNT*16,stdout);
    fwrite((const void *)(cells+HUD_ITEM_BANK_WORDS),sizeof(short),HUD_ITEM_COUNT*16,stdout);
    fwrite(hud_item_palette[hud_item_front],1,HUD_ITEM_COUNT,stdout);
    fwrite(cram_ram+768,sizeof(short),256,stdout);
}
int main(void) {
#ifdef _WIN32
    _setmode(_fileno(stdout),_O_BINARY);
#endif
    for(unsigned i=0;i<0x10000;i++) ram[i]=0xA5A5;
    memcpy((void *)HUD_VRAM_CELLS,button_data,sizeof(button_data));
    memcpy(HUD_NAMES,name_data,sizeof(name_data));
    memcpy(HUD_ICON_ATLAS,icon_data,sizeof(icon_data));
    /* Equipped sword changes while the generic GP_SWORD bit stays set.
     * No C-item rebake or action/Navi change is needed to refresh its icon. */
    for(unsigned weapon=1;weapon<=3;weapon++) {
        save_state.equip_sword=weapon;
        hud_visibility(16);
        unsigned front=hud_item_front;
        for(unsigned i=0;i<HUD_WEAPON_COUNT;i++)
            assert(ram[hud_weapon_positions[i]]==(0x2000u|(0x4000/32+
                name_data[HUD_WEAPON_OFFSET+weapon*8*HUD_WEAPON_COUNT+i])));
        hud_visibility(17); assert(hud_item_front==front);
    }
    save_state.equip_sword=0;
    hud_visibility(0);
    for(unsigned i=0;i<HUD_WEAPON_COUNT;i++)
        assert(ram[hud_weapon_positions[i]]==(0x2000u|(0x4000/32+
            name_data[HUD_WEAPON_OFFSET+i])));
    memcpy(save_state.source_items,inventory,24);
    for(unsigned i=0;i<4;i++) save_state.bottle_items[i]=inventory[18+i];
    save_state.stick_owned=save_state.nut_owned=save_state.slingshot=save_state.fairy_ocarina=1;
    for(unsigned slot=0;slot<24;slot++) {
        if(!save_inventory_slot_usable(slot)) save_state.link_age^=1;
        save_state.c_items[0]=save_c_item_for_slot(slot);
        save_state.c_items[1]=save_state.c_items[2]=0;
        hud_visibility(0);
        unsigned front=hud_item_front;
        /* A-label and Navi changes select existing banks without composition. */
        hud_visibility(3); assert(hud_item_front==front);
        hud_visibility(0); assert(hud_item_front==front);
        unsigned base=0xB800/32+front*2*HUD_ITEM_BANK_WORDS/16;
        for(unsigned i=0;i<HUD_ITEM_COUNT;i++)
            assert(ram[hud_item_positions[i]]==((unsigned)hud_item_palette[front][i]<<12|(base+i)));
        dump();
    }
    /* Same assignment can gain a new bottle content or upgraded ocarina. */
    save_state.link_age=1;
    save_state.c_items[0]=save_c_item_for_slot(18);
    save_state.c_items[1]=4;
    save_state.c_items[2]=save_c_item_for_slot(23);
    hud_visibility(0); dump();
    unsigned previous=hud_item_front;
    save_state.bottle_items[0]=0x1A;
    save_state.source_items[7]=7;
    hud_visibility(0);
    assert(hud_item_front!=previous); dump();
    previous=hud_item_front;
    hud_visibility(0); assert(hud_item_front==previous);
    /* Same action/item key: camera changes alone must redraw and clear hints. */
    for(unsigned state=0;state<8;state++) {
        overhead=state&1; first_person=state&2; interior=state&4;
        hud_visibility(0);
        bool camera=overhead && !first_person && !interior;
        for(unsigned y=0;y<HUD_CAMERA_H;y++) for(unsigned x=0;x<HUD_CAMERA_W;x++) {
            unsigned expected=camera ? 0xB000u | (0x4000u/32u+
                HUD_CAMERA_TILE+y*HUD_CAMERA_W+x) : 0x2000u/32u;
            assert(ram[(HUD_CAMERA_Y+y)*64+HUD_CAMERA_X+x]==expected);
        }
        assert(hud_item_front==previous);
    }
    overhead=true; first_person=interior=false;
    hud_visibility(-1); assert(hud_item_front==previous);
    for(unsigned y=0;y<HUD_CAMERA_H;y++) for(unsigned x=0;x<HUD_CAMERA_W;x++)
        assert(ram[(HUD_CAMERA_Y+y)*64+HUD_CAMERA_X+x]==0x2000u/32u);
    hud_visibility(0); assert(hud_item_front==previous);
    /* Composing icons cannot touch heart banks/atlas or spill a 60-cell bank. */
    for(unsigned i=0x10000/2;i<0x12000/2;i++) assert(ram[i]==0xA5A5);
    for(unsigned b=0;b<4;b++) for(unsigned i=HUD_ITEM_COUNT*16;i<HUD_ITEM_BANK_WORDS;i++)
        assert(HUD_ITEM_CELLS[b*HUD_ITEM_BANK_WORDS+i]==0xA5A5);
}
'''
        compiler = graphics.GCC
        env = dict(os.environ)
        env['PATH'] = str(Path(compiler).parent) + os.pathsep + env.get('PATH', '')
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            (p / 'hud.c').write_text(source)
            subprocess.run([compiler, '-std=c99', '-O2', str(p / 'hud.c'), '-o', str(p / 'hud.exe')],
                           check=True, env=env)
            output = subprocess.check_output([str(p / 'hud.exe')], env=env)

        def tiled(data, cell_ids):
            pixels = [[0] * 80 for _ in range(48)]
            for cell, tile in enumerate(cell_ids):
                for pixel in range(64):
                    index = (data[tile * 32 + pixel // 2] >> (0 if pixel & 1 else 4)) & 15
                    pixels[cell // 10 * 8 + pixel // 8][cell % 10 * 8 + pixel % 8] = index
            return pixels

        blank_ids = names[defs['HUD_ITEM_OFFSET']:defs['HUD_ITEM_OFFSET'] + 60]
        blank = tiled(buttons, blank_ids)
        empty = tiled(buttons, [names[(2 + c // 10) * defs['HUD_MAP_W'] + 9 + c % 10] for c in range(60)])
        overlay = tiled(buttons, names[defs['HUD_NAVI_OFFSET']:defs['HUD_NAVI_OFFSET'] + 60])

        def rgb(index):
            return palette[index] & 0x7FFF if index else None

        def expected(assignment, navi):
            """Exact source colours (RGB555, None = transparent)."""
            pixels = [[rgb(i) for i in row] for row in empty]
            for item, (left, top) in zip(assignment, ((25, 18), (3, 2), (47, 2))):
                if item == 255:
                    continue
                off = icondefs['PAUSE_ICON_META'] + item * icondefs['PAUSE_ICON_RECORD']
                colours = struct.unpack_from('>16H', icons, off + 32)
                for y in range(26):
                    for x in range(26):
                        sample = (y * 28 // 26) * 28 + x * 28 // 26
                        index = (icons[off + 64 + sample // 2] >> (0 if sample & 1 else 4)) & 15
                        pixels[top + y][left + x] = (colours[index] & 0x7FFF if index else
                                                     rgb(blank[top + y][left + x]))
            if navi:
                pixels = [[rgb(b) if b else a for a, b in zip(row, over)] for row, over in zip(pixels, overlay)]
            return pixels

        def distance(a, b):
            return sum((((a >> s) & 31) - ((b >> s) & 31)) ** 2 for s in (0, 5, 10))

        dump = 2 * 1920 + 60 + 512
        assignments = [(item, 255, 255) for item in items] + [(20, 8, 43), (26, 7, 43)]
        self.assertEqual(len(output), len(assignments) * dump)
        exact = total = 0
        for test, assignment in enumerate(assignments):
            chunk = output[test * dump:(test + 1) * dump]
            pal = chunk[3840:3900]
            cram = struct.unpack('=256H', chunk[3900:])
            for navi in range(2):
                words = struct.unpack('=960H', chunk[navi * 1920:(navi + 1) * 1920])
                actual = tiled(struct.pack('>960H', *words), range(60))
                want = expected(assignment, navi)
                for y in range(48):
                    for x in range(80):
                        bank = pal[y // 8 * 10 + x // 8]
                        index, colour = actual[y][x], want[y][x]
                        context = (test, assignment, navi, x, y)
                        self.assertEqual(index == 0, colour is None, context)
                        if colour is None:
                            continue
                        got = palette[index] & 0x7FFF if bank == 2 else cram[bank * 16 + index]
                        entries = ([palette[i] & 0x7FFF for i in range(1, 16)] if bank == 2 else
                                   cram[bank * 16 + 1:bank * 16 + 16])
                        # Each pixel takes the closest colour its cell's palette offers.
                        self.assertEqual(distance(got, colour),
                                         min(distance(e, colour) for e in entries), context)
                        exact += got == colour
                        total += 1
        # Per-icon palettes keep the menu colours (shared palette lost most).
        self.assertGreater(exact * 100, total * 90, (exact, total))
        self.assertNotEqual(expected((8, 255, 255), 0), expected((7, 255, 255), 0))


if __name__ == '__main__':
    unittest.main()
