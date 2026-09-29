"""CPU texture inspection preview. Affine/painter rendering, not Saturn emulation."""
import math
from PIL import Image, ImageDraw
import viewport_scene


def textured_frame(ordered,width,height):
    scale=min(1,640/max(1,width),400/max(1,height))
    size=(max(1,round(width*scale)),max(1,round(height*scale)))
    frame=Image.new('RGBA',size,'#20262d'); draw=ImageDraw.Draw(frame)
    for _,polygon,face in ordered:
        if face['layer']!='Mesh': continue
        points=[(x*scale,y*scale) for x,y in polygon]
        raw=face.get('source_face')
        if not raw or len(points)!=3 or face.get('_near_clipped'):
            draw.polygon(points,fill=tuple(face['colour'])+(255,)); continue
        x0,y0=points[0]; x1,y1=points[1]; x2,y2=points[2]
        determinant=(x1-x0)*(y2-y0)-(x2-x0)*(y1-y0)
        if abs(determinant)<.1: continue
        left=max(0,math.floor(min(p[0] for p in points))); top=max(0,math.floor(min(p[1] for p in points)))
        right=min(size[0],math.ceil(max(p[0] for p in points))); bottom=min(size[1],math.ceil(max(p[1] for p in points)))
        if right<=left or bottom<=top: continue
        if '_patch' not in face: face['_patch']=viewport_scene.map_meshes.triangle_image(raw)
        a,b=(y2-y0)/determinant,-(x2-x0)/determinant
        d,e=-(y1-y0)/determinant,(x1-x0)/determinant
        coefficients=(31*a,31*b,31*(a*(left-x0)+b*(top-y0)),31*d,31*e,31*(d*(left-x0)+e*(top-y0)))
        patch=face['_patch'].transform((right-left,bottom-top),Image.Transform.AFFINE,coefficients,Image.Resampling.BILINEAR)
        frame.alpha_composite(patch,(left,top))
    return frame.resize((width,height),Image.Resampling.NEAREST)
