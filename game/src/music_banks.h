/*
** The game's music banks. This is the only file that names actual tracks; the
** player in music.h is content-agnostic. Add a track by staging its PCM and
** envelope files on the CD and adding a bank here.
*/

#ifndef VIEWER_MUSIC_BANKS_H
#define VIEWER_MUSIC_BANKS_H

#include "music.h"

extern const music_bank_t music_bank_title;
extern const music_bank_t music_bank_kokiri;
/* The opening cutscenes' cues. NA_BGM_OPENING_GANON has no bank yet: its
** sequence uses percussion the score builder cannot bake. */
extern const music_bank_t music_bank_navi;
extern const music_bank_t music_bank_deku_tree;

#endif
