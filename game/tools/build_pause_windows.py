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
            if page==5 and row==0 and column==1:
                # Repeat the heading tile's clean left border strip across
                # its entire width, including the lettering's top pixels.
                strip=tile.crop((0,0,8,32))
                for x in range(0,80,8): tile.paste(strip,(x,0))
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
            cloud.putdata([(180,185,195,r*96//255) for r,g,b,a in cloud.getdata()])
            map_layer.alpha_composite(cloud,(160+xs[i],120-ys[i]))
        dot=load_texture(textures,'gWorldMapDotTex')
        dot.putdata([(r,r,0,a) for r,g,b,a in dot.getdata()])
        map_layer.alpha_composite(dot,(234,129))
        # Reuse the page's stone rim around the enlarged map. The frame sits
        # outside its 288x171 image, so no terrain is cropped or squeezed.
        stone=image.crop((48,192,128,200))
        side=image.crop((40,72,48,168)).resize((8,171),Image.Resampling.LANCZOS)
        for x in range(8,312,80):
            strip=stone.crop((0,0,min(80,312-x),8))
            image.alpha_composite(strip,(x,24))
            image.alpha_composite(strip,(x,203))
        image.alpha_composite(side,(8,32))
        image.alpha_composite(side.transpose(Image.Transpose.FLIP_LEFT_RIGHT),(304,32))
        rim=ImageDraw.Draw(image)
        rim.rectangle((8,24,311,210),outline=(76,80,86,255))
        rim.rectangle((15,31,304,203),outline=(12,14,18,255))
        image.alpha_composite(map_layer.crop((52,59,268,187)).resize(
            (288,171),Image.Resampling.LANCZOS),(16,32))
        # Current region marker: a dark outline and white ring remain visible
        # against both forest greens and pale clouds. Baked VDP2 art, no sprite.
        marker=ImageDraw.Draw(image)
        marker.ellipse((254,121,274,141),fill=(8,12,20,255))
        marker.ellipse((256,123,272,139),fill=(255,255,255,255))
        marker.ellipse((259,126,269,136),fill=(255,224,32,255))
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
        for name,x in (() if page==5 else (('gInfoPanelBgLeftTex',88),('gInfoPanelBgRightTex',160))):
            panel=load_texture(textures,name)
            panel.putdata([(r*90//255,r*100//255,r*130//255,a) for r,g,b,a in panel.getdata()])
            image.alpha_composite(panel,(x,204 if page==1 else 196))
    if page==5:
        # Solid text beds stop the frozen world/dither cutting through glyphs.
        draw=ImageDraw.Draw(image)
        draw.rectangle((48,60,271,187),fill=(12,16,23,255))
        draw.rectangle((48,196,271,231),fill=(12,16,23,255))
    return image


def pack(image):
    """Direct RGB555, no palette quantization. Zero is transparent."""
    return b''.join(struct.pack('>H',0 if a<128 else
        0x8000 | (r>>3) | (g>>3)<<5 | (b>>3)<<10)
        for r,g,b,a in image.getdata())


def menu_font(sdk):
    """Use Jo's native 8x8 bitmap, without resampling or threshold erosion.

    Font source: jo_engine/tools.c, Jo Engine BSD-3-Clause (Johannes Fetz).
    The SDK license remains with that source; only the existing bitmap is baked.
    """
    source=(sdk/'jo_engine/tools.c').read_text(encoding='utf-8')
    body=source.split('static unsigned char __jo_font[] =',1)[1].split('};',1)[0]
    font=bytes(int(v,16) for v in re.findall(r'0x([0-9A-Fa-f]{2})',body))
    if len(font)!=1024: raise ValueError('Expected Jo native 128-glyph 8x8 font')
    return font


def build(oot,cd,out,sdk=ROOT.parent.parent/'joengine'):
    cd.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
    for page in range(6):
        variants=range(4) if page in (0,3) else range(2) if page==2 else range(1)
        for variant in variants:
            image=page_image(oot,page,variant,page==0 and bool(variant&1),page==2 and variant==1,page==0 and bool(variant&2))
            blob=pack(image)
            (cd/('PAUSE%d%d.BIN'%(page,variant))).write_bytes(blob)
            image.save(out/('pause-%d-%d.png'%(page,variant)))
            preview=Image.new('RGBA',(WIDTH,HEIGHT))
            preview.putdata([((word&31)*255//31,((word>>5)&31)*255//31,
                             ((word>>10)&31)*255//31,255 if word else 0)
                             for (word,) in struct.iter_unpack('>H',blob)])
            preview.save(out/('pause-%d-%d-packed.png'%(page,variant)))
    masks=[]
    textures=oot/'extracted/ntsc-1.2/assets/textures'
    for corner in ('TopLeft','TopRight','BottomLeft','BottomRight'):
        tex=load_texture(textures,'gPauseMenuCursor'+corner+'Tex')
        masks.append([sum(1<<x for x in range(16) if tex.getpixel((x,y))[3]>=128) for y in range(16)])
    (out/'pause_cursor_data.h').write_text('/* Original OoT cursor alpha masks. */\nstatic const unsigned short pause_cursor_masks[4][16] = {\n'+
        ',\n'.join('{'+','.join(map(str,m))+'}' for m in masks)+'\n};\n')
    (cd/'PAUSEFNT.BIN').write_bytes(menu_font(sdk))
    print('Pause windows: full RGB555, 153600 bytes per page; font 1024 bytes')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--oot',type=Path,default=Path('D:/Workspace-Claude/game-decomps/n64/oot'))
    p.add_argument('--cd',type=Path,default=ROOT/'build/cd')
    p.add_argument('--out',type=Path,default=ROOT/'build/generated')
    p.add_argument('--sdk',type=Path,default=ROOT.parent.parent/'joengine')
    a=p.parse_args();build(a.oot,a.cd,a.out,a.sdk)
