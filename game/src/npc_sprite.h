/* Baked NPC sprite impostors (SPR1 clips, SPR2 complete skeleton libraries).
** Sheets stay in the cart. Native C actors own individual cel slots; decomp
** actors share stable cel entries, pinned for each command-list frame. */
#ifndef DOSEI_NPC_SPRITE_H
#define DOSEI_NPC_SPRITE_H

#include <stdint.h>
#define NPC_SPRITE_SLOT_NONE UINT16_MAX

typedef struct npc_sprite_inst {
    const unsigned char *sheet;     /* sheet the slot's size/CLUT are set for */
    uint16_t slot, colno, shown;
} npc_sprite_inst_t;

/* Claim the instance's cel slot in the actor texture bank. False = full.
** A slot can later draw any sheet whose cel is not bigger than this one's:
** draw rebinds size and CLUT when the sheet changes. */
int  npc_sprite_upload(const unsigned char *spr, npc_sprite_inst_t *inst);
/* frame: source animation frame (ticks table index, wraps). */
void npc_sprite_draw(const unsigned char *spr, npc_sprite_inst_t *inst, unsigned int frame,
                     int x, int y, int z, uint16_t yaw);
/* Target/talk focus height above the actor origin, world units. */
int  npc_sprite_focus_y(const unsigned char *spr);
/* Conservative sphere/frustum rejection before cel uploads or facing math. */
int npc_sprite_in_view(int x, int y, int z, unsigned int radius);
unsigned char *npc_sprite_load(const char *name);
/* Nonzero: npc_sprite_draw skips the ground shadow (held/flying tools). */
extern unsigned char npc_sprite_shadow_off;
int npc_sprite_valid(const unsigned char *sheet, unsigned int bytes);
int npc_sprite_visible(const unsigned char *sheet, int x, int y, int z);
int npc_sprite_visible_scaled(const unsigned char *sheet, int x, int y, int z,
                              unsigned sx, unsigned sy);
/* SPR2 owns complete clip libraries. Validate once before exposing any clip. */
int npc_sprite_archive_valid(const unsigned char *archive, unsigned int bytes,
                             unsigned int skeleton);
const unsigned char *npc_sprite_archive_clip(const unsigned char *archive, unsigned int animation);
const unsigned char *npc_sprite_archive_largest(const unsigned char *archive);
/* Shared cel entries are pinned until all commands for this frame are built.
 * A pinned different cel can never be overwritten while VDP1 still uses it. */
unsigned int npc_sprite_cel(const unsigned char *sheet, unsigned int frame, int x, int z, uint16_t yaw);
/* cel's low 16 bits identify pixels; bit 16 requests a horizontal mirror.
 * Call after visible(), then submit immediately (uses its cached depth). */
void npc_sprite_draw_sample(const unsigned char *sheet, npc_sprite_inst_t *inst,
                            unsigned int sample, int x, int y, int z);
void npc_sprite_draw_styled(const unsigned char *sheet, npc_sprite_inst_t *inst,
                            unsigned int sample, int x, int y, int z,
                            unsigned sx, unsigned sy, unsigned alpha, unsigned tint);
/* Presentation-only direct cel, 320x240 screen coordinates. Uses the same
 * bounded upload slot as world sprites; no projection or gameplay mutation. */
void npc_sprite_draw_screen(const unsigned char *sheet, npc_sprite_inst_t *inst,
                            unsigned int cel, int x, int y, int scale_q16);
npc_sprite_inst_t *npc_sprite_cache_claim(npc_sprite_inst_t *slots, unsigned int count,
                                         unsigned int *pinned, const unsigned char *sheet,
                                         unsigned int cel);

#endif
