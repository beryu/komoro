#!/usr/bin/env python3
"""Render the saved review model with translucent cases to expose routing.
Run in Blender. Does not modify the source .blend.
"""
from pathlib import Path
import bpy,json,hashlib
from mathutils import Vector
HERE=Path(__file__).resolve().parent;OUT=HERE/'generated'
source=OUT/'komoro-folding-101mm.blend'
bpy.ops.wm.open_mainfile(filepath=str(source))
ghost=bpy.data.materials.new('Inspection only / translucent case');ghost.use_nodes=True
nodes=ghost.node_tree.nodes;nodes.clear()
out=nodes.new('ShaderNodeOutputMaterial');mix=nodes.new('ShaderNodeMixShader');mix.inputs[0].default_value=.96
solid=nodes.new('ShaderNodeBsdfPrincipled');solid.inputs['Base Color'].default_value=(.7,.75,.72,1)
transparent=nodes.new('ShaderNodeBsdfTransparent')
ghost.node_tree.links.new(solid.outputs[0],mix.inputs[1]);ghost.node_tree.links.new(transparent.outputs[0],mix.inputs[2]);ghost.node_tree.links.new(mix.outputs[0],out.inputs[0])
ribbon=bpy.data.materials.new('Inspection only / orange interconnect');ribbon.use_nodes=True
ribbon.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.65,.18,.025,1)
ribbon.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.5
report={'source':source.name,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'note':'Cases/cell transparent and keycaps hidden for inspection only; cable is the same geometric envelope as the native model.','images':{}}
for name,label,cx,cz in [('01_Open','cable-open-render',0,.014),('02_Folded','cable-folded-render',.014,.018)]:
 scene=bpy.data.scenes[name];bpy.context.window.scene=scene
 for obj in scene.objects:
  if '_key_' in obj.name or 'cable_cover' in obj.name:obj.hide_render=True
  if 'CAD_part' in obj and obj.get('CAD_part') not in ('latch_slider',):
   obj.data=obj.data.copy();obj.data.materials.clear();obj.data.materials.append(ghost)
  if any(n in obj.name for n in ('AAA_cell_reference','AAA_holder_visual_only')) or (name=='02_Folded' and 'PCB_reference' in obj.name):
   obj.data=obj.data.copy();obj.data.materials.clear();obj.data.materials.append(ghost)
  if 'Interconnect ribbon' in obj.name:
   obj.data=obj.data.copy();obj.data.materials.clear();obj.data.materials.append(ribbon)
 scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=64;scene.cycles.use_denoising=True;scene.cycles.transparent_max_bounces=64;scene.cycles.max_bounces=32
 scene.render.resolution_x=1400;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
 scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
 scene.view_settings.view_transform='AgX';scene.view_settings.exposure=-.5
 scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.78,.82,.86,1);scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.35
 target=Vector((cx,.0445,cz))
 cam=scene.camera;cam.location=target+Vector((.13,-.35,.8) if name=='01_Open' else (.4,-.7,.55)).normalized()*.5;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.103
 for n,pos,power in [('Key',(.05,-.2,.42),1.5),('Fill',(-.27,.03,.28),.8),('Rim',(.19,.28,.34),1.)]:
  data=bpy.data.lights.new(name+n,'AREA');data.energy=power;data.shape='DISK';data.size=.3
  light=bpy.data.objects.new(data.name,data);scene.collection.objects.link(light);light.location=pos;light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
 scene.render.filepath=str(OUT/(label+'.png'));bpy.ops.render.render(write_still=True,scene=name)
 report['images'][label]=hashlib.sha256((OUT/(label+'.png')).read_bytes()).hexdigest()
(OUT/'cable-render-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('CABLE_RENDERS_COMPLETE')
