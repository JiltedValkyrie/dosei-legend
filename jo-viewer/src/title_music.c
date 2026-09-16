/* Approved baseline US 1.2 score, driven by Jo's vblank hook.
 * Jo's stock audio module must stay disabled: this player owns SCSP slots.
 * Sample upload uses word writes and a small staging buffer, not the heap
 * sized for a whole 480 KB sample bank. No CD reads occur in the interrupt.
 */
#include <jo/jo.h>
#include "title_score.h"
#include "title_music.h"

#define REG(o) (*(volatile unsigned short *)(0x25b00000UL + (o)))
#define SLOT(s,o) REG((s)*32+(o))
static unsigned char *levels;
static unsigned short frame, cursor, keys[TITLE_VOICES];
static bool active[TITLE_VOICES];
static volatile unsigned int ticks;
static unsigned int phase, refresh;

static void stop_all(void)
{
    unsigned int i;
    for (i=0; i<TITLE_VOICES; ++i) {
        SLOT(i,12)=255;
        keys[i] &= ~0x0800;
        SLOT(i,0)=keys[i];
        active[i]=false;
    }
    SLOT(0,0)=keys[0] | 0x1000;
}

static void start_note(const title_trigger_t *event)
{
    unsigned int s=event->slot;
    const title_pcm_t *sample=&title_pcm[event->sample];
    unsigned int address=TITLE_SAMPLE_BASE+sample->offset;
    SLOT(s,12)=255;
    SLOT(s,0)=(keys[s]&~0x0800) | 0x1000;
    keys[s]=0x0020 | ((address>>16)&15);
    SLOT(s,0)=keys[s];
    SLOT(s,2)=address & 65535;
    SLOT(s,4)=sample->loop_start;
    SLOT(s,6)=sample->loop_end;
    SLOT(s,8)=31;
    SLOT(s,10)=31;
    SLOT(s,14)=0;
    SLOT(s,16)=event->pitch;
    SLOT(s,18)=0;
    SLOT(s,20)=0;
    SLOT(s,22)=(7<<13) | (event->pan<<8);
    keys[s] |= 0x0800;
    SLOT(s,0)=keys[s] | 0x1000;
    active[s]=true;
}

static void score_tick(void)
{
    unsigned int i;
    if (frame==TITLE_FRAMES) {
        stop_all();
        frame=TITLE_LOOP_FRAME;
        cursor=0;
        while (cursor<TITLE_TRIGGER_COUNT && title_triggers[cursor].frame<frame)
            ++cursor;
    }
    while (cursor<TITLE_TRIGGER_COUNT && title_triggers[cursor].frame==frame)
        start_note(&title_triggers[cursor++]);
    for (i=0; i<TITLE_VOICES; ++i)
        if (active[i]) SLOT(i,12)=levels[frame*TITLE_VOICES+i];
    ++frame;
    ++ticks;
}

static void music_vblank(void)
{
    phase+=60;
    while (phase>=refresh) {
        phase-=refresh;
        score_tick();
    }
}

bool viewer_music_init(void)
{
    jo_file file;
    unsigned short *staging;
    unsigned int offset=0, i;
    int length=0, got;
    volatile unsigned short *ram=(volatile unsigned short *)0x25a00000UL;
    levels=(unsigned char *)jo_fs_read_file("TITLE.LVL", &length);
    if (!levels) return false;
    if (length!=TITLE_FRAMES*TITLE_VOICES) {
        jo_free(levels);
        return false;
    }
    if (!jo_fs_open(&file,"TITLE.PCM")) { jo_free(levels); return false; }
    if (file.size!=480046 || TITLE_SAMPLE_BASE+file.size>0x80000) {
        jo_fs_close(&file); jo_free(levels); return false;
    }
    staging=jo_malloc(2048);
    if (!staging) { jo_fs_close(&file); jo_free(levels); return false; }

    /* Use SGL SMPC requests, never install a libyaul interrupt handler.
     * Restart the idle 68000 before the slow CD upload, as in the baseline. */
    slSoundOffWait();
    REG(0x400)=0x0200;
    REG(0x41e)=0;
    REG(0x42a)=0;
    for (i=0; i<0x400; i+=2) REG(i)=0;
    for (i=0; i<32; ++i) { SLOT(i,12)=255; SLOT(i,10)=31; }
    SLOT(0,0)=0x1000;
    for (i=0; i<0x200; i+=2) { ram[i]=0; ram[i+1]=0x0400; }
    ram[1]=0x0ff0;
    ram[0x200]=0x46fc; ram[0x201]=0x2700; ram[0x202]=0x60fe;
    slSoundOnWait();
    while (offset<(unsigned int)file.size) {
        unsigned int want=(unsigned int)file.size-offset;
        if (want>2048) want=2048;
        got=jo_fs_read_next_bytes(&file,(char *)staging,want);
        if (got!=(int)want || (got&1)) {
            jo_fs_close(&file); jo_free(staging); jo_free(levels); return false;
        }
        for (i=0; i<(unsigned int)got/2; ++i)
            ram[(TITLE_SAMPLE_BASE+offset)/2+i]=staging[i];
        offset+=got;
    }
    jo_fs_close(&file);
    jo_free(staging);
    stop_all();
    frame=cursor=0; ticks=phase=0;
    refresh=(JO_VDP2_TVSTAT & 1) ? 50 : 60;
    if (!jo_core_add_vblank_callback(music_vblank)) {
        jo_free(levels); return false;
    }
    REG(0x400)=0x020f;
    return true;
}

unsigned int viewer_music_ticks(void) { return ticks; }
