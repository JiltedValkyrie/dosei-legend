"""Apply workshop quad topology while retaining source N64 material/UV data.

The workshop atlas is a lossy preview. Only unchanged source geometry and
material-compatible joins are accepted here; other source faces stay intact.
"""
import collections
import hashlib
import itertools
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'tools/mesh-workshop'))
import mesh_assets
import build_quads as quads


def preferred_pairs(path, faces, source_path):
    path = pathlib.Path(path)
    provenance = path.parent / 'source.json'
    if not provenance.is_file():
        provenance = path.parent / 'mesh.json'
    metadata = json.loads(provenance.read_text())
    expected = metadata.get('sha256', metadata.get('source_sha256'))
    if hashlib.sha256(pathlib.Path(source_path).read_bytes()).hexdigest() != expected:
        raise ValueError('Workshop OBJ source hash does not match the scene')
    diagnostics = {}
    vertices, _, polygons, _ = mesh_assets.parse_obj(
        path, split_incompatible=True, diagnostics=diagnostics)
    originals = collections.defaultdict(list)
    positions = {v[:3] for f in faces for v in f['vertices']}
    for v in vertices:
        rounded = tuple(round(x) for x in v)
        if rounded not in positions or max(abs(x-y) for x,y in zip(v,rounded)) > .01:
            raise ValueError('Workshop topology import requires unchanged source positions')
    for i, face in enumerate(faces):
        key = frozenset(v[:3] for v in face['vertices'])
        originals[key].append(i)
    pairs, used = [], set()
    rejected = 0
    for material, corners in polygons:
        if len(corners) != 4:
            continue
        boundary = [tuple(round(x) for x in vertices[v]) for v,_ in corners]
        candidates = [i for triangle in itertools.combinations(boundary,3)
                      for i in originals[frozenset(triangle)]]
        match = None
        for i,j in itertools.combinations(candidates,2):
            if i in used or j in used or not quads.same_texture(faces[i],faces[j]):
                continue
            flags = int(faces[i]['transparent']) | (int(faces[i]['cull']) << 1)
            if material != 'flags_%d' % flags:
                continue
            joined = quads.joined_points(faces[i],faces[j])
            if joined is None:
                continue
            joined_positions = [v[:3] for v in joined]
            if any(joined_positions == boundary[n:] + boundary[:n] for n in range(4)):
                match = (min(i,j),max(i,j))
                break
        if match is None:
            rejected += 1
        else:
            pairs.append(match)
            used.update(match)
    report = dict(path=str(path.resolve()), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  valid_quads=sum(len(c)==4 for _,c in polygons),
                  split_incompatible=diagnostics['split_quads'],
                  accepted_pairs=len(pairs), material_or_uv_rejected=rejected,
                  texture_source='original N64', source_faces_preserved=len(faces))
    return pairs, report
