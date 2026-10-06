"""Original OoT button artwork, adapted to Saturn A/X/C controls on NBG2."""
from pathlib import Path
import struct
from PIL import Image, ImageDraw

# Fixed screen patch, aligned to the VDP2 8x8 grid.
X, Y, W, H = 152, 0, 152, 64
CELL_LIMIT = 0x4000
ITEM_PATCH_CELLS = [(y,x) for y in range(2,8) for x in range(9,19)]
WEAPON_PATCH_CELLS = [(y,x) for y in range(2,7) for x in range(1,5)]
CAMERA_X, CAMERA_Y, CAMERA_W, CAMERA_H = 216, 64, 88, 24


def camera_strip():
    """Native pixel artwork for the approved Z / B+Z overhead-camera hint."""
    im = Image.new('RGBA', (W, H))
    d = ImageDraw.Draw(im)
    glyphs = dict(zip('CAMERZB+', (
        ('0111','1000','1000','1000','0111'),
        ('0110','1001','1111','1001','1001'),
        ('10001','11011','10101','10001','10001'),
        ('1111','1000','1110','1000','1111'),
        ('1110','1001','1110','1010','1001'),
        ('1111','0001','0010','0100','1111'),
        ('1110','1001','1110','1001','1110'),
        ('000','010','111','010','000'))))
    def text(word, x, y):
        for dx, colour in ((1, (8,12,24,255)), (0, (248,248,224,255))):
            at = x
            for ch in word:
                for row, bits in enumerate(glyphs[ch]):
                    for col, bit in enumerate(bits):
                        if bit == '1': d.point((at+col+dx,y+row+dx),fill=colour)
                at += len(glyphs[ch][0])+1
    text('CAMERA', 28, 1)
    for left, right in ((2,40),(46,85)):
        d.rounded_rectangle((left,9,right,23),radius=2,fill=(8,12,24,255))
        d.rectangle((left+2,10,right-2,20),fill=(40,48,88,255))
        d.line((left+2,10,right-2,10),fill=(136,152,192,255))
        d.line((left+2,11,left+2,19),fill=(88,104,152,255))
    text('Z', 13, 14)
    text('B+Z', 51, 14)
    arrow = [(3,0),(2,1),(1,2),(2,3),(3,4),(2,2),(5,2),(6,3),(7,4),(7,5),(6,6),(5,7),(3,7)]
    for ox, mirror in ((26,False),(73,True)):
        for shadow, colour in ((1,(8,12,24,255)),(0,(248,248,224,255))):
            for x,y in arrow:
                d.point((ox+(7-x if mirror else x)+shadow,12+y+shadow),fill=colour)
    return im


def make_images(oot, analog=False, mode="saturn", citems=None,
                empty_buttons=False, overlay_only=False, weapon=1):
    root = Path(oot) / 'extracted/ntsc-1.2/assets/textures'
    def tex(group, name):
        return Image.open(root / group / name).convert('RGBA')
    circle = tex('parameter_static', 'gButtonBackgroundTex.ia8.png')
    sword_name = ('Kokiri', 'Master', 'Biggoron')[weapon-1] if 1 <= weapon <= 3 else None
    sword = tex('icon_item_static', 'gItemIconSword%sTex.rgba32.png' % sword_name) if sword_name else None
    def tint(im, rgb):
        out = im.copy()
        out.putdata([(r * rgb[0] // 255, r * rgb[1] // 255,
                      r * rgb[2] // 255, a) for r, g, b, a in im.getdata()])
        return out
    def place(dst, im, x, y):
        dst.alpha_composite(im, (x-X, y-Y))
    # Tiny Saturn identifiers are deliberate adaptations, not N64 artwork.
    glyphs = {'A': ('010','101','111','101','101'),
              'B': ('110','101','110','101','110'),
              'Q': ('111','101','101','101','111'),
              '+': ('000','010','111','010','000'),
              'L': ('100','100','100','100','111'),
              '1': ('010','110','010','010','111'),
              'S': ('011','100','010','001','110'),
              'T': ('111','010','010','010','010'),
              'I': ('111','010','010','010','111'),
              'K': ('101','101','110','101','101'),
              'X': ('101','101','010','101','101'),
              'C': ('011','100','100','100','011'),
              'D': ('110','101','101','101','110'),
              'P': ('110','101','110','100','100'),
              '-': ('000','000','111','000','000')}
    def label(dst, text, x, y):
        if len(text) > 1:
            for i, ch in enumerate(text): label(dst,ch,x+4*i,y)
            return
        d = ImageDraw.Draw(dst)
        for j, bits in enumerate(glyphs[text]):
            for i, bit in enumerate(bits):
                if bit == '1':
                    d.point((x-X+i+1,y-Y+j+1), fill=(0,0,0,255))
        for j, bits in enumerate(glyphs[text]):
            for i, bit in enumerate(bits):
                if bit == '1': d.point((x-X+i,y-Y+j), fill='white')
    images = []
    for owned in (range(2) if citems is None else (0,)):
        for action in (('', 'Talk', 'Open', 'Enter', 'Check', 'Grab', 'Drop', 'Throw') if citems is None else ('',)):
            for navi in range(2):
                im = Image.new('RGBA', (W,H))
                place(im, tint(circle, (0,150,0)).resize((28,28), Image.Resampling.NEAREST), 160,17)
                if owned and sword is not None:
                    place(im, sword.resize((26,26), Image.Resampling.LANCZOS), 161,18)
                label(im, 'B' if mode in ('n64','gamecube') else 'Q' if mode=='playstation' else 'X', 171,47)
                place(im, tint(circle,(90,90,255)),186,9)
                label(im, 'X' if mode=='playstation' else 'A',200,43)
                if action:
                    word = tex('do_action_static', 'g%sDoActionENGTex.ia4.png' % ('Speak' if action == 'Talk' else action))
                    place(im,word.resize((40,13),Image.Resampling.LANCZOS),182,18)
                for slot,name,x,y in ((1,'Left',227,18),(0,'Down',249,34),(2,'Right',271,18)):
                    place(im,tint(circle,(255,160,0)).resize((26,26),Image.Resampling.NEAREST),x,y)
                    item = citems[slot] if citems else 0
                    if item:
                        icon = tex('icon_item_static', ('gItemIconDekuStickTex.rgba32.png',
                                   'gItemIconSlingshotTex.rgba32.png',
                                   'gItemIconDekuNutTex.rgba32.png')[item-1])
                        place(im,icon.resize((26,26),Image.Resampling.LANCZOS),x,y)
                    elif not empty_buttons:
                        arrow = tex('parameter_static','gEmptyC%sArrowTex.ia8.png' % name)
                        place(im,arrow.resize((26,26),Image.Resampling.NEAREST),x,y)
                header = ('C' if mode=='n64' else 'C-STICK' if mode=='gamecube' else
                          'D-PAD' if analog else 'C+DPAD' if mode=='xbox' else
                          'L1+DPAD' if mode=='playstation' else 'C')
                label(im,header,240 if len(header)>5 else 244 if len(header)>1 else 252,6)
                if overlay_only:
                    im = Image.new('RGBA', (W,H))
                if navi:
                    place(im,tint(circle,(255,160,0)).resize((16,16),Image.Resampling.NEAREST),254,16)
                    place(im,tex('parameter_static','gNaviCUpENGTex.ia4.png'),247,20)
                images.append(im)
    return images


def encode(images):
    """One shared 15-colour palette; transparent index zero; deduplicate cells."""
    atlas = Image.new('RGB',(W,H*len(images)))
    for i, im in enumerate(images): atlas.paste(im.convert('RGB'),(0,i*H))
    pal_image = atlas.quantize(colors=15, method=Image.Quantize.MEDIANCUT)
    palette = pal_image.getpalette()[:45]
    colours = [tuple(palette[i:i+3]) for i in range(0,45,3)]
    words = [0] + [0x8000 | (b>>3)<<10 | (g>>3)<<5 | (r>>3) for r,g,b in colours]
    tiles, ids, maps = [bytes(32)], {bytes(32):0}, []
    for im in images:
        quant = im.convert('RGB').quantize(palette=pal_image,dither=Image.Dither.NONE)
        entries = []
        for cy in range(H//8):
            for cx in range(W//8):
                pixels = []
                for y in range(8):
                    for x in range(8):
                        p = (cx*8+x,cy*8+y)
                        pixels.append(quant.getpixel(p)+1 if im.getpixel(p)[3]>=128 else 0)
                tile = bytes((pixels[i]<<4)|pixels[i+1] for i in range(0,64,2))
                if tile not in ids: ids[tile]=len(tiles); tiles.append(tile)
                entries.append(ids[tile])
        maps.append(entries)
    blob = b''.join(tiles)
    if len(blob)>CELL_LIMIT: raise ValueError('Gameplay HUD exceeds B0 cell reservation')
    return blob, words, maps


def build(oot, out_cd, out_gen):
    from build_health_hud import build as build_health
    out_cd, out_gen = Path(out_cd),Path(out_gen)
    out_cd.mkdir(parents=True,exist_ok=True); out_gen.mkdir(parents=True,exist_ok=True)
    build_health(oot, out_cd)
    images = make_images(oot)
    # Each preset contributes only changed label cells, never duplicate full maps.
    variants = [make_images(oot, analog=a, mode=m) for m in
                ('saturn','xbox','n64','gamecube','playstation') for a in (False,True)]
    # Runtime composes source ItemId icons into cached C-area banks. Keep only
    # clean button backgrounds and a transparent Navi overlay, avoiding an
    # exponential map for every assignment (and supporting all inventory slots).
    background = make_images(oot,citems=(0,0,0),empty_buttons=True)[0]
    navi_overlay = make_images(oot,citems=(0,0,0),overlay_only=True)[1]
    # Replace the whole weapon button plus its control label. Including the
    # label preserves every preset; old Kokiri hilt pixels cannot survive when
    # the equipped sword changes. Share cells, never duplicate action maps.
    # The rightmost cell overlaps the A artwork. Keep all eight action
    # captions so replacing a sword cannot erase the edge of Talk/Open/etc.
    # Only X/B/Q weapon labels differ here; analog and C labels are outside.
    weapons = [im for m in ('saturn','n64','playstation') for w in range(4)
               for im in make_images(oot,mode=m,weapon=w)[16:32:2]]
    blob, palette, all_maps = encode([im for group in variants for im in group] +
                                     [background,navi_overlay] + weapons)
    maps = all_maps[:32]
    # Includes C header, sword label (two rows), and action label (two rows).
    patch_cells = [(y,x) for y in range(2) for x in range(11,15)] + [(5,2),(6,2),(5,6),(6,6)]
    patches = []
    for mode in range(10):
        for owned in range(2):
            mapping = all_maps[mode*32 + owned*16]
            patches.append([mapping[y*(W//8)+x] for y,x in patch_cells])
    # Name-map reservation is full. Store this single strip in contiguous cells
    # so runtime derives tile IDs without another map or main-RAM table.
    camera_tile = len(blob)//32
    camera_blob, camera_palette, camera_maps = encode([camera_strip()])
    camera_cells = [camera_maps[0][y*(W//8)+x]
                    for y in range(CAMERA_H//8) for x in range(CAMERA_W//8)]
    blob += b''.join(camera_blob[tile*32:tile*32+32] for tile in camera_cells)
    camera_palette_offset = len(blob)
    blob += struct.pack('>16H', *camera_palette)
    if len(blob)>CELL_LIMIT: raise ValueError('Camera HUD exceeds button cell reservation')
    (out_cd/'BUTTONS.BIN').write_bytes(blob)
    map_words = [v for mapping in maps for v in mapping] + [v for patch in patches for v in patch]
    item_offset = len(map_words)
    map_words += [mapping[y*(W//8)+x] for mapping in all_maps[320:322]
                  for y,x in ITEM_PATCH_CELLS]
    weapon_offset = len(map_words)
    map_words += [mapping[y*(W//8)+x] for mapping in all_maps[322:322+len(weapons)]
                  for y,x in WEAPON_PATCH_CELLS]
    if len(map_words)*2 > 0x3800: raise ValueError('HUD maps collide with composed C-item banks')
    (out_cd/'BUTTONS.MAP').write_bytes(struct.pack('>%dH'%len(map_words),*map_words))
    h = ['/* Generated original OoT graphics with Saturn control labels. */',
         '#ifndef GAMEPLAY_HUD_DATA_H','#define GAMEPLAY_HUD_DATA_H',
         '#define HUD_PIXEL_BYTES %d' % len(blob),
         '#define HUD_MAP_X %d' % (X//8),'#define HUD_MAP_Y %d' % (Y//8),
         '#define HUD_MAP_W %d' % (W//8),'#define HUD_MAP_H %d' % (H//8),
         'static const unsigned short hud_palette[16] = {%s};' % ','.join(map(str,palette)),
         '#define HUD_VARIANT_COUNT 32',
         '#define HUD_ITEM_OFFSET %d' % item_offset,
         '#define HUD_NAVI_OFFSET %d' % (item_offset+len(ITEM_PATCH_CELLS)),
         '#define HUD_ITEM_COUNT %d' % len(ITEM_PATCH_CELLS),
         '#define HUD_WEAPON_OFFSET %d' % weapon_offset,
         '#define HUD_WEAPON_COUNT %d' % len(WEAPON_PATCH_CELLS),
         'static const unsigned short hud_weapon_positions[] = {%s};' %
             ','.join(str(y*64+x+X//8) for y,x in WEAPON_PATCH_CELLS),
         '#define HUD_ITEM_W 10', '#define HUD_ITEM_X 9', '#define HUD_ITEM_Y 2',
         'static const unsigned short hud_item_positions[] = {%s};' %
             ','.join(str(y*64+x+X//8) for y,x in ITEM_PATCH_CELLS),
         '#define HUD_MAP_BYTES %d' % (len(map_words)*2),
         '#define HUD_CAMERA_TILE %d' % camera_tile,
         '#define HUD_CAMERA_PALETTE %d' % camera_palette_offset,
         '#define HUD_CAMERA_X %d' % (CAMERA_X//8),
         '#define HUD_CAMERA_Y %d' % (CAMERA_Y//8),
         '#define HUD_CAMERA_W %d' % (CAMERA_W//8),
         '#define HUD_CAMERA_H %d' % (CAMERA_H//8),
         '#define HUD_PATCH_OFFSET %d' % (32*W*H//64),
         '#define HUD_PATCH_COUNT %d' % len(patch_cells),
         'static const unsigned short hud_patch_positions[] = {%s};' %
             ','.join(str(y*64+x+X//8) for y,x in patch_cells),
         '#endif','']
    (out_gen/'gameplay_hud_data.h').write_text('\n'.join(h))
    # Preview the actual quantized, deduplicated tile stream, not the source.
    preview = Image.new('RGBA',(W,H))
    for i, tile in enumerate(maps[11]):
        for pixel in range(64):
            packed = blob[tile*32+pixel//2]
            index = (packed >> (0 if pixel & 1 else 4)) & 15
            colour = palette[index]
            preview.putpixel(((i%(W//8))*8+pixel%8,(i//(W//8))*8+pixel//8),
                             ((colour&31)*255//31,((colour>>5)&31)*255//31,
                              ((colour>>10)&31)*255//31,255 if index else 0))
    preview.resize((W*4,H*4),Image.Resampling.NEAREST).save(out_gen/'gameplay-hud-preview.png')
    print('Gameplay HUD: %d cells, %d VDP2 bytes; no VDP1 slots' % (len(blob)//32,len(blob)))
