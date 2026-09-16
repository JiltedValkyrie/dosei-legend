#ifndef DOSEI_VIDEO_MODE_H
#define DOSEI_VIDEO_MODE_H
/* Forced into every translation unit, including locally-built Jo sources.
 * Keep the 512x256 RGB555 bitmap allocation. Stock JO_480i selects a
 * 1024x512 bitmap, incompatible with the current background memory layout. */
#include <jo/conf.h>
#ifdef DOSEI_HIRES
#undef JO_TV_RES
#undef JO_TV_HEIGHT
#undef JO_TV_HEIGHT_2
#undef JO_TV_HEIGHT_4
#define JO_TV_RES TV_320x480
#define JO_TV_HEIGHT 480
#define JO_TV_HEIGHT_2 240
#define JO_TV_HEIGHT_4 120
#endif
#endif
