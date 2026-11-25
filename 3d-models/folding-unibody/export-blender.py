#!/usr/bin/env python3
"""Build a self-contained Blender review file from the existing CAD exports.

Run using Blender --background --factory-startup --python this_file.
One Blender unit is one metre; source CAD coordinates are millimetres.
"""
from pathlib import Path
import hashlib
import json
import math
import struct
import os

import bpy
from mathutils import Vector

HERE = Path(os.environ.get('FOLD_MODEL_DIR', str(Path(__file__).resolve().parent)))
OUT = HERE / 'generated'
CHECK = json.loads((OUT / 'validation.json').read_text())
PREVIEW = json.loads((OUT / 'preview-mesh.json').read_text())
MM = .001
PRINTS = list(CHECK['parts'])
INPUTS = [Path(__file__).resolve(), OUT / 'preview-mesh.json', OUT / 'validation.json'] + [OUT / (n + '.stl') for n in PRINTS]

bpy.ops.wm.read_factory_settings(use_empty=False)
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
bpy.context.preferences.filepaths.save_version = 0


def material(name, color, metallic=0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = .32 if metallic else .48
    return m


MAT = {
    'shell': material('Warm grey / printed tray', (.68, .69, .65)),
    'plate': material('Ivory / printed plate', (.84, .84, .79)),
    'key': material('Ivory keycap envelope', (.92, .91, .86)),
    'accent': material('Charcoal accent key', (.055, .075, .09)),
    'metal': material('Metal pins, magnets and ball', (.57, .61, .65), .8),
    'cell': material('Battery wrapper / illustrative', (.88, .88, .82)),
    'red': material('Battery band / illustrative', (.55, .035, .025)),
    'pcb': material('PCB reference', (.035, .20, .095)),
    'black': material('Connector envelope', (.025, .03, .035)),
    'ribbon': material('Grey FFSD ribbon',(.30,.32,.34)),
    'reference': material('Assumed component envelope', (.25, .40, .48)),
}


def welded_mesh(name, vertices, triangles):
    # Weld the STL triangle soup without changing the CAD boundary.
    unique, remap, lookup = [], [], {}
    for v in vertices:
        key = tuple(round(float(x), 5) for x in v)
        if key not in lookup:
            lookup[key] = len(unique)
            unique.append(tuple(float(x) * MM for x in v))
        remap.append(lookup[key])
    faces = [tuple(remap[i] for i in tri) for tri in triangles]
    faces = [f for f in faces if len(set(f)) == 3]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(unique, [], faces)
    mesh.update()
    assert not mesh.validate(), ('Invalid exported mesh', name)
    return mesh


MESH = {}
for name in PRINTS:
    raw = (OUT / (name + '.stl')).read_bytes()
    count = struct.unpack_from('<I', raw, 80)[0]
    vertices = []
    for i in range(count):
        record = struct.unpack_from('<12fH', raw, 84 + i * 50)
        vertices.extend([record[3:6], record[6:9], record[9:12]])
    MESH[name] = welded_mesh(name, vertices, [range(i * 3, i * 3 + 3) for i in range(count)])

for name, item in PREVIEW.items():
    if name not in MESH:
        MESH[name] = welded_mesh(name, item['vertices'], item['triangles'])


def key_meshes(name):
    # Keep individual keys selectable. Connected components preserve the
    # conservative CAD envelopes, including the two depressed closed keys.
    item = PREVIEW[name]
    graph = {i: set() for i in range(len(item['vertices']))}
    for tri in item['triangles']:
        for i in tri:
            graph[i].update(tri)
    result, seen = [], set()
    for start in graph:
        if start in seen:
            continue
        todo, group = [start], set()
        while todo:
            i = todo.pop()
            if i in group:
                continue
            group.add(i)
            todo.extend(graph[i] - group)
        seen.update(group)
        ids = sorted(group)
        remap = {old: new for new, old in enumerate(ids)}
        verts = [item['vertices'][i] for i in ids]
        tris = [[remap[i] for i in t] for t in item['triangles'] if t[0] in group]
        center = [sum(v[j] for v in verts) / len(verts) for j in range(3)]
        result.append((welded_mesh(name + '_' + str(len(result) + 1), verts, tris), center))
    return result


KEYS = {name: key_meshes(name) for name in ('Keys_left', 'Keys_left_closed', 'Keys_right')}
assert len(KEYS['Keys_left']) == CHECK['key_counts']['left']
assert len(KEYS['Keys_right']) == CHECK['key_counts']['right']


def collection(scene, name, hidden=False, reference=False):
    c = bpy.data.collections.new(scene.name + ' / ' + name)
    scene.collection.children.link(c)
    c.hide_viewport = hidden
    c.hide_render = hidden or reference
    return c


def object_for(c, name, mesh, mat, folded=False, smooth=False):
    obj = bpy.data.objects.new(name, mesh)
    c.objects.link(obj)
    if not mesh.materials:
        mesh.materials.append(mat)
    obj.color = mat.diffuse_color
    if folded:
        # Store explicit local channels, so the fold survives save/reload
        # independently of the evaluated world-matrix cache of each scene.
        obj.rotation_euler = (0, math.pi, 0)
        obj.location = (0, 0, 2 * CHECK['axis_z_mm'] * MM)
    if smooth:
        for p in mesh.polygons:
            p.use_smooth = True
    return obj


def bounds(objects):
    # Review objects have no parents or constraints. Use their stored local
    # transform, not an inactive scene's unevaluated world-matrix cache.
    points = [o.matrix_basis @ Vector(v) for o in objects for v in o.bound_box]
    low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    return low, high


def camera_for(scene, c, name, direction, objects):
    low, high = bounds(objects)
    target = (low + high) / 2
    data = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name, data)
    c.objects.link(obj)
    obj.location = target + Vector(direction).normalized() * .8
    obj.rotation_euler = (target - obj.location).to_track_quat('-Z', 'Y').to_euler()
    data.type = 'ORTHO'
    data.sensor_fit = 'HORIZONTAL'
    rotation = obj.rotation_euler.to_matrix().transposed()
    points = [rotation @ (o.matrix_basis @ Vector(v) - target) for o in objects for v in o.bound_box]
    width = max(p.x for p in points) - min(p.x for p in points)
    height = max(p.y for p in points) - min(p.y for p in points)
    aspect = scene.render.resolution_x / scene.render.resolution_y
    data.ortho_scale = max(width, height * aspect) * 1.16
    data.clip_start = .001
    data.clip_end = 10
    return obj


def build_scene(name, closed=False, service=False, battery_service=False):
    scene = bpy.data.scenes.new(name)
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.length_unit = 'MILLIMETERS'
    scene.unit_settings.scale_length = 1
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 760
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.world = bpy.data.worlds.new(name + ' World')
    scene.world.color = (.12, .14, .16)
    sh = scene.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'MATERIAL'
    sh.show_shadows = True
    sh.show_cavity = True
    sh.cavity_type = 'BOTH'
    sh.background_type = 'WORLD'
    parts = collection(scene, '01 Printed parts')
    covers = collection(scene, '02 Bottom covers (toggle to inspect)', hidden=service)
    lid = collection(scene, '03 Power lid (toggle to inspect)')
    battery_lid = collection(scene, '04 Battery cover (remove to replace cell)', hidden=battery_service)
    keys = collection(scene, '05 Keycap envelopes')
    refs = collection(scene, '05 PCB and connector references')
    visible = collection(scene, '06 Battery, pins, magnets and ball')
    assumed = collection(scene, '07 Assumed envelopes (hidden)', hidden=True, reference=True)
    cameras = collection(scene, '08 View cameras', hidden=True)
    cameras.hide_render = False
    model = []
    for part in PRINTS:
        c = covers if 'cable_cover' in part else lid if part in ('power_lid','power_rear_lid') else battery_lid if part == 'battery_cap' else parts
        mat = MAT['plate'] if part.endswith('plate') or part in ('power_lid','power_rear_lid', 'battery_cap', 'latch_cap') else MAT['black'] if part == 'latch_slider' else MAT['shell']
        obj = object_for(c, name + ' / ' + part, MESH[part], mat, closed and part.startswith('left_'))
        obj['CAD_part'] = part
        if not (service and 'cable_cover' in part) and not (battery_service and part == 'battery_cap'):
            model.append(obj)
    for side in ('left', 'right'):
        source = 'Keys_left_closed' if side == 'left' and closed else 'Keys_' + side
        for i, (mesh, center) in enumerate(KEYS[source]):
            cx, cy = (-36.05, 8.5) if side == 'left' else (53.05, 12.5)
            accent = abs(center[0] - cx) < .2 and abs(center[1] - cy) < .2
            obj = object_for(keys, name + ' / ' + side + '_key_' + str(i + 1).zfill(2), mesh, MAT['accent'] if accent else MAT['key'], closed and side == 'left')
            obj['purpose'] = 'Keycap clearance envelope, not printable keycap geometry'
            model.append(obj)
        for suffix in ('PCB_reference', 'SplitHeader_reference'):
            source = side + '_' + suffix
            model.append(object_for(refs, name + ' / ' + source, MESH[source], MAT['pcb'] if suffix == 'PCB_reference' else MAT['black'], closed and side == 'left'))
    model.append(object_for(refs, name + ' / right_XIAO_reference', MESH['right_XIAO_reference'], MAT['plate']))
    for source in ('AAA_cell_reference', 'Hinge_hardware_front', 'Hinge_hardware_rear', 'Closure_magnets_left', 'Closure_magnets_right', 'Trackball_visual_only', 'AAA_holder_visual_only'):
        obj = object_for(visible, name + ' / ' + source, MESH[source], MAT['cell'] if source == 'AAA_cell_reference' else MAT['black'] if source == 'AAA_holder_visual_only' else MAT['metal'], closed and source.endswith('_left'), source == 'Trackball_visual_only')
        if source == 'AAA_holder_visual_only':
            obj['purpose'] = 'Holder resin ends trimmed to Z13 mm in this assumed profile; preserve real metal contacts and anchors'
        if source == 'AAA_cell_reference' and len(obj.data.materials) == 1:
            obj.data.materials.append(MAT['red'])
            min_y = min(v.co.y for v in obj.data.vertices)
            for poly in obj.data.polygons:
                y = sum(obj.data.vertices[i].co.y for i in poly.vertices) / len(poly.vertices)
                poly.material_index = 1 if y < min_y + .00675 else 0
        model.append(obj)
    for source in ('AAA_holder_assumed', 'AAA_contact_keepout_assumed', 'Power_wire_internal_reserved', 'Boost_module_assumed', 'PTC_assumed', 'Diode_assumed', 'Switch_assumed', 'Switch_knob_assumed', 'Power_disconnect_reserved', 'Split_cable_storage_reserved', 'Trackball_reserved_envelope', 'Latch_spring_envelope'):
        if source not in MESH:
            continue
        obj = object_for(assumed, name + ' / ' + source, MESH[source], MAT['reference'])
        obj.display_type = 'WIRE'
        obj['purpose'] = 'Assumed envelope, not manufacturing geometry'
    for source in ('Power_wire_GND_nominal', 'Power_wire_VBUS_nominal'):
        if source in MESH:
            model.append(object_for(visible, name+' / '+source, MESH[source], MAT['black'] if 'GND' in source else MAT['red']))
    for source in ('left_socket_assumed','right_socket_assumed'):
        if source in MESH:
            model.append(object_for(refs,name+' / '+source,MESH[source],MAT['black'],closed and source.startswith('left_')))
    source='Cable_ribbon_closed' if closed else 'Cable_ribbon_open'
    if source in MESH:
        obj=object_for(visible,name+' / Interconnect ribbon',MESH[source],MAT['ribbon'])
        obj['purpose']='Continuous nominal-length ribbon envelope; fatigue and physical connector stack unverified'
        model.append(obj)
    bpy.context.window.scene = scene
    bpy.context.view_layer.update()
    directions = {'Top': (0, 0, 1), 'Bottom': (0, 0, -1), 'Front': (0, -1, 0),
                  'Back': (0, 1, 0), 'Left': (-1, 0, 0), 'Right': (1, 0, 0), 'Isometric': (.28, -.55, .8)}
    cams = {n: camera_for(scene, cameras, name + ' / ' + n, d, model) for n, d in directions.items()}
    scene.camera = cams['Bottom' if service else 'Isometric']
    scene['CAD_dimensions_mm'] = CHECK['closed_size_mm'] if closed else CHECK['open_size_mm']
    scene['Note'] = 'Rigid CAD review. Cable motion, printed strength and pin retention remain unverified.'
    return scene, model, cams


open_scene, open_objects, open_cams = build_scene('01_Open')
closed_scene, closed_objects, closed_cams = build_scene('02_Folded', closed=True)
service_scene, service_objects, service_cams = build_scene('03_Underside_covers_hidden', service=True)
battery_scene, battery_objects, battery_cams = build_scene('04_Battery_cover_removed', battery_service=True)
default = bpy.data.scenes.get('Scene')
if default:
    bpy.data.scenes.remove(default)
bpy.context.window.scene = open_scene

# Save a useful initial viewport, with cameras and assumed boxes hidden.
low, high = bounds(open_objects)
target = (low + high) / 2
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            space = area.spaces.active
            space.clip_start = .0001
            space.clip_end = 100
            space.shading.type = 'SOLID'
            space.shading.color_type = 'MATERIAL'
            space.shading.show_cavity = True
            space.shading.background_type = 'WORLD'
            space.overlay.show_floor = False
            space.overlay.show_axis_x = False
            space.overlay.show_axis_y = False
            space.overlay.show_extras = False
            space.region_3d.view_location = target
            space.region_3d.view_distance = .43
            space.region_3d.view_rotation = Vector((.28, -.55, .8)).to_track_quat('Z', 'Y')
            space.region_3d.view_perspective = 'ORTHO'

readme = bpy.data.texts.new('START_HERE / はじめに')
readme.write('''komoro folding keyboard — CAD review model

Scene selector:
01_Open: assembled keyboard.
02_Folded: inward folded, including CAD-required key depression.
03_Underside_covers_hidden: bottom covers hidden to inspect wiring channels.
04_Battery_cover_removed: independent cover hidden for battery replacement.

Use the middle mouse button to orbit. The viewport axis gizmo selects views.
Numpad 7 / Ctrl+7: top / bottom; 1 / Ctrl+1: front / back; 3 / Ctrl+3: right / left.
Collections separate printed parts, covers, keys and assumed reference envelopes.
One Blender unit = 1 metre. Display units are millimetres.

Printed parts are imported from the validated STL exports without changing
their shape. Keycaps, electronics and ball are CAD envelopes / illustrations.
The cap uses a real concentric cylindrical hollow: inner R5.8 / outer R7 mm.
Holder resin ends are assumed trimmed to 9.5 mm above the holder bottom.
Real metal contacts and their anchors must be retained; fit is unmeasured.
This file does not animate or validate cable motion or mechanical strength.
The GLB contains the open scene only; all four states are in this .blend.
''')

report = {'blender_version': bpy.app.version_string, 'units': 'metres, displayed as millimetres',
          'source_sha256': {os.path.relpath(p,HERE): hashlib.sha256(p.read_bytes()).hexdigest() for p in INPUTS},
          'scenes': {}}
for scene, objects, key in ((open_scene, open_objects, 'open_size_mm'), (closed_scene, closed_objects, 'closed_size_mm')):
    lo, hi = bounds(objects)
    dimensions = [(hi[i] - lo[i]) / MM for i in range(3)]
    # OCC's transformed BRep bounds are conservative: the closed CAD box
    # reports 166.8 mm while its untouched STL vertices span 166.6 mm.
    assert all(-.05 < expected - actual < .35 for actual, expected in zip(dimensions, CHECK[key])), (scene.name, dimensions, CHECK[key])
    report['scenes'][scene.name] = {'mesh_objects': len(objects), 'mesh_dimensions_mm': dimensions,
                                  'CAD_BRep_bounds_mm': CHECK[key], 'within_CAD_BRep_bounds': True}

bpy.ops.object.select_all(action='DESELECT')
for obj in open_objects:
    obj.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(OUT / 'komoro-folding-open.glb'), export_format='GLB', use_selection=True)
bpy.ops.object.select_all(action='DESELECT')
bpy.context.view_layer.objects.active = None
# Restore display units after scene creation and glTF export. Changing the
# unit system can reset the active scene's length unit, so set only length.
for scene in bpy.data.scenes:
    scene.unit_settings.length_unit = 'MILLIMETERS'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'komoro-folding-review.blend'), compress=True)

# A distinct filename avoids confusion with an already-open older review.
bpy.context.window.scene = battery_scene
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'komoro-folding-battery-access.blend'), compress=True)
bpy.context.window.scene = open_scene
if 'Cable_ribbon_open' in MESH:
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'komoro-folding-101mm.blend'),compress=True)
else:
    for alias in ('raised-battery', 'arched-battery', 'conformal-battery',
                  'trimmed-holder', 'end-rims', 'hidden-power'):
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT / ('komoro-folding-'+alias+'.blend')),compress=True)

# Orthographic preview renders also verify the saved meshes look as expected.
preview_dir = OUT / 'blender-views'
preview_dir.mkdir(exist_ok=True)
for scene, camera, label in [(open_scene, open_cams[n], n) for n in ('Isometric', 'Top', 'Bottom', 'Front', 'Back', 'Left', 'Right')] + [(closed_scene, closed_cams['Isometric'], 'Folded'), (service_scene, service_cams['Bottom'], 'Service'), (battery_scene, battery_cams['Isometric'], 'Battery_open')]:
    scene.camera = camera
    scene.render.filepath = str(preview_dir / (label + '.png'))
    bpy.ops.render.render(write_still=True, scene=scene.name)
report['preview_directory'] = 'blender-views'
report['native_file'] = 'komoro-folding-review.blend'
report['portable_file'] = 'komoro-folding-open.glb'
(OUT / 'blender-validation.json').write_text(json.dumps(report, indent=2) + '\n')
print('BLENDER_EXPORT_COMPLETE', OUT / 'komoro-folding-review.blend')
