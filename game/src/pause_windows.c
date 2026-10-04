/* Full RGB pause pages on scaling NBG0. NBG1 keeps the frozen room backdrop.
 * Font/HUD are restored exactly on exit; no VDP1 textures or commands. */
#include <jo/jo.h>
#include "pause_windows.h"
#include "gameplay.h"
#include "save_state.h"
#include "ram_cart.h"
#include "demo.h"
#include "sgl_registers.h"
#include "pause_cursor_data.h"
#include "dungeon_map_data.h"
#include "pause_inventory_data.h"
#include "scene_flow.h"
#include "minimap.h"
#pragma GCC optimize ("Os")

#define PAGE_BYTES (320u * 240u * 2u)
#define PAGE_MAP ((volatile unsigned short *)0x25E3C000u)
#define CELLS0 ((volatile unsigned short *)0x25E40000u)
#define CELLS1 ((volatile unsigned short *)0x25E68000u)
static int loaded = -1, drawn = -1, direction;
static unsigned phase, started;
static bool failed, active;
static unsigned int cycles[4];
static const unsigned char *icons;

static unsigned icon_u16(const unsigned char *p) { return (unsigned)p[0]*256u+p[1]; }
static const unsigned char *icon_record(unsigned item)
{
    return icons && item<PAUSE_ICON_COUNT ? icons+PAUSE_ICON_META+item*PAUSE_ICON_RECORD : 0;
}
const char *pause_windows_item_name(unsigned item)
{
    const unsigned char *p=icon_record(item);
    return p ? (const char *)p : "";
}
static unsigned equipment_item(unsigned slot)
{
    unsigned row=slot/4,col=slot%4;
    if (slot>=16) return 255;
    if (!col) {
        unsigned shift=row==0 ? (save_state.link_age ? 14 : 0) : row*3;
        unsigned level=(save_state.source_upgrades>>shift)&7;
        unsigned base=row==0 ? (save_state.link_age ? 0x47 : 0x4a) : row==1 ? 0x4d : row==2 ? 0x50 : 0x53;
        return level && level<=(row==3 ? 2u : 3u) ? base+level-1 : 255;
    }
    unsigned owned=save_state.source_equipment | 0x1100u;
    if (save_state.owned_sword>=1 && save_state.owned_sword<=3) owned|=1u<<(save_state.owned_sword-1);
    if (save_state.owned_shield>=1 && save_state.owned_shield<=3) owned|=16u<<(save_state.owned_shield-1);
    if (save_tunic_unlocked(1)) owned|=0x400;
    if (save_tunic_unlocked(2)) owned|=0x200;
    return owned&(1u<<(row*4+col-1)) ? 0x3b+row*3+col-1 : 255;
}
const char *pause_windows_selection_name(void)
{
    const pause_window_state_t *s=&gameplay.pause_window;
    unsigned cursor=s->cursor[s->page], item=255;
    if (s->page==PAUSE_ITEMS) item=save_inventory_item(cursor);
    else if (s->page==PAUSE_EQUIPMENT) item=equipment_item(cursor);
    else if (s->page==PAUSE_MAP) return scene_name(scene_flow_scene());
    else if (s->page==PAUSE_QUEST && cursor<24 && icons && (save_state.quest_items&(1u<<cursor)))
        item=icon_u16(icons+cursor*6);
    return pause_windows_item_name(item);
}

static unsigned short *cache(void) { return ram_cart_fixed(RAM_CART_PAUSE_OFFSET, RAM_CART_PAUSE_BYTES); }
static volatile unsigned short *cell(unsigned tile)
{
    return tile < 1024 ? CELLS0 + tile * 64 : CELLS1 + (tile - 1024) * 64;
}
static void copy_words(volatile unsigned short *to, const volatile unsigned short *from, unsigned count)
{
    while (count--) *to++ = *from++;
}
static bool read_file(const char *name, void *data, unsigned size)
{
    /* One GFS_Load, not one CD request per 2 KB sector (seconds on hardware).
     * The read writes one terminator byte after `size`: a page clears font
     * byte 0 (char 0, never printed); the font's lands in carve slack. */
    jo_file file;
    int len=0;
    bool ok;
    if (!jo_fs_open(&file, (char *)name)) return false;
    ok = file.size == size;
    jo_fs_close(&file);
    return ok && jo_fs_read_file_ptr(name,data,&len) && len==(int)size;
}
static bool begin(void)
{
    unsigned short *backup=ram_cart_fixed(RAM_CART_PAUSE_BACKUP_OFFSET,RAM_CART_PAUSE_BACKUP_BYTES);
    unsigned i;
    if (!backup || !cache() || !minimap_icons_ready() ||
        !read_file("PAUSEFNT.BIN",(char *)cache()+PAGE_BYTES,1024)) return false;
    copy_words(backup,CELLS0,0x10000);
    /* The source atlas was validated once at HUD init. Its exact B0 backup
     * survives while pause paints over VRAM: no second 56 KB allocation or CD
     * read on every open. This pointer belongs to the fixed backup carve. */
    icons=(const unsigned char *)backup+0x12000;
    copy_words(backup+0x10000,CELLS1,0x2C40);
    copy_words(backup+0x12C40,PAGE_MAP,0x2000);
    for (i=0;i<4;++i)
        cycles[i]=*(volatile unsigned int *)sgl_vdp2_shadow(0x10+i*4);
    /* RGB NBG0 uses ZOOM_1 (enlargement only), four character fetches.
     * Names live in unused bottom rows of the NBG1 bitmap. A1 retains
     * four NBG1 bitmap fetches and three CPU slots alongside one name. */
    slScrCycleSet(cycles[0],0x05555EEE,0x4444EEEE,0x4444EEEE);
    for (i=0;i<64;++i) cell(1200)[i]=0;
    for (i=0;i<4096;++i) {
        unsigned x=i%64,y=i/64;
        unsigned tile=x<40 && y<30 ? y*40+x : 1200;
        PAGE_MAP[i*2]=0;
        PAGE_MAP[i*2+1]=((unsigned)cell(tile)-0x25E00000u)/32u;
    }
    slCharNbg0(COL_TYPE_32768,CHAR_SIZE_1x1);
    slPageNbg0((void *)CELLS0,(void *)JO_VDP2_CRAM,PNB_2WORD);
    slPlaneNbg0(PL_SIZE_1x1);
    slMapNbg0((void *)PAGE_MAP,(void *)PAGE_MAP,(void *)PAGE_MAP,(void *)PAGE_MAP);
    slZoomModeNbg0(ZOOM_1);
    slScrWindowModeNbg0(win0_IN);
    active=true;
    return true;
}
void pause_windows_reset(void)
{
    icons=0;
    if (active) {
        const unsigned short *backup=ram_cart_fixed(RAM_CART_PAUSE_BACKUP_OFFSET,RAM_CART_PAUSE_BACKUP_BYTES);
        copy_words(CELLS0,backup,0x10000);
        copy_words(CELLS1,backup+0x10000,0x2C40);
        copy_words(PAGE_MAP,backup+0x12C40,0x2000);
        slScrCycleSet(cycles[0],cycles[1],cycles[2],cycles[3]);
        slCharNbg0(COL_TYPE_256,CHAR_SIZE_1x1);
        slPageNbg0((void *)VDP2_VRAM_B1,(void *)JO_VDP2_CRAM,PNB_1WORD | CN_10BIT);
        slPlaneNbg0(PL_SIZE_1x1);
        slMapNbg0((void *)NBG0_MAP,(void *)NBG0_MAP,(void *)NBG0_MAP,(void *)NBG0_MAP);
        slZoomModeNbg0(ZOOM_1);
        slZoomNbg0(65536,65536); slScrPosNbg0(0,0);
        slScrWindowModeNbg0(0);
    }
    loaded=drawn=-1; phase=0; active=failed=false;
}
bool pause_windows_failed(void) { return failed; }
bool pause_windows_text_ready(void)
{
    const pause_window_state_t *s=&gameplay.pause_window;
    unsigned page=s->system_confirm ? PAUSE_EXTRA : s->save_prompt ? PAUSE_SAVE : s->page;
    return active && !failed && phase!=1 && loaded/32==(int)page;
}
static void pixel(int x,int y,unsigned colour)
{
    if (x<0 || x>=320 || y<0 || y>=240) return;
    cell((y/8)*40+x/8)[(y&7)*8+(x&7)]=colour;
}
static void pulse_map_marker(unsigned now)
{
    /* Two-second UI-clock breath. Keep the white ring and dark outline
     * steady so the current region remains readable at minimum brightness. */
    unsigned t=now%120u, level, colour;
    int x,y,cx,cy;
    unsigned scene=scene_flow_entry()->oot_scene;
    /* Scene_CommandMiscSettings: these interiors share scene IDs between
     * Market (child) and Kakariko (adult). Preserve that source exception. */
    if (!save_state.link_age && (scene==0x2C || scene==0x42)) scene=0x52;
    if (!icons || scene>=124) return;
    cx=icon_u16(icons+144+scene*4); cy=icon_u16(icons+146+scene*4);
    if (!cx || !cy) return;
    if (t>60u) t=120u-t;
    level=t*t*(180u-2u*t)/7200u; /* smoothstep, 0..30 */
    colour=0x8000u | (20u+11u*level/30u) |
           ((12u+16u*level/30u)<<5) | ((level/10u)<<10);
    for (y=-9;y<=9;++y)
        for (x=-9;x<=9;++x) {
            unsigned r=x*x+y*y;
            if (r<=81) pixel(cx+x,cy+y,r<=25 ? colour : r<=49 ? 0xffff : 0x8000);
        }
}
static void frame(int x, int y, int size, unsigned colour)
{
    int side, xx, yy, dx, dy;
    for (side = 0; side < 4; ++side) {
        xx = x + ((side & 1) ? size - 15 : 0);
        yy = y + ((side & 2) ? size - 15 : 0);
        for (dy = 0; dy < 16; ++dy)
            for (dx = 0; dx < 16; ++dx)
                if (pause_cursor_masks[side][dy] & (1u << dx))
                    pixel(xx + dx, yy + dy, colour);
    }
}


static bool dungeon_map(void)
{
    return save_state.scene_id == SAVE_SCENE_DEKU_TREE ||
           save_state.scene_id == SAVE_SCENE_DEKU_TREE_BOSS;
}
static unsigned map_colour(unsigned tag)
{
    unsigned floor=gameplay.pause_window.cursor[PAUSE_MAP]%5;
    unsigned rooms=deku_map_rooms[floor][tag&15];
    if (rooms & save_state.deku_visited_rooms) return 0xFD40; /* source visited blue */
    if (rooms && (save_state.deku_dungeon_items&2)) return 0xBDEF; /* unvisited */
    if ((tag&15)==14) return 0xA108; /* source map background */
    if ((tag&15)==15 && (save_state.deku_dungeon_items&2)) return 0x8000;
    return 0x8C41;
}
static void paint(void)
{
    const unsigned short *data=cache();
    unsigned x,y,tile,i;
    for (tile=0;tile<1200;++tile) {
        volatile unsigned short *dst=cell(tile);
        x=(tile%40)*8; y=(tile/40)*8;
        for (i=0;i<64;++i) {
            unsigned colour=data[(y+i/8)*320+x+i%8];
            if (loaded/32==PAUSE_MAP && loaded%32 && colour>=0x10 && colour<=0x1F)
                colour=map_colour(colour);
            dst[i]=colour;
        }
    }
}
void pause_windows_print(int x,int y,const char *text)
{
    const unsigned short *data=cache();
    const unsigned char *font=(const unsigned char *)data+PAGE_BYTES;
    if (!pause_windows_text_ready() || !data || y<0 || y>=30) return;
    while (*text && x<40) {
        unsigned c=(unsigned char)*text++,xx,yy;
        if (x>=0) for (yy=0;yy<8;++yy) for (xx=0;xx<8;++xx) {
            unsigned colour=data[(y*8+yy)*320+x*8+xx];
            if (c<128 && (font[c*8+yy] & (0x80u>>xx))) colour=0xFFFF;
            pixel(x*8+xx,y*8+yy,colour);
        }
        ++x;
    }
}
static void stamp_icon(unsigned item,unsigned left,unsigned top,unsigned width,unsigned height,bool dim)
{
    const unsigned char *p=icon_record(item);
    unsigned x,y;
    if (!p || left+width>320 || top+height>240) return;
    p+=32;
    for (y=0;y<height;++y) for (x=0;x<width;++x) {
        unsigned at=(y*28/height)*28+x*28/width;
        unsigned index=(p[32+at/2]>>(at&1 ? 0 : 4))&15;
        if (index) {
            unsigned colour=icon_u16(p+index*2);
            if (dim) {
                unsigned grey=((colour&31)+((colour>>5)&31)+((colour>>10)&31))/4;
                colour=0x8000u | grey | (grey<<5) | (grey<<10);
            }
            cache()[(top+y)*320+left+x]=colour;
        }
    }
}
static void compose_inventory(unsigned page)
{
    unsigned i;
    if (page==PAUSE_ITEMS) for (i=0;i<24;++i)
        stamp_icon(save_inventory_item(i),66+(i%6)*32,64+(i/6)*32,28,28,!save_inventory_slot_usable(i));
    else if (page==PAUSE_QUEST) for (i=0;i<24;++i) {
        const unsigned char *q=icons+i*6;
        if (save_state.quest_items&(1u<<i)) stamp_icon(icon_u16(q),q[2],q[3],q[4],q[5],false);
    }
    else if (page==PAUSE_EQUIPMENT) for (i=0;i<16;++i)
        stamp_icon(equipment_item(i),i%4 ? 142+(i%4)*32 : 48,64+(i/4)*32,28,28,false);
}
static bool load_page(int key)
{
    char name[]="PAUSE00.BIN";
    name[5]+=key/32; name[6]="0123456789ABCDEF"[key%32];
    failed=!read_file(name,cache(),PAGE_BYTES);
    if (!failed) compose_inventory(key/32);
    loaded=key; drawn=-1;
    return !failed;
}
static void transform(unsigned t)
{
    int width=320,height=240,centre=160,left,top,right,bottom;
    /* RGB555 normal planes allow enlargement, not sub-1x reduction.
     * Bring each departing/arriving page forward on the carousel arc. */
    if (phase==1) { width+=64*(int)t/12; height+=48*(int)t/12; centre-=direction*400*(int)t/12; }
    if (phase==2) { width=384-64*(int)t/12; height=288-48*(int)t/12; centre+=direction*400*(12-(int)t)/12; }
    left=centre-width/2; top=120-height/2; right=left+width-1;
    bottom=top+height-1;
    /* SGL takes reciprocal scales; scroll origin uses source pixels. */
    slZoomNbg0(320*65536/width,240*65536/height);
    slScrPosNbg0((-left*65536/width)*320,(-top*65536/height)*240);
    if (left<0) left=0; if (left>319) left=319;
    if (right<left) right=left; if (right>319) right=319;
    if (top<0) top=0; if (bottom>239) bottom=239;
    slScrWindow0(left,top,right,bottom);
}
bool pause_windows_update(void)
{
    pause_window_state_t *s=&gameplay.pause_window;
    unsigned page=s->system_confirm ? PAUSE_EXTRA : s->save_prompt ? PAUSE_SAVE : s->page;
    unsigned variant=page==PAUSE_MAP && dungeon_map() ? 1+s->cursor[PAUSE_MAP]%5 : 0;
    int key=page*32+variant;
    int cursor=s->save_prompt ? s->save_choice : s->cursor[s->page];
    int stamp=cursor+(gameplay.equipped<<8)+(s->system_confirm<<16)+(save_state.tunic<<12);
    if (page==PAUSE_EQUIPMENT) stamp^=(save_state.equip_sword<<20)|(save_state.equip_shield<<24);
    unsigned now=demo_clock(),t;
    if (page==PAUSE_ITEMS) stamp=cursor | (save_state.c_items[0]<<5) | (save_state.c_items[1]<<11) | (save_state.c_items[2]<<17);
    if (failed) return false;
    if (!active && !begin()) { failed=true; return false; }
    if (loaded<0) { if (!load_page(key)) goto fail; }
    if (!phase && key!=loaded) {
        if (key/32!=loaded/32 && page!=PAUSE_SAVE && loaded/32!=PAUSE_SAVE && !s->system_confirm) {
            int from=loaded/32==PAUSE_EXTRA ? 4 : loaded/32;
            int to=page==PAUSE_EXTRA ? 4 : page;
            direction=((to-from+5)%5)<=2 ? 1 : -1;
            phase=1; started=now;
        } else if (!load_page(key)) goto fail;
    }
    t=now-started;
    if (phase && t>=12) {
        if (phase==1) {
            if (!load_page(key)) goto fail;
            phase=2; started=demo_clock(); t=0;
        } else { phase=0; t=0; }
    }
    if (phase==1) { transform(t); return !failed; }
    if (key!=loaded) { transform(phase ? t : 0); return !failed; }
    if (failed) return false;
    if (stamp!=drawn) {
        paint();
        if (page==PAUSE_ITEMS) {
            unsigned i;
            for (i=0;i<3;++i) {
                unsigned slot=save_c_item_inventory_slot(save_state.c_items[i]);
                if (slot<24) frame(65+(slot%6)*32,63+(slot/6)*32,29,0x83FF);
            }
            frame(64+(cursor%6)*32,62+(cursor/6)*32,31,0xFF50);
        }
        else if (page==PAUSE_EQUIPMENT) {
            static const short columns[4]={46,172,204,236};
            if (save_state.equip_sword>=1 && save_state.equip_sword<=3) frame(141+save_state.equip_sword*32,63,29,0x83FF);
            if (save_state.equip_shield>=1 && save_state.equip_shield<=3) frame(141+save_state.equip_shield*32,95,29,0x83FF);
            frame(save_state.tunic==1?237:save_state.tunic==2?205:173,127,29,0x83FF);
            frame(columns[cursor%4],62+(cursor/4)*32,31,0xFF50);
        } else if (page==PAUSE_SAVE) frame(cursor ? 168 : 100,118,47,0xFF50);
        else if (page==PAUSE_QUEST && cursor<24 && icons) {
            const unsigned char *q=icons+cursor*6;
            frame(q[2]-1,q[3]-1,q[4]+2,0xFF50);
        }
        drawn=stamp;
    }
    if (page==PAUSE_MAP) {
        if (!variant) pulse_map_marker(now);
        else {
            static const char *floors[5]={"3F","2F","1F","B1","B2"};
            unsigned f;
            for (f=0;f<5;++f) {
                pause_windows_print(6,6+f*3,floors[f]);
                pause_windows_print(5,6+f*3,f==variant-1 ? ">" : " ");
            }
        }
    }
    transform(phase ? t : 0);
    return true;
fail:
    pause_windows_reset();
    failed=true;
    return false;
}
