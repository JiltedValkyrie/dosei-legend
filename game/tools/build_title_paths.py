"""Build collision-checked title routes from the forest's actual floor mesh."""
import heapq
import hashlib
import math
import struct
from functools import lru_cache
from pathlib import Path
from build_sgl_scene import read_scene

ROOT = Path(__file__).resolve().parents[1]
STEP = 16


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
        for x in range((lo[0] - 28) // 128, (hi[0] + 28) // 128 + 1):
            for z in range((lo[2] - 28) // 128, (hi[2] + 28) // 128 + 1):
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
    def clear(p):
        for vertices, n, lo, hi in nearby(p[0], p[2]):
            if any(p[k] < lo[k]-16 or p[k] > hi[k]+16 for k in range(3)):
                continue
            a = vertices[0]
            distance = sum((p[k]-a[k])*n[k] for k in range(3))
            if abs(distance) >= 16:
                continue
            projected = [p[k]-distance*n[k] for k in range(3)]
            if inside(projected, vertices, n):
                return False
            for a, b in zip(vertices, vertices[1:]+vertices[:1]):
                edge = [b[k]-a[k] for k in range(3)]
                length = sum(v*v for v in edge)
                t = max(0, min(1, sum((p[k]-a[k])*edge[k] for k in range(3))/length)) if length else 0
                if sum((p[k]-a[k]-edge[k]*t)**2 for k in range(3)) < 16**2:
                    return False
        return True

    @lru_cache(None)
    def node(x, z):
        heights = []
        for vertices, n, lo, hi in nearby(x, z):
            if x < lo[0] or x > hi[0] or z < lo[2] or z > hi[2]:
                continue
            if n[1] < 0.5:
                continue
            a = vertices[0]
            y = a[1] - (n[0]*(x-a[0]) + n[2]*(z-a[2]))/n[1]
            if y <= 350 and inside((x,y,z), vertices, n):
                heights.append(y)
        positions = []
        for y in sorted(set(round(v) for v in heights)):
            for eye in (90, 50, 130, 170):
                p = (x, round(y + eye), z)
                if clear(p) and p not in positions:
                    positions.append(p)
        return positions

    @lru_cache(maxsize=200000)
    def segment(a, b):
        count = max(1, math.ceil(math.dist(a,b)/4))
        return all(clear(tuple(a[k]+(b[k]-a[k])*i/count for k in range(3)))
                   for i in range(count+1))

    @lru_cache(None)
    def wall_cost(p):
        # Prefer the middle of a passage over the shortest wall-hugging route.
        # Narrow tunnels remain possible, but open village space wins ties.
        return sum(not clear((p[0]+dx,p[1],p[2]+dz))
                   for dx,dz in ((32,0),(-32,0),(0,32),(0,-32))) * 0.6

    def nearest(x,z):
        candidates = [(dx,dz) for dx in range(-8,9) for dz in range(-8,9)]
        candidates.sort(key=lambda d:d[0]**2+d[1]**2)
        for dx,dz in candidates:
            p = node(round(x/STEP)*STEP+dx*STEP, round(z/STEP)*STEP+dz*STEP)
            if p:
                return p[0]
        raise ValueError(f'No safe camera near {x},{z}')

    def route(start, end):
        start, end = nearest(*start), nearest(*end)
        queue = [(0,start)]
        cost, parent = {start:0}, {}
        visited = set()
        while queue:
            _, current = heapq.heappop(queue)
            if current in visited:
                continue
            visited.add(current)
            if current == end:
                break
            for dx,dz in ((STEP,0),(-STEP,0),(0,STEP),(0,-STEP),
                          (STEP,STEP),(STEP,-STEP),(-STEP,STEP),(-STEP,-STEP)):
                for nxt in node(current[0]+dx,current[2]+dz):
                    if abs(nxt[1]-current[1]) > 40 or not segment(current,nxt):
                        continue
                    value = cost[current]+math.dist(current,nxt)*(1+wall_cost(nxt))
                    if value < cost.get(nxt,math.inf):
                        cost[nxt],parent[nxt] = value,current
                        heapq.heappush(queue,(value+math.dist(nxt,end),nxt))
        else:
            closest = min(cost, key=lambda p: math.dist(p,end))
            raise ValueError(f'No connected camera route: {start} -> {end}; closest={closest}; reachable={len(cost)}')
        path = [end]
        while path[-1] != start:
            path.append(parent[path[-1]])
        path.reverse()
        # Chaikin corner cutting, accepted only if every resulting segment is clear.
        for _ in range(3):
            smooth = [path[0]]
            for a,b in zip(path,path[1:]):
                smooth.extend(tuple(round(a[k]*(1-t)+b[k]*t) for k in range(3)) for t in (.25,.75))
            smooth.append(path[-1])
            if all(segment(a,b) for a,b in zip(smooth,smooth[1:])):
                path = smooth
        # Even arc-length sampling produces constant speed through bends.
        samples = [path[0]]
        carried = 0
        for a,b in zip(path,path[1:]):
            length = math.dist(a,b)
            offset = 16-carried
            while offset < length:
                samples.append(tuple(round(a[k]+(b[k]-a[k])*offset/length) for k in range(3)))
                offset += 16
            carried = length-(offset-16)
        samples.append(path[-1])
        if not all(segment(a,b) for a,b in zip(samples,samples[1:])):
            samples = [path[0]]
            cursor = 0
            while cursor < len(path)-1:
                last = cursor+1
                for candidate in range(cursor+2,len(path)):
                    if math.dist(path[cursor],path[candidate]) > 20:
                        break
                    if segment(path[cursor],path[candidate]):
                        last = candidate
                if path[last] != samples[-1]:
                    samples.append(path[last])
                cursor = last
        assert all(segment(a,b) for a,b in zip(samples,samples[1:])), 'Camera intersects geometry'
        return samples

    shots = [((-350,-350),(800,450)), ((700,450),(1500,100)),
             ((1400,100),(2900,-400)), ((2800,-400),(3500,-800)),
             ((-700,1500),(-300,2050))]
    lines = [signature, '/* Generated collision-checked camera routes. */',
             'typedef struct { short x,y,z; } title_point_t;']
    for i,(start,end) in enumerate(shots):
        points = route(start,end)
        print(f'Title shot {i+1}: {len(points)} samples, all segments clear')
        lines.append(f'static const title_point_t title_path_{i}[] = {{')
        lines.extend('    {%d,%d,%d},' % p for p in points)
        lines.append('};')
    lines.append('static const title_point_t *const title_paths[] = {'+
                 ','.join(f'title_path_{i}' for i in range(len(shots)))+'};')
    lines.append('static const unsigned short title_path_counts[] = {'+
                 ','.join(f'sizeof(title_path_{i})/sizeof(title_point_t)' for i in range(len(shots)))+'};')
    output.write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    build()
