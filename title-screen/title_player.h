#ifndef TITLE_PLAYER_H
#define TITLE_PLAYER_H

/* title_music_init owns initialization and the vblank callback. Do not call
 * update from the renderer: score time must not depend on rendering speed. */
void title_player_init(void);
void title_player_update(void);

#endif
