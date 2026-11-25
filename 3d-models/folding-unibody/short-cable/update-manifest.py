"""Hash the delivered, versioned design and generated artifacts after checks."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
# STEP exports are deliberately tracked for this variant despite the global
# repository ignore. Exclude FreeCAD/Blender autosave files and old aliases.
files=[p for p in HERE.rglob('*') if p.is_file() and p.suffix in
       ('.py','.md','.json','.FCStd','.blend','.step','.stl','.png','.glb')
       and p.name!='artifact-manifest.json' and '__pycache__' not in p.parts]
result={'native_model_sha256':sha(HERE/'generated/komoro-folding-101mm.blend'),
        'files':{str(p.relative_to(HERE)):sha(p) for p in sorted(files)}}
(HERE/'generated/artifact-manifest.json').write_text(json.dumps(result,indent=2)+'\n')
