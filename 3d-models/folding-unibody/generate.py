#!/usr/bin/env python3
"""Rev A inward folding enclosure. Run with FreeCAD's freecadcmd.

Only this directory is written. The split-case generator is a read-only
geometry library; PCB Edge.Cuts and footprints remain the source of truth.
"""
from pathlib import Path
import hashlib
import json
import math
import os
import runpy

import FreeCAD as App
import Part
import Mesh

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'generated'
V = App.Vector

# mm. Key height is user-measured; the other envelopes still need fit checks.
AXIS_Z = float(os.environ.get('FOLD_AXIS_Z_MM', '18.5'))
KEY_HEIGHT = float(os.environ.get('FOLD_KEY_HEIGHT_MM', '10.5'))  # user-measured above PCB top
TRACKBALL_TOP = float(os.environ.get('FOLD_TRACKBALL_TOP_MM', '21.3424'))
KEY_PRESS_LIMIT = float(os.environ.get('FOLD_KEY_PRESS_LIMIT_MM', '2.0'))
STOP_HEIGHT = 16.0
STOP_FINGER_THICKNESS = 4.0
CLOSURE_MAGNET = {
    'size_mm': [6., 2., 2.3], 'grade': 'N52', 'quantity': 4, 'pairs': 2,
    'magnetisation': 'through 2.3 mm thickness',
    'pocket_mm': [6.3, 2.3, 2.5], 'nominal_face_recess_mm': .1,
    'nominal_adhesive_bed_mm': .1,
    'source': 'https://www.neomag.jp/shop/magnets/category_list1.php?cat2_id=1&categorysDir=DESC&categorysOrder=Sorter6&shape_id=4',
    'published_steel_pull_kgf_reference_only': .55,
    'actual_closed_retention': 'unverified; steel pull is not the force between installed magnets',
}
BATTERY_WINDOW = {'width_mm': 10.5, 'length_mm': 43., 'corner_radius_mm': 1.,
                  'center_xy_mm': [-6.5, 35.5]}
CABLE_ROUTE = {'channel_width_mm': 8., 'channel_top_z_mm': 2.0,
               'cover_bottom_z_mm': -1.2, 'cover_top_z_mm': -.2,
               'cable_width_assumed_mm': 7.6, 'cable_thickness_assumed_mm': 1.,
               'flex_exit_y_mm': [5., 13.],
               'dynamic_flex_and_254mm_storage': 'unverified; not a continuous cable motion simulation'}
THUMB_SLOT_X = 6.8
THUMB_SLOT_LENGTH = 9.4
LATCH_MAX_TRAVEL = THUMB_SLOT_X + THUMB_SLOT_LENGTH - 10
SPRING_SPEC = {
    'manufacturer': 'ACCURATE', 'model': 'C101',
    'source': 'https://www.accurate.jp/products/c101/',
    'outer_diameter_mm': 3.5, 'inner_diameter_mm': 3.1,
    'free_length_mm': 15., 'rate_N_per_mm': .059,
    'minimum_allowed_length_mm': 4.5, 'maximum_allowed_force_N': .62,
    'solid_length_mm': 1.9, 'installed_length_mm': 12.,
}
SWITCH_SPEC = {
    'model': 'Lofree x Kailh Specter',
    'source': 'https://www.lofree.co/products/specter-low-profile-pom-switches',
    'nominal_travel_mm': 2.8, 'travel_tolerance_mm': .25,
    'minimum_published_travel_mm': 2.55,
}
SPINE_HALF = 18.0
BOARD_WIDTH = 128.5
CASE_OFFSET = 2.05
EXTENT = SPINE_HALF + BOARD_WIDTH + 2 * CASE_OFFSET
FLOOR = 1.5
HINGE_RADIUS = 3.5
PIN_RADIUS = 1.7
PCB_TOP = 6.1
LID_Z = 19.0
LID_THICKNESS = 1.5
Y0, Y1 = -14., 88.


def box(x, y, z, dx, dy, dz):
    return Part.makeBox(dx, dy, dz, V(x, y, z))


def union(shapes):
    first, *rest = shapes
    return first.multiFuse(rest).removeSplitter() if rest else first


def folded(shape, angle):
    result = shape.copy()
    result.rotate(V(0, 0, AXIS_Z), V(0, 1, 0), angle)
    return result


def cylinder_y(x, y, z, radius, length):
    return Part.makeCylinder(radius, length, V(x, y, z), V(0, 1, 0))


def battery_window():
    w, length = BATTERY_WINDOW['width_mm'], BATTERY_WINDOW['length_mm']
    cx, cy = BATTERY_WINDOW['center_xy_mm']
    window = box(cx - w / 2, cy - length / 2, LID_Z - .1,
                 w, length, LID_THICKNESS + .2)
    vertical = [e for e in window.Edges if e.BoundBox.ZLength > LID_THICKNESS
                and e.BoundBox.XLength < .001 and e.BoundBox.YLength < .001]
    return window.makeFillet(BATTERY_WINDOW['corner_radius_mm'], vertical)


def underfloor_wiring(shapes):
    """Open-bottom channels: install terminated cable sideways, then fit lids.

    The top-mounted headers are retained. The ribbon comes over the plate,
    down OUTSIDE the PCB edge, and then into the lower channel. Only ribbon,
    never the assembled socket, passes through the narrow side slots.
    """
    screws = {'left': [(-24, 2), (-24, 52)],
              'right': [(-11, 2), (-11, 67), (12, 2), (12, 67), (25, 2), (25, 45)]}
    ribs = {'left': box(-28, 0, 0, 10, 54, 3.5),
            'right': union([box(-16, 0, 0, 34, 69, 3.5), box(18, 0, 0, 11, 47, 3.5)])}
    # Ceiling at 2.0 mm, reinforced to 3.5 mm above. The removable cover
    # leaves a 2.2 mm-high cable chamber and a 1.5 mm solid roof.
    voids = {
        'left': union([box(-27, 5, -.19, 8, 44, 2.19),
                       box(-27, 5, -.19, 9.1, 8, 2.19),
                       box(-20, 40.5, -.19, 2.1, 8, 15.2)]),
        'right': union([box(-14, 5, -.19, 30, 60, 2.19),
                        box(-16.1, 5, -.19, 43.1, 8, 2.19),
                        box(19, 5, -.19, 8, 38, 2.19),
                        box(18, 34.5, -.19, 2., 8, 15.2)])}
    covers = {'left': box(-28, 0, -1.2, 10, 54, 1.),
              'right': union([box(-16, 0, -1.2, 34, 69, 1.),
                              box(18, 0, -1.2, 11, 47, 1.)])}
    # Remove the battery holder tie holes only in the cable-room roof: a
    # tie threaded into this chamber could snag the moving ribbon. Existing
    # end fences and supports remain; retention still needs a holder fit test.
    for side in ('left', 'right'):
        name = side + '_tray'
        shapes[name] = union([shapes[name], ribs[side]]).cut(voids[side])
        for x, y in screws[side]:
            shapes[name] = shapes[name].cut(Part.makeCylinder(.85, 3.2, V(x, y, -.1)))
            covers[side] = covers[side].cut(Part.makeCylinder(1.1, 1.2, V(x, y, -1.3)))
        shapes[side + '_cable_cover'] = covers[side].removeSplitter()
    # These slot volumes are kept clear through the cover/plate as well.
    for side, x, y in (('left', -20, 40.5), ('right', 18, 34.5)):
        slot = box(x, y, -.19, 2 if side == 'right' else 2.1, 8, 15.2)
        shapes[side + '_plate'] = shapes[side + '_plate'].cut(slot)
    return voids


def closure_magnet_pockets(left):
    face = 2 * AXIS_Z - STOP_HEIGHT if left else STOP_HEIGHT
    cx = -12 if left else 12
    w, d, depth = CLOSURE_MAGNET['pocket_mm']
    return Part.makeCompound([box(cx - w / 2, y - d / 2, face - depth,
                                 w, d, depth + .02) for y in (2, 72)])


def closure_magnets(left):
    face = 2 * AXIS_Z - STOP_HEIGHT if left else STOP_HEIGHT
    cx = -12 if left else 12
    w, d, h = CLOSURE_MAGNET['size_mm']
    return Part.makeCompound([box(cx - w / 2, y - d / 2,
        face - CLOSURE_MAGNET['nominal_face_recess_mm'] - h, w, d, h) for y in (2, 72)])


def hinge_arm(left, y):
    # Separate axial bands; the 0.4 mm gap is a print-fit assumption.
    start, length = (y, 5.6) if left else (y + 6, 6.)
    x0 = -24 if left else 0
    pillar_x = -5 if left else 0
    shape = union([
        box(x0, y, 0, 24, 12, 5),
        box(pillar_x, start, 0, 5, length, AXIS_Z),
        cylinder_y(0, start, AXIS_Z, HINGE_RADIUS, length),
    ])
    return shape.cut(cylinder_y(0, start - .1, AXIS_Z, PIN_RADIUS, length + .2))


def closed_stop(left):
    # The fixed stops are structural end lands of the central power block.
    # Short fingers integrated into the moving hinge leaves land on them;
    # there are no separate upright stop towers beside the hinges.
    if not left:
        return Part.makeCompound([box(6, y, 0, 10, 4, STOP_HEIGHT)
                                  for y in (0, 70)]).cut(closure_magnet_pockets(False))
    height = STOP_FINGER_THICKNESS
    finger_bottom = 2 * AXIS_Z - STOP_HEIGHT - height
    fingers = []
    for y, length, root_y in ((-14, 18, -14), (70, 11.6, 76)):
        finger = box(-16, y, finger_bottom, 10, length, height)
        edges = [e for e in finger.Edges if e.BoundBox.ZLength > height - .01
                 and e.BoundBox.XLength < .001 and e.BoundBox.YLength < .001]
        finger = finger.makeFillet(.8, edges)
        root = box(-7, root_y, finger_bottom, 5, 5.6, height)
        fingers.append(finger.fuse(root))
    return Part.makeCompound(fingers).cut(closure_magnet_pockets(True))


def latch_parts():
    # Front, spring-loaded rectangular plunger. Pull the exposed thumb tab
    # right 6 mm to release. A sloped upper nose cams inward on reopening;
    # the flat lower face holds the moving socket against upward motion.
    housing = box(0, -14, 1.5, 28, 10, 10.5)
    channel = box(-.1, -12.3, 3.7, 24.1, 4.6, 4.6)
    thumb_slot = box(THUMB_SLOT_X, -14.2, 4.5, THUMB_SLOT_LENGTH, 3, 3)
    housing = housing.cut(channel).cut(thumb_slot)
    housing = housing.cut(Part.makeCylinder(1.05, 5, V(23.5, -10, 6), V(1, 0, 0)))
    # Top is open for installing spring and slider, closed by a separate cap.
    housing = housing.cut(box(1.5, -12.3, 8, 24, 4.6, 5))
    for x in (3, 25):
        housing = housing.cut(Part.makeCylinder(.85, 4.5, V(x, -6.2, 7.5)))
    cap = union([box(0, -14, 12, 28, 10, 1.8),
                 box(1.6, -12.2, 8.3, 23.8, 4.4, 3.8)])
    for x in (3, 25):
        cap = cap.cut(Part.makeCylinder(1.1, 2, V(x, -6.2, 11.9)))
    # Pin tip: top ramps from z=4 to z=8 across x=-5..-1.
    profile = [V(-5, -12, 4), V(12, -12, 4), V(12, -12, 8),
               V(-1, -12, 8), V(-5, -12, 4)]
    slider = Part.Face(Part.makePolygon(profile)).extrude(V(0, 4, 0))
    slider = union([slider, box(7, -16, 5, 3, 5, 2),
                    Part.makeCylinder(.8, 9, V(12, -10, 6), V(1, 0, 0))])
    socket = box(-12, -14, 1.5, 12, 10, 10.5).cut(
        box(-10, -12.15, 3.85, 10.1, 4.3, 4.3))
    spring = Part.makeCylinder(1.75, 12, V(12, -10, 6), V(1, 0, 0)).cut(
        Part.makeCylinder(SPRING_SPEC['inner_diameter_mm'] / 2, 12, V(12, -10, 6), V(1, 0, 0)))
    return housing, cap, slider, socket, spring


def power_room():
    # Right-hand fixed spine, AAA holder long axis along keyboard depth.
    body = box(-16, 0, 0, 34, 74, LID_Z).cut(box(-14, 2, 2, 30, 70, LID_Z - 1))
    # Holder supports, end fences, module support and tie slots.
    body = union([body,
        box(-13, 13, 2, 13, 4, 1.5), box(-13, 55, 2, 13, 4, 1.5),
        box(-14, 8, 2, 15, 1.5, 3), box(-14, 62, 2, 15, 1.5, 3),
        box(-14, 9.5, 2, .6, 52.5, 4), box(.4, 9.5, 2, 1.6, 52.5, 4),
        box(4, 28, 2, 10, 7.5, 2), box(4, 65, 2, 9.5, 6, 3),
    ])
    for yy in (20, 52):
        for xx in (-13.8, .7):
            body = body.cut(box(xx, yy, -.1, 1.1, 3.2, 2.3))
    for xx in (2.8, 14.6):
        body = body.cut(box(xx, 30, -.1, 1.1, 3.2, 2.3))
    for xx in (3, 14):
        body = body.cut(box(xx, 47, -.1, 1.1, 3.2, 2.3))
        body = body.cut(box(xx, 66, -.1, 1.1, 3.2, 2.3))
    # Switch knob access, rightward 5V/GND exit. Wiring is confined to fixed
    # right body; only the split interconnect must cross the folding joint.
    body = body.cut(box(1, 71, 4, 14, 4, 7))
    body = body.cut(box(15, 64.5, 15, 4, 4.5, 4))
    # An elevated open duct carries the two power wires over the XIAO cover,
    # away from its USB mouth (north of y=71). Its end drops to pads 13/14.
    duct = box(16, 64, 14, 28, 6, 3).cut(box(15.9, 65.2, 15, 28.2, 3.6, 2.1))
    body = body.fuse(duct)
    lid = box(-16, 0, LID_Z, 34, 74, LID_THICKNESS)
    # Display the cell through a rounded opening; retain a solid cover over
    # the adjacent electronics. Holder must expose the cell's upper surface.
    lid = lid.cut(battery_window())
    # Move right-hand lid screws away from the structural landing surfaces.
    for x, y in ((-12, 6.5), (-12, 66), (13.5, 8), (13.5, 60)):
        body = body.fuse(Part.makeCylinder(3.2, 6, V(x, y, LID_Z - 6)))
        body = body.cut(Part.makeCylinder(.85, 5, V(x, y, LID_Z - 4.9)))
        lid = lid.cut(Part.makeCylinder(1.1, LID_THICKNESS + .2, V(x, y, LID_Z - .1)))
    for y in (0, 70):
        # Recessed structural lands receive the fingers when closed. The
        # opposite recess clears the same fingers while the keyboard is open.
        body = body.cut(box(5.2, y - .3, STOP_HEIGHT, 11.1, 4.6, 20))
        open_clear_z = 2 * AXIS_Z - STOP_HEIGHT - STOP_FINGER_THICKNESS - .5
        body = body.cut(box(-16.3, y - .3, open_clear_z, 11.1, 4.6, 20))
        lid = lid.cut(box(5.2, y - .3, LID_Z - .1, 11.1, 4.6, LID_THICKNESS + .2))
        lid = lid.cut(box(-16.3, y - .3, LID_Z - .1, 11.1, 4.6, LID_THICKNESS + .2))
    body = body.fuse(closed_stop(False))
    # Retain the rear EN-switch opening below the structural rear land.
    body = body.cut(box(1, 71, 4, 14, 4, 7))
    body = body.cut(box(5, 69.8, 4, 6, 4.3, 7))
    # Clearance for hinge bolt tails / locknuts and the rear bolt head.
    if LID_Z + LID_THICKNESS > AXIS_Z - 3.5:
        for yy in (-.1, 72):
            notch = box(-4, yy, AXIS_Z - 4, 8, 6.1 if yy < 0 else 2.1, 8)
            body = body.cut(notch)
            lid = lid.cut(notch)
    # The original wall/floor can refill part of a pocket during fusion.
    body = body.cut(closure_magnet_pockets(False))
    refs = {
        'AAA_holder_assumed': box(-13, 10, 3.5, 13, 51, 15),
        'AAA_cell_reference': Part.makeCylinder(5.25, 44.5, V(-6.5, 13.25, 11), V(0, 1, 0)),
        'Boost_module_assumed': box(4, 28, 4, 10, 7.5, 3),
        'PTC_assumed': box(4.5, 46, 4, 8.5, 3.5, 10),
        'Diode_assumed': Part.makeCylinder(1.3, 3.5, V(9, 55, 5.3), V(0, 1, 0)),
        'Switch_assumed': box(4, 66, 5, 8.8, 3.9, 3.5),
        'Switch_knob_assumed': box(6, 69.9, 6, 4, 4, 2),
        'Power_disconnect_reserved': box(4, 13, 4, 11, 9, 7),
    }
    return body.removeSplitter(), lid.removeSplitter(), refs


def feature(doc, name, shape, color, visible=True):
    o = doc.addObject('Part::Feature', name)
    o.Label = name.replace('_', ' ')
    o.Shape = shape
    if o.ViewObject:
        o.ViewObject.ShapeColor = color
        o.ViewObject.Visibility = visible
    return o


def main():
    assert 2 * AXIS_Z - STOP_HEIGHT - STOP_FINGER_THICKNESS > 12, 'Stop fingers reach the front latch'
    assert 2 * AXIS_Z - 2 * (PCB_TOP + KEY_HEIGHT) >= 2, 'Opposing keycaps collide'
    assert 2 * AXIS_Z - TRACKBALL_TOP - (PCB_TOP + KEY_HEIGHT - KEY_PRESS_LIMIT) >= .5, 'Insufficient key depression allowance'
    assert KEY_PRESS_LIMIT <= SWITCH_SPEC['minimum_published_travel_mm'], 'Design key travel exceeds Specter specification'
    spring_at_stop = SPRING_SPEC['installed_length_mm'] - LATCH_MAX_TRAVEL
    assert spring_at_stop > SPRING_SPEC['minimum_allowed_length_mm'], 'Spring overcompressed at button stop'
    OUT.mkdir(exist_ok=True)
    lib = runpy.run_path(str(ROOT / '3d-models/FreeCAD/generate-keyboard-case.py'), run_name='split_case_library')
    doc = App.newDocument('FoldingUnibodyRevA')
    doc.Label = 'komoro folding unibody Rev A — fit prototype'
    # _make_side builds from current PCB without saving or changing split files.
    shapes, moving_refs, fixed_refs, counts = {}, {}, {}, {}
    left_keys = {}
    for side in ('left', 'right'):
        bottom, top = lib['_make_side'](doc, ROOT, side)
        dx = -SPINE_HALF - BOARD_WIDTH - CASE_OFFSET if side == 'left' else SPINE_HALF + CASE_OFFSET
        for group in doc.Objects:
            if group.Name.startswith(side + '_') and group.isDerivedFrom('Part::Feature'):
                group.Shape = group.Shape.translated(V(dx, 0, 0))
                if group.ViewObject:
                    group.ViewObject.Visibility = False
        tray, plate = bottom.Shape.copy(), top.Shape.copy()
        # Keep the source PCB-following perimeter and column steps. Only the
        # inner 8 mm spine rail extends to the front/rear hinge roots; there
        # is no rectangular skirt under the outer key field.
        rail_x = -26 if side == 'left' else 18
        tray = union([tray, box(rail_x, Y0, 0, 8, Y1 - Y0, 5)])
        arms = [hinge_arm(side == 'left', yy) for yy in (-14, 76)]
        tray = union([tray] + arms + ([closed_stop(True)] if side == 'left' else []))
        shapes[side + '_tray'] = tray
        shapes[side + '_plate'] = plate
        data = lib['_board_data'](ROOT / 'pcb' / lib['PCB_FILENAMES'][side])
        if side == 'right':
            # The rectangular base must not fill the original trackball slot.
            recess = [r for r in data['records'] if r['kind'] == 'gr_line'
                      and abs(r['start'][1] - r['end'][1]) < .02
                      and min(r['start'][1], r['end'][1]) > .02
                      and abs(r['start'][0] - r['end'][0]) >= 30
                      and max(r['start'][0], r['end'][0]) < 90]
            edge = min(recess, key=lambda r: r['start'][1])
            slot_x = min(edge['start'][0], edge['end'][0]) + 2 + dx
            slot_y = lib['TRACKBALL_MOUNT_FRONT_LIP'] - lib['TRACKBALL_MOUNT_SLOT_SOUTH_SHIFT']
            slot = box(slot_x, slot_y, -.1, lib['TRACKBALL_MOUNT_SLOT_WIDTH'],
                       lib['TRACKBALL_MOUNT_SLOT_DEPTH'], FLOOR + .2)
            recess_head = box(slot_x - .9, slot_y - .9, -.1,
                       lib['TRACKBALL_MOUNT_SLOT_WIDTH'] + 1.8, 4.2, .5)
            shapes['right_tray'] = shapes['right_tray'].cut(slot).cut(recess_head)
        key_shapes = []
        for f in data['footprints']:
            if 'CHOC_V2_SOCKET' in f['name']:
                key = lib['_rotated_box'](16, 16, f['cad_x'] + dx,
                    f['cad_y'], f['cad_angle'], PCB_TOP + 5, KEY_HEIGHT - 5)
                key_shapes.append(key)
                if side == 'left':
                    left_keys[f['reference']] = key
        counts[side] = len(key_shapes)
        refs = moving_refs if side == 'left' else fixed_refs
        refs['Keys_' + side] = Part.makeCompound(key_shapes)
        for name in ('PCB_reference', 'XIAO_reference', 'SplitHeader_reference'):
            obj = doc.getObject(side + '_' + name)
            if obj:
                refs[side + '_' + name] = obj.Shape.copy()
    body, lid, power_refs = power_room()
    assert lid.common(battery_window()).Volume < .001, 'Battery display opening obstructed'
    housing, cap, slider, socket, spring = latch_parts()
    shapes['left_tray'] = union([shapes['left_tray'], socket]).cut(
        box(-10, -12.15, 3.85, 10.1, 4.3, 4.3))
    shapes['left_tray'] = shapes['left_tray'].cut(closure_magnet_pockets(True))
    # Spine is integral with fixed right tray. Low floor bridges do not touch
    # the left moving case (2 mm gap to x=-18).
    bridge = box(14, 3, 0, 8, 68, FLOOR)
    shapes['right_tray'] = union([shapes['right_tray'], body, bridge, housing])
    # Reapply openings after the hinge roots and floor have been fused.
    shapes['right_tray'] = shapes['right_tray'].cut(box(-.1, -12.3, 3.7, 24.1, 4.6, 4.6))
    shapes['right_tray'] = shapes['right_tray'].cut(box(THUMB_SLOT_X, -14.2, 4.5, THUMB_SLOT_LENGTH, 3, 3))
    shapes['right_tray'] = shapes['right_tray'].cut(Part.makeCylinder(1.05, 5, V(23.5, -10, 6), V(1, 0, 0)))
    # Inner-spine service route. The former full-width rear rail is removed.
    shapes['right_tray'] = shapes['right_tray'].cut(box(17, 79, 2.5, 10, 3, 3))
    # Open access to the outer 5V/GND solder pads. No PCB copper is edited.
    shapes['right_plate'] = shapes['right_plate'].cut(box(41, 63, 6, 4, 6, 8))
    shapes.update(power_lid=lid, latch_cap=cap, latch_slider=slider)
    cable_voids = underfloor_wiring(shapes)
    # Keep old source parts as hidden references, then add the print assembly.
    for obj in doc.Objects:
        if obj.ViewObject:
            obj.ViewObject.Visibility = False
    colors = {'left_tray': (.80, .80, .77), 'right_tray': (.80, .80, .77),
              'left_plate': (.90, .90, .87), 'right_plate': (.90, .90, .87),
              'power_lid': (.90, .90, .87), 'latch_cap': (.80, .80, .77),
              'left_cable_cover': (.80, .80, .77), 'right_cable_cover': (.80, .80, .77),
              'latch_slider': (.24, .27, .29)}
    objects = {}
    validation = {'revision': 'A / unprinted fit prototype', 'axis_z_mm': AXIS_Z,
                  'PCB_top_z_mm': PCB_TOP, 'key_height_above_PCB_mm': KEY_HEIGHT,
                  'key_height_default_basis': 'User measured 10.5 mm above PCB; same switches and keycaps as split version',
                  'configuration': {'trackball': 'retained', 'lock': 'automatic spring latch, manual release',
                      'folding': 'keys may depress on contact; power off before folding'},
                  'key_press_limit_assumption_mm': KEY_PRESS_LIMIT,
                  'switch': dict(SWITCH_SPEC),
                  'closure_magnets': dict(CLOSURE_MAGNET),
                  'spring': {**SPRING_SPEC, 'maximum_button_travel_mm': LATCH_MAX_TRAVEL,
                      'length_at_button_stop_mm': spring_at_stop,
                      'locked_force_N': SPRING_SPEC['rate_N_per_mm'] * (SPRING_SPEC['free_length_mm'] - SPRING_SPEC['installed_length_mm']),
                      'released_force_N': SPRING_SPEC['rate_N_per_mm'] * (SPRING_SPEC['free_length_mm'] - SPRING_SPEC['installed_length_mm'] + 6),
                      'force_at_button_stop_N': SPRING_SPEC['rate_N_per_mm'] * (SPRING_SPEC['free_length_mm'] - spring_at_stop)},
                  'power_room': {'top_mm': LID_Z + LID_THICKNESS, 'lid_bottom_mm': LID_Z,
                      'lid_thickness_mm': LID_THICKNESS, 'holder_height_assumption_mm': 15.,
                      'holder_bottom_mm': 3.5, 'holder_roof_clearance_mm': LID_Z - 18.5,
                      'height_basis': 'holder remains unmeasured; retain previous 15 mm envelope'},
                  'styling': {'perimeter': 'original PCB-following contour, inner hinge rails only',
                      'battery_window': dict(BATTERY_WINDOW),
                      'battery_visibility': 'requires an open-top holder; actual holder remains unmeasured'},
                  'interconnect': dict(CABLE_ROUTE),
                  'trackball_top_z_assumption_mm': TRACKBALL_TOP,
                  'key_counts': counts, 'parts': {}, 'sweep': [],
                  'sources_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in [ROOT / 'pcb' / lib['PCB_FILENAMES'][s] for s in ('left', 'right')] +
                              [ROOT / '3d-models/FreeCAD/generate-keyboard-case.py', HERE / 'generate.py']}}
    for name, shape in shapes.items():
        shape = shape.removeSplitter()
        assert shape.isValid() and len(shape.Solids) == 1, (name, 'invalid/disconnected', len(shape.Solids))
        obj = feature(doc, 'Print_' + name, shape, colors[name])
        objects[name] = obj
        mesh = Mesh.Mesh(shape.tessellate(.08))
        path = OUT / (name + '.stl')
        mesh.write(str(path))
        lib['_close_stl_roundoff'](path)
        saved = Mesh.Mesh(str(path))
        assert saved.isSolid(), (name, 'STL is not closed')
        Part.export([obj], str(OUT / (name + '.step')))
        bb = shape.BoundBox
        validation['parts'][name] = {'volume_mm3': round(shape.Volume, 3),
            'size_mm': [round(bb.XLength, 3), round(bb.YLength, 3), round(bb.ZLength, 3)],
            'valid_solid': True, 'closed_STL': True}
    # Conservative trackball envelope in the right recess, not an exact mount.
    fixed_refs['Trackball_reserved_envelope'] = box(62, -3, 1.5, 30, 21, TRACKBALL_TOP - 1.5)
    # Storage below the battery: this does not pretend to be the flexible
    # cable's changing shape through the folding motion.
    fixed_refs['Split_cable_storage_reserved'] = box(-13.8, 14, -.15, 29.6, 50.8, 2.0)
    moving_refs['Closure_magnets_left'] = closure_magnets(True)
    fixed_refs['Closure_magnets_right'] = closure_magnets(False)
    # M3x18 screw, two 0.5 mm washers, 4 mm tall locknut. The circular
    # nut envelope conservatively encloses a 5.5 mm across-flats hexagon.
    for y, label in ((-14, 'front'), (76, 'rear')):
        shaft = cylinder_y(0, y - .5, AXIS_Z, 1.5, 18)
        head = cylinder_y(0, y - 3.5, AXIS_Z, 2.75, 3)
        nut = cylinder_y(0, y + 12.5, AXIS_Z, 3.2, 4).cut(
            cylinder_y(0, y + 12.4, AXIS_Z, 1.5, 4.2))
        washers = [cylinder_y(0, yy, AXIS_Z, 3.5, .5).cut(
            cylinder_y(0, yy - .1, AXIS_Z, 1.6, .7)) for yy in (y - .5, y + 12)]
        fixed_refs['Hinge_hardware_' + label] = Part.makeCompound([shaft, head, nut] + washers)
    moving = union([shapes['left_tray'], shapes['left_plate'], shapes['left_cable_cover']])
    fixed = union([shapes['right_tray'], shapes['right_plate'], shapes['right_cable_cover'], lid, cap])
    validation['interconnect']['clear_passages_mm3'] = {}
    for side in ('left', 'right'):
        assembly = shapes[side + '_tray'].fuse(shapes[side + '_plate']).fuse(shapes[side + '_cable_cover'])
        overlap = assembly.common(cable_voids[side]).Volume
        assert overlap < .001, ('Cable passage obstructed', side, overlap)
        validation['interconnect']['clear_passages_mm3'][side] = round(overlap, 6)
    for name in ('Hinge_hardware_front', 'Hinge_hardware_rear'):
        assert fixed_refs[name].common(fixed).Volume < .01, ('Hinge hardware hits fixed body', name)
    moving_obstacles = Part.makeCompound([s for n, s in moving_refs.items() if n != 'Keys_left'])
    fixed_obstacles = Part.makeCompound(list(fixed_refs.values()))
    key_blockers = Part.makeCompound([fixed, fixed_obstacles])
    closed_key_pressures = {}
    validation['key_depression_by_angle'] = []
    # Slider is deliberately omitted from sweep: retract before folding. Its
    # locked engagement and released clearance are checked separately below.
    angles = sorted(set(range(0, 181, 5)) | {175 + i * .5 for i in range(11)})
    for angle in angles:
        mv = folded(moving, angle)
        vol = mv.common(fixed).Volume
        released_vol = mv.common(slider.translated(V(6, 0, 0))).Volume
        component_vol = folded(moving_obstacles, angle).common(fixed_obstacles).Volume
        mixed_vol = mv.common(fixed_obstacles).Volume + folded(moving_obstacles, angle).common(fixed).Volume
        pressed = {}
        for name, key in left_keys.items():
            required = 0.
            if folded(key, angle).common(key_blockers).Volume > .001:
                for step in range(1, int(KEY_PRESS_LIMIT * 10) + 1):
                    required = step / 10
                    if folded(key.translated(V(0, 0, -required)), angle).common(key_blockers).Volume < .001:
                        break
                else:
                    raise AssertionError(('Key cannot clear within allowed travel', name, angle, KEY_PRESS_LIMIT))
            if required:
                pressed[name] = required
        validation['key_depression_by_angle'].append({'angle_deg': angle, 'required_mm': pressed})
        if angle == 180:
            closed_key_pressures = pressed
        validation['sweep'].append({'angle_deg': angle, 'body_overlap_mm3': round(vol, 6),
            'component_overlap_mm3': round(component_vol, 6), 'body_component_overlap_mm3': round(mixed_vol, 6),
            'released_latch_overlap_mm3': round(released_vol, 6)})
        assert max(vol, component_vol, mixed_vol, released_vol) < .01, ('fold collision', validation['sweep'][-1])
    validation['latch'] = {
        'locked_overlap_mm3': round(slider.common(shapes['left_tray']).Volume, 6),
        'retracted_overlap_mm3': round(slider.translated(V(6, 0, 0)).common(shapes['left_tray']).Volume, 6),
        'engaged_depth_mm': 5, 'release_travel_mm': 6,
        'automatic_cam_and_spring_force': 'not physically verified',
    }
    assert validation['latch']['locked_overlap_mm3'] < .01, validation['latch']
    assert validation['latch']['retracted_overlap_mm3'] < .01
    validation['latch']['fixed_body_overlap_mm3'] = round(slider.common(fixed).Volume, 6)
    assert validation['latch']['fixed_body_overlap_mm3'] < .01
    for travel in (0, 1, 2, 3, 4, 5, 6):
        assert slider.translated(V(travel, 0, 0)).common(fixed).Volume < .01, ('Slider channel obstructed', travel)
    assert slider.translated(V(LATCH_MAX_TRAVEL + .1, 0, 0)).common(fixed).Volume > .01, 'Button overtravel stop missing'
    validation['latch']['overtravel_stop_overlap_mm3'] = round(slider.translated(V(LATCH_MAX_TRAVEL + .1, 0, 0)).common(fixed).Volume, 6)
    # A rigid cam-path test, independent of spring force/friction: at each
    # approach angle at least one permitted slider position must fit.
    cam = []
    for angle in range(0, 31):
        socket_at_angle = folded(shapes['left_tray'], angle)
        allowed = [i / 4 for i in range(25) if slider.translated(V(i / 4, 0, 0)).common(socket_at_angle).Volume < .001]
        assert allowed, ('No automatic latch cam path', angle)
        cam.append({'angle_deg': angle, 'minimum_retraction_mm': min(allowed)})
    validation['latch']['cam_approach'] = cam
    validation['latch']['holding_overlap_at_5_deg_mm3'] = round(slider.common(folded(shapes['left_tray'], 5)).Volume, 6)
    validation['latch']['open_stop_overlap_at_minus_1_deg_mm3'] = round(folded(moving, -1).common(fixed).Volume, 6)
    assert validation['latch']['holding_overlap_at_5_deg_mm3'] > .01, 'Latch does not restrain folding'
    assert validation['latch']['open_stop_overlap_at_minus_1_deg_mm3'] > .01, 'Open stop does not restrain overtravel'
    closed_left_stop = folded(closed_stop(True), 180)
    right_stop = closed_stop(False)
    left_bb, right_bb = closed_left_stop.BoundBox, right_stop.BoundBox
    # Probe 0.001 mm into the contact plane to measure the rounded contact
    # area robustly; common() may discard exactly touching coplanar faces.
    contact_probe = closed_left_stop.translated(V(0, 0, -.001))
    stop_area = contact_probe.common(right_stop).Volume / .001
    validation['closed_stop'] = {
        'location': 'front and rear structural end lands integrated into central power block',
        'nominal_contact_area_at_180_deg_mm2': round(stop_area, 6),
        'separation_at_180_deg_mm': round(closed_left_stop.distToShape(right_stop)[0], 9),
        'contact_plane_gap_mm': round(left_bb.ZMin - right_bb.ZMax, 9),
        'overtravel_overlap_at_181_deg_mm3': round(folded(moving, 181).common(fixed).Volume, 6),
        'lid_overlap_under_contact_probe_mm3': round(contact_probe.common(lid).Volume, 9),
        'old_inner_tower_overlap_below_hinge_axis_mm3': {},
        'outer_corner_overlap_above_5_mm3': {},
    }
    assert stop_area > 45 and abs(left_bb.ZMin - right_bb.ZMax) < 1e-6, 'Closed stop faces do not align'
    assert closed_left_stop.distToShape(right_stop)[0] < 1e-6, 'Closed stops do not meet'
    assert validation['closed_stop']['overtravel_overlap_at_181_deg_mm3'] > .01, 'Closed stop does not restrain overtravel'
    assert contact_probe.common(lid).Volume < .0001, 'Closed load must bypass the power lid'
    left_magnets, right_magnets = closure_magnets(True), closure_magnets(False)
    assert left_magnets.common(shapes['left_tray']).Volume < .0001
    assert right_magnets.common(fixed).Volume < .0001
    magnet_gap = folded(left_magnets, 180).distToShape(right_magnets)[0]
    assert abs(magnet_gap - .2) < 1e-6, ('Closure magnet gap', magnet_gap)
    validation['closure_magnets'].update({
        'closed_face_gap_mm': round(magnet_gap, 6),
        'minimum_side_wall_mm': .85,
        'remaining_finger_floor_mm': STOP_FINGER_THICKNESS - CLOSURE_MAGNET['pocket_mm'][2],
        'magnet_lever_arm_mm': 12.,
        'example_only': {'assumed_force_per_pressed_key_N': .5,
            'key_lever_arms_mm': [70.05, 87.05],
            'required_pull_per_pair_N': round(.5 * (70.05 + 87.05) / (12 * 2), 4),
            'note': 'illustration, not measured key force or validated magnetic holding force'},
    })
    for side, x in (('left', -20), ('right', 12)):
        ceiling = 2 * AXIS_Z - STOP_HEIGHT - STOP_FINGER_THICKNESS - .5
        vol = shapes[side + '_tray'].common(box(x, 76, 5.01, 8, 12, ceiling - 5.01)).Volume
        validation['closed_stop']['old_inner_tower_overlap_below_hinge_axis_mm3'][side] = round(vol, 6)
        assert vol < .001, ('Separate inner stop tower remains', side)
    for side in ('left', 'right'):
        corner_x = -EXTENT if side == 'left' else EXTENT - 8
        for yy in (-14, 80):
            vol = shapes[side + '_tray'].common(box(corner_x, yy, 5.01, 8, 8, AXIS_Z)).Volume
            validation['closed_stop']['outer_corner_overlap_above_5_mm3'][side + '_' + str(yy)] = round(vol, 6)
            assert vol < .001, ('Outer corner tower remains', side, yy)
    validation['power_envelope_overlap_mm3'] = {}
    for name, ref in power_refs.items():
        vol = ref.common(shapes['right_tray']).Volume + ref.common(lid).Volume
        validation['power_envelope_overlap_mm3'][name] = round(vol, 6)
        assert vol < .01, ('Power-room collision', name, vol)
    # Spring envelope and pin/hardware are references, never printable parts.
    fixed_refs.update(power_refs)
    validation['maximum_required_key_depression_mm'] = max(
        [p for row in validation['key_depression_by_angle'] for p in row['required_mm'].values()] or [0])
    validation['switch']['minimum_travel_minus_required_mm'] = round(
        SWITCH_SPEC['minimum_published_travel_mm'] - validation['maximum_required_key_depression_mm'], 3)
    validation['closed_key_depression_mm'] = closed_key_pressures
    closed_keys = Part.makeCompound([key.translated(V(0, 0, -closed_key_pressures.get(name, 0)))
                                    for name, key in left_keys.items()])
    fixed_refs['Latch_spring_envelope'] = spring
    for name, shape in {**moving_refs, **fixed_refs}.items():
        color = (.91, .91, .88) if 'AAA_cell' in name or 'Keys_' in name else (.34, .38, .4)
        feature(doc, 'Reference_' + name, shape, color, 'Keys_' in name or name == 'AAA_cell_reference')
    for name in ('left_tray', 'left_plate'):
        feature(doc, 'Folded_' + name, folded(shapes[name], 180), colors[name], False)
    feature(doc, 'Folded_Keys_left', folded(closed_keys, 180), (.34, .38, .4), False)
    # Print these small, full-scale front joint sections before a full body.
    validation['fit_coupons'] = {}
    coupons = {}
    for side, x0, width in (('left', -32, 32), ('right', -16, 48)):
        coupon = shapes[side + '_tray'].common(box(x0, -14, -.1, width,
                                                24, AXIS_Z + 5.2)).removeSplitter()
        coupons['fit_' + side + '_joint'] = coupon
    coupons['fit_front_power_lid'] = lid.common(box(-16, 0, 0, 34, 10, 25)).removeSplitter()
    coupons['fit_power_room'] = body.copy()
    for name, coupon in coupons.items():
        assert coupon.isValid() and len(coupon.Solids) == 1
        obj = feature(doc, name, coupon, (.31, .58, .62), False)
        path = OUT / (name + '.stl')
        Mesh.Mesh(coupon.tessellate(.08)).write(str(path))
        lib['_close_stl_roundoff'](path)
        Part.export([obj], str(OUT / (name + '.step')))
        bb = coupon.BoundBox
        validation['fit_coupons'][name] = {'valid_solid': True, 'closed_STL': True,
            'size_mm': [round(bb.XLength, 3), round(bb.YLength, 3), round(bb.ZLength, 3)]}
    front_fixed = coupons['fit_right_joint'].fuse(coupons['fit_front_power_lid'])
    front_moving_closed = folded(coupons['fit_left_joint'], 180)
    assert front_moving_closed.common(front_fixed).Volume < .01
    assert folded(coupons['fit_left_joint'], 181).common(front_fixed).Volume > .01
    validation['front_coupon_closed_stop_verified'] = True
    mesh_preview = {}
    # A sphere for presentation only. Collision checks continue to use the
    # larger reserved envelope; actual cradle/sensor location is unverified.
    visual_refs = {'Trackball_visual_only': Part.makeSphere(9.525, V(77, 7.5, 11.3))}
    feature(doc, 'Visual_Trackball_not_mount_geometry', visual_refs['Trackball_visual_only'], (.72, .74, .75))
    for name, shape in {**shapes, **moving_refs, **fixed_refs, 'Keys_left_closed': closed_keys, **coupons, **visual_refs}.items():
        vertices, triangles = shape.tessellate(.35)
        mesh_preview[name] = {'vertices': [[v.x, v.y, v.z] for v in vertices], 'triangles': triangles}
    (OUT / 'preview-mesh.json').write_text(json.dumps(mesh_preview))
    bbox = Part.makeCompound(list(shapes.values())).BoundBox
    closed_bbox = Part.makeCompound([folded(shapes[n], 180) if n.startswith('left_') else shapes[n]
                                   for n in shapes]).BoundBox
    validation['open_size_mm'] = [round(bbox.XLength, 2), round(bbox.YLength, 2), round(bbox.ZLength, 2)]
    validation['closed_size_mm'] = [round(closed_bbox.XLength, 2), round(closed_bbox.YLength, 2), round(closed_bbox.ZLength, 2)]
    validation['assembled_open_size_including_hinge_hardware_mm'] = [validation['open_size_mm'][0], 111., validation['open_size_mm'][2]]
    validation['assembled_closed_size_including_hinge_hardware_mm'] = [validation['closed_size_mm'][0], 111., validation['closed_size_mm'][2]]
    validation['key_to_key_closed_gap_mm'] = round(2 * AXIS_Z - 2 * (PCB_TOP + KEY_HEIGHT), 2)
    validation['trackball_to_key_closed_gap_mm'] = round(2 * AXIS_Z - TRACKBALL_TOP - (PCB_TOP + KEY_HEIGHT), 2)
    validation['unverified'] = ['keycap lateral envelope and actual assembled trackball dimensions', 'wiring and FFSD bend fatigue',
        'actual switch travel, contact force and sustained key depression',
        'magnetic retention against key reaction, polarity and adhesive strength',
        'printed fit / strength / creep', 'spring selection and automatic latch cam',
        '5V solder-joint clearance and insulation', 'power thermal performance and battery life']
    (OUT / 'validation.json').write_text(json.dumps(validation, indent=2) + '\n')
    doc.recompute()
    doc.saveAs(str(OUT / 'folding-unibody-rev-a.FCStd'))
    print(json.dumps({k: validation[k] for k in ('open_size_mm', 'closed_size_mm', 'key_counts')}, indent=2))


if __name__ == '__main__':
    main()
