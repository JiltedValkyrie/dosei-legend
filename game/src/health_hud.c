#include <jo/jo.h>
#include "health_hud.h"
#include "health_hud_state.h"
#include "save_state.h"
#include "recomp.h"

/* B0: independent of map, button and pause cells. Source images also live in
 * VDP2 RAM so neither the sprite table nor scarce work RAM holds the atlas. */
#define HEART_CELLS ((volatile unsigned short *)0x25E50000u)
#define HEART_BACK_CELLS ((volatile unsigned short *)0x25E51000u)
#define HEART_ATLAS ((volatile unsigned short *)0x25E50800u)
#define HEART_MAP ((volatile unsigned short *)0x25E40000u)
/* Region rows 4-5 (map rows 6-7, the magic meter below two heart rows):
 * 30 more cells per bank in B0 slack between the atlas and HUD icons. */
#define MAGIC_CELLS ((volatile unsigned short *)0x25E50B00u)
#define MAGIC_BACK_CELLS ((volatile unsigned short *)0x25E51780u)
#define HEARTS_FILE_BYTES 823
#define HUD_CELLS 90
static bool ready;
/* build_health_hud.py: gMagicMeterEndTex, one gMagicMeterMidTex column and
 * the seven gMagicMeterFillTex rows, as CLUT indices (12-15). */
static unsigned char meter_end[128], meter_mid[16], meter_fill[7];
static int last_key = -2;
static unsigned front;

void health_hud_reset(void) { last_key = -2; }

bool __attribute__((optimize("Os"))) health_hud_init(void)
{
    jo_file file;
    unsigned short buffer[16];
    unsigned offset, i;
    ready = false;
    if (!jo_fs_open(&file, "HEARTS.BIN")) return false;
    if (file.size == HEARTS_FILE_BYTES) {
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
        if (ready && (jo_fs_read_next_bytes(&file, (char *)meter_end, 128) != 128 ||
                      jo_fs_read_next_bytes(&file, (char *)meter_mid, 16) != 16 ||
                      jo_fs_read_next_bytes(&file, (char *)meter_fill, 7) != 7))
            ready = false;
    }
    jo_fs_close(&file);
    health_hud_reset();
    return ready;
}

/* Region pixel: rows 0-3 in the heart bank, rows 4-5 in the magic bank. */
static void hud_pixel(volatile unsigned short *cells, volatile unsigned short *magic,
                      unsigned px, unsigned py, unsigned colour)
{
    unsigned cell = (py / 8) * 15 + px / 8, shift = (3 - px % 4) * 4;
    volatile unsigned short *word = (cell < 60 ? cells + cell * 16 : magic + (cell - 60) * 16) +
                                    (py % 8) * 2 + px % 8 / 4;
    if (colour) *word = (*word & ~(15u << shift)) | colour << shift;
}

/* Magic_DrawMeter: R_MAGIC_METER_X 18, Y 34 (one heart row) or 42, fill
 * from R_MAGIC_FILL_X 26, rows y+3..y+9; capacity 0x30 per magic level.
 * Region origin is screen (16,16). No consumption flash (magicState). */
static void magic_meter(volatile unsigned short *cells, volatile unsigned short *magic,
                        unsigned hearts)
{
    unsigned level = save_state.source_magic_level, capacity, amount, x, y;
    unsigned top = hearts > 10 ? 42 - 16 : 34 - 16, left = 18 - 16;
    if (!level) return;
    capacity = (level > 2 ? 2 : level) * 0x30;
    amount = save_state.source_magic < capacity ? save_state.source_magic : capacity;
    for (y = 0; y < 16; ++y) {
        for (x = 0; x < 8; ++x) {
            hud_pixel(cells, magic, left + x, top + y, meter_end[y * 8 + x]);
            /* Right end: G_TX_MIRROR on S from texel 8. */
            hud_pixel(cells, magic, left + 8 + capacity + x, top + y, meter_end[y * 8 + 7 - x]);
        }
        for (x = 0; x < capacity; ++x)
            hud_pixel(cells, magic, left + 8 + x, top + y, meter_mid[y]);
    }
    for (y = 0; y < 7; ++y)
        for (x = 0; x < amount; ++x)
            hud_pixel(cells, magic, left + 8 + x, top + 3 + y, meter_fill[y]);
}

void health_hud_draw(bool visible)
{
    unsigned health = save_state.health, capacity = save_state.health_capacity / 16;
    unsigned pulse = (recomp_clock() / 3) % 10, size, heart, x, y, i;
    static const unsigned char sample11[11]={0,1,2,4,5,7,8,10,11,13,14};
    unsigned char sample[16];
    int key;
    volatile unsigned short *cells, *magic;
    unsigned magic_key = (save_state.source_magic_level & 3) << 7 |
                         (save_state.source_magic & 127);
    if (!ready) return;
    if (capacity > 20) capacity = 20;
    if (health > capacity * 16) health = capacity * 16;
    size = 11 + (pulse > 5 ? pulse - 5 : 5 - pulse);
    key = visible ? (int)(health | capacity << 9 | size << 14 | magic_key << 19) : -1;
    if (last_key == key) return;
    last_key = key;
    if (!visible) {
        for (i = 0; i < HUD_CELLS; ++i)
            HEART_MAP[(2 + i / 15) * 64 + 2 + i % 15] = 0x2000u / 32;
        return;
    }
    /* Compose off-screen. Clearing active cells caused visible blank hearts
     * whenever a slow actor frame overlapped VDP2 scanning the HUD. Two 1,920 B
     * banks fit reserved B0 slack; the immutable atlas stays at 0x50800. */
    front ^= 1u;
    cells = front ? HEART_BACK_CELLS : HEART_CELLS;
    magic = front ? MAGIC_BACK_CELLS : MAGIC_CELLS;
    for (i = 0; i < 60 * 16; ++i) cells[i] = 0;
    for (i = 0; i < 30 * 16; ++i) magic[i] = 0;
    /* Only the pulsing heart changes size. Avoid variable division for every
     * pixel of all twenty hearts on the SH-2. */
    for (i = 0; i < size; ++i) sample[i] = i * 16 / size;
    for (heart = 0; heart < capacity; ++heart) {
        unsigned fill = health_hud_fill(health, heart);
        unsigned extent = health && heart == (health - 1) / 16 ? size : 11;
        const unsigned char *sample_at=extent==11 ? sample11 : sample;
        int left = 14 + (heart % 10) * 10 - extent / 2;
        int top = 10 + (heart / 10) * 10 - extent / 2;
        for (y = 0; y < extent; ++y) for (x = 0; x < extent; ++x) {
            unsigned sx = sample_at[x], sy = sample_at[y];
            unsigned colour = (HEART_ATLAS[fill * 64 + sy * 4 + sx / 4] >> ((3 - sx % 4) * 4)) & 15;
            unsigned px = left + x, py = top + y;
            unsigned offset = ((py / 8) * 15 + px / 8) * 16 + (py % 8) * 2 + px % 8 / 4;
            unsigned shift = (3 - px % 4) * 4;
            if (colour) cells[offset] = (cells[offset] & ~(15u << shift)) | colour << shift;
        }
    }
    magic_meter(cells, magic, capacity);
    for (i = 0; i < 60; ++i)
        HEART_MAP[(2 + i / 15) * 64 + 2 + i % 15] =
            0x4000u | ((front ? 0x11000u : 0x10000u) / 32 + i);
    for (i = 60; i < HUD_CELLS; ++i)
        HEART_MAP[(2 + i / 15) * 64 + 2 + i % 15] =
            0x4000u | ((front ? 0x11780u : 0x10B00u) / 32 + i - 60);
}
