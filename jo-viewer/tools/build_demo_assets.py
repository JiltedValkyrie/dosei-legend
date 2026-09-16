"""Stage existing baseline title/collision assets; no mesh rebuild."""
from pathlib import Path
import struct
from PIL import Image
from build_sgl_scene import read_scene

ROOT = Path(__file__).resolve().parents[1]

def rgb555(rgb):
    r, g, b = rgb
    return 0 if not (r or g or b) else 0x8000 | (b >> 3) << 10 | (g >> 3) << 5 | (r >> 3)

def main():
    baseline = ROOT.parent / 'title-screen'
    data, header, _, _ = read_scene(baseline / 'cd/FOREST.BIN')
    start = header['collision_off']
    size = header['ncollision'] * 36
    collision = data[start:start + size]
    if len(collision) != size or not size:
        raise ValueError('Invalid collision extent')
    (ROOT / 'cd/FOREST.COL').write_bytes(collision)
    with Image.open(baseline / 'assets/TITLE.TGA') as title:
        if title.size != (512, 256):
            raise ValueError('Unexpected title dimensions')
        pixels = title.convert('RGB').getdata()
        (ROOT / 'cd/TITLE.RGB').write_bytes(b''.join(struct.pack('>H', rgb555(p)) for p in pixels))
    (ROOT / 'cd/START.RGB').write_bytes((baseline / 'assets/PRESS_START.RAW').read_bytes())

if __name__ == '__main__':
    main()
