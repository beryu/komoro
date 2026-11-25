"""Audit the approved functional geometry against the pre-C CAD."""
from pathlib import Path
import argparse,json,hashlib,runpy
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
# Preserve the upstream USB-C access reservations as well as its XIAO body.
root=Path(__file__).resolve().parents[3]
lib=runpy.run_path(str(root/'3d-models/FreeCAD/generate-keyboard-case.py'),run_name='library')
data=lib['_board_data'](root/'pcb'/lib['PCB_FILENAMES']['right'])
xiao=next(f for f in data['footprints'] if 'XIAO-nRF52840-Plus' in f['name'])
usb_end=lib['XIAO_ASSEMBLY_BODY'][0]/2+lib['XIAO_ASSEMBLY_CENTER_OFFSET'][0]-lib['XIAO_USB_INWARD_OVERLAP']+lib['XIAO_USB_OPENING_LENGTH']
cx,cy=lib['_local_point'](xiao,(usb_end-lib['XIAO_USB_OPENING_LENGTH']/2,0))
top_z=lib['BOTTOM_THICKNESS']+lib['PCB_THICKNESS']+lib['TOP_PLATE_GAP']
opening=lib['_rotated_box'](lib['XIAO_USB_OPENING_LENGTH'],lib['XIAO_USB_OPENING_WIDTH'],cx,cy,xiao['cad_angle'],lib['BOTTOM_THICKNESS']+lib['PCB_THICKNESS']+lib['XIAO_USB_CENTER_HEIGHT']-lib['XIAO_USB_OPENING_HEIGHT']/2,lib['XIAO_USB_OPENING_HEIGHT'])
hood_top=top_z+lib['XIAO_USB_SHELL_HEIGHT_FROM_PADS']+lib['XIAO_USB_SEATING_CLEARANCE']+lib['TOP_THICKNESS']
w=lib['XIAO_USB_PLUG_NOTCH_WIDTH']/2
notch=lib['_local_profile_prism'](xiao,lib['XIAO_USB_PLUG_NOTCH_START_X'],usb_end,[(-w,top_z-.1),(w,top_z-.1),(w,hood_top+.1),(-w,hood_top+.1)])
report['USB_reservations']={}
for label,region in [('opening',opening),('full_height_plug_notch',notch)]:
 region=region.translated(A.Vector(20.05,6,0))
 row={}
 for n in ('right_tray','right_plate'):
  prior=a.getObject('Print_'+n).Shape.common(region).Volume
  now=b.getObject('Print_'+n).Shape.common(region).Volume
  assert now<=prior+.001,(label,n,'USB access reduced',prior,now)
  row[n]={'baseline_overlap_mm3':prior,'current_overlap_mm3':now}
 wire=b.getObject('Reference_Power_wire_internal_reserved').Shape
 assert wire.common(region).Volume<.001,(label,'wire blocks USB')
 row['wire_gap_mm']=wire.distToShape(region)[0]
 report['USB_reservations'][label]=row
(out/'mechanical-preservation-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('MECHANICAL_INTERFACES_PRESERVED',len(report['unchanged_reference_difference_mm3']))
