#ifndef VIEWER_DEMO_H
#define VIEWER_DEMO_H
#include "kokiri_camera.h"
bool demo_init(void);
void demo_update(void);
extern camera_position_t demo_camera;
extern uint16_t demo_yaw;
extern int32_t demo_pitch;
#endif
