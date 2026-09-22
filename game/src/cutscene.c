#include <jo/jo.h>
#include "cutscene.h"
#include "demo.h"
#include "game_mode.h"
#include "message.h"
#include "music.h"
#include "music_banks.h"
#include "save_state.h"
#include "scene_flow.h"

typedef struct
{
    bool              active;
    bool              finished;
    unsigned char     id;
    unsigned short    frame;
    unsigned char     text_cursor;
    unsigned char     music_cursor;
    cutscene_point_t *track;
}                   cutscene_state_t;

static cutscene_state_t state;

#define CUTSCENE_FADE_FRAMES 10

static unsigned int scene_for_cutscene(unsigned int scene)
{
    switch (scene) {
    case CUTSCENE_SCENE_LINK_HOME: return SCENE_LINK_HOME;
    case CUTSCENE_SCENE_SPOT04:    return SCENE_SPOT04;
    default:                       return SCENE_LINK_HOME;
    }
}

static const music_bank_t *bank_for_cutscene(unsigned int bank)
{
    (void)bank;
    return (&music_bank_kokiri);
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
    game_mode_set(GAME_MODE_LOADING);
    scene_flow_load(scene_for_cutscene(cs->scene), 0);
    if (!load_track(cs))
        return (false);
    game_mode_set(GAME_MODE_CUTSCENE);
    state.active = true;
    return (true);
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
        if (id)
            message_start(id);
        else
            message_stop();
        ++state.text_cursor;
    }
    while (state.music_cursor < cs->music_count &&
           cs->music[state.music_cursor].start <= (short)state.frame) {
        const cutscene_music_t *music = &cs->music[state.music_cursor];
        if (!music->stop && music->bank != CUTSCENE_BANK_NONE)
            music_fade_to(bank_for_cutscene(music->bank), CUTSCENE_FADE_FRAMES);
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
    step_events(cs, confirm);
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

unsigned int cutscene_id(void)
{
    return (state.id);
}

unsigned int cutscene_frame(void)
{
    return (state.frame);
}
