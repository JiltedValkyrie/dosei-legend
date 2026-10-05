"""Measure texture-coordinate error from actual captured VDP1 commands.

Compare bilinear VDP1 mapping with perspective projection of the same world
surface samples. This is geometric evidence, not a substitute for window tests.
"""
import json
import math
from pathlib import Path
import statistics
from control import RUN


def inverse(q,x,y):
    ax,ay=q[0];bx,by=[q[1][i]-q[0][i] for i in (0,1)]
    cx,cy=[q[3][i]-q[0][i] for i in (0,1)]
    dx,dy=[q[0][i]-q[1][i]+q[2][i]-q[3][i] for i in (0,1)]
    u=v=.5
    for _ in range(15):
        fx=ax+bx*u+cx*v+dx*u*v-x;fy=ay+by*u+cy*v+dy*u*v-y
        j00=bx+dx*v;j01=cx+dx*u;j10=by+dy*v;j11=cy+dy*u
        det=j00*j11-j01*j10
        if abs(det)<1e-9:return None
        du=(fx*j11-fy*j01)/det;dv=(fy*j00-fx*j10)/det
        u-=du;v-=dv
        if abs(du)+abs(dv)<1e-8:break
    return (u,v) if -.02<=u<=1.02 and -.02<=v<=1.02 else None


def analyze(folder):
    manifest=json.loads((folder/'assets.json').read_text())
    assets=manifest['faces']
    levels=manifest['levels']
    def tile(j):
        for n in levels:
            if j<n*n:return n,j
            j-=n*n
        raise ValueError('Tile outside pyramid')
    byworld={tuple(tuple(p) for p in a['world']):a for a in assets}
    allresults={}
    for path in sorted(folder.glob('m[023]-*.json')):
        record=json.loads(path.read_text());mode=int(path.name[1])
        commands=[c['words'] for c in record['commands'] if c['words'][0]&15==2]
        # Palette identifies the current parent's pyramid; offsets locate it
        # independently of load-history sprite slots.
        data=[];missing=0;total=0
        for f in record['faces']:
            asset=byworld.get(tuple(tuple(p) for p in f['world']))
            if not asset:continue
            a,b,d=f['view'][:3]
            e=[b[k]-a[k] for k in range(3)];g=[d[k]-a[k] for k in range(3)]
            normal=[e[1]*g[2]-e[2]*g[1],e[2]*g[0]-e[0]*g[2],e[0]*g[1]-e[1]*g[0]]
            if sum(n*x for n,x in zip(normal,a))>=0:continue
            relevant=[c for c in commands if c[3]==f['palette']]
            root=[c for c in relevant if c[4]==f['source']]
            # Infer common texture-pyramid VRAM base from each unique parent.
            candidates={}
            if mode>=2:
                for c in relevant:
                    for j,offset in enumerate(asset['offsets']):
                        n,_=tile(j)
                        if c[5]!=(max(8,asset['width']//n)<<5 | asset['height']//n):continue
                        base=c[4]*8-offset
                        candidates[base]=candidates.get(base,0)+1
            base=record.get('tr_vram',max(candidates,key=candidates.get) if candidates else None)
            leaves={}
            for c in relevant:
                if base is not None and c[4]*8-base in asset['offsets']:
                    j=asset['offsets'].index(c[4]*8-base);n,idx=tile(j)
                    if c[5]==(max(8,asset['width']//n)<<5 | asset['height']//n):leaves[(n,idx%n,idx//n)]=c
            for iy in range(1,32):
                for ix in range(1,32):
                    # Avoid exact cell boundaries; integer raster corners can
                    # move a shared boundary by a fraction of a screen pixel.
                    u=(ix+.371)/32;v=(iy+.619)/32
                    weights=((1-u)*(1-v),u*(1-v),u*v,(1-u)*v)
                    view=[sum(w*p[k] for w,p in zip(weights,f['view'])) for k in range(3)]
                    if view[2]<1:continue
                    x,y=240*view[0]/view[2],240*view[1]/view[2]
                    # The lower viewport excludes sky, HUD and most far faces.
                    if not (-150<x<150 and 0<y<110):continue
                    total+=1
                    n=1;cx=cy=0;c=root[0] if root else None
                    if mode>=2 and leaves:
                        for div in reversed(levels):
                            candidate=leaves.get((div,int(u*div),int(v*div)))
                            if candidate is not None:n=div;cx=int(u*n);cy=int(v*n);c=candidate;break
                    if c is None:missing+=1;continue
                    signed=lambda n:n-65536 if n&32768 else n
                    quad=[(signed(c[6+i*2]),signed(c[7+i*2])) for i in range(4)]
                    uv=inverse(quad,x,y)
                    if uv is None:missing+=1;continue
                    a,b=uv
                    if c[0]&16:a=1-a
                    if c[0]&32:b=1-b
                    du=((cx+a)/n-u)*asset['width'];dv=((cy+b)/n-v)*asset['height']
                    data.append(math.hypot(du,dv))
        allresults[path.stem]=dict(samples=total,unmapped_samples=missing,
            mean_texel_error=round(statistics.mean(data),3) if data else None,
            p90_texel_error=round(sorted(data)[int(.9*(len(data)-1))],3) if data else None)
    (folder/'mapping-error.json').write_text(json.dumps(allresults,indent=2))
    print(json.dumps(allresults,indent=2))


if __name__=='__main__':
    import sys
    analyze(Path(sys.argv[1]) if len(sys.argv)>1 else RUN/'verification/tr-v1')
