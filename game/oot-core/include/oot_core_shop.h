#ifndef OOT_CORE_SHOP_H
#define OOT_CORE_SHOP_H
/* Source EnOssan state, copied after update before host input/drawing. */
#define OOT_SHOP_OWNED 1u
#define OOT_SHOP_BROWSING 2u
#define OOT_SHOP_CONTROL 4u
#define OOT_SHOP_CURSOR 8u
#define OOT_SHOP_LEFT 16u
#define OOT_SHOP_RIGHT 32u
typedef struct OotCoreShopView {
    unsigned short flags;
    short face_degrees;
    int cursor[3];
    unsigned char state, cursor_index, pulse, reserved;
} OotCoreShopView;
#endif
