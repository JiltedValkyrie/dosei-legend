#ifndef ACTION_AUDIO_H
#define ACTION_AUDIO_H
#include <stdbool.h>
#include <stdint.h>
bool action_audio_init(void);
void action_audio_events(uint32_t events);
/* Scene-load swap of the reserved action PCM tail; music is untouched. */
bool action_audio_set_opening(bool opening);
enum { OPENING_CUT, OPENING_THUNDER, OPENING_BRIDGE, OPENING_BRIDGE_STOP,
       OPENING_HOOVES, OPENING_NEIGH, OPENING_DUST, OPENING_DASH, OPENING_RAIN };
void action_audio_opening_play(unsigned int sound, unsigned int channel, bool loop);
void action_audio_opening_stop(unsigned int channel);
#endif
