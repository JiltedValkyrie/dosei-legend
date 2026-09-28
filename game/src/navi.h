#ifndef DOSEI_NAVI_H
#define DOSEI_NAVI_H
#include <stdbool.h>
#include <stdint.h>

/*
** Link's companion fairy in gameplay, from ovl_En_Elf's idle follow.
**
** The cutscene fairy is a cue channel and the Kokiri fairies mark NPC homes;
** neither is Navi. This one belongs to Link: she is snapped beside him the
** moment gameplay takes over and follows him through rooms and save loads.
**
** Source state 1 (func_80A01C38): an orbit of 7.5 units across and 5 up,
** stepping 0x800 / 0x1000 per source frame, around the hover point above his
** head, approached by func_80A03148. En_Elf updates at 20 Hz, so navi_step()
** is called per 30 Hz fixed step and runs the source update on two of three.
*/
/* x/y/z: the player's focus.pos (head point, link_anim_focus), world. */
void     navi_reset(int32_t link_x, int32_t link_y, int32_t link_z);
void     navi_step(int32_t link_x, int32_t link_y, int32_t link_z);
/*
** Attention-driven step (attention.h): hover = naviHoverPos, hat = Link's
** focus (PLAYER_BODYPART_HAT stand-in). has_actor: naviHoverActor set;
** moving: naviMoveProgressFactor != 0; colour: attention_colour_t wanted.
*/
void     navi_step_hover(const int32_t hover[3], const int32_t hat[3],
                         bool has_actor, bool moving, unsigned int colour);
/* attention_colour_t currently drawn (swaps after the source fade). */
unsigned int navi_colour(void);
bool     navi_active(void);
int32_t  navi_x(void);
int32_t  navi_y(void);
int32_t  navi_z(void);

/*
** True for the one step Navi breaks into a dash to catch up -- source plays
** NA_SE_EV_FAIRY_DASH here. demo.c consumes this immediately through the
** resident gameplay sample on Navi's dedicated SCSP slot.
*/
bool     navi_dash_started(void);

/*
** EnElf_SpawnSparkles (life 16) -> EffectSsKiraKira, one per En_Elf update,
** in a fixed pool (no allocation; a full pool drops the new sparkle as
** EffectSs_Spawn does). Stepped at the source 20 Hz with Navi. World
** position, spin (binang) and age out of NAVI_SPARKLE_LIFE.
*/
#define NAVI_SPARKLES       16      /* = life: one spawn per update, oldest frees first */
#define NAVI_SPARKLE_LIFE   16
bool     navi_sparkle(unsigned int i, int32_t pos[3], uint16_t *yaw, unsigned int *life);
#endif
