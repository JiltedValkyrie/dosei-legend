"""Bake OoT pause-page artwork for the VDP2 window renderer.

Source: KaleidoScope_SetPageVertices / sPageBgColor* / English page arrays.
The offline canvas uses the pause page's front-facing coordinate system.
"""
import argparse
import re
import struct
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
PAGES = ('SelectItem', 'Map', 'QuestStatus', 'Equipment', 'Save', 'Save')
SOURCE_PAGE = (0, 4, 3, 1, 5, 5)
WIDTH, HEIGHT = 320, 240


def load_texture(root, name):
    for folder in ('icon_item_nes_static','icon_item_static','icon_item_field_static','icon_item_24_static'):
        candidates = list((root/folder).glob(name+'.*.png'))
        if candidates:
            return Image.open(candidates[0]).convert('RGBA')
    raise ValueError('Missing pause texture '+name)


def source_colours(source):
    channels=[]
    for channel in ('Red','Green','Blue'):
        body=source.split('sPageBgColor'+channel+'[][4] = {',1)[1].split('};',1)[0]
        rows=re.findall(r'\{([^}]+)\}',body)
        channels.append([[int(x) for x in row.split(',') if x.strip()] for row in rows])
    return channels


def page_image(oot, page, gear=0, stick=False, emerald=False, slingshot=False):
    textures=oot/'extracted/ntsc-1.2/assets/textures'
    source=(oot/'src/overlays/misc/ovl_kaleido_scope/z_kaleido_scope.c').read_text(encoding='utf-8')
    colours=source_colours(source)
    image=Image.new('RGBA',(WIDTH,HEIGHT))
    image.putdata([(56,56,56,255) if (x+y)%2 == 0 else (0,0,0,0)
                   for y in range(HEIGHT) for x in range(WIDTH)])
    for column in range(3):
        for row in range(5):
            stem='gPause%s%d%d' % (PAGES[page],column,row)
            try: tile=load_texture(textures,stem+'ENGTex')
            except ValueError: tile=load_texture(textures,stem+'Tex')
            if tile.size != (80,32): raise ValueError('Pause section size changed')
            pixels=tile.load()
            for y in range(32):
                for x in range(80):
                    intensity,_,_,alpha=pixels[x,y]
                    rgb=tuple((c[SOURCE_PAGE[page]][column]*(79-x)+
                               c[SOURCE_PAGE[page]][column+1]*x)*intensity//(79*255)
                              for c in colours)
                    pixels[x,y]=(*rgb,alpha)
            image.alpha_composite(tile,(40+column*80,40+row*32))
    def icon(name,x,y,size=28):
        image.alpha_composite(load_texture(textures,name).resize((size,size),Image.Resampling.LANCZOS),(x,y))
    if page==0 and stick:
        icon('gItemIconDekuStickTex',66,64)
    if page==0 and slingshot:
        icon('gItemIconSlingshotTex',66,96)
    if page==3:
        if gear&1: icon('gItemIconSwordKokiriTex',174,64)
        if gear&2: icon('gItemIconShieldDekuTex',174,96)
        icon('gItemIconTunicKokiriTex',174,128)
        icon('gItemIconBootsKokiriTex',174,160)
    if page==2 and emerald:
        icon('gQuestIconKokiriEmeraldTex',182,168,20)
    if page==1:
        # Assemble at source coordinates, then scale the whole map uniformly.
        # 216x128 -> 288x171 (nearest integer height); never stretch to a square.
        map_layer=Image.new('RGBA',(WIDTH,HEIGHT))
        world=load_texture(textures,'gWorldMapImageTex')
        map_layer.alpha_composite(world,(52,59))
        # The slice only visits Kokiri and its interiors. Other regions stay
        # clouded; no invented discovery flags or unowned quest items.
        def numbers(name):
            body=source.split(name,1)[1].split('{',1)[1].split('};',1)[0]
            return [int(v) for v in re.findall(r'^\s*(-?\d+),',body,re.M)]
        xs=numbers('sVtxPageMapWorldQuadsX[')
        ys=numbers('sVtxPageMapWorldQuadsY[')
        map_source=(oot/'src/overlays/misc/ovl_kaleido_scope/z_kaleido_map.c').read_text(encoding='utf-8')
        cloud_names=re.findall(r'gWorldMapCloud\w+Tex',map_source.split('cloudTexs[] = {',1)[1].split('};',1)[0])
        for i,name in enumerate(cloud_names):
            cloud=load_texture(textures,name)
            cloud.putdata([(235,235,235,r) for r,g,b,a in cloud.getdata()])
            map_layer.alpha_composite(cloud,(160+xs[i],120-ys[i]))
        dot=load_texture(textures,'gWorldMapDotTex')
        dot.putdata([(r,r,0,a) for r,g,b,a in dot.getdata()])
        map_layer.alpha_composite(dot,(234,129))
        image.alpha_composite(map_layer.crop((52,59,268,187)).resize(
            (288,171),Image.Resampling.LANCZOS),(16,32))
    if page==4:
        for name,x,y in (('gPauseSavePromptENGTex',84,84),
                         ('gPauseYesENGTex',102,126),('gPauseNoENGTex',170,126)):
            image.alpha_composite(load_texture(textures,name),(x,y))
    if page != 4:
        # Clean keycaps have no baked letters: the live font supplies the
        # selected controller's label at (16,112) / (280,112).
        draw=ImageDraw.Draw(image)
        for x in (12,276):
            draw.rounded_rectangle((x,104,x+31,127),radius=4,
                                   fill=(55,61,72,255),outline=(210,218,230,255),width=1)
        for name,x in (('gInfoPanelBgLeftTex',88),('gInfoPanelBgRightTex',160)):
            panel=load_texture(textures,name)
            panel.putdata([(r*90//255,r*100//255,r*130//255,a) for r,g,b,a in panel.getdata()])
            image.alpha_composite(panel,(x,204 if page==1 else 196))
    return image


def pack(image):
    # Index 14 is equipped gold; 15 is the light-blue selection. Pixels use a page-local palette.
    rgb=image.convert('RGB').quantize(colors=13,method=Image.Quantize.MEDIANCUT)
    colours=rgb.getpalette()[:39]
    palette=[0] + [0x8000 | (colours[i]>>3) | (colours[i+1]>>3)<<5 |
             (colours[i+2]>>3)<<10 for i in range(0,39,3)] + [0x83FF, 0xFF50]
    indices=[i+1 if a>=128 else 0 for i,(_,_,_,a) in zip(rgb.getdata(),image.getdata())]
    data=bytes((indices[i]<<4)|indices[i+1] for i in range(0,len(indices),2))
    return struct.pack('>16H',*palette)+data


def pack_map(image):
    """Eleven regional palettes, preserving the existing 4bpp cell format.

    CRAM 848..1023 is reserved for this page. 352 palette bytes, 1200 cell
    bank bytes and 38400 pixel bytes fit the existing 40 KiB cart buffer.
    Other HUD palettes and character allocations are never overwritten.
    """
    palettes=[]
    indices=Image.new('L',image.size)
    banks=[]
    for bank in range(11):
        left=(bank*40//11)*8
        right=((bank+1)*40//11)*8
        region=image.crop((left,0,right,HEIGHT))
        quant=region.convert('RGB').quantize(colors=15,method=Image.Quantize.MEDIANCUT)
        colours=quant.getpalette()[:45]
        palettes.extend([0]+[0x8000 | (colours[i]>>3) |
            (colours[i+1]>>3)<<5 | (colours[i+2]>>3)<<10 for i in range(0,45,3)])
        encoded=Image.new('L',region.size)
        encoded.putdata([q+1 if p[3]>=128 else 0 for q,p in zip(quant.getdata(),region.getdata())])
        indices.paste(encoded,(left,0))
    for y in range(30):
        for x in range(40):
            banks.append(next(b+5 for b in range(11) if b*40//11<=x<(b+1)*40//11))
    pixels=list(indices.getdata())
    packed=bytes((pixels[i]<<4)|pixels[i+1] for i in range(0,len(pixels),2))
    return struct.pack('>176H',*palettes)+bytes(banks)+packed


def build(oot,cd,out):
    cd.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
    for page in range(6):
        variants=range(4) if page in (0,3) else range(2) if page==2 else range(1)
        for variant in variants:
            image=page_image(oot,page,variant,page==0 and bool(variant&1),page==2 and variant==1,page==0 and bool(variant&2))
            blob=pack_map(image) if page==1 else pack(image)
            (cd/('PAUSE%d%d.BIN'%(page,variant))).write_bytes(blob)
            image.save(out/('pause-%d-%d.png'%(page,variant)))
            if page==1:
                palette=struct.unpack('>176H',blob[:352])
                preview=Image.new('RGBA',(WIDTH,HEIGHT))
                pixels=[]
                for y in range(HEIGHT):
                    for x in range(WIDTH):
                        index=(blob[1552+y*160+x//2]>>(0 if x&1 else 4))&15
                        bank=blob[352+(y//8)*40+x//8]-5
                        word=palette[bank*16+index]
                        pixels.append(((word&31)*255//31,((word>>5)&31)*255//31,
                                       ((word>>10)&31)*255//31,255 if index else 0))
                preview.putdata(pixels)
                preview.save(out/'pause-map-packed.png')
    masks=[]
    textures=oot/'extracted/ntsc-1.2/assets/textures'
    for corner in ('TopLeft','TopRight','BottomLeft','BottomRight'):
        tex=load_texture(textures,'gPauseMenuCursor'+corner+'Tex')
        masks.append([sum(1<<x for x in range(16) if tex.getpixel((x,y))[3]>=128) for y in range(16)])
    (out/'pause_cursor_data.h').write_text('/* Original OoT cursor alpha masks. */\nstatic const unsigned short pause_cursor_masks[4][16] = {\n'+
        ',\n'.join('{'+','.join(map(str,m))+'}' for m in masks)+'\n};\n')
    print('Pause windows: 38432 bytes per page; map 39952 bytes, 11 palettes')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--oot',type=Path,default=Path('D:/Workspace-Claude/game-decomps/n64/oot'))
    p.add_argument('--cd',type=Path,default=ROOT/'build/cd')
    p.add_argument('--out',type=Path,default=ROOT/'build/generated')
    a=p.parse_args();build(a.oot,a.cd,a.out)
