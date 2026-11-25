"""Approved C variant: solid tapers, flat floors and nominal 1 mm power wires.

Coordinates use the folding assembly frame, in mm. No study CAD is an input.
The split generator's default remains unchanged; its optional flat construction
provides exact differences without filling PCB, USB or mounting clearances.
"""
from pathlib import Path
import math
import runpy
import FreeCAD as App
import Part

V = App.Vector
ROOT = Path(__file__).resolve().parents[3]
WIRE_OD = 1.0
# 0.01 mm above the study radius avoids a tangent sliver at the old roof
# boundary X43.35. This preserves the nominal wires and makes a closed STL.
CHANNEL_RADIUS = .66
ROUTES = [
    [(-9.55,67.55,11.7),(-9.55,67.55,3.55),(37,67.55,3.55),
     (41.7,67.55,2.35),(43.4,70.,2.35),(43.4,78.5,2.35),
     (43.45,79.35,4.5),(43.45,79.35,6.7),(44.,78.55,7.35),(44.,70.48,7.35)],
    [(-8.2,69.02,12.9),(-8.2,69.02,3.55),(43.,69.02,3.55),
     (45.18,71.83,3.55),(45.18,78.65,3.55),(45.42,79.65,4.55),
     (45.42,79.65,7.4),(44.18,78.65,8.45),(44.,73.02,8.45)],
]


def path(coords):
    """Tangent line/arc centreline, preserving the approved corner trims."""
    ps = [V(*c) for c in coords]
    edges, radii = [], []
    last = ps[0]
    for before, p, after in zip(ps, ps[1:], ps[2:]):
        u, v = before-p, after-p
        angle = u.getAngle(v)
        if angle > math.pi-.0001:
            continue
        trim = min(1.35, u.Length*.44, v.Length*.44)
        u.normalize(); v.normalize()
        direction = u+v; direction.normalize()
        radius = trim*math.tan(angle/2)
        center = p+direction*(trim/math.cos(angle/2))
        q1, q2 = p+u*trim, p+v*trim
        edges.extend((Part.makeLine(last,q1), Part.Arc(q1,center-direction*radius,q2).toShape()))
        last = q2
        radii.append(radius)
    edges.append(Part.makeLine(last,ps[-1]))
    return Part.Wire(edges), ps[0], ps[1]-ps[0], min(radii)


def tube(route, radius):
    spine, start, axis, _ = route
    return spine.makePipeShell([Part.Wire([Part.makeCircle(radius,start,axis)])],True,True).removeSplitter()


def chamfer_top(shape, z, amount, predicate=lambda e: True):
    # Only straight perimeter edges: round screw bores are never candidates.
    edges = [e for e in shape.Edges if type(e.Curve).__name__ == 'Line'
             and abs(e.BoundBox.ZMin-z)<.001 and abs(e.BoundBox.ZMax-z)<.001
             and predicate(e)]
    assert edges, ('no C taper edges', z)
    result = shape.makeChamfer(amount,edges)
    assert result.isValid() and len(result.Solids)==1, 'C taper invalid'
    return result


def apply(parts, refs, base):
    box, union = base['box'], base['union']
    lib = runpy.run_path(str(ROOT/'3d-models/FreeCAD/generate-keyboard-case.py'),run_name='split_library')
    receipt = {'style':'C / solid perimeter chamfers preserve bores and closure lands',
               'wire_OD_mm':WIRE_OD, 'channel_radius_mm':CHANNEL_RADIUS,
               'route_points_mm':ROUTES, 'bottom_changes':{}, 'tapers':{}}
    for side,offset in [('left',V(-148.55,0,0)),('right',V(20.05,6,0))]:
        original_doc = App.newDocument('LegacyBottom')
        flat_doc = App.newDocument('FlatBottom')
        before,_ = lib['_make_side'](original_doc,ROOT,side)
        after,_ = lib['_make_side'](flat_doc,ROOT,side,legacy_bottom_features=False)
        fill = after.Shape.cut(before.Shape).translated(offset)
        shave = before.Shape.cut(after.Shape).translated(offset)
        if side == 'right':
            outer = box(20.05,-20,-2,180,125,60)
            fill,shave = fill.common(outer),shave.common(outer)
        name = side+'_tray'
        prior = parts[name]
        parts[name] = prior.fuse(fill).cut(shave)
        if side == 'left':
            parts[name] = parts[name].cut(box(-28,0,-1.21,10,54,1.21))
        parts[name] = parts[name].removeSplitter()
        receipt['bottom_changes'][side] = {'added_mm3':parts[name].cut(prior).Volume,
                                         'removed_mm3':prior.cut(parts[name]).Volume}
        App.closeDocument(original_doc.Name); App.closeDocument(flat_doc.Name)
    # Use small real solid tapers rather than deforming a mesh and its bores.
    # Top shoulder perimeter beside the hinge only; stop lands are lower.
    for side in ('left','right'):
        name = side+'_tray'
        s = parts[name]
        bands = ((.3,3.7),(70.3,73.7)) if side=='left' else ((-2.,0.),(4.,6.),(74.,76.))
        for lo,hi in bands:
            for y,direction in ((lo,1),(hi,-1)):
                # Wedge starts above the pin bore (top Z19.55), preserving
                # its complete diameter and all closure contact surfaces.
                poly=[V(-4,y,19.7),V(-4,y,22.),V(-4,y+direction*.45,22.),V(-4,y,19.7)]
                s=s.cut(Part.Face(Part.makePolygon(poly)).extrude(V(8,0,0)))
        parts[name] = s.removeSplitter()
        receipt['tapers'][name] = .35
    for name,z,amount in [('latch_cap',15.8,.3),('power_lid',16.3,.65),('power_rear_lid',16.3,.65)]:
        parts[name] = chamfer_top(parts[name].removeSplitter(),z,amount,lambda e: name!='latch_cap' or e.BoundBox.YMin<13.49)
        receipt['tapers'][name] = amount
    paths = [path(c) for c in ROUTES]
    wires = [tube(p,WIRE_OD/2) for p in paths]
    trench = Part.makeCompound([tube(p,CHANNEL_RADIUS) for p in paths])
    # Original split floor, USB and screw clearances remain untouched.
    parts['right_tray'] = parts['right_tray'].cut(trench).removeSplitter()
    lip = union([box(44.55,68.3,6.1,.75,11.25,3.7), box(43.12,69.2,9.22,1.94,6.7,.97)]).cut(trench)
    parts['right_plate'] = parts['right_plate'].fuse(lip).cut(trench).removeSplitter()
    refs['Power_wire_internal_reserved'] = Part.makeCompound(wires)
    refs['Power_wire_GND_nominal'] = wires[0]
    refs['Power_wire_VBUS_nominal'] = wires[1]
    receipt['minimum_wire_surface_gap_mm'] = wires[0].distToShape(wires[1])[0]
    receipt['minimum_centerline_bend_radius_mm'] = [p[-1] for p in paths]
    return receipt
