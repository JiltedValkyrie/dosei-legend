#ifndef OOT_CORE_AUDIO_H
#define OOT_CORE_AUDIO_H
/* Source requests cross to the Saturn audio backend at a joined frame. */
#define OOT_CORE_AUDIO_FANFARE 1u
#define OOT_CORE_AUDIO_SEQUENCE 2u
#define OOT_CORE_AUDIO_STOP 3u
#define OOT_CORE_AUDIO_MAIN_VOLUME 4u
#define OOT_CORE_AUDIO_PUSH_SEQUENCE 5u
#define OOT_CORE_AUDIO_POP_SEQUENCE 6u
#define OOT_CORE_AUDIO_MINIGAME_TEMPO 7u
#define OOT_CORE_AUDIO_SINGING 8u
#define OOT_CORE_AUDIO_SPATIAL 9u
#define OOT_CORE_AUDIO_SFX_PITCH 10u /* command high byte: frequency ratio Q6 */
#define OOT_CORE_AUDIO_TEMPO 11u /* Q8 main BGM tempo after fanfare; no pitch shift */
void OotCore_RouteAudioBegin(void);
void OotCore_RouteAudioEnd(void);
void OotCore_AudioRequest(unsigned int command, unsigned int argument);
#endif
