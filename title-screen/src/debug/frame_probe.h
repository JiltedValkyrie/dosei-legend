#ifndef FRAME_PROBE_H
#define FRAME_PROBE_H
#include <stdint.h>
void frame_probe_stage(uint8_t stage);
void frame_probe_tick(void);
void frame_probe_complete(void);
#endif
