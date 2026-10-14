/* Generated from source z_parameter.c by ranch_sources.timer_source.
 * Source main timer only; called at the source 20 Hz cadence, never render FPS.
 */
#include "oot_prelude.h"
#include "play_state.h"
#include "player.h"
#include "save.h"
#include "sfx.h"
#include "audio.h"
#include "interface.h"
#include "attributes.h"
#include "oot_core_timer.h"
static s16 sEnvHazardActive;
static s16 sTimerStateTimer;
static s16 sTimerNextSecondTimer;
void Interface_SetTimer(s16 seconds) {
    gSaveContext.timerX[TIMER_ID_MAIN] = 140;
    gSaveContext.timerY[TIMER_ID_MAIN] = 80;
    sEnvHazardActive = false;
    gSaveContext.timerSeconds = seconds;

    if (seconds != 0) {
        // count down
        gSaveContext.timerState = TIMER_STATE_DOWN_INIT;
    } else {
        // count up
        gSaveContext.timerState = TIMER_STATE_UP_INIT;
    }
}

void OotCore_UpdateRouteTimer(PlayState* play) {
    MessageContext* msgCtx = &play->msgCtx;
    Player* player = GET_PLAYER(play);
    s16 svar1;
    s16 timerId;
    s16 previousOnesDigit = gSaveContext.timerSeconds % 10;
        if (!IS_PAUSED(&play->pauseCtx) && (play->gameOverCtx.state == GAMEOVER_INACTIVE) &&
            (msgCtx->msgMode == MSGMODE_NONE) && !(player->stateFlags2 & PLAYER_STATE2_24) &&
            (play->transitionTrigger == TRANS_TRIGGER_OFF) && (play->transitionMode == TRANS_MODE_OFF) &&
            !Play_InCsMode(play) && (gSaveContext.minigameState != 1) && (play->shootingGalleryStatus <= 1) &&
            !((play->sceneId == SCENE_BOMBCHU_BOWLING_ALLEY) && Flags_GetSwitch(play, 0x38))) {

            timerId = TIMER_ID_MAIN;

            switch (gSaveContext.timerState) {
                case TIMER_STATE_ENV_HAZARD_INIT:
                    sTimerStateTimer = 20;
                    sTimerNextSecondTimer = 20;
                    gSaveContext.timerSeconds = gSaveContext.save.info.playerData.health >> 1;
                    gSaveContext.timerState = TIMER_STATE_ENV_HAZARD_PREVIEW;
                    break;

                case TIMER_STATE_ENV_HAZARD_PREVIEW:
                    sTimerStateTimer--;
                    if (sTimerStateTimer == 0) {
                        sTimerStateTimer = 20;
                        gSaveContext.timerState = TIMER_STATE_ENV_HAZARD_MOVE;
                    }
                    break;

                case TIMER_STATE_DOWN_INIT:
                case TIMER_STATE_UP_INIT:
                    sTimerStateTimer = 20;
                    sTimerNextSecondTimer = 20;
                    if (gSaveContext.timerState == TIMER_STATE_DOWN_INIT) {
                        gSaveContext.timerState = TIMER_STATE_DOWN_PREVIEW;
                    } else {
                        gSaveContext.timerState = TIMER_STATE_UP_PREVIEW;
                    }
                    break;

                case TIMER_STATE_DOWN_PREVIEW:
                case TIMER_STATE_UP_PREVIEW:
                    sTimerStateTimer--;
                    if (sTimerStateTimer == 0) {
                        sTimerStateTimer = 20;
                        if (gSaveContext.timerState == TIMER_STATE_DOWN_PREVIEW) {
                            gSaveContext.timerState = TIMER_STATE_DOWN_MOVE;
                        } else {
                            gSaveContext.timerState = TIMER_STATE_UP_MOVE;
                        }
                    }
                    break;

                case TIMER_STATE_ENV_HAZARD_MOVE:
                case TIMER_STATE_DOWN_MOVE:
                    svar1 = (gSaveContext.timerX[TIMER_ID_MAIN] - 26) / sTimerStateTimer;
                    gSaveContext.timerX[TIMER_ID_MAIN] -= svar1;

                    if (gSaveContext.save.info.playerData.healthCapacity > 0xA0) {
                        svar1 = (gSaveContext.timerY[TIMER_ID_MAIN] - 54) / sTimerStateTimer; // two rows of hearts
                    } else {
                        svar1 = (gSaveContext.timerY[TIMER_ID_MAIN] - 46) / sTimerStateTimer; // one row of hearts
                    }
                    gSaveContext.timerY[TIMER_ID_MAIN] -= svar1;

                    sTimerStateTimer--;
                    if (sTimerStateTimer == 0) {
                        sTimerStateTimer = 20;
                        gSaveContext.timerX[TIMER_ID_MAIN] = 26;

                        if (gSaveContext.save.info.playerData.healthCapacity > 0xA0) {
                            gSaveContext.timerY[TIMER_ID_MAIN] = 54; // two rows of hearts
                        } else {
                            gSaveContext.timerY[TIMER_ID_MAIN] = 46; // one row of hearts
                        }

                        if (gSaveContext.timerState == TIMER_STATE_ENV_HAZARD_MOVE) {
                            gSaveContext.timerState = TIMER_STATE_ENV_HAZARD_TICK;
                        } else {
                            gSaveContext.timerState = TIMER_STATE_DOWN_TICK;
                        }
                    }
                    FALLTHROUGH;
                case TIMER_STATE_ENV_HAZARD_TICK:
                case TIMER_STATE_DOWN_TICK:
                    if ((gSaveContext.timerState == TIMER_STATE_ENV_HAZARD_TICK) ||
                        (gSaveContext.timerState == TIMER_STATE_DOWN_TICK)) {
                        if (gSaveContext.save.info.playerData.healthCapacity > 0xA0) {
                            gSaveContext.timerY[TIMER_ID_MAIN] = 54; // two rows of hearts
                        } else {
                            gSaveContext.timerY[TIMER_ID_MAIN] = 46; // one row of hearts
                        }
                    }

                    if ((gSaveContext.timerState >= TIMER_STATE_ENV_HAZARD_MOVE) && (msgCtx->msgLength == 0)) {
                        if (--sTimerNextSecondTimer == 0) {
                            if (gSaveContext.timerSeconds != 0) {
                                gSaveContext.timerSeconds--;
                            }

                            sTimerNextSecondTimer = 20;

                            if (gSaveContext.timerSeconds == 0) {
                                // Out of time
                                gSaveContext.timerState = TIMER_STATE_STOP;
                                if (sEnvHazardActive) {
                                    gSaveContext.save.info.playerData.health = 0;
                                    play->damagePlayer(play, -(gSaveContext.save.info.playerData.health + 2));
                                }
                                sEnvHazardActive = false;
                            } else if (gSaveContext.timerSeconds > 60) {
                                // Beep at "xx:x1" (every 10 seconds)
                                if (previousOnesDigit == 1) {
                                    SFX_PLAY_CENTERED(NA_SE_SY_MESSAGE_WOMAN);
                                }
                            } else if (gSaveContext.timerSeconds > 10) {
                                // Beep on alternating seconds
                                if ((previousOnesDigit % 2) != 0) {
                                    SFX_PLAY_CENTERED(NA_SE_SY_WARNING_COUNT_N);
                                }
                            } else {
                                // Beep every second
                                SFX_PLAY_CENTERED(NA_SE_SY_WARNING_COUNT_E);
                            }
                        }
                    }
                    break;

                case TIMER_STATE_UP_MOVE:
                    svar1 = (gSaveContext.timerX[TIMER_ID_MAIN] - 26) / sTimerStateTimer;
                    gSaveContext.timerX[TIMER_ID_MAIN] -= svar1;

                    if (gSaveContext.save.info.playerData.healthCapacity > 0xA0) {
                        svar1 = (gSaveContext.timerY[TIMER_ID_MAIN] - 54) / sTimerStateTimer; // two rows of hearts
                    } else {
                        svar1 = (gSaveContext.timerY[TIMER_ID_MAIN] - 46) / sTimerStateTimer; // one row of hearts
                    }
                    gSaveContext.timerY[TIMER_ID_MAIN] -= svar1;

                    sTimerStateTimer--;
                    if (sTimerStateTimer == 0) {
                        sTimerStateTimer = 20;
                        gSaveContext.timerX[TIMER_ID_MAIN] = 26;
                        if (gSaveContext.save.info.playerData.healthCapacity > 0xA0) {
                            gSaveContext.timerY[TIMER_ID_MAIN] = 54; // two rows of hearts
                        } else {
                            gSaveContext.timerY[TIMER_ID_MAIN] = 46; // one row of hearts
                        }

                        gSaveContext.timerState = TIMER_STATE_UP_TICK;
                    }
                    FALLTHROUGH;
                case TIMER_STATE_UP_TICK:
                    if (gSaveContext.timerState == TIMER_STATE_UP_TICK) {
                        if (gSaveContext.save.info.playerData.healthCapacity > 0xA0) {
                            gSaveContext.timerY[TIMER_ID_MAIN] = 54; // two rows of hearts
                        } else {
                            gSaveContext.timerY[TIMER_ID_MAIN] = 46; // one row of hearts
                        }
                    }

                    if (gSaveContext.timerState >= TIMER_STATE_ENV_HAZARD_MOVE) {
                        sTimerNextSecondTimer--;
                        if (sTimerNextSecondTimer == 0) {
                            gSaveContext.timerSeconds++;
                            sTimerNextSecondTimer = 20;

                            if (gSaveContext.timerSeconds == 3599) { // 59 minutes, 59 seconds
                                sTimerStateTimer = 40;
                                gSaveContext.timerState = TIMER_STATE_UP_FREEZE;
                            } else {
                                SFX_PLAY_CENTERED(NA_SE_SY_WARNING_COUNT_N);
                            }
                        }
                    }
                    break;

                case TIMER_STATE_STOP:
                    if (gSaveContext.subTimerState != SUBTIMER_STATE_OFF) {
                        gSaveContext.timerX[TIMER_ID_SUB] = 140;
                        gSaveContext.timerY[TIMER_ID_SUB] = 80;

                        if (gSaveContext.subTimerState <= SUBTIMER_STATE_STOP) {
                            gSaveContext.subTimerState = SUBTIMER_STATE_DOWN_PREVIEW;
                        } else {
                            gSaveContext.subTimerState = SUBTIMER_STATE_UP_PREVIEW;
                        }

                        gSaveContext.timerState = TIMER_STATE_OFF;
                    } else {
                        gSaveContext.timerState = TIMER_STATE_OFF;
                    }
                    FALLTHROUGH;
                case TIMER_STATE_UP_FREEZE:
                    break;

                default: break;
            }
        }
}

void OotCore_TimerView(OotCoreTimerView* out) {
    if (!out) return;
    out->state = gSaveContext.timerState;
    out->reserved = 0;
    out->seconds = gSaveContext.timerSeconds;
    out->x = gSaveContext.timerX[TIMER_ID_MAIN];
    out->y = gSaveContext.timerY[TIMER_ID_MAIN];
}
