#!/usr/bin/env python3
"""Show the actual cap, cradle and service path from CAD tessellations."""
from pathlib import Path
import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/folding-unibody-mpl")
import runpy
from types import SimpleNamespace
import numpy as np
from matplotlib.collections import PolyCollection
HERE=Path(__file__).resolve().parent
ns=runpy.run_path(str(HERE/'render.py'))
plt=ns['plt']; mesh=ns['MESH']; draw=ns['draw']
fig=plt.figure(figsize=(14,7),facecolor='#f4f6f7')
fig.text(.04,.94,'電池に沿って内側をくり抜いた、低い単四カバー',fontsize=21,color='#183c4b')
for i,removed in enumerate((False,True)):
 ax=fig.add_axes([.04+i*.49,.16,.44,.67],facecolor='#f4f6f7'); c=SimpleNamespace()
 for name,color in [('fit_power_room','#cacbc5'),('power_lid','#e4e4dd'),('battery_cap','#e4e4dd'),('AAA_holder_visual_only','#343a3e'),('AAA_cell_reference','#e8e8e1')]:
  if removed and name=='battery_cap':continue
  draw(c,name,color)
 faces=np.concatenate(c._fold_faces);colors=np.concatenate(c._fold_colors)
 a,e=np.deg2rad([-65,55]); right=np.array([-np.sin(a),np.cos(a),0]);up=np.array([-np.cos(a)*np.sin(e),-np.sin(a)*np.sin(e),np.cos(e)]);camera=np.array([np.cos(a)*np.cos(e),np.sin(a)*np.cos(e),np.sin(e)])
 xy=faces@np.stack([right,up],axis=1);order=(faces.mean(axis=1)@camera).argsort(kind='stable')
 ax.add_collection(PolyCollection(xy[order],facecolors=colors[order],edgecolors='none',antialiased=False))
 lo,hi=xy.min(axis=(0,1)),xy.max(axis=(0,1));ax.set(xlim=(lo[0]-3,hi[0]+3),ylim=(lo[1]-3,hi[1]+3));ax.set_aspect('equal');ax.axis('off')
 ax.set_title('02  カバーだけを外して交換' if removed else '01  窓から電池を見せる',loc='left',fontsize=14,color='#183c4b')
fig.text(.04,.08,'左の弾性スカート2箇所で留める試作案。回路側のふたは残す。黒いホルダーは表示用の仮形状。',fontsize=11,color='#526670')
fig.text(.04,.035,'単三用STLは構造の参考のみ。単四ホルダーの寸法・ツメの着脱力は、受け台試験片で現物確認。',fontsize=11,color='#7d6440')
fig.savefig(HERE/'generated/battery-service.png',dpi=160,facecolor=fig.get_facecolor());plt.close(fig)

# Isolate the actual cap silhouette for comparison with the user's reference.
import struct
raw=(HERE/'generated/battery_cap.stl').read_bytes()
count=struct.unpack_from('<I',raw,80)[0]
vertices=[]
for i in range(count):
 record=struct.unpack_from('<12fH',raw,84+i*50)
 vertices.extend([record[3:6],record[6:9],record[9:12]])
mesh['battery_cap']={'vertices':vertices,'triangles':[(i*3,i*3+1,i*3+2) for i in range(count)]}
fig=plt.figure(figsize=(10,6),facecolor='#eef0f1')
ax=fig.add_axes([.04,.13,.92,.75]); c=SimpleNamespace()
draw(c,'battery_cap','#eeeeea')
faces=np.concatenate(c._fold_faces); colors=np.concatenate(c._fold_colors)
a,e=np.deg2rad([-25,25]); right=np.array([-np.sin(a),np.cos(a),0]);up=np.array([-np.cos(a)*np.sin(e),-np.sin(a)*np.sin(e),np.cos(e)]);camera=np.array([np.cos(a)*np.cos(e),np.sin(a)*np.cos(e),np.sin(e)])
xy=faces@np.stack([right,up],axis=1);order=(faces.mean(axis=1)@camera).argsort(kind='stable')
ax.add_collection(PolyCollection(xy[order],facecolors=colors[order],edgecolors='none',antialiased=False))
lo,hi=xy.min(axis=(0,1)),xy.max(axis=(0,1));ax.set(xlim=(lo[0]-3,hi[0]+3),ylim=(lo[1]-2,hi[1]+2));ax.set_aspect('equal');ax.axis('off')
fig.text(.04,.94,'単四電池カバー：枠15 mm、曲面頂点18 mm',fontsize=17,color='#183c4b')
fig.text(.04,.05,'実際のCAD形状。長辺の下側を開口し、端部の脚と着脱用のツメを残す。',fontsize=11,color='#526670')
fig.savefig(HERE/'generated/battery-cap-shape.png',dpi=160,facecolor=fig.get_facecolor());plt.close(fig)

check=ns['CHECK']['battery_service']
if 'cross_section' in check:
 from matplotlib.patches import Circle,Rectangle
 fig,ax=plt.subplots(figsize=(10,6),facecolor='#f4f6f7');ax.set_facecolor('#f4f6f7')
 for edge in check['cross_section']['cover_edges_xz_mm']:
  points=np.array(edge);ax.plot(points[:,0],points[:,1],color='#274a5a',lw=2.5)
 ax.add_patch(Circle((-6.5,11),5.25,facecolor='#e4cf99',edgecolor='#9b7b35',label='単四電池の参照形状'))
 for x,y,w,hh in [(-13,3.5,13,1),(-13,4.5,1,7),(-1,4.5,1,7)]:
  ax.add_patch(Rectangle((x,y),w,hh,facecolor='#6e777d',alpha=.55))
 ax.axhline(18.5,color='#448eac',ls='--',lw=1,label='ヒンジ軸 Z=18.5 mm')
 ax.annotate('内側R5.8 / 外側R7.0\n肉厚1.2 mm、電池との隙間0.55 mm',xy=(-6.5,16.8),xytext=(-18,21.2),fontsize=10,color='#274a5a',arrowprops={'arrowstyle':'->','color':'#274a5a'})
 ax.set(xlim=(-20,7),ylim=(2,24),xlabel='X [mm]',ylabel='Z [mm]',title='曲面部の実CAD断面（Y=19 mm）：中身を円筒に沿ってくり抜く')
 ax.set_aspect('equal');ax.legend(loc='lower right',fontsize=9);ax.grid(alpha=.15)
 fig.text(.05,.035,'濃線：カバーの実断面 ／ 灰色：未実測ホルダーの側壁・床の仮定。端子は曲面内の予約空間へ収める。',fontsize=9,color='#526670')
 fig.tight_layout(rect=(0,.07,1,1));fig.savefig(HERE/'generated/battery-cap-section.png',dpi=160);plt.close(fig)
