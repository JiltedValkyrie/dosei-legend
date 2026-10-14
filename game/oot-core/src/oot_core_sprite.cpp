/* Pure sprite library admission lives in the core cart, not scarce high WRAM.
 * No actor import, skeleton evaluation, pose data or mid-play disc access. */
#include "oot_core_api.h"
#include "oot_scene_blob.h"
#include "oot_sprite_archive.h"

extern const OotCoreHost* gOotCoreHost;
static unsigned int sSpriteScene;
void OotCore_SpriteSetScene(unsigned int scene) { sSpriteScene = scene; }

const unsigned char* OotCore_SpriteClip(const unsigned char* archive, unsigned int animation) {
    return OotSprite_Clip(archive, animation);
}

/* Largest archives first: a late 200+ KB request must not fail on holes the
 * small ones left. On failure *missing keeps the count in bits 0-7 and the
 * first failure in the rest for the host's error line: object id (bits 8-19),
 * library row (20-27) and reason (28-30: 1 file, 2 heap, 3 read/validate,
 * 4 invalid library count or scratch allocation). */
unsigned int OotCore_SpritePreload(const void* scene, const OotCoreSpriteLibrary* rows,
                                  unsigned int count, unsigned char** archives, unsigned int* missing,
                                  unsigned int layer) {
    static const char hex[]="0123456789ABCDEF";
    const OotSceneBlob* blob=(const OotSceneBlob*)scene;
    /* Only the destination layer's objects: OoT loads the object list of
     * the header that layer runs, so other layers' actors never spawn. */
    const unsigned int objects=OotScene_LayerObjects(blob,layer);
    int* lengths;
    unsigned int loaded=0, failed=0, first=0;
    if (!count || count>256 || !(lengths=(int*)gOotCoreHost->sprite_memory(0,count*sizeof(int)))) {
        *missing=0x40000001u; return 0;
    }
    for (unsigned int r=0;r<count;++r) {
        char file[]="G00000.SP2";
        unsigned int k;
        lengths[r]=0;
        if (rows[r].object==0xfffu) {
            /* Scene-local reward atlas: complete before any chest/cue starts. */
            file[0]='I'; file[1]=hex[(sSpriteScene>>4)&15]; file[2]=hex[sSpriteScene&15];
            file[3]='.'; file[4]='S'; file[5]='P'; file[6]='2'; file[7]=0;
        } else {
            for (k=0;k<blob->num_objects;++k)
                if (blob->objects[k]==rows[r].object && (objects>>k&1u)) break;
            if (k==blob->num_objects) continue;
            file[1]=hex[(rows[r].object>>8)&15]; file[2]=hex[(rows[r].object>>4)&15];
            file[3]=hex[rows[r].object&15]; file[4]=hex[rows[r].file>>4]; file[5]=hex[rows[r].file&15];
        }
        lengths[r]=gOotCoreHost->scene_file(file,0,0);
        if (lengths[r]<16 || (unsigned int)lengths[r]>0x800000u) {
            if (!failed++) first=(1u<<28)|(r<<20)|((rows[r].object&0xFFFu)<<8);
            lengths[r]=0;
        }
    }
    for (;;) {
        unsigned int r=count, best;
        char file[]="G00000.SP2";
        for (best=0;best<count;++best)
            if (lengths[best]>0 && (r==count || lengths[best]>lengths[r])) r=best;
        if (r==count) break;
        int length=lengths[r];
        unsigned int reason=2;
        lengths[r]=0;
        file[1]=hex[(rows[r].object>>8)&15]; file[2]=hex[(rows[r].object>>4)&15];
        file[3]=hex[rows[r].object&15]; file[4]=hex[rows[r].file>>4]; file[5]=hex[rows[r].file&15];
        if (rows[r].object==0xfffu) {
            file[0]='I'; file[1]=hex[(sSpriteScene>>4)&15]; file[2]=hex[sSpriteScene&15];
            file[3]='.'; file[4]='S'; file[5]='P'; file[6]='2'; file[7]=0;
        }
        archives[r]=(unsigned char*)gOotCoreHost->sprite_memory(0,(unsigned int)length+1);
        if (archives[r] &&
            (gOotCoreHost->scene_file(file,archives[r],(unsigned int)length)!=length ||
             !OotSprite_ArchiveValid(archives[r],(unsigned int)length,rows[r].skeleton))) {
            gOotCoreHost->sprite_memory(archives[r],0); archives[r]=0;
            reason=3;
        }
        if (archives[r]) ++loaded;
        else if (!failed++) first=(reason<<28)|(r<<20)|((rows[r].object&0xFFFu)<<8);
    }
    *missing=failed ? (first|(failed>255u ? 255u : failed)) : 0u;
    gOotCoreHost->sprite_memory(lengths,0);
    return loaded;
}
