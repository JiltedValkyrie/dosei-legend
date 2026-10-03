/*
 * Scene data blob layout (<scene>.OOC, oot-core/scenecol.ld). Shared by C
 * (host) and oot-core C++. OotSceneBlob sits at the blob's load address; the
 * pointers inside are absolute (blob linked at OOT_SCENECOL_ADDR). Data is cut
 * verbatim from the extracted scene/room .c files by tools/oot_core_import.py.
 */
#ifndef OOT_SCENE_BLOB_H
#define OOT_SCENE_BLOB_H

#define OOT_SCENE_MAX_ROOMS 32

/* One room's actor list in one scene layer (0 = main header, L = room
 * AltHeaders[L - 1]). present 0: no header for that layer (NULL entry), the
 * runtime falls back as Scene_CommandAlternateHeaderList does. */
typedef struct OotSceneLayer {
    const void* actors;          /* decomp ActorEntry[] or NULL */
    unsigned short num_actors;
    unsigned short present;
} OotSceneLayer;

typedef struct OotSceneBlob {
    const void* col_header;      /* decomp CollisionHeader */
    unsigned int num_rooms;
    unsigned int num_layers;
    const OotSceneLayer* layers; /* [room * num_layers + layer] */
} OotSceneBlob;

#endif
