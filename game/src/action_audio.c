/* Music owns 0..23, actions 24..30, Navi 31. No CD reads in play. */
#include <jo/jo.h>
#include "action_audio.h"
#include "action_audio_data.h"
#include "opening_audio_data.h"
#include "gameplay.h"
#include "music.h"

#define SLOT(s,o) (*(volatile unsigned short *)(0x25b00000UL + (s)*32 + (o)))
static volatile bool ready;
static bool opening_bank;
static unsigned int voice;
static volatile bool rupee_active;
static volatile unsigned int rupee_clock, rupee_note;
static unsigned int sound_refresh;
static volatile bool navi_flying;
static volatile unsigned int navi_frequency;
static unsigned int navi_note_clock, navi_env_clock, navi_env_tick;
static bool navi_first_envelope;
static void rupee_vblank(void);
static void navi_vblank(void);

static bool load_pcm(const char *name, unsigned int bytes)
{
    jo_file file;
    unsigned short buffer[256];
    unsigned int offset = 0, i;
    volatile unsigned short *ram = (volatile unsigned short *)0x25a00000UL;
    ready = false;
    navi_flying = false;
    if (ACTION_PCM_BASE < MUSIC_SAMPLE_LIMIT ||
        ACTION_PCM_BASE + bytes > 0x80000 ||
        !jo_fs_open(&file, name)) return false;
    if ((unsigned int)file.size != bytes) { jo_fs_close(&file); return false; }
    while (offset < bytes) {
        unsigned int count = bytes - offset;
        if (count > sizeof(buffer)) count = sizeof(buffer);
        if (jo_fs_read_next_bytes(&file, (char *)buffer, count) != (int)count) {
            jo_fs_close(&file); return false;
        }
        for (i = 0; i < count/2; ++i)
            ram[(ACTION_PCM_BASE + offset)/2+i] = buffer[i];
        offset += count;
    }
    jo_fs_close(&file);
    for (i = 24; i < 32; ++i) { SLOT(i,0) = 0; SLOT(i,12) = 255; }
    voice = 0;
    rupee_active = false;
    ready = true;
    return true;
}

bool action_audio_init(void)
{
    opening_bank = false;
    if (!load_pcm("ACTIONS.PCM", ACTION_PCM_BYTES)) return false;
    sound_refresh = (JO_VDP2_TVSTAT & 1) ? 50 : 60;
    if (!jo_core_add_vblank_callback(rupee_vblank)) return false;
    ready = true;
    return true;
}

bool action_audio_set_opening(bool opening)
{
    unsigned int i;
    rupee_active = false;
    navi_flying = false;
    for (i = 24; i < 32; ++i) { SLOT(i,12) = 255; SLOT(i,0) = 0x1000; }
    if (opening == opening_bank && ready) return true;
    if (!load_pcm(opening ? "OPENING.PCM" : "ACTIONS.PCM",
                  opening ? OPENING_PCM_BYTES : ACTION_PCM_BYTES)) return false;
    opening_bank = opening;
    return true;
}

static void play_sample(unsigned int id, unsigned int slot, unsigned int pitch,
                        unsigned int level, bool loop)
{
    const action_pcm_t *sample;
    unsigned int address, key;
    if (!ready || id >= (opening_bank ? OPENING_PCM_COUNT : ACTION_PCM_COUNT)) return;
    sample = opening_bank ? &opening_pcm[id] : &action_pcm[id];
    address = ACTION_PCM_BASE + sample->offset;
    SLOT(slot,0) = 0x1000; /* key off old one-shot before retrigger */
    SLOT(slot,12) = 255;
    key = 0x0010 | (loop ? 0x0020 : 0) | ((address >> 16) & 15);
    SLOT(slot,0) = key;
    SLOT(slot,2) = address & 65535;
    SLOT(slot,4) = 0;
    SLOT(slot,6) = sample->length;
    SLOT(slot,8) = 31;
    SLOT(slot,10) = 31;
    SLOT(slot,14) = 0;
    SLOT(slot,16) = pitch;
    SLOT(slot,18) = 0;
    SLOT(slot,20) = 0;
    SLOT(slot,22) = 7 << 13;
    SLOT(slot,12) = level;
    SLOT(slot,0) = key | 0x1800;
}

void action_audio_opening_play(unsigned int sound, unsigned int channel, bool loop)
{
    if (!opening_bank || channel >= 7) return;
    play_sample(sound, 24 + channel, 13 << 11,
                sound == OPENING_RAIN ? 52 : 18, loop);
}

void action_audio_opening_stop(unsigned int channel)
{
    if (!opening_bank || channel >= 7) return;
    SLOT(24 + channel,12) = 255;
    SLOT(24 + channel,0) = 0x1000;
}

static void play(unsigned int id, unsigned int slot)
{
    unsigned int octave = (id >= ACTION_VOICE0 && id <= ACTION_VOICE3) ? 13 : 14;
    play_sample(id, slot, octave << 11, 12, false);
}

void action_audio_navi_dash(void)
{
    play_sample(opening_bank ? OPENING_DASH : ACTION_NAVI_DASH,
                26, 13 << 11, 0, false);
}

void action_audio_navi_flight(unsigned int speed, bool active)
{
    unsigned int scale;
    if (!ready) return;
    if (!active || !opening_bank) {
        navi_flying = false;
        SLOT(31,12) = 255; SLOT(31,0) = 0x1000;
        return;
    }
    if (speed > 30) speed = 30;
    /* ObjectKankyo_Fairies -> func_800F436C: speed changes frequency, not
     * volume. arg=0.6+0.4*min(cameraTravel/30,1), then the low-end mapping. */
    scale = 614 + speed * 410 / 30;
    navi_frequency = scale < 768 ? 512 + scale / 3 : scale;
    if (navi_flying) return;
    navi_note_clock = navi_env_clock = navi_env_tick = 0;
    navi_first_envelope = true;
    play_sample(OPENING_NAVI_FLY, 31, 14 << 11, 255, true);
    SLOT(31,4) = NAVI_FLY_LOOP_START;
    navi_flying = true;
}

static void navi_vblank(void)
{
    unsigned int ratio, index, amplitude, phase;
    int octave = 0;
    if (!ready || !navi_flying) return;
    /* Sequence 0: 120 BPM, 48 ticks/beat, repeated 32-tick legato note.
     * The sample stays keyed on; only pitch/envelope registers change. */
    index = navi_note_clock * 128 / (32 * sound_refresh);
    ratio = (navi_fly_pitch[index] * navi_frequency) >> 10;
    while (ratio < 65536) { ratio <<= 1; --octave; }
    SLOT(31,16) = ((octave & 15) << 11) | ((ratio - 65536) >> 6);
    navi_note_clock = (navi_note_clock + 96) % (32 * sound_refresh);
    /* ENVELOPE_67D8: 400 audio updates to 32700, 400 to 20000, repeat.
     * NTSC audio uses three synthesis updates per 60 Hz frame. */
    phase = navi_env_tick;
    if (phase < 400) {
        unsigned int start = navi_first_envelope ? 0 : 20000;
        amplitude = start + (32700 - start) * phase / 400;
    } else amplitude = 32700 - 12700 * (phase - 400) / 400;
    /* CHAN_2582 note velocity 50: OoT squares velocity / 127 before
     * multiplying the envelope (seqplayer.c / effects.c). */
    amplitude = amplitude * (50u * 50u) / (127u * 127u);
    SLOT(31,12) = navi_fly_level[amplitude >> 8];
    navi_env_clock += 180;
    navi_env_tick += navi_env_clock / sound_refresh;
    navi_env_clock %= sound_refresh;
    if (navi_env_tick >= 800) { navi_env_tick -= 800; navi_first_envelope = false; }
}

static void rupee_start(void)
{
    if (!ready || music_busy()) return;
    rupee_active = false; /* interrupt must not touch half-written slot setup */
    rupee_clock = rupee_note = 0;
    play_sample(ACTION_RUPEE,29,14 << 11,RUPEE_BED_LEVEL,false);
    play_sample(ACTION_RUPEE_WAVE,30,rupee_pitches[0],rupee_levels[0],true);
    rupee_active = true;
}

static void rupee_vblank(void)
{
    unsigned int tick, previous, start, age;
    navi_vblank();
    if (!ready || !rupee_active) return;
    if (music_busy()) {
        SLOT(30,12) = 255;
        SLOT(30,0) = 0x1000;
        rupee_active = false;
        return;
    }
    /* 120 BPM * 48 sequence ticks/beat = 96 ticks/sec, PAL or NTSC.
     * IRQ writes only resident SCSP registers: no allocation or disc reads. */
    rupee_clock += RUPEE_TICKS_PER_SECOND;
    tick = rupee_clock / sound_refresh;
    previous = rupee_note;
    while (rupee_note < RUPEE_NOTE_COUNT && tick >= rupee_ends[rupee_note])
        ++rupee_note;
    if (rupee_note == RUPEE_NOTE_COUNT) {
        SLOT(30,12) = 255;
        SLOT(30,0) = 0x1000;
        rupee_active = false;
        return;
    }
    start = rupee_note ? rupee_ends[rupee_note-1] : 0;
    age = tick - start;
    if (age > 23) age = 23;
    if (previous != rupee_note)
        play_sample(ACTION_RUPEE_WAVE,30,rupee_pitches[rupee_note],rupee_levels[age],true);
    else
        SLOT(30,12) = rupee_levels[age];
}

void action_audio_events(uint32_t events)
{
    if (opening_bank) return;
    if (events & GP_EVENT_SWING) {
        play(ACTION_SWING, 24);
        play(ACTION_VOICE0 + (voice++ & 3), 25);
    }
    if (events & GP_EVENT_RUPEE) rupee_start();
    if (events & GP_EVENT_CUT) play(ACTION_CUT, 26);
    if (events & GP_EVENT_SHIELD_UP) play(ACTION_SHIELD, 24);
    if (events & GP_EVENT_JUMP) play(ACTION_JUMP, 25);
    if (events & GP_EVENT_ROLL_VOICE) play(ACTION_VOICE0 + (voice++ & 3), 25);
    if (events & GP_EVENT_ROLL) play(ACTION_ROLL, 28);
    else if (events & GP_EVENT_FOOTSTEP) play(ACTION_FOOTSTEP, 28);
    if (events & (GP_EVENT_PICKUP | GP_EVENT_EQUIP)) play(ACTION_EQUIP, 27);
    else if (events & (GP_EVENT_TALK_OPEN | GP_EVENT_TALK_PAGE | GP_EVENT_TALK_CLOSE |
                       GP_EVENT_MENU_OPEN | GP_EVENT_MENU_CLOSE | GP_EVENT_MENU_MOVE))
        play(ACTION_MESSAGE, 27);
}
