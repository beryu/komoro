from pathlib import Path
import runpy,json,hashlib
import FreeCAD as App,Part
HERE=Path(__file__).resolve().parent;OUT=HERE/'generated'
ns=runpy.run_path(str(HERE.parent/'generate.py'),run_name='library')
doc=App.openDocument(str(OUT/'folding-unibody-rev-a.FCStd'))
shape=lambda n:doc.getObject(n).Shape.copy()
hooks=ns['battery_cap']()[1].mirror(App.Vector(1.75,0,0),App.Vector(1,0,0)).translated(App.Vector(0,0,1))
cap=shape('Print_battery_cap').cut(hooks)
blockers=Part.makeCompound([o.Shape for o in doc.Objects if (o.Name.startswith('Print_') and o.Name!='Print_battery_cap') or o.Name in ('Reference_AAA_holder_assumed','Reference_AAA_cell_reference','Reference_AAA_contact_keepout_assumed','Reference_Power_wire_internal_reserved','Cable_ribbon_open')])
report={}
for lift in (0,.5,2,5,15,25):
 v=cap.translated(App.Vector(0,0,lift)).common(blockers).Volume
 assert v<.001,('battery cap lift obstructed',lift,v)
 report[str(lift)]=v
(OUT/'battery-service-validation.json').write_text(json.dumps({'CAD_sha256':hashlib.sha256((OUT/'folding-unibody-rev-a.FCStd').read_bytes()).hexdigest(),'scope':'Snap hooks released; assumed trimmed holder and fixed ribbon; physical snap force unverified','lift_overlap_mm3':report},indent=2)+'\n')
print('BATTERY_SERVICE_VALID',report)
