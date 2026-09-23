"""Original nightmare drawbridge and chains, in native local world units."""
import argparse
import pathlib
import xml.etree.ElementTree as ET

import build_link_model as link


def build(oot, rom_dir, out):
    data = link.read_object(oot, 'object_spot00_objects', rom_dir)
    xml = ET.parse(oot / 'assets/xml/objects/object_spot00_objects.xml')
    offsets = {e.attrib['Name']: int(e.attrib['Offset'], 16)
               for e in xml.iter('DList')}
    for name, symbol in [('BRIDGE', 'gHyruleFieldCastleDrawbridgeDL'),
                         ('CHAINS', 'gHyruleFieldCastleDrawbridgeChainsDL')]:
        lists = link.LimbLists(b'', b'')
        lists.segments = {6: data}
        lists.current_limb = 0
        lists.matrix_limbs = []
        lists.walk(0x06000000 | offsets[symbol])
        for face in lists.faces:
            face['limb'] = 0
            face['full_texture'] = True
        link.apply_primitive_colour(lists.faces)
        link.write_model(lists.faces, out / (name + '.BIN'), character=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=pathlib.Path, default=link.OOT_DEFAULT)
    parser.add_argument('--rom-dir', type=pathlib.Path)
    parser.add_argument('--out', type=pathlib.Path,
                        default=pathlib.Path(__file__).resolve().parents[1] / 'build/generated')
    args = parser.parse_args()
    build(args.oot, args.rom_dir, args.out)
