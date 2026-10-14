#ifndef OOT_CUTSCENE_CAMERA_H
#define OOT_CUTSCENE_CAMERA_H

struct PlayState;
struct Actor;

/* Copied after the core joins; no core pointers cross into the renderer. */
typedef struct OotCoreCutsceneCameraView {
    int eye[3], at[3];
    int fov_q8;
    short roll;
    unsigned char active, letterbox;
} OotCoreCutsceneCameraView;

void OotCore_CutsceneCameraReset(struct PlayState* play);
void OotCore_CutsceneCameraSeed(struct PlayState* play, const OotCoreCutsceneCameraView* view);
void OotCore_CutsceneCameraStep(struct PlayState* play);
int OotCore_CutsceneCameraRead(struct PlayState* play, OotCoreCutsceneCameraView* out);
void OotCore_CameraActorScreenPos(struct PlayState*, struct Actor*, short*, short*);

#endif
