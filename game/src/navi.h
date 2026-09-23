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
/* `link_y` is Link's FEET, the model origin -- not the collision/eye height.
** Navi anchors on his head, which is a fixed rise above his feet. */
void     navi_reset(int32_t link_x, int32_t link_y, int32_t link_z);
void     navi_step(int32_t link_x, int32_t link_y, int32_t link_z);
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
#endif
