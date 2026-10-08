#ifndef DOSEI_LEVEL_SELECT_H
#define DOSEI_LEVEL_SELECT_H
#include <stdbool.h>
typedef struct {unsigned scene,room;bool visible,failed,max_gear,adult;unsigned page,region,cursor,map_cursor;} level_select_t;
enum {LEVEL_REGIONS,LEVEL_MAPS,LEVEL_OPTIONS};
enum {LEVEL_NONE,LEVEL_BEGIN,LEVEL_BACK};
unsigned level_select_count(void);
unsigned level_select_map(unsigned region,unsigned index);
const char *level_select_region(unsigned region);
unsigned level_select_step(int vertical,int horizontal,bool confirm,bool cancel);
extern level_select_t level_select;
void level_select_open(void);
void level_select_move(int vertical,int horizontal);
void level_select_toggle_max_gear(void);
void level_select_toggle_era(void);
void level_select_prepare(void);
#endif
