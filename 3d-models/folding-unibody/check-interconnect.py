#!/usr/bin/env python3
"""Check PCB-edge lead and underfloor channel envelopes in the saved CAD.

This does not model the flexible span between the two front ports.
Run after generate.py with FreeCAD's Python.
"""
from pathlib import Path
import runpy, json, hashlib
import FreeCAD as App
import Part
HERE = Path(__file__).resolve().parent
OUT = HERE / 'generated'
ns = runpy.run_path(str(HERE / 'generate.py'), run_name='geometry_library')
box, union, folded = (ns[n] for n in ('box', 'union', 'folded'))
doc = App.openDocument(str(OUT / 'folding-unibody-rev-a.FCStd'))
shape = lambda name: doc.getObject(name).Shape
leads = {
 'left': union([box(-33.85,40.7,12,15.35,7.6,1),
                box(-19.5,40.7,1.1,1,7.6,11.9),
                box(-26.8,40.7,.1,8.3,7.6,1),
                box(-26.8,5.2,.1,7.6,43.6,1),
                box(-26.8,8.2,.1,8.8,7.6,1)]),
 'right': union([box(18.5,34.7,12,15.75,7.6,1),
                 box(18.5,34.7,1.1,1,7.6,11.9),
                 box(18.5,34.7,.1,8.3,7.6,1),
                 box(19.2,5.2,.1,7.6,37.6,1),
                 box(-16,8.2,.1,42.8,7.6,1)])}
report = {'scope':'Rigid lead envelopes only. Flexible port-to-port span, 254 mm storage, bend radii and fatigue are not validated.',
          'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'CAD_sha256':hashlib.sha256((OUT / 'folding-unibody-rev-a.FCStd').read_bytes()).hexdigest(),
          'own_case_overlap_mm3':{},'own_PCB_overlap_mm3':{},'case_to_PCB_overlap_mm3':{},'sweep':[]}
assemblies = {}
for side in ('left','right'):
 assemblies[side] = union([shape('Print_'+side+'_'+n) for n in ('tray','plate','cable_cover')])
 if side == 'right': assemblies[side] = union([assemblies[side],shape('Print_power_lid'),shape('Print_latch_cap'),shape('Print_battery_cap')])
 own=leads[side].common(assemblies[side]).Volume
 pcb=leads[side].common(shape('Reference_'+side+'_PCB_reference')).Volume
 assert max(own,pcb)<.001,(side,'lead obstructed',own,pcb)
 case_pcb = assemblies[side].common(shape('Reference_'+side+'_PCB_reference')).Volume
 assert case_pcb < .001, (side, 'case obstructs PCB', case_pcb)
 report['case_to_PCB_overlap_mm3'][side] = round(case_pcb,6)
 report['own_case_overlap_mm3'][side]=round(own,6)
 report['own_PCB_overlap_mm3'][side]=round(pcb,6)
for angle in sorted(set(range(0,181,5)) | {175+i*.5 for i in range(11)}):
 left = folded(assemblies['left'],angle)
 lead = folded(leads['left'],angle)
 vol=lead.common(assemblies['right']).Volume+left.common(leads['right']).Volume+lead.common(leads['right']).Volume
 assert vol<.001,('lead sweep collision',angle,vol)
 report['sweep'].append({'angle_deg':angle,'overlap_mm3':round(vol,6)})
(OUT/'interconnect-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='sweep'}))
