/* Music owns slots 0..23. Resident actions own 24..30, no CD reads in play. */
#include <jo/jo.h>
#include "action_audio.h"
#include "action_audio_data.h"
#include "gameplay.h"
#include "music.h"

#define SLOT(s,o) (*(volatile unsigned short *)(0x25b00000UL + (s)*32 + (o)))
static volatile bool ready;
static unsigned int voice;
static volatile bool rupee_active;
static volatile unsigned int rupee_clock, rupee_note;
static unsigned int sound_refresh;
static void rupee_vblank(void);

bool action_audio_init(void)
{
    jo_file file;
    unsigned short buffer[256];
    unsigned int offset = 0, i;
    volatile unsigned short *ram = (volatile unsigned short *)0x25a00000UL;
    ready = false;
    if (ACTION_PCM_BASE < MUSIC_SAMPLE_LIMIT ||
        ACTION_PCM_BASE + ACTION_PCM_BYTES > 0x80000 ||
        !jo_fs_open(&file, "ACTIONS.PCM")) return false;
    if (file.size != ACTION_PCM_BYTES) { jo_fs_close(&file); return false; }
    while (offset < ACTION_PCM_BYTES) {
        unsigned int count = ACTION_PCM_BYTES - offset;
        if (count > sizeof(buffer)) count = sizeof(buffer);
        if (jo_fs_read_next_bytes(&file, (char *)buffer, count) != (int)count) {
            jo_fs_close(&file); return false;
        }
        for (i = 0; i < count/2; ++i)
            ram[(ACTION_PCM_BASE + offset)/2+i] = buffer[i];
        offset += count;
    }
    jo_fs_close(&file);
    for (i = 24; i < 31; ++i) { SLOT(i,0) = 0; SLOT(i,12) = 255; }
    voice = 0;
    rupee_active = false;
    sound_refresh = (JO_VDP2_TVSTAT & 1) ? 50 : 60;
    if (!jo_core_add_vblank_callback(rupee_vblank)) return false;
    ready = true;
    return true;
}

static void play_sample(unsigned int id, unsigned int slot, unsigned int pitch,
                        unsigned int level, bool loop)
{
    const action_pcm_t *sample;
    unsigned int address, key;
    if (!ready || id >= ACTION_PCM_COUNT || music_busy()) return;
    sample = &action_pcm[id];
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

static void play(unsigned int id, unsigned int slot)
{
    play_sample(id, slot, 14 << 11, 12, false); /* 11025 Hz one-shot */
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
