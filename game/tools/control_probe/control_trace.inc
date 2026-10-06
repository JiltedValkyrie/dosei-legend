/* Captured at forest submit; finish runs AFTER slSynch, before the next draw.
 * CMDSRCA match multiplicity remains explicit: a shared address is ambiguous.
 * Exact world corners identify each child independently of slots/partitioning. */
extern void slGetMatrix(MATRIX);
extern FIXED slCalcPoint(FIXED, FIXED, FIXED, FIXED[XYZ]);
static const short control_mid[3][3] = {{0,160,4250},{736,360,4675},{736,200,3825}};
void __attribute__((optimize("Os"))) control_trace_prepare(int visible)
{
    control_trace_t *t = (control_trace_t *)&CONTROL->pending;
    unsigned i,j,k;
    t->frame = CONTROL->frame; t->request = CONTROL->ack;
    t->count = 0; t->visible = visible; t->total = forest_polygon_count;
    t->accepted = kokiri_accepted_mask & 1;
    t->camera[0]=recomp_camera.x; t->camera[1]=recomp_camera.y;
    t->camera[2]=recomp_camera.z; t->camera[3]=recomp_yaw; t->camera[4]=recomp_pitch;
    slGetMatrix((FIXED (*)[3])t->matrix);
    for(i=0;i<forest_polygon_count && t->count<CONTROL_FACES;++i) {
        const unsigned short *v=kokiri_pdata.pltbl[i].Vertices;
        bool hit=(CONTROL->hud & 1024u) && (forest_mesh[i] & FOREST_FACE_LANDMARK);
        control_face_t *f;
        if (hit && ((CONTROL->hud >> 11) & 3u)) {
            unsigned kind = (kokiri_pdata.pntbl[v[0]][0] >> 16) > 4000 ? 1u :
                (kokiri_pdata.pntbl[v[0]][2] >> 16) < 1000 ? 2u : 3u;
            hit = kind == ((CONTROL->hud >> 11) & 3u);
        }
        for(j=0;j<4 && !hit && !(CONTROL->hud & 1024u);++j)for(k=0;k<3;++k)
            if((kokiri_pdata.pntbl[v[j]][0]>>16)==control_mid[k][0] &&
              -(kokiri_pdata.pntbl[v[j]][1]>>16)==control_mid[k][1] &&
               (kokiri_pdata.pntbl[v[j]][2]>>16)==control_mid[k][2]) {hit=true;break;}
        if(!hit)continue;
        f=&t->face[t->count++];
        f->poly=i;f->submitted=i<visible;
        f->slot=kokiri_pdata.attbl[i].texno;
        f->source=__jo_sprite_def[f->slot].adr;
        f->size=__jo_sprite_def[f->slot].size;
        f->palette=kokiri_pdata.attbl[i].colno;
        f->attr=kokiri_pdata.attbl[i].atrb;
        f->matches=0;
        memset(f->command,0,sizeof(f->command));
        for(j=0;j<4;++j) {
            POINT *p=&kokiri_pdata.pntbl[v[j]];
            f->world[j][0]=(*p)[0]>>16;
            f->world[j][1]=-((*p)[1]>>16);
            f->world[j][2]=(*p)[2]>>16;
            slCalcPoint((*p)[0],(*p)[1],(*p)[2],f->view[j]);
        }
    }
}
void __attribute__((optimize("Os"))) control_trace_finish(void)
{
    control_trace_t *t=(control_trace_t *)&CONTROL->pending;
    volatile unsigned short *vram=(volatile unsigned short *)JO_VDP1_VRAM;
    unsigned at=0,ret=0,steps,i,k;
    if(CONTROL->magic!=CONTROL_MAGIC || !t->frame)return;
    for(steps=0;steps<GAME_TEXTURE_BASE/32;++steps) {
        volatile unsigned short *c=vram+at/2;
        unsigned ctrl=c[0],jp=(ctrl>>12)&7,next=at+32;
        if(ctrl&0x8000)break;
        if(!(jp&4) && (ctrl&15)<=2)for(i=0;i<t->count;++i) {
            control_face_t *f=&t->face[i];
            if(c[4]!=(unsigned)f->source)continue;
            ++f->matches;
            for(k=0;k<16;++k)f->command[k]=c[k];
        }
        switch(jp&3){case 1:next=c[1]*8;break;case 2:ret=at+32;next=c[1]*8;break;
                    case 3:if(ret){next=ret;ret=0;}break;}
        if(next>=GAME_TEXTURE_BASE)break;
        at=next;
    }
    ++CONTROL->trace_seq;
    memcpy((void *)&CONTROL->completed,t,sizeof(*t));
    ++CONTROL->trace_seq;
}
