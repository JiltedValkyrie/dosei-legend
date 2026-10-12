#include <jo/jo.h>
#include "health_hud.h"
#include "health_hud_state.h"
#include "save_state.h"
#include "recomp.h"
#include "action_audio.h"
#include "ram_low.h"

/* B0: independent of map, button and pause cells. Keep its source atlas for
 * the existing VRAM layout, but never read it back during CPU composition. */
#define HEART_CELLS ((volatile unsigned short *)0x25E50000u)
#define HEART_BACK_CELLS ((volatile unsigned short *)0x25E51000u)
#define HEART_ATLAS ((volatile unsigned short *)0x25E50800u)
#define HEART_MAP ((volatile unsigned short *)0x25E40000u)
/* Region rows 4-5 (map rows 6-7, the magic meter below two heart rows):
 * 30 more cells per bank in B0 slack between the atlas and HUD icons. */
#define MAGIC_CELLS ((volatile unsigned short *)0x25E50B00u)
#define MAGIC_BACK_CELLS ((volatile unsigned short *)0x25E51780u)
#define HEARTS_FILE_BYTES 823
#define HEART_ATLAS_WORDS (5u * 64u)
#ifdef __sh__
#define HEART_SOURCE ((unsigned short *)RAM_LOW(RAM_LOW_HEART_ATLAS_OFFSET))
typedef char heart_atlas_fits[HEART_ATLAS_WORDS * sizeof(unsigned short) <=
                             RAM_LOW_HEART_ATLAS_BYTES ? 1 : -1];
#else
static unsigned short heart_source[HEART_ATLAS_WORDS];
#define HEART_SOURCE heart_source
#endif
#define HUD_CELLS 90
static bool ready;
/* build_health_hud.py: gMagicMeterEndTex, one gMagicMeterMidTex column and
 * the seven gMagicMeterFillTex rows, as CLUT indices (12-15). */
static unsigned char meter_end[128], meter_mid[16], meter_fill[7];
#define METER_BORDER_CRAM 13 /* CLUT entry of the meter's border colour */

/* z_parameter.c Magic_Update / Magic_RequestChange / Magic_Reset. Host-owned
 * gSaveContext.magicState, magicCapacity, magicTarget and magicFillTarget
 * until real Player; magic itself stays in save_state.source_magic. One call
 * per source frame (20 Hz). Lens and spell states are not used yet. */
enum { MAGIC_IDLE, MAGIC_STEP_CAPACITY, MAGIC_FILL, MAGIC_CONSUME_SETUP, MAGIC_CONSUME,
       MAGIC_METER_FLASH_1, MAGIC_RESET };
static unsigned char magic_state, magic_prev_state, magic_capacity, magic_fill_target, magic_target;
static short border_rgb[3] = { 255, 255, 255 }, border_ratio = 2, border_step = 1;
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
                else {
                    unsigned at = (offset - 32) / 2 + i;
                    HEART_ATLAS[at] = buffer[i];
                    HEART_SOURCE[at] = buffer[i];
                }
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

static void border_upload(void)
{
    ((volatile unsigned short *)JO_VDP2_CRAM)[832 + METER_BORDER_CRAM] =
        0x8000u | (unsigned)(border_rgb[0] >> 3) | (unsigned)(border_rgb[1] >> 3) << 5 |
        (unsigned)(border_rgb[2] >> 3) << 10;
}

static void border_white(void)
{
    border_rgb[0] = border_rgb[1] = border_rgb[2] = 255;
}

/* FileSelect_LoadGame, z_select and KaleidoScope continue: magicCapacity and
 * magic restart at 0, then STEP_CAPACITY (+8) and FILL (+4) rebuild them. */
void __attribute__((optimize("Os"))) health_hud_magic_start(void)
{
    magic_capacity = 0;
    magic_fill_target = save_state.source_magic;
    save_state.source_magic = 0;
    magic_prev_state = MAGIC_IDLE;
    magic_state = save_state.source_magic_level ? MAGIC_STEP_CAPACITY : MAGIC_IDLE;
    if (!save_state.source_magic_level) save_state.source_magic = magic_fill_target;
    border_white();
}

bool health_hud_magic_idle(void) { return magic_state == MAGIC_IDLE; }

bool health_hud_magic_available(unsigned amount)
{
    return save_state.source_magic_level && save_state.source_magic >= amount;
}

/* MAGIC_CONSUME_NOW (the bow's func_8083442C): callers check idle/available. */
bool health_hud_magic_consume(unsigned amount)
{
    if (!health_hud_magic_idle() || !health_hud_magic_available(amount)) return false;
    magic_target = (unsigned char)(save_state.source_magic - amount);
    magic_state = MAGIC_CONSUME_SETUP;
    return true;
}

void health_hud_magic_reset(void)
{
    if (magic_state != MAGIC_STEP_CAPACITY && magic_state != MAGIC_FILL)
        magic_state = MAGIC_RESET;
}

void __attribute__((optimize("Os"))) health_hud_magic_update(void)
{
    static const short colours[2][3] = { { 255, 255, 255 }, { 150, 150, 150 } };
    static const unsigned char indices[4] = { 0, 1, 1, 0 }, ratios[4] = { 2, 1, 2, 1 }; /* YREG(40-43) */
    unsigned target = (save_state.source_magic_level > 2 ? 2 : save_state.source_magic_level) * 0x30, c;
    int magic;
    switch (magic_state) {
    case MAGIC_STEP_CAPACITY:
        if (magic_capacity != target) {
            magic_capacity = magic_capacity < target ? (magic_capacity + 8 > target ? target : magic_capacity + 8)
                                                     : (magic_capacity <= target + 8 ? target : magic_capacity - 8);
        } else magic_state = MAGIC_FILL;
        break;
    case MAGIC_FILL:
        magic = save_state.source_magic + 4;
        action_audio_decomp_sfx(0x481F - 0x800); /* NA_SE_SY_GAUGE_UP - SFX_FLAG */
        if (magic >= magic_fill_target) {
            magic = magic_fill_target;
            magic_state = magic_prev_state;
            magic_prev_state = MAGIC_IDLE;
        }
        save_state.source_magic = (unsigned char)magic;
        break;
    case MAGIC_CONSUME_SETUP:
        border_ratio = 2;
        magic_state = MAGIC_CONSUME;
        break;
    case MAGIC_CONSUME:
        magic = save_state.source_magic - 2;
        if (magic <= 0 || magic == magic_target) {
            if (magic < 0) magic = 0;
            magic_state = MAGIC_METER_FLASH_1;
            border_white();
        }
        save_state.source_magic = (unsigned char)magic;
        /* fall through: the border flashes while magic is consumed */
    case MAGIC_METER_FLASH_1: {
        const short *to = colours[indices[border_step]];
        for (c = 0; c < 3; ++c) {
            short change = (short)((border_rgb[c] > to[c] ? border_rgb[c] - to[c] : to[c] - border_rgb[c]) /
                                   border_ratio);
            border_rgb[c] = (short)(border_rgb[c] >= to[c] ? border_rgb[c] - change : border_rgb[c] + change);
        }
        if (--border_ratio == 0) {
            for (c = 0; c < 3; ++c) border_rgb[c] = to[c];
            border_ratio = ratios[border_step];
            border_step = (short)((border_step + 1) & 3);
        }
        break;
    }
    case MAGIC_RESET:
        border_white();
        magic_state = MAGIC_IDLE;
        break;
    default:
        if (save_state.source_magic_level && magic_capacity != target) magic_capacity = (unsigned char)target;
        break;
    }
    if (ready) border_upload();
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
    unsigned capacity = magic_capacity, amount, x, y;
    unsigned top = hearts > 10 ? 42 - 16 : 34 - 16, left = 18 - 16;
    if (!save_state.source_magic_level) return;
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

/* One heart into a cell bank (any memory). */
static void heart_draw(unsigned short *cells, unsigned health, unsigned heart, unsigned extent,
                       const unsigned char *sample_at)
{
    unsigned fill = health_hud_fill(health, heart), x, y;
    int left = 14 + (heart % 10) * 10 - extent / 2;
    int top = 10 + (heart / 10) * 10 - extent / 2;
    for (y = 0; y < extent; ++y) for (x = 0; x < extent; ++x) {
        unsigned sx = sample_at[x], sy = sample_at[y];
        unsigned colour = (HEART_SOURCE[fill * 64 + sy * 4 + sx / 4] >> ((3 - sx % 4) * 4)) & 15;
        unsigned px = left + x, py = top + y;
        unsigned offset = ((py / 8) * 15 + px / 8) * 16 + (py % 8) * 2 + px % 8 / 4;
        unsigned shift = (3 - px % 4) * 4;
        if (colour) cells[offset] = (cells[offset] & ~(15u << shift)) | colour << shift;
    }
}

void health_hud_draw(bool visible)
{
    static unsigned short base_cells[60 * 16], base_magic[30 * 16];
    static unsigned short work_cells[60 * 16];
    static int base_key = -1, bank_key[2] = {-1,-1}, bank_magic[2] = {-1,-1};
    unsigned health = save_state.health, capacity = save_state.health_capacity / 16;
    unsigned pulse = (recomp_clock() / 3) % 10, size, heart, x, y, i;
    static const unsigned char sample11[11]={0,1,2,4,5,7,8,10,11,13,14};
    unsigned char sample[16];
    int key;
    volatile unsigned short *cells, *magic;
    unsigned magic_key = (save_state.source_magic_level ? 1u << 11 : 0) |
                         (magic_capacity / 8u) << 7 | (save_state.source_magic & 127);
    if (!ready) return;
    if (capacity > 20) capacity = 20;
    if (health > capacity * 16) health = capacity * 16;
    size = 11 + (pulse > 5 ? pulse - 5 : 5 - pulse);
    key = visible ? (int)(health | capacity << 9 | size << 14 | magic_key << 19) : -1; /* 31 bits */
    if (last_key == -2) {
        /* Scene reload/pause restoration can overwrite either VRAM bank.
         * Invalidate before the hidden return too: showing it later must
         * initialize both banks again, even when health has not changed. */
        base_key = bank_key[0] = bank_key[1] = bank_magic[0] = bank_magic[1] = -1;
    }
    if (last_key == key) return;
    last_key = key;
    if (!visible) {
        for (i = 0; i < HUD_CELLS; ++i)
            HEART_MAP[(2 + i / 15) * 64 + 2 + i % 15] = 0x2000u / 32;
        return;
    }
    /* Compose off-screen. Clearing active cells caused visible blank hearts
     * whenever a slow actor frame overlapped VDP2 scanning the HUD. Two 1,920 B
     * banks fit reserved B0 slack; atlas reads use the immutable Low RAM copy.
     *
     * Only the pulsing heart's maximum 16x16 footprint changes on a normal
     * frame. Restore/upload those cells; every destination bank has its own
     * content keys because the other bank may still hold an older health or
     * magic state. A pulse must erase that bank's old LARGE footprint before
     * painting a smaller heart. Full banks initialize only on state/reset. */
    {
        int still_key = (int)(health | capacity << 9 | magic_key << 19);
        int meter_key = (int)(magic_key | (capacity > 10u ? 1u << 12 : 0));
        unsigned pulse_heart = health ? (health - 1) / 16 : ~0u;
        unsigned left=0,right=0,top=0,bottom=0;
        if (pulse_heart < capacity) {
            unsigned cx=14+(pulse_heart%10)*10, cy=10+(pulse_heart/10)*10;
            left=(cx-8)/8; right=(cx+7)/8;
            top=(cy-8)/8; bottom=(cy+7)/8;
        }
        if (base_key != still_key) {
            base_key = still_key;
            for (i = 0; i < 60 * 16; ++i) base_cells[i] = 0;
            for (i = 0; i < 30 * 16; ++i) base_magic[i] = 0;
            for (heart = 0; heart < capacity; ++heart)
                if (heart != pulse_heart) heart_draw(base_cells, health, heart, 11, sample11);
            magic_meter(base_cells, base_magic, capacity);
            for (i = 0; i < 60 * 16; ++i) work_cells[i] = base_cells[i];
        } else if (pulse_heart < capacity) {
            for (y=top;y<=bottom;++y) for (x=left;x<=right;++x) {
                unsigned at=(y*15+x)*16;
                for (i=0;i<16;++i) work_cells[at+i]=base_cells[at+i];
            }
        }
        /* Only the pulsing heart changes size. Avoid variable division for
         * every pixel on the SH-2. */
        for (i = 0; i < size; ++i) sample[i] = i * 16 / size;
        if (pulse_heart < capacity)
            heart_draw(work_cells, health, pulse_heart, size, size == 11 ? sample11 : sample);
        front ^= 1u;
        cells = front ? HEART_BACK_CELLS : HEART_CELLS;
        magic = front ? MAGIC_BACK_CELLS : MAGIC_CELLS;
        if (bank_key[front] != still_key) {
            for (i = 0; i < 60 * 16; ++i) cells[i] = work_cells[i];
            bank_key[front] = still_key;
        } else if (pulse_heart < capacity) {
            for (y=top;y<=bottom;++y) for (x=left;x<=right;++x) {
                unsigned at=(y*15+x)*16;
                for (i=0;i<16;++i) cells[at+i]=work_cells[at+i];
            }
        }
        if (bank_magic[front] != meter_key) {
            for (i = 0; i < 30 * 16; ++i) magic[i] = base_magic[i];
            bank_magic[front] = meter_key;
        }
    }
    for (i = 0; i < 60; ++i)
        HEART_MAP[(2 + i / 15) * 64 + 2 + i % 15] =
            0x4000u | ((front ? 0x11000u : 0x10000u) / 32 + i);
    for (i = 60; i < HUD_CELLS; ++i)
        HEART_MAP[(2 + i / 15) * 64 + 2 + i % 15] =
            0x4000u | ((front ? 0x11780u : 0x10B00u) / 32 + i - 60);
}
