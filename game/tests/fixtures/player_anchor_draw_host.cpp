/* Gameplay-visible outputs of the real Actor_Draw and Feet shadow wrappers. */
typedef Fx f32;
typedef int s32;
typedef unsigned int u32;
typedef unsigned char u8;
typedef struct { f32 x,y,z; } Vec3f;
typedef struct { short x,y,z; } Vec3s;
typedef struct { int unused; } MtxF, CollisionPoly, CollisionContext, FaultClient;
typedef struct { u8 r,g,b,a; } Color_RGBA8;
typedef struct { struct { signed char dir[3]; u8 col[3]; } l; } Light;
typedef struct { int numLights; struct { Light l[8]; } l; } Lights;
struct Actor;
struct PlayState;
typedef void (*Shadow)(Actor*,Lights*,PlayState*);
struct Actor {
    struct {Vec3f pos;} world;
    Vec3f scale;
    struct { f32 yOffset,shadowScale; u8 shadowAlpha,feetFloorFlag; Vec3s rot;
             Vec3f feetPos[2]; Shadow shadowDraw; } shape;
    f32 floorHeight;
    unsigned flags,bgCheckFlags,colorFilterTimer,colorFilterParams,objectSlot,callbackState;
    void (*draw)(Actor*,PlayState*);
};
struct PlayState {
    struct {void* gfxCtx;} state;
    struct {int listHead;} lightCtx;
    struct {Vec3f quakeOffset;} mainCamera;
    struct {struct {void* segment;} slots[4];} objectCtx;
    CollisionContext colCtx;
};
#define ACTOR_FLAG_IGNORE_QUAKE 1u
#define ACTOR_FLAG_IGNORE_POINT_LIGHTS 2u
#define BGCHECKFLAG_GROUND 1u
#define FOOT_LEFT 0
#define FOOT_RIGHT 1
#define MTXMODE_APPLY 1
#define CLAMP_MAX(x,m) ((x)>(m)?(m):(x))
#define COLORFILTER_COLORFLAG_GRAY 1u
#define COLORFILTER_COLORFLAG_RED 2u
#define COLORFILTER_BUFFLAG_XLU 4u
#define COLORFILTER_GET_COLORINTENSITY(p) ((p)&0xf8)
#define COLORFILTER_GET_DURATION(p) ((p)&0xff)
#define PLATFORM_IQUE 0
#define NULL 0
#define OPEN_DISPS(...)
#define CLOSE_DISPS(...)
#define Fault_AddClient(...)
#define Fault_RemoveClient(...)
#define gSPSegment(...)
#define SETUPDL_44 0
#define ABS(x) ((x)<0?-(x):(x))
extern "C" int printf(const char*, ...);
extern "C" int memcmp(const void*,const void*,unsigned long);
extern "C" void* memset(void*,int,unsigned long);
#define CHECK(c) do{if(!(c)){printf("line %d: %s\n",__LINE__,#c);return 1;}}while(0)
static Lights lights;
static int gfx_calls,queries,draws,dependencies,transforms,scales,custom_shadows;
static int POLY_OPA_DISP;
static Vec3f ray_positions[2],matrix_pos,matrix_scale;
static Vec3s matrix_rot;
static f32 floor_values[2];
static void* object_segment;
static unsigned seed=0x21345149u;
static unsigned random_word(){seed=seed*1664525u+1013904223u;return seed;}
static void reset_trace(){
    gfx_calls=queries=draws=dependencies=transforms=scales=custom_shadows=0;
    memset(ray_positions,0,sizeof(ray_positions));
}
static Lights* LightContext_NewLights(void*,void*){++gfx_calls;return &lights;}
static void Lights_BindAll(Lights*,int,Vec3f*){++gfx_calls;}
static void Lights_Draw(Lights*,void*){++gfx_calls;}
static int Gfx_SetupDL(int p,int){++gfx_calls;return p;}
static void func_80026860(PlayState*,Color_RGBA8*,unsigned,unsigned){++gfx_calls;}
static void func_80026400(PlayState*,Color_RGBA8*,unsigned,unsigned){++gfx_calls;}
static void func_80026A6C(PlayState*){++gfx_calls;}
static void func_80026608(PlayState*){++gfx_calls;}
static void Matrix_SetTranslateRotateYXZ(f32 x,f32 y,f32 z,Vec3s* rot){
    ++transforms;matrix_pos={x,y,z};matrix_rot=*rot;
}
static void Matrix_Scale(f32 x,f32 y,f32 z,u8){++scales;matrix_scale={x,y,z};}
static void Actor_SetObjectDependency(PlayState* play,Actor* actor){
    ++dependencies;object_segment=play->objectCtx.slots[actor->objectSlot].segment;
}
static f32 BgCheck_AnyRaycastDown1(CollisionContext*,CollisionPoly*,Vec3f* position){
    if(queries<2)ray_positions[queries]=*position;
    return floor_values[queries++&1];
}
static f32 func_800BFCB8(PlayState* play,MtxF*,Vec3f* position){
    CollisionPoly poly;return BgCheck_AnyRaycastDown1(&play->colCtx,&poly,position);
}
static void ActorShadow_DrawCircle(Actor*,Lights*,PlayState*){++gfx_calls;}
static void ActorShadow_DrawFoot(PlayState*,Light*,MtxF*,s32,f32,f32,f32){++gfx_calls;}
static void custom_shadow(Actor* actor,Lights*,PlayState*){++custom_shadows;actor->callbackState+=100;}
static void source_draw(Actor* actor,PlayState*){
    ++draws;++actor->callbackState;
    actor->shape.feetPos[0].y+=Fx::raw(3141);
    actor->shape.feetPos[1].y-=Fx::raw(1618);
}

/* SOURCE_FUNCTIONS */
/* PRODUCTION_FUNCTIONS */

static int feet_test(){
    for(unsigned sample=0;sample<100000;++sample){
        PlayState play={};Actor original={},fast={};
        original.world.pos.y=Fx::raw((int)random_word());
        original.floorHeight=sample%4?original.world.pos.y-Fx((int)(sample%205)-3):Fx::raw((int)random_word());
        original.bgCheckFlags=sample&1?BGCHECKFLAG_GROUND:0;
        original.shape.feetFloorFlag=sample%4;
        original.shape.shadowAlpha=(u8)random_word();
        original.shape.shadowScale=Fx::raw((int)random_word());
        original.scale.x=Fx::raw((int)random_word());
        for(int foot=0;foot<2;++foot){
            original.shape.feetPos[foot]={Fx((int)(random_word()%4001)-2000),Fx::raw((int)random_word()),Fx(foot)};
            floor_values[foot]=original.shape.feetPos[foot].y+Fx::raw((int)(sample%7)*32768-65536);
        }
        fast=original;reset_trace();ActorShadow_DrawFeet(&original,&lights,&play);
        int expected_queries=queries;Vec3f rays[2]={ray_positions[0],ray_positions[1]};
        reset_trace();PlayerAnchor_Feet(&fast,&play);
        CHECK(!memcmp(&original,&fast,sizeof(Actor)));
        CHECK(queries==expected_queries && !memcmp(rays,ray_positions,sizeof(rays)));
        CHECK(gfx_calls==0);
    }
    printf("Player feet: 100000 exact actor states, ray counts/positions and contact flags\n");
    return 0;
}
static int wrapper_test(){
    for(unsigned sample=0;sample<24000;++sample){
        PlayState play={};Actor original={},fast={};
        for(int slot=0;slot<4;++slot)play.objectCtx.slots[slot].segment=(void*)(unsigned long)(0x100+slot*8);
        play.mainCamera.quakeOffset={Fx(-4),Fx(3),Fx(2)};
        original.world.pos={Fx((int)(random_word()%4001)-2000),Fx(20),Fx(71)};
        original.scale={Fx::raw(655),Fx::raw(sample&1?-655:655),Fx::raw(655)};
        original.shape.yOffset=Fx((int)(sample%200)-100);
        original.shape.rot={(short)random_word(),(short)random_word(),(short)random_word()};
        original.shape.feetPos[0]={Fx(17),Fx::raw((int)sample),Fx(-4)};
        original.shape.feetPos[1]={Fx(9),Fx::raw((int)sample),Fx(6)};
        original.shape.shadowScale=Fx(40);original.shape.shadowAlpha=150;
        original.shape.feetFloorFlag=sample%4;original.floorHeight=Fx(0);
        original.flags=sample&3;original.bgCheckFlags=sample&1;
        original.colorFilterTimer=sample%3;original.colorFilterParams=sample%16;
        original.objectSlot=sample%4;original.draw=source_draw;
        original.shape.shadowDraw=sample%3==0?0:(sample%3==1?ActorShadow_DrawFeet:custom_shadow);
        floor_values[0]=Fx::raw((int)sample+30000);floor_values[1]=Fx::raw((int)sample-30000);
        fast=original;reset_trace();Actor_Draw(&play,&original);
        Vec3f rays[2]={ray_positions[0],ray_positions[1]},pos=matrix_pos,scale=matrix_scale;
        Vec3s rot=matrix_rot;void* segment=object_segment;
        int old_queries=queries,old_custom=custom_shadows;
        reset_trace();PlayerAnchor_Draw(&play,&fast);
        CHECK(!memcmp(&original,&fast,sizeof(Actor)));
        CHECK(queries==old_queries && !memcmp(rays,ray_positions,sizeof(rays)));
        CHECK(custom_shadows==old_custom && draws==1 && dependencies==1 && transforms==1 && scales==1);
        CHECK(!memcmp(&pos,&matrix_pos,sizeof(pos)) && !memcmp(&scale,&matrix_scale,sizeof(scale)));
        CHECK(!memcmp(&rot,&matrix_rot,sizeof(rot)) && segment==object_segment);
        CHECK(sample%3==2 || gfx_calls==0);
    }
    printf("Player wrapper: 24000 exact gameplay states, transform inputs and object dependencies; custom fallback exact\n");
    return 0;
}
int main(int argc,char**argv){
    lights.numLights=4;
    for(int i=0;i<8;++i){lights.l.l[i].l.dir[1]=50;for(int k=0;k<3;++k)lights.l.l[i].l.col[k]=100;}
    return argc!=2?2:(argv[1][0]=='f'?feet_test():wrapper_test());
}
