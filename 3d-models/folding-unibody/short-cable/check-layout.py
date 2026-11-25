#!/usr/bin/env python3
"""Reopen saved CAD and check ribbon plus altered rigid parts through the fold."""
from pathlib import Path
import runpy,json,hashlib,math
import FreeCAD as App,Part
HERE=Path(__file__).resolve().parent;OUT=HERE/'generated'
ns=runpy.run_path(str(HERE.parent/'generate.py'),run_name='library')
folded,union=ns['folded'],ns['union']
cable=runpy.run_path(str(HERE/'cable.py'))
doc=App.openDocument(str(OUT/'folding-unibody-rev-a.FCStd'))
shape=lambda n:doc.getObject(n).Shape.copy()
parts={o.Name[6:]:o.Shape.copy() for o in doc.Objects if o.Name.startswith('Print_')}
refs={o.Name[10:]:o.Shape.copy() for o in doc.Objects if o.Name.startswith('Reference_')}
report={'CAD_sha256':hashlib.sha256((OUT/'folding-unibody-rev-a.FCStd').read_bytes()).hexdigest(),'sweep':[],'part_overlaps':{},'component_overlaps':{}}
for i,(n,s) in enumerate(parts.items()):
 for m,t in list(parts.items())[i+1:]:
  overlap=s.common(t).Volume
  assert overlap<.001,('print pair',n,m,overlap)
left=union([s for n,s in parts.items() if n.startswith('left_')])
right=union([s for n,s in parts.items() if not n.startswith('left_') and n!='latch_slider'])
for n in ('Boost_module_assumed','PTC_assumed','Diode_assumed','Switch_assumed','Switch_knob_assumed','Power_disconnect_reserved'):
 v=refs[n].common(right).Volume;report['component_overlaps'][n]=v
 assert v<.001,('power component blocked',n,v)
pw=refs['Power_wire_internal_reserved'].common(Part.makeCompound([right,refs['right_PCB_reference'],refs['right_XIAO_reference']])).Volume
assert pw<.001,('power route obstructed',pw)
report['power_route_overlap_mm3']=pw
fixed_components=Part.makeCompound([s for n,s in refs.items() if n in ('AAA_holder_assumed','AAA_cell_reference','right_PCB_reference','right_XIAO_reference','right_SplitHeader_reference','right_socket_assumed','Boost_module_assumed','PTC_assumed','Diode_assumed','Switch_assumed','Switch_knob_assumed','Power_disconnect_reserved','Power_wire_internal_reserved','Keys_right','Trackball_reserved_envelope')])
key_pieces=[s for n,s in parts.items() if not n.startswith('left_') and n!='latch_slider']+[s for n,s in refs.items() if n in ('AAA_holder_assumed','AAA_cell_reference','right_PCB_reference','right_XIAO_reference','right_SplitHeader_reference','right_socket_assumed','Boost_module_assumed','PTC_assumed','Diode_assumed','Switch_assumed','Switch_knob_assumed','Power_disconnect_reserved','Power_wire_internal_reserved','Keys_right','Trackball_reserved_envelope')]
def bb_overlap(a,b):
 return all(getattr(a,c+'Max')>=getattr(b,c+'Min') and getattr(b,c+'Max')>=getattr(a,c+'Min') for c in 'XYZ')
def blocked(k,angle):
 moved=folded(k,angle);possible=[s for s in key_pieces if bb_overlap(moved.BoundBox,s.BoundBox)]
 return bool(possible) and moved.common(Part.makeCompound(possible)).Volume>.001
# Bottom-cover fastener shafts must not cross either wiring envelope.
shafts=Part.makeCompound([Part.makeCylinder(1.05,4.,App.Vector(x,y,-1.2)) for x,y in ((-11,64),(12,64))])
assert shafts.common(refs['Power_wire_internal_reserved']).Volume<.001,'screw crosses power wire'
for angle in (0,180):
 assert shafts.common(cable['solid'](angle)).Volume<.001,'screw crosses ribbon'
report['bottom_screw_wire_overlap_mm3']=0.
leftkeys=list(refs['Keys_left'].Solids)
closedkeys=[];maximum=0
for angle in range(0,181,5):
 ribbon=cable['solid'](angle)
 blockers=Part.makeCompound([folded(left,angle),right,folded(refs['left_PCB_reference'],angle),fixed_components])
 # Socket bodies contain the mating endpoints. Ribbon ends exactly at
 # their exit faces; references intentionally include no strain relief.
 overlap=ribbon.common(blockers).Volume
 assert overlap<.001,('ribbon blocked',angle,overlap)
 rigid=folded(left,angle).common(Part.makeCompound([right,fixed_components])).Volume
 assert rigid<.001,('moving case collision',angle,rigid)
 presses=[]
 for k in leftkeys:
  shift=0
  if blocked(k,angle):
   for step in range(1,21):
    shift=step/10
    if not blocked(k.translated(App.Vector(0,0,-shift)),angle):break
   else:raise AssertionError(('key travel exceeds 2 mm',angle))
  presses.append(shift)
  if angle==180:closedkeys.append(k.translated(App.Vector(0,0,-shift)))
 maximum=max(maximum,max(presses))
 report['sweep'].append({'angle_deg':angle,'ribbon_overlap_mm3':overlap,'moving_case_overlap_mm3':rigid,'key_press_max_mm':max(presses)})
 print('SWEEP',angle,overlap,max(presses),flush=True)
# Save changed depressed keys as an unfurled local mesh, for the exporter.
preview=json.loads((OUT/'preview-mesh.json').read_text())
vs,ts=Part.makeCompound(closedkeys).tessellate(.08)
preview['Keys_left_closed']={'vertices':[[v.x,v.y,v.z] for v in vs],'triangles':[list(t) for t in ts]}
(OUT/'preview-mesh.json').write_text(json.dumps(preview,separators=(',',':')))
report['maximum_key_press_mm']=maximum
(OUT/'layout-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('LAYOUT_CHECK_COMPLETE',maximum)
