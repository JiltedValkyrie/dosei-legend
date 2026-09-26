#ifndef DOSEI_CUTSCENE_H
#define DOSEI_CUTSCENE_H

#include <stdbool.h>
#include <stdint.h>
#include "cutscenes.h"

bool            cutscene_start(unsigned int id);
bool            cutscene_step(bool confirm);
void            cutscene_skip_shot(void);
unsigned int    cutscene_shot_key(void);
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
/* SGL screen distance for the shot on screen, baked from its fov. Zero when
** no cutscene is playing, in which case the caller keeps its own. */
unsigned int    cutscene_screen_distance(void);
int16_t         cutscene_camera_roll(void);
unsigned int    cutscene_rain_count(void);
unsigned int    cutscene_lightning(void);
int16_t         cutscene_bridge_angle(void);

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
** position snaps to the cue start as in func_808529D0, so the
** storyboard's sleeping Link is where the original puts him rather than
** wherever gameplay last left him.
**
** False when no cue is running, in which case the caller draws nothing: the
** opening's shots that do not cue Link do not contain him.
*/
/*
** The shot's other actors, one per cue channel.
**
** The dream has two: the rider crossing the drawbridge and the one chasing.
** `channel` is the cue list they came from, which is what identifies an actor
** across a cutscene -- the cues carry no actor id of their own.
*/
unsigned int    cutscene_actor_channels(void);
bool            cutscene_actor_channel_visible(unsigned int channel);
int32_t         cutscene_actor_channel_x(unsigned int channel);
int32_t         cutscene_actor_channel_y(unsigned int channel);
int32_t         cutscene_actor_channel_z(unsigned int channel);
uint16_t        cutscene_actor_channel_yaw(unsigned int channel);

bool            cutscene_link_visible(void);
int32_t         cutscene_link_x(void);
int32_t         cutscene_link_y(void);
int32_t         cutscene_link_z(void);
uint16_t        cutscene_link_yaw(void);
/* LINK_CLIP_* for the current cue, and the frame within it. */
unsigned int    cutscene_link_clip(void);
unsigned int    cutscene_link_frame(void);

unsigned int cutscene_link_fraction(void);
#endif
