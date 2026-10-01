#ifndef DOSEI_STORY_ROUTE_H
#define DOSEI_STORY_ROUTE_H
#include <stdbool.h>
void story_route_free(void);
bool story_route_load(unsigned scene);
void story_route_arrive(unsigned spawn);
void story_route_finish(void);
void story_route_step(void);
void story_route_draw(unsigned tick);
bool story_owl_talking(void);
void story_owl_camera(void);
unsigned story_owl_screen_distance(void);
#endif
