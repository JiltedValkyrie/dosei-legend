#pragma GCC optimize ("Os") /* Cold 20 Hz script player; preserve high-RAM headroom. */
#include <jo/jo.h>
#include "asset_loading.h"
#include "cutscene.h"
#include "demo.h"
#include "tree_mouth.h"
#include "emerald_story.h"
#include "story_route.h"
#include "game_mode.h"
#include "link_clips.h"
#include "message.h"
#include "music.h"
#include "music_banks.h"
#include "music_songs.h"
#include "save_state.h"
#include "scene_flow.h"
#include "kokiri_sgl.h"
#include "cutscene_actor.h"
#include "npc_draw.h"
#include "action_audio.h"
#include "vdp1_draw_wait.h"
#include "kokiri_camera.h"

typedef struct
{
    bool              active;
    bool              finished;
    bool              skip_finish;
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
    /* True when the cutscene was entered from inside its own scene, as
    ** En_Sa does for Saria's greeting: it installs the script into
    ** csCtx.script and sets cutsceneTrigger instead of the scene header
    ** starting it (z_en_sa.c EnSa_Init). Nothing is loaded or unloaded --
    ** the room, its streamed textures, the action sound bank and the
    ** playing music all stay exactly as gameplay left them. */
    bool              in_scene;
    cutscene_point_t *track;
    const cutscene_cue_t *player_cue;
    const cutscene_cue_t *actor_cues[10];
    int32_t actor_pos[10][3];
    int32_t navi_pos[3], navi_velocity[3];
    /* En_Elf's own hover, func_80A02A20: the cue gives Navi a path, the
    ** orbit around it is what makes her circle and bob on it. */
    uint16_t navi_orbit_xz, navi_orbit_y;
    unsigned short applied_frame;
    unsigned char rain, flash;
    short bridge_start;
    unsigned char scenery_bank;
    unsigned short sound_frame;
    short sound_bridge_angle;
    int32_t sound_navi_y;
    bool sound_hooves, sound_navi_falling;
    int32_t sound_eye[3];
    bool sound_eye_valid;
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
** Navi's flight uses S2R0..9, built from the ordinary streamed room meshes.
** Each bank covers 100 camera frames, keeping the room textures that can
** enter fog range and flat fog-coloured geometry beyond it. Source trees
** and huts therefore survive shots that look across a gameplay room portal.
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
        case CUTSCENE_BANK_NIGHTMARE: return music_song_bank(NA_BGM_OPENING_GANON);
        case CUTSCENE_BANK_NAVI:      return music_song_bank(NA_BGM_NAVI_OPENING);
        case CUTSCENE_BANK_STONE: return music_song_bank(NA_BGM_SPIRITUAL_STONE);
        case CUTSCENE_BANK_FAIRYGET: return music_song_bank(NA_BGM_OCA_FAIRY_GET);
        case CUTSCENE_BANK_KOKIRI: return music_song_bank(NA_BGM_KOKIRI);
        case CUTSCENE_BANK_DEKU_TREE: return music_song_bank(NA_BGM_DEKU_TREE_CS);
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
        state.track[i].dist = read_be16(p + 12);
    }
    jo_free(data);
    return (true);
}

static const cutscene_t *cutscene_reset(unsigned int id)
{
    const cutscene_t *cs;

    if (id >= CUTSCENE_COUNT)
        return ((const cutscene_t *)0);
    if (state.track) {
        jo_free(state.track);
        state.track = 0;
    }
    message_stop();
    cs = &cutscenes[id];
    state.active = false;
    state.finished = false;
    state.skip_finish = false;
    state.id = (unsigned char)id;
    state.frame = 0;
    state.applied_frame = 0;
    state.rain = state.flash = 0;
    state.bridge_start = -1;
    state.scenery_bank = 0;
    state.sound_frame = 65535;
    state.sound_bridge_angle = -16384;
    state.sound_navi_y = 0;
    state.sound_eye_valid = false;
    state.sound_hooves = state.sound_navi_falling = false;
    state.player_cue = 0;
    { unsigned int axis; for (axis = 0; axis < 3; ++axis)
        state.navi_pos[axis] = state.navi_velocity[axis] = 0; }
    state.navi_orbit_xz = state.navi_orbit_y = 0;
    {
        unsigned int i;
        for (i = 0; i < 10; ++i) {
            state.actor_cues[i] = 0;
            state.actor_pos[i][0] = state.actor_pos[i][1] = state.actor_pos[i][2] = 0;
        }
    }
    state.text_cursor = 0;
    state.music_cursor = 0;
    state.text_hold_end = 0;
    state.in_scene = false;
    /* Start covered. The opening's first transition is a fade OUT from black,
    ** so the frames before it are black in the original too. */
    state.fade_alpha = 255;
    state.fade_colour = CUTSCENE_FADE_BLACK;
    return (cs);
}

bool cutscene_start(unsigned int id)
{
    const cutscene_t *cs = cutscene_reset(id);

    if (!cs)
        return (false);
    kokiri_opening_cache_free();
    npc_draw_free();
    story_route_free();
    emerald_story_free();
    /* The opening starts in silence. link_home's cutscene layer is
    ** SCENE_CMD_SOUND_SETTINGS(..., NA_BGM_GENERAL_SFX) -- ambience only -- so
    ** the title theme stops here rather than playing on under the narration.
    ** Later beats start their own cue through CS_START_SEQ. */
    if (id == CUTSCENE_SLEEP || id == CUTSCENE_NIGHTMARE)
        music_silence(CUTSCENE_FADE_FRAMES);
    asset_loading("CUTSCENE SCENE");
    game_mode_set(GAME_MODE_LOADING);
    if(id>=CUTSCENE_EMERALD1 && id<=CUTSCENE_EMERALD9) {
        static const unsigned char banks[]={20,21,21,23,23,25,26,21,28};
        cutscene_actors_free();
        state.scene_loaded=kokiri_scene_load_bank(banks[id-CUTSCENE_EMERALD1],0);
        if(!state.scene_loaded || !emerald_story_load(id-CUTSCENE_EMERALD1+1))return false;
    } else if (cs->scene == CUTSCENE_SCENE_SPOT00) {
        state.scene_loaded = kokiri_scene_load_bank(CUTSCENE_FIELD_BANK, 0);
        /* The riders load after the bank, into the VDP1 space it leaves empty
        ** and the cart RAM nothing else wants. Failing to load them costs the
        ** shot its riders, not the cutscene. */
        if (state.scene_loaded)
            cutscene_actors_load();
    } else if (cs->scene == CUTSCENE_SCENE_SPOT04) {
        cutscene_actors_free();
        if (!kokiri_opening_cache_load()) return false;
        state.scene_loaded = kokiri_scene_load_bank(2, 0);
        if (state.scene_loaded && id == CUTSCENE_NAVI_FLY)
            state.scene_loaded = npc_draw_load_navi();
    } else if (cs->scene == CUTSCENE_SCENE_LINK_HOME) {
        cutscene_actors_free();
        /* Moving house cameras use SKYBOX_HOUSE_LINK, not the fixed JPEG. */
        state.scene_loaded = kokiri_scene_load_bank(4, 0);
    } else {
        cutscene_actors_free();
        int scene = scene_for_cutscene(cs->scene);

        state.scene_loaded = scene >= 0 &&
                             scene_flow_load((unsigned int)scene, 0);
    }
    asset_loading(cs->track_file);
    if (!load_track(cs))
        return (false);
    asset_loading("OPENING.PCM");
    if (!action_audio_set_opening(true)) return false;
    asset_loading_done();
    game_mode_set(GAME_MODE_CUTSCENE);
    state.active = true;
    return (true);
}

/*
** Start a cutscene inside the scene that is already running.
**
** En_Sa's greeting is the case this exists for: EnSa_Init points
** play->csCtx.script at gKokiriForestSariaGreetingCs and sets cutsceneTrigger,
** and z_demo begins playback on the next frame. No scene is loaded, no room
** is swapped, and the scene's own BGM keeps playing -- the greeting script has
** no CS_START_SEQ or CS_STOP_SEQ at all.
**
** So this deliberately skips everything cutscene_start does around the track:
** the cache frees, the scene bank load, the OPENING.PCM swap and the LOADING
** screen. Only the baked camera track is read from the disc. Failure leaves
** gameplay exactly as it was rather than dropping into a half-loaded scene.
*/
bool cutscene_start_in_scene(unsigned int id)
{
    const cutscene_t *cs = cutscene_reset(id);

    if (!cs)
        return (false);
    if (!load_track(cs))
        return (false);
    state.in_scene = true;
    state.scene_loaded = true;
    /* Nothing covers an in-scene cutscene: it cuts straight from gameplay,
    ** and its script carries no CS_TRANSITION to clear a black screen with. */
    state.fade_alpha = 0;
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

        /* z_demo.c: CS_TRANS_TRIGGER_INSTANCE sets transitionControl=1.
         * It does not set screenFillColor/alpha. Treating it as an opaque
         * fill blacked out the Deku Tree throughout his speech. */
        if (fade->direction == CUTSCENE_FADE_TRIGGER) continue;

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
            default:
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

static void step_sounds(void)
{
    unsigned int i;
    if (state.sound_frame == state.frame) {
        if (state.id == CUTSCENE_NAVI_FLY) action_audio_navi_flight(0, true);
        return; /* held text is not a new cue */
    }
    state.sound_frame = state.frame;
    if(state.id==CUTSCENE_EMERALD9 && state.frame==783)
        action_audio_opening_play(OPENING_TREE_DEATH,2,false);
    if (state.id == CUTSCENE_NIGHTMARE) {
        /* EnViewer_UpdateImpl, scene layer 4: the original shot-cut accents. */
        static const unsigned short cuts[] = {20,59,71,129,140,219,280,320,380,409,438};
        const cutscene_cue_t *horse = state.actor_cues[0];
        const cutscene_cue_t *ganon = state.actor_cues[1];
        int angle = cutscene_bridge_angle();
        bool hooves = horse && state.frame <= horse->end &&
                      (horse->x != horse->ex || horse->z != horse->ez);
        if (!state.frame) action_audio_opening_play(OPENING_RAIN, 0, true);
        for (i = 0; i < sizeof(cuts)/sizeof(cuts[0]); ++i)
            if (state.frame == cuts[i]) action_audio_opening_play(OPENING_CUT, 1, false);
        /* Pair the lightning flashes, so the second flash does not restart
         * the same thunder tail a fraction of a second later. */
        if (state.frame == 20 || state.frame == 163 || state.frame == 370)
            action_audio_opening_play(OPENING_THUNDER, 2, false);
        if (angle > -16384 && state.sound_bridge_angle == -16384)
            action_audio_opening_play(OPENING_BRIDGE, 3, true);
        if (angle == 0 && state.sound_bridge_angle < 0) {
            action_audio_opening_stop(3);
            action_audio_opening_play(OPENING_BRIDGE_STOP, 3, false);
        }
        state.sound_bridge_angle = (short)angle;
        if (hooves != state.sound_hooves) {
            if (hooves) action_audio_opening_play(OPENING_HOOVES, 4, true);
            else action_audio_opening_stop(4);
            state.sound_hooves = hooves;
        }
        /* The rearing cue begins at 361; EnViewer sounds source frames 8
         * and 30 before its animation update. */
        if (state.frame == 369) action_audio_opening_play(OPENING_NEIGH, 5, false);
        if (state.frame == 391) action_audio_opening_play(OPENING_HOOVES, 6, false);
        if (ganon && ganon->id == 2 && state.frame == (unsigned int)ganon->start + 25)
            action_audio_opening_play(OPENING_DUST, 6, false);
    } else if (state.id == CUTSCENE_NAVI_FLY) {
        int32_t eye[3] = {demo_camera.x, demo_camera.y, demo_camera.z};
        unsigned int sum = 0, speed = 0;
        for (i = 0; i < 3; ++i) {
            int delta = state.sound_eye_valid ? eye[i] - state.sound_eye[i] : 0;
            if (delta < 0) delta = -delta;
            if (delta > 30) delta = 30;
            sum += delta * delta;
            state.sound_eye[i] = eye[i];
        }
        state.sound_eye_valid = true;
        while (speed < 30 && (speed + 1) * (speed + 1) <= sum) ++speed;
        action_audio_navi_flight(speed, true);
    } else if (state.id == CUTSCENE_WAKE_UP) {
        const cutscene_cue_t *navi = state.actor_cues[8];
        int32_t y = state.actor_pos[8][1];
        bool falling = y < state.sound_navi_y;
        /* EnElf: entrance frame 55, then each downward turn while waking Link. */
        if (state.frame == 55 || (navi && navi->id == 3 && falling && !state.sound_navi_falling))
            action_audio_navi_dash();
        state.sound_navi_y = y;
        state.sound_navi_falling = falling;
    }
}

static void step_events(const cutscene_t *cs, bool confirm)
{
    while (state.text_cursor < cs->text_count &&
           cs->text[state.text_cursor].start <= (short)state.frame) {
        /* A following NONE/text command may start exactly at hold_end.
         * Do not erase the current page before the clock can hold it. */
        if (message_is_active()) break;
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

        /* A scene can reach its cue while the previous score still fades.
         * Keep the cue pending: the player refuses switches while busy. */
        if (bank && music_busy()) break;
        if (music->stop) {
            /* CS_STOP_SEQ. Only silence what is actually playing: the stop
            ** names a sequence, and if a later cue has already replaced it
            ** there is nothing to stop. */
            if (bank && (music_current() == bank ||
                         (state.id==CUTSCENE_EMERALD1 && music->start==0)))
                music_silence(CUTSCENE_FADE_FRAMES);
        } else if (bank) {
            if(music_fade_to(bank, CUTSCENE_FADE_FRAMES)) {
                if(music->bank==CUTSCENE_BANK_FAIRYGET)music_once(bank,music_song_bank(NA_BGM_KOKIRI));
                else if(music->bank==CUTSCENE_BANK_STONE)music_once(bank,music_song_bank(NA_BGM_DEKU_TREE_CS));
            }
        }
        ++state.music_cursor;
    }
    message_step(confirm);
}

static void update_cues(const cutscene_t *cs);

static void finish_cutscene(const cutscene_t *cs)
{
    unsigned int next = (unsigned int)cs->destination;
    if (state.in_scene && (state.id==CUTSCENE_TREE_MEETING || state.id==CUTSCENE_TREE_CHOICE)) {
        tree_mouth_prepare_choice();
        unsigned branch=message_choice() ? CUTSCENE_TREE_AGAIN : CUTSCENE_TREE_OPEN;
        if(cutscene_start_in_scene(branch)) {
            if(branch==CUTSCENE_TREE_OPEN)save_set_event_chk_inf(EVENTCHKINF_DEKU_TREE_MOUTH_OPEN);
            return;
        }
    }
    state.active = false;
    state.finished = true;
    message_stop();
    if (cs->destination >= 0) {
        if (!cutscene_start(next))
            state.finished = true;
    } else if (state.in_scene) {
        /* The scene, its textures, the action sound bank and the music were
        ** never disturbed, so there is nothing to restore: hand control back.
        ** The EVENTCHKINF below belongs to the opening chain and must not be
        ** set by an in-scene cutscene. The caller owns its own flag, the way
        ** EnSa_BecomeIdle owns INFTABLE_SARIA_GREETED_LINK. */
        if (state.track) { jo_free(state.track); state.track = 0; }
        /* in_scene stays set: the caller reads it on the frame it sees
        ** cutscene_finished(), to know gameplay is still standing behind the
        ** cutscene and must not be reloaded. cutscene_reset clears it. */
        game_mode_set(GAME_MODE_PLAY);
    } else {
        cutscene_actors_free();
        emerald_story_free();
        asset_loading("ACTIONS.PCM");
        if (!action_audio_set_opening(false))
            jo_core_error("Action sound bank reload failed");
        asset_loading_done();
        save_set_event_chk_inf(EVENTCHKINF_DEKU_TREE_INTRO_CS_SEEN);
    }
}

static void update_misc(const cutscene_t *cs)
{
    unsigned int i;
    (void)cs;
    if (state.flash > 10) state.flash -= 10; else state.flash = 0;
    for (i = 0; i < CUTSCENE_MISC_COUNT; ++i) {
        const cutscene_misc_t *event = &cutscene_misc[i];
        if (event->scene != state.id || state.frame != event->start) continue;
        if (event->kind == 0) state.rain = 20;
        else if (event->kind == 1) state.flash = 100;
        else if (event->kind == 2) state.bridge_start = state.frame;
    }
}

unsigned int cutscene_shot_key(void)
{
    unsigned int i, start = 0;
    const cutscene_t *cs;
    if (!state.active) return ~0u;
    cs = &cutscenes[state.id];
    for (i = 0; i < cs->shot_count; ++i)
        if (cs->shots[i] <= state.applied_frame) start = cs->shots[i];
    return ((unsigned int)state.id << 16) | start;
}

void cutscene_skip_shot(void)
{
    const cutscene_t *cs;
    unsigned int i, target;
    bool last_shot = true;
    if (!state.active) return;
    cs = &cutscenes[state.id];
    target = cs->frames - 1;
    if (cs->stop_frame >= 0 && (unsigned int)cs->stop_frame < target)
        target = cs->stop_frame;
    if (cs->destination >= 0 && cs->destination_frame >= 0 &&
        (unsigned int)cs->destination_frame < target)
        target = cs->destination_frame;
    for (i = 0; i < cs->shot_count; ++i)
        if (cs->shots[i] > state.applied_frame && cs->shots[i] < target) {
            target = cs->shots[i];
            last_shot = false;
            break;
        }
    message_stop();
    /* Discard skipped dialogue, not dialogue starting at the destination. */
    while (state.text_cursor < cs->text_count &&
           cs->text[state.text_cursor].start < (short)target)
        ++state.text_cursor;
    /* Advance persistent actor/misc state without intermediate CD loads,
     * sound bursts or dialogue. Navi's easing needs each source tick. */
    while (state.frame < target) {
        update_misc(cs);
        update_cues(cs);
        ++state.frame;
    }
    if (last_shot) {
        /* Let pending score switches settle before chaining to a script
         * without music commands (wake-up inherits Navi's opening theme). */
        state.text_cursor = cs->text_count;
        state.skip_finish = true;
        cutscene_step(false);
        return;
    }
    for (i = 0; i < 7; ++i) action_audio_opening_stop(i);
    state.sound_hooves = false;
    state.sound_eye_valid = false;
    state.sound_frame = 65535;
    if (state.id == CUTSCENE_NIGHTMARE) {
        int angle;
        state.applied_frame = state.frame;
        angle = cutscene_bridge_angle();
        state.sound_bridge_angle = (short)angle;
        action_audio_opening_play(OPENING_RAIN, 0, true);
        if (angle > -16384 && angle < 0)
            action_audio_opening_play(OPENING_BRIDGE, 3, true);
    }
    /* Normal stepping applies the target camera, bank and remaining events,
     * or follows the normal chain/cleanup when this was the last shot. */
    cutscene_step(false);
}

bool cutscene_step(bool confirm)
{
    const cutscene_t *cs;

    state.finished = false;
    if (!state.active || state.id >= CUTSCENE_COUNT)
        return (false);
    cs = &cutscenes[state.id];
    /* Navi's flight streams a room bank per 100 camera frames. An in-scene
    ** cutscene plays in the room gameplay already has loaded; reloading bank 2
    ** under it would replace the live room's textures mid-shot. */
    if (cs->scene == CUTSCENE_SCENE_SPOT04 && !state.in_scene &&
        state.frame / 100 != state.scenery_bank) {
        /* Wait for the previous VDP1 draw before replacing its textures. */
        if (!vdp1_wait_for_draw_end()) return true;
        state.scenery_bank = (unsigned char)(state.frame / 100);
        state.scene_loaded = kokiri_scene_load_bank(2, state.scenery_bank);
    }
    if (state.frame < cs->frames)
        apply_camera(&state.track[state.frame]);
    update_misc(cs);
    state.applied_frame = state.frame;
    update_cues(cs);
    update_fade(cs);
    step_sounds();
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
    if (state.skip_finish && state.music_cursor < cs->music_count &&
        cs->music[state.music_cursor].start <= (short)state.frame)
        return true;
    if ((cs->destination >= 0 && state.frame >= (unsigned short)cs->destination_frame) ||
        (cs->stop_frame >= 0 && state.frame >= (unsigned short)cs->stop_frame) ||
        state.frame + 1 >= cs->frames) {
        finish_cutscene(cs);
        return (state.active);
    }
    ++state.frame;
    return (true);
}

bool cutscene_is_playing(void)
{
    return (state.active);
}

bool cutscene_is_in_scene(void)
{
    return (state.in_scene);
}

bool cutscene_finished(void)
{
    bool out = state.finished;
    state.finished = false;
    return (out);
}

/* z_demo retains cue pointers until the next script starts. */
static const cutscene_cue_t *current_cue(void)
{
    return state.active ? state.player_cue : 0;
}

static const cutscene_cue_t *current_actor_cue(unsigned int channel)
{
    return state.active && channel < 10 ? state.actor_cues[channel] : 0;
}


/*
** En_Elf's hover offset for the cutscene fairy (func_80A02A20), with the
** state func_80A0461C picks from the channel 8 cue id: 4 is state 9, 3 the
** wide bob she wakes Link with, 1 the still entrance. The cue path alone is
** motionless while she nags him at frames 250-350 -- this orbit is what
** actually moves her, and so what the source's downward-turn dash cue is
** measured from.
*/
static void navi_orbit(unsigned int cue_id, int32_t *offset)
{
    /* step_y, step_xz, amplitude_y, amplitude_xz */
    static const struct { unsigned short step_y, step_xz; short y, xz; }
        states[4] = {{0x0400, 0x0200,  5, 20},   /* no id: state 0 */
                     {0x0400, 0x0000,  5,  0},   /* id 1: state 10 */
                     {0x1000, 0x0800, 60, 20},   /* id 3: state 6 */
                     {0x1000, 0x0200,  3, 10}};  /* id 4: state 9 */
    unsigned int which = cue_id == 1 ? 1 : cue_id == 3 ? 2 : cue_id == 4 ? 3 : 0;
    int32_t sine, cosine;

    kokiri_camera_sincos(state.navi_orbit_xz, &sine, &cosine);
    offset[0] = (int32_t)(((int64_t)sine * states[which].xz * 256) >> 16);
    offset[2] = (int32_t)(((int64_t)cosine * states[which].xz * 256) >> 16);
    kokiri_camera_sincos(state.navi_orbit_y, &sine, &cosine);
    offset[1] = (int32_t)(((int64_t)sine * states[which].y * 256) >> 16);
    state.navi_orbit_xz = (uint16_t)(state.navi_orbit_xz + states[which].step_xz);
    state.navi_orbit_y = (uint16_t)(state.navi_orbit_y + states[which].step_y);
}

/* Last matching command wins; gaps retain the previous pointer and position. */
static void update_cues(const cutscene_t *cs)
{
    unsigned int i;
    for (i = 0; i < cs->cue_count; ++i) {
        const cutscene_cue_t *cue = &cs->cues[i];
        if (state.frame > cue->start && state.frame <= cue->end)
            state.player_cue = cue;
    }
    for (i = 0; i < cs->actor_cue_count; ++i) {
        const cutscene_cue_t *cue = &cs->actor_cues[i];
        if (cue->clip < 10 && state.frame > cue->start && state.frame <= cue->end)
            state.actor_cues[cue->clip] = cue;
    }
    for (i = 0; i < 10; ++i) {
        const cutscene_cue_t *cue = state.actor_cues[i];
        int span, into;
        if (i == 8 && cue) {
            int starts[3] = {cue->x, cue->y, cue->z};
            int ends[3] = {cue->ex, cue->ey, cue->ez};
            int32_t offset[3];
            unsigned int axis;
            navi_orbit(cue->id, offset);
            span = cue->end - cue->start;
            into = state.frame - cue->start;
            if (into > span) into = span;
            for (axis = 0; axis < 3; ++axis) {
                int32_t target = starts[axis] * 256 + offset[axis];
                int32_t velocity, change, step = axis == 1 ? 8192 : 384;
                if (span > 0) target += (int32_t)((int64_t)(ends[axis] - starts[axis]) * into * 256 / span);
                velocity = (target - state.navi_pos[axis]) / 5;
                if (velocity > 5120) velocity = 5120;
                if (velocity < -5120) velocity = -5120;
                change = velocity - state.navi_velocity[axis];
                if (change > step) change = step;
                if (change < -step) change = -step;
                state.navi_velocity[axis] += change;
                state.navi_pos[axis] += state.navi_velocity[axis];
                if (cue->id == 1 && axis != 1) {
                    state.navi_pos[axis] = target; state.navi_velocity[axis] = 0;
                }
                state.actor_pos[i][axis] = state.navi_pos[axis] / 256;
            }
            continue;
        }
        if (!cue || state.frame >= cue->end)
            continue; /* EnViewer stops before the end frame, not at endPos. */
        span = cue->end - cue->start;
        into = state.frame - cue->start;
        if (span <= 0) continue;
        state.actor_pos[i][0] = cue->x + (int32_t)((int64_t)(cue->ex - cue->x) * into / span);
        state.actor_pos[i][1] = cue->y + (int32_t)((int64_t)(cue->ey - cue->y) * into / span);
        state.actor_pos[i][2] = cue->z + (int32_t)((int64_t)(cue->ez - cue->z) * into / span);
    }
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
    return current_actor_cue(channel) ? state.actor_pos[channel][0] : 0;
}

int32_t cutscene_actor_channel_y(unsigned int channel)
{
    return current_actor_cue(channel) ? state.actor_pos[channel][1] : 0;
}

int32_t cutscene_actor_channel_z(unsigned int channel)
{
    return current_actor_cue(channel) ? state.actor_pos[channel][2] : 0;
}

/*
** The raw cue id for a channel.
**
** EnSa_HandleCutscene uses it as the index into sAnimationInfo1[] and gates
** its footstep sfx on id 3, so the actor needs the id itself, not a clip we
** have already mapped for Link.
*/
unsigned int cutscene_actor_channel_cue(unsigned int channel)
{
    const cutscene_cue_t *cue = current_actor_cue(channel);

    return (cue ? cue->id : 0);
}

uint16_t cutscene_actor_channel_yaw(unsigned int channel)
{
    const cutscene_cue_t *cue = current_actor_cue(channel);

    return (cue ? cue->yaw : 0);
}

bool cutscene_link_visible(void)
{
    const cutscene_cue_t *cue = current_cue();

    return (state.in_scene && state.id>=CUTSCENE_TREE_MEETING) || (cue && (cue->clip != CUTSCENE_CLIP_HOLD || state.id>=CUTSCENE_EMERALD1));
}

static int32_t link_position(unsigned axis)
{
    const cutscene_cue_t *cue=current_cue();
    int32_t base=axis==0?demo_link.x:axis==1?demo_link.y-DEMO_LINK_EYE_HEIGHT:demo_link.z;
    if(cue) {
        int32_t start=axis==0?cue->x:axis==1?cue->y:cue->z;
        int32_t end=axis==0?cue->ex:axis==1?cue->ey:cue->ez;
        if((state.id==CUTSCENE_TREE_MEETING || state.id==CUTSCENE_SARIA_BRIDGE || state.id>=CUTSCENE_EMERALD1) && cue->end>cue->start) {
            unsigned elapsed=state.applied_frame>cue->start?state.applied_frame-cue->start:0;
            unsigned span=cue->end-cue->start;
            if(elapsed>span)elapsed=span;
            return start+(end-start)*(int32_t)elapsed/(int32_t)span;
        }
        return start;
    }
    return state.in_scene?base:0;
}
int32_t cutscene_link_x(void) {return link_position(0);}
int32_t cutscene_link_y(void) {return link_position(1);}
int32_t cutscene_link_z(void) {return link_position(2);}

uint16_t cutscene_link_yaw(void)
{
    const cutscene_cue_t *cue = current_cue();

    return (cue ? cue->yaw : demo_link_yaw);
}

/* LinkAnimation advances 1.5 source frames per 20 Hz tick (R_UPDATE_RATE
 * times 0.5). Cue duration never stretches the animation. The two one-shot
 * bed movements hand over to their original wait loops when they finish. */
static void link_sample(unsigned int *clip, unsigned int *frame, unsigned int *fraction)
{
    const cutscene_cue_t *cue = current_cue();
    unsigned int elapsed, source, limit, stride, first, span;
    bool loop = false;
    *clip = LINK_CLIP_IDLE; *frame = *fraction = 0;
    if (!cue) return;
    switch (cue->clip) {
        case CUTSCENE_CLIP_SLEEPING: *clip = LINK_CLIP_SLEEPING; loop = true; break;
        case CUTSCENE_CLIP_TURN_OVER: *clip = LINK_CLIP_TURN_OVER; break;
        case CUTSCENE_CLIP_SIT_UP: *clip = LINK_CLIP_SIT_UP; break;
        case CUTSCENE_CLIP_STAND_UP: *clip = LINK_CLIP_STAND_UP; break;
        case CUTSCENE_CLIP_TURN_LOOK: *clip = LINK_CLIP_TURN_LOOK; break;
        case CUTSCENE_CLIP_OCARINA_START: *clip=LINK_CLIP_OCARINA_START;break;
        case CUTSCENE_CLIP_OCARINA_GET: *clip=LINK_CLIP_OCARINA_GET;break;
        case CUTSCENE_CLIP_RETURN_IDLE: *clip=LINK_CLIP_RETURN_IDLE;break;
        case CUTSCENE_CLIP_STEP_BACK: *clip=LINK_CLIP_STEP_BACK;break;
        case CUTSCENE_CLIP_STONE_GET2: *clip=LINK_CLIP_STONE_GET2;break;
        case CUTSCENE_CLIP_STONE_GET3: *clip=LINK_CLIP_STONE_GET3;break;
        case CUTSCENE_CLIP_STONE_STAND: *clip=LINK_CLIP_STONE_STAND;break;
        case CUTSCENE_CLIP_STONE_WAIT: *clip=LINK_CLIP_STONE_WAIT;break;

        default:
            if(cue->clip==CUTSCENE_CLIP_HOLD && (cue->x!=cue->ex || cue->z!=cue->ez) &&
               (state.id==CUTSCENE_SARIA_BRIDGE || state.id>=CUTSCENE_EMERALD1)) *clip=LINK_CLIP_RUN;
            loop = true; break;
    }
    elapsed = state.applied_frame > cue->start ? state.applied_frame - cue->start - 1 : 0;
    source = elapsed * 3 / 2;
    limit = link_clip_source_count[*clip];
    if ((*clip == LINK_CLIP_TURN_OVER || *clip == LINK_CLIP_SIT_UP) &&
        elapsed > ((limit - 1) * 2 + 2) / 3) {
        unsigned int end_tick = ((limit - 1) * 2 + 2) / 3 + 1;
        *clip = *clip == LINK_CLIP_TURN_OVER ? LINK_CLIP_SLEEP_WAIT2 : LINK_CLIP_SIT_WAIT3;
        source = (elapsed - end_tick) * 3 / 2;
        limit = link_clip_source_count[*clip];
        loop = true;
    }
    if(*clip==LINK_CLIP_OCARINA_START && source>=limit) {
        source-=limit;*clip=LINK_CLIP_OCARINA_HOLD;limit=link_clip_source_count[*clip];loop=true;
    }
    if (!limit) return;
    source = loop ? source % limit : (source >= limit ? limit - 1 : source);
    stride = link_clip_stride[*clip];
    *frame = source / stride;
    if (*frame >= link_clips[*clip].count - 1) {
        *frame = link_clips[*clip].count - 1;
        return;
    }
    first = *frame * stride;
    span = limit - 1 - first;
    if (span > stride) span = stride;
    if (span) *fraction = (source - first) * 256 / span;
}

unsigned int cutscene_link_clip(void)
{
    unsigned int clip, frame, fraction;
    link_sample(&clip, &frame, &fraction); return clip;
}

unsigned int cutscene_link_frame(void)
{
    unsigned int clip, frame, fraction;
    link_sample(&clip, &frame, &fraction); return frame;
}

unsigned int cutscene_link_fraction(void)
{
    unsigned int clip, frame, fraction;
    link_sample(&clip, &frame, &fraction); return fraction;
}

unsigned int cutscene_screen_distance(void)
{
    const cutscene_t *cs;

    if (!state.active || state.id >= CUTSCENE_COUNT || !state.track)
        return (0);
    cs = &cutscenes[state.id];
    if (state.frame >= cs->frames)
        return (0);
    return ((unsigned int)state.track[state.applied_frame].dist);
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
    return (state.applied_frame);
}

int16_t cutscene_camera_roll(void)
{
    return state.active && state.track ? state.track[state.applied_frame].roll : 0;
}

unsigned int cutscene_rain_count(void)
{
    unsigned int ramp = (state.applied_frame / 8 + 1) * 2;
    return !state.active ? 0 : (ramp < state.rain ? ramp : state.rain);
}
unsigned int cutscene_lightning(void) { return state.active ? state.flash : 0; }
int16_t cutscene_bridge_angle(void)
{
    int angle = -16384;
    if (state.bridge_start >= 0 && state.applied_frame > state.bridge_start)
        angle += (state.applied_frame - state.bridge_start) * 120;
    return angle < 0 ? angle : 0;
}
