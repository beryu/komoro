#!/usr/bin/env python3
"""Actual underside CAD projection, with an explicitly schematic cable route."""
from pathlib import Path
import runpy
import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/folding-unibody-mpl')
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.patches import Rectangle
HERE = Path(__file__).resolve().parent
ns = runpy.run_path(str(HERE / 'render.py'))
MESH, OUT = ns['MESH'], ns['OUT']
fig = plt.figure(figsize=(14, 8), facecolor='#f4f6f7')
fig.text(.045, .94, '電池の下に配線室を追加 ／ 底ぶたを外した下面', fontsize=21, color='#183c4b')
ax=fig.add_axes([.04,.37,.92,.52])
faces=[]
for side in ('left','right'):
 item=MESH[side+'_tray']
 v=np.array(item['vertices']); f=v[np.array(item['triangles'])]
 faces.append(f)
f=np.concatenate(faces)
depth=f.mean(axis=1)[:,2]
colors=np.tile(np.array([.75,.78,.77,1.]),(len(f),1))
colors[depth>1.3,:3]=[.85,.86,.82]
order=np.argsort(-depth,kind='stable')
ax.add_collection(PolyCollection(f[order,:,:2],facecolors=colors[order],edgecolors='none',antialiased=False))
ax.add_patch(Rectangle((-14,14),30,51,facecolor='#e6b876',edgecolor='#b07637',alpha=.65,lw=1))
left=np.array([[-19,44.5],[-23,44.5],[-23,12],[-18,12]])
right=np.array([[-16,12],[23,12],[23,38.5],[19,38.5]])
for line in (left,right):ax.plot(*line.T,color='#bd7432',lw=4,solid_capstyle='round')
for line in ([[-33.85,44.5],[-19,44.5]],[[19,38.5],[34.25,38.5]]):
 ax.plot(*np.array(line).T,color='#375e72',lw=2,ls='--')
for x,y in ((-33.85,44.5),(34.25,38.5)):
 ax.plot(x,y,'o',color='#375e72',ms=5)
ax.plot([-18,-16],[12,12],color='#b34e46',lw=4)
ax.annotate('左J101 → PCB縁の外で下面へ',(-33.85,44.5),xytext=(-124,83),fontsize=11,color='#375e72',arrowprops={'arrowstyle':'->','color':'#375e72'})
ax.annotate('右PCB縁から上面へ → J202',(34.25,38.5),xytext=(55,83),fontsize=11,color='#375e72',arrowprops={'arrowstyle':'->','color':'#375e72'})
ax.annotate('可動口は電池窓の手前側',(-17,12),xytext=(-124,-13),fontsize=11,color='#9a5146',arrowprops={'arrowstyle':'->','color':'#9a5146'})
ax.annotate('電池・回路の下の余長室',(5,38),xytext=(49,-13),fontsize=11,color='#9d682c',arrowprops={'arrowstyle':'->','color':'#9d682c'})
ax.set(xlim=(-155,155),ylim=(-20,93));ax.set_aspect('equal');ax.axis('off')
fig.text(.05,.30,'実線：下面の通路 ／ 破線：PCB縁までの上面リード',fontsize=12,color='#526670')
fig.text(.05,.245,'ルート線は配線の模式図です。',fontsize=12,color='#526670')
fig.text(.05,.20,'開閉中のケーブル全長の形・254 mmの余長収納・',fontsize=11,color='#7d6440')
fig.text(.05,.16,'曲げ半径と屈曲寿命は、仮組みで確認します。',fontsize=11,color='#7d6440')
ax=fig.add_axes([.57,.10,.38,.22])
for y,h,c,label in [(-1.2,1.,'#9aa7a5','底ぶた 1 mm'),(-.2,2.2,'#e6b876','配線室 2.2 mm'),(2,1.5,'#ced5cd','天井 1.5 mm'),(3.5,1.5,'#7e919b','電池ホルダー（下端）')]:
 ax.add_patch(Rectangle((0,y),26,h,facecolor=c,edgecolor='#526670',lw=.8))
 ax.text(13,y+h/2,label,ha='center',va='center',fontsize=10,color='#203e4a')
ax.set(xlim=(-2,28),ylim=(-1.5,5.4));ax.axis('off')
fig.text(.57,.06,'断面模式図：電池室上面20.5 mm・回転軸18.5 mmは維持',fontsize=10,color='#526670')
fig.savefig(OUT/'underfloor-wiring.png',dpi=155,facecolor=fig.get_facecolor())
plt.close(fig)
