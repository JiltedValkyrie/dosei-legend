#ifndef DOSEI_GOHMA_H
#define DOSEI_GOHMA_H
#include "gameplay.h"
bool gohma_init(void *memory,unsigned bytes);
bool gohma_bind(const uint8_t *poses,unsigned bytes);
void gohma_reset(void);
void gohma_step(const gameplay_input_t *in);
void gohma_register(void);
void gohma_collect(void);
void gohma_notice(int32_t x,int32_t y,int32_t z,uint16_t yaw,int16_t pitch);
bool gohma_body(int32_t p[3],uint16_t *yaw,int16_t *pitch,unsigned *frame);
bool gohma_cinematic(void);
bool gohma_defeated(void);
bool gohma_warp_active(void);
bool gohma_warp_ready(void);
bool gohma_reward_body(unsigned kind, int32_t p[3], uint16_t *yaw);
void gohma_skip_shot(void);
unsigned gohma_shot_key(void);
bool gohma_camera(int32_t eye[3],int32_t at[3]);
unsigned gohma_filter(void);
#endif
