#!/usr/bin/env python3
"""Reopen the delivered .blend and inspect its saved scenes and mesh edges."""
from pathlib import Path
import json,hashlib
import bpy
from mathutils import Vector
HERE=Path(__file__).resolve().parent;OUT=HERE/'generated'
path=OUT/'komoro-folding-101mm.blend'
bpy.ops.wm.open_mainfile(filepath=str(path))
check=json.loads((OUT/'validation.json').read_text())
report=json.loads((OUT/'blender-validation.json').read_text())
for name,sha in report['source_sha256'].items():
 assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==sha,('stale source',name)
rows={}
for name in ('01_Open','02_Folded','03_Underside_covers_hidden','04_Battery_cover_removed'):
 s=bpy.data.scenes[name];bpy.context.window.scene=s;bpy.context.view_layer.update()
 assert s.unit_settings.length_unit=='MILLIMETERS'
 assert len([o for o in s.objects if 'CAD_part' in o])==len(check['parts'])
 assert len([o for o in s.objects if '_key_' in o.name])==48
 cable=next(o for o in s.objects if 'Interconnect ribbon' in o.name)
 edges={}
 for p in cable.data.polygons:
  for key in p.edge_keys:edges[key]=edges.get(key,0)+1
 assert all(n==2 for n in edges.values()),('open ribbon mesh',name)
 assert sum(abs(v) for v in cable.rotation_euler)<1e-8,('double fold transform',name)
 assert len([o for o in s.objects if 'Power_wire_' in o.name and '_nominal' in o.name])==2
 for obj in [o for o in s.objects if 'CAD_part' in o]:
  counts={}
  for poly in obj.data.polygons:
   for edge in poly.edge_keys:counts[edge]=counts.get(edge,0)+1
  assert all(n==2 for n in counts.values()),('open print mesh',name,obj.name)
 rows[name]={'closed_print_meshes':True,'nominal_power_wires':2,'print_parts':len(check['parts']),'key_envelopes':48,'closed_ribbon_mesh':True}
result={'native_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source_hashes_match':True,'scenes':rows}
(OUT/'saved-blender-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print('SAVED_BLENDER_VALID',rows)
