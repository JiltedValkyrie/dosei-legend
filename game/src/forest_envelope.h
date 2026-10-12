/* Conservative geometry candidates for a bounded set of cameras.
 *
 * The reusable camera set has |dx|+|dy|+|dz| <= 64 world units and wrapped
 * yaw/pitch changes <= 256 binang. FOV/roll, bank and LOD must stay equal.
 * All stored values and arithmetic are 32-bit. mul_q16 uses only the native
 * SH-2 multiply's 64-bit product; no wide divide or stored wide temporary.
 *
 * For either yaw coefficient, |delta(sin/cos)| <= 7*256+16 raw Q16 units.
 * 2*pi < 7, and 16 covers the SGL table's two-binang quantization/rounding.
 * The host test exhaustively checks this bound against the linked SGL LUT.
 * A point's depth/side error is therefore at most
 *   64 + ceil((|dx|+|dz|)*(7*256+16)/65536) + 2.
 * The final two units cover separate product rounding. Bounds use actual
 * point offsets, not FAR: a long polygon may cross FAR from much farther.
 *
 * fe_begin_sized widens the set (2026-10-12 moving-prepare A/B): position
 * P <= 256 and angle A <= 1024 give error P + ceil(extent*(7A+16)/65536) + 2,
 * the same argument with 7A+16 >= A*2*pi + 16. extent*(7*1024+16) < 2^30.
 * The centre need not be the current camera: callers may lead it along the
 * camera's motion, provided the current camera is inside (fe_contains).
 */
#ifndef FOREST_ENVELOPE_H
#define FOREST_ENVELOPE_H
#include <stdint.h>

#define FE_POSITION 64
#define FE_ANGLE 256
#define FE_TRIG (7 * FE_ANGLE + 16)
#define FE_POSITION_MAX 256
#define FE_ANGLE_MAX 1024

typedef struct {
    int32_t x, y, z, sine, cosine;
    int32_t side_dist, sin_upper_q8, cos_lower_q8;
    int32_t distance, roll;
    int32_t position, angle, trig;
    uint16_t yaw, pitch;
    int valid;
} fe_camera;

typedef struct {int32_t near_depth, far_depth; unsigned side;} fe_vertex;

static int32_t fe_abs(int32_t value) {return value < 0 ? -value : value;}
static int fe_coord(int32_t value) {return value >= -32768 && value <= 32767;}
static int32_t fe_angle_delta(uint16_t a, uint16_t b) {
    int32_t difference = (uint16_t)(a - b);
    return difference >= 32768 ? difference - 65536 : difference;
}
static int32_t fe_mul_q16(int32_t a, int32_t b) {
    return (int32_t)(((int64_t)a * b) >> 16);
}

/* Once per candidate build: size over speed. */
static fe_camera __attribute__((optimize("Os"))) fe_begin_sized(int32_t x, int32_t y, int32_t z, uint16_t yaw,
                                uint16_t pitch, int32_t distance, int32_t roll,
                                int32_t sine, int32_t cosine,
                                int32_t pitch_sine, int32_t pitch_cosine,
                                int32_t position, int32_t angle) {
    fe_camera result = {0};
    int32_t signed_pitch = fe_angle_delta(pitch, 0), ps, pc;
    result.x=x; result.y=y; result.z=z; result.yaw=yaw; result.pitch=pitch;
    result.distance=distance; result.roll=roll; result.sine=sine; result.cosine=cosine;
    result.position=position; result.angle=angle; result.trig=7*angle+16;
    result.valid=position >= 0 && position <= FE_POSITION_MAX &&
        angle >= 0 && angle <= FE_ANGLE_MAX &&
        fe_coord(x) && fe_coord(y) && fe_coord(z) &&
        sine >= -65536 && sine <= 65536 && cosine >= -65536 && cosine <= 65536 &&
        pitch_sine >= -65536 && pitch_sine <= 65536 &&
        pitch_cosine >= -65536 && pitch_cosine <= 65536;
    if (!result.valid) return result;
    ps=fe_abs(pitch_sine)+result.trig; if (ps>65536) ps=65536;
    pc=pitch_cosine-result.trig; if (pc<0) pc=0;
    result.sin_upper_q8=(ps+255)>>8;
    result.cos_lower_q8=pc>>8;
    /* If any member view disables the original side cull, the candidate
     * list must not reject on a side plane at all. */
    if (!roll && distance>0 && distance<=1024 &&
        signed_pitch-angle>-8192 && signed_pitch+angle<8192 && pc>0)
        result.side_dist=distance;
    return result;
}

static fe_camera fe_begin(int32_t x, int32_t y, int32_t z, uint16_t yaw,
                          uint16_t pitch, int32_t distance, int32_t roll,
                          int32_t sine, int32_t cosine,
                          int32_t pitch_sine, int32_t pitch_cosine) {
    return fe_begin_sized(x, y, z, yaw, pitch, distance, roll, sine, cosine,
                          pitch_sine, pitch_cosine, FE_POSITION, FE_ANGLE);
}

static int fe_contains(const fe_camera* c, int32_t x, int32_t y, int32_t z,
                        uint16_t yaw, uint16_t pitch, int32_t distance, int32_t roll) {
    if (!c->valid || !fe_coord(x) || !fe_coord(y) || !fe_coord(z)) return 0;
    return fe_abs(x-c->x)+fe_abs(y-c->y)+fe_abs(z-c->z)<=c->position &&
        fe_abs(fe_angle_delta(yaw,c->yaw))<=c->angle &&
        fe_abs(fe_angle_delta(pitch,c->pitch))<=c->angle &&
        distance==c->distance && roll==c->roll;
}

static fe_vertex fe_bound_vertex(const fe_camera* c, int32_t x, int32_t y, int32_t z) {
    fe_vertex result = {-32768,32767,0};
    int32_t dx,dy,dz,extent,error,depth,side,zb,lim;
    if (!c->valid || !fe_coord(x) || !fe_coord(y) || !fe_coord(z)) return result;
    dx=x-c->x; dy=y-c->y; dz=z-c->z;
    extent=fe_abs(dx)+fe_abs(dz); /* <=131070; product below 2^30. */
    error=c->position+((extent*c->trig+65535)>>16)+2;
    depth=fe_mul_q16(dx,c->sine)+fe_mul_q16(dz,c->cosine);
    /* The existing renderer stores depth and side as signed short. If the
     * envelope can cross a wrapping endpoint, include this vertex. */
    if (depth-error < -32768 || depth+error > 32767) return result;
    result.near_depth=depth-error; result.far_depth=depth+error;
    if (!c->side_dist) return result;
    side=fe_mul_q16(dx,c->cosine)-fe_mul_q16(dz,c->sine);
    if (side-error < -32768 || side+error > 32767) return result;
    /* Monotone upper bound of the existing pitched-depth side test. For a
     * negative depth, the smallest cosine gives the largest product. */
    zb=result.far_depth;
    if (zb<0) zb=((zb*c->cos_lower_q8)>>8)+1;
    zb+=(((fe_abs(dy)+c->position)*c->sin_upper_q8+255)>>8)+2;
    lim=zb*160+32*c->side_dist;
    result.side=((side-error)*c->side_dist>lim ? 1u:0u) |
                ((-side-error)*c->side_dist>lim ? 2u:0u);
    return result;
}

static int fe_face_candidate(const fe_vertex corner[4], int32_t far) {
    int32_t near_depth=corner[0].near_depth, far_depth=corner[0].far_depth;
    unsigned side=corner[0].side;
    int i;
    for(i=1;i<4;++i) {
        if(corner[i].near_depth<near_depth) near_depth=corner[i].near_depth;
        if(corner[i].far_depth>far_depth) far_depth=corner[i].far_depth;
        side&=corner[i].side;
    }
    return far_depth>=0 && near_depth<=far && !side;
}

static int fe_object_candidate(const fe_camera* c, int32_t low_x, int32_t low_z,
                               int32_t high_x, int32_t high_z, int32_t far) {
    int32_t dx,dz,radius;
    if (!c->valid || !fe_coord(low_x) || !fe_coord(low_z) ||
        !fe_coord(high_x) || !fe_coord(high_z) || low_x>high_x || low_z>high_z ||
        far<0 || far>32767-c->position) return 1;
    radius=far+c->position;
    dx=c->x<low_x ? low_x-c->x : (c->x>high_x ? c->x-high_x : 0);
    dz=c->z<low_z ? low_z-c->z : (c->z>high_z ? c->z-high_z : 0);
    if(dx>radius || dz>radius) return 0;
    /* The scalar checks cap each square below 2^30; their sum fits s32. */
    return dx*dx+dz*dz<=radius*radius;
}
#endif
