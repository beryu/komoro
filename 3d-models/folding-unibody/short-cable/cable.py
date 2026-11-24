"""Finite width/thickness ribbon with its easy bend axis parallel to Y.

The section director is constant Y: this is a generalized cylindrical,
developable strip. No in-plane bending or twist is used. mm throughout.
"""
import math,json
from pathlib import Path
WIDTH=7.7978
THICKNESS=.7366
HERE=Path(__file__).resolve().parent

def rotate(p,angle):
    x,y,z=p;t=math.radians(angle)
    return (x*math.cos(t)+(z-18.5)*math.sin(t),y,18.5-x*math.sin(t)+(z-18.5)*math.cos(t))

def points(angle):
    def line(a,b,n=10):return [tuple(a[j]+(b[j]-a[j])*i/n for j in range(3)) for i in range(n+1)]
    left=[rotate(p,angle) for p in line((-32.325,44.5,12.5),(-20,44.5,12.5))]
    paths=json.loads((HERE/'generated/cable-paths.json').read_text())
    free=paths[str(angle)]['points']
    right=line((0,44.5,2.4),(16.3,44.5,2.4))
    for i in range(1,25):
        t=-math.pi/2+math.pi/2*i/24
        right.append((16.3+3*math.cos(t),44.5,5.4+3*math.sin(t)))
    right+=line((19.3,44.5,5.4),(19.3,44.5,11.3))[1:]
    for i in range(1,25):
        t=math.pi-math.pi/2*i/24
        right.append((22.3+3*math.cos(t),44.5,11.3+3*math.sin(t)))
    right+=line((22.3,44.5,14.3),(25.,44.5,14.3))[1:]
    beta=math.acos(.7)
    for i in range(1,25):
        t=math.pi/2-beta*i/24
        right.append((25.+3*math.cos(t),44.5,11.3+3*math.sin(t)))
    cx=25.+6*math.sin(beta)
    for i in range(1,25):
        t=-math.pi/2-beta+beta*i/24
        right.append((cx+3*math.cos(t),44.5,15.5+3*math.sin(t)))
    right+=line((cx,44.5,12.5),(32.725,44.5,12.5))[1:]
    return left+free[1:]+right[1:]

def sections(pts):
    out=[]
    for i,p in enumerate(pts):
        # Tangent-bisecting normals avoid steps at sampling boundaries.
        a=pts[max(0,i-1)];b=pts[min(len(pts)-1,i+1)]
        dx,dz=b[0]-a[0],b[2]-a[2];d=math.hypot(dx,dz)
        nx,nz=-dz/d,dx/d
        out.append([(p[0]+s*THICKNESS/2*nx,p[1]+w*WIDTH/2,p[2]+s*THICKNESS/2*nz) for s,w in ((-1,-1),(-1,1),(1,1),(1,-1))])
    return out

def mesh(angle):
    rings=sections(points(angle));vertices=[p for ring in rings for p in ring];triangles=[]
    for i in range(len(rings)-1):
        for j in range(4):
            a=i*4+j;b=i*4+(j+1)%4;c=b+4;d=a+4
            triangles.extend([(a,b,c),(a,c,d)])
    triangles.extend([(0,2,1),(0,3,2)])
    n=len(vertices)-4;triangles.extend([(n,n+1,n+2),(n,n+2,n+3)])
    return {'vertices':vertices,'triangles':triangles}

def solid(angle):
    import FreeCAD as App,Part
    wires=[Part.makePolygon([App.Vector(*p) for p in ring+[ring[0]]]) for ring in sections(points(angle))]
    return Part.makeLoft(wires,True,True)
