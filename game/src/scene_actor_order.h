/* SGL 3.02j actor/world ordering repair. Included once by kokiri_sgl.c.
 * Never reorder the level against itself; only insert actor commands into
 * geometrically valid slots between the original level commands. */
#include "actor_order.h"
#include "sgl_order_queue.h"

#define ORDER_COMMAND_CAPACITY 2700
#define ORDER_ACTOR_CAPACITY (LINK_POLYGON_COUNT + 32)

typedef struct {
    short posed[LINK_VERTEX_COUNT][3]; /* baked-world space, not camera space */
    int camera[3];
    int feet_y;
    bool valid;
} scene_order_context;
static scene_order_context scene_order_frame;
static volatile unsigned int scene_order_changed, scene_order_conflicts;
static volatile unsigned int scene_order_frames;
static volatile unsigned int scene_order_error;

/* These buffers belong only to the ordered slave callback. */
static uint32_t scene_order_commands[ORDER_COMMAND_CAPACITY];
static uint32_t scene_order_actors[ORDER_ACTOR_CAPACITY];
static actor_order_interval scene_order_intervals[ORDER_ACTOR_CAPACITY];
static uint16_t scene_order_slots[ORDER_ACTOR_CAPACITY];
static uint16_t scene_order_radix[512];

static int scene_order_abs(int value) { return value < 0 ? -value : value; }

/* Convex VDP1 polygon overlap, including collapsed triangle fourth corners.
 * Contact at an edge is not visible overlap. This tests emitted screen points,
 * so SGL's actual clipping/projection, not a second guessed camera, is used. */
static bool scene_order_overlap(const int16_t *a, const int16_t *b)
{
    int aminx=a[0], amaxx=a[0], aminy=a[1], amaxy=a[1];
    int bminx=b[0], bmaxx=b[0], bminy=b[1], bmaxy=b[1];
    unsigned int i, j, pass;
    for (i=1;i<4;++i) {
        if (a[2*i]<aminx) aminx=a[2*i];
        if (a[2*i]>amaxx) amaxx=a[2*i];
        if (a[2*i+1]<aminy) aminy=a[2*i+1];
        if (a[2*i+1]>amaxy) amaxy=a[2*i+1];
        if (b[2*i]<bminx) bminx=b[2*i];
        if (b[2*i]>bmaxx) bmaxx=b[2*i];
        if (b[2*i+1]<bminy) bminy=b[2*i+1];
        if (b[2*i+1]>bmaxy) bmaxy=b[2*i+1];
    }
    if (amaxx<=bminx || bmaxx<=aminx || amaxy<=bminy || bmaxy<=aminy)
        return false;
    /* SAT is exact only for convex perimeter order. Animation or clipping
     * can produce a concave, crossed, or degenerate emitted quad. In those
     * cases retain the conservative AABB overlap rather than discard a
     * potentially visible actor/world constraint. Adjacent duplicate corners
     * and collinear edges are valid for the usual collapsed triangle. */
    for (pass=0;pass<2;++pass) {
        const int16_t *p=pass ? b:a;
        int positive=0, negative=0;
        for (i=0;i<4;++i) {
            unsigned int next=(i+1)&3, after=(i+2)&3;
            int dx=p[2*next]-p[2*i], dy=p[2*next+1]-p[2*i+1];
            int ex=p[2*after]-p[2*next], ey=p[2*after+1]-p[2*next+1];
            int64_t turn=(int64_t)dx*ey-(int64_t)dy*ex;
            positive|=turn>0;
            negative|=turn<0;
        }
        if ((positive && negative) || (!positive && !negative))
            return true;
    }
    for (pass=0;pass<2;++pass) {
        const int16_t *p=pass ? b:a;
        for (i=0;i<4;++i) {
            unsigned int next=(i+1)&3;
            int nx=p[2*next+1]-p[2*i+1], ny=p[2*i]-p[2*next];
            int64_t alo, ahi, blo, bhi;
            if (!nx && !ny) continue;
            alo=ahi=(int64_t)nx*a[0]+(int64_t)ny*a[1];
            blo=bhi=(int64_t)nx*b[0]+(int64_t)ny*b[1];
            for (j=1;j<4;++j) {
                int64_t av=(int64_t)nx*a[2*j]+(int64_t)ny*a[2*j+1];
                int64_t bv=(int64_t)nx*b[2*j]+(int64_t)ny*b[2*j+1];
                if (av<alo) alo=av;
                if (av>ahi) ahi=av;
                if (bv<blo) blo=bv;
                if (bv>bhi) bhi=bv;
            }
            if (ahi<=blo || bhi<=alo) return false;
        }
    }
    return true;
}

static void actor_order_prepare(int x, int y, int z, int yaw)
{
    unsigned int i, k;
    scene_order_context *ctx=&scene_order_frame;
    ctx->valid=true;
    ctx->camera[0]=demo_camera.x;
    ctx->camera[1]=-demo_camera.y;
    ctx->camera[2]=demo_camera.z;
    ctx->feet_y=-y;
    jo_3d_push_matrix();
    slUnitMatrix(0);
    jo_3d_translate_matrix(x,-y,z);
    jo_3d_rotate_matrix_y((yaw*360)>>16);
    for (i=0;i<LINK_VERTEX_COUNT;++i) {
        FIXED transformed[3];
        slCalcPoint(link_pdata.pntbl[i][0],link_pdata.pntbl[i][1],
                    link_pdata.pntbl[i][2],transformed);
        for (k=0;k<3;++k) {
            int value=transformed[k]>>16;
            if (value < -32768 || value > 32767) ctx->valid=false;
            ctx->posed[i][k]=(short)value;
        }
    }
    jo_3d_pop_matrix();
    for (i=0;i<LINK_POLYGON_COUNT;++i) {
        ATTR *a=&link_pdata.attbl[i];
        if ((a->sort & (UseLight|UseGouraud)) || (a->atrb & CL_Gouraud))
            ctx->valid=false;
        a->gstb=(unsigned short)(0x8000u | (i+1));
    }
}

/* Callback and queue integration follows the adapter's verified SGL layout. */
static void scene_order_repair(void *argument);
static void actor_order_queue(void)
{
    if (scene_order_frame.valid && (kokiri_accepted_mask & 2u))
        slSlaveFunc(scene_order_repair, (void *)((uintptr_t)&scene_order_frame | 0x20000000u));
}

unsigned int kokiri_order_changed(void)
{ return *(volatile unsigned int *)((uintptr_t)&scene_order_changed | 0x20000000u); }
unsigned int kokiri_order_conflicts(void)
{ return *(volatile unsigned int *)((uintptr_t)&scene_order_conflicts | 0x20000000u); }
unsigned int kokiri_order_frames(void)
{ return *(volatile unsigned int *)((uintptr_t)&scene_order_frames | 0x20000000u); }
unsigned int kokiri_order_error(void)
{ return *(volatile unsigned int *)((uintptr_t)&scene_order_error | 0x20000000u); }

static void scene_order_repair(void *argument)
{
    const scene_order_context *ctx=(const scene_order_context *)argument;
    const PDATA *world=(const PDATA *)sgl_order_cache_through(&kokiri_pdata);
    const PDATA *actor=(const PDATA *)sgl_order_cache_through(&link_pdata);
    const POLYGON *wp=(const POLYGON *)sgl_order_cache_through(world->pltbl);
    const POLYGON *ap=(const POLYGON *)sgl_order_cache_through(actor->pltbl);
    const POINT *points=(const POINT *)sgl_order_cache_through(world->pntbl);
    sgl_order_queue queue;
    unsigned int window, count, na=0, nw=0, nc=0, i, j, k, changed=0;
    int16_t bounds[8];
    int minx=32767,maxx=-32768,miny=32767,maxy=-32768;
    sgl_order_result result;
    queue.heads=(volatile uint32_t *)Zbuffer;
    queue.sprite_memory=(volatile unsigned char *)SpriteBuf;
    queue.sprite_address=(uint32_t)(uintptr_t)SpriteBuf;
    queue.sprite_bytes=SpriteBufSize;
    ++scene_order_frames;
    if (!ctx->valid) return;
    result=sgl_order_find_window(&queue,0x8000,0x8000,ORDER_COMMAND_CAPACITY,&window);
    scene_order_error=100+result;
    if (result != SGL_ORDER_OK) goto failed;
    result=sgl_order_collect(&queue,window,scene_order_commands,ORDER_COMMAND_CAPACITY,
                             scene_order_radix,&count);
    scene_order_error=200+result;
    if (result != SGL_ORDER_OK) goto failed;
    scene_order_error=300;
    for (i=0;i<count;++i) {
        uint32_t address=scene_order_commands[i];
        volatile sgl_order_command *command=sgl_order_resolve(&queue,address);
        if (command->grda & 0x8000) {
            if (na>=ORDER_ACTOR_CAPACITY || !(command->grda & 0x7fff) ||
                (command->grda & 0x7fff)>LINK_POLYGON_COUNT) goto failed;
            scene_order_actors[na]=address;
            scene_order_intervals[na].original=(uint16_t)nw;
            for (k=0;k<4;++k) {
                int x=((volatile int16_t *)&command->xa)[2*k];
                int y=((volatile int16_t *)&command->xa)[2*k+1];
                if (x<minx) minx=x;
                if (x>maxx) maxx=x;
                if (y<miny) miny=y;
                if (y>maxy) maxy=y;
            }
            ++na;
        } else scene_order_commands[nw++]=address;
    }
    if (!na) return;
    bounds[0]=bounds[6]=(short)minx; bounds[2]=bounds[4]=(short)maxx;
    bounds[1]=bounds[3]=(short)miny; bounds[5]=bounds[7]=(short)maxy;
    /* Reuse radix scratch for the bounded screen-space candidate set. */
    scene_order_error=400;
    for (j=0;j<nw;++j) {
        volatile sgl_order_command *wc=sgl_order_resolve(&queue,scene_order_commands[j]);
        int16_t xy[8];
        if ((wc->ctrl & 15)!=2 || !wc->grda || wc->grda>world->nbPolygon) continue;
        for (k=0;k<8;++k) xy[k]=((volatile int16_t *)&wc->xa)[k];
        if (!scene_order_overlap(bounds,xy)) continue;
        if (nc>=512) goto failed;
        scene_order_radix[nc++]=(uint16_t)j;
    }
    for (i=0;i<na;++i) {
        volatile sgl_order_command *ac=sgl_order_resolve(&queue,scene_order_actors[i]);
        const POLYGON *polygon=&ap[(ac->grda & 0x7fff)-1];
        int16_t axy[8];
        actor_order_interval *interval=&scene_order_intervals[i];
        interval->lo=0; interval->hi=(uint16_t)nw;
        for (k=0;k<8;++k) axy[k]=((volatile int16_t *)&ac->xa)[k];
        unsigned int candidate;
        for (candidate=0;candidate<nc;++candidate) {
            j=scene_order_radix[candidate];
            volatile sgl_order_command *wc=sgl_order_resolve(&queue,scene_order_commands[j]);
            const POLYGON *surface;
            int16_t wxy[8];
            int origin[3];
            int64_t camera=0, low=INT64_MAX, high=INT64_MIN;
            int relation=ACTOR_ORDER_UNRESOLVED;
            int tolerance, planar=1, below_feet=1;
            if ((wc->ctrl & 15)!=2 || !wc->grda || wc->grda>world->nbPolygon)
                continue; /* Untagged fairy sprites retain their world order. */
            for (k=0;k<8;++k) wxy[k]=((volatile int16_t *)&wc->xa)[k];
            if (!scene_order_overlap(axy,wxy)) continue;
            surface=&wp[wc->grda-1];
            for (k=0;k<3;++k) {
                origin[k]=points[surface->Vertices[0]][k]>>16;
                camera+=(int64_t)surface->norm[k]*(ctx->camera[k]-origin[k]);
            }
            for (k=0;k<4;++k) {
                const short *p=ctx->posed[polygon->Vertices[k]];
                int64_t distance=(int64_t)surface->norm[0]*(p[0]-origin[0])+
                    (int64_t)surface->norm[1]*(p[1]-origin[1])+
                    (int64_t)surface->norm[2]*(p[2]-origin[2]);
                if (distance<low) low=distance;
                if (distance>high) high=distance;
            }
            tolerance=scene_order_abs(surface->norm[0])+scene_order_abs(surface->norm[1])+
                      scene_order_abs(surface->norm[2]);
            for (k=0;k<4;++k) {
                const FIXED *p=points[surface->Vertices[k]];
                int64_t distance=(int64_t)surface->norm[0]*((p[0]>>16)-origin[0])+
                    (int64_t)surface->norm[1]*((p[1]>>16)-origin[1])+
                    (int64_t)surface->norm[2]*((p[2]>>16)-origin[2]);
                if (distance>tolerance || distance < -tolerance) planar=0;
                if ((p[1]>>16)<ctx->feet_y) below_feet=0;
            }
            /* Rounded posed vertices / collision contact can penetrate a
             * sloping floor by less than two world units. Only forgive this
             * tiny contact band for floors, never walls or overhead faces. */
            if (planar && below_feet && scene_order_abs(surface->norm[1])>=55706) {
                if (camera>2*tolerance && low<0 && low>=-2*tolerance && high>2*tolerance)
                    low=0;
                if (camera < -2*tolerance && high>0 && high<=2*tolerance && low < -2*tolerance)
                    high=0;
            }
            if (planar) relation=actor_order_classify_plane(camera,low,high,tolerance);
            if (relation==ACTOR_ORDER_UNRESOLVED)
                relation=j<interval->original ? ACTOR_ORDER_WORLD_BEFORE_ACTOR :
                                               ACTOR_ORDER_ACTOR_BEFORE_WORLD;
            if (relation==ACTOR_ORDER_WORLD_BEFORE_ACTOR && interval->lo<j+1)
                interval->lo=(uint16_t)(j+1);
            if (relation==ACTOR_ORDER_ACTOR_BEFORE_WORLD && interval->hi>j)
                interval->hi=(uint16_t)j;
        }
    }
    scene_order_error=500;
    if (!actor_order_solve(scene_order_intervals,na,nw,scene_order_slots,ORDER_ACTOR_CAPACITY))
        goto failed;
    for (i=0;i<na;++i)
        if (scene_order_slots[i]!=scene_order_intervals[i].original) ++changed;
    scene_order_error=0;
    if (!changed) return;
    i=count; j=nw; k=na;
    while (i) {
        if (k && scene_order_slots[k-1]==j)
            scene_order_commands[--i]=scene_order_actors[--k];
        else if (j) scene_order_commands[--i]=scene_order_commands[--j];
        else goto failed;
    }
    result=sgl_order_rebuild(&queue,window,scene_order_commands,count,
                            (unsigned char *)scene_order_radix,sizeof(scene_order_radix));
    if (result != SGL_ORDER_OK) { scene_order_error=600+result; goto failed; }
    scene_order_changed+=changed;
    return;
failed:
    ++scene_order_conflicts;
}
