"""Build collision-checked title routes from the forest's actual floor mesh."""
import hashlib
import math
import struct
from functools import lru_cache
from pathlib import Path
from build_sgl_scene import read_scene

ROOT = Path(__file__).resolve().parents[1]


def build():
    source = ROOT / 'levels/kokiri/assets/static/FOREST.BIN'
    output = ROOT / 'build/generated/title_paths.h'
    signature = '/* '+hashlib.sha256(source.read_bytes()+Path(__file__).read_bytes()).hexdigest()+' */'
    if output.exists() and output.read_text().startswith(signature):
        print('Title routes: cached collision-validated paths')
        return
    data, header, *_ = read_scene(source)
    buckets = {}
    triangles = []
    for i in range(header['ncollision']):
        values = struct.unpack_from('>18h', data, header['collision_off'] + i * 36)
        vertices = [values[j:j + 3] for j in (0, 3, 6)]
        normal = tuple(n / 16384 for n in values[9:12])
        lo, hi = values[12:15], values[15:18]
        triangles.append((vertices, normal, lo, hi))
        for x in range((lo[0] - 128) // 128, (hi[0] + 128) // 128 + 1):
            for z in range((lo[2] - 128) // 128, (hi[2] + 128) // 128 + 1):
                buckets.setdefault((x, z), []).append(i)

    def inside(p, vertices, normal):
        signs = []
        for a, b in zip(vertices, vertices[1:] + vertices[:1]):
            u = [b[k] - a[k] for k in range(3)]
            v = [p[k] - a[k] for k in range(3)]
            cross = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
            signs.append(sum(cross[k]*normal[k] for k in range(3)))
        return min(signs) >= -0.1 or max(signs) <= 0.1

    def nearby(x, z):
        return (triangles[i] for i in buckets.get((int(x)//128, int(z)//128), ()))

    @lru_cache(maxsize=200000)
    def clear(p, clearance=16):
        for vertices, n, lo, hi in nearby(p[0], p[2]):
            if any(p[k] < lo[k]-clearance or p[k] > hi[k]+clearance for k in range(3)):
                continue
            a = vertices[0]
            distance = sum((p[k]-a[k])*n[k] for k in range(3))
            if abs(distance) >= clearance:
                continue
            projected = [p[k]-distance*n[k] for k in range(3)]
            if inside(projected, vertices, n):
                return False
            for a, b in zip(vertices, vertices[1:]+vertices[:1]):
                edge = [b[k]-a[k] for k in range(3)]
                length = sum(v*v for v in edge)
                t = max(0, min(1, sum((p[k]-a[k])*edge[k] for k in range(3))/length)) if length else 0
                if sum((p[k]-a[k]-edge[k]*t)**2 for k in range(3)) < clearance**2:
                    return False
        return True

    def segment(a, b, clearance=96):
        count = max(1, math.ceil(math.dist(a, b) / 4))
        return all(clear(tuple(a[k] + (b[k]-a[k])*i/count for k in range(3)), clearance)
                   for i in range(count+1))

    # Main village only. No routes to the Deku tunnel or training passages.
    # Fixed fairy/home subjects keep yaw independent of small path tangents.
    subjects = [(-292,58,-430), (45,58,-272), (669,58,521),
                (853,158,-311), (-10,238,-22), (-608,178,1022),
                (18,-22,873), (-678,59,-179)]
    styles = ('clearing traverse', 'pull-back reveal', 'rising crane', 'diagonal flyby')
    lines = [signature, '/* Elevated movie shots, collision checked offline. */',
             '#define TITLE_SHOT_TICKS 600',
             f'#define TITLE_SHOT_COUNT {len(subjects)}',
             'typedef struct { short x,y,z,yaw,pitch; } title_point_t;']
    for i, target in enumerate(subjects):
        points = None
        # Search clear staging for four distinct travelling shots. Never
        # substitute a tunnel route or a stationary swivel when a shot fails.
        for height in (200, 260, 320):
            if points is not None:
                break
            for radius in (360, 440, 280):
                if points is not None:
                    break
                for turn in range(24):
                    angle = (turn + i*3) * math.tau / 24
                    candidate = []
                    for sample in range(65):
                        t = sample / 64
                        t = t*t*(3-2*t)  # gentle acceleration and braking
                        if i % 4 == 0:
                            forward, across, up = radius, 520*(t-.5), height
                        elif i % 4 == 1:
                            forward, across, up = radius-80+280*t, 0, height
                        elif i % 4 == 2:
                            forward, across, up = radius+100*t, 0, height+140*t
                        else:
                            forward, across, up = radius+140-200*t, 420*(t-.5), height+60-40*t
                        x = target[0] + forward*math.sin(angle) + across*math.cos(angle)
                        z = target[2] + forward*math.cos(angle) - across*math.sin(angle)
                        y = target[1] + up
                        distance = math.hypot(x-target[0], z-target[2])
                        # Project subject to x=60/260 with title focal length
                        # 180, including elevation. Logo stays in the middle.
                        ratio = 100 / 180
                        side = math.asin(math.sqrt(ratio**2*(up**2+distance**2)
                                                 / (distance**2*(1+ratio**2))))
                        pitch = round(-math.atan2(up, distance*math.cos(side))*65536/math.tau)
                        yaw = round(math.atan2(target[0]-x, target[2]-z)*65536/math.tau)
                        # Logo owns the centre. Alternate left/right margins.
                        yaw += round(side*(1 if i % 2 == 0 else -1)*65536/math.tau)
                        yaw = (yaw+32768)%65536-32768
                        candidate.append((round(x),round(y),round(z),yaw,pitch))
                    if (all(segment(a[:3],b[:3]) for a,b in zip(candidate,candidate[1:]))
                            and all(segment(p[:3], target, 16) for p in candidate[::8])):
                        points = candidate
                        break
        if points is None:
            raise ValueError(f'No clear {styles[i%4]} for fairy {i}: {target}')
        print(f'Title shot {i+1}: {styles[i%4]}, all segments clear')
        lines.append(f'static const title_point_t title_path_{i}[] = {{')
        lines.extend('    {%d,%d,%d,%d,%d},' % p for p in points)
        lines.append('};')
    lines.append('static const title_point_t *const title_paths[] = {'+
                 ','.join(f'title_path_{i}' for i in range(len(subjects)))+'};')
    output.write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    build()
