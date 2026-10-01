#pragma GCC optimize("Os") /* Cold death/menu flow: preserve high RAM. */
/* Game Over flow: see game_over.h. */
#include "game_over.h"
#include "save_state.h"

#define STEPS(frames)   (((frames) * 3 + 1) / 2)    /* 20 Hz frames -> 30 Hz */

static game_over_state_t state;
static unsigned int timer, cursor, fade;
static bool         failed, choice_yes;
static uint32_t     events;

void                game_over_reset(void)
{
    state = GAME_OVER_OFF;
    timer = cursor = fade = 0;
    failed = choice_yes = false;
    events = 0;
}

void                game_over_start(void)
{
    if (state != GAME_OVER_OFF)
        return;                         /* lethal exactly once */
    game_over_reset();
    state = GAME_OVER_DYING;
    /* GameOver_Update DEATH_START: the save-relevant reset (naviTimer; the
    ** slice has no timers, trade items, B-button items or magic). */
    save_state.navi_timer = 0;
    events |= GAME_OVER_EV_START;
}

void                game_over_anim_done(void)
{
    if (state == GAME_OVER_DYING) {
        state = GAME_OVER_DELAY;
        timer = STEPS(20);
    }
}

void                game_over_save_done(bool ok)
{
    if (state != GAME_OVER_SAVING)
        return;
    failed = !ok;
    if (ok) {
        state = GAME_OVER_SAVED;
        timer = STEPS(90);
    } else {
        state = GAME_OVER_SAVE;         /* say so; let the player choose again */
    }
}

game_over_result_t  game_over_step(int menu_step, bool confirm)
{
    events &= GAME_OVER_EV_START;       /* START survives to the first read */
    switch (state) {
    case GAME_OVER_OFF:
    case GAME_OVER_DYING:
    case GAME_OVER_SAVING:
        break;
    case GAME_OVER_DELAY:
        if (timer) --timer;
        if (!timer) {
            state = GAME_OVER_MESSAGE;
            timer = STEPS(40);
        }
        break;
    case GAME_OVER_MESSAGE:
        if (timer) --timer;
        if (!timer) {
            state = GAME_OVER_SAVE;
            cursor = 0;
        }
        break;
    case GAME_OVER_SAVE:
    case GAME_OVER_CONTINUE:
        if (menu_step) {
            cursor ^= 1u;
            events |= GAME_OVER_EV_MOVE;
        }
        if (!confirm)
            break;
        if (state == GAME_OVER_SAVE) {
            if (cursor == 0) {
                events |= GAME_OVER_EV_YES | GAME_OVER_EV_SAVE;
                failed = false;
                state = GAME_OVER_SAVING;
            } else {
                events |= GAME_OVER_EV_DECIDE;
                state = GAME_OVER_CONTINUE;
                cursor = 0;
            }
        } else {
            choice_yes = cursor == 0;
            events |= choice_yes ? GAME_OVER_EV_YES : GAME_OVER_EV_DECIDE;
            state = GAME_OVER_FINISH;
            fade = 0;
        }
        break;
    case GAME_OVER_SAVED:
        if (timer) --timer;
        if (!timer || (confirm && timer <= STEPS(80))) {
            state = GAME_OVER_CONTINUE;
            cursor = 0;
        }
        break;
    case GAME_OVER_FINISH:
        fade += 10 * 2 / 3 + 1;         /* 10 a 20 Hz frame, ~7 a step */
        if (fade >= 255) {
            fade = 255;
            if (choice_yes) {
                save_state.health = GAME_OVER_CONTINUE_HEALTH;
                if (save_state.health > save_state.health_capacity)
                    save_state.health = save_state.health_capacity;
            }
            state = GAME_OVER_OFF;
            return choice_yes ? GAME_OVER_RESULT_CONTINUE : GAME_OVER_RESULT_TITLE;
        }
        break;
    }
    return GAME_OVER_RESULT_NONE;
}

uint32_t            game_over_events(void)
{
    uint32_t e = events;
    events &= ~GAME_OVER_EV_START;
    return e;
}

game_over_state_t   game_over_state(void) { return state; }
bool                game_over_active(void) { return state != GAME_OVER_OFF; }
unsigned int        game_over_cursor(void) { return cursor; }
bool                game_over_save_failed(void) { return failed; }
unsigned int        game_over_fade(void) { return fade; }
