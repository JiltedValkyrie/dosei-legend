"""Offline Field ground panels outside the accepted central retopology.

Split source planes only: collision remains the same surface, without spending
collision nodes on coplanar visual subdivisions. UVs, lighting and material
boundaries come from each original face. Central patch/fans remain untouched.
"""
import math

import build_quads as quads
from field_retopo import clip, area_poly, attributes, tile_size

# Finer whole-map trials (512/768/896/1024) exceed the combined Field + Link
# + owl vertex/polygon/slot limits. The central bundle keeps its 184 grid.
CELL = 1280


def extend(groups, excluded):
    replaced = panels = 0
    for group in groups:
        if group.get('retopo_drop') or set(group['source']) & excluded:
            continue
        if group['tri'].get('authored_mesh') or group['tri'].get('lod0_of') is not None:
            continue
        points = group['points']
        normal = quads.normal(points)
        if abs(normal[1]) < .85 * math.sqrt(sum(n*n for n in normal)) or not normal[1]:
            continue
        if quads.span(points) <= CELL:
            continue
        outline = [(p[0], p[2]) for p in points]
        xs, zs = [p[0] for p in points], [p[2] for p in points]
        plane = sum(normal[k] * points[0][k] for k in range(3))
        kids = []
        # A joined group has a coplanar, UV-continuous boundary. Its first
        # triangle supplies the same affine attributes across the whole quad.
        parent = dict(group['tri'], vertices=points[:3])
        for x in range(math.floor(min(xs) / CELL), math.ceil(max(xs) / CELL)):
            for z in range(math.floor((min(zs)-5100) / CELL), math.ceil((max(zs)-5100) / CELL)):
                polygon = clip(outline, x*CELL, (x+1)*CELL, 5100+z*CELL, 5100+(z+1)*CELL)
                if len(polygon) < 3 or abs(area_poly(polygon)) < 1e-6:
                    continue
                vertices = []
                for px, pz in polygon:
                    py = (plane - normal[0]*px - normal[2]*pz) / normal[1]
                    raw = attributes(parent, (px, py, pz))
                    vertex = (round(px), round(py), round(pz)) + tuple(raw[3:])
                    if not vertices or vertex[:3] != vertices[-1][:3]:
                        vertices.append(vertex)
                if len(vertices) > 1 and vertices[0][:3] == vertices[-1][:3]:
                    vertices.pop()
                if len(vertices) < 3:
                    continue
                parts = [vertices] if len(vertices) <= 4 else [
                    [vertices[0], vertices[i], vertices[i+1]] for i in range(1, len(vertices)-1)]
                for part in parts:
                    if not any(quads.normal(part)):
                        continue
                    kids.append(dict(kind=quads.BAKE, repeat=(1, 1),
                                     tri=dict(parent, vertices=part), points=part,
                                     texture=group['texture'], size=quads.span(part),
                                     source=group['source'], far_sort=True,
                                     retopo_tile=min(16, tile_size(part, group['texture']))))
        if not kids:
            raise ValueError('Field grid collapsed source %s' % group['source'])
        group['retopo_drop'] = kids
        replaced += 1
        panels += len(kids)
    print('Field ground grid: %d source groups -> %d panels, cell %d; central patch preserved'
          % (replaced, panels, CELL), flush=True)
    return groups
