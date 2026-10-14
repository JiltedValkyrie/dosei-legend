#ifndef OOT_CORE_TIMER_H
#define OOT_CORE_TIMER_H
typedef struct OotCoreTimerView {
    unsigned char state, reserved;
    short seconds, x, y;
} OotCoreTimerView;
#endif
