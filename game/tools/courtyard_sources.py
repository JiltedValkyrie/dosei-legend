"""Real child Zelda and Impa states with sprite presentation and root anchors."""
import re
import struct
import xml.etree.ElementTree as ET
from field_enemy_sources import replace_body
from child_route_npcs import append_update
from owl_sources import function

ACTORS = ('En_Zl4', 'Demo_Im', 'En_Viewer')
SOURCES = [f'src/overlays/actors/ovl_{name}/z_{name.lower()}.c' for name in ACTORS]
OBJECTS = ('object_zl4', 'object_im', 'object_gndd')
NPC_SOURCES = [('ACTOR_' + name.upper(), source) for name, source in zip(ACTORS, SOURCES)]
SOURCE_SCENES = ('nakaniwa',)
VIEWER_ANIMS = ('gYoungGanondorfWalkAnim', 'gYoungGanondorfKneelStartAnim',
                'gYoungGanondorfKneelLoopAnim', 'gYoungGanondorfKneelLookSidewaysAnim')


def moving_animations(oot):
    source = (oot / SOURCES[0]).read_text(encoding='utf-8')
    return re.findall(r'&([A-Za-z0-9_]+)', function(source, 'EnZl4_InMovingAnim'))


def root_anchors(oot):
    """Only the source movement channel, no limbs or runtime joint tracks."""
    import build_link_model as link
    data = link.read_object(oot, 'object_zl4', oot / 'baseroms/ntsc-1.2')
    root = ET.parse(oot / 'assets/xml/objects/object_zl4.xml')
    offsets = {a.attrib['Name']:int(a.attrib['Offset'],16) for a in root.iter('Animation')}
    rows = []
    for name in moving_animations(oot):
        frames, _, values, indices, static_max = struct.unpack_from('>hhIIh', data, offsets[name])
        values &= 0xffffff
        ix, _, iz = struct.unpack_from('>3H', data, indices & 0xffffff)
        points = []
        for frame in range(frames):
            point = tuple(struct.unpack_from('>h', data, values+2*(i if i<static_max else i+frame))[0]
                          for i in (ix,iz))
            # Run-length anchors retain exact integer frame positions while
            # long stationary parts need only one entry.
            if not points or point != points[-1][1:]:points.append((frame,*point))
        rows.append((name,frames,points))
    return rows


def anchor_source(oot):
    rows = root_anchors(oot)
    out = ['/* Offline root XZ only; source actor collision follows its animation. */',
           'struct CourtyardRootPoint { s16 frame, x, z; };']
    for name,_,points in rows:
        out.append('static const CourtyardRootPoint '+name+'_root[] = {')
        out.extend('    {%d,%d,%d},'%p for p in points)
        out.append('};')
    out += ['static void Courtyard_ZeldaMove(Actor* actor, SkelAnime* skel) {',
            '    const CourtyardRootPoint* points = NULL;', '    unsigned count = 0;']
    for name,_,points in rows:
        out.append(f'    if (skel->animation == &{name}) {{ points={name}_root; count={len(points)}; }}')
    out += ['    if (!points) return;',
            '    int frame = (int)skel->curFrame; unsigned i=0;',
            '    while (i+1<count && points[i+1].frame<=frame) ++i;',
            '    f32 x=points[i].x, z=points[i].z;',
            '    f32 sine=Math_SinS(actor->shape.rot.y), cosine=Math_CosS(actor->shape.rot.y);',
            '    f32 oldSine=Math_SinS(skel->prevRot), oldCosine=Math_CosS(skel->prevRot);',
            '    if (!(skel->movementFlags & ANIM_FLAG_ADJUST_STARTING_POS)) {',
            '        actor->world.pos.x += (x*cosine+z*sine-skel->prevTransl.x*oldCosine-skel->prevTransl.z*oldSine)*actor->scale.x;',
            '        actor->world.pos.z += (z*cosine-x*sine-skel->prevTransl.z*oldCosine+skel->prevTransl.x*oldSine)*actor->scale.z;',
            '    }',
            '    skel->prevTransl.x=points[i].x; skel->prevTransl.z=points[i].z;',
            '    skel->prevRot=actor->shape.rot.y;',
            '    skel->movementFlags &= ~ANIM_FLAG_ADJUST_STARTING_POS;', '}']
    return '\n'.join(out)+'\n'


def adapt(rel, text):
    if rel in [p[:-2]+'.h' for p in SOURCES]:
        text=re.sub(r'Vec3s (jointTable|morphTable)\[[^]]+\];', r'Vec3s* \1;', text)
        if rel==SOURCES[2][:-2]+'.h':
            text=text.replace('Skin skin;', 'struct { SkelAnime skelAnime; } skin;')
        return text
    if rel not in SOURCES:return text
    text = '#include "child_route_npc_sprite.h"\n' + text
    text = text.replace('SkelAnime_InitFlex(', 'OotCore_SpriteInitFlex(')
    text = text.replace('SkelAnime_Init(', 'OotCore_SpriteInit(')
    text = text.replace('Npc_TrackPoint(', 'ChildRouteSprite_TrackBody(')
    for name in re.findall(r'^void ((?:EnZl4|DemoIm)_(?:Draw\w*|PostLimbDraw))\([^;{}]*\) \{',text,re.M):
        text=replace_body(text,name,'    /* Offline sprite; source state machine runs in Update. */')
    for name in ('EnZl4_OverrideLimbDraw','DemoIm_OverrideLimbDraw'):
        if name+'(' in text:text=replace_body(text,name,'    return 0; /* No runtime character pose. */')
    if rel==SOURCES[0]:
        text=text.replace('void EnZl4_SetMove(EnZl4* this, PlayState* play) {',
                          '#include "courtyard_root.inc"\n\nvoid EnZl4_SetMove(EnZl4* this, PlayState* play) {')
        text=replace_body(text,'EnZl4_SetMove','    Courtyard_ZeldaMove(&this->actor, &this->skelAnime);')
        text=append_update(text,'EnZl4_Update','    Actor_SetFocus(&this->actor, 40.0f);')
    elif rel==SOURCES[1]:
        text=replace_body(text,'func_80984DB8','    /* Removed head/torso smoothing, source body tracking remains. */')
        text=append_update(text,'DemoIm_Update','    Actor_SetFocus(&this->actor, 65.0f);')
    else:
        # This pack admits only courtyard type8. Other Viewer variants need
        # their own scene admission, sprites and source service coverage.
        text=re.sub(r'static EnViewerInitData sInitData\[\] = \{.*?\n\};', '''static EnViewerInitData sInitData[10] = {
    {}, {}, {}, {}, {}, {}, {}, {},
    { OBJECT_GNDD, OBJECT_GNDD, 1, -6, ENVIEWER_SHADOW_NONE, 10,
      ENVIEWER_DRAW_GANONDORF, &gYoungGanondorfSkel, &gYoungGanondorfWalkAnim }, {},
};''', text, flags=re.S)
        text=text.replace('PARAMS_GET_NOMASK(this->actor.params, 8)', 'ENVIEWER_TYPE_8_GANONDORF')
        start=text.index('void EnViewer_Init(Actor* thisx, PlayState* play) {')
        at=text.index('    Actor_ProcessInitChain',start)
        text=text[:at]+'''    if (PARAMS_GET_NOMASK(this->actor.params, 8) != ENVIEWER_TYPE_8_GANONDORF) {
        Actor_Kill(&this->actor); return; /* Not admitted by this child route. */
    }
'''+text[at:]
        text=re.sub(r'        sGanondorfCape = \(EnGanonMant\*\)Actor_SpawnAsChild\(.*?\);',
                    '        /* Cape is baked with the sprite; no runtime cloth actor. */',text,flags=re.S)
        for name in re.findall(r'^void (EnViewer_(?:Draw\w*|\w*PostLimbDraw\w*|UpdateGanondorfCape|InitAnimHorse|Destroy))\([^;{}]*\) \{',text,re.M):
            text=replace_body(text,name,'    /* Offline sprite; no runtime pose or cloth. */')
        for name in re.findall(r'^s32 (EnViewer_\w*OverrideLimbDraw)\([^;{}]*\) \{',text,re.M):
            text=replace_body(text,name,'    return 0; /* No runtime pose. */')
        # The source's post-start states lack cue guards. Hold the last pose
        # if a script ends between source actors' updates.
        text=text.replace('if (play->csCtx.actorCues[1]->id == 10)',
                          'if (play->csCtx.actorCues[1] && play->csCtx.actorCues[1]->id == 10)')
        text=text.replace('if (play->csCtx.actorCues[1]->id == 4)',
                          'if (play->csCtx.actorCues[1] && play->csCtx.actorCues[1]->id == 4)')
    return text
