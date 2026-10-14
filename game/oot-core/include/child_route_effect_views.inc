/* Source-owned dirt and target fragments use the existing bounded particle view. */
static unsigned ChildRoute_EffectViews(OotCoreEffectView* out, unsigned capacity,
                                      unsigned count, unsigned* dropped) {
    if (!gOotCorePlay) return count;
    if (gSaveContext.minigameState == 1) {
        if (count == capacity) ++*dropped;
        else {
            OotCoreEffectView* row=&out[count++];*row={};
            row->type=OOT_CORE_EFFECT_MINIGAME_SCORE;
            row->regs[0]=gSaveContext.minigameScore;
            row->life=1;
        }
    }
    static const u8 colour[6][3] = {{40,220,50},{40,100,250},{240,40,30},
                                   {210,60,200},{245,190,30},{190,190,190}};
    for (unsigned cat=0;cat<ACTORCAT_MAX;++cat)
    for (Actor* actor=gOotCorePlay->actorCtx.actorLists[cat].head;actor;actor=actor->next) {
        if (!actor->update || (actor->id!=ACTOR_EN_G_SWITCH && actor->id!=ACTOR_EN_TK && actor->id!=ACTOR_BG_DY_YOSEIZO)) continue;
        unsigned total=actor->id==ACTOR_BG_DY_YOSEIZO ? BG_DY_YOSEIZO_EFFECT_COUNT : actor->id==ACTOR_EN_TK ? 20 : ((EnGSwitch*)actor)->numEffects;
        if (total>100) total=100;
        for (unsigned i=0;i<total;++i) {
            const Vec3f* pos; int radius,alpha=255; const u8* rgb; const u8 dirt[]={170,130,90};
            if (actor->id==ACTOR_BG_DY_YOSEIZO) {
                const BgDyYoseizoEffect* eff=&((BgDyYoseizo*)actor)->effects[i];
                if (!eff->active || !eff->alpha) continue;
                pos=&eff->pos; radius=(int)(eff->scale*5);alpha=eff->alpha;rgb=&eff->innerColor.r;
            } else if (actor->id==ACTOR_EN_TK) {
                const EnTkEff* eff=&((EnTk*)actor)->eff[i];
                if (!eff->active || !eff->timeTotal) continue;
                pos=&eff->pos;radius=(int)(eff->size*20);alpha=eff->timeLeft*255/eff->timeTotal;rgb=dirt;
            } else {
                const EnGSwitchEffect* eff=&((EnGSwitch*)actor)->effects[i];
                if (!eff->flag) continue;
                pos=&eff->pos;radius=eff->scale*644/10000;rgb=colour[(u32)eff->colorIdx<6?eff->colorIdx:0];
            }
            if (count==capacity) {++*dropped;continue;}
            OotCoreEffectView* row=&out[count++];*row={};
            row->x=(int)pos->x;row->y=(int)pos->y;row->z=(int)pos->z;
            row->regs[0]=radius>0?radius:1;row->regs[1]=rgb[0];row->regs[2]=rgb[1];row->regs[3]=rgb[2];row->regs[4]=alpha;
            row->life=1;row->priority=1;row->slot=i;row->type=OOT_CORE_EFFECT_MOUNTAIN_FRAGMENT;
        }
    }
    return count;
}
