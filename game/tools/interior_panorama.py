"""Original z_vr_box skyboxes used by the shared interior pivot camera.

Bank rooms retain the existing six Kokiri filenames. Other source houses use
new rooms in the same virtual bank, independent of gameplay scene numbering.
Shops retain their source fixed viewpoint; only Kokiri browsing is wired yet.
"""

# prefix: (bank room, source skybox ID, asset, side count, Y rotation)
PANORAMAS = {
    'link_home': (0, 7, 'LHVR', 4, 0.0),
    'kokiri_shop': (2, 17, 'KSVR', 2, 0.8),
    'kokiri_home': (3, 12, 'KHVR', 4, 0.0),
    'kokiri_home3': (4, 14, 'K3VR', 3, 0.0),
    'kokiri_home4': (5, 32, 'K4VR', 3, 0.0),
    'kokiri_home5': (6, 33, 'K5VR', 3, 0.0),
    'kakariko': (7, 16, 'KKRVR', 4, 0.0),
    'kakariko3': (8, 34, 'KR3VR', 3, 0.0),
    'impa': (9, 26, 'IPVR', 4, 0.0),
    'malon_stable': (10, 15, 'MLVR', 4, 0.0),
    'labo': (11, 27, 'LBVR', 4, 0.0),
    'tent': (12, 28, 'TTVR', 3, 0.0),
}


def panorama_room(prefix, scene, source):
    spec = PANORAMAS.get(prefix)
    if spec is None:
        return 255
    skybox = source.scene_header(scene).get(0x11)
    cameras = source.collision_data(scene)['bgcams']
    setting = 0x17 if prefix == 'kokiri_shop' else 0x1a
    if not skybox or skybox[0][4] != spec[1] or len(cameras) < 2 or \
            cameras[1]['setting'] != setting or len(cameras[1]['vectors']) < 3:
        raise ValueError('%s panorama does not match source skybox/pivot camera' % prefix)
    return spec[0]
