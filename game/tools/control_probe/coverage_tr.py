"""Screen-ray coverage check of the selected ground and emitted command union.

This checks geometry, not framebuffer colors or visibility through actors.
A one-pixel raster tolerance avoids treating rounded shared edges as holes.
"""
import json
from pathlib import Path
import math


def dot(a,b):return sum(x*y for x,y in zip(a,b))
def sub(a,b):return [x-y for x,y in zip(a,b)]
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]


def coverage(folder):
    manifest=json.loads((folder/'assets.json').read_text())
    rows=[]
    points=[(x,y) for y in range(1,111,2) for x in range(-150,151,2)]
    rays=[(x/240,y/240,1) for x,y in points]
    for path in sorted(folder.glob('m[02]-*.json')):
        r=json.loads(path.read_text());mode=int(path.name[1]);expected=set()
        for f in r['faces']:
            a,b,c=f['view'][:3];e=sub(b,a);g=sub(c,a);n=cross(e,g)
            ee=dot(e,e);gg=dot(g,g);eg=dot(e,g);det=ee*gg-eg*eg;na=dot(n,a)
            # All ten selected STM faces are authored Single_Plane. Their
            # raw cross product points away from the visible side in SGL view.
            if na>=0:continue
            if det<1e-9:continue
            for i,ray in enumerate(rays):
                den=dot(ray,n)
                if abs(den)<1e-9:continue
                z=na/den
                if z<=1:continue
                p=[v*z-q for v,q in zip(ray,a)];pe=dot(p,e);pg=dot(p,g)
                u=(pe*gg-pg*eg)/det;v=(pg*ee-pe*eg)/det
                if u>=0 and v>=0 and u+v<=1:expected.add(i)
        covered=set();patch=0;parents={f['source'] for f in r['faces']}
        for command in r['commands']:
            c=command['words']
            if c[0]&15!=2:continue
            if mode==0:
                if c[4] not in parents:continue
            elif not r['tr_vram']<=c[4]*8<r['tr_vram']+manifest['extra_vram']:continue
            patch+=1
            sg=lambda v:v-65536 if v>=32768 else v
            q=[(sg(c[6+j*2]),sg(c[7+j*2])) for j in range(4)]
            area=abs(sum(q[j][0]*q[(j+1)%4][1]-q[(j+1)%4][0]*q[j][1] for j in range(4)))
            if area<1:continue
            edges=[sub(q[(j+1)%4],q[j]) for j in range(4)]
            tol=[math.hypot(*e) for e in edges]
            x0=max(-150,math.ceil(min(p[0] for p in q)-1));x1=min(150,math.floor(max(p[0] for p in q)+1))
            y0=max(1,math.ceil(min(p[1] for p in q)-1));y1=min(109,math.floor(max(p[1] for p in q)+1))
            if x0%2:x0+=1
            if not y0%2:y0+=1
            for y in range(y0,y1+1,2):
                for x in range(x0,x1+1,2):
                    side=[e[0]*(y-p[1])-e[1]*(x-p[0]) for e,p in zip(edges,q)]
                    if all(s>=-t for s,t in zip(side,tol)) or all(s<=t for s,t in zip(side,tol)):
                        covered.add(((y-1)//2)*151+(x+150)//2)
        rows.append(dict(name=path.stem,expected=len(expected),uncovered=len(expected-covered),commands=patch))
    (folder/'coverage.json').write_text(json.dumps(rows,indent=2))
    print(json.dumps(rows,indent=2))


if __name__=='__main__':
    import sys
    coverage(Path(sys.argv[1]))
