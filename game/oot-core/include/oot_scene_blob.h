/*
 * Scene data blob layout (<scene>.OOC, oot-core/scenecol.ld). Shared by C
 * (host) and oot-core C++. OotSceneBlob sits at the blob's load address; the
 * pointers inside are absolute (blob linked at OOT_SCENECOL_ADDR). Data is cut
 * verbatim from the extracted scene/room .c files by tools/oot_core_import.py.
 */
#ifndef OOT_SCENE_BLOB_H
#define OOT_SCENE_BLOB_H

#define OOT_SCENE_MAX_ROOMS 32
/* Objects any layer lists (32-bit layer masks). One layer's objects take
 * ObjectContext slots: 32 minus gameplay_keep and the Player stub. */
#define OOT_SCENE_MAX_OBJECTS 32
#define OOT_SCENE_MAX_LAYER_OBJECTS 30
#define OOT_SCENE_BLOB_FORMAT 0x4f4f4305u

typedef struct OotSceneCutscene {
    unsigned int id;
    const void* script;
    unsigned int bytes;
} OotSceneCutscene;

/* One room's actor list in one scene layer (0 = main header, L = room
 * AltHeaders[L - 1]). present 0: no header for that layer (NULL entry), the
 * runtime falls back as Scene_CommandAlternateHeaderList does. */
typedef struct OotSceneLayer {
    const void* actors;          /* decomp ActorEntry[] or NULL */
    unsigned short num_actors; /* room ActorEntry count, or scene Path count */
    unsigned short present;
    unsigned short time;       /* baked Scene_CommandTimeSettings conversion */
    unsigned char time_speed;
    unsigned char time_flags;  /* bit 0 command exists; bit 1 sets time */
    unsigned char room_type;
    unsigned char behavior_flags; /* bit 0 command exists; bit 1 disables warp songs */
    unsigned char sky_id, sky_config, sky_light, sky_flags;
    unsigned char seq_id, nature_id, sound_flags;
} OotSceneLayer;

typedef struct OotSceneBlob {
    const void* col_header;      /* decomp CollisionHeader */
    unsigned int num_rooms;
    unsigned int num_layers;
    const OotSceneLayer* layers; /* [room * num_layers + layer] */
    /* Data objects (O<id>.OOB, oot_core_import.py OBJECTS) that any room or
     * layer of the scene lists: the host loads them after this blob. */
    const unsigned short* objects;
    unsigned int num_objects;
    /* Scene_CommandPathList per scene layer (actors = decomp Path[] or
     * NULL; present 0 = no header for that layer). */
    const OotSceneLayer* paths;
    unsigned int num_path_layers;
    /* ABI26: reject older blobs before reading appended transition lists. */
    unsigned int format;
    const OotSceneLayer* transitions; /* original TransitionActorEntry[], per layer */
    unsigned int num_transition_layers;
    const OotSceneLayer* exits; /* original s16 exit lists, per scene layer */
    unsigned int num_exit_layers;
    const OotSceneCutscene* cutscenes; /* complete scene-local source scripts */
    unsigned int num_cutscenes;
    /* Format 5: bit k of layer_objects[L] = objects[k] is in scene layer L
     * (union of the room object lists that layer's headers name, with the
     * room-layer fallback; keep/shop/boss-reward objects in every layer).
     * At least layers 0-3; a higher layer the scene lacks uses [0]. */
    const unsigned int* layer_objects;
    unsigned int num_object_layers;
} OotSceneBlob;

#define OOT_SCENE_MAX_OBJECT_LAYERS 64

/* Objects scene layer `layer` loads (OoT: the active header's object list).
 * A macro: host headers take no new static inline bodies (BUILD.md 110). */
#define OotScene_LayerObjects(blob, layer)     ((layer) < (blob)->num_object_layers ? (blob)->layer_objects[layer] : (blob)->layer_objects[0])

#endif
