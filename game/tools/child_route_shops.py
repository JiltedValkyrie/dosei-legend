"""Source shops: purchase state machines stay intact, keepers use sprites.

Admission requires the shelf actor, all stock object identities, keeper/item
archives, camera/input/cursor support and matching host item grants. This
module does not claim admission merely because actors compile.
"""
import re

from field_enemy_sources import replace_body, replace_once

ACTORS = ('En_Ossan', 'En_GirlA', 'En_Tana')
SOURCES = [f'src/overlays/actors/ovl_{name}/z_{name.lower()}.c' for name in ACTORS]
KEEPER_SOURCE, ITEM_SOURCE, SHELF_SOURCE = SOURCES
SPRITE_OBJECTS = ('object_ossan', 'object_oF1d_map', 'object_os', 'object_zo', 'object_rs',
                  'object_ds2', 'object_km1', 'object_masterkokiri', 'object_mastergolon',
                  'object_masterzoora', 'object_masterkokirihead')
ANIMATION_OBJECTS = {
    'object_km1': ('object_masterkokiri',),
    'object_oF1d_map': ('object_mastergolon',),
    'object_zo': ('object_masterzoora',),
}
GEOMETRY_OBJECTS = ('object_shop_dungen',)
SOURCE_SCENES = ('shop1', 'drag', 'alley_shop', 'night_shop', 'face_shop', 'golon')
STOCK_OBJECTS = ('object_gi_nuts', 'object_gi_arrow', 'object_gi_bomb_1', 'object_gi_stick',
                 'object_gi_fish', 'object_gi_liquid', 'object_gi_longsword', 'object_gi_shield_2',
                 'object_gi_shield_1', 'object_gi_clothes', 'object_gi_heart', 'object_gi_milk',
                 'object_gi_egg', 'object_gi_bomb_2', 'object_gi_seed', 'object_gi_ki_tan_mask',
                 'object_gi_redead_mask', 'object_gi_skj_mask', 'object_gi_rabit_mask',
                 'object_gi_truth_mask', 'object_gi_zoramask', 'object_gi_golonmask',
                 'object_gi_gerudomask', 'object_gi_soldout', 'object_gi_fire', 'object_gi_insect',
                 'object_gi_ghost', 'object_gi_soul')


def adapt(rel, text):
    if rel == ITEM_SOURCE:
        text = replace_body(text, 'EnGirlA_Draw', '    /* Source stock/rotation has an offline sprite view. */')
        return replace_body(text, 'EnGirlA_Destroy', '    /* Shelf items never allocate a runtime skeleton. */')
    if rel != KEEPER_SOURCE:
        return text
    text = '#include "sprite_actor.h"\n' + text
    text = text.replace('SkelAnime_InitFlex(', 'OotCore_SpriteInitFlex(')
    text = replace_once(text, '    Math_StepToS(&this->headRot, this->headTargetRot, 0x190);',
                        '    /* Sprite facing uses body yaw; no head interpolation. */')
    for name in re.findall(r'^void (EnOssan_Draw\w*)\([^;{}]*\) \{', text, re.M):
        text = replace_body(text, name, '    /* Keeper sprite and shop UI are Saturn backend views. */')
    for name in re.findall(r'^s32 (EnOssan_OverrideLimbDraw\w*)\([^;{}]*\) \{', text, re.M):
        text = replace_body(text, name, '    return 0; /* No runtime character pose. */')
    return text


def stock_entries(oot):
    """All 50 original stock slots, not a hand-maintained route subset."""
    text = (oot / ITEM_SOURCE).read_text(encoding='utf-8')
    start = text.index('static ShopItemEntry sShopItemEntries[]') if 'static ShopItemEntry sShopItemEntries[]' in text else text.index('ShopItemEntry sShopItemEntries[]')
    body = text[start:text.index('\n};', start)]
    rows = re.findall(r'\{\s*(OBJECT_\w+),\s*(GID_\w+),[^{}]*?\}', body, re.S)
    if len(rows) != 50:
        raise ValueError(f'Shop stock table changed: expected 50, found {len(rows)}')
    return rows


def stock_draws(oot):
    """Get-item display lists keyed by source GID; real ROM input only."""
    text = (oot / 'src/code/z_draw.c').read_text(encoding='utf-8')
    table = {gid: (draw, lists) for gid, draw, lists in re.findall(
        r'//\s*(GID_\w+)\s*\n\s*\{\s*(\w+),\s*\{([^{}]*)\}', text)}
    result = {}
    for obj, gid in stock_entries(oot):
        if gid not in table:
            raise ValueError('Source get-item recipe missing: ' + gid)
        draw, words = table[gid]
        lists = tuple(re.findall(r'\b(?:gGi\w+|g\w+DL|object_\w+DL_\w+)\b', words))
        if not lists:
            raise ValueError('Empty source shop display recipe: ' + gid)
        marker = 'void ' + draw + '(PlayState* play, s16 giDrawId) {'
        start = text.index(marker)
        body = text[start:text.index('\n}', start)]
        indices = [int(n) for n in re.findall(r'(?:sDrawItemTable\[giDrawId\]\.|entry->)dlists\[(\d+)\]', body)]
        if not indices or any(i >= len(lists) for i in indices):
            raise ValueError('Source get-item draw order changed: ' + draw)
        result[gid] = (obj, tuple(lists[i] for i in indices))
    return result


def stock_sprite_keys(oot):
    """One archive per stock object; GID variants are source-table order."""
    variants, bases, result = {}, {}, {}
    recipes = stock_draws(oot)
    objects = {obj.lower() for obj, _ in recipes.values()}
    if objects != set(STOCK_OBJECTS):
        raise ValueError('Shop object registry differs from original stock table')
    for gid, (obj, lists) in recipes.items():
        base = bases.setdefault(obj, lists[0])
        variant = variants.get(obj, 0)
        variants[obj] = variant + 1
        result[gid] = (obj.lower(), base, variant, lists)
    return result


def scene_objects(oot, scene_c):
    """Actual keeper/store closure; never preload all fifty stock variants."""
    stem = scene_c.name.removesuffix('_scene.c')
    text = ''.join(p.read_text(encoding='utf-8') for p in scene_c.parent.glob(stem + '*ActorEntryList.inc.c'))
    kinds = [int(n, 0) for n in re.findall(
        r'ACTOR_EN_OSSAN,\s*\{[^}]*\},[^\n]*\n\s*\{[^}]*\},[^\n]*\n\s*(0x[0-9a-fA-F]+|\d+),', text)]
    if not kinds:
        return set()
    keeper = (oot / KEEPER_SOURCE).read_text(encoding='utf-8')
    start = keeper.index('static s16 sShopkeeperObjectIds')
    rows = re.findall(r'\{([^{}]+)\}', keeper[start:keeper.index('\n};', start)])
    keeper_objects = [set(re.findall(r'OBJECT_\w+', row)) - {'OBJECT_ID_MAX'} for row in rows]
    header = (oot / ITEM_SOURCE).with_suffix('.h').read_text(encoding='utf-8')
    names = re.findall(r'/\* 0x[0-9A-F]+ \*/ (SI_\w+),', header)
    stock = dict(zip(names, stock_entries(oot)))
    start = keeper.index('static ShopItem sShopkeeperStores')
    stores = re.findall(r'\{\s*(SI_\w+),', keeper[start:keeper.index('\n};', start)])
    if len(stores) != 88 or len(keeper_objects) != 11:
        raise ValueError('Source shop keeper/store layout changed')
    result = {'object_shop_dungen'}
    for kind in kinds:
        result.update('object_oF1d_map' if obj == 'OBJECT_OF1D_MAP' else obj.lower()
                      for obj in keeper_objects[kind])
        result.update(stock[name][0].lower() for name in stores[kind * 8:kind * 8 + 8])
        if kind in (2, 10):
            result.add('object_gi_soldout')
    return result
