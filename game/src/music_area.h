#ifndef DOSEI_MUSIC_AREA_H
#define DOSEI_MUSIC_AREA_H
#include <stdbool.h>
/* Area theme baked by tools/build_area_music.py: M<seq>.HDR/.PCM/.LVL on the
** disc, tables loaded into the jo heap, played through a shared bank.
** False when the scene's sequence has no baked bank. */
bool music_area_play(unsigned int seq, unsigned int fade_frames);
#endif
