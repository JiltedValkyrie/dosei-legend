"""Original nightmare drawbridge and chains, in native local world units."""
import argparse
import pathlib
import struct
from PIL import Image
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
            if name == 'CHAINS':
                # OoT renders these cutouts through an opaque display list.
                # KFR1 bit 0 controls VDP1 transparent-pixel processing.
                face['transparent'] = True
        link.apply_primitive_colour(lists.faces)
        link.write_model(lists.faces, out / (name + '.BIN'), character=False)
    build_flame(oot, out / 'GATEFIRE.BIN')


def build_flame(oot, path):
    """Bake gEffFire1DL's two-texture combiner into 32 scroll phases.

    BgSpot00Hanebasi_DrawTorches: yellow primitive, red environment,
    PRIM_LOD_FRAC=128, scale .008. Source quad is 64 x 128 world units.
    Quarter-resolution tiles retain both source textures; alpha is represented
    by transparent index zero with ordered coverage (Saturn has no alpha blend).
    """
    source = oot / 'extracted/ntsc-1.2/assets/objects/gameplay_keep'
    noise = Image.open(source / 'gEffFire1Tex.i4.png').convert('L')
    shape = Image.open(source / 'gEffFire2Tex.i8.png').convert('L')
    assert noise.size == (32,128) and shape.size == (32,64)
    bayer = ((0,8,2,10),(12,4,14,6),(3,11,1,9),(15,7,13,5))
    palette = [0] + [0x8000 | 31 | (round(i*31/15) << 5) for i in range(1,16)]
    texture, records = bytearray(), bytearray()
    for phase in range(32):
        indices = []
        for y in range(32):
            for x in range(16):
                # Tile-1 origin scroll is -20 in quarter-texel units/frame.
                a = max(0,min(255,shape.getpixel((x*2+1,y*2+1)) +
                    round((noise.getpixel((x*2+1,(y*2+1+phase*4)%128))-255)*128/255)))
                indices.append(max(1,round(a*15/255)) if a > bayer[y%4][x%4]*16+8 else 0)
        offset = len(texture)
        texture.extend(struct.pack('>16H',*palette))
        texture.extend(bytes((indices[i]<<4)|indices[i+1] for i in range(0,len(indices),2)))
        records.extend(struct.pack('>4HIIHH',0,1,2,3,offset+32,offset,0x220,1))
    vertices = struct.pack('>12h',-32,128,0,32,128,0,32,0,0,-32,0,0)
    record_off = 64+len(vertices)
    texture_off = record_off+len(records)
    header = struct.pack('>9I3i4I',0x4b465231,2,4,32,64,record_off,
                         texture_off,len(texture),texture_off+len(texture),0,64,0,72,35,texture_off,0)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(header+vertices+records+texture)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=pathlib.Path, default=link.OOT_DEFAULT)
    parser.add_argument('--rom-dir', type=pathlib.Path)
    parser.add_argument('--out', type=pathlib.Path,
                        default=pathlib.Path(__file__).resolve().parents[1] / 'build/generated')
    args = parser.parse_args()
    build(args.oot, args.rom_dir, args.out)
