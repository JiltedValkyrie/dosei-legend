/* Baked NPC sprite impostors. Format: tools/build_npc_sprites.py docstring. */
#pragma GCC optimize("Os")
#include <jo/jo.h>
#include "npc_sprite.h"
#include "kokiri_sgl.h"
#include "gameplay.h"
#include "recomp.h"
#include "kokiri_camera.h"
#include "perf_sub.h"
#include "../oot-core/include/oot_sprite_archive.h"
#ifdef DOSEI_OOT_CORE
#include "oot_core_api.h"
#endif

#define U16(s, o) ((unsigned int)((s)[o] << 8 | (s)[(o) + 1]))
#define CELS(s) (0x34u + ((U16(s, 0x0C) * 2u + 3u) & ~3u))

int npc_sprite_valid(const unsigned char *s, unsigned int length)
{
    unsigned int w, h, poses, ticks, base, i;
    if (!s || length < 0x34 || s[0]!='S' || s[1]!='P' || s[2]!='R' || s[3]!='1') return 0;
    w=U16(s,4); h=U16(s,6); poses=U16(s,10); ticks=U16(s,12);
    if (!w || w>256 || (w&7) || !h || h>255 || !poses || poses>256 ||
        !ticks || U16(s,8)!=5 || !U16(s,16)) return 0;
    base=CELS(s);
    if (base + w*h/2*poses*5 != length) return 0;
    for (i=0;i<ticks;++i) if (U16(s,0x34+i*2)>=poses) return 0;
    return 1;
}

int npc_sprite_archive_valid(const unsigned char *s, unsigned int bytes, unsigned int skeleton)
{
    return OotSprite_ArchiveValid(s,bytes,skeleton);
}

const unsigned char *npc_sprite_archive_clip(const unsigned char *s, unsigned int animation)
{
    if (!s) return 0;
#ifdef DOSEI_OOT_CORE
    return ((const OotCoreEntry*)OOT_CORE_LOAD_ADDR)->sprite_clip(s,animation);
#else
    return OotSprite_Clip(s,animation);
#endif
}

const unsigned char *npc_sprite_archive_largest(const unsigned char *s)
{
    if (!s) return 0;
#ifdef DOSEI_OOT_CORE
    return ((const OotCoreEntry*)OOT_CORE_LOAD_ADDR)->sprite_clip(s,~0u);
#else
    return OotSprite_Clip(s,~0u);
#endif
}

npc_sprite_inst_t *npc_sprite_cache_claim(npc_sprite_inst_t *slots, unsigned int count,
                                         unsigned int *pinned, const unsigned char *sheet,
                                         unsigned int cel)
{
    /* Rotate misses through the available slots so previous animation cels
     * survive beyond one frame, rather than repeatedly replacing slot zero. */
    static unsigned replacement;
    unsigned int i, candidate=count, start=replacement<count?replacement:0;
    if (count>32) return 0;
    for (i=0;i<count;++i) {
        if (slots[i].slot==NPC_SPRITE_SLOT_NONE) continue;
        if (slots[i].sheet==sheet && slots[i].shown==cel) {
            *pinned |= 1u<<i;
            return &slots[i];
        }
        if (!(*pinned & (1u<<i)) &&
            (candidate==count || (candidate<start && i>=start))) candidate=i;
    }
    if (candidate==count) return 0;
    replacement=candidate+1<count?candidate+1:0;
    *pinned |= 1u<<candidate;
    return &slots[candidate];
}

unsigned char *npc_sprite_load(const char *name)
{
    int length = 0;
    unsigned char *s = (unsigned char *)jo_fs_read_file(name, &length);
    if (!s) return 0;
    if (!npc_sprite_valid(s, (unsigned int)length)) {
        jo_free(s);
        return 0;
    }
    return s;
}

int npc_sprite_upload(const unsigned char *spr, npc_sprite_inst_t *inst)
{
    unsigned int colno = 0;
    inst->slot = (uint16_t)kokiri_bank_tile_upload(spr + CELS(spr), spr + 0x14,
                                                   U16(spr, 4), U16(spr, 6), &colno);
    inst->colno = (uint16_t)colno;
    inst->shown = 0;
    inst->sheet = spr;
    return inst->slot != NPC_SPRITE_SLOT_NONE;
}

int npc_sprite_focus_y(const unsigned char *spr) { return (int16_t)U16(spr, 0x12); }

static int last_depth; /* view depth of the last in_view point */
int npc_sprite_in_view(int x, int y, int z, unsigned int radius)
{
    static int32_t sy, cy, sp, cp;
    static uint16_t yaw, pitch;
    static int valid;
    int h, right, depth, up, limit, distance = recomp_screen_distance();
    last_depth = 32767;
    x -= recomp_camera.x; y -= recomp_camera.y; z -= recomp_camera.z;
    /* Keep every intermediate in signed 32-bit. Large/unusual views are left
     * to SGL instead of risking a false rejection or a wide-math fallback. */
    if (x < -32767 || x > 32767 || y < -32767 || y > 32767 ||
        z < -32767 || z > 32767 || radius > 1024 || distance > 4096 || distance < 1)
        return 1;
    if (!valid || yaw != (uint16_t)recomp_yaw || pitch != (uint16_t)recomp_pitch) {
        yaw = (uint16_t)recomp_yaw; pitch = (uint16_t)recomp_pitch; valid = 1;
        kokiri_camera_sincos(yaw, &sy, &cy);
        kokiri_camera_sincos(pitch, &sp, &cp);
        sy /= 256; cy /= 256; sp /= 256; cp /= 256;
    }
    h = (x * sy + z * cy) / 256;
    right = (-x * cy + z * sy) / 256;
    depth = (h * cp + y * sp) / 256;
    up = (y * cp - h * sp) / 256;
    last_depth = depth;
    if (depth + (int)radius <= 0) return 0;
    /* 200 covers the 320x240 screen's half diagonal, including camera roll. */
    limit = depth * 200 + (int)radius * (distance + 400);
    if (right < 0) right = -right;
    if (up < 0) up = -up;
    return right * distance <= limit && up * distance <= limit;
}

int npc_sprite_visible(const unsigned char *spr, int x, int y, int z)
{
    unsigned int radius = (U16(spr, 4) + U16(spr, 6)) * U16(spr, 0x10) / 512 + 8;
    return npc_sprite_in_view(x, y + (int16_t)U16(spr, 0x0E) / 16, z, radius);
}

unsigned char npc_sprite_shadow_off;
unsigned int npc_sprite_cel(const unsigned char *spr, unsigned int frame, int x, int z, uint16_t yaw)
{
    uint16_t phi=(uint16_t)(yaw-gameplay_facing(recomp_camera.x-x,recomp_camera.z-z));
    unsigned int d8=((phi+0x1000u)>>13)&7, dir=d8<=4?d8:8-d8;
    if (!npc_sprite_shadow_off && last_depth>500) frame &= ~1u;
    if (!npc_sprite_shadow_off && last_depth>1200) frame=0;
    return (U16(spr,0x34+(frame%U16(spr,0x0C))*2)*U16(spr,8)+dir) |
           (d8>4 ? 0x10000u : 0);
}

int npc_sprite_visible_scaled(const unsigned char *spr, int x, int y, int z,
                              unsigned sx, unsigned sy)
{
    if (!sx || !sy) return 0;
    if (sx > 4096) sx = 4096;
    if (sy > 4096) sy = 4096;
    unsigned radius = (U16(spr, 4) * sx + U16(spr, 6) * sy) / 256;
    radius = radius * U16(spr, 0x10) / 512 + 8;
    return npc_sprite_in_view(x, y + (int16_t)U16(spr, 0x0E) * (int)sy / 4096, z, radius);
}

void npc_sprite_draw(const unsigned char *spr, npc_sprite_inst_t *inst, unsigned int frame,
                     int x, int y, int z, uint16_t yaw)
{
    if (inst->slot == NPC_SPRITE_SLOT_NONE ||
        !npc_sprite_visible(spr, x, y, z)) return;
    npc_sprite_draw_sample(spr,inst,npc_sprite_cel(spr,frame,x,z,yaw),x,y,z);
}

/* Debug fallback, master-owned. DMA is joined before publishing shown or
 * submitting a sprite; never replace a channel while another transfer runs. */
volatile unsigned npc_sprite_cpu_copy;
static void npc_sprite_bind_sample(const unsigned char *spr, npc_sprite_inst_t *inst,
                                   unsigned int cel)
{
    unsigned int bytes = U16(spr, 4) * U16(spr, 6) / 2;
    if (inst->sheet != spr) {
        jo_texture_definition *t = &__jo_sprite_def[inst->slot];
        uint16_t *clut = (uint16_t *)(JO_VDP1_VRAM + inst->colno * 8u);
        unsigned int k;
        t->width = (unsigned short)U16(spr, 4);
        t->height = (unsigned short)U16(spr, 6);
        t->size = JO_MULT_BY_32(t->width & 0x1f8) | t->height;
        for (k = 0; k < 16; ++k) clut[k] = (uint16_t)U16(spr, 0x14 + k * 2);
        inst->sheet = spr;
        inst->shown = 0xFFFF;
    }
    if (cel != inst->shown) {
        const uint32_t *from = (const uint32_t *)(spr + CELS(spr) + cel * bytes);
        uint32_t *to = (uint32_t *)__jo_sprite_pic[inst->slot].data;
        unsigned int k, t0 = frame_timer_ticks();
        if (!npc_sprite_cpu_copy) {
            slDMAWait();
            jo_dma_copy((void *)from, to, bytes);
            slDMAWait();
        } else for (k = 0; k < bytes / 4; ++k) to[k] = from[k];
        inst->shown = (uint16_t)cel;
        PS_ACC(PS_CEL, frame_timer_ticks_to_us(frame_timer_ticks() - t0));
        PS_ACC(PS_CELB, bytes);
    }
}

void npc_sprite_draw_screen(const unsigned char *spr, npc_sprite_inst_t *inst,
                            unsigned int cel, int x, int y, int scale_q16)
{
    FIXED pos[5];
    SPR_ATTR attr = SPR_ATTRIBUTE(0, 0, No_Gouraud, CL16Look | ECdis,
                                  sprNoflip | FUNC_Sprite);
    if (!spr || inst->slot == NPC_SPRITE_SLOT_NONE || cel >= U16(spr,8)*U16(spr,10)) return;
    npc_sprite_bind_sample(spr, inst, cel);
    pos[0] = (x-JO_TV_WIDTH_2)*65536;
    pos[1] = (y-JO_TV_HEIGHT_2)*65536;
    pos[2] = kokiri_hud_depth(4);
    pos[3] = pos[4] = scale_q16;
    attr.texno = inst->slot;
    attr.colno = inst->colno;
#ifdef DOSEI_HIRES
    pos[1] = (y*2-JO_TV_HEIGHT_2)*65536;
    pos[4] *= 2;
    slDispSpriteHV(pos, &attr, 1);
#else
    slDispSprite(pos, &attr, 0);
#endif
}

void npc_sprite_draw_sample(const unsigned char *spr, npc_sprite_inst_t *inst,
                            unsigned int sample, int x, int y, int z)
{
    npc_sprite_draw_styled(spr, inst, sample, x, y, z, 256, 256, 255, 0);
}

void npc_sprite_draw_styled(const unsigned char *spr, npc_sprite_inst_t *inst,
                            unsigned int sample, int x, int y, int z,
                            unsigned sx, unsigned sy, unsigned alpha, unsigned tint)
{
    FIXED pos[5];
    /* SGL sprHflip is broken (PDATA16 typo): bit 4 is the H flip. */
    SPR_ATTR attr = SPR_ATTRIBUTE(0, 0, No_Gouraud, CL16Look | ECdis,
                                  (sample & 0x10000u ? (1 << 4) : 0) | sprNoflip | FUNC_Sprite);
    if (inst->slot == NPC_SPRITE_SLOT_NONE || !sx || !sy || !alpha) return;
    if (sx > 4096) sx = 4096;
    if (sy > 4096) sy = 4096;
    if (alpha < 255) attr.atrb |= MESHon;
    if (tint) { attr.atrb |= CL_Gouraud; attr.gstb = kokiri_hit_gouraud(tint); }
    {
        unsigned int t0 = frame_timer_ticks();
        if (!npc_sprite_shadow_off) kokiri_actor_shadow(x,y,z,U16(spr,4)*U16(spr,0x10)/1024+4);
        PS_ACC(PS_SSHADOW, frame_timer_ticks_to_us(frame_timer_ticks() - t0));
        PS_ACC(PS_SCOUNT, 1u);
    }
    npc_sprite_bind_sample(spr, inst, sample & 0xffffu);
    {
        /* SGL drops a sprite whose single anchor is nearer than the screen
         * distance >> ZDSP level 3; narrow cutscene shots move that cut out.
         * Slide a near anchor out along the view ray to just past the cut and
         * grow the scale so it keeps its size; then cap the projected height
         * (~900 px) so a huge close sprite cannot wrap VDP1 coordinates. */
        int dist = recomp_screen_distance(), near = dist / 8 + 6, depth = last_depth;
        int32_t cx = recomp_camera.x, cy = recomp_camera.y, cz = recomp_camera.z;
        int32_t ay = y + (int16_t)U16(spr, 0x0E) * (int)sy / 4096, k = 256;
        int32_t scale = (int32_t)U16(spr, 0x10), px;
        if (depth < 4) depth = 4;
        if (depth < near) {
            k = near * 256 / depth;
            x = cx + (x - cx) * k / 256;
            ay = cy + (ay - cy) * k / 256;
            z = cz + (z - cz) * k / 256;
            depth = near;
        }
        px = U16(spr, 6) * U16(spr, 0x10) / 256 * sy / 256 * k / 256 * dist / depth;
        if (px > 900) k = k * 900 / px;
        pos[0] = x * 65536;
        pos[1] = -ay * 65536;
        pos[2] = z * 65536;
        pos[3] = scale * (int)sx / 256 * k;
        pos[4] = scale * (int)sy / 256 * k;
    }
    attr.texno = inst->slot;
    attr.colno = inst->colno;
    {
        unsigned int t0 = frame_timer_ticks();
        slPutSprite(pos, &attr, 0);
        PS_ACC(PS_SPUT, frame_timer_ticks_to_us(frame_timer_ticks() - t0));
    }
}
