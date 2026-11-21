#!/usr/bin/env python3
"""Compare two real CAD meshes in identical styling.

Pass the previous generated/preview-mesh.json with --before.
"""
from pathlib import Path
import argparse, json, os, runpy
os.environ.setdefault('MPLCONFIGDIR','/tmp/folding-unibody-mpl')
parser=argparse.ArgumentParser()
parser.add_argument('--before',type=Path,required=True)
args=parser.parse_args()
HERE=Path(__file__).resolve().parent
ns=runpy.run_path(str(HERE/'render.py'))
plt=ns['plt']; current=ns['MESH']; before=json.loads(args.before.read_text())
fig=plt.figure(figsize=(14,9),facecolor='#f4f6f7')
fig.text(.045,.955,'中央の張り出しを削減',fontsize=23,color='#183c4b')
for meshes,rect,title in [(before,[.035,.51,.93,.36],'変更前：外付けボルトとロック箱'),
                          (current,[.035,.10,.93,.36],'変更後：短い軸受けと内蔵ロック')]:
 ns['draw'].__globals__['MESH']=meshes
 ax=fig.add_axes(rect,facecolor='#f4f6f7')
 ns['projected_scene'](ax,elev=65,azim=-75)
 ax.set_title(title,loc='left',fontsize=14,color='#183c4b',pad=2)
ns['draw'].__globals__['MESH']=current
fig.text(.045,.045,'金具を含む奥行：111 → 80.75 mm ／ 収納厚39.4 mmを維持 ／ 強度・抜け止めは実物確認前',fontsize=12,color='#526670')
fig.savefig(HERE/'generated/compact-comparison.png',dpi=155,facecolor=fig.get_facecolor())
plt.close(fig)
