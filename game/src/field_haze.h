#ifndef DOSEI_FIELD_HAZE_H
#define DOSEI_FIELD_HAZE_H

static inline int32_t field_fade_offset(int32_t sine, int32_t cosine)
{
    return ((recomp_camera.x-recomp_link.x)*(sine/256)+
            (recomp_camera.z-recomp_link.z)*(cosine/256))/256;
}

/* View-aligned curtain: cancel camera translation, yaw and pitch so its
 * vertical screen position stays fixed on hills and in first-person.
 * All 3D scenes share depth 3200; nearer room geometry occludes the curtain.
 * Map/time tint matches the dark gradient band. VDP1 hardware mesh supplies
 * the screen-door transparency;
 * no texture/CLUT/sprite slot or screen-space overlay is allocated.
 * Static tables remain alive until SGL's slave has consumed the submission. */
static void __attribute__((optimize("Os"))) field_haze_draw(void)
{
    /* Give each half an on-screen edge. A single screen-spanning face has
     * all four corners outside the horizontal clip window. */
    static POINT points[6] = {
        {-4096*65536, -320*65536, 3200*65536},
        {0, -320*65536, 3200*65536},
        {0, 560*65536, 3200*65536},
        {-4096*65536, 560*65536, 3200*65536},
        {4096*65536, -320*65536, 3200*65536},
        {4096*65536, 560*65536, 3200*65536}
    };
    static POLYGON faces[2] = {{{0,0,-65536},{0,1,2,3}},
                              {{0,0,-65536},{1,4,5,2}}};
#define FIELD_HAZE_ATTR ATTRIBUTE(Dual_Plane, SORT_MIN | UseNearClip, 0, \
        C_RGB(1,2,1), No_Gouraud, MESHon | ECdis | SPdis, sprPolygon, No_Option)
    static ATTR attrs[2] = {FIELD_HAZE_ATTR, FIELD_HAZE_ATTR};
#undef FIELD_HAZE_ATTR
    static PDATA data = {points,6,faces,2,attrs};
    attrs[0].colno=attrs[1].colno=environment_haze_colour(scene_flow_scene(),oot_core_skybox_time());
    slPushMatrix();
    slTranslate(recomp_camera.x*65536, -recomp_camera.y*65536, recomp_camera.z*65536);
    slRotY((ANGLE)recomp_yaw);
    slRotX((ANGLE)recomp_pitch);
    submit(&data, 8u);
    slPopMatrix();
}

#endif
