#ifndef KOKIRI_SCENE_H
#define KOKIRI_SCENE_H
#include <yaul.h>
void kokiri_scene_init(void);
void kokiri_scene_camera_update(const smpc_peripheral_digital_t *pad, bool title_visible);
void kokiri_scene_update_and_draw(void);
#endif
