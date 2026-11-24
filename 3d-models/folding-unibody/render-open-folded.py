#!/usr/bin/env python3
"""Render open/folded CAD review scenes with the same studio lighting.

Run with Blender --background --factory-startup --python-exit-code 1.
The source .blend is never overwritten.
"""
from pathlib import Path
import hashlib,json,os
import bpy
from mathutils import Vector
HERE=Path(__file__).resolve().parent
OUT=Path(os.environ.get('FOLD_MODEL_DIR', str(HERE)))/'generated'
source=OUT/os.environ.get('FOLD_REVIEW_FILE','komoro-folding-hidden-power.blend')
bpy.ops.wm.open_mainfile(filepath=str(source))
report={'source':source.name,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'engine':'Cycles CPU','samples':48,'images':{}}
for scene_name,label in [('01_Open','open-render'),('02_Folded','folded-render')]:
    scene=bpy.data.scenes[scene_name]
    bpy.context.window.scene=scene
    bpy.context.view_layer.update()
    scene.render.engine='CYCLES'
    scene.cycles.device='CPU'
    scene.cycles.samples=48
    scene.cycles.use_denoising=True
    scene.cycles.adaptive_threshold=.03
    scene.render.resolution_x=1800
    scene.render.resolution_y=1140
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.render.film_transparent=False
    scene.render.image_settings.color_mode='RGB'
    scene.view_settings.view_transform='AgX'
    scene.view_settings.exposure=-.5
    scene.world.use_nodes=True
    bg=scene.world.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value=(.78,.82,.86,1)
    bg.inputs['Strength'].default_value=.25
    studio=bpy.data.collections.new(scene_name+' Render studio')
    scene.collection.children.link(studio)
    mat=bpy.data.materials.new(scene_name+' Ground material');mat.use_nodes=True
    bsdf=mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value=(.72,.75,.77,1)
    bsdf.inputs['Roughness'].default_value=.75
    mesh=bpy.data.meshes.new(scene_name+' Ground mesh')
    mesh.from_pydata([(-1,-1,-.0014),(1,-1,-.0014),(1,1,-.0014),(-1,1,-.0014)],[],[(0,1,2,3)])
    ground=bpy.data.objects.new(scene_name+' Ground',mesh);studio.objects.link(ground);mesh.materials.append(mat)
    for name,location,power,size in [('Key',(.05,-.20,.42),1.5,.32),('Fill',(-.27,.03,.28),.6,.30),('Rim',(.19,.28,.34),1.,.25)]:
        data=bpy.data.lights.new(scene_name+' '+name,'AREA');data.energy=power;data.shape='DISK';data.size=size
        light=bpy.data.objects.new(data.name,data);studio.objects.link(light);light.location=location
        light.rotation_euler=(Vector((0,.035,.01))-light.location).to_track_quat('-Z','Y').to_euler()
    scene.camera=next(o for o in scene.objects if o.type=='CAMERA' and o.name.endswith('/ Isometric'))
    # Native file has parentless review objects; preserve its fixed model
    # transforms and the individually fitted isometric cameras.
    assert len([o for o in scene.objects if 'CAD_part' in o])==len(json.loads((OUT/'validation.json').read_text())['parts'])
    scene.render.filepath=str(OUT/(label+'.png'))
    bpy.ops.render.render(write_still=True,scene=scene.name)
    report['images'][label]={'scene':scene_name,'width':1800,'height':1140,
        'sha256':hashlib.sha256((OUT/(label+'.png')).read_bytes()).hexdigest()}
(OUT/'open-folded-render.json').write_text(json.dumps(report,indent=2)+'\n')
print('OPEN_FOLDED_RENDERS_COMPLETE')
