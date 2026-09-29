"""Install self-contained, version-controlled visual room overrides."""
import json
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys
import tempfile

from mesh_assets import PROJECT, import_obj

sys.path.insert(0, str(PROJECT / 'tools'))
import room_imports
from build_sgl_scene import read_scene, collect_tiles

GAME_TARGETS = {
    'Kokiri Forest - room 0': 'spot04_room_0',
    'Kokiri Forest - room 1': 'spot04_room_1',
    'Kokiri Forest - room 2': 'spot04_room_2',
    'Deku Tree - entry room 0': 'ydan_room_0',
}


def install_mesh(path, target, *, split_incompatible=False, project=PROJECT):
    """Validate and bake before replacing files. Restore old files on write failure."""
    if target not in GAME_TARGETS:
        raise ValueError('Choose a supported game room')
    key = GAME_TARGETS[target]
    path = Path(path).resolve()
    actor_path = project / 'build/generated/LINK.BIN'
    if not actor_path.is_file():
        raise ValueError('Build the game Clean once first; Link mesh is needed for the room memory check.')
    try:
        data, head, vertices, faces = read_scene(actor_path)
        tiles = collect_tiles(data, head, faces)
    except SystemExit as exc:
        raise ValueError('Invalid generated Link mesh; rebuild Clean: ' + str(exc)) from exc
    actor = dict(tiles=[(t['width'], t['height']) for t in tiles.values()],
                 polygons=len(faces), vertices=len(vertices))
    config = project / 'assets/room_imports.json'
    entries = json.loads(config.read_text(encoding='utf-8')) if config.exists() else {}
    if not isinstance(entries, dict):
        raise ValueError('room_imports.json must contain a room mapping')
    destination = project / 'assets/room-meshes' / key
    with tempfile.TemporaryDirectory() as temp:
        # Import into temporary storage: reject broken UVs, materials, geometry
        # and unsupported textures without touching a previously installed room.
        bundle = import_obj(dict(id=key, source=str(path)), path, project,
                            Path(temp), split_incompatible=split_incompatible,
                            require_quads=False)
        override = dict(obj=bundle / 'mesh.obj', uv_mode='keep',
                        forest=key.startswith('spot04_'))
        room_imports.convert(override, actor)
        try:
            source = path.relative_to(project.parent.resolve()).as_posix()
        except ValueError:
            source = None  # External files are identified by hash, not a workstation path.
        publication = dict(published_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                           source=source, source_name=path.name,
                           source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                           files={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in bundle.iterdir() if p.name != 'mesh.json'})
        entries[key] = dict(obj=f'room-meshes/{key}/mesh.obj', uv_mode='keep',
                            publication=publication)
        writes = {destination / source.name: source.read_bytes()
                  for source in bundle.iterdir() if source.name != 'mesh.json'}
        # Manifest last: the build sees the new selection only after its files exist.
        writes[config] = (json.dumps(entries, indent=2) + '\n').encode('utf-8')
        previous = {p: p.read_bytes() if p.exists() else None for p in writes}
        changed = []
        try:
            for output, content in writes.items():
                output.parent.mkdir(parents=True, exist_ok=True)
                staged = output.parent / (output.name + '.workshop-tmp')
                try:
                    staged.write_bytes(content)
                    staged.replace(output)
                    changed.append(output)
                finally:
                    staged.unlink(missing_ok=True)
        except OSError:
            for output in reversed(changed):
                if previous[output] is None:
                    output.unlink(missing_ok=True)
                else:
                    output.write_bytes(previous[output])
            raise
    return destination
