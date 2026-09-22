#include <jo/jo.h>
#include "cutscene.h"
#include "demo.h"
#include "game_mode.h"
#include "link_clips.h"
#include "message.h"
#include "music.h"
#include "music_banks.h"
#include "save_state.h"
#include "scene_flow.h"
#include "kokiri_sgl.h"
#include "cutscene_actor.h"

typedef struct
{
    bool              active;
    bool              finished;
    unsigned char     id;
    unsigned short    frame;
    unsigned char     text_cursor;
    unsigned char     music_cursor;
    /* Current screen fill, rebuilt every frame from the transition list. */
    unsigned char     fade_alpha;
    unsigned char     fade_colour;
    /* End frame of the text command currently on screen. Past it, the
    ** cutscene clock holds until the player has read the message. */
    short             text_hold_end;
    /* False when this cutscene's scene is not in the scene table yet, so the
    ** screen is held covered instead of showing an unrelated room. */
    bool              scene_loaded;
    cutscene_point_t *track;
}                   cutscene_state_t;

static cutscene_state_t state;

#define CUTSCENE_FADE_FRAMES 10

/*
** Which scene_table entry a cutscene plays in, or -1 when that scene has not
** been extracted yet.
**
** SPOT00 -- the castle drawbridge the nightmare rides across -- is not in the
** table. It must NOT fall back to Link's house: that put the bedroom backdrop
** behind Ganondorf's ride. A missing scene keeps the screen covered instead,
** which reads as work still to do rather than as a wrong room.
*/
static int scene_for_cutscene(unsigned int scene)
{
    switch (scene) {
    case CUTSCENE_SCENE_LINK_HOME: return SCENE_LINK_HOME;
    case CUTSCENE_SCENE_SPOT04:    return SCENE_SPOT04;
    default:                       return -1;
    }
}

/*
** The dream rides across Hyrule Field, which is a bank of its own.
**
** SPOT00 has no scene_table entry: it is never walked into, only flown over,
** so the cutscene asks for the bank by number. It is flat shaded -- every
** face carries its own colour and there are no tiles at all -- so it costs
** nothing of the VDP1 texture area that the streamed forest fills, which is
** what makes a second environment affordable during the opening.
**
** Built by tools/build_flat_scene.py from levels/hyrule/assets/static.
*/
#define CUTSCENE_FIELD_BANK 3

/*
** Navi's flight uses the ordinary streamed rooms.
**
** A single authored bank of the whole zone was tried instead -- the flight
** crosses rooms that are not resident, so parts of the forest are missing
** from the shot. It was not worth it: fitting the whole zone into one bank
** meant 1,795 sixteen-pixel tiles, which came out corrupted and dropped VDP1
** to 21 FPS, and its capacities grew the shared bank buffers enough to take
** the .bss gap from 39 KB to 7 KB. Missing scenery during a fly-through is
** the cheaper problem. tools/build_cutscene_scene.py is kept for a mesh that
** is actually cheap enough; nothing builds one today.
*/

/*
** The bank a CS_START_SEQ asks for, or NULL when we have not built it.
**
** NULL is honest silence: the cutscene leaves whatever is playing alone rather
** than substituting an unrelated theme. NA_BGM_OPENING_GANON is the one still
** missing -- its sequence uses percussion the score builder cannot bake.
*/
static const music_bank_t *bank_for_cutscene(unsigned int bank)
{
    switch (bank) {
        case CUTSCENE_BANK_NAVI:      return (&music_bank_navi);
        case CUTSCENE_BANK_DEKU_TREE: return (&music_bank_deku_tree);
        default:                      return ((const music_bank_t *)0);
    }
}

static int16_t read_be16(const unsigned char *p)
{
    return (int16_t)((uint16_t)p[0] << 8 | p[1]);
}

static bool load_track(const cutscene_t *cs)
{
    void        *data;
    int          length = 0;
    unsigned int i;
    unsigned char *bytes;

    data = jo_fs_read_file(cs->track_file, &length);
    if (!data || length != (int)cs->frames * CUTSCENE_TRACK_BYTES) {
        if (data)
            jo_free(data);
        return (false);
    }
    state.track = (cutscene_point_t *)jo_malloc(
        cs->frames * sizeof(cutscene_point_t));
    if (!state.track) {
        jo_free(data);
        return (false);
    }
    bytes = (unsigned char *)data;
    for (i = 0; i < cs->frames; ++i) {
        unsigned char *p = bytes + i * CUTSCENE_TRACK_BYTES;
        state.track[i].x = read_be16(p + 0);
        state.track[i].y = read_be16(p + 2);
        state.track[i].z = read_be16(p + 4);
        state.track[i].yaw = read_be16(p + 6);
        state.track[i].pitch = read_be16(p + 8);
        state.track[i].roll = read_be16(p + 10);
        state.track[i].fov = read_be16(p + 12);
    }
    jo_free(data);
    return (true);
}

bool cutscene_start(unsigned int id)
{
    const cutscene_t *cs;

    if (id >= CUTSCENE_COUNT)
        return (false);
    if (state.track) {
        jo_free(state.track);
        state.track = 0;
    }
    message_stop();
    cs = &cutscenes[id];
    state.active = false;
    state.finished = false;
    state.id = (unsigned char)id;
    state.frame = 0;
    state.text_cursor = 0;
    state.music_cursor = 0;
    state.text_hold_end = 0;
    /* Start covered. The opening's first transition is a fade OUT from black,
    ** so the frames before it are black in the original too. */
    state.fade_alpha = 255;
    state.fade_colour = CUTSCENE_FADE_BLACK;
    /* The opening starts in silence. link_home's cutscene layer is
    ** SCENE_CMD_SOUND_SETTINGS(..., NA_BGM_GENERAL_SFX) -- ambience only -- so
    ** the title theme stops here rather than playing on under the narration.
    ** Later beats start their own cue through CS_START_SEQ. */
    if (id == CUTSCENE_SLEEP)
        music_silence(CUTSCENE_FADE_FRAMES);
    game_mode_set(GAME_MODE_LOADING);
    if (cs->scene == CUTSCENE_SCENE_SPOT00) {
        state.scene_loaded = kokiri_scene_load_bank(CUTSCENE_FIELD_BANK, 0);
        /* The riders load after the bank, into the VDP1 space it leaves empty
        ** and the cart RAM nothing else wants. Failing to load them costs the
        ** shot its riders, not the cutscene. */
        if (state.scene_loaded)
            cutscene_actors_load();
    } else {
        cutscene_actors_free();
        int scene = scene_for_cutscene(cs->scene);

        state.scene_loaded = scene >= 0 &&
                             scene_flow_load((unsigned int)scene, 0);
    }
    if (!load_track(cs))
        return (false);
    game_mode_set(GAME_MODE_CUTSCENE);
    state.active = true;
    return (true);
}

/*
** The screen fill for this frame, from the cutscene's CS_TRANSITION list.
**
** Straight from z_demo.c:1550-1574, where lerp runs 0..1 across the
** transition's frames:
**
**   FILL_IN        alpha = 255 * lerp            ends opaque
**   FILL_OUT       alpha = 255 * (1 - lerp)      starts opaque, clears
**   OUT_TO_HALF    alpha = 255 - 155 * lerp      255 -> 100
**   IN_FROM_HALF   alpha = 255 - 155 * (1-lerp)  100 -> 255
**
** Before the first transition and after the last, the fill holds at whatever
** that transition implies rather than snapping to clear: a cutscene that opens
** with a FILL_OUT is on screen *because* the screen is already filled, which
** is exactly the case in the sleep cutscene -- its first transition is at
** frame 55, and the 55 frames before it are black in the original.
**
** Integer only: lerp is applied as a numerator over the transition's length.
*/
static void update_fade(const cutscene_t *cs)
{
    unsigned int    i;
    unsigned int    alpha = 0;
    unsigned char   colour = CUTSCENE_FADE_BLACK;
    bool            have = false;

    for (i = 0; i < cs->fade_count; ++i) {
        const cutscene_fade_t *fade = &cs->fades[i];
        int span = fade->end - fade->start;
        int into = (int)state.frame - fade->start;
        int lerp_num, lerp_den;

        if (into < 0) {
            /* Not reached yet. Only the FIRST pending transition decides what
            ** is on screen now, and only if it expects to start opaque. */
            if (!have) {
                if (fade->direction == CUTSCENE_FADE_OUT ||
                    fade->direction == CUTSCENE_FADE_OUT_HALF) {
                    alpha = 255;
                    colour = fade->colour;
                }
                have = true;
            }
            continue;
        }
        /* A zero-length transition applies its end state immediately. */
        lerp_den = span > 0 ? span : 1;
        lerp_num = span > 0 ? (into < span ? into : span) : 1;
        colour = fade->colour;
        have = true;
        switch (fade->direction) {
            case CUTSCENE_FADE_IN:
                alpha = (unsigned int)(255 * lerp_num / lerp_den);
                break;
            case CUTSCENE_FADE_OUT:
                alpha = (unsigned int)(255 - 255 * lerp_num / lerp_den);
                break;
            case CUTSCENE_FADE_OUT_HALF:
                alpha = (unsigned int)(255 - 155 * lerp_num / lerp_den);
                break;
            case CUTSCENE_FADE_IN_HALF:
                alpha = (unsigned int)(255 - 155 * (lerp_den - lerp_num)
                                       / lerp_den);
                break;
            default:            /* CUTSCENE_FADE_INSTANT */
                alpha = 255;
                break;
        }
    }
    state.fade_alpha = (unsigned char)alpha;
    state.fade_colour = colour;
}

static void apply_camera(const cutscene_point_t *point)
{
    demo_camera.x = point->x;
    demo_camera.y = point->y;
    demo_camera.z = point->z;
    demo_yaw = (uint16_t)point->yaw;
    demo_pitch = point->pitch;
}

static void step_events(const cutscene_t *cs, bool confirm)
{
    while (state.text_cursor < cs->text_count &&
           cs->text[state.text_cursor].start <= (short)state.frame) {
        unsigned short id = cs->text[state.text_cursor].id;
        if (id) {
            message_start(id);
            state.text_hold_end = cs->text[state.text_cursor].end;
        } else {
            message_stop();
        }
        ++state.text_cursor;
    }
    while (state.music_cursor < cs->music_count &&
           cs->music[state.music_cursor].start <= (short)state.frame) {
        const cutscene_music_t *music = &cs->music[state.music_cursor];
        const music_bank_t *bank = bank_for_cutscene(music->bank);
        if (!music->stop && bank)
            music_fade_to(bank, CUTSCENE_FADE_FRAMES);
        ++state.music_cursor;
    }
    message_step(confirm);
}

bool cutscene_step(bool confirm)
{
    const cutscene_t *cs;

    state.finished = false;
    if (!state.active || state.id >= CUTSCENE_COUNT)
        return (false);
    cs = &cutscenes[state.id];
    if (state.frame < cs->frames)
        apply_camera(&state.track[state.frame]);
    update_fade(cs);
    step_events(cs, confirm);
    /*
    ** A cutscene waits for what it is saying.
    **
    ** Once the clock passes a text command's end frame, OoT holds it there
    ** while the box is still open -- literally csCtx->curFrame-- in
    ** z_demo.c:1787. Without this the Deku Tree's speech is still on screen
    ** while Navi has already set off through the forest, because the camera
    ** and the text were running on the same clock but only one of them waits
    ** for the player.
    */
    if (message_is_active() && (short)state.frame >= state.text_hold_end)
        return (true);
    if ((cs->destination >= 0 && state.frame >= (unsigned short)cs->destination_frame) ||
        (cs->stop_frame >= 0 && state.frame >= (unsigned short)cs->stop_frame) ||
        state.frame + 1 >= cs->frames) {
        unsigned int next = (unsigned int)cs->destination;
        state.active = false;
        state.finished = true;
        message_stop();
        if (cs->destination >= 0) {
            if (!cutscene_start(next))
                state.finished = true;
        } else {
            cutscene_actors_free();
            save_set_event_chk_inf(EVENTCHKINF_DEKU_TREE_INTRO_CS_SEEN);
        }
        return (state.active);
    }
    ++state.frame;
    return (true);
}

bool cutscene_is_playing(void)
{
    return (state.active);
}

bool cutscene_finished(void)
{
    bool out = state.finished;
    state.finished = false;
    return (out);
}

/*
** The player cue running on this frame, or NULL.
**
** Cues do not overlap in the opening, so the first one whose window contains
** the frame is the one in force.
*/
static const cutscene_cue_t *current_cue(void)
{
    const cutscene_t *cs;
    unsigned int      i;

    if (!state.active || state.id >= CUTSCENE_COUNT)
        return ((const cutscene_cue_t *)0);
    cs = &cutscenes[state.id];
    for (i = 0; i < cs->cue_count; ++i) {
        const cutscene_cue_t *cue = &cs->cues[i];

        if ((short)state.frame >= cue->start && (short)state.frame < cue->end)
            return (cue);
    }
    return ((const cutscene_cue_t *)0);
}

/* How far through the current cue we are, as a 0..256 fraction. */
static int cue_progress(const cutscene_cue_t *cue)
{
    int span = cue->end - cue->start;
    int into = (int)state.frame - cue->start;

    if (span <= 0)
        return (0);
    if (into < 0)
        into = 0;
    if (into > span)
        into = span;
    return (into * 256 / span);
}

static int cue_lerp(int from, int to, int progress)
{
    return (from + (to - from) * progress / 256);
}

/* The cue running on `channel` this frame, or NULL. */
static const cutscene_cue_t *current_actor_cue(unsigned int channel)
{
    const cutscene_t *cs;
    unsigned int      i;

    if (!state.active || state.id >= CUTSCENE_COUNT)
        return ((const cutscene_cue_t *)0);
    cs = &cutscenes[state.id];
    for (i = 0; i < cs->actor_cue_count; ++i) {
        const cutscene_cue_t *cue = &cs->actor_cues[i];

        if (cue->clip == channel &&
            (short)state.frame >= cue->start && (short)state.frame < cue->end)
            return (cue);
    }
    return ((const cutscene_cue_t *)0);
}

unsigned int cutscene_actor_channels(void)
{
    const cutscene_t *cs;
    unsigned int      i, highest = 0;

    if (!state.active || state.id >= CUTSCENE_COUNT)
        return (0);
    cs = &cutscenes[state.id];
    for (i = 0; i < cs->actor_cue_count; ++i)
        if (cs->actor_cues[i].clip + 1u > highest)
            highest = cs->actor_cues[i].clip + 1u;
    return (highest);
}

bool cutscene_actor_channel_visible(unsigned int channel)
{
    return (current_actor_cue(channel) != (const cutscene_cue_t *)0);
}

int32_t cutscene_actor_channel_x(unsigned int channel)
{
    const cutscene_cue_t *cue = current_actor_cue(channel);

    return (cue ? cue_lerp(cue->x, cue->ex, cue_progress(cue)) : 0);
}

int32_t cutscene_actor_channel_y(unsigned int channel)
{
    const cutscene_cue_t *cue = current_actor_cue(channel);

    return (cue ? cue_lerp(cue->y, cue->ey, cue_progress(cue)) : 0);
}

int32_t cutscene_actor_channel_z(unsigned int channel)
{
    const cutscene_cue_t *cue = current_actor_cue(channel);

    return (cue ? cue_lerp(cue->z, cue->ez, cue_progress(cue)) : 0);
}

uint16_t cutscene_actor_channel_yaw(unsigned int channel)
{
    const cutscene_cue_t *cue = current_actor_cue(channel);

    return (cue ? cue->yaw : 0);
}

bool cutscene_link_visible(void)
{
    const cutscene_cue_t *cue = current_cue();

    return (cue && cue->clip != CUTSCENE_CLIP_HOLD);
}

int32_t cutscene_link_x(void)
{
    const cutscene_cue_t *cue = current_cue();

    return (cue ? cue_lerp(cue->x, cue->ex, cue_progress(cue)) : 0);
}

int32_t cutscene_link_y(void)
{
    const cutscene_cue_t *cue = current_cue();

    return (cue ? cue_lerp(cue->y, cue->ey, cue_progress(cue)) : 0);
}

int32_t cutscene_link_z(void)
{
    const cutscene_cue_t *cue = current_cue();

    return (cue ? cue_lerp(cue->z, cue->ez, cue_progress(cue)) : 0);
}

uint16_t cutscene_link_yaw(void)
{
    const cutscene_cue_t *cue = current_cue();

    return (cue ? cue->yaw : 0);
}

unsigned int cutscene_link_clip(void)
{
    const cutscene_cue_t *cue = current_cue();

    if (!cue)
        return (LINK_CLIP_IDLE);
    switch (cue->clip) {
        case CUTSCENE_CLIP_SLEEPING:  return (LINK_CLIP_SLEEPING);
        case CUTSCENE_CLIP_TURN_OVER: return (LINK_CLIP_TURN_OVER);
        case CUTSCENE_CLIP_SIT_UP:    return (LINK_CLIP_SIT_UP);
        case CUTSCENE_CLIP_STAND_UP:  return (LINK_CLIP_STAND_UP);
        case CUTSCENE_CLIP_TURN_LOOK: return (LINK_CLIP_TURN_LOOK);
        default:                      return (LINK_CLIP_IDLE);
    }
}

unsigned int cutscene_link_frame(void)
{
    const cutscene_cue_t *cue = current_cue();
    unsigned int          count;
    unsigned int          frame;

    if (!cue)
        return (0);
    count = link_clips[cutscene_link_clip()].count;
    if (!count)
        return (0);
    /* Play the clip once across the cue rather than looping it: a sit-up that
    ** restarted halfway would have Link lie back down. The sleeping pose is
    ** the exception -- it is a breathing loop, so it wraps. */
    frame = (unsigned int)cue_progress(cue) * count / 256;
    if (cue->clip == CUTSCENE_CLIP_SLEEPING)
        return (frame % count);
    return (frame >= count ? count - 1 : frame);
}

unsigned int cutscene_fade_alpha(void)
{
    return (state.active ? state.fade_alpha : 0);
}

unsigned int cutscene_fade_colour(void)
{
    return (state.fade_colour);
}

bool cutscene_hides_scene(void)
{
    /* Nothing of the world can show through a full-strength fill, and the
    ** scenes the opening asks for are not all extracted yet, so a cutscene
    ** whose scene could not be loaded stays covered rather than showing
    ** whichever scene happened to be resident. */
    return (state.active &&
            (state.fade_alpha >= 255 || !state.scene_loaded));
}

unsigned int cutscene_id(void)
{
    return (state.id);
}

unsigned int cutscene_frame(void)
{
    return (state.frame);
}
