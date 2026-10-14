#ifndef OOT_CORE_CUTSCENE_H
#define OOT_CORE_CUTSCENE_H

struct PlayState;
struct OotSceneBlob;
void OotCore_CutsceneBind(const struct OotSceneBlob* scene);
void* OotCore_CutsceneResolve(void* script);
int OotCore_CutsceneAvailable(void* script);
void OotCore_CutsceneInit(struct PlayState* play);
void OotCore_CutsceneStep(struct PlayState* play);
/* Presentation debt observed in admitted scripts: lightning, ambience,
 * fixed-background camera, quake, monochrome, long Scarecrow song respectively. */
unsigned int OotCore_CutsceneUnsupportedEffects(void);

#endif
