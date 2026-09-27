#ifndef DOSEI_MINIMAP_H
#define DOSEI_MINIMAP_H
#include <stdbool.h>
#include <stdint.h>

/*
** Overworld minimap (z_map_exp.c Minimap_Draw / Minimap_DrawCompassIcons).
** The map is VDP2 NBG2; markers are VDP1 palette sprites whose priority bit
** puts them above NBG2 while the RGB world stays below it. Per-scene rows
** come from tools/build_minimap.py; plan in docs/MINIMAP_PLAN.md.
**
** Reservations (nothing else may use them):
**   VDP2 VRAM B0 +0x0000  NBG2 page map, 64x64 one-word names (8 KB)
**   VDP2 VRAM B0 +0x2000  NBG2 cells, 16-colour, up to 16 KB
**   CRAM 768..783         map palette (NBG2 palette 0 at CRAM offset 3)
**   CRAM 784..799         marker palette (sprite colour bank 0x300)
**   Sprite priority 1     marker sprites (PR bit in the colour bank)
**   Cart carve            MINIMAP.BIN (ram_cart.h RAM_CART_MINIMAP_*)
*/
#define MINIMAP_VRAM_MAP        0x25E40000u
#define MINIMAP_VRAM_CELLS      0x25E42000u
#define MINIMAP_VRAM_CELL_BYTES 0x4000u
#define MINIMAP_CRAM_MAP        768u
#define MINIMAP_CRAM_MARKER     784u
#define MINIMAP_SPRITE_PRIORITY_BIT 0x2000u   /* type 3 PR bits 14-13 = 01 */

/* Validate MINIMAP.BIN (in its cart carve) and keep it. */
bool    minimap_bind(const uint8_t *blob, uint32_t bytes);
/* Once after the VDP1 texture setup: upload the marker frames. */
bool    minimap_init(void);
/* Scene load: upload that scene's map, or switch the map off. */
void    minimap_scene(unsigned int save_scene);
/* Hide toggle (future pause-menu option); rules still apply when shown. */
void    minimap_set_hidden(bool hidden);
/* NBG2ON when the map should be on screen this frame, else 0. */
uint32_t minimap_layer_flags(void);
/* Sprite priority 1 above NBG2; call after each jo_core_set_screens_order. */
void    minimap_priorities(void);
/* Pad snapshot each VBlank for the enemy-dot cheat (cheat_code.h). */
void    minimap_cheat_sample(uint16_t held);
bool    minimap_enemy_dots(void);
/* True once after the code is entered: the caller plays the get-item sound
** (main loop, not VBlank, so it never races action_audio's slot writes). */
bool    minimap_cheat_chime(void);
/* Link's arrow (world x/z, facing binang) plus enemy dots when cheated. */
void    minimap_draw(int32_t x, int32_t z, uint16_t yaw);

#endif
