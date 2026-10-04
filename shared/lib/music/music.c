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
#define STREAM_SECTORS   (LOAD_CHUNK / 2048) /* most sectors copied per frame */
#define STREAM_STALL     20            /* empty frames before restarting the drive */

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
static volatile bool cdda_muted;
static volatile unsigned char cdda_volume = VOLUME_MAX;
static volatile unsigned int cdda_restore;
static unsigned int fade_step, fade_length = FADE_DEFAULT;
static unsigned int transition_start, transition_frames;
/* Switch measurements. audible_frames is request -> new bank actually playing;
 * transition_frames is request -> full volume. worst_stall is the longest gap
 * between successive music_service() calls during a switch, i.e. the longest
 * frame the streaming load cost. */
static unsigned int audible_frames, worst_stall, last_service, swap_count;

/* Swap progress, owned by music_service() on the main thread. */
/* A swap streams during gameplay. Blocking reads cost real CD time every
 * frame (2x drive: ~150 sectors/s), which Kronos hides and Mednafen/hardware
 * do not. So the drive reads ahead into the CD buffer (GFS_NwCdRead) and each
 * frame copies only sectors that have already arrived. */
typedef struct {
    GfsHn gfs;
    unsigned int size, offset, idle;
    bool suspended;
} cd_stream_t;
extern Sint32 GFS_GetNumCdbuf(GfsHn gfs);  /* LIBCD; Jo has no prototype */
extern Sint32 GFS_NwStop(GfsHn gfs);

static cd_stream_t level_stream;
static bool level_file_open;
static unsigned int level_offset;
static cd_stream_t swap_stream;
static bool swap_file_open;
static unsigned short *swap_staging;
static unsigned int swap_offset;

static bool stream_open(cd_stream_t *s, const char *name, unsigned int size)
{
    Sint32 fid = GFS_NameToId((Sint8 *)name), sector, count, last;
    if (fid < 0 || !(s->gfs = GFS_Open(fid))) { s->gfs = 0; return false; }
    GFS_GetFileSize(s->gfs, &sector, &count, &last);
    if ((unsigned int)(sector * (count - 1) + last) != size) {
        GFS_Close(s->gfs); s->gfs = 0; return false;
    }
    s->size = size; s->offset = 0; s->idle = 0;
    GFS_SetTmode(s->gfs, GFS_TMODE_CPU);
    s->suspended = false;
    if (GFS_NwCdRead(s->gfs, count) < 0) {
        GFS_Close(s->gfs); s->gfs = 0; return false;
    }
    return true;
}

static void stream_close(cd_stream_t *s)
{
    if (s->gfs) { GFS_NwStop(s->gfs); GFS_Close(s->gfs); }
    s->gfs = 0;
}

/* Main-thread file loaders must cancel read-ahead before using the CD.
 * NwCdRead stays active until host consumption or NwStop, even with all
 * sectors buffered. Keep the handle and resume at the consumed offset. */
bool __attribute__((optimize("Os"))) music_yield_cd(void)
{
    cd_stream_t *s;
    unsigned i;
    for (i = 0; i < 2; ++i) {
        s = i ? &swap_stream : &level_stream;
        if (s->gfs && !s->suspended) {
            if (GFS_NwStop(s->gfs) < 0) return false;
            s->suspended = true;
        }
    }
    return true;
}

/* Bytes copied into buf (0 = nothing buffered yet), or -1 on error. Never
 * waits on the drive, except one sector after a long stall: another file's
 * read stops our read-ahead, and a blocking read always resumes it. */
static int stream_read(cd_stream_t *s, void *buf, unsigned int max)
{
    Sint32 have, want = (Sint32)(max / 2048), got;
    unsigned int bytes;
    if (s->offset >= s->size) return 0;
    if (s->suspended) {
        if (GFS_Seek(s->gfs, (Sint32)(s->offset / 2048), GFS_SEEK_SET) < 0 ||
            GFS_NwCdRead(s->gfs, (Sint32)((s->size - s->offset + 2047) / 2048)) < 0)
            return -1;
        s->suspended = false;
        s->idle = 0;
    }
    GFS_NwExecOne(s->gfs);
    have = GFS_GetNumCdbuf(s->gfs);
    if (have <= 0) {
        ++s->idle;
        if (s->idle == STREAM_STALL) {
            if (GFS_NwStop(s->gfs) < 0 ||
                GFS_NwCdRead(s->gfs, (Sint32)((s->size - s->offset + 2047) / 2048)) < 0)
                return -1;
        }
        if (s->idle < 2 * STREAM_STALL) return 0;
        have = 1;
    }
    s->idle = 0;
    if (want > have) want = have;
    bytes = (unsigned int)want * 2048;
    if (bytes > s->size - s->offset) bytes = s->size - s->offset;
    got = GFS_Fread(s->gfs, want, buf, (Sint32)bytes);
    if (got != (Sint32)bytes) return -1;
    s->offset += bytes;
    return (int)bytes;
}
static bool swap_failed;
static const music_bank_t *once_bank,*once_resume;
static volatile bool once_done;
void music_once(const music_bank_t *one_shot,const music_bank_t *resume)
{once_bank=one_shot;once_resume=resume;once_done=false;}
static const music_bank_t *section_bank;
static const unsigned short (*section_ranges)[2];
static unsigned section_count,section_current;
static unsigned (*section_next)(unsigned);
void music_set_sections(const music_bank_t *target,const unsigned short (*ranges)[2],
                        unsigned count,unsigned (*next)(unsigned))
{
    section_bank=target;section_ranges=ranges;section_count=count;section_next=next;section_current=0;
}

/* SCSP TL is 0.375 dB/step. Fade only the music slots: master volume also
 * controls resident effects, which must remain audible during silent scenes. */
static unsigned int faded_level(unsigned int level)
{
    static const unsigned char attenuation[16] =
        {255,63,47,37,31,25,21,18,15,12,9,7,5,3,2,0};
    unsigned int result = level + attenuation[volume] + attenuation[cdda_volume]
                          + (menu_duck ? 16u : 0u);
    return result > 255 ? 255 : result;
}

static void set_volume(unsigned int level)
{
    unsigned int i;
    volume = (unsigned char)level;
    for (i = 0; i < MUSIC_MAX_VOICES; ++i)
        if (active[i]) SLOT(i,12) = faded_level(voice_levels[i]);
}

void music_cdda_mute(bool enabled)
{
    if (enabled) {
        cdda_muted = true;
        cdda_restore = 0;
        cdda_volume = 0;
        set_volume(volume);
    } else if (cdda_muted) {
        cdda_restore = refresh / 2; /* 30 NTSC / 25 PAL VBlanks */
        cdda_muted = false;
    }
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
    if(event->sample==255){if(s<MUSIC_MAX_VOICES && active[s])SLOT(s,16)=event->pitch;return;}
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
    if(bank==section_bank && section_count){
        if(frame==0)section_current=0;
        if(frame>=section_ranges[section_current][1]){
            unsigned next=section_next?section_next(section_current):1;
            if(next>=section_count)next=0;
            stop_all();section_current=next;frame=section_ranges[next][0];cursor=0;
            while(cursor<bank->trigger_count && bank->triggers[cursor].frame<frame)++cursor;
        }
    }
    if(frame==bank->frames && bank==once_bank){stop_all();playing=false;once_done=true;return;}
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
    if (!cdda_muted && cdda_restore) {
        --cdda_restore;
        cdda_volume = ((refresh / 2) - cdda_restore) * VOLUME_MAX / (refresh / 2);
        set_volume(volume);
    }
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
    if (cdda_muted || state != MUSIC_IDLE || !bank)
        return (false);
    once_bank=once_resume=JO_NULL;once_done=false;
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
        cdda_muted || state != MUSIC_IDLE || bank == target) return false;
    if(target!=once_bank){once_bank=once_resume=JO_NULL;once_done=false;}
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
    /* Do not seek the drive back to data while a Red Book track owns it. */
    if (cdda_muted) return;
    if(once_done && state==MUSIC_IDLE){
        const music_bank_t *resume=once_resume;
        once_done=false;once_bank=once_resume=JO_NULL;
        if(resume)music_fade_to(resume,10);else music_silence(1);
    }

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
            if (!stream_open(&level_stream, incoming->level_file, incoming->level_bytes)) {
                jo_free(pending_levels); pending_levels = JO_NULL;
                swap_failed = true; swap_stage = 0; set_volume(VOLUME_MAX);
                state = MUSIC_IDLE; return;
            }
            level_offset = 0;
            level_file_open = true;
        }
        got = stream_read(&level_stream, (char *)pending_levels + level_offset, LOAD_CHUNK);
        if (got < 0) {
            stream_close(&level_stream); level_file_open = false;
            jo_free(pending_levels); pending_levels = JO_NULL;
            swap_failed = true; swap_stage = 0; set_volume(VOLUME_MAX);
            state = MUSIC_IDLE; return;
        }
        level_offset += (unsigned int)got;
        if (level_offset < incoming->level_bytes) return;
        stream_close(&level_stream);
        level_file_open = false;
        swap_stage = 2;
        return;
    }

    if (state != MUSIC_SWAP) return;

    if (!swap_file_open) {
        if (incoming->sample_base + incoming->pcm_bytes > 0x80000 ||
            !stream_open(&swap_stream, incoming->pcm_file, incoming->pcm_bytes)) {
            swap_failed = true; swap_stage = 0; set_volume(VOLUME_MAX);
            state = MUSIC_IDLE; return;
        }
        swap_staging = jo_malloc(LOAD_CHUNK);
        if (!swap_staging) {
            stream_close(&swap_stream); swap_failed = true; swap_stage = 0; set_volume(VOLUME_MAX);
            state = MUSIC_IDLE; return;
        }
        swap_offset = 0;
        swap_file_open = true;
    }

    {
        int got = stream_read(&swap_stream, swap_staging, LOAD_CHUNK);
        if (got < 0 || (got & 1)) {
            stream_close(&swap_stream); jo_free(swap_staging);
            swap_staging = JO_NULL; swap_file_open = false;
            swap_failed = true; swap_stage = 0; set_volume(VOLUME_MAX); state = MUSIC_IDLE;
            return;
        }
        if (got) upload(swap_staging, incoming->sample_base, swap_offset, (unsigned int)got);
        swap_offset += (unsigned int)got;
    }

    if (swap_offset < incoming->pcm_bytes) return;   /* more next frame */

    stream_close(&swap_stream);
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
    return music_init_with_scratch(first, JO_NULL, 0);
}

bool music_init_with_scratch(const music_bank_t *first, void *scratch, unsigned int capacity)
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
    staging = scratch && capacity > bank->pcm_bytes ? scratch : jo_malloc(LOAD_CHUNK);
    if (!staging) { jo_fs_close(&file); jo_free(levels); return false; }

    if (staging == scratch) {
        jo_fs_close(&file);
        if (!jo_fs_read_file_ptr(bank->pcm_file, scratch, &got) ||
            (unsigned int)got != bank->pcm_bytes || (got & 1)) {
            jo_free(levels); return false;
        }
    }

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
        if (staging == scratch) {
            upload(staging, bank->sample_base, 0, bank->pcm_bytes);
            break;
        }
        if (want > LOAD_CHUNK) want = LOAD_CHUNK;
        got = GFS_Fread((GfsHn)file.handle, (want + 2047) / 2048, staging, want);
        if (got != (int)want || (got & 1)) {
            jo_fs_close(&file); jo_free(staging); jo_free(levels); return false;
        }
        upload(staging, bank->sample_base, offset, (unsigned int)got);
        offset += (unsigned int)got;
    }
    if (staging != scratch) {
        jo_fs_close(&file);
        jo_free(staging);
    }
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
unsigned int music_vblank_count(void) { return vblanks; }
const music_bank_t *music_current(void) { return bank; }
bool music_busy(void) { return state != MUSIC_IDLE; }
bool music_failed(void) { return swap_failed; }
unsigned int music_transition_frames(void) { return transition_frames; }
