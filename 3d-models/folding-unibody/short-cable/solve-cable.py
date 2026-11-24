from pathlib import Path
import numpy as np, math,json
HERE=Path(__file__).resolve().parent
from scipy.optimize import minimize
P1=np.array([0.,2.4]); Tf=np.array([1.,0.]);beta=math.acos(1-1.8/6)
EXTRA=1.8+6*(beta-math.sin(beta))
L=101.6-6.1-12.325-(10.425+math.pi*3+4.1+16.3)-EXTRA
T=np.linspace(0,1,121)[:,None]
def cubic(p):
 a,b,c,d=p;t=T
 q=(1-t)**3*a+3*(1-t)**2*t*b+3*(1-t)*t*t*c+t**3*d
 dq=3*((1-t)**2*(b-a)+2*(1-t)*t*(c-b)+t*t*(d-c))
 dd=6*((1-t)*(c-2*b+a)+t*(d-2*c+b))
 return q,dq,dd

def setup(angle, seed=None):
 t=math.radians(angle);start=np.array([-20*math.cos(t)-6*math.sin(t),18.5+20*math.sin(t)-6*math.cos(t)]);ts=np.array([math.cos(t),-math.sin(t)])
 def calc(v):
  m=v[:2];tm=np.array([np.cos(v[2]),np.sin(v[2])]);a,b,c,d=v[3:]
  q1,d1,dd1=cubic([start,start+a*ts,m-b*tm,m]);q2,d2,dd2=cubic([m,m+c*tm,P1-d*Tf,P1]);q=np.r_[q1,q2[1:]];dq=np.r_[d1,d2[1:]];dd=np.r_[dd1,dd2[1:]]
  ds=np.linalg.norm(np.diff(q,axis=0),axis=1);s=np.r_[0,np.cumsum(ds)];f=s/s[-1];y=np.full(len(f),44.5);xyz=np.c_[q[:,0],y,q[:,1]]
  leng=np.linalg.norm(np.diff(xyz,axis=0),axis=1).sum()
  curv=np.abs(dq[:,0]*dd[:,1]-dq[:,1]*dd[:,0])/np.maximum(np.linalg.norm(dq,axis=1),1e-8)**3
  return xyz,leng,curv
 def ine(v):
  q,l,k=calc(v);x=q[:,0];z=q[:,2]
  # Keep clear of battery and its cover, Z4.5..19 and X1..19.5.
  obs=np.maximum.reduce([.3-x,3.8-z,z-19.8])
  # Moving PCB inner edge: exclude its local X<-20.05 when below top.
  xr=x*math.cos(t)-(z-18.5)*math.sin(t);zr=18.5+x*math.sin(t)+(z-18.5)*math.cos(t)
  moving=np.maximum(xr+19.6,zr-6.8)
  # Reject a path that doubles back over itself, including near-cusps.
  ds=np.r_[0,np.cumsum(np.linalg.norm(np.diff(q,axis=0),axis=1))]
  ix=np.arange(0,len(q),4);qq=q[ix];ss=ds[ix]
  dd=np.linalg.norm(qq[:,None,:]-qq[None,:,:],axis=2)
  dd[np.abs(ss[:,None]-ss[None,:])<4]=100.
  return np.r_[1/3-k, z-.3,obs,moving,dd.min()-1.2,1e3 if angle!=0 else 21.1-z]
 best=None
 for guess in ([seed] if seed is not None else [])+[[ -8,16,-math.pi/2,8,8,8,8],[-8,22,-math.pi/2,8,8,8,8],[-10,12,-math.pi/2,15,12,12,8],[-10,20,-math.pi/2,10,10,10,10]]:
  res=minimize(lambda v:np.sum(calc(v)[2]**2)*.01+np.sum(v[3:]**2)*.00001,guess,method='SLSQP',constraints=[{'type':'eq','fun':lambda v:calc(v)[1]-L},{'type':'ineq','fun':ine}],bounds=[(-30,25),(0,50),(-8,8)]+[(.1,50)]*4,options={'maxiter':600,'ftol':1e-8})
  q,l,k=calc(res.x);score=max(abs(l-L),max(0,-ine(res.x).min()))
  if best is None or score<best[0]:best=(score,res,q,l,k)
  if score<1e-4:break
 return best
if __name__=='__main__':
 (HERE/'generated').mkdir(exist_ok=True)
 target=L
 seed=None
 # Continuation selects the simple loop branch, avoiding a folded-back
 # stationary point of the cubic. Every final pose is independently checked.
 for initial_length in (40.35095,40.4,40.45,40.5,40.55,40.6,target):
  L=initial_length
  err,res,q,l,k=setup(0,seed)
  assert err<.001,('initial path',initial_length,err)
  seed=res.x
 out={}
 for ang in range(0,181,5):
  err,res,q,l,k=setup(ang,seed)
  assert err<.001,(ang,err)
  seed=res.x
  out[str(ang)]={'points':q.tolist(),'length':l,'radius':1/k.max(),'error':err,'params':res.x.tolist()}
  print(ang,'length',l,'min radius',1/k.max(),flush=True)
 (HERE/'generated/cable-paths.json').write_text(json.dumps(out)+'\n')
