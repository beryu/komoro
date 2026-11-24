#!/usr/bin/env python3
"""Necessary length bounds for the CURRENT front-port routing, not a cable fit test.

A straight segment may pass through solid material, so these are deliberately
optimistic lower bounds. Passing this check never proves that a cable fits.
"""
from pathlib import Path
import hashlib, json, math
HERE = Path(__file__).resolve().parent
OUT = HERE / 'generated'

def distance_boxes(a, b):
    return math.sqrt(sum(max(0., a[0][i]-b[1][i], b[0][i]-a[1][i])**2 for i in range(3)))

# Larger than the PCB header reference: include the female body and permit
# an endpoint ANYWHERE inside it, even the underside. This underestimates
# rather than overestimates the necessary free lead length.
left_socket = ((-36.39,38.595,6.1),(-31.31,50.405,14.5))
right_socket = ((31.71,32.595,6.1),(36.79,44.405,14.5))
left_port = ((-18.,8.,-.2),(-18.,16.,2.))
right_port = ((-16.1,8.,-.2),(-16.1,16.,2.))
left_port_closed = ((18.,8.,35.),(18.,16.,37.2))
legs = [distance_boxes(left_socket,left_port),distance_boxes(right_socket,right_port)]
nominal_left=(-33.85,44.5,12.5)
nominal_right=(34.25,38.5,12.5)
a=(-18.,12.,.6)
b=(-16.,12.,.6)
def rotate(p,angle):
    t=math.radians(angle)
    return (p[0]*math.cos(t)+(p[2]-18.5)*math.sin(t),p[1],18.5-p[0]*math.sin(t)+(p[2]-18.5)*math.cos(t))
nominal_fixed_legs=math.dist(nominal_left,a)+math.dist(nominal_right,b)
minimum=sum(legs)+distance_boxes(left_port_closed,right_port)
report={
 'scope':'Current front-port topology only; not a proof for other routes or PCB/connector positions.',
 'CAD_sha256':hashlib.sha256((OUT/'folding-unibody-rev-a.FCStd').read_bytes()).hexdigest(),
 'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 'nominal_centerline_chord_sum_mm':{str(t):nominal_fixed_legs+math.dist(rotate(a,t),b) for t in (0,90,180)},
 'optimistic_closed_lower_bound_mm':minimum,
 'lower_bound_terms_mm':legs+[distance_boxes(left_port_closed,right_port)],
 'available_assembly_lengths_mm':[76.2,101.6,254.],
 'length_only_results':{str(length):'insufficient for current front-port route' if length<minimum else 'not rejected by length bound; fit NOT validated' for length in (76.2,101.6,254.)},
 'ignored_to_make_bound_optimistic':['bends','obstacles','strain relief','connector portion included in assembly length','slack','one common port point for adjacent segments'],
 'continuous_cable_geometry':'not implemented',
 'dynamic_flex_validation':'not performed',
}
assert minimum>101.6
(OUT/'cable-length-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
