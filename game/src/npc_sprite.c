/* Baked NPC sprite impostors. Format: tools/build_npc_sprites.py docstring. */
#pragma GCC optimize("Os")
#include <jo/jo.h>
#include "npc_sprite.h"
#include "kokiri_sgl.h"
#include "gameplay.h"
#include "demo.h"
#include "kokiri_camera.h"

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

int npc_sprite_in_view(int x, int y, int z, unsigned int radius)
{
    static int32_t sy, cy, sp, cp;
    static uint16_t yaw, pitch;
    static int valid;
    int h, right, depth, up, limit, distance = demo_screen_distance();
    x -= demo_camera.x; y -= demo_camera.y; z -= demo_camera.z;
    /* Keep every intermediate in signed 32-bit. Large/unusual views are left
     * to SGL instead of risking a false rejection or a wide-math fallback. */
    if (x < -32767 || x > 32767 || y < -32767 || y > 32767 ||
        z < -32767 || z > 32767 || radius > 1024 || distance > 4096 || distance < 1)
        return 1;
    if (!valid || yaw != (uint16_t)demo_yaw || pitch != (uint16_t)demo_pitch) {
        yaw = (uint16_t)demo_yaw; pitch = (uint16_t)demo_pitch; valid = 1;
        kokiri_camera_sincos(yaw, &sy, &cy);
        kokiri_camera_sincos(pitch, &sp, &cp);
        sy /= 256; cy /= 256; sp /= 256; cp /= 256;
    }
    h = (x * sy + z * cy) / 256;
    right = (-x * cy + z * sy) / 256;
    depth = (h * cp + y * sp) / 256;
    up = (y * cp - h * sp) / 256;
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

void npc_sprite_draw(const unsigned char *spr, npc_sprite_inst_t *inst, unsigned int frame,
                     int x, int y, int z, uint16_t yaw)
{
    if (inst->slot == NPC_SPRITE_SLOT_NONE ||
        !npc_sprite_visible(spr, x, y, z)) return;
    unsigned int bytes = U16(spr, 4) * U16(spr, 6) / 2;
    kokiri_actor_shadow(x,y,z,U16(spr,4)*U16(spr,0x10)/1024+4);
    /* phi: camera seen from the actor's frame, 0 = in front (bake view()).
    ** Sign confirmed in Kronos 2026-10-03. */
    uint16_t phi = (uint16_t)(yaw - gameplay_facing(demo_camera.x - x, demo_camera.z - z));
    unsigned int d8 = ((phi + 0x1000u) >> 13) & 7, dir = d8 <= 4 ? d8 : 8 - d8;
    unsigned int pose = U16(spr, 0x34 + (frame % U16(spr, 0x0C)) * 2);
    unsigned int cel = pose * U16(spr, 8) + dir;
    FIXED pos[5];
    /* SGL sprHflip is broken (PDATA16 typo): bit 4 is the H flip. */
    SPR_ATTR attr = SPR_ATTRIBUTE(0, 0, No_Gouraud, CL16Look | ECdis,
                                  (d8 > 4 ? (1 << 4) : 0) | sprNoflip | FUNC_Sprite);
    if (inst->slot == NPC_SPRITE_SLOT_NONE) return;
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
        unsigned int k;
        for (k = 0; k < bytes / 4; ++k) to[k] = from[k];
        inst->shown = (uint16_t)cel;
    }
    pos[0] = x * 65536;
    pos[1] = -(y * 65536 + (int16_t)U16(spr, 0x0E) * 4096);
    pos[2] = z * 65536;
    pos[3] = pos[4] = (FIXED)U16(spr, 0x10) * 256;
    attr.texno = inst->slot;
    attr.colno = inst->colno;
    slPutSprite(pos, &attr, 0);
}
