"""Audit the approved functional geometry against the pre-C CAD."""
from pathlib import Path
import argparse,json,hashlib
parser=argparse.ArgumentParser(description="Compare saved C CAD to an explicit upstream pre-C baseline")
parser.add_argument("--baseline-cad",type=Path,required=True)
parser.add_argument("--baseline-commit",required=True)
args=parser.parse_args()
import FreeCAD as A,Part
out=Path(__file__).resolve().parent/'generated'
a=A.openDocument(str(args.baseline_cad));b=A.openDocument(str(out/'folding-unibody-rev-a.FCStd'))
report={'baseline_commit':args.baseline_commit,'baseline_CAD_sha256':hashlib.sha256(args.baseline_cad.read_bytes()).hexdigest(),'checker_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'CAD_sha256':hashlib.sha256((out/'folding-unibody-rev-a.FCStd').read_bytes()).hexdigest(),'unchanged_reference_difference_mm3':{},'unchanged_part_difference_mm3':{},'protected_interfaces_difference_mm3':{}}
def delta(x,y):return x.cut(y).Volume+y.cut(x).Volume
for o in a.Objects:
 if o.Name.startswith('Reference_') and o.Name!='Reference_Power_wire_internal_reserved' and b.getObject(o.Name):
  d=delta(o.Shape,b.getObject(o.Name).Shape);assert d<.001,(o.Name,d)
  report['unchanged_reference_difference_mm3'][o.Name]=d
for n in ('left_plate','latch_slider','battery_cap'):
 d=delta(a.getObject('Print_'+n).Shape,b.getObject('Print_'+n).Shape);assert d<.001,(n,d)
 report['unchanged_part_difference_mm3'][n]=d
for n in ('left_tray','right_tray'):
 for y in (-3,70):
  mask=Part.makeBox(34,9,9.7,A.Vector(-17,y,10))
  d=delta(a.getObject('Print_'+n).Shape.common(mask),b.getObject('Print_'+n).Shape.common(mask));assert d<.001,(n,y,d)
  report['protected_interfaces_difference_mm3'][n+str(y)]=d
for n,z in [('latch_cap',15.49),('power_lid',15.64),('power_rear_lid',15.64)]:
 mask=Part.makeBox(100,100,z+10,A.Vector(-50,-10,-10))
 d=delta(a.getObject('Print_'+n).Shape.common(mask),b.getObject('Print_'+n).Shape.common(mask));assert d<.001,(n,d)
 report['protected_interfaces_difference_mm3'][n]=d
(out/'mechanical-preservation-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('MECHANICAL_INTERFACES_PRESERVED',len(report['unchanged_reference_difference_mm3']))
