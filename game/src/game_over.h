#ifndef DOSEI_GAME_OVER_H
#define DOSEI_GAME_OVER_H
#include <stdbool.h>
#include <stdint.h>

/*
** Death -> Game Over -> save -> continue (M2e). Platform free: demo.c plays
** Link's death clip, writes the save and reloads the scene; main.c draws the
** VDP2 text. Source: z_player.c func_80836448 / func_80843AE8,
** z_game_over.c GameOver_Update, z_kaleido_scope.c PAUSE_STATE_GAME_OVER_*.
** Source frames are 20 Hz; the steps here are 30 Hz, so timers are x3/2.
**
**   DYING      derth_rebirth plays (NA_BGM_GAME_OVER, NA_SE_VO_LI_DOWN_KID)
**   DELAY      GAMEOVER_DEATH_DELAY_MENU: 20 frames after the clip ends
**   MESSAGE    GAME_OVER_SHOW_MESSAGE + WINDOW_DELAY (40)
**   SAVE       "Save?"  Yes: Sram_WriteSave (savedSceneId = scene). No: on.
**   SAVED      90 frames, A/Start skips once 10 have passed
**   CONTINUE   "Continue playing?" Yes: respawn, 3 hearts. No: title.
**   FINISH     the fade to black (255 at 10 a frame: 26 frames)
**
** A device write that fails is reported ("SAVE FAILED") and the save
** prompt returns; the source has no failure path, the plan requires one.
*/

typedef enum {
    GAME_OVER_OFF, GAME_OVER_DYING, GAME_OVER_DELAY, GAME_OVER_MESSAGE,
    GAME_OVER_SAVE, GAME_OVER_SAVING, GAME_OVER_SAVED, GAME_OVER_CONTINUE,
    GAME_OVER_FINISH
} game_over_state_t;

typedef enum {
    GAME_OVER_RESULT_NONE, GAME_OVER_RESULT_CONTINUE, GAME_OVER_RESULT_TITLE
} game_over_result_t;

#define GAME_OVER_EV_START      (1u << 0)   /* NA_BGM_GAME_OVER + DOWN voice */
#define GAME_OVER_EV_SAVE       (1u << 1)   /* platform: write the save now */
#define GAME_OVER_EV_MOVE       (1u << 2)   /* cursor moved (NA_SE_SY_CURSOR) */
#define GAME_OVER_EV_DECIDE     (1u << 3)   /* NA_SE_SY_DECIDE (No) */
#define GAME_OVER_EV_YES        (1u << 4)   /* NA_SE_SY_PIECE_OF_HEART (Yes) */

/* Health restored on Continue (kaleido FINISH: 0x30, three hearts). */
#define GAME_OVER_CONTINUE_HEALTH   0x30

void                game_over_start(void);      /* GAMEOVER_DEATH_START */
void                game_over_anim_done(void);  /* the death clip ended */
/* One 30 Hz step. menu_step -1/+1 moves the Yes/No cursor. */
game_over_result_t  game_over_step(int menu_step, bool confirm);
void                game_over_save_done(bool ok);
void                game_over_reset(void);
game_over_state_t   game_over_state(void);
bool                game_over_active(void);
unsigned int        game_over_cursor(void);     /* 0 Yes, 1 No */
bool                game_over_save_failed(void);
uint32_t            game_over_events(void);     /* this step's GAME_OVER_EV_* */
/* 0..255 fade over the scene (FINISH), for the platform to draw. */
unsigned int        game_over_fade(void);

#endif
