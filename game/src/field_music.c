#pragma GCC optimize("Os") /* small logic: size over speed (work RAM) */
#include "field_music.h"
#include "music_banks.h"
#include "field_phrases.h"
static volatile unsigned still_ticks, moving_ticks;
static volatile bool still_mode;
static unsigned random_state=1;
static unsigned pick(unsigned n){random_state=random_state*1664525u+1013904223u;return (random_state>>16)%n;}
/* seq_2.prg.seq: normal random 0..10 +4; still entry20 then 0..2 +21.
 * Retain its two-draw / decrement rule for the previous random choice. */
static unsigned next_phrase(unsigned previous)
{
    bool still=still_mode;
    unsigned base=still?13:1,n=still?3:11,old=previous>=base?previous-base:255;
    unsigned probe;
    if(still && previous<12)return 12;
    probe=pick(n);
    return base+(probe==old ? (pick(n)+n-1)%n : pick(n));
}
void field_music_init(void){music_set_sections(&music_bank_field,field_phrases,
    sizeof(field_phrases)/sizeof(field_phrases[0]),next_phrase);}
/* Audio_SetSequenceMode: 30 still / 20 moving source ticks, scaled 20->30 Hz. */
void field_music_motion(bool moving)
{
    if(moving){if(still_mode)moving_ticks=0;still_ticks=0;if(moving_ticks<32)++moving_ticks;still_mode=false;}
    else {if(still_ticks<45)++still_ticks;still_mode=!(still_ticks<45 && moving_ticks>30);}
}
