#ifndef DOSEI_MUSIC_AREA_H
#define DOSEI_MUSIC_AREA_H
#include <stdbool.h>
/* Area theme baked by tools/build_area_music.py: M<seq>.HDR/.PCM/.LVL on the
** disc, tables loaded into the jo heap, played through a shared bank.
** False when the scene's sequence has no baked bank. */
bool music_area_play(unsigned int seq, unsigned int fade_frames);
bool music_area_fanfare(unsigned int seq);
unsigned int music_area_current_sequence(void); /* 0xffff for built-in/no bank */
/* Release inaudible cached tables before another scene's large asset loads. */
void music_area_trim(void);
#endif
