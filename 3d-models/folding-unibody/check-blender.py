#!/usr/bin/env python3
"""Reopen the native review model and independently reimport its GLB."""
from pathlib import Path
import json, math, hashlib
import bpy
from mathutils import Vector
out=Path(__file__).resolve().parent/'generated'
bpy.ops.wm.open_mainfile(filepath=str(out/'komoro-folding-review.blend'))
report=json.loads((out/'blender-validation.json').read_text())
part_count=len(json.loads((out/'validation.json').read_text())['parts'])
expected={'01_Open','02_Folded','03_Underside_covers_hidden','04_Battery_cover_removed'}
assert set(bpy.data.scenes.keys())==expected,list(bpy.data.scenes.keys())
assert bpy.context.window.scene.name=='01_Open'
for scene in bpy.data.scenes:
 bpy.context.window.scene=scene
 bpy.context.view_layer.update()
 assert scene.unit_settings.system=='METRIC' and scene.unit_settings.length_unit=='MILLIMETERS'
 parts=[o for o in scene.objects if 'CAD_part' in o]
 assert len(parts)==part_count,(scene.name,len(parts))
 assert len([o for o in scene.objects if '_key_' in o.name])==48
 covers=next(c for c in scene.collection.children if '02 Bottom covers' in c.name)
 assert covers.hide_viewport==(scene.name=='03_Underside_covers_hidden')
 battery_cover=next(c for c in scene.collection.children if '04 Battery cover' in c.name)
 assert battery_cover.hide_viewport==(scene.name=='04_Battery_cover_removed')
 if scene.name=='02_Folded':
  left=next(o for o in parts if o['CAD_part']=='left_tray')
  assert abs(left.location.z-.037)<1e-7
  assert abs(left.rotation_euler.y-math.pi)<1e-6
assert bpy.data.texts.get('START_HERE / はじめに')
assert not [i for i in bpy.data.images if i.source=='FILE' and not i.packed_file]
closed=bpy.data.scenes['02_Folded']
bpy.context.window.scene=closed
closed.frame_set(closed.frame_current)
closed.render.filepath=str(out/'blender-views/Folded.png')
bpy.ops.render.render(write_still=True,scene=closed.name)
report['validation_script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
report['native_reopen']={'file_sha256':hashlib.sha256((out/'komoro-folding-review.blend').read_bytes()).hexdigest(),'passed':True,'scenes':sorted(expected),'printed_parts_per_scene':part_count,'keys_per_scene':48,'external_images':False}
scene=bpy.data.scenes.new('GLB_IMPORT_CHECK')
bpy.context.window.scene=scene
bpy.ops.import_scene.gltf(filepath=str(out/'komoro-folding-open.glb'))
bpy.context.view_layer.update()
objects=[o for o in scene.objects if o.type=='MESH']
assert len(objects)==report['scenes']['01_Open']['mesh_objects'],len(objects)
points=[o.matrix_world@Vector(v) for o in objects for v in o.bound_box]
dims=[(max(p[i] for p in points)-min(p[i] for p in points))*1000 for i in range(3)]
expected_dims=report['scenes']['01_Open']['mesh_dimensions_mm']
assert all(abs(a-b)<.01 for a,b in zip(dims,expected_dims)),(dims,expected_dims)
report['GLB_reimport']={'file_sha256':hashlib.sha256((out/'komoro-folding-open.glb').read_bytes()).hexdigest(),'passed':True,'mesh_objects':len(objects),'dimensions_mm':dims}
bpy.ops.wm.open_mainfile(filepath=str(out/'komoro-folding-battery-access.blend'))
assert bpy.context.window.scene.name=='04_Battery_cover_removed'
cover=next(c for c in bpy.context.scene.collection.children if '04 Battery cover' in c.name)
assert cover.hide_viewport and cover.hide_render
assert any(o.get('CAD_part')=='battery_cap' for o in cover.objects)
report['battery_access_reopen']={'passed':True,'initial_scene':bpy.context.scene.name,'file_sha256':hashlib.sha256((out/'komoro-folding-battery-access.blend').read_bytes()).hexdigest()}
bpy.ops.wm.open_mainfile(filepath=str(out/'komoro-folding-end-rims.blend'))
assert bpy.context.scene.name=='01_Open'
parts={o['CAD_part']:o for o in bpy.context.scene.objects if 'CAD_part' in o}
heights={n:max(v.co.z for v in parts[n].data.vertices)*1000 for n in ('battery_cap','power_lid')}
assert abs(heights['battery_cap']-18.)<.001 and abs(heights['power_lid']-16.3)<.001,heights
curve_vertices=[v.co for v in parts['battery_cap'].data.vertices if .01731<v.co.y<.06469]
radial=[math.hypot(v.x*1000+6.5,v.z*1000-11.) for v in curve_vertices]
assert min(radial)>5.798 and sum(abs(r-5.8)<.003 for r in radial)>8, (min(radial),len(radial))
rim_heights={}
for side,x0,x1,expected in (('left',-16.01,-8.,19.),('right',6.,16.,18.)):
 region=[v.co.z*1000 for v in parts[side+'_tray'].data.vertices if x0<v.co.x*1000<x1 and .5<v.co.y*1000<3.5]
 assert region and abs(max(region)-expected)<.001,(side,max(region) if region else None)
 rim_heights[side]=max(region)
report['end_rims_reopen']={'passed':True,'crest_z_mm':rim_heights}
holder=next(o for o in bpy.context.scene.objects if o.name.endswith('/ AAA_holder_visual_only'))
holder_top=max(v.co.z for v in holder.data.vertices)*1000
assert abs(holder_top-13.)<.001 and holder.visible_get(),(holder_top,holder.visible_get())
report['trimmed_holder_reopen']={'passed':True,'holder_top_z_mm':holder_top,'holder_visible':True}
report['conformal_battery_reopen']={'passed':True,'top_z_mm':heights,'step_mm':heights['battery_cap']-heights['power_lid']}
(out/'blender-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('REOPEN_VERIFIED',json.dumps({'native':report['native_reopen'],'glb':report['GLB_reimport']}))
