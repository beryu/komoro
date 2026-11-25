"""Reopen actual CAD: C feature absence, hardware interfaces and wire sweep."""
from pathlib import Path
import hashlib,json,runpy
import FreeCAD as App, Part, Mesh
HERE=Path(__file__).resolve().parent;OUT=HERE/'generated'
base=runpy.run_path(str(HERE.parent/'generate.py'),run_name='library')
c=runpy.run_path(str(HERE/'c-design.py'))
lib=runpy.run_path(str(HERE.parents[1]/'FreeCAD/generate-keyboard-case.py'),run_name='split_library')
doc=App.openDocument(str(OUT/'folding-unibody-rev-a.FCStd'))
p={o.Name[6:]:o.Shape for o in doc.Objects if o.Name.startswith('Print_')}
r={o.Name[10:]:o.Shape for o in doc.Objects if o.Name.startswith('Reference_')}
box,folded=base['box'],base['folded']
report={'CAD_sha256':hashlib.sha256((OUT/'folding-unibody-rev-a.FCStd').read_bytes()).hexdigest(),'checker_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'solids':{},'floor_pockets':{},'sweep':[]}
for n,s in p.items():
 assert s.isValid() and s.isClosed() and len(s.Solids)==1,n
 assert Mesh.Mesh(str(OUT/(n+'.stl'))).isSolid(),n
 report['solids'][n]={'valid_closed_single_solid':True,'closed_STL':True}
# Compare each reconstructed flat split floor only where those trays survive.
# The difference excludes mounting holes, USB and hardware recesses by design.
for side,offset in [('left',App.Vector(-148.55,0,0)),('right',App.Vector(20.05,6,0))]:
 d0=App.newDocument('Before');d1=App.newDocument('Flat')
 old,_=lib['_make_side'](d0,c['ROOT'],side)
 flat,_=lib['_make_side'](d1,c['ROOT'],side,legacy_bottom_features=False)
 fill=flat.Shape.cut(old.Shape).translated(offset)
 shave=old.Shape.cut(flat.Shape).translated(offset)
 if side=='right':
  clip=box(20.05,-20,-2,180,125,60);fill=fill.common(clip);shave=shave.common(clip)
 # New wire trench is the sole intentional exception to the flat floor.
 trench=Part.makeCompound([c['tube'](c['path'](coords),c['CHANNEL_RADIUS']) for coords in c['ROUTES']])
 missing=fill.cut(trench).cut(p[side+'_tray']).Volume
 remaining=shave.common(p[side+'_tray']).Volume
 assert missing<.001 and remaining<.001,(side,'legacy bottom',missing,remaining)
 report[side+'_legacy_bottom']={'missing_flat_fill_mm3':missing,'remaining_rib_mm3':remaining}
 for i,(px,py) in enumerate(lib['LEFT_MAGNET_POCKET_CENTERS']):
  x,y=(px-148.55,py) if side=='left' else (lib['MAGNET_MIRROR_X']-px+20.05,py+6)
  probe=Part.makeCylinder(lib['MAGNET_POCKET_DIAMETER']/2,lib['MAGNET_POCKET_DEPTH'],App.Vector(x,y,lib['BOTTOM_THICKNESS']-lib['MAGNET_POCKET_DEPTH'])).cut(trench)
  gap=probe.cut(p[side+'_tray']).Volume
  assert gap<.001,(side,'floor pocket',i,gap)
  report['floor_pockets'][side+str(i)]=gap
 App.closeDocument(d0.Name);App.closeDocument(d1.Name)
assert p['left_tray'].common(box(-28,0,-1.21,10,54,1.21)).Volume<.001
assert p['right_cable_cover'].cut(box(-16.01,13.79,-1.21,35.52,56.22,1.03)).Volume<.001
# Only two original power lids; no long upper or rear underside shroud.
assert set(p)=={'left_tray','left_plate','right_tray','right_plate','right_cable_cover','latch_cap','latch_slider','power_lid','power_rear_lid','battery_cap'}
wires=[r['Power_wire_GND_nominal'],r['Power_wire_VBUS_nominal']]
wire=Part.makeCompound(wires)
fixed_names=['right_PCB_reference','right_XIAO_reference','Keys_right','AAA_cell_reference','AAA_holder_assumed','AAA_contact_keepout_assumed','Hinge_hardware_front','Hinge_hardware_rear','Closure_magnets_right','Boost_module_assumed','PTC_assumed','Diode_assumed','Switch_assumed','Switch_knob_assumed','Power_disconnect_reserved','Trackball_reserved_envelope']
fixed=Part.makeCompound([r[n] for n in fixed_names]+[s for n,s in p.items() if not n.startswith('left_')])
assert wire.common(fixed).Volume<.001,'wire hits stationary parts'
report['fixed_clearances_mm']={n:wire.distToShape(r[n])[0] for n in fixed_names}
report['wire_surface_gap_mm']=wires[0].distToShape(wires[1])[0]
assert report['wire_surface_gap_mm']>.03
moving=Part.makeCompound([p['left_tray'],p['left_plate']]+[r[n] for n in ('left_PCB_reference','Keys_left','Closure_magnets_left')])
minimum=100
for angle in sorted(set(range(0,181,5))|{175+i*.5 for i in range(11)}):
 moved=folded(moving,angle)
 overlap=wire.common(moved).Volume
 assert overlap<.001,('wire fold collision',angle,overlap)
 gap=wire.distToShape(moved)[0];minimum=min(minimum,gap)
 report['sweep'].append({'angle_deg':angle,'overlap_mm3':overlap,'wire_gap_mm':gap})
report['minimum_moving_gap_mm']=minimum
# Lids retain open screw bores; these checks catch mesh taper bore loss.
for name,points,z in [('power_lid',[(-13.2,17),(-2.5,17)],14.8),('power_rear_lid',[(-13.2,56.5),(-2.5,65)],14.8),('latch_cap',[(2.5,12.3),(17,12.3)],14.)]:
 for x,y in points:
  bore=Part.makeCylinder(1.09,1.8,App.Vector(x,y,z))
  assert bore.common(p[name]).Volume<.001,(name,'screw bore lost')
# Assemble open wires before fitting the PCB/plate; do not thread soldered ends
# through closed bores. Only nominal wire bodies are claimed by this check.
report['assembly']='Lay loose wires with plate/PCB removed; solder/insulate at XIAO before closing cover; physical assembly and USB plug unverified'
report['limitations']=['nominal 1 mm OD only','no insulation compression or manufacturing tolerance','minimum bend is geometric, not wire supplier rating','no solder fillets, real USB plug, print strength or fatigue validation']
(OUT/'c-design-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('C_DESIGN_VALID',minimum,report['wire_surface_gap_mm'],flush=True)
