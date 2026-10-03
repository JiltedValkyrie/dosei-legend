/* Music owns 0..23, actions 24..30, Navi 31. No CD reads in play. */
/* Event dispatch / bank setup: size-oriented, outside geometry and mixing loops. */
#ifdef __GNUC__
#pragma GCC optimize ("Os")
#endif
#include <jo/jo.h>
#include "action_audio.h"
#include "action_audio_data.h"
#include "opening_audio_data.h"
#include "gameplay.h"
#include "player_items.h"
#include "karebaba.h"
#include "game_over.h"
#include "music.h"

#define SLOT(s,o) (*(volatile unsigned short *)(0x25b00000UL + (s)*32 + (o)))
static volatile bool ready;
static bool opening_bank;
static unsigned int area_bank;          /* SFX bank index, 0 = none */
static bool area_ready;
static unsigned int voice;
static volatile bool rupee_active;
static volatile unsigned int rupee_clock, rupee_note;
static unsigned int sound_refresh;
static volatile bool navi_flying;
static volatile unsigned int navi_frequency;
static unsigned int navi_note_clock, navi_env_clock, navi_env_tick;
static bool navi_first_envelope;
static void rupee_vblank(void);
static bool load_area(void);
static void navi_vblank(void);

/* Copy one PCM file into sound RAM at `base`. Bounds: never below the music
** sample limit, never past the end of sound RAM. */
static bool upload(const char *name, unsigned int base, unsigned int bytes)
{
    jo_file file;
    unsigned short buffer[256];
    unsigned int offset = 0, i;
    volatile unsigned short *ram = (volatile unsigned short *)0x25a00000UL;
    if (base < MUSIC_SAMPLE_LIMIT || (base & 1) || base + bytes > 0x80000 ||
        !jo_fs_open(&file, name)) return false;
    if ((unsigned int)file.size != bytes) { jo_fs_close(&file); return false; }
    while (offset < bytes) {
        unsigned int count = bytes - offset;
        if (count > sizeof(buffer)) count = sizeof(buffer);
        if (jo_fs_read_next_bytes(&file, (char *)buffer, count) != (int)count) {
            jo_fs_close(&file); return false;
        }
        for (i = 0; i < count/2; ++i)
            ram[(base + offset)/2+i] = buffer[i];
        offset += count;
    }
    jo_fs_close(&file);
    return true;
}

static bool load_pcm(const char *name, unsigned int bytes)
{
    unsigned int i;
    ready = false;
    navi_flying = false;
    area_ready = false;                 /* whole region overwritten */
    if (!upload(name, ACTION_PCM_BASE, bytes)) return false;
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
    area_bank = 0;
    if (!load_area()) return false;
    sound_refresh = (JO_VDP2_TVSTAT & 1) ? 50 : 60;
    if (!jo_core_add_vblank_callback(rupee_vblank)) return false;
    ready = true;
    return true;
}

/* Area bank sits after the core. Bank 0 has no file. While the opening bank
** owns the region, only remember the choice; it loads when gameplay returns. */
static bool load_area(void)
{
    area_ready = false;
    if (opening_bank) return true;
    SLOT(26,12) = 255; SLOT(26,0) = 0x1000;     /* area one-shot slot */
    if (sfx_bank_file[area_bank] &&
        (sfx_bank_bytes[area_bank] > SFX_AREA_LIMIT ||
         !upload(sfx_bank_file[area_bank], SFX_AREA_BASE, sfx_bank_bytes[area_bank])))
        return false;
    area_ready = true;
    return true;
}

bool action_audio_set_area(unsigned int bank)
{
    if (bank >= SFX_BANK_COUNT) return false;
    if (bank == area_bank && (area_ready || opening_bank)) return true;
    area_bank = bank;
    return load_area();
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
    return opening || load_area();
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

/* One-shot at a note velocity: OoT mixes (velocity / 127)^2; SCSP TL is
** 0.375 dB a step, so `extra` = TL steps of that attenuation. */
static void play_level(unsigned int id, unsigned int slot, unsigned int extra)
{
    play_sample(id, slot, (unsigned int)action_pcm_octave[id < ACTION_PCM_COUNT ? id : 0] << 11,
                12 + extra, false);
}

static void play(unsigned int id, unsigned int slot)
{
    /* OCT from the stored rate: half-rate samples (voices, climb, shield,
    ** equip) play one octave down so they keep their pitch. */
    play_sample(id, slot, (unsigned int)action_pcm_octave[id < ACTION_PCM_COUNT ? id : 0] << 11,
                12, false);
}

/* Area one-shot: silent when the current area bank lacks the sound.
** `shift` is added to the sample's pitch register (OCT/FNS). */
static void play_area_pitch(unsigned int id, unsigned int slot, unsigned int shift);
static void play_area(unsigned int id, unsigned int slot)
{
    play_area_pitch(id, slot, 0);
}

static void play_area_pitch(unsigned int id, unsigned int slot, unsigned int shift)
{
    const action_pcm_t *sample;
    unsigned int address, key;
    if (!ready || opening_bank || !area_ready || id >= AREA_SFX_COUNT) return;
    sample = &sfx_bank_pcm[area_bank][id];
    if (!sample->length) return;
    address = SFX_AREA_BASE + sample->offset;
    SLOT(slot,0) = 0x1000;
    SLOT(slot,12) = 255;
    key = 0x0010 | ((address >> 16) & 15);
    SLOT(slot,0) = key;
    SLOT(slot,2) = address & 65535;
    SLOT(slot,4) = 0;
    SLOT(slot,6) = sample->length;
    SLOT(slot,8) = 31;
    SLOT(slot,10) = 31;
    SLOT(slot,14) = 0;
    SLOT(slot,16) = (unsigned short)(((unsigned int)area_sfx_octave[id] << 11) + shift);
    SLOT(slot,18) = 0;
    SLOT(slot,20) = 0;
    SLOT(slot,22) = 7 << 13;
    SLOT(slot,12) = 12;
    SLOT(slot,0) = key | 0x1800;
}

/* Kaleido Game Over prompts: PIECE_OF_HEART for Yes, DECIDE for No, CURSOR
** on a move. */
void action_audio_game_over(uint32_t ev)
{
    if (opening_bank) return;
    if (ev & GAME_OVER_EV_YES) play(ACTION_HEART_PIECE, 27);
    else if (ev & GAME_OVER_EV_DECIDE) play(ACTION_DECIDE, 27);
    else if (ev & GAME_OVER_EV_MOVE) play(ACTION_CURSOR, 27);
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
    play_sample(ACTION_RUPEE,29,(unsigned int)action_pcm_octave[ACTION_RUPEE] << 11,RUPEE_BED_LEVEL,false);
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
    uint32_t events2 = gameplay.events2;
    unsigned items = player_items_events();
    if (opening_bank) return;
    if (items & PLAYER_ITEM_FIRE) play(ACTION_SEED_FIRE, 28);
    if (items & PLAYER_ITEM_IMPACT) play(ACTION_SEED_IMPACT, 28);
    if (items & PLAYER_ITEM_FLASH) play(ACTION_NUT_FLASH, 28);
    /* Attention_Update: NA_SE_SY_LOCK_ON for an attention+hostile lock,
    ** NA_SE_SY_LOCK_ON_HUMAN otherwise. */
    if (events & GP_EVENT_TARGET_ON)
        play((events2 & GP2_EVENT_LOCK_HOSTILE) ? ACTION_LOCK_ON : ACTION_LOCK_ON_HUMAN, 29);
    /* Navi, slot 31 (the opening's flight loop is not live in gameplay). */
    if (events2 & GP2_EVENT_NAVI_HELLO) play(ACTION_NAVI_HELLO, 31);
    if (events2 & GP2_EVENT_NAVI_CALL) {
        /* CHAN_60F2: rand 3 over ARRAY_65A7, velocity 100/95/105 (TL 11,
        ** 13, 9); layer 1's INST_69 glide at velocity 65 (TL 31). */
        static const unsigned char tl[3] = { 11, 13, 9 };
        unsigned int take = (voice++) % 3;
        play_level(ACTION_NAVI_CALL0 + take, 31, tl[take]);
        play_level(ACTION_NAVI_CHIME, 30, 31);
    }
    if (events2 & GP2_EVENT_NAVI_TALK) play(ACTION_NAVI_TALK, 31);
    /* M2e: func_80837C0C NA_SE_PL_DAMAGE + NA_SE_VO_LI_DAMAGE_S_KID (rand 3);
    ** knockdown NA_SE_VO_LI_FALL_L_KID; func_80843E64 landing voice + original BODY_HIT;
    ** func_80836448 NA_SE_VO_LI_DOWN_KID; Health_IsCritical alarm. */
    if (events & GP_EVENT_HURT) {
        play(ACTION_PL_DAMAGE, 24);
        play(ACTION_HURT0 + (voice++ % 3), 25);
    }
    if (events & GP_EVENT_KNOCKDOWN) play(ACTION_FALL_L0, 25);
    if (events2 & GP2_EVENT_LAND_DAMAGE) {
        play(ACTION_BODY_HIT, 24);
        play(ACTION_LAND_HURT0, 25);
    }
    if (events2 & GP2_EVENT_DEATH) play(ACTION_DOWN, 25);
    if (events2 & GP2_EVENT_ALARM) play(ACTION_ALARM, 30);
    {
        /* En_Karebaba (forest area bank) and its stick pickup. One baba
        ** sound a step on slot 28; Enemy_StartFinishingBlow on 30. */
        uint32_t baba = gameplay.baba_events;
        gameplay.baba_events = 0; /* Other motion sounds can call us again this step. */
        if (baba & KAREBABA_EV_DEAD) play_area(AREA_SFX_BABA_DEAD, 28);
        else if (baba & KAREBABA_EV_GROUND) play_area(AREA_SFX_BABA_GROUND, 28);
        else if (baba & KAREBABA_EV_AWAKEN) play_area(AREA_SFX_BABA_AWAKEN, 28);
        else if (baba & KAREBABA_EV_MOUTH) play_area(AREA_SFX_BABA_MOUTH, 28);
        if (baba & KAREBABA_EV_LAST_DAMAGE) play(ACTION_LAST_DAMAGE, 30);
        /* func_8083E4C4: NA_SE_SY_GET_ITEM for a quiet (already owned) give. */
        if (baba & KAREBABA_EV_STICK) play(ACTION_GET_ITEM, 27);
    }
    if (events & GP_EVENT_SWING) {
        play(ACTION_SWING, 24);
        play(ACTION_VOICE0 + (voice++ & 3), 25);
    }
    if (events & GP_EVENT_RUPEE) rupee_start();
    if (events & GP_EVENT_CUT) play_area(AREA_SFX_CUT, 26);
    /* M2c combat, forest bank, slot 28 (footsteps: Link is not walking while
    ** swinging or guarding; 29/30 are the rupee). func_80842DF4: DIRT_SOFT (11) walls
    ** play NA_SE_IT_WALL_HIT_SOFT (same instrument, A3 against E2: one
    ** octave plus FNS for five semitones), others HARD. The shield bounce and
    ** a sword bounce play NA_SE_IT_SHIELD_REFLECT_SW's first layer. */
    if (events & GP_EVENT_WALL_HIT)
        play_area_pitch(AREA_SFX_WALL_HIT, 28,
                        gameplay.wall_material == 11 ? (1u << 11) + 343u : 0u);
    else if (events & (GP_EVENT_GUARD | GP_EVENT_REBOUND))
        play_area(AREA_SFX_REFLECT, 28);
    if (events & GP_EVENT_NUT_BREAK) play_area(AREA_SFX_NUT_BREAK, 28);
    if (events & GP_EVENT_SHIELD_UP) play(ACTION_SHIELD, 24);
    if (events & GP_EVENT_JUMP) play(ACTION_JUMP, 25);
    /* Ledge hop: NA_SE_VO_LI_SWORD_N_KID, the same four takes as a swing. */
    if (events & GP_EVENT_HOP_VOICE) play(ACTION_VOICE0 + (voice++ & 3), 25);
    /* CHAN_639A: rand 2 over ARRAY_63AB. */
    if (events & GP_EVENT_CLIMB_END) play(ACTION_CLIMB0 + (voice++ & 1), 25);
    if (events & GP_EVENT_ROLL_VOICE) play(ACTION_VOICE0 + (voice++ & 3), 25);
    if (events & GP_EVENT_ROLL) play(ACTION_ROLL, 28);
    else if (events & GP_EVENT_FOOTSTEP) play(ACTION_FOOTSTEP, 28);
    if (events2 & GP2_EVENT_HP_RECOVER) play(ACTION_HP_RECOVER, 27);
    else if (events2 & GP2_EVENT_GET_ITEM) play(ACTION_GET_ITEM, 27);
    else if (events & (GP_EVENT_PICKUP | GP_EVENT_EQUIP)) play(ACTION_EQUIP, 27);
    else if (events & (GP_EVENT_TALK_OPEN | GP_EVENT_TALK_PAGE | GP_EVENT_TALK_CLOSE |
                       GP_EVENT_MENU_OPEN | GP_EVENT_MENU_CLOSE | GP_EVENT_MENU_MOVE))
        play(ACTION_MESSAGE, 27);
    {
        static const unsigned char sounds[GP_SFX_COUNT] = {AREA_SFX_SCRUB_UP, AREA_SFX_SCRUB_DOWN, AREA_SFX_SCRUB_THROW, AREA_SFX_SCRUB_WALK, AREA_SFX_SCRUB_HIT, AREA_SFX_SCRUB_FAINT, AREA_SFX_FOOT_SWITCH, AREA_SFX_DEKU_HIT, AREA_SFX_DEKU_DEAD, AREA_SFX_SKULL_HIT, AREA_SFX_SKULL_DEAD, AREA_SFX_LARVA_HIT, AREA_SFX_LARVA_DEAD, AREA_SFX_GOHMA_HIT, AREA_SFX_GOHMA_DEAD, AREA_SFX_CORRECT, AREA_SFX_APPEAR, AREA_SFX_DOOR_OPEN, AREA_SFX_DOOR_CLOSE, AREA_SFX_FREEZE, AREA_SFX_BOX_ITEM};
        uint32_t pending=gameplay.world_sfx; unsigned i;
        gameplay.world_sfx=0;
        /* Scrub motion, switch clicks and combat use separate existing slots.
         * Later (death) events override hit/movement from the same step. */
        for(i=0;i<GP_SFX_COUNT;++i) if(pending & (1u<<i))
            play_area(sounds[i],i==GP_SFX_CORRECT || i==GP_SFX_APPEAR?30:i>=GP_SFX_DOOR_OPEN?26:i<GP_SFX_FOOT_SWITCH?26:i==GP_SFX_FOOT_SWITCH?27:28);
    }
}

void action_audio_tree_open(void) {play_area(AREA_SFX_TREE_OPEN,30);}

void action_audio_owl_flap(void){play_area(AREA_SFX_OWL_FLAP,26);}

/* Decomp sfxIds (include/tables/sfx/<bank>_table.h) the oot-core actors play. */
void action_audio_decomp_sfx(unsigned int sfx_id)
{
    switch (sfx_id) {
    case 0x284E: play_area(AREA_SFX_CUT, 26); break;   /* NA_SE_EV_PLANT_BROKEN */
    case 0x4803: rupee_start(); break;                 /* NA_SE_SY_GET_RUPY */
    case 0x4824: play(ACTION_GET_ITEM, 27); break;     /* NA_SE_SY_GET_ITEM */
    case 0x480B: play(ACTION_HP_RECOVER, 27); break;   /* NA_SE_SY_HP_RECOVER */
    case 0x4818:                                       /* NA_SE_SY_MESSAGE_PASS */
    case 0x482E:                                       /* NA_SE_SY_MESSAGE_END */
    case 0x4808:                                       /* NA_SE_SY_DECIDE */
    case 0x4809: play(ACTION_MESSAGE, 27); break;      /* NA_SE_SY_CURSOR */
    default: break;
    }
}
