/*
** The game's music banks. This is the only file that names actual tracks; the
** player in music.h is content-agnostic. Add a track by staging its PCM and
** envelope files on the CD and adding a bank here.
*/

#ifndef VIEWER_MUSIC_BANKS_H
#define VIEWER_MUSIC_BANKS_H

#include "music.h"

extern music_bank_t music_bank_title;
extern music_bank_t music_bank_kokiri;
extern music_bank_t music_bank_house;
extern music_bank_t music_bank_shop;
extern music_bank_t music_bank_dungeon;
extern music_bank_t music_bank_woods;
extern music_bank_t music_bank_fairy;
extern music_bank_t music_bank_boss;
extern music_bank_t music_bank_bossclear;
extern music_bank_t music_bank_owl, music_bank_fairyget, music_bank_field, music_bank_stone;
/* The opening cutscenes' original sequence banks, including Ganon percussion. */
extern music_bank_t music_bank_nightmare;
extern music_bank_t music_bank_navi;
extern music_bank_t music_bank_deku_tree;

/* Bind MUSICTRG.BIN (cart carve) to every bank's triggers. */
bool music_banks_bind(const uint8_t *blob, uint32_t bytes);
/* MUSICTRG.BIN limit (tools/build_cart_tables.py MUSICTRG_LIMIT); loaded once
** at boot into a cart heap block. */
#define MUSICTRG_BYTES 0x18000u

#endif
