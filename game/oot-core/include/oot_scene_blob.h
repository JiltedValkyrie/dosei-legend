/*
 * Scene data blob layout (<NAME>COL.BIN, oot-core/scenecol.ld). Shared by C
 * (host) and oot-core C++. OotSceneBlob sits at the blob's load address; the
 * pointers inside are absolute (blob linked at OOT_SCENECOL_ADDR). Data is cut
 * verbatim from the extracted scene/room .c files by tools/oot_core_import.py.
 */
#ifndef OOT_SCENE_BLOB_H
#define OOT_SCENE_BLOB_H

#define OOT_SCENE_MAX_ROOMS 32

typedef struct OotSceneRoom {
    const void* actors;       /* decomp ActorEntry[] of the room's main header */
    unsigned int num_actors;
} OotSceneRoom;

typedef struct OotSceneBlob {
    const void* col_header;   /* decomp CollisionHeader */
    unsigned int num_rooms;
    OotSceneRoom rooms[OOT_SCENE_MAX_ROOMS];
} OotSceneBlob;

#endif
