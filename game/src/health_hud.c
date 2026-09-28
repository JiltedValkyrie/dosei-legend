#include <jo/jo.h>
#include "health_hud.h"
#include "health_hud_state.h"
#include "save_state.h"
#include "demo.h"

/* B0: independent of map, button and pause cells. Source images also live in
 * VDP2 RAM so neither the sprite table nor scarce work RAM holds the atlas. */
#define HEART_CELLS ((volatile unsigned short *)0x25E50000u)
#define HEART_ATLAS ((volatile unsigned short *)0x25E50800u)
#define HEART_MAP ((volatile unsigned short *)0x25E40000u)
static bool ready;
static int last_key = -2;

void health_hud_reset(void) { last_key = -2; }

bool health_hud_init(void)
{
    jo_file file;
    unsigned short buffer[16];
    unsigned offset, i;
    ready = false;
    if (!jo_fs_open(&file, "HEARTS.BIN")) return false;
    if (file.size == 672) {
        ready = true;
        for (offset = 0; offset < 672; offset += 32) {
            if (jo_fs_read_next_bytes(&file, (char *)buffer, 32) != 32) {
                ready = false; break;
            }
            for (i = 0; i < 16; ++i) {
                if (!offset) ((volatile unsigned short *)JO_VDP2_CRAM)[832 + i] = buffer[i];
                else HEART_ATLAS[(offset - 32) / 2 + i] = buffer[i];
            }
        }
    }
    jo_fs_close(&file);
    health_hud_reset();
    return ready;
}

void health_hud_draw(bool visible)
{
    unsigned health = save_state.health, capacity = save_state.health_capacity / 16;
    unsigned pulse = (demo_clock() / 3) % 10, size, heart, x, y, i;
    int key;
    if (!ready) return;
    if (capacity > 20) capacity = 20;
    if (health > capacity * 16) health = capacity * 16;
    size = 11 + (pulse > 5 ? pulse - 5 : 5 - pulse);
    key = visible ? (int)(health | capacity << 9 | size << 14) : -1;
    if (last_key == key) return;
    last_key = key;
    for (i = 0; i < 60; ++i) {
        HEART_MAP[(2 + i / 15) * 64 + 2 + i % 15] = visible ?
            0x4000u | (0x10000u / 32 + i) : 0x2000u / 32;
    }
    if (!visible) return;
    for (i = 0; i < 60 * 16; ++i) HEART_CELLS[i] = 0;
    for (heart = 0; heart < capacity; ++heart) {
        unsigned fill = health_hud_fill(health, heart);
        unsigned extent = health && heart == (health - 1) / 16 ? size : 11;
        int left = 14 + (heart % 10) * 10 - extent / 2;
        int top = 10 + (heart / 10) * 10 - extent / 2;
        for (y = 0; y < extent; ++y) for (x = 0; x < extent; ++x) {
            unsigned sx = x * 16 / extent, sy = y * 16 / extent;
            unsigned colour = (HEART_ATLAS[fill * 64 + sy * 4 + sx / 4] >> ((3 - sx % 4) * 4)) & 15;
            unsigned px = left + x, py = top + y;
            unsigned offset = ((py / 8) * 15 + px / 8) * 16 + (py % 8) * 2 + px % 8 / 4;
            unsigned shift = (3 - px % 4) * 4;
            if (colour) HEART_CELLS[offset] = (HEART_CELLS[offset] & ~(15u << shift)) | colour << shift;
        }
    }
}
