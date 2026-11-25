"""Recompute nominal FFSD length and sampled nonlocal self-clearance."""
from pathlib import Path
import hashlib,json,runpy
import numpy as np
HERE=Path(__file__).resolve().parent;OUT=HERE/'generated'
c=runpy.run_path(str(HERE/'cable.py'))
paths=json.loads((OUT/'cable-paths.json').read_text())
report={'scope':'37 geometric poses, nominal assembly length; sampled self-clearance for centreline arclength separations >=4 mm; not continuous elastic analysis',
        'sources_sha256':{str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),HERE/'cable.py',HERE/'solve-cable.py',OUT/'cable-paths.json')},'poses':[]}
for angle in range(0,181,5):
 p=np.asarray(c['points'](angle));s=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
 length=s[-1]+6.1
 distances=np.linalg.norm(p[:,None,:]-p[None,:,:],axis=2)
 distances[np.abs(s[:,None]-s[None,:])<4.]=np.inf
 gap=float(distances.min()-c['THICKNESS'])
 radius=paths[str(angle)]['radius']
 assert abs(length-101.6)<.01,(angle,length)
 assert gap>0 and radius>=2.999,(angle,gap,radius)
 report['poses'].append({'angle_deg':angle,'assembly_length_mm':float(length),'sampled_self_clearance_mm':gap,'minimum_free_radius_mm':radius})
(OUT/'cable-length-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('CABLE_LENGTH_VALID',min(r['sampled_self_clearance_mm'] for r in report['poses']))
