"""Host-only camera math in native OoT coordinates (+Y up)."""
import math

def add(a, b): return tuple(x+y for x,y in zip(a,b))
def sub(a, b): return tuple(x-y for x,y in zip(a,b))
def mul(a, n): return tuple(x*n for x in a)
def dot(a, b): return sum(x*y for x,y in zip(a,b))

def bounds(points):
    points = list(points)
    return (tuple(min(p[i] for p in points) for i in range(3)),
            tuple(max(p[i] for p in points) for i in range(3))) if points else ((-100,-100,-100),(100,100,100))

def clip_near(points, near=5):
    """Clip a camera-space convex polygon; do not drop faces crossing the eye plane."""
    output = []
    for a,b in zip(points, points[1:] + points[:1]):
        inside_a, inside_b = a[2] >= near, b[2] >= near
        if inside_a: output.append(a)
        if inside_a != inside_b:
            t = (near-a[2])/(b[2]-a[2])
            output.append(add(a,mul(sub(b,a),t)))
    return output

def contains(poly, x, y):
    inside = False
    for a,b in zip(poly, poly[1:] + poly[:1]):
        if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
            inside = not inside
    return inside

class Camera:
    def __init__(self):
        self.position = (0,400,-800)
        self.yaw, self.pitch = 0., -.35
        self.pivot = (0,0,0)
        self.speed = 700.

    def basis(self):
        sy,cy,sp,cp = math.sin(self.yaw),math.cos(self.yaw),math.sin(self.pitch),math.cos(self.pitch)
        # Same handedness as the game: screen right is -X while looking +Z.
        return (sy*cp,sp,cy*cp), (-cy,0,sy), (-sy*sp,cp,-cy*sp)

    def look(self, dx, dy, orbit=False):
        distance = math.sqrt(dot(sub(self.position,self.pivot),sub(self.position,self.pivot)))
        self.yaw -= dx*.005
        self.pitch = max(-1.53,min(1.53,self.pitch-dy*.005))
        if orbit: self.position = sub(self.pivot,mul(self.basis()[0],max(10,distance)))

    def fly(self, keys, seconds):
        f,r,_ = self.basis()
        direction = add(add(mul(f,int('w' in keys)-int('s' in keys)),
                            mul(r,int('d' in keys)-int('a' in keys))),
                        (0,int('e' in keys)-int('q' in keys),0))
        length = math.sqrt(dot(direction,direction))
        if length: self.position = add(self.position,mul(direction,self.speed*seconds/length))

    def frame(self, box, aspect=1.4):
        lo,hi = box
        self.pivot = mul(add(lo,hi),.5)
        radius = max(40,math.sqrt(dot(sub(hi,lo),sub(hi,lo)))*.5)
        distance = radius / math.sin(math.atan(min(1,aspect)*math.tan(math.radians(60)/2))) * 1.15
        self.position = sub(self.pivot,mul(self.basis()[0],distance))

    def pan(self, dx, dy):
        _,r,u = self.basis()
        distance = math.sqrt(dot(sub(self.position,self.pivot),sub(self.position,self.pivot)))
        movement = mul(add(mul(r,-dx),mul(u,dy)),max(.1,distance*.0015))
        self.position = add(self.position,movement)
        self.pivot = add(self.pivot,movement)

    def dolly(self, amount):
        self.position = add(self.position,mul(self.basis()[0],amount))

    def view(self, point):
        f,r,u = self.basis()
        p = sub(point,self.position)
        return dot(p,r),dot(p,u),dot(p,f)

def project(p, width, height):
    scale = height/(2*math.tan(math.radians(60)/2))
    return width*.5+p[0]*scale/p[2],height*.5-p[1]*scale/p[2]
