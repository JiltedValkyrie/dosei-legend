"""Per-scene/room CD file names: one base-36 character per id (0-9, A-Z).

Mirrors `src/asset_names.h`. Keeps names 8.3 while allowing up to 36
scenes and 36 rooms (ydan 12 rooms, spot10 10 rooms).
"""
LIMIT = 36


def digit(value):
    if not 0 <= value < LIMIT:
        raise ValueError('asset id %r outside 0..%d' % (value, LIMIT - 1))
    return '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'[value]


def scene_stem(scene):
    """S<s> below 36, else Z<s1><s0> (src/asset_names.h asset_scene_name)."""
    if scene < LIMIT:
        return 'S' + digit(scene)
    if scene >= LIMIT * LIMIT:
        raise ValueError('scene id %r outside 0..%d' % (scene, LIMIT * LIMIT - 1))
    return 'Z' + digit(scene // LIMIT) + digit(scene % LIMIT)


def room_asset(scene, room, ext):
    return '%sR%s.%s' % (scene_stem(scene), digit(room), ext)


def scene_asset(scene, ext):
    return '%s.%s' % (scene_stem(scene), ext)
