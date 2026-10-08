"""Remove obsolete mesh banks for rooms now registered as image backdrops.

The density experiment must not stage old story banks under real image-scene
IDs. scene_flow_load takes the RGB/panorama branch for these registrations;
their old native MSH/TEX files are unreachable. Keep RGB, collision, all mesh
scenes and the separate C* panorama/story namespace.
"""
import hashlib
import json
from pathlib import Path

import asset_names
from build_hybrid_scene import texture_halve_mode


def prune(generated, cd, scenes):
    removed = []
    for scene, entry in enumerate(scenes):
        if entry['shape'] != 'image':
            continue
        for room in range(entry['rooms']):
            for folder in (generated, cd):
                for ext in ('MSH', 'TEX'):
                    path = folder / asset_names.room_asset(scene, room, ext)
                    if path.is_file():
                        data = path.read_bytes()
                        removed.append(dict(file=path.name, folder=folder.name,
                                            prefix=entry['prefix'], bytes=len(data),
                                            sha256=hashlib.sha256(data).hexdigest()))
                        path.unlink()
    return removed


if __name__ == '__main__':
    # An unset/zero mode retains the pre-experiment build behavior exactly.
    if texture_halve_mode():
        from build_scene_table import SCENES
        root = Path(__file__).resolve().parents[1]
        removed = prune(root / 'build/generated', root / 'build/cd', SCENES)
        if removed:
            report = root / 'build/generated/obsolete_image_banks.json'
            report.write_text(json.dumps(removed, indent=2) + '\n')
            print('Removed unreachable image-scene mesh banks:',
                  ', '.join(sorted({r['file'] for r in removed})))
