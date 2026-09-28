/* SCSP score player. See music.h for what a bank is and why only one fits.
 * Jo's stock audio module must stay disabled: this player owns SCSP slots.
 * Sample upload uses word writes and a small staging buffer, not the heap
 * sized for a whole 480 KB sample bank. No CD reads occur in the interrupt.
 */
#include <jo/jo.h>
#include "music.h"

#define REG(o) (*(volatile unsigned short *)(0x25b00000UL + (o)))
#define SLOT(s,o) REG((s)*32+(o))
/* Red Book input: the CD's left/right (EXTS0/1) reach the mix through
** slots 16/17's EFSDL/EFPAN (low byte of register 0x16). Every write of
** that register keeps them at full level, hard left/right, or a CD track
** would be muted whenever those two music voices play. */
#define CD_SEND(s) ((s) == 16 ? ((menu_duck ? 6 : 7)<<5) | 0x1F : (s) == 17 ? ((menu_duck ? 6 : 7)<<5) | 0x0F : 0)
#define MUSIC_MAX_VOICES 24
#define VOLUME_MAX       15
/* Default half-fade length; music_fade_to() takes an explicit one. */
#define FADE_DEFAULT     15
#define LOAD_CHUNK       8192          /* staging buffer, word-copied to SCSP */
#define LOAD_PER_FRAME   4             /* chunks per rendered frame: 32 KB */

enum { MUSIC_IDLE, MUSIC_FADE_OUT, MUSIC_SWAP, MUSIC_FADE_IN };

static const music_bank_t *bank;
static const music_bank_t *incoming;
static unsigned char *levels, *pending_levels;
/* 0 none, 1 envelopes pending, 2 envelopes done and PCM to follow. */
static volatile unsigned char swap_stage;
static unsigned short frame, cursor, keys[MUSIC_MAX_VOICES];
static bool active[MUSIC_MAX_VOICES];
static unsigned char voice_levels[MUSIC_MAX_VOICES];
static volatile unsigned int ticks, vblanks;
static unsigned int phase, refresh;
static volatile bool playing;
static volatile unsigned char state;
static volatile unsigned char volume = VOLUME_MAX;
static volatile bool menu_duck;
static unsigned int fade_step, fade_length = FADE_DEFAULT;
static unsigned int transition_start, transition_frames;
/* Switch measurements. audible_frames is request -> new bank actually playing;
 * transition_frames is request -> full volume. worst_stall is the longest gap
 * between successive music_service() calls during a switch, i.e. the longest
 * frame the streaming load cost. */
static unsigned int audible_frames, worst_stall, last_service, swap_count;

/* Swap progress, owned by music_service() on the main thread. */
static jo_file level_file;
static bool level_file_open;
static unsigned int level_offset;
static jo_file swap_file;
static bool swap_file_open;
static unsigned short *swap_staging;
static unsigned int swap_offset;
static bool swap_failed;

/* SCSP TL is 0.375 dB/step. Fade only the music slots: master volume also
 * controls resident effects, which must remain audible during silent scenes. */
static unsigned int faded_level(unsigned int level)
{
    static const unsigned char attenuation[16] =
        {255,63,47,37,31,25,21,18,15,12,9,7,5,3,2,0};
    unsigned int result = level + attenuation[volume] + (menu_duck ? 16u : 0u);
    return result > 255 ? 255 : result;
}

static void set_volume(unsigned int level)
{
    unsigned int i;
    volume = (unsigned char)level;
    for (i = 0; i < MUSIC_MAX_VOICES; ++i)
        if (active[i]) SLOT(i,12) = faded_level(voice_levels[i]);
}

void music_menu_duck(bool enabled)
{
    if (menu_duck == enabled) return;
    unsigned i;
    menu_duck = enabled;
    for (i=0; i<MUSIC_MAX_VOICES; ++i)
        if (active[i]) SLOT(i,12)=faded_level(voice_levels[i]);
    /* CD external sends use the same -6 dB step; preserve music direct sends. */
    SLOT(16,0x16) = (SLOT(16,0x16) & 0xFF00u) | CD_SEND(16);
    SLOT(17,0x16) = (SLOT(17,0x16) & 0xFF00u) | CD_SEND(17);
}

static void stop_all(void)
{
    unsigned int i;
    for (i = 0; i < MUSIC_MAX_VOICES; ++i) {
        SLOT(i,12) = 255;
        keys[i] &= ~0x0800;
        SLOT(i,0) = keys[i];
        active[i] = false;
    }
    SLOT(0,0) = keys[0] | 0x1000;
}

static void start_note(const music_trigger_t *event)
{
    unsigned int s = event->slot;
    const music_pcm_t *sample = &bank->pcm[event->sample];
    unsigned int address = bank->sample_base + sample->offset;
    SLOT(s,12) = 255;
    voice_levels[s] = 255;
    SLOT(s,0) = (keys[s] & ~0x0800) | 0x1000;
    keys[s] = 0x0020 | ((address>>16)&15);
    SLOT(s,0) = keys[s];
    SLOT(s,2) = address & 65535;
    SLOT(s,4) = sample->loop_start;
    SLOT(s,6) = sample->loop_end;
    SLOT(s,8) = 31;
    SLOT(s,10) = 31;
    SLOT(s,14) = 0;
    SLOT(s,16) = event->pitch;
    SLOT(s,18) = 0;
    SLOT(s,20) = 0;
    SLOT(s,22) = (7<<13) | (event->pan<<8) | CD_SEND(s);
    keys[s] |= 0x0800;
    SLOT(s,0) = keys[s] | 0x1000;
    active[s] = true;
}

static void score_tick(void)
{
    unsigned int i;
    if (frame == bank->frames) {
        stop_all();
        frame = (unsigned short)bank->loop_frame;
        cursor = 0;
        while (cursor < bank->trigger_count && bank->triggers[cursor].frame < frame)
            ++cursor;
    }
    while (cursor < bank->trigger_count && bank->triggers[cursor].frame == frame)
        start_note(&bank->triggers[cursor++]);
    /* Envelopes are released early during a switch so the incoming set can
    ** load while the outgoing bank is still fading. Voices then hold their
    ** last level, which the master-volume ramp is already taking down. */
    if (levels)
        for (i = 0; i < bank->voices; ++i)
            if (active[i]) {
                voice_levels[i] = levels[frame * bank->voices + i];
                SLOT(i,12) = faded_level(voice_levels[i]);
            }
    ++frame;
    ++ticks;
}

static void music_vblank(void)
{
    ++vblanks;
    /* The fade is a master-volume ramp, cheap enough for the interrupt. The
     * bank swap it triggers is NOT done here: no CD reads or allocation. */
    if (state == MUSIC_FADE_OUT || state == MUSIC_FADE_IN) {
        if (fade_step) {
            --fade_step;
            set_volume(state == MUSIC_FADE_OUT
                       ? fade_step * VOLUME_MAX / fade_length
                       : VOLUME_MAX - fade_step * VOLUME_MAX / fade_length);
        }
        if (!fade_step) {
            if (state == MUSIC_FADE_OUT) {
                set_volume(0);
                playing = false;
                stop_all();
                state = MUSIC_SWAP;      /* main thread picks this up */
            } else {
                set_volume(VOLUME_MAX);
                state = MUSIC_IDLE;
                transition_frames = vblanks - transition_start;
            }
        }
    }
    if (!playing) return;
    phase += 60;
    while (phase >= refresh) {
        phase -= refresh;
        score_tick();
    }
}

/* Upload one staged chunk to sound RAM as words, as the initial load does. */
static void upload(const unsigned short *source, unsigned int base,
                   unsigned int offset, unsigned int bytes)
{
    volatile unsigned short *ram = (volatile unsigned short *)0x25a00000UL;
    unsigned int i;
    for (i = 0; i < bytes / 2; ++i)
        ram[(base + offset) / 2 + i] = source[i];
}

static unsigned char *read_levels(const music_bank_t *target)
{
    int length = 0;
    unsigned char *loaded = (unsigned char *)jo_fs_read_file(target->level_file,
                                                             &length);
    if (!loaded) return JO_NULL;
    if ((unsigned int)length != target->level_bytes) {
        jo_free(loaded);
        return JO_NULL;
    }
    return loaded;
}

/*
** Fade out and stay silent.
**
** A cutscene beat can genuinely have no music: the opening's sleep layer is
** SCENE_CMD_SOUND_SETTINGS(..., NA_BGM_GENERAL_SFX), which is ambience only,
** so the title theme has to stop rather than play on under the narration.
**
** Shares the fade-out ramp with music_fade_to(); it differs only in having no
** incoming bank, so the vblank half ends at silence and the main thread frees
** the outgoing bank and goes idle.
*/
bool music_silence(unsigned int fade_frames)
{
    if (state != MUSIC_IDLE || !bank)
        return (false);
    incoming = JO_NULL;
    fade_length = fade_frames ? fade_frames : 1;
    transition_start = vblanks;
    transition_frames = 0;
    fade_step = fade_length;
    swap_stage = 1;
    audible_frames = 0;
    worst_stall = 0;
    last_service = vblanks;
    state = MUSIC_FADE_OUT;
    return (true);
}

bool music_fade_to(const music_bank_t *target, unsigned int fade_frames)
{
    if (!target || target->sample_base > MUSIC_SAMPLE_LIMIT ||
        target->pcm_bytes > MUSIC_SAMPLE_LIMIT - target->sample_base ||
        target->voices > MUSIC_MAX_VOICES ||
        state != MUSIC_IDLE || bank == target) return false;
    incoming = target;
    fade_length = fade_frames ? fade_frames : 1;
    transition_start = vblanks;
    transition_frames = 0;
    fade_step = fade_length;
    swap_stage = 1;
    audible_frames = 0;
    worst_stall = 0;
    last_service = vblanks;
    state = MUSIC_FADE_OUT;
    return true;
}

/*
** Main-thread half of the transition: free the outgoing bank and stream the
** incoming one into sound RAM a few chunks per rendered frame. Called every
** frame; does nothing unless a swap is pending.
*/
void music_service(void)
{
    unsigned int chunk;

    /* Called once per rendered frame, so the gap between calls is the frame
     * time; the largest one during a switch is the worst stall it caused. */
    if (state != MUSIC_IDLE || swap_stage) {
        unsigned int now = vblanks, gap = now - last_service;
        if (gap > worst_stall) worst_stall = gap;
        last_service = now;
    }

    /* No incoming bank: music_silence(). The fade-out has already stopped the
    ** voices, so all that is left is to drop the outgoing envelopes and go
    ** idle -- there is nothing to stream in. */
    if (swap_stage && !incoming) {
        if (state == MUSIC_SWAP) {
            unsigned char *outgoing = levels;

            levels = JO_NULL;         /* the vblank stops reading it here */
            if (outgoing) jo_free(outgoing);
            bank = JO_NULL;
            swap_stage = 0;
            state = MUSIC_IDLE;
            transition_frames = vblanks - transition_start;
        }
        return;
    }

    if (swap_stage == 1) {
        /* Off the critical path: the envelope file goes to the heap, not sound
        ** RAM, so it loads while the outgoing bank is still fading. Releasing
        ** the outgoing set first also keeps the two (112 KB + 74 KB) from
        ** having to coexist in the arena this build configures.
        **
        ** Streamed in the same chunks as the PCM. Reading it in one call cost
        ** a single 266-366 ms frame, which is the whole stall a switch used to
        ** produce; the total is CD-bound either way, so spreading it is free. */
        int got;
        if (!level_file_open) {
            unsigned char *outgoing = levels;
            levels = JO_NULL;             /* the vblank stops reading it here */
            if (outgoing) jo_free(outgoing);
            pending_levels = jo_malloc(incoming->level_bytes);
            if (!pending_levels) {
                swap_failed = true; swap_stage = 0; set_volume(VOLUME_MAX);
                state = MUSIC_IDLE; return;
            }
            if (!jo_fs_open(&level_file, incoming->level_file) ||
                (unsigned int)level_file.size != incoming->level_bytes) {
                if (level_file.size) jo_fs_close(&level_file);
                jo_free(pending_levels); pending_levels = JO_NULL;
                swap_failed = true; swap_stage = 0; set_volume(VOLUME_MAX);
                state = MUSIC_IDLE; return;
            }
            level_offset = 0;
            level_file_open = true;
        }
        for (chunk = 0; chunk < LOAD_PER_FRAME &&
                        level_offset < incoming->level_bytes; ++chunk) {
            unsigned int want = incoming->level_bytes - level_offset;
            if (want > LOAD_CHUNK) want = LOAD_CHUNK;
            got = jo_fs_read_next_bytes(&level_file,
                                        (char *)pending_levels + level_offset,
                                        want);
            if (got != (int)want) {
                jo_fs_close(&level_file); level_file_open = false;
                jo_free(pending_levels); pending_levels = JO_NULL;
                swap_failed = true; swap_stage = 0; set_volume(VOLUME_MAX);
                state = MUSIC_IDLE; return;
            }
            level_offset += (unsigned int)got;
        }
        if (level_offset < incoming->level_bytes) return;
        jo_fs_close(&level_file);
        level_file_open = false;
        swap_stage = 2;
        return;
    }

    if (state != MUSIC_SWAP) return;

    if (!swap_file_open) {
        if (!jo_fs_open(&swap_file, incoming->pcm_file)) {
            swap_failed = true; swap_stage = 0; set_volume(VOLUME_MAX); state = MUSIC_IDLE; return;
        }
        if ((unsigned int)swap_file.size != incoming->pcm_bytes ||
            incoming->sample_base + incoming->pcm_bytes > 0x80000) {
            jo_fs_close(&swap_file); swap_failed = true; swap_stage = 0; set_volume(VOLUME_MAX);
            state = MUSIC_IDLE; return;
        }
        swap_staging = jo_malloc(LOAD_CHUNK);
        if (!swap_staging) {
            jo_fs_close(&swap_file); swap_failed = true; swap_stage = 0; set_volume(VOLUME_MAX);
            state = MUSIC_IDLE; return;
        }
        swap_offset = 0;
        swap_file_open = true;
    }

    for (chunk = 0; chunk < LOAD_PER_FRAME && swap_offset < incoming->pcm_bytes;
         ++chunk) {
        unsigned int want = incoming->pcm_bytes - swap_offset;
        int got;
        if (want > LOAD_CHUNK) want = LOAD_CHUNK;
        got = jo_fs_read_next_bytes(&swap_file, (char *)swap_staging, want);
        if (got != (int)want || (got & 1)) {
            jo_fs_close(&swap_file); jo_free(swap_staging);
            swap_staging = JO_NULL; swap_file_open = false;
            swap_failed = true; swap_stage = 0; set_volume(VOLUME_MAX); state = MUSIC_IDLE;
            return;
        }
        upload(swap_staging, incoming->sample_base, swap_offset, (unsigned int)got);
        swap_offset += (unsigned int)got;
    }

    if (swap_offset < incoming->pcm_bytes) return;   /* more next frame */

    jo_fs_close(&swap_file);
    jo_free(swap_staging);
    swap_staging = JO_NULL;
    swap_file_open = false;

    bank = incoming;
    levels = pending_levels;
    pending_levels = JO_NULL;
    swap_stage = 0;
    frame = cursor = 0;
    phase = 0;
    audible_frames = vblanks - transition_start;
    ++swap_count;
    playing = true;
    fade_step = fade_length;
    state = MUSIC_FADE_IN;
}

bool music_init(const music_bank_t *first)
{
    jo_file file;
    unsigned short *staging;
    unsigned int offset = 0, i;
    volatile unsigned short *ram = (volatile unsigned short *)0x25a00000UL;
    int got;

    if (!first || first->sample_base > MUSIC_SAMPLE_LIMIT ||
        first->pcm_bytes > MUSIC_SAMPLE_LIMIT - first->sample_base ||
        first->voices > MUSIC_MAX_VOICES) return false;
    bank = first;
    levels = read_levels(bank);
    if (!levels) return false;
    if (!jo_fs_open(&file, bank->pcm_file)) { jo_free(levels); return false; }
    if ((unsigned int)file.size != bank->pcm_bytes ||
        bank->sample_base + (unsigned int)file.size > MUSIC_SAMPLE_LIMIT) {
        jo_fs_close(&file); jo_free(levels); return false;
    }
    staging = jo_malloc(LOAD_CHUNK);
    if (!staging) { jo_fs_close(&file); jo_free(levels); return false; }

    /* Use SGL SMPC requests, never install a libyaul interrupt handler.
     * Restart the idle 68000 before the slow CD upload, as in the baseline. */
    slSoundOffWait();
    REG(0x400) = 0x0200;
    REG(0x41e) = 0;
    REG(0x42a) = 0;
    for (i = 0; i < 0x400; i += 2) REG(i) = 0;
    for (i = 0; i < 32; ++i) { SLOT(i,12) = 255; SLOT(i,10) = 31; }
    SLOT(16,22) = CD_SEND(16);
    SLOT(17,22) = CD_SEND(17);
    SLOT(0,0) = 0x1000;
    for (i = 0; i < 0x200; i += 2) { ram[i] = 0; ram[i+1] = 0x0400; }
    ram[1] = 0x0ff0;
    ram[0x200] = 0x46fc; ram[0x201] = 0x2700; ram[0x202] = 0x60fe;
    slSoundOnWait();
    while (offset < bank->pcm_bytes) {
        unsigned int want = bank->pcm_bytes - offset;
        if (want > LOAD_CHUNK) want = LOAD_CHUNK;
        got = jo_fs_read_next_bytes(&file, (char *)staging, want);
        if (got != (int)want || (got & 1)) {
            jo_fs_close(&file); jo_free(staging); jo_free(levels); return false;
        }
        upload(staging, bank->sample_base, offset, (unsigned int)got);
        offset += (unsigned int)got;
    }
    jo_fs_close(&file);
    jo_free(staging);
    stop_all();
    frame = cursor = 0; ticks = phase = 0; vblanks = 0;
    state = MUSIC_IDLE;
    playing = true;
    refresh = (JO_VDP2_TVSTAT & 1) ? 50 : 60;
    if (!jo_core_add_vblank_callback(music_vblank)) {
        jo_free(levels); return false;
    }
    REG(0x400) = 0x0200 | VOLUME_MAX;
    set_volume(VOLUME_MAX);
    return true;
}

unsigned int music_audible_frames(void) { return audible_frames; }
unsigned int music_worst_stall(void) { return worst_stall; }
unsigned int music_swap_count(void) { return swap_count; }
unsigned int music_ticks(void) { return ticks; }
const music_bank_t *music_current(void) { return bank; }
bool music_busy(void) { return state != MUSIC_IDLE; }
bool music_failed(void) { return swap_failed; }
unsigned int music_transition_frames(void) { return transition_frames; }
