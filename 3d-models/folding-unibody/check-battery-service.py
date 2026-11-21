#!/usr/bin/env python3
"""Check the saved cover's lift path against the modified holder and contacts.

The holder and contact geometry is an assumption, not a measured part model.
Run after generate.py using FreeCAD's Python.
"""
from pathlib import Path
import hashlib, json, runpy
import FreeCAD as App
HERE=Path(__file__).resolve().parent
OUT=HERE/'generated'
lib=runpy.run_path(str(HERE/'generate.py'),run_name='geometry_library')
doc=App.openDocument(str(OUT/'folding-unibody-rev-a.FCStd'))
hooks=lib['battery_cap']()[1]
cover=doc.getObject('Print_battery_cap').Shape.cut(hooks)
refs=['AAA_holder_assumed','AAA_contact_keepout_assumed','AAA_cell_reference']
reserved=lib['union']([doc.getObject('Reference_'+n).Shape for n in refs])
report={'scope':'Released snap hooks; assumed resin-trimmed holder, metal-contact keepout and cell, not measured hardware.',
        'CAD_sha256':hashlib.sha256((OUT/'folding-unibody-rev-a.FCStd').read_bytes()).hexdigest(),
        'checker_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'references':refs,'lift_overlap_mm3':{}}
for height in (0,.5,2,5,15,25):
    overlap=cover.translated(App.Vector(0,0,height)).common(reserved).Volume
    assert overlap<.001,('Cover snags holder/contact/cell',height,overlap)
    report['lift_overlap_mm3'][str(height)]=round(overlap,6)
(OUT/'battery-service-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
