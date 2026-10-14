#ifndef OOT_DODONGO_ENEMY_SPRITE_H
#define OOT_DODONGO_ENEMY_SPRITE_H
#include "sprite_actor.h"
#include "actor.h"
struct EnDodojr;
struct EnDodongo;
struct EnAm;
struct EnZf;
struct EnVm;
struct EnSw;
struct EnWf;
void DodongoSprite_Baby(EnDodojr*);
void DodongoSprite_Dodongo(EnDodongo*);
void DodongoSprite_Armos(EnAm*);
void DodongoSprite_Lizalfos(EnZf*);
void DodongoSprite_Beamos(EnVm*, PlayState*);
void DodongoSprite_Skulltula(EnSw*);
void DodongoSprite_Wolfos(EnWf*);
#endif
