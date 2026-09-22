#ifndef DOSEI_CUTSCENE_H
#define DOSEI_CUTSCENE_H

#include <stdbool.h>
#include <stdint.h>
#include "cutscenes.h"

bool            cutscene_start(unsigned int id);
bool            cutscene_step(bool confirm);
bool            cutscene_is_playing(void);
bool            cutscene_finished(void);
unsigned int    cutscene_id(void);
unsigned int    cutscene_frame(void);

/*
** The screen fill, from the cutscene's own CS_TRANSITION commands.
**
** OoT draws these as a full-screen coloured quad whose alpha the transition
** ramps (z_demo.c:1550-1574). The opening depends on it: the narration plays
** over a black screen, the house is revealed part-way through, and the screen
** goes back to black before the dream. Without it the scene shows from the
** first frame, which is what "Link's house leaking during the narration" was.
**
** 0 = nothing over the scene, 255 = the scene is completely hidden.
*/
unsigned int    cutscene_fade_alpha(void);

/* Which colour the fill is, as CUTSCENE_FADE_BLACK / _GRAY. */
unsigned int    cutscene_fade_colour(void);

/* True when the fill is opaque, so there is no point drawing the world behind
** it at all. The caller skips the scene and the backdrop layer. */
bool            cutscene_hides_scene(void);

/*
** Link, placed and posed by the cutscene's own player cues.
**
** A cue carries a start and end position and a facing, and names the pose
** Link holds while it runs -- asleep in bed, turning over, sitting up. The
** position is interpolated across the cue exactly as OoT does, so the
** storyboard's sleeping Link is where the original puts him rather than
** wherever gameplay last left him.
**
** False when no cue is running, in which case the caller draws nothing: the
** opening's shots that do not cue Link do not contain him.
*/
bool            cutscene_link_visible(void);
int32_t         cutscene_link_x(void);
int32_t         cutscene_link_y(void);
int32_t         cutscene_link_z(void);
uint16_t        cutscene_link_yaw(void);
/* LINK_CLIP_* for the current cue, and the frame within it. */
unsigned int    cutscene_link_clip(void);
unsigned int    cutscene_link_frame(void);

#endif
