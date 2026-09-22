#ifndef DOSEI_CUTSCENE_H
#define DOSEI_CUTSCENE_H

#include <stdbool.h>
#include <stdint.h>
#include "cutscenes.h"

bool            cutscene_start(unsigned int id);
bool            cutscene_step(bool confirm);
bool            cutscene_is_playing(void);
bool            cutscene_finished(void);
unsigned int    cutscene_id(void);
unsigned int    cutscene_frame(void);

#endif
