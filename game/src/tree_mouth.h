#ifndef DOSEI_TREE_MOUTH_H
#define DOSEI_TREE_MOUTH_H
#include <stdint.h>
void tree_mouth_prepare_choice(void);
void tree_mouth_reset(void);
void tree_mouth_step(void);
void tree_mouth_position(int32_t *x,int32_t *y,int32_t *z);
#endif
