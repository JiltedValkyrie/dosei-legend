#ifndef ACTION_AUDIO_H
#define ACTION_AUDIO_H
#include <stdbool.h>
#include <stdint.h>
bool action_audio_init(void);
void action_audio_events(uint32_t events);
/* game_over_events() bits (game_over.h). */
void action_audio_game_over(uint32_t events);
/* Resident fairy one-shot, available in both opening and gameplay banks. */
void action_audio_navi_dash(void);
/* Opening-only NAVY_FLY; camera travel per source update (clamped to 30). */
void action_audio_navi_flight(unsigned int speed, bool active);
/* Scene-load swap of the reserved action PCM tail; music is untouched. */
bool action_audio_set_opening(bool opening);
/* Per-area SFX bank (scene_entry_t.sfx_bank) after the resident core. */
bool action_audio_set_area(unsigned int bank);
enum { OPENING_CUT, OPENING_THUNDER, OPENING_BRIDGE, OPENING_BRIDGE_STOP,
       OPENING_HOOVES, OPENING_NEIGH, OPENING_DUST, OPENING_DASH, OPENING_RAIN,
       OPENING_NAVI_FLY, OPENING_TREE_DEATH };
void action_audio_opening_play(unsigned int sound, unsigned int channel, bool loop);
void action_audio_opening_stop(unsigned int channel);
void action_audio_tree_open(void);
void action_audio_owl_flap(void);
/* oot-core OotCoreHost.play_sfx: decomp sfxId (NA_SE_*) -> loaded PCM.
** Ids without a Saturn sample are ignored. */
void action_audio_decomp_sfx(unsigned int sfx_id);
#endif
