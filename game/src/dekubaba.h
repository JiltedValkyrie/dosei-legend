#ifndef DOSEI_DEKUBABA_H
#define DOSEI_DEKUBABA_H
#include "gameplay.h"
#define DEKUBABA_MAX 3
typedef struct {
    int32_t head[3],home[3],scale;
    int16_t stem[3],pitch;
    uint16_t yaw,frame;
    uint8_t pruned,stick;
} dekubaba_view;
bool dekubaba_init(void *storage,unsigned bytes);
void dekubaba_reset(void);
void dekubaba_step(const gameplay_input_t *in);
void dekubaba_register(void);
void dekubaba_collect(void);
bool dekubaba_room(unsigned room);
const dekubaba_view *dekubaba_body(unsigned i);
void kokiri_dekubaba_stem(const dekubaba_view *view);
unsigned dekubaba_filter(unsigned i);
#endif
