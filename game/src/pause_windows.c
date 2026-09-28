/* NBG2 pause windows share the HUD name table, but not its character cells.
 * One page is streamed into the reserved cart pool on a page/ownership change.
 * Cursor movement restores from that copy; it never reads the CD. */
#include <jo/jo.h>
#include "pause_windows.h"
#include "gameplay.h"
#include "save_state.h"
#include "ram_cart.h"
#include "pause_cursor_data.h"

#define PAGE_MAP ((volatile unsigned short *)0x25E40000u)
#define PAGE_CELLS ((volatile unsigned short *)0x25E46000u)
#define PAGE_BYTES 38432u
#define MAP_BYTES 39952u
static int loaded = -1, drawn = -1;
static bool failed;

void pause_windows_reset(void) { loaded = drawn = -1; failed = false; }
bool pause_windows_failed(void) { return failed; }

static void pixel(int x, int y, unsigned colour)
{
    unsigned offset, shift;
    if (x < 0 || x >= 320 || y < 0 || y >= 240) return;
    offset = ((y / 8) * 40 + x / 8) * 16 + (y & 7) * 2 + (x & 7) / 4;
    shift = (3 - (x & 3)) * 4;
    PAGE_CELLS[offset] = (PAGE_CELLS[offset] & ~(15u << shift)) | (colour << shift);
}

static void frame(int x, int y, int size, unsigned colour)
{
    int side, xx, yy, dx, dy;
    for (side = 0; side < 4; ++side) {
        xx = x + ((side & 1) ? size - 15 : 0);
        yy = y + ((side & 2) ? size - 15 : 0);
        for (dy = 0; dy < 16; ++dy)
            for (dx = 0; dx < 16; ++dx)
                if (pause_cursor_masks[side][dy] & (1u << dx))
                    pixel(xx + dx, yy + dy, colour);
    }
}

bool pause_windows_update(void)
{
    pause_window_state_t *s = &gameplay.pause_window;
    unsigned page = s->system_confirm ? PAUSE_EXTRA : s->save_prompt ? PAUSE_SAVE : s->page;
    unsigned variant = page == PAUSE_EQUIPMENT ? gameplay.owned & 3 :
        page == PAUSE_ITEMS ? (!!save_state.stick_owned | (!!save_state.slingshot << 1)) :
        page == PAUSE_QUEST ? !!(save_state.quest_items & (1u << QUEST_KOKIRI_EMERALD)) : 0;
    int key = page * 4 + variant;
    unsigned bytes = page == PAUSE_MAP ? MAP_BYTES : PAGE_BYTES;
    unsigned pixel_start = page == PAUSE_MAP ? 1552u : 32u;
    unsigned char *data = ram_cart_fixed(RAM_CART_PAUSE_OFFSET, bytes);
    unsigned x, y, tile, i;
    int cursor = s->save_prompt ? s->save_choice : s->cursor[s->page];
    int stamp = cursor + (gameplay.equipped << 8);
    if (!data) { failed = true; return false; }
    if (key != loaded) {
        jo_file stream;
        char name[] = "PAUSE00.BIN";
        bool ok = false;
        name[5] += page; name[6] += variant;
        if (jo_fs_open(&stream, name)) {
            ok = stream.size == bytes;
            for (i = 0; ok && i < bytes; i += 512) {
                unsigned n = bytes - i;
                if (n > 512) n = 512;
                ok = jo_fs_read_next_bytes(&stream, (char *)data + i, n) == (int)n;
            }
            jo_fs_close(&stream);
        }
        loaded = key; drawn = -1; failed = !ok;
        if (failed) return false;
        for (i = 0; i < (page == PAUSE_MAP ? 176u : 16u); ++i)
            ((volatile unsigned short *)JO_VDP2_CRAM)[(page == PAUSE_MAP ? 848 : 816) + i] =
                ((unsigned)data[i * 2] << 8) | data[i * 2 + 1];
    }
    if (failed) return false;
    if (stamp == drawn) return true;
    for (tile = 0; tile < 1200; ++tile) {
        x = (tile % 40) * 4; y = (tile / 40) * 8;
        PAGE_MAP[(tile / 40) * 64 + tile % 40] =
            ((page == PAUSE_MAP ? (unsigned)data[352 + tile] : 3u) << 12) | (0x6000u / 32 + tile);
        for (i = 0; i < 16; ++i) {
            unsigned offset = pixel_start + (y + i / 2) * 160 + x + (i & 1) * 2;
            PAGE_CELLS[tile * 16 + i] = ((unsigned)data[offset] << 8) | data[offset + 1];
        }
    }
    if (page == PAUSE_ITEMS) frame(64 + (cursor % 6) * 32, 62 + (cursor / 6) * 32, 31, 15);
    else if (page == PAUSE_EQUIPMENT) {
        static const short columns[4] = {46, 172, 204, 236};
        if (gameplay.equipped & GP_SWORD) frame(173, 63, 29, 14);
        if (gameplay.equipped & GP_SHIELD) frame(173, 95, 29, 14);
        frame(columns[cursor % 4], 62 + (cursor / 4) * 32, 31, 15);
    } else if (page == PAUSE_SAVE) frame(cursor ? 168 : 100, 118, 47, 15);
    else if (page == PAUSE_QUEST && variant) frame(179, 165, 25, 15);
    drawn = stamp;
    return true;
}
