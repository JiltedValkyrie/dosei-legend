#ifndef DOSEI_ITEM_DROP_H
#define DOSEI_ITEM_DROP_H
#include <stdint.h>
#include <stdbool.h>
/* Original ITEM00 numbers; FAIRY is the En_Elf result of FLEXIBLE. */
#define DROP_NONE 255
#define DROP_FAIRY 254
#define DROP_ACTOR_ID 0x701
#define DROP_LIFETIME 330 /* 220 source frames at 20 Hz -> 30 Hz */
typedef struct { uint8_t item, count; } item_drop_t;
item_drop_t item_drop_random(unsigned int table, unsigned int roll);
int item_drop_filter(unsigned int item);
bool item_drop_give(unsigned int item);
#endif
