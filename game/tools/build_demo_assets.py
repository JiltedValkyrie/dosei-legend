"""Stage existing baseline title/collision assets; no mesh rebuild."""
from pathlib import Path
import argparse
import struct
from PIL import Image
from build_sgl_scene import read_scene

ROOT = Path(__file__).resolve().parents[1]

def rgb555(rgb):
    r, g, b = rgb
    return 0 if not (r or g or b) else 0x8000 | (b >> 3) << 10 | (g >> 3) << 5 | (r >> 3)


def build_fairy_sprite(wing):
    wing = wing.convert('L').resize((5, 10), Image.Resampling.LANCZOS)
    out = Image.new('RGB', (16, 16))
    pixels = out.load()
    wings = wing.load()
    for y in range(16):
        for x in range(16):
            dx, dy = x - 7.5, y - 7.5
            distance = (dx * dx + dy * dy) ** 0.5
            glow = max(0, int(255 - distance * 42))
            value = glow
            # Mirror the authentic OoT wing on either side of the glow.
            if 1 <= x < 6 and 3 <= y < 13:
                value = max(value, wings[x - 1, y - 3])
            if 10 <= x < 15 and 3 <= y < 13:
                value = max(value, wings[14 - x, y - 3])
            if value < 22:
                pixels[x, y] = (0, 0, 0)
            else:
                pixels[x, y] = (min(255, 80 + value),
                                min(255, 120 + value), 255)
    return out


def main(oot=None):
    baseline = ROOT.parent / 'shared'
    data, header, _, _ = read_scene(ROOT / 'levels/kokiri/assets/static/FOREST.BIN')
    start = header['collision_off']
    size = header['ncollision'] * 36
    collision = data[start:start + size]
    if len(collision) != size or not size:
        raise ValueError('Invalid collision extent')
    (ROOT / 'build/cd/FOREST.COL').write_bytes(collision)
    with Image.open(baseline / 'assets/static/ui/TITLE.TGA') as title:
        if title.size != (512, 256):
            raise ValueError('Unexpected title dimensions')
        pixels = title.convert('RGB').getdata()
        (ROOT / 'build/cd/TITLE.RGB').write_bytes(b''.join(struct.pack('>H', rgb555(p)) for p in pixels))
    (ROOT / 'build/cd/START.RGB').write_bytes((baseline / 'assets/static/ui/PRESS_START.RAW').read_bytes())
    if oot is None:
        oot = Path('D:/Workspace-Claude/game-decomps/n64/oot')
    candidates = sorted(Path(oot).glob(
        'extracted/*/assets/objects/gameplay_keep/gFairyWingTex.i8.png'))
    if not candidates:
        raise FileNotFoundError('extracted OoT fairy wing texture not found')
    with Image.open(candidates[-1]) as wing:
        fairy = build_fairy_sprite(wing)
    fairy.save(ROOT / 'build/generated/fairy-preview.png')
    (ROOT / 'build/cd/FAIRY.RGB').write_bytes(b''.join(
        struct.pack('>H', rgb555(pixel)) for pixel in fairy.getdata()))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--oot', type=Path)
    main(parser.parse_args().oot)
