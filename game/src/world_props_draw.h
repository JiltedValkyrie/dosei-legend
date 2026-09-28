#ifndef WORLD_PROPS_DRAW_H
#define WORLD_PROPS_DRAW_H
#include <stdbool.h>
bool world_props_draw_load(unsigned int scene);
void world_props_draw_free(void);
bool world_props_draw_upload(void);
void world_props_draw(unsigned int tick);
#endif
