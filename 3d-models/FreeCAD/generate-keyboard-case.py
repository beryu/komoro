#!/usr/bin/env python3
"""Generate the torabo-tsuki-om keyboard case with FreeCAD.

Run with FreeCAD's Python interpreter, not CPython::

    freecadcmd -c "exec(open('3d-models/FreeCAD/generate-keyboard-case.py').read())"

The KiCad board outline and footprint positions are the source of truth.  The
generated FCStd file deliberately contains named, simple Part::Feature objects
so it remains convenient to inspect and modify in the FreeCAD GUI.
"""

from __future__ import annotations

import math
import os
import re
import struct
from pathlib import Path

import FreeCAD as App
import Part
import Mesh


# ---------------------------------------------------------------------------
# Human-editable dimensions (all values are millimetres)
# ---------------------------------------------------------------------------

BOTTOM_THICKNESS = 1.5
TOP_THICKNESS = 1.5
PCB_THICKNESS = 1.6
PCB_CLEARANCE = 0.25
WALL_THICKNESS = 1.8

# The PCB is pressed against the underside of the top plate by a perimeter
# foam strip. A 1 mm-high rib can therefore reinforce a 1 mm-deep underside
# cable groove without meeting the PCB. Its path follows the gap between the
# two rows of Choc sockets nearest the split-cable connector.
CABLE_RIB_WIDTH = 9.0
CABLE_RIB_HEIGHT = 1.0
CABLE_GROOVE_WIDTH = 7.0
CABLE_GROOVE_DEPTH = 1.0
CABLE_GROOVE_EDGE_CHAMFER = 0.4
CABLE_GROOVE_TURN_RADIUS = 2.0
# The back-side socket outline in the 17 mm Choc footprint extends from
# local Y=1.35 to 8.25 mm and local X=-7.3 to +2.3 mm in the board file.
SOCKET_LOCAL_Y_NEAR = 1.35
SOCKET_LOCAL_Y_FAR = 8.25
SOCKET_LOCAL_X_MIN = -7.3
SOCKET_LOCAL_X_MAX = 2.3
SOCKET_COLUMN_PITCH = 17.0

# The tray wall height beyond the 1.6 mm PCB thickness. The PCB reference is
# now placed against the plate underside, supported by compressed perimeter
# foam; this value still sets the existing tray and plate separation.
TOP_PLATE_GAP = 3.0

# Size the 20 switch cutouts in the 3D-printed top plate to 14.2 x 14.0 mm.
# The former 13.6 mm square required excessive force to insert switches.
SWITCH_WINDOW_X = 14.2
SWITCH_WINDOW_Y = 14.0

# The white component area of the XIAO that should remain visible.  Local X is
# along the 21 mm side of the XIAO footprint; local Y is along its 17.8 mm side.
# The Plus v2 STEP's white label is 10.2 x 12.2 mm and the metal shield below
# it is 10.6 x 12.6 mm. The top opening masks the black border while the wider
# underside pocket clears the shield; the resulting masking lip is 0.3 mm tall.
XIAO_WHITE_WINDOW = (10.5, 12.5)
XIAO_WHITE_WINDOW_OFFSET = (-1.4, 0.0)
XIAO_WHITE_SHIELD_POCKET = (11.2, 13.2)
XIAO_WHITE_SHIELD_HEIGHT_FROM_PADS = 3.2
XIAO_WHITE_SHIELD_VERTICAL_CLEARANCE = 0.1

# The XIAO is surface-mounted on top of the main PCB. Seeed's official
# nRF52840 3D model measures 4.21 mm from its mounting datum to the tallest
# component. The physical USB-C shell reaches about local X=+12.3 mm while the
# antenna end is near X=-10.5 mm, so the cover envelope must not be centred on
# the footprint. Use a conservative 23.5 mm envelope shifted 0.5 mm toward USB,
# with 0.5 mm horizontal print clearance per side and extra vertical margin.
XIAO_ASSEMBLY_BODY = (23.5, 17.8)
XIAO_ASSEMBLY_CENTER_OFFSET = (0.5, 0.0)
XIAO_HORIZONTAL_CLEARANCE = 1.0
XIAO_ASSEMBLY_HEIGHT = 4.8
XIAO_VERTICAL_CLEARANCE = 0.8

# Cable opening centred on the USB-C receptacle at the +X end of the XIAO.
# The dimensions include print/cable-shell clearance; the long tunnel cuts
# through both the local XIAO cover and whichever case perimeter wall lies in
# front of it.
# A 12 mm opening also clears the moulded shoulder of typical USB-C plugs and
# avoids a thin angled remnant where the left case perimeter meets the tunnel.
XIAO_USB_OPENING_WIDTH = 12.0
XIAO_USB_OPENING_HEIGHT = 5.5
XIAO_USB_OPENING_LENGTH = 24.0
XIAO_USB_INWARD_OVERLAP = 1.0
XIAO_USB_CENTER_HEIGHT = 3.0
# The XIAO PCB raises the receptacle above the module mounting datum. The
# bottom-tray wall therefore only needs to be opened from this height upward;
# the taller top-cover cutter remains centred on the connector shell.
XIAO_USB_BOTTOM_ABOVE_DATUM = 0.9

# The supplied XIAO nRF52840 Plus v2 STEP has a USB shell 8.94 mm wide,
# reaching 4.21 mm above its datum (the bottom pads extend to -0.20 mm).
# The normal assembled position already clears the cover, but when the module
# is seated against the inverted top plate its metal shell needs a deeper
# local pocket. Keep 0.5 mm over the shell and a full-thickness roof above it.
XIAO_USB_SHELL_HEIGHT_FROM_PADS = 4.41
XIAO_USB_SEATING_CLEARANCE = 0.5
# The shell narrows near its top: 8.94 mm wide below, about 8.3 mm at 3.8 mm
# above its datum. Use a narrow raised roof over the connector, with the reset
# and LED access holes outside its high centre. The existing 12 mm cable exit
# remains at the case wall but does not widen this raised pocket.
XIAO_USB_HOOD_START_X = 4.2
XIAO_USB_HOOD_END_X = 16.8
# Stop the raised hood before the receptacle mouth (STEP local X ~= 12.3 mm).
# A full-height notch from here outward leaves room for a USB-C plug body.
XIAO_USB_PLUG_NOTCH_START_X = 11.5
XIAO_USB_PLUG_NOTCH_WIDTH = 12.0
XIAO_USB_HOOD_BASE_WIDTH = 11.8
XIAO_USB_HOOD_MID_WIDTH = 10.6
XIAO_USB_HOOD_TOP_WIDTH = 8.4
XIAO_USB_POCKET_BASE_WIDTH = 9.8
XIAO_USB_POCKET_MID_WIDTH = 8.8
XIAO_USB_POCKET_TOP_WIDTH = 6.8

# Reset and LED positions are expressed in the XIAO footprint's local
# coordinate system. Coordinates come from Seeed's official XIAO nRF52840 Plus
# v1.1 KiCad PCB (K1, RGB6, and CHG0). The reset hole is intentionally generous
# enough for a 1.5 mm pin tool.
XIAO_RESET_OFFSET = (8.5725, -5.715)
XIAO_RESET_DIAMETER = 3.0
XIAO_LED_OFFSETS = ((7.6835, 5.715), (9.8425, 5.715))
XIAO_LED_DIAMETER = 2.2

# The keyed FTSH body is 5.08 x 7.54 mm. Its footprint origin is pin 1,
# 0.635 mm left and 3.175 mm above the body centre in KiCad coordinates.
# The FFSD-06 socket is 5.08 x (6 * 1.27 + 4.19) = 5.08 x 11.81 mm in
# Samtec's series drawing. Leave roughly 0.6 mm per side for printed clearance
# and let the ribbon leave upward without trapping it under the switch plate.
SPLIT_HEADER_BODY_CENTER_OFFSET = (0.635, 3.175)
SPLIT_CABLE_OPENING = (6.4, 13.0)

# The first straight segment of the right PCB recess is 34 mm wide, but the
# cutout continues another switch-column pitch to the right. Fill that space
# so the separate trackball case can move right. Reuse the former 44.2 mm slot
# length. The case's front rim is 18 mm north of its forward fixing-hole row;
# move that row south so the rim clears the recess wall by at least 2 mm.
# Leave a 2.5 mm lip south of the shifted mounting slot.
TRACKBALL_RECESS_MIN_WIDTH = 30.0
TRACKBALL_FLOOR_EXTRA_WIDTH = 17.0
TRACKBALL_FLOOR_CORNER_RADIUS = 2.0
TRACKBALL_MOUNT_SLOT_WIDTH = 44.2
TRACKBALL_MOUNT_SLOT_DEPTH = 2.4
TRACKBALL_MOUNT_FRONT_LIP = 2.8
TRACKBALL_MOUNT_SLOT_SOUTH_SHIFT = 5.0
TRACKBALL_MOUNT_SOUTH_LIP = 2.5
TRACKBALL_FLOOR_SOUTH_EXTENSION = (
    TRACKBALL_MOUNT_SLOT_SOUTH_SHIFT
    - TRACKBALL_MOUNT_FRONT_LIP
    + TRACKBALL_MOUNT_SOUTH_LIP
)

# Bottom-side head recess for the M2 x 3.5 mm FX-0235EB low-profile screws
# referenced by build-guide.md. The manufacturer lists a 4.0 mm head diameter
# and 0.3 mm head height. Add 0.2 mm diametral and 0.1 mm depth clearance for
# printing. Since the screw position is adjustable along the mount slot, the
# shallow flat-bottom recess follows the full slot instead of using fixed round
# counterbores. This is not a conical countersink.
TRACKBALL_SCREW_HEAD_DIAMETER = 4.0
TRACKBALL_SCREW_HEAD_CLEARANCE = 0.2
TRACKBALL_SCREW_HEAD_RECESS_DEPTH = 0.4

# Only an edge-on FFC cable passes through the rear wall of the trackball
# recess, below the lower-right corner of the third switch column from the
# right. The former 13.8 mm window's quarter-width sets a 3.45 mm cable path.
# Keep this independent from later switch-window fit tuning.
# This is deliberately much narrower than the FFC adapter footprint because
# the connector itself remains inside the case.
FFC_WALL_OPENING_WIDTH = 3.45
FFC_WALL_CLEARANCE = 0.3
# Start from the previous switch-window-based centre, then move left only as
# needed to keep the full width on the straight PCB edge before its corner.
FFC_WALL_OPENING_CENTER_OFFSET = 3 * 13.6 / 8

# The four former mounting-hole centres per side now lie outside the PCB. The
# routed Edge.Cuts reliefs clear a 4.6 mm boss at these positions.
MOUNT_CENTERS = {
    "left": ((95.5, 41.5), (10.5, 45.5), (134.0, 115.5), (10.5, 115.5)),
    "right": ((79.3, 116.5), (164.3, 190.5), (40.8, 190.5), (164.3, 120.5)),
}
SCREW_BOSS_DIAMETER = 4.6
CASE_SCREW_LENGTH = 3.5
M2_INSERT_PILOT_DIAMETER = 3.2
M2_INSERT_PILOT_DEPTH = 4.0
M2_TOP_CLEARANCE_DIAMETER = 2.4

# The reference left case has four top-open pockets for 12 x 1 mm magnets.
# Its measured pocket diameter is 12.1 mm (0.1 mm diametral clearance), with
# a 1.0 mm depth in a 1.5 mm floor. The left-hand centres follow the stepped
# outer contour rather than forming a rectangle. Mirror them across the case
# width on the right, so each pocket meets its mate bottom-to-bottom.
MAGNET_POCKET_DIAMETER = 12.1
MAGNET_POCKET_DEPTH = 1.0
MAGNET_MIRROR_X = 128.5
# At these x positions the outer left/right edges are -2.05/130.55 mm;
# the lower edge is -2.05 mm, and the stepped upper edge is 70.05/74.05 mm.
# Each centre is 13.05 mm from its two adjacent edges: radius 6.05 + gap 7.0.
LEFT_MAGNET_POCKET_CENTERS = (
    (11.0, 11.0), (11.0, 57.0),
    (117.5, 11.0), (117.5, 61.0),
)

SIDES = ("left", "right")
PCB_FILENAMES = {
    side: f"torabo-tsuki-lp-S-ortho-mini-{side}.kicad_pcb" for side in SIDES
}

SCRIPT_RELATIVE_PATH = Path("3d-models/FreeCAD/generate-keyboard-case.py")
REQUIRED_PCB = Path("pcb") / PCB_FILENAMES["left"]


def _tokenize(text: str):
    """Yield the small subset of S-expression tokens used by KiCad."""
    pattern = re.compile(r'"(?:\\.|[^"\\])*"|\(|\)|[^\s()]+')
    for match in pattern.finditer(text):
        token = match.group(0)
        if token.startswith('"'):
            yield token[1:-1].replace(r'\"', '"').replace("\\\\", "\\")
        else:
            yield token


def _parse_sexpr(text: str):
    stack = []
    root = None
    for token in _tokenize(text):
        if token == "(":
            node = []
            if stack:
                stack[-1].append(node)
            stack.append(node)
            if root is None:
                root = node
        elif token == ")":
            if not stack:
                raise ValueError("unmatched ')' in KiCad file")
            stack.pop()
        else:
            if not stack:
                raise ValueError("token outside S-expression")
            stack[-1].append(token)
    if stack:
        raise ValueError("unterminated S-expression in KiCad file")
    return root


def _children(node, name):
    return [item for item in node if isinstance(item, list) and item and item[0] == name]


def _child(node, name):
    found = _children(node, name)
    return found[0] if found else None


def _number(value):
    return float(value)


def _xy(node, name):
    item = _child(node, name)
    if item is None or len(item) < 3:
        raise ValueError(f"missing ({name} x y)")
    return (_number(item[1]), _number(item[2]))


def _distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _ordered_edges(records, tolerance=0.0001):
    """Order and orient unordered Edge.Cuts line/arc records into one loop."""
    if not records:
        raise ValueError("no Edge.Cuts geometry found")
    # Routed screw reliefs include segments shorter than 0.02 mm. A larger
    # matching tolerance skips those segments and leaves an open wire.
    remaining = list(records[1:])
    ordered = [records[0]]
    while remaining:
        tail = ordered[-1]["end"]
        for index, record in enumerate(remaining):
            if _distance(tail, record["start"]) <= tolerance:
                ordered.append(record)
                remaining.pop(index)
                break
            if _distance(tail, record["end"]) <= tolerance:
                reversed_record = dict(record)
                reversed_record["start"], reversed_record["end"] = (
                    record["end"],
                    record["start"],
                )
                ordered.append(reversed_record)
                remaining.pop(index)
                break
        else:
            raise ValueError(
                f"Edge.Cuts is not one connected loop near {tail}; "
                f"{len(remaining)} segment(s) remain"
            )
    if _distance(ordered[-1]["end"], ordered[0]["start"]) > tolerance:
        raise ValueError("Edge.Cuts loop is not closed")
    return ordered


def _board_data(path: Path):
    root = _parse_sexpr(path.read_text(encoding="utf-8"))
    records = []
    footprints = []

    for item in root:
        if not isinstance(item, list) or not item:
            continue
        if item[0] in ("gr_line", "gr_arc"):
            layer = _child(item, "layer")
            if not layer or len(layer) < 2 or layer[1] != "Edge.Cuts":
                continue
            record = {
                "kind": item[0],
                "start": _xy(item, "start"),
                "end": _xy(item, "end"),
            }
            if item[0] == "gr_arc":
                record["mid"] = _xy(item, "mid")
            records.append(record)
        elif item[0] == "footprint":
            at = _child(item, "at")
            if at is None:
                continue
            reference = ""
            for prop in _children(item, "property"):
                if len(prop) >= 3 and prop[1] == "Reference":
                    reference = prop[2]
                    break
            footprints.append(
                {
                    "name": item[1],
                    "reference": reference,
                    "layer": (_child(item, "layer") or ["layer", ""])[1],
                    "x": _number(at[1]),
                    "y": _number(at[2]),
                    "angle": _number(at[3]) if len(at) > 3 else 0.0,
                }
            )

    records = _ordered_edges(records)
    points = [r["start"] for r in records] + [records[-1]["end"]]
    min_x = min(p[0] for p in points)
    max_y = max(p[1] for p in points)

    # KiCad Y grows downwards. Reflect it so the FreeCAD top view matches the
    # physical board while keeping a conventional right-handed coordinate set.
    def transform(point):
        return (point[0] - min_x, max_y - point[1])

    for record in records:
        record["start"] = transform(record["start"])
        record["end"] = transform(record["end"])
        if "mid" in record:
            record["mid"] = transform(record["mid"])
    for footprint in footprints:
        footprint["cad_x"], footprint["cad_y"] = transform(
            (footprint["x"], footprint["y"])
        )
        # Reflecting both the board Y coordinate above and the footprint-local
        # Y coordinate in _local_point() preserves KiCad's rotation angle.
        # Negating it here would mirror asymmetric local features (such as the
        # XIAO reset button and LEDs) onto the antenna end of the footprint.
        footprint["cad_angle"] = footprint["angle"]

    return {
        "records": records,
        "footprints": footprints,
        "origin_x": min_x,
        "origin_max_y": max_y,
        "transform": transform,
    }


def _wire_from_records(records):
    edges = []
    for record in records:
        start = App.Vector(*record["start"], 0)
        end = App.Vector(*record["end"], 0)
        if record["kind"] == "gr_line":
            edges.append(Part.makeLine(start, end))
        else:
            mid = App.Vector(*record["mid"], 0)
            edges.append(Part.Arc(start, mid, end).toShape())
    return Part.Wire(edges)


def _largest_wire(shape):
    wires = list(shape.Wires)
    if not wires:
        raise ValueError("2D offset did not produce a wire")
    return max(wires, key=lambda wire: abs(Part.Face(wire).Area))


def _offset_wire(wire, distance):
    """Return an outward offset regardless of the source loop orientation."""
    candidates = []
    for signed_distance in (distance, -distance):
        result = wire.makeOffset2D(signed_distance, 0, False, False, False)
        candidate = result if result.ShapeType == "Wire" else _largest_wire(result)
        candidates.append(candidate)
    return max(candidates, key=lambda candidate: abs(Part.Face(candidate).Area))


def _rotated_box(width, height, x, y, angle, z=0.0, depth=1.0):
    box = Part.makeBox(width, height, depth, App.Vector(-width / 2, -height / 2, z))
    box.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), angle)
    box.translate(App.Vector(x, y, 0))
    return box


def _rotated_rectangle_face(width, height, x, y, angle):
    face = Part.makePlane(
        width,
        height,
        App.Vector(-width / 2, -height / 2, 0),
    )
    face.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), angle)
    face.translate(App.Vector(x, y, 0))
    return face


def _local_point(footprint, offset):
    angle = math.radians(footprint["cad_angle"])
    # KiCad's local footprint coordinates use the same downward-positive Y
    # convention as the board. The board import reflects Y for FreeCAD, so the
    # local offset must be reflected as well before applying the CAD rotation.
    dx, kicad_dy = offset
    dy = -kicad_dy
    return (
        footprint["cad_x"] + dx * math.cos(angle) - dy * math.sin(angle),
        footprint["cad_y"] + dx * math.sin(angle) + dy * math.cos(angle),
    )


def _cable_track_face(data, split_header, outer_face, width):
    """Build a strip centred between adjacent back-side socket rows."""
    columns = {}
    for fp in data["footprints"]:
        if "CHOC_V2_SOCKET_HANDSOLDERING_17mm" not in fp["name"]:
            continue
        if fp["layer"] != "B.Cu" or abs(fp["cad_angle"]) > 0.001:
            raise ValueError("cable track requires unrotated back-side Choc sockets")
        columns.setdefault(round(fp["cad_x"], 4), []).append(fp["cad_y"])

    # The two magnet rows bound the usable central band. A path closer to the
    # connector would run into the upper magnets at the short edges.
    magnet_radius = MAGNET_POCKET_DIAMETER / 2
    lower_magnets = [y for _, y in LEFT_MAGNET_POCKET_CENTERS if y < 30]
    upper_magnets = [y for _, y in LEFT_MAGNET_POCKET_CENTERS if y > 30]
    safe_min = max(lower_magnets) + magnet_radius + width / 2 + 0.5
    safe_max = min(upper_magnets) - magnet_radius - width / 2 - 0.5

    candidates = []
    for x, rows in columns.items():
        rows = sorted(rows, reverse=True)
        for high, low in zip(rows, rows[1:]):
            if abs(high - low - SOCKET_COLUMN_PITCH) > 0.05:
                continue
            # In CAD Y, the mirrored back-side socket occupies
            # [row_y - 8.25, row_y - 1.35].
            near_edge = low - SOCKET_LOCAL_Y_NEAR
            far_edge = high - SOCKET_LOCAL_Y_FAR
            center_y = (near_edge + far_edge) / 2
            if safe_min <= center_y <= safe_max:
                candidates.append((x, center_y))

    if not candidates:
        raise ValueError("no magnet-clear socket corridor for the cable track")
    _, anchor_y = min(
        candidates,
        key=lambda item: (abs(item[0] - split_header["cad_x"]),
                          abs(item[1] - split_header["cad_y"])),
    )
    centers = []
    for x in sorted(columns):
        options = [y for column_x, y in candidates if column_x == x]
        if options:
            y = min(options, key=lambda value: abs(value - anchor_y))
            if abs(y - anchor_y) <= 7.5:
                centers.append((x, y))
    if len(centers) < 3:
        raise ValueError("too few socket columns to define cable track")

    # Hold each centre within its socket column and change Y only in the
    # between-column space. Both halves must use the same track when one is
    # mirrored bottom-to-bottom, so include the socket's X envelope and its
    # mirrored envelope at every column.
    x_min = outer_face.BoundBox.XMin - 1.0
    x_max = outer_face.BoundBox.XMax + 1.0
    socket_half_span = max(abs(SOCKET_LOCAL_X_MIN), abs(SOCKET_LOCAL_X_MAX))
    path = [(x_min, centers[0][1])]
    for x, y in centers:
        path.extend(((x - socket_half_span, y),
                     (x + socket_half_span, y)))
    path.append((x_max, centers[-1][1]))
    if any(b[0] <= a[0] for a, b in zip(path, path[1:])):
        raise ValueError("socket columns do not define an increasing cable path")
    lower = [App.Vector(x, y - width / 2, 0) for x, y in path]
    upper = [App.Vector(x, y + width / 2, 0) for x, y in reversed(path)]
    return Part.Face(Part.makePolygon(lower + upper + [lower[0]]))


def _chamfer_cable_groove_edges(shape, track):
    """Cut straight bevels at the cable-contacting groove mouth."""
    tolerance = 0.005
    y_min = track.BoundBox.YMin - tolerance
    y_max = track.BoundBox.YMax + tolerance
    edges = []
    for edge in shape.Edges:
        box = edge.BoundBox
        if box.YMin < y_min or box.YMax > y_max:
            continue
        if abs(box.ZMax) < tolerance:
            edges.append(edge)
    if not edges:
        raise ValueError("could not find the cable groove edges to round")
    chamfered = shape.makeChamfer(CABLE_GROOVE_EDGE_CHAMFER, edges)
    if not chamfered.isValid() or len(chamfered.Solids) != 1:
        raise ValueError("cable groove edge chamfer is not a valid solid")
    return chamfered


def _local_profile_prism(footprint, start_x, end_x, profile):
    """Extrude a local Y/Z connector section along the footprint's X axis."""
    points = []
    for local_y, z in profile:
        x, y = _local_point(footprint, (start_x, local_y))
        points.append(App.Vector(x, y, z))
    face = Part.Face(Part.makePolygon(points + [points[0]]))
    angle = math.radians(footprint["cad_angle"])
    return face.extrude(App.Vector(
        (end_x - start_x) * math.cos(angle),
        (end_x - start_x) * math.sin(angle), 0))


def _add_feature(doc, group, name, label, shape, color):
    obj = doc.addObject("PartDesign::Feature", name)
    obj.Label = label
    obj.Shape = shape
    if obj.ViewObject is not None:
        obj.ViewObject.ShapeColor = color
    group.addObject(obj)
    return obj


def _add_dimension_properties(obj):
    properties = {
        "BottomThickness": BOTTOM_THICKNESS,
        "TopThickness": TOP_THICKNESS,
        "PcbThickness": PCB_THICKNESS,
        "PcbClearance": PCB_CLEARANCE,
        "WallThickness": WALL_THICKNESS,
        "TopPlateGap": TOP_PLATE_GAP,
        "CableRibWidth": CABLE_RIB_WIDTH,
        "CableRibHeight": CABLE_RIB_HEIGHT,
        "CableGrooveWidth": CABLE_GROOVE_WIDTH,
        "CableGrooveDepth": CABLE_GROOVE_DEPTH,
        "CableGrooveEdgeChamfer": CABLE_GROOVE_EDGE_CHAMFER,
        "CableGrooveTurnRadius": CABLE_GROOVE_TURN_RADIUS,
        "SwitchWindowX": SWITCH_WINDOW_X,
        "SwitchWindowY": SWITCH_WINDOW_Y,
        "XiaoAssemblyHeight": XIAO_ASSEMBLY_HEIGHT,
        "XiaoHorizontalClearance": XIAO_HORIZONTAL_CLEARANCE,
        "XiaoVerticalClearance": XIAO_VERTICAL_CLEARANCE,
        "XiaoUsbOpeningWidth": XIAO_USB_OPENING_WIDTH,
        "XiaoUsbOpeningHeight": XIAO_USB_OPENING_HEIGHT,
        "XiaoUsbBottomAboveDatum": XIAO_USB_BOTTOM_ABOVE_DATUM,
        "XiaoUsbSeatingClearance": XIAO_USB_SEATING_CLEARANCE,
        "XiaoUsbHoodBaseWidth": XIAO_USB_HOOD_BASE_WIDTH,
        "XiaoUsbHoodTopWidth": XIAO_USB_HOOD_TOP_WIDTH,
        "XiaoUsbPocketBaseWidth": XIAO_USB_POCKET_BASE_WIDTH,
        "XiaoUsbPlugNotchStartX": XIAO_USB_PLUG_NOTCH_START_X,
        "XiaoUsbPlugNotchWidth": XIAO_USB_PLUG_NOTCH_WIDTH,
        "XiaoWhiteWindowLength": XIAO_WHITE_WINDOW[0],
        "XiaoWhiteWindowWidth": XIAO_WHITE_WINDOW[1],
        "XiaoResetDiameter": XIAO_RESET_DIAMETER,
        "XiaoLedDiameter": XIAO_LED_DIAMETER,
        "SplitCableOpeningWidth": SPLIT_CABLE_OPENING[0],
        "SplitCableOpeningLength": SPLIT_CABLE_OPENING[1],
        "TrackballMountSlotWidth": TRACKBALL_MOUNT_SLOT_WIDTH,
        "TrackballFloorExtraWidth": TRACKBALL_FLOOR_EXTRA_WIDTH,
        "TrackballFloorSouthExtension": TRACKBALL_FLOOR_SOUTH_EXTENSION,
        "TrackballFloorCornerRadius": TRACKBALL_FLOOR_CORNER_RADIUS,
        "TrackballMountSlotDepth": TRACKBALL_MOUNT_SLOT_DEPTH,
        "TrackballMountFrontLip": TRACKBALL_MOUNT_FRONT_LIP,
        "TrackballMountSlotSouthShift": TRACKBALL_MOUNT_SLOT_SOUTH_SHIFT,
        "TrackballMountSouthLip": TRACKBALL_MOUNT_SOUTH_LIP,
        "TrackballScrewHeadDiameter": TRACKBALL_SCREW_HEAD_DIAMETER,
        "TrackballHeadRecessDepth": TRACKBALL_SCREW_HEAD_RECESS_DEPTH,
        "FfcWallOpeningWidth": FFC_WALL_OPENING_WIDTH,
        "ScrewBossDiameter": SCREW_BOSS_DIAMETER,
        "CaseScrewLength": CASE_SCREW_LENGTH,
        "M2InsertPilotDiameter": M2_INSERT_PILOT_DIAMETER,
        "M2InsertPilotDepth": M2_INSERT_PILOT_DEPTH,
        "M2TopClearanceDiameter": M2_TOP_CLEARANCE_DIAMETER,
        "MagnetPocketDiameter": MAGNET_POCKET_DIAMETER,
        "MagnetPocketDepth": MAGNET_POCKET_DEPTH,
    }
    for name, value in properties.items():
        obj.addProperty("App::PropertyLength", name, "Case dimensions")
        setattr(obj, name, value)
    obj.addProperty("App::PropertyString", "Source", "Generation")
    obj.Source = "generate-keyboard-case.py (edit script values, then regenerate)"


def _close_stl_roundoff(path: Path):
    """Weld sub-micron tessellation gaps at the routed right PCB corner."""
    data = path.read_bytes()
    count = struct.unpack_from("<I", data, 80)[0]
    if len(data) != 84 + 50 * count:
        raise ValueError(f"not a binary STL: {path}")
    facets = []
    for index in range(count):
        normal = data[84 + 50 * index:96 + 50 * index]
        vertices = [
            tuple(round(value, 4) for value in struct.unpack_from(
                "<fff", data, 96 + 50 * index + 12 * vertex))
            for vertex in range(3)
        ]
        if len(set(vertices)) < 3:
            continue
        facets.append(normal + b"".join(struct.pack("<fff", *v) for v in vertices)
                      + data[132 + 50 * index:134 + 50 * index])
    path.write_bytes(data[:80] + struct.pack("<I", len(facets)) + b"".join(facets))
    if not Mesh.Mesh(str(path)).isSolid():
        raise ValueError(f"STL mesh is not closed: {path}")


def _make_side(doc, repo_root: Path, side: str, *, legacy_bottom_features=True):
    pcb_path = repo_root / "pcb" / PCB_FILENAMES[side]
    data = _board_data(pcb_path)
    pcb_wire = _wire_from_records(data["records"])
    pcb_face = Part.Face(pcb_wire)
    cavity_wire = _offset_wire(pcb_wire, PCB_CLEARANCE)
    outer_wire = _offset_wire(pcb_wire, PCB_CLEARANCE + WALL_THICKNESS)
    cavity_face = Part.Face(cavity_wire)
    outer_face = Part.Face(outer_wire)

    xiaos = [fp for fp in data["footprints"] if "XIAO-nRF52840-Plus" in fp["name"]]
    if len(xiaos) != (1 if side == "right" else 0):
        raise ValueError(f"unexpected XIAO count on {side}: {len(xiaos)}")
    xiao = xiaos[0] if xiaos else None
    xiao_assembly_center = _local_point(xiao, XIAO_ASSEMBLY_CENTER_OFFSET) if xiao else None
    split_headers = [fp for fp in data["footprints"]
                     if "Samtec_FTSH-106-01-L-D-K" in fp["name"] and fp["layer"] == "F.Cu"]
    if len(split_headers) != 1:
        raise ValueError(f"expected one FTSH header on {side}, found {len(split_headers)}")
    split_header = split_headers[0]
    split_header_center = _local_point(split_header, SPLIT_HEADER_BODY_CENTER_OFFSET)
    mounting_holes = [{"cad_x": data["transform"](center)[0],
                       "cad_y": data["transform"](center)[1]}
                      for center in MOUNT_CENTERS[side]]
    case_outer_face = outer_face
    case_cavity_face = cavity_face
    top_z = BOTTOM_THICKNESS + PCB_THICKNESS + TOP_PLATE_GAP
    pcb_bottom_z = top_z - PCB_THICKNESS

    side_group = doc.addObject("App::Part", side.capitalize())
    side_group.Label = f"{side.capitalize()} case"

    reference_group = doc.addObject("App::DocumentObjectGroup", f"{side}_References")
    reference_group.Label = "References (hidden)"
    side_group.addObject(reference_group)
    pcb_reference_shape = pcb_face.extrude(App.Vector(0, 0, PCB_THICKNESS))
    pcb_reference_shape.translate(App.Vector(0, 0, pcb_bottom_z))
    pcb_reference = _add_feature(
        doc, reference_group, f"{side}_PCB_reference",
        "PCB reference (1.6 mm)", pcb_reference_shape, (0.15, 0.55, 0.22))
    if pcb_reference.ViewObject is not None:
        pcb_reference.ViewObject.Transparency = 65
        pcb_reference.ViewObject.Visibility = False

    if xiao:
        xiao_reference = _add_feature(
            doc, reference_group, f"{side}_XIAO_reference",
            "XIAO nRF52840 Plus envelope reference",
            _rotated_box(XIAO_ASSEMBLY_BODY[0], XIAO_ASSEMBLY_BODY[1],
                         xiao_assembly_center[0], xiao_assembly_center[1],
                         xiao["cad_angle"], top_z,
                         XIAO_ASSEMBLY_HEIGHT), (0.92, 0.92, 0.92))
        if xiao_reference.ViewObject is not None:
            xiao_reference.ViewObject.Transparency = 55
            xiao_reference.ViewObject.Visibility = False
    header_reference = _add_feature(
        doc, reference_group, f"{side}_SplitHeader_reference",
        "FTSH header body reference",
        _rotated_box(5.08, 7.54, split_header_center[0], split_header_center[1],
                     split_header["cad_angle"], top_z,
                     TOP_PLATE_GAP + TOP_THICKNESS + 1.0), (0.15, 0.15, 0.15))
    if header_reference.ViewObject is not None:
        header_reference.ViewObject.Visibility = False
    bottom_group = doc.addObject("App::DocumentObjectGroup", f"{side}_Bottom")
    bottom_group.Label = "Bottom tray"
    side_group.addObject(bottom_group)

    bottom_shape = case_outer_face.extrude(App.Vector(0, 0, BOTTOM_THICKNESS))
    wall_height = PCB_THICKNESS + TOP_PLATE_GAP
    wall_ring = case_outer_face.cut(case_cavity_face).extrude(
        App.Vector(0, 0, wall_height)
    )
    wall_ring.translate(App.Vector(0, 0, BOTTOM_THICKNESS))

    rib_track = _cable_track_face(data, split_header, case_outer_face,
                                  CABLE_RIB_WIDTH)
    groove_track = _cable_track_face(data, split_header, case_outer_face,
                                     CABLE_GROOVE_WIDTH)
    cable_rib = rib_track.common(case_cavity_face).extrude(
        App.Vector(0, 0, CABLE_RIB_HEIGHT))
    cable_rib.translate(App.Vector(0, 0, BOTTOM_THICKNESS))
    cable_groove = groove_track.extrude(
        App.Vector(0, 0, CABLE_GROOVE_DEPTH + 0.01))
    cable_groove.translate(App.Vector(0, 0, -0.01))
    groove_corners = [
        edge for edge in cable_groove.Edges
        if edge.BoundBox.ZLength > CABLE_GROOVE_DEPTH
        and edge.BoundBox.XLength < 0.005
        and edge.BoundBox.YLength < 0.005
    ]
    cable_groove = cable_groove.makeFillet(
        CABLE_GROOVE_TURN_RADIUS, groove_corners)
    if not cable_groove.isValid() or len(cable_groove.Solids) != 1:
        raise ValueError("rounded cable groove is not a valid solid")

    if xiao:
        xiao_usb_center = _local_point(xiao, (
            XIAO_ASSEMBLY_BODY[0] / 2 + XIAO_ASSEMBLY_CENTER_OFFSET[0]
            - XIAO_USB_INWARD_OVERLAP + XIAO_USB_OPENING_LENGTH / 2, 0.0))
        xiao_usb_opening = _rotated_box(
            XIAO_USB_OPENING_LENGTH, XIAO_USB_OPENING_WIDTH,
            xiao_usb_center[0], xiao_usb_center[1], xiao["cad_angle"],
            BOTTOM_THICKNESS + PCB_THICKNESS + XIAO_USB_CENTER_HEIGHT
            - XIAO_USB_OPENING_HEIGHT / 2, XIAO_USB_OPENING_HEIGHT)
        xiao_usb_bottom_z = BOTTOM_THICKNESS + PCB_THICKNESS + XIAO_USB_BOTTOM_ABOVE_DATUM
        wall_ring = wall_ring.cut(_rotated_box(
            XIAO_USB_OPENING_LENGTH, XIAO_USB_OPENING_WIDTH,
            xiao_usb_center[0], xiao_usb_center[1], xiao["cad_angle"],
            xiao_usb_bottom_z, top_z + 0.2 - xiao_usb_bottom_z))

    trackball_mount_floor = None
    trackball_mount_slot = None
    trackball_head_recess = None
    if side == "right":
        switch_columns = sorted(
            {
                round(fp["x"], 3)
                for fp in data["footprints"]
                if "CHOC_V2_SOCKET" in fp["name"]
            },
            reverse=True,
        )
        if len(switch_columns) != 7:
            raise ValueError(
                "expected seven right-hand switch columns, "
                f"found {len(switch_columns)}: {switch_columns}"
            )
        third_from_right = switch_columns[2]
        fourth_from_right = switch_columns[3]
        fifth_from_right = switch_columns[4]
        recess_probe_x = data["transform"](
            ((fourth_from_right + fifth_from_right) / 2, 0)
        )[0]

        # Find the first horizontal back edge of the U-shaped recess. The
        # outline continues one switch column farther right at a 0.6 mm
        # shallower depth; the support floor spans both portions.
        recess_edges = []
        for record in data["records"]:
            if record["kind"] != "gr_line":
                continue
            x1, y1 = record["start"]
            x2, y2 = record["end"]
            if abs(y1 - y2) > 0.02:
                continue
            xmin, xmax = sorted((x1, x2))
            if (
                xmin <= recess_probe_x <= xmax
                and xmax - xmin >= TRACKBALL_RECESS_MIN_WIDTH
                and y1 > 0.02
            ):
                recess_edges.append((y1, xmin, xmax))
        if not recess_edges:
            raise ValueError("could not find the right-hand trackball recess edge")
        recess_y, recess_xmin, recess_xmax = min(recess_edges)
        recess_width = recess_xmax - recess_xmin
        floor_width = recess_width + TRACKBALL_FLOOR_EXTRA_WIDTH
        if TRACKBALL_MOUNT_SLOT_WIDTH > floor_width - 4.0:
            raise ValueError(
                f"trackball mount slot is {TRACKBALL_MOUNT_SLOT_WIDTH} mm wide, "
                f"but the support floor is only {floor_width:.3f} mm"
            )

        # Extend the floor to the right by one 17 mm switch pitch. The last
        # 1.7 mm overlaps the existing base under the adjacent PCB edge.
        slot_left_x = recess_xmin + 2.0
        slot_center_x = slot_left_x + TRACKBALL_MOUNT_SLOT_WIDTH / 2
        slot_south_y = TRACKBALL_MOUNT_FRONT_LIP - TRACKBALL_MOUNT_SLOT_SOUTH_SHIFT
        trackball_mount_floor = Part.makeBox(
            floor_width,
            recess_y + TRACKBALL_FLOOR_SOUTH_EXTENSION,
            BOTTOM_THICKNESS,
            App.Vector(
                recess_xmin,
                -TRACKBALL_FLOOR_SOUTH_EXTENSION,
                0,
            ),
        )
        # Match the two exposed southern corners; leave the mounting slot and
        # the PCB outline corners unchanged.
        floor_corner_edges = [
            edge for edge in trackball_mount_floor.Edges
            if len(edge.Vertexes) == 2
            and edge.BoundBox.ZLength > BOTTOM_THICKNESS - 0.001
            and all(
                any(
                    abs(vertex.Point.x - corner_x) < 0.001
                    for corner_x in (recess_xmin, recess_xmin + floor_width)
                )
                and abs(vertex.Point.y + TRACKBALL_FLOOR_SOUTH_EXTENSION) < 0.001
                for vertex in edge.Vertexes
            )
        ]
        if len(floor_corner_edges) != 2:
            raise ValueError("could not find both exposed trackball floor corners")
        trackball_mount_floor = trackball_mount_floor.makeFillet(
            TRACKBALL_FLOOR_CORNER_RADIUS, floor_corner_edges)

        # Continue the adjustable mounting slot across the added column while
        # stopping before the side wall at the next PCB column.
        trackball_mount_slot = Part.makeBox(
            TRACKBALL_MOUNT_SLOT_WIDTH,
            TRACKBALL_MOUNT_SLOT_DEPTH,
            BOTTOM_THICKNESS + 0.2,
            App.Vector(
                slot_left_x,
                slot_south_y,
                -0.1,
            ),
        )
        head_recess_width = (
            TRACKBALL_MOUNT_SLOT_WIDTH
            + TRACKBALL_SCREW_HEAD_DIAMETER
            + TRACKBALL_SCREW_HEAD_CLEARANCE
            - TRACKBALL_MOUNT_SLOT_DEPTH
        )
        head_recess_depth = (
            TRACKBALL_SCREW_HEAD_DIAMETER + TRACKBALL_SCREW_HEAD_CLEARANCE
        )
        trackball_head_recess = Part.makeBox(
            head_recess_width,
            head_recess_depth,
            TRACKBALL_SCREW_HEAD_RECESS_DEPTH + 0.1,
            App.Vector(
                slot_center_x - head_recess_width / 2,
                slot_south_y
                + TRACKBALL_MOUNT_SLOT_DEPTH / 2
                - head_recess_depth / 2,
                -0.1,
            ),
        )

        # Pass only the FFC cable below the lower-right corner of the third
        # switch column from the right. The connector remains inside the case.
        third_column_cad_x = data["transform"]((third_from_right, 0))[0]
        desired_ffc_x = third_column_cad_x + FFC_WALL_OPENING_CENTER_OFFSET
        # The back edge steps from y=19.6 to y=19.0 at this column. Find the
        # actual straight edge under the key, then keep the complete slit clear
        # of the rounded corner at its right end.
        ffc_edges = []
        for record in data["records"]:
            if record["kind"] != "gr_line":
                continue
            x1, y1 = record["start"]
            x2, y2 = record["end"]
            xmin, xmax = sorted((x1, x2))
            if (
                abs(y1 - y2) < 0.02
                and xmin <= desired_ffc_x <= xmax
                and xmax - xmin >= FFC_WALL_OPENING_WIDTH + 0.4
                and 0.02 < y1 < recess_y
            ):
                ffc_edges.append((y1, xmin, xmax))
        if not ffc_edges:
            raise ValueError("could not find the FFC cable exit edge")
        ffc_edge_y, _, ffc_edge_xmax = min(ffc_edges)
        ffc_opening_center_x = min(
            desired_ffc_x,
            ffc_edge_xmax - FFC_WALL_OPENING_WIDTH / 2 - 0.2,
        )
        ffc_cutter_y = (ffc_edge_y - PCB_CLEARANCE - WALL_THICKNESS
                        - FFC_WALL_CLEARANCE)
        ffc_wall_opening = Part.makeBox(
            FFC_WALL_OPENING_WIDTH,
            WALL_THICKNESS + 2 * PCB_CLEARANCE + 2 * FFC_WALL_CLEARANCE,
            top_z - BOTTOM_THICKNESS + 0.1,
            App.Vector(
                ffc_opening_center_x - FFC_WALL_OPENING_WIDTH / 2,
                ffc_cutter_y,
                BOTTOM_THICKNESS,
            ),
        )

    bottom_shape = bottom_shape.fuse(wall_ring)
    if legacy_bottom_features:
        bottom_shape = bottom_shape.fuse(cable_rib).cut(cable_groove)
    if trackball_mount_floor is not None:
        bottom_shape = bottom_shape.fuse(trackball_mount_floor)
        bottom_shape = bottom_shape.cut(trackball_mount_slot)
        bottom_shape = bottom_shape.cut(trackball_head_recess)
        # Apply the notch after adding the floor, at z >= its top surface, so
        # the wall is open and the bottom retains its full 1.5 mm thickness.
        bottom_shape = bottom_shape.cut(ffc_wall_opening)

    for mounting_hole in mounting_holes:
        # The routed relief leaves part of each boss outside the floor outline.
        # Start at the print bed so that no portion overhangs the bottom face.
        boss = Part.makeCylinder(
            SCREW_BOSS_DIAMETER / 2,
            top_z,
            App.Vector(
                mounting_hole["cad_x"],
                mounting_hole["cad_y"],
                0,
            ),
        )
        # Drill from the current boss top so the 4 mm pilot remains 4 mm deep
        # when the tray wall height changes.
        pilot_hole = Part.makeCylinder(
            M2_INSERT_PILOT_DIAMETER / 2,
            M2_INSERT_PILOT_DEPTH + 0.1,
            App.Vector(
                mounting_hole["cad_x"],
                mounting_hole["cad_y"],
                top_z - M2_INSERT_PILOT_DEPTH,
            ),
        )
        bottom_shape = bottom_shape.fuse(boss).cut(pilot_hole)

    # Open the magnet pockets from the PCB side, leaving 0.5 mm of floor.
    magnet_centers = (
        LEFT_MAGNET_POCKET_CENTERS if side == "left" else
        tuple((MAGNET_MIRROR_X - x, y) for x, y in LEFT_MAGNET_POCKET_CENTERS)
    )
    for x, y in (magnet_centers if legacy_bottom_features else ()):
        pocket = Part.makeCylinder(
            MAGNET_POCKET_DIAMETER / 2,
            MAGNET_POCKET_DEPTH + 0.1,
            App.Vector(x, y, BOTTOM_THICKNESS - MAGNET_POCKET_DEPTH),
        )
        bottom_shape = bottom_shape.cut(pocket)

    if legacy_bottom_features:
        bottom_shape = _chamfer_cable_groove_edges(bottom_shape, groove_track)

    bottom_obj = _add_feature(
        doc,
        bottom_group,
        f"{side}_BottomTray",
        f"{side.capitalize()} bottom tray",
        bottom_shape,
        (0.18, 0.32, 0.72),
    )
    _add_dimension_properties(bottom_obj)

    top_group = doc.addObject("App::DocumentObjectGroup", f"{side}_Top")
    top_group.Label = "Top plate"
    side_group.addObject(top_group)
    # The removable plate follows the current PCB perimeter.
    top_shape = case_outer_face.extrude(App.Vector(0, 0, TOP_THICKNESS))
    top_shape.translate(App.Vector(0, 0, top_z))

    cut_depth = TOP_THICKNESS + 0.4
    cut_z = top_z - 0.2

    # The FFSD socket and ribbon pass vertically through the top plate.
    top_shape = top_shape.cut(_rotated_box(
        SPLIT_CABLE_OPENING[0], SPLIT_CABLE_OPENING[1],
        split_header_center[0], split_header_center[1],
        split_header["cad_angle"], cut_z, cut_depth))

    if xiao:
        xiao_inner_width = XIAO_ASSEMBLY_BODY[0] + XIAO_HORIZONTAL_CLEARANCE
        xiao_inner_height = XIAO_ASSEMBLY_BODY[1] + XIAO_HORIZONTAL_CLEARANCE
        xiao_roof_inner_z = (BOTTOM_THICKNESS + PCB_THICKNESS
                             + XIAO_ASSEMBLY_HEIGHT + XIAO_VERTICAL_CLEARANCE)
        xiao_roof_top_z = xiao_roof_inner_z + TOP_THICKNESS
        xiao_cap_outer = _rotated_box(
            xiao_inner_width + 2 * WALL_THICKNESS,
            xiao_inner_height + 2 * WALL_THICKNESS,
            xiao_assembly_center[0], xiao_assembly_center[1],
            xiao["cad_angle"], top_z, xiao_roof_top_z - top_z)
        xiao_cap_cavity = _rotated_box(
            xiao_inner_width, xiao_inner_height,
            xiao_assembly_center[0], xiao_assembly_center[1],
            xiao["cad_angle"], top_z - 0.1,
            xiao_roof_inner_z - top_z + 0.1)
        usb_pocket_top_z = (top_z + XIAO_USB_SHELL_HEIGHT_FROM_PADS
                            + XIAO_USB_SEATING_CLEARANCE)
        usb_hood_top_z = usb_pocket_top_z + TOP_THICKNESS
        usb_hood_outer = _local_profile_prism(
            xiao, XIAO_USB_HOOD_START_X, XIAO_USB_HOOD_END_X,
            [(-XIAO_USB_HOOD_BASE_WIDTH / 2, xiao_roof_top_z - 0.1),
             (XIAO_USB_HOOD_BASE_WIDTH / 2, xiao_roof_top_z - 0.1),
             (XIAO_USB_HOOD_MID_WIDTH / 2, top_z + 4.4),
             (XIAO_USB_HOOD_TOP_WIDTH / 2, usb_hood_top_z),
             (-XIAO_USB_HOOD_TOP_WIDTH / 2, usb_hood_top_z),
             (-XIAO_USB_HOOD_MID_WIDTH / 2, top_z + 4.4)])
        # Follow the shell's rounded width reduction toward its top. The
        # lower 9.8 mm pocket clears the mounting wings; only the connector's
        # narrow crown needs to reach the high part of the hood.
        usb_pocket = _local_profile_prism(
            xiao, XIAO_USB_HOOD_START_X, XIAO_USB_HOOD_END_X,
            [(-XIAO_USB_POCKET_BASE_WIDTH / 2, top_z - 0.1),
             (XIAO_USB_POCKET_BASE_WIDTH / 2, top_z - 0.1),
             (XIAO_USB_POCKET_BASE_WIDTH / 2, top_z + 3.75),
             (XIAO_USB_POCKET_MID_WIDTH / 2, top_z + 4.4),
             (XIAO_USB_POCKET_TOP_WIDTH / 2, usb_pocket_top_z),
             (-XIAO_USB_POCKET_TOP_WIDTH / 2, usb_pocket_top_z),
             (-XIAO_USB_POCKET_MID_WIDTH / 2, top_z + 4.4),
             (-XIAO_USB_POCKET_BASE_WIDTH / 2, top_z + 3.75)])
        top_shape = top_shape.cut(_rotated_box(
            xiao_inner_width, xiao_inner_height,
            xiao_assembly_center[0], xiao_assembly_center[1],
            xiao["cad_angle"], cut_z, cut_depth)).fuse(
                xiao_cap_outer.fuse(usb_hood_outer).cut(
                    xiao_cap_cavity.fuse(usb_pocket)))
        top_shape = top_shape.cut(xiao_usb_opening)
        # The lower cable tunnel alone leaves a roof tongue beyond the USB-C
        # mouth, blocking the moulded part of a plug. Open that central region
        # through the full hood height while retaining its side walls.
        top_shape = top_shape.cut(_local_profile_prism(
            xiao, XIAO_USB_PLUG_NOTCH_START_X,
            XIAO_ASSEMBLY_BODY[0] / 2 + XIAO_ASSEMBLY_CENTER_OFFSET[0]
            - XIAO_USB_INWARD_OVERLAP + XIAO_USB_OPENING_LENGTH,
            [(-XIAO_USB_PLUG_NOTCH_WIDTH / 2, top_z - 0.1),
             (XIAO_USB_PLUG_NOTCH_WIDTH / 2, top_z - 0.1),
             (XIAO_USB_PLUG_NOTCH_WIDTH / 2, usb_hood_top_z + 0.1),
             (-XIAO_USB_PLUG_NOTCH_WIDTH / 2, usb_hood_top_z + 0.1)]))

    switch_count = 0
    for footprint in data["footprints"]:
        if "CHOC_V2_SOCKET" not in footprint["name"]:
            continue
        switch_count += 1
        cutter = _rotated_box(
            SWITCH_WINDOW_X,
            SWITCH_WINDOW_Y,
            footprint["cad_x"],
            footprint["cad_y"],
            footprint["cad_angle"],
            cut_z,
            cut_depth,
        )
        top_shape = top_shape.cut(cutter)

    if xiao:
        window_center = _local_point(xiao, XIAO_WHITE_WINDOW_OFFSET)
        xiao_roof_cut_z = top_z - 0.2
        xiao_roof_cut_depth = usb_hood_top_z - xiao_roof_cut_z + 0.2
        shield_pocket_top_z = (top_z + XIAO_WHITE_SHIELD_HEIGHT_FROM_PADS
                               + XIAO_WHITE_SHIELD_VERTICAL_CLEARANCE)
        top_shape = top_shape.cut(_rotated_box(
            XIAO_WHITE_SHIELD_POCKET[0], XIAO_WHITE_SHIELD_POCKET[1],
            window_center[0], window_center[1], xiao["cad_angle"],
            xiao_roof_cut_z, shield_pocket_top_z - xiao_roof_cut_z))
        top_shape = top_shape.cut(_rotated_box(
            XIAO_WHITE_WINDOW[0], XIAO_WHITE_WINDOW[1],
            window_center[0], window_center[1], xiao["cad_angle"],
            shield_pocket_top_z - 0.1,
            usb_hood_top_z - shield_pocket_top_z + 0.3))
        reset_center = _local_point(xiao, XIAO_RESET_OFFSET)
        top_shape = top_shape.cut(Part.makeCylinder(
            XIAO_RESET_DIAMETER / 2, xiao_roof_cut_depth,
            App.Vector(reset_center[0], reset_center[1], xiao_roof_cut_z)))
        for offset in XIAO_LED_OFFSETS:
            center = _local_point(xiao, offset)
            top_shape = top_shape.cut(Part.makeCylinder(
                XIAO_LED_DIAMETER / 2, xiao_roof_cut_depth,
                App.Vector(center[0], center[1], xiao_roof_cut_z)))

    for mounting_hole in mounting_holes:
        # Fuse a complete pad over each routed screw relief, then drill it.
        screw_pad = Part.makeCylinder(
            SCREW_BOSS_DIAMETER / 2,
            TOP_THICKNESS,
            App.Vector(
                mounting_hole["cad_x"],
                mounting_hole["cad_y"],
                top_z,
            ),
        )
        screw_clearance = Part.makeCylinder(
            M2_TOP_CLEARANCE_DIAMETER / 2,
            TOP_THICKNESS + 0.4,
            App.Vector(
                mounting_hole["cad_x"],
                mounting_hole["cad_y"],
                cut_z,
            ),
        )
        top_shape = top_shape.fuse(screw_pad).cut(screw_clearance)

    top_obj = _add_feature(
        doc,
        top_group,
        f"{side}_TopPlate",
        f"{side.capitalize()} top plate ({switch_count} switch windows)",
        top_shape,
        (0.82, 0.82, 0.86),
    )
    _add_dimension_properties(top_obj)
    return bottom_obj, top_obj


def _find_repo_root():
    """Locate the checkout even when FreeCAD console omits ``__file__``."""
    candidates = []

    file_value = globals().get("__file__")
    if file_value and not str(file_value).startswith("<"):
        script_path = Path(file_value).expanduser().resolve()
        if len(script_path.parents) >= 3:
            candidates.append(script_path.parents[2])

    override = os.environ.get("TORABO_TSUKI_OM_ROOT")
    if override:
        candidates.append(Path(override).expanduser().resolve())

    current = Path.cwd().resolve()
    candidates.extend((current, *current.parents))

    # FreeCAD.app commonly starts its Python console with '/' as the working
    # directory. Search the conventional ghq location without hard-coding the
    # GitHub account name.
    ghq_root = Path.home() / "ghq" / "github.com"
    if ghq_root.is_dir():
        candidates.extend(ghq_root.glob("*/torabo-tsuki-om"))

    seen = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if (candidate / REQUIRED_PCB).is_file() and (
            candidate / SCRIPT_RELATIVE_PATH
        ).is_file():
            return candidate

    raise FileNotFoundError(
        "torabo-tsuki-om repository could not be located. Set "
        "TORABO_TSUKI_OM_ROOT to the repository's absolute path."
    )


def main():
    repo_root = _find_repo_root()
    script_path = repo_root / SCRIPT_RELATIVE_PATH
    output_dir = script_path.parent / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = App.newDocument("ToraboTsukiKeyboardCase")
    doc.Label = "torabo-tsuki-om keyboard case"
    generated = {}
    for side in SIDES:
        generated[side] = _make_side(doc, repo_root, side)

    doc.recompute()
    fcstd_path = output_dir / "torabo-tsuki-om-keyboard-case.FCStd"
    doc.saveAs(str(fcstd_path))

    for side, (bottom, top) in generated.items():
        for part, obj in (("bottom-tray", bottom), ("top-plate", top)):
            path = output_dir / f"{side}-{part}.stl"
            Mesh.export([obj], str(path))
            _close_stl_roundoff(path)
        Part.export([bottom], str(output_dir / f"{side}-bottom-tray.step"))
        Part.export([top], str(output_dir / f"{side}-top-plate.step"))

    print(f"Generated {fcstd_path}")
    for side, (bottom, top) in generated.items():
        print(
            f"  {side}: bottom {bottom.Shape.Volume:.1f} mm^3, "
            f"top {top.Shape.Volume:.1f} mm^3"
        )


if __name__ == "__main__":
    main()
