#!/usr/bin/env python3
"""101.6 mm cable layout study derived from the checked base CAD.
Run after solve-cable.py, with FreeCAD's Python. Never modifies the base CAD.
"""
from pathlib import Path
import runpy, json, math, hashlib
import FreeCAD as App
import Part, Mesh
HERE=Path(__file__).resolve().parent
BASE=HERE.parent
OUT=HERE/'generated'; OUT.mkdir(exist_ok=True)
ns=runpy.run_path(str(BASE/'generate.py'),run_name='geometry_library')
box,union,folded,V=(ns[n] for n in ('box','union','folded','V'))
old=App.openDocument(str(BASE/'generated/folding-unibody-rev-a.FCStd'))
shape=lambda n:old.getObject(n).Shape.copy()
oldcheck=json.loads((BASE/'generated/validation.json').read_text())
parts={n:shape('Print_'+n) for n in oldcheck['parts']}
refs={n[10:]:o.Shape.copy() for o in old.Objects if (n:=o.Name).startswith('Reference_') and hasattr(o,'Shape')}
# Coordinate reflection preserves the same body width, placing the cell on
# the right. Only the battery receives the +1 mm floor-height change.
def mirror(s):
    return s.mirror(V(1.75,0,0),V(1,0,0))
def battery(s):return mirror(s).translated(V(0,0,1))
# Align the two connectors in Y using the same unmodified PCBs.
# Shift the right PCB-shaped outer shell and plate 6 mm toward the rear.
outer_clip=box(20.05,-20,-2,180,125,60)
outer=parts['right_tray'].common(outer_clip).translated(V(0,6,0))
inner=parts['right_tray'].cut(outer_clip)
parts['right_tray']=union([inner,outer,box(18,4,0,8,78,3.5)])
parts['right_plate']=parts['right_plate'].translated(V(0,6,0))
for n in ('right_PCB_reference','right_SplitHeader_reference','right_XIAO_reference','Keys_right','Trackball_reserved_envelope','Trackball_visual_only'):
    if n in refs:refs[n]=refs[n].translated(V(0,6,0))
# Remove the old central service region while retaining hinge end lands,
# latch mechanism, PCB-shaped shells and the previously hidden power route.
parts['right_tray']=parts['right_tray'].cut(box(-16.01,13.8,-.01,35.52,56.2,25))
# Underfloor chamber: cable centre Z2.4; roof Z3..4.5, battery floor Z4.5.
base=box(-16,13.8,0,35.5,56.2,4.5)
chamber=box(-14,15,-.21,31.5,51,3.21)
base=base.cut(chamber)
# The open transverse flex well replaces an enclosing wall at the hinge.
well=box(-18.1,33.5,1.5,21.1,16.,45)
base=base.cut(well)
for y,h in ((14.,19.5),(49.5,20.5)):
    base=base.cut(box(-14.5,y,3.5,13.5,h,1.1))
# Front/rear power bays; no bridge across the flex well.
for y,h in ((14.,19.5),(49.5,20.5)):
    base=union([base,box(-16,y,4.5,1.5,h,10.3),box(-1,y,4.5,2,h,10.3)])
# Low removable battery cradle, translated and reflected from base design.
rails=union([box(-14.7,15.5,3.5,1.5,51,2.5),box(.2,15.5,3.5,1.,51,2.5),box(-13,14.5,3.5,13,1,2.5),box(-13,66.5,3.5,13,1,2.5)])
for y0,y1 in ns['BATTERY_CAP']['clip_intervals_y_mm']:
    rails=rails.cut(box(-14.71,y0-.2,4.,.81,y1-y0+.4,1.2))
base=union([base,battery(rails)])
parts['right_tray']=union([parts['right_tray'],base])
# Right lead drops around the unmodified PCB edge, then goes straight west
# below the battery; no 90-degree turn in the ribbon's own plane.
slot=box(16.,40.2,1.9,4.5,8.6,12.)
for p in ('right_tray','right_plate'):
    parts[p]=parts[p].cut(slot)
# Clear the cradle rail and stationary latch after the PCB shift.
parts['right_plate']=parts['right_plate'].cut(box(17.8,13.8,5.9,2.,54.4,4.5))
parts['right_plate']=parts['right_plate'].cut(box(17.8,3.8,5.9,2.2,9.9,8.4))
parts['right_plate']=parts['right_plate'].cut(box(17.8,69.8,5.9,.5,4.4,2.))
# A direct opening on the moving side, above the PCB's inner edge.
parts['left_plate']=parts['left_plate'].cut(box(-24,40.2,10.9,6.2,8.6,5.))
# Bottom plate with the existing screw points. No moving cable trapped here.
parts['right_cable_cover']=box(-16,13.8,-1.2,35.5,56.2,1.)
for x,y in ((-11,64),(12,64)):
    boss=Part.makeCylinder(2.5,3.5,V(x,y,0)).cut(Part.makeCylinder(.85,2.5,V(x,y,-.1)))
    parts['right_tray']=parts['right_tray'].fuse(boss)
    parts['right_cable_cover']=parts['right_cable_cover'].cut(Part.makeCylinder(1.1,1.2,V(x,y,-1.3)))
# The obsolete moving-side underfloor loop is now a solid tray floor.
parts['left_tray']=union([parts['left_tray'],box(-28,0,-1.2,10,54,4.7)])
parts.pop('left_cable_cover')
parts['left_plate']=parts['left_plate'].fuse(box(-20,40.5,6.1,2,8,4.8))
# Two separate lids are intentional: a connecting strap would obstruct flex.
parts['power_lid']=box(-16,14,14.8,17,19.5,1.5)
parts['power_rear_lid']=box(-16,49.5,14.8,17,20.5,1.5)
for name,yy in (('power_lid',17.),('power_rear_lid',65.)):
    for xx in (-13.2,-2.5):
        if name=='power_rear_lid' and xx==-13.2:yy=56.5
        else:yy=17. if name=='power_lid' else 65.
        boss=Part.makeCylinder(2.5,3.5,V(xx,yy,11.3)).cut(Part.makeCylinder(.85,3.6,V(xx,yy,11.2)))
        parts['right_tray']=parts['right_tray'].fuse(boss)
        parts[name]=parts[name].cut(Part.makeCylinder(1.1,1.7,V(xx,yy,14.7)))
parts['battery_cap']=battery(parts['battery_cap'])
# Open-bottom notch frees the fixed lead beneath the side rail. The upper
# 2.3 mm rail stays continuous and the cover can lift off without unplugging.
parts['battery_cap']=parts['battery_cap'].cut(box(18.2,40.2,10.8,2.3,8.6,2.9))
for n in ('AAA_holder_assumed','AAA_contact_keepout_assumed','AAA_cell_reference'):
    refs[n]=battery(refs[n])
refs['AAA_holder_visual_only']=refs['AAA_holder_assumed']
# Repack real power subassemblies into bays either side of the cable well.
for n,dy in [('Boost_module_assumed',-2),('PTC_assumed',8),('Diode_assumed',6.5),('Switch_assumed',0),('Switch_knob_assumed',0),('Power_disconnect_reserved',0)]:
    refs[n]=mirror(refs[n]).translated(V(0,dy,0))
for n in ('Boost_module_assumed','Power_disconnect_reserved'):
    refs[n]=refs[n].translated(V(-.8,0,0))
for n in ('Switch_assumed','Switch_knob_assumed'):
    refs[n]=refs[n].translated(V(-2.7,0,0))
refs['Switch_assumed']=box(-14,59.5,9,3.9,8.8,3.5)
refs['Switch_knob_assumed']=box(-18,61.9,10,4,4,2)
parts['right_tray']=parts['right_tray'].cut(box(-16.1,61.4,9.5,2.2,5,3))
# Rear power wiring is a new routing reservation, not the obsolete right bay.
refs.pop('Power_wire_internal_reserved',None)
refs.pop('Split_cable_storage_reserved',None)
# Two power leads stay beneath the rear floor and return around the new
# PCB rear edge. This remains a wire envelope, not a solder-joint model.
parts['right_plate']=parts['right_plate'].fuse(box(43.05,77.9,6.1,3.55,3.7,4.4))
power_void=union([box(-11.6,66.8,.1,3.,2.4,10.),box(-11.6,66.8,-.19,57.1,2.4,1.99),
 box(43.,66.8,-.19,2.8,14.7,1.99),box(43.,80.1,.1,2.8,1.4,8.5),box(43.,70.,6.8,2.8,11.5,2.2)])
for p in ('right_tray','right_plate'):
    parts[p]=parts[p].cut(power_void)
parts['right_cable_cover']=union([parts['right_cable_cover'],box(15,66.2,-1.2,31,15.6,1)])
for y in (72.,79.):
    boss=Part.makeCylinder(2.5,3.5,V(40,y,0)).cut(Part.makeCylinder(.85,2.5,V(40,y,-.1)))
    parts['right_tray']=parts['right_tray'].fuse(boss)
    parts['right_cable_cover']=parts['right_cable_cover'].cut(Part.makeCylinder(1.1,1.2,V(40,y,-1.3)))
refs['Power_wire_internal_reserved']=union([box(-11.1,67.0,.3,2.,2.,9.2),box(-11.1,67.0,.3,56.,2.,1.),
 box(43.4,67.0,.3,2.,14.,1.),box(43.4,80.2,.3,2.,.8,7.8),box(43.4,70.8,7.1,2.,10.2,1.)])

# Actual female body envelope, separate from the existing header references.
for side,cx,cy in (('left',-33.85,44.5),('right',34.25,44.5)):
    refs[side+'_socket_assumed']=box(cx-1.525,cy-5.905,8.12,3.05,11.81,5.08)
# Keep the base visualization references that have no native Reference_ object.
refs['Trackball_visual_only']=Part.makeSphere(9.525,V(77,13.5,11.3))
for n,o in [('Trackball_visual_only','Reference_Trackball_visual_only')]:
    if n not in refs and old.getObject(o):refs[n]=shape(o)

doc=App.newDocument('Folding101Layout')
check={'revision':'101.6 mm cable layout study / unprinted','axis_z_mm':18.5,'key_counts':oldcheck['key_counts'],'parts':{},
 'sources_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),BASE/'generated/folding-unibody-rev-a.FCStd')},
 'battery_service':{'cell_center_x_mm':10.,'cell_center_z_mm':12.,'cover_top_z_mm':19.},
 'right_PCB_translation_y_mm':6.,
 'unverified':['mated connector height','power wiring after rearrangement','ribbon strain and fatigue','printed fit']}
preview={}
def feature(n,s,color=(.8,.8,.77)):
    o=doc.addObject('Part::Feature',n);o.Shape=s
    if o.ViewObject:o.ViewObject.ShapeColor=color
    return o
def meshdata(s):
    vs,ts=s.tessellate(.08)
    return {'vertices':[[v.x,v.y,v.z] for v in vs],'triangles':[list(t) for t in ts]}
for n,s in parts.items():
    s=s.removeSplitter();parts[n]=s
    assert s.isValid() and len(s.Solids)==1,(n,'invalid/disconnected',len(s.Solids))
    o=feature('Print_'+n,s)
    m=Mesh.Mesh(s.tessellate(.08));m.write(str(OUT/(n+'.stl')))
    ns0=runpy.run_path(str(BASE.parent/'FreeCAD/generate-keyboard-case.py'),run_name='split_library') if n==next(iter(parts)) else ns0
    ns0['_close_stl_roundoff'](OUT/(n+'.stl'))
    assert Mesh.Mesh(str(OUT/(n+'.stl'))).isSolid(),n
    Part.export([o],str(OUT/(n+'.step')))
    bb=s.BoundBox;check['parts'][n]={'volume_mm3':s.Volume,'size_mm':[bb.XLength,bb.YLength,bb.ZLength],'valid_solid':True,'closed_STL':True}
    preview[n]=meshdata(s)
for n,s in refs.items():
    feature('Reference_'+n,s);preview[n]=meshdata(s)
for n in ('Keys_left_closed','Trackball_visual_only'):
    if n not in preview:preview[n]=json.loads((BASE/'generated/preview-mesh.json').read_text())[n]
# Mechanical changes must still pass the original sampled full opening arc.
left=union([parts[n] for n in ('left_tray','left_plate')])
right=union([s for n,s in parts.items() if not n.startswith('left_') and n!='latch_slider'])
check['sweep']=[]
for angle in sorted(set(range(0,181,5))|{175+i*.5 for i in range(11)}):
    overlap=folded(left,angle).common(right).Volume
    check['sweep'].append({'angle_deg':angle,'case_overlap_mm3':overlap})
    assert overlap<.001,('cases collide',angle,overlap)
for side in ('left','right'):
    own=union([s for n,s in parts.items() if n.startswith(side+'_')])
    assert own.common(refs[side+'_PCB_reference']).Volume<.001,(side,'PCB obstructed')
for n in ('AAA_holder_assumed','AAA_cell_reference','AAA_contact_keepout_assumed'):
    overlap=refs[n].common(right).Volume
    assert overlap<.001,(n,'battery blocked',overlap)
# Validate the actual, continuous ribbon, not disconnected lead boxes.
cable=runpy.run_path(str(HERE/'cable.py'))
check['interconnect']={'assembly_length_nominal_mm':101.6,'connector_body_length_total_mm':6.1,
 'ribbon_width_max_mm':cable['WIDTH'],'ribbon_thickness_max_mm':cable['THICKNESS'],
 'minimum_bend_radius_design_assumption_mm':3.,'mated_exit_z_assumption_mm':12.5,
 'length_tolerance_mm':3.175,'manufacturer_cycle_rating':'not established',
 'length_tolerance_fit':'nominal cable only; shorter/longer samples not yet simulated','sweep':[]}
for angle in (0,45,90,135,180):
    ribbon=cable['solid'](angle)
    assert ribbon.isValid() and len(ribbon.Solids)==1,('invalid ribbon',angle)
    moving=folded(left,angle)
    blockers=Part.makeCompound([moving,right,folded(refs['left_PCB_reference'],angle),refs['right_PCB_reference'],refs['AAA_cell_reference'],refs['AAA_holder_assumed']])
    overlap=ribbon.common(blockers).Volume
    check['interconnect']['sweep'].append({'angle_deg':angle,'case_PCB_cell_holder_overlap_mm3':overlap})
    print('CABLE_CHECK',angle,overlap,flush=True)
    assert overlap<.001,('Cable obstructed',angle,overlap)
for n,a in (('Cable_ribbon_open',0),('Cable_ribbon_closed',180)):
    feature(n,cable['solid'](a));preview[n]=cable['mesh'](a)
# CAD-only bounds include case/key/reference illustrations, not hidden reserves.
for closed in (False,True):
    ss=[folded(s,180) if closed and n.startswith('left_') else s for n,s in parts.items()]
    for n in ('Keys_left_closed' if closed else 'Keys_left','Keys_right','AAA_cell_reference','AAA_holder_visual_only','Trackball_visual_only'):
        if n in refs:ss.append(folded(refs[n],180) if closed and n=='Keys_left_closed' else refs[n])
    bb=Part.makeCompound(ss).BoundBox
    check['closed_size_mm' if closed else 'open_size_mm']=[bb.XLength,bb.YLength,bb.ZLength]
doc.recompute();doc.saveAs(str(OUT/'folding-unibody-rev-a.FCStd'))
(OUT/'validation.json').write_text(json.dumps(check,indent=2)+'\n')
(OUT/'preview-mesh.json').write_text(json.dumps(preview,separators=(',',':')))
print('SHORT_CABLE_LAYOUT_COMPLETE')
