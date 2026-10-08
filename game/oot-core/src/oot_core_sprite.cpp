/* Pure sprite library admission lives in the core cart, not scarce high WRAM.
 * No actor import, skeleton evaluation, pose data or mid-play disc access. */
#include "oot_core_api.h"
#include "oot_scene_blob.h"
#include "oot_sprite_archive.h"

extern const OotCoreHost* gOotCoreHost;

const unsigned char* OotCore_SpriteClip(const unsigned char* archive, unsigned int animation) {
    return OotSprite_Clip(archive, animation);
}

unsigned int OotCore_SpritePreload(const void* scene, const OotCoreSpriteLibrary* rows,
                                  unsigned int count, unsigned char** archives, unsigned int* missing) {
    static const char hex[]="0123456789ABCDEF";
    const OotSceneBlob* blob=(const OotSceneBlob*)scene;
    unsigned int loaded=0;
    *missing=0;
    for (unsigned int r=0;r<count;++r) {
        char file[]="G00000.SP2";
        unsigned int k;
        int length;
        for (k=0;k<blob->num_objects;++k) if (blob->objects[k]==rows[r].object) break;
        if (k==blob->num_objects) continue;
        file[1]=hex[(rows[r].object>>8)&15]; file[2]=hex[(rows[r].object>>4)&15];
        file[3]=hex[rows[r].object&15]; file[4]=hex[rows[r].file>>4]; file[5]=hex[rows[r].file&15];
        length=gOotCoreHost->scene_file(file,0,0);
        if (length<16 || (unsigned int)length>0x800000u) { ++*missing; continue; }
        archives[r]=(unsigned char*)gOotCoreHost->sprite_memory(0,(unsigned int)length+1);
        if (archives[r] &&
            (gOotCoreHost->scene_file(file,archives[r],(unsigned int)length)!=length ||
             !OotSprite_ArchiveValid(archives[r],(unsigned int)length,rows[r].skeleton))) {
            gOotCoreHost->sprite_memory(archives[r],0); archives[r]=0;
        }
        if (archives[r]) ++loaded;
        else ++*missing;
    }
    return loaded;
}
