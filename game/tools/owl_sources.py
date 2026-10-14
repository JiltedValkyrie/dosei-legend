"""Real En_Owl actions with clock-only source animations and baked sprites.

The source flip counters gate dialogue, so their timing remains. Limb angles,
pose arrays, matrix focus and runtime character draws do not survive import.
"""
import re
from field_enemy_sources import replace_body
from child_route_npcs import append_update

ACTORS = ('En_Owl',)
SOURCE = 'src/overlays/actors/ovl_En_Owl/z_en_owl.c'
SOURCES = (SOURCE,)
OBJECTS = ('object_owl',)
NPC_SOURCES = [('ACTOR_EN_OWL', SOURCE)]
ANIMATIONS = {
    'gOwlPerchingSkel': ('gOwlPerchAnim',),
    'gOwlFlyingSkel': ('gOwlUnfoldWingsAnim', 'gOwlTakeoffAnim', 'gOwlFlyAnim', 'gOwlGlideAnim'),
}


def adapt(rel, text):
    if rel == SOURCE[:-2] + '.h':
        return re.sub(r'Vec3s (jointTable2?|morphTable2?)\[[^]]+\];', r'Vec3s* \1;', text)
    if rel != SOURCE:
        return text
    text = '#include "sprite_actor.h"\n' + text
    text = text.replace('SkelAnime_InitFlex(', 'OotCore_SpriteInitFlex(')
    for name in ('EnOwl_PostLimbUpdate', 'EnOwl_Draw'):
        text = replace_body(text, name, '    /* Offline sprite; source actions remain in Update. */')
    text = replace_body(text, 'EnOwl_OverrideLimbDraw', '    return false; /* No runtime pose. */')
    # These outputs are consumed exclusively by the removed limb callback.
    # Keep source phase/counter changes because actionFuncs wait on them.
    text = re.sub(r'^\s*phi_a1 = Math_(?:Sin|Cos)S\([^\n]+;\n', '\n', text, flags=re.M)
    text = re.sub(r'^\s*this->unk_3(?:EC|F0|F2) = [^\n]+;\n', '\n', text, flags=re.M)
    text = text.replace('this->unk_407 = this->unk_3F2;', 'this->unk_407 = 0;')
    text = append_update(text, 'EnOwl_Update', '    Actor_SetFocus(&this->actor, 60.0f);')
    return text


def function(text, name):
    match = re.search(r'^\w+ ' + name + r'\([^;]*?\) \{', text, re.M)
    if not match:
        raise ValueError('source camera function moved: ' + name)
    start = match.start()
    end, depth = text.index('{', start) + 1, 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end] + '\n'


def camera_source(oot, packed=False, attention=False, demo9_enabled=True, free2_enabled=False):
    """Resident source interpolation; scene packs own keyframe data/setup."""
    camera = (oot / 'src/code/z_camera.c').read_text(encoding='utf-8')
    olib = (oot / 'src/code/z_olib.c').read_text(encoding='utf-8')
    body = ''
    for name in ('OLib_Vec3fDist', 'OLib_ClampMinDist', 'OLib_Vec3fDistNormalize',
                 'OLib_VecSphToVec3f', 'OLib_VecGeoToVec3f', 'OLib_Vec3fToVecSph',
                 'OLib_Vec3fToVecGeo', 'OLib_Vec3fDiffToVecGeo'):
        body += function(olib, name).replace('SQ(', 'OOT_SQ(').replace('f32 distXZSq', 'FxSq distXZSq')
    for name in ('Camera_LERPCeilF', 'Camera_LERPFloorF', 'Camera_LERPCeilS', 'Camera_LERPFloorS',
                 'Camera_AddVecGeoToVec3f'):
        row = function(camera, name)
        if name == 'Camera_BGCheckInfo':
            row = row.replace('return floorBgId + 1;', 'return to->bgId + 1;')
        body += row
    shared = body
    body = '''extern s32 D_8011D3AC;
static void Camera_UpdateInterface(s16 field) {
    Interface_ChangeHudVisibilityMode((field >> 8) & 15);
}
extern s32 Camera_RequestModeImpl(Camera*,s16,u8);
'''
    for name in ('Camera_LERPCeilF', 'Camera_LERPFloorF', 'Camera_LERPCeilS', 'Camera_LERPFloorS',
                 'Camera_AddVecGeoToVec3f'):
        body += function(camera, name).split('{',1)[0].strip() + ';\n'
    if attention:
        body += function(camera, 'Camera_BGCheckInfo').replace('return floorBgId + 1;', 'return to->bgId + 1;')
        body += function(camera, 'Camera_BGCheck')
    update = function(camera, 'Camera_Unique9')
    start = update.index('    if (RELOAD_PARAMS(camera)')
    end = update.index('    playerPosRot =', start)
    update = update[:start] + '    Letterbox_SetSizeTarget(32);\n\n' + update[end:]
    update = update.replace('        func_80043B60(camera);',
                            '        /* Follow-camera update rates do not affect Unique9. */')
    if not attention:
        update=update.replace('''    if (rwData->curKeyFrame->actionFlags & ONEPOINT_CS_ACTION_FLAG_BGCHECK) {
        Camera_BGCheck(camera, at, eye);
    }''','''    /* Admitted source keyframes explicitly disable background checks. */''')
    body += update
    # CS_3 is named DEMO3 in the setting table but actually dispatches Demo9.
    # 3050 requests only world-space points and the 1020 return action.
    demo9 = function(camera, 'Camera_Demo9')
    start = demo9.index('    if (RELOAD_PARAMS(camera)')
    end = demo9.index('    switch (camera->animState)', start)
    demo9 = demo9[:start] + '    Letterbox_SetSizeTarget(32);\n\n' + demo9[end:]
    start = demo9.index('                if (onePointCamData->actionParameters == 1)')
    end = demo9.index('\n                *eyeNext = newEye;', start)
    demo9 = demo9[:start] + '                newEye = csEyeUpdate;\n                newAt = csAtUpdate;\n' + demo9[end:]
    # Source STOP short-circuit leaves samples uninitialized: retain last view.
    demo9 = demo9.replace('Vec3f csEyeUpdate;', 'Vec3f csEyeUpdate = camera->eye;')
    demo9 = demo9.replace('Vec3f csAtUpdate;', 'Vec3f csAtUpdate = camera->at;')
    demo9 = demo9.replace('f32 newRoll;', 'f32 newRoll = f32(camera->roll) / 256;')
    if demo9_enabled:
        body += function(camera, 'Camera_LERPCeilVec3f') + demo9
    if attention:
        play_source = (oot / 'src/code/z_play.c').read_text(encoding='utf-8')
        door = function(play_source, 'func_800C0D34').replace('func_800C0D34', 'Pack_DoorYaw')
        # Malformed or non-transition door targets cannot index a missing list.
        door = door.replace('    transitionActor =', '''    if (!this->transitionActors.list ||
        GET_TRANSITION_ACTOR_INDEX(actor) >= this->transitionActors.count) return 0;
    transitionActor =''')
        body += re.sub(r'\bthis\b', 'play', door)
        body += 'static s32 sDemo5PrevAction12Frame = -16;\n'
        demo5 = function(camera, 'Camera_Demo5')
        demo5 = demo5.replace('sCameraInterfaceField = CAM_INTERFACE_FIELD(CAM_LETTERBOX_LARGE, CAM_HUD_VISIBILITY_NOTHING_ALT, 0);',
                              'Letterbox_SetSizeTarget(32);')
        demo5 = demo5.replace('func_800C0D34(', 'Pack_DoorYaw(')
        demo5 = demo5.replace('Actor_GetScreenPos(camera->play,', 'OotCore_CameraActorScreenPos(camera->play,')
        demo5 = re.sub(r'Camera_RequestSettingImpl\(camera, CAM_SET_CS_C,\s*CAM_REQUEST_SETTING_PRESERVE_BG_CAM_INDEX \| CAM_REQUEST_SETTING_FORCE_CHANGE\);',
                       'Camera_RequestSetting(camera, CAM_SET_CS_C);', demo5)
        demo5 = demo5.replace('(u32)camera->data1', '(u32)(uintptr_t)camera->data1')
        demo5 = demo5.replace('        camera->target = NULL;\n        return true;',
                              '        camera->target = NULL;\n        camera->timer = 0;\n        return true;')
        body += demo5
    if packed:
        if free2_enabled:
            free2=function(camera, 'Camera_Unique6')
            start=free2.index('    if (RELOAD_PARAMS(camera)')
            end=free2.index('    if (camera->animState == 0)',start)
            free2=free2[:start]+free2[end:]
            free2=free2.replace('        func_80043ABC(camera);',
                                '        /* Normal-camera tuning rates are host-owned. */')
            free2=free2.replace('(roData->interfaceField & UNIQUE6_FLAG_0) && ', '')
            body+=free2
        body += '''extern "C" int oot_pack_onepoint_step(Camera* camera) {
    if (camera->setting == CAM_SET_CS_C) return Camera_Unique9(camera);
'''
        if demo9_enabled:
            body += '    if (camera->setting == CAM_SET_CS_3) return Camera_Demo9(camera);\n'
        if attention:
            body += '    if (camera->setting == CAM_SET_CS_ATTENTION) return Camera_Demo5(camera);\n'
        if free2_enabled:
            body += '    if (camera->setting == CAM_SET_FREE2) return Camera_Unique6(camera);\n'
        return body + '    return false;\n}\n'
    body = shared
    onepoint = (oot / 'src/code/z_onepointdemo.c').read_text(encoding='utf-8')
    body += function(onepoint, 'OnePointCutscene_SetAsChild')
    body += function(onepoint, 'OnePointCutscene_RemoveCamera')
    init = function(onepoint, 'OnePointCutscene_Init')
    init = init.replace('    subCamId = Play_CreateSubCamera(play);', '''    if (!camera_at(play, parentCamId) ||
        !OotCore_PackOnePointSetup(NULL, 0, csId, NULL, 0)) return CAM_ID_NONE;
    subCamId = Play_CreateSubCamera(play);''')
    init = init.replace('OnePointCutscene_SetInfo(', 'OotCore_PackOnePointSetup(')
    for alias, target in {'vChildCamId':'temp2', 'vSubCamStatus':'temp1',
                          'vCurCamId':'temp2', 'vNextCamId':'temp3', 'vParentCamId':'temp1'}.items():
        init = init.replace(alias, target)
    body += init + function(camera, 'Camera_Finish')
    for name in ('OnePointCutscene_Attention', 'OnePointCutscene_AttentionSetSfx',
                 'OnePointCutscene_CheckForCategory'):
        row = function(onepoint, name)
        row = re.sub(r'#if DEBUG_FEATURES.*?#endif\n', '', row, flags=re.S)
        row = row.replace('    sUnused = -1;\n', '')
        row = row.replace('vTargetCat', 'temp1').replace('vParentCamId', 'temp1')
        row = row.replace('vLastHigherCat', 'temp2').replace('vSubCamId', 'temp2')
        body += row
    return body
