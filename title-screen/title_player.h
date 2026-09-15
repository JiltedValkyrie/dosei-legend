#ifndef TITLE_PLAYER_H
#define TITLE_PLAYER_H

/*
 * Sequences the OoT title theme (NA_BGM_TITLE / Sequence_30) over Ponesound
 * voices. All the sequence interpretation happens host-side (see
 * tools/make_title_sequence.py and title_sequence.h) - this just walks a
 * flat, time-stamped note-event table and claims/releases Ponesound pcmCtrl
 * slots as a simple voice pool. Call title_player_init() once after
 * title_music_init() has loaded the driver and the sound CPU has had time
 * to boot, then title_player_update() once per frame (vblank).
 */

void title_player_init(void);
void title_player_update(void);

#endif /* !TITLE_PLAYER_H */
