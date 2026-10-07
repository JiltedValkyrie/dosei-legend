#ifndef DOSEI_FIELD_HAZE_H
#define DOSEI_FIELD_HAZE_H

static inline int32_t field_fade_offset(int32_t sine, int32_t cosine)
{
    return ((recomp_camera.x-recomp_link.x)*(sine/256)+
            (recomp_camera.z-recomp_link.z)*(cosine/256))/256;
}

/* Upright world-space curtain anchored to Link and turned with camera yaw.
 * Camera pitch and height affect its screen position normally.
 * Static geometry survives until SGL consumes the submission. */
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
    slTranslate(recomp_link.x*65536, -recomp_link.y*65536, recomp_link.z*65536);
    slRotY((ANGLE)recomp_yaw);
    submit(&data, 8u);
    slPopMatrix();
}

#endif
