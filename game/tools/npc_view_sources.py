"""Compile actor-specific sprite snapshots into their owning scene packs."""
from pathlib import Path
import re

TEMPLATE = Path(__file__).resolve().parents[1] / 'oot-core/include/oot_pack_npc_views.inc'
ITEM_ACTORS = {'ACTOR_EN_EX_ITEM', 'ACTOR_ITEM_ETCETERA', 'ACTOR_EN_EX_RUPPY', 'ACTOR_EN_G_SWITCH'}


def actor_ids():
    text = TEMPLATE.read_text()
    return (
        set(re.findall(r'case (ACTOR_\w+):', text)) |
        set(re.findall(r'NPC_IN_PACK\((ACTOR_\w+)\)', text)) | ITEM_ACTORS)


def pack_source(names):
    selected = {'ACTOR_' + name.upper() for name in names}
    text = TEMPLATE.read_text()
    selected &= actor_ids()
    if not selected:
        return ''
    text = re.sub(r'^        case (ACTOR_\w+):[^\n]*\n',
                  lambda m: m.group() if m[1] in selected else '', text, flags=re.M)
    # Constant membership makes absent actor branches and their asset references
    # disappear at compile time. No runtime registry or duplicated mutable state.
    text = re.sub(r'NPC_IN_PACK\((ACTOR_\w+)\)', lambda m: '1' if m[1] in selected else '0', text)
    if not selected.intersection(ITEM_ACTORS):
        text = text.replace('#include "child_minigame_views.inc"\n', '')
        text = text.replace('    s32 itemView=ChildMinigame_ItemView(actor,play,v);\n    if (itemView) return itemView;\n', '')
    return text


if __name__ == '__main__':
    import argparse
    from oot_core_import import fix_float_literals
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    names = [n[6:] for n in actor_ids()]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(fix_float_literals(pack_source(names), {'fxl': 0}, 'npc_view_fixture'), encoding='utf8')
