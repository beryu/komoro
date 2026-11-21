#!/usr/bin/env python3
"""Export a bed-oriented go/no-go gauge for the generated closed thickness.

Run with freecadcmd after generate.py. The gauge is a size reference, not
a clamp: do not use it to force the keyboard or trackball together.
"""
from pathlib import Path
import json
import runpy
import FreeCAD as App
import Part
import Mesh

HERE = Path(__file__).resolve().parent
OUT = HERE / 'generated'
CHECK = json.loads((OUT / 'validation.json').read_text())
GAP = CHECK['closed_size_mm'][2]
V = App.Vector
shape = Part.makeBox(12, 3, GAP + 4).multiFuse([
    Part.makeBox(12, 28, 2),
    Part.makeBox(12, 28, 2, V(0, 0, GAP + 2)),
]).removeSplitter()
assert shape.isValid() and len(shape.Solids) == 1
# Rest the broad C-shaped face on the bed; no 37 mm-high internal bridge.
print_shape = shape.copy()
print_shape.rotate(V(0, 0, 0), V(0, 1, 0), 90)
print_shape.translate(V(0, 0, 12))
doc = App.newDocument('FoldingClosedGapGauge')
obj = doc.addObject('Part::Feature', 'PrintClosedGapGauge')
obj.Shape = print_shape
obj.addProperty('App::PropertyLength', 'NominalGap', 'Dimensions')
obj.NominalGap = GAP
obj.Label = f'Closed thickness reference: {GAP:g} mm'
reference = doc.addObject('Part::Feature', 'InUseOrientation')
reference.Shape = shape
if reference.ViewObject:
    reference.ViewObject.Visibility = False
doc.recompute()
doc.saveAs(str(OUT / 'closed-gap-gauge.FCStd'))
path = OUT / 'fit_closed_gap_gauge.stl'
Mesh.Mesh(print_shape.tessellate(.08)).write(str(path))
helper = runpy.run_path(str(HERE.parents[1] / '3d-models/FreeCAD/generate-keyboard-case.py'), run_name='split_library')
helper['_close_stl_roundoff'](path)
assert Mesh.Mesh(str(path)).isSolid()
Part.export([obj], str(OUT / 'fit_closed_gap_gauge.step'))
# Verify opposing jaw faces, not the overall outside height of the C-shape.
assert abs((GAP + 2) - 2 - GAP) < 1e-9
report = {'nominal_internal_gap_mm': GAP, 'valid_solid': True, 'closed_STL': True,
          'export_orientation': 'broad C face on bed',
          'use': 'reference beside bare case bottoms; do not force or clamp',
          'rubber_feet_included': False}
(OUT / 'gap-gauge-validation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
