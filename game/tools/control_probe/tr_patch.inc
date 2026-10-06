/* Local TR-style experiment. SGL remains the sort/DMA backend; only these
 * ten existing triangles use bounded subdivision and guard-band projection.
 * No VRAM writes, tile repacking or source-material changes during drawing. */
#include "tr_patch_data.h"
extern Bool slSetSprite(SPRITE *, FIXED);
extern FIXED slCalcPoint(FIXED, FIXED, FIXED, FIXED[XYZ]);
static unsigned tr_vram;
typedef struct { unsigned char level,x,y,flags; } tr_cell;
typedef struct {
    int root[4][3]; /* Q8 view coordinates, transformed by the real SGL matrix */
    int point[25][3];
    short screen[25][2];
    unsigned emitted, dropped, clamped;
    SPRITE command[160];
    FIXED depth[160];
    int focal;
    tr_cell cell[16];
} tr_work;
#define TR_WORK ((tr_work *)RAM_LOW(0x1F000u))
typedef char tr_work_fits[(0x1F000u+sizeof(tr_work)<=RAM_LOW_SAVE_OFFSET)?1:-1];

static unsigned tr_mode(void) { return (CONTROL->hud>>8)&3u; }
static unsigned __attribute__((optimize("Os"))) tr_match(unsigned i)
{
    unsigned f,j,k;
    for(f=0;f<TR_PATCH_FACES;++f) {
        for(j=0;j<4;++j) {
            POINT *p=&kokiri_pdata.pntbl[kokiri_pdata.pltbl[i].Vertices[j]];
            for(k=0;k<3;++k)if(((*p)[k]>>16)!=tr_assets[f].world[j][k])break;
            if(k!=3)break;
        }
        if(j==4)return (f+1)<<4;
    }
    return 0;
}
static bool __attribute__((optimize("Os"))) tr_load(void)
{
    int bytes=0;
    void *data=jo_fs_read_file_ptr("TRPATCH.TEX",0,&bytes);
    tr_vram=0;
    if(!data || bytes!=TR_PATCH_BYTES || vram_used+TR_PATCH_BYTES>TEXTURE_CAPACITY) {
        if(data)jo_free(data);
        jo_core_error("TR patch bank does not fit"); return false;
    }
    tr_vram=texture_base+vram_used;
    slDMAWait();jo_dma_copy(data,(void *)(JO_VDP1_VRAM+tr_vram),bytes);slDMAWait();
    jo_free(data);vram_used+=bytes;return true;
}

/* Products fit signed 32 bits: projection uses Q4 view coordinates within
 * this local Field patch and focal distance <=512. */
static void tr_project(const int *point,short *screen)
{
    int z=point[2]>>4,inv=0,k;
    if(z<16)z=16;
    for(k=0;k<2;++k) {
        int value=point[k]>>4,limit=(k?JO_TV_HEIGHT:JO_TV_WIDTH)/2+128;
        int a=value*TR_WORK->focal;
        if(a < -limit*z)screen[k]=-limit;
        else if(a > limit*z)screen[k]=limit;
        else {
            /* One 32/32 reciprocal for both axes. The guard test bounds the
             * remaining product by limit*2^20 (<2^29). No 64-bit multiply. */
            if(!inv)inv=(TR_WORK->focal<<20)/z;
            screen[k]=(value*inv)>>20;
        }
    }
}
static void tr_submit(unsigned visible)
{
    tr_work *w=TR_WORK;
    unsigned i;
    for(i=0;i<w->emitted;++i) {
        if(visible+i+1>=GAME_TEXTURE_BASE/32-704 || !slSetSprite(&w->command[i],w->depth[i]))++kokiri_rejected;
        else ++submitted;
    }
}
/* Return 0 off-screen, otherwise bit 0 visible, bit 1 guarded, bit 2 near.
 * Homogeneous outcodes reject a cell before any division. point[0..3] is
 * scratch, never a retained pointer. Level <=4 bounds all Q8 products. */
static unsigned tr_cell_points(unsigned level,unsigned cx,unsigned cy)
{
    tr_work *w=TR_WORK;
    unsigned j,k,n=1u<<level,outside=15,flags=1;
    int far=-32768;
    for(j=0;j<4;++j) {
        unsigned x=cx+(j==1||j==2),y=cy+(j>=2),code=0;
        int px,py,z;
        for(k=0;k<3;++k) {
            int a=(w->root[0][k]*(int)(n-x)+w->root[1][k]*(int)x)>>level;
            int b=(w->root[3][k]*(int)(n-x)+w->root[2][k]*(int)x)>>level;
            w->point[j][k]=(a*(int)(n-y)+b*(int)y)>>level;
        }
        px=(w->point[j][0]>>4)*w->focal;py=(w->point[j][1]>>4)*w->focal;
        z=w->point[j][2]>>4;
        if(z>far)far=z;
        if(z<16)flags|=4;
        if(px < -(JO_TV_WIDTH/2)*z)code|=1;
        if(px > (JO_TV_WIDTH/2)*z)code|=2;
        if(py < -(JO_TV_HEIGHT/2)*z)code|=4;
        if(py > (JO_TV_HEIGHT/2)*z)code|=8;
        outside&=code;
        if(px < -(JO_TV_WIDTH/2+128)*z || px > (JO_TV_WIDTH/2+128)*z ||
           py < -(JO_TV_HEIGHT/2+128)*z || py > (JO_TV_HEIGHT/2+128)*z)flags|=2;
    }
    return outside||far<16?0:flags;
}
static void __attribute__((optimize("Os"))) tr_draw(unsigned visible)
{
    tr_work *w=TR_WORK;
    unsigned i,j,k;
    const int gx=JO_TV_WIDTH/2+128,gy=JO_TV_HEIGHT/2+128;
    if(!tr_mode() || !tr_vram || !field_active) {w->emitted=w->dropped=w->clamped=0;return;}
    if(forest_reused && w->focal==recomp_screen_distance()) {tr_submit(visible);return;}
    w->focal=recomp_screen_distance();
    w->emitted=w->dropped=w->clamped=0;
    for(i=0;i<forest_polygon_count;++i) {
        unsigned tag=forest_mesh[i]>>4,n=1,cx,cy,shift=0,count=0,ci;
        unsigned outside=15;
        int lo=32767,hi=-32768,span=0,clamp=0;
        int left=gx,right=-gx,top=gy,bottom=-gy;
        ATTR *attr=&kokiri_pdata.attbl[i];
        const tr_asset *asset;
        if(!tag || !object_visible[kokiri_objects[i]])continue;
        asset=&tr_assets[tag-1];
        if(attr->flag==Single_Plane) {
            /* Raw sprites bypass SGL's normal test. Preserve the authored
             * sidedness: otherwise an under-terrain camera sees its underside
             * painted over Link. Q12 normal dot world delta fits 32 bits. */
            const POLYGON *poly=&kokiri_pdata.pltbl[i];
            int side=(poly->norm[0]>>4)*(recomp_camera.x-asset->world[0][0])+
                     (poly->norm[1]>>4)*(-recomp_camera.y-asset->world[0][1])+
                     (poly->norm[2]>>4)*(recomp_camera.z-asset->world[0][2]);
            if(side<=0)continue;
        }
        for(j=0;j<4;++j) {
            FIXED out[3];
            int x,y,z;
            unsigned code=0;
            POINT *p=&kokiri_pdata.pntbl[kokiri_pdata.pltbl[i].Vertices[j]];
            slCalcPoint((*p)[0],(*p)[1],(*p)[2],out);
            for(k=0;k<3;++k)w->root[j][k]=out[k]>>8;
            z=w->root[j][2]>>8;
            if(z<lo)lo=z;
            if(z>hi)hi=z;
            /* Homogeneous viewport rejection before division. Valid even
             * when a corner is behind the eye; no guessed projected bounds. */
            x=(w->root[j][0]>>4)*w->focal;
            y=(w->root[j][1]>>4)*w->focal;
            z=w->root[j][2]>>4;
            if(x < -(JO_TV_WIDTH/2)*z)code|=1;
            if(x > (JO_TV_WIDTH/2)*z)code|=2;
            if(y < -(JO_TV_HEIGHT/2)*z)code|=4;
            if(y > (JO_TV_HEIGHT/2)*z)code|=8;
            outside&=code;
        }
        if(hi<1 || lo>FOREST_FAR || outside)continue;
        for(j=0;j<4;++j) {
            short xy[2];int x,y;
            tr_project(w->root[j],xy);x=xy[0];y=xy[1];
            if(x<left)left=x;
            if(x>right)right=x;
            if(y<top)top=y;
            if(y>bottom)bottom=y;
            if(w->root[j][2]<256 || x==gx || x==-gx || y==gy || y==-gy)clamp=1;
        }
        if(tr_mode()>=2) {
            /* Far/ordinary cells stay coarse. Near/large or clamped cells get
             * 2x2 then 2x2 again, never more than sixteen per input face. */
            span=right-left;if(bottom-top>span)span=bottom-top;
            if(span>96)n=2;
            if(clamp || span>192 || (lo<800 && hi>lo*2))n=4;
        }
        shift=(n==4)?2:(n==2)?1:0;
        for(cy=0;cy<n;++cy)for(cx=0;cx<n;++cx) {
            unsigned flags=tr_cell_points(shift,cx,cy);
            if(flags)w->cell[count++]=(tr_cell){shift,cx,cy,flags};
        }
        /* Two extra boundary-only levels, with the same sixteen-leaf cap.
         * Offscreen children cost no commands. Ordinary interior cells retain
         * the 1/4/16 split. No far group or source geometry is changed. */
        for(ci=0;tr_mode()>=2 && ci<count;) {
            tr_cell parent=w->cell[ci],child[4];unsigned used=0;
            if(parent.level>=4 || !(parent.flags&6)) {++ci;continue;}
            for(cy=0;cy<2;++cy)for(cx=0;cx<2;++cx) {
                unsigned x=parent.x*2+cx,y=parent.y*2+cy;
                unsigned flags=tr_cell_points(parent.level+1,x,y);
                if(flags)child[used++]=(tr_cell){parent.level+1,x,y,flags};
            }
            if(count-1+used>16) {++ci;continue;}
            memmove(&w->cell[ci+used],&w->cell[ci+1],(count-ci-1)*sizeof(tr_cell));
            for(j=0;j<used;++j)w->cell[ci+j]=child[j];
            count=count-1+used;
        }
        for(ci=0;ci<count;++ci) {
            tr_cell cell=w->cell[ci];
            SPRITE s;
            short *xy=&s.XA;
            int zmax=0,minx=gx,maxx=-gx,miny=gy,maxy=-gy,behind=0;
            tr_cell_points(cell.level,cell.x,cell.y);
            memset(&s,0,sizeof(s));
            for(j=0;j<4;++j) {
                int z=w->point[j][2]>>8,x,y;
                tr_project(w->point[j],w->screen[j]);
                x=w->screen[j][0];y=w->screen[j][1];
                if(z<1)behind=1;
                if(z>zmax)zmax=z;
                if(x<minx)minx=x;
                if(x>maxx)maxx=x;
                if(y<miny)miny=y;
                if(y>maxy)maxy=y;
                xy[j*2]=x;xy[j*2+1]=y;
                if(x==gx||x==-gx||y==gy||y==-gy)++w->clamped;
            }
            /* Reject near-crossing cells. Guard clamping behind the eye was
             * tested and rejected: it can cover the player with a folded quad. */
            if(behind || zmax<1 || minx>JO_TV_WIDTH/2 || maxx < -JO_TV_WIDTH/2 ||
               miny>JO_TV_HEIGHT/2 || maxy < -JO_TV_HEIGHT/2 || minx==maxx || miny==maxy) {
                ++w->dropped;continue;
            }
            s.CTRL=2;s.PMOD=attr->atrb & ~MESHon;s.COLR=attr->colno;
            if((forest_mesh[i]&1) || lo>FOREST_FAR*7/8)s.PMOD|=MESHon;
            if(tr_mode()<2) {s.SRCA=__jo_sprite_def[attr->texno].adr;s.SIZE=__jo_sprite_def[attr->texno].size;}
            else {
                unsigned div=1u<<cell.level,tx=cell.x,ty=cell.y;
                unsigned width=asset->width/div;
                unsigned offset;
                if(width<8)width=8;
                offset=asset->offset[cell.level]*8+(ty*div+tx)*width*(asset->height/div)/2;
                s.SRCA=(tr_vram+offset)/8;
                s.SIZE=(width<<5)|(asset->height/div);
            }
            /* These selected assets are upward-facing, single-sided ground.
             * Far sort keeps standing actors ahead of each small floor cell. */
            if(zmax<32)zmax=32;
            w->command[w->emitted]=s;
            w->depth[w->emitted]=zmax*65536;
            ++w->emitted;
        }
    }
    tr_submit(visible);
}
