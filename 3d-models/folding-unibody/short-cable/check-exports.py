"""Read every delivered STEP back and compare it to its native CAD solid."""
from pathlib import Path
import hashlib,json
import FreeCAD as App,Part
OUT=Path(__file__).resolve().parent/'generated'
doc=App.openDocument(str(OUT/'folding-unibody-rev-a.FCStd'))
report={}
for obj in doc.Objects:
 if not obj.Name.startswith('Print_'):continue
 name=obj.Name[6:];path=OUT/(name+'.step')
 exported=Part.Shape();exported.read(str(path))
 assert exported.isValid() and exported.isClosed() and len(exported.Solids)==1,name
 difference=exported.cut(obj.Shape).Volume+obj.Shape.cut(exported).Volume
 assert difference<.001,(name,difference)
 report[name]={'valid_closed_single_solid':True,'symmetric_difference_mm3':difference,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
(OUT/'step-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('STEP_EXPORTS_VALID',len(report))
