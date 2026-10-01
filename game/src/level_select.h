#ifndef DOSEI_LEVEL_SELECT_H
#define DOSEI_LEVEL_SELECT_H
#include <stdbool.h>
typedef struct {unsigned scene,room;bool visible,failed;} level_select_t;
extern level_select_t level_select;
void level_select_open(void);
void level_select_move(int vertical,int horizontal);
void level_select_prepare(void);
#endif
