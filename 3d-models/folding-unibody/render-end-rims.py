#!/usr/bin/env python3
"""Compare exported front-joint CAD with the prior finger/pad geometry."""
import argparse,json,runpy
from pathlib import Path
from types import SimpleNamespace
import numpy as np
HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--before',type=Path,required=True);args=parser.parse_args()
ns=runpy.run_path(str(HERE/'render.py'));draw=ns['draw'];plt=ns['plt'];g=draw.__globals__
from matplotlib.collections import PolyCollection
current=g['MESH'];before=json.loads(args.before.read_text())
fig=plt.figure(figsize=(14,9),facecolor='#f4f6f7')
fig.text(.04,.95,'前後端を、柱から連続した線状のリブへ',fontsize=21,color='#183c4b')
for i,(mesh,angle,title) in enumerate([(before,0,'以前：短いツメと独立して見える受け'),(current,0,'変更後：端面から立ち上がる連続したリブ'),(current,180,'収納時：リブ同士が当たり、磁石で保持')]):
 g['MESH']=mesh;c=SimpleNamespace()
 for name,color,a in [('fit_right_joint','#b9bcb5',0),('fit_left_joint','#e2e3dc',angle),('fit_front_power_lid','#e2e3dc',0),('latch_cap','#b9bcb5',0),('latch_slider','#41484c',0),('Hinge_hardware_front','#c5cbd0',0)]:
  draw(c,name,color,a)
 for side in ('left','right'):
  item=mesh['Closure_magnets_'+side];v=np.array(item['vertices']);t=np.array(item['triangles']);t=t[v[t][:,:,1].mean(axis=1)<10]
  key='magnet_front_'+side;mesh[key]={'vertices':item['vertices'],'triangles':t.tolist()};draw(c,key,'#c5cbd0',angle if side=='left' else 0)
 faces=np.concatenate(c._fold_faces);colors=np.concatenate(c._fold_colors)
 az,e=np.deg2rad([-65,28]);right=np.array([-np.sin(az),np.cos(az),0]);up=np.array([-np.cos(az)*np.sin(e),-np.sin(az)*np.sin(e),np.cos(e)]);cam=np.array([np.cos(az)*np.cos(e),np.sin(az)*np.cos(e),np.sin(e)])
 xy=faces@np.stack([right,up],axis=1);order=(faces.mean(axis=1)@cam).argsort(kind='stable')
 ax=fig.add_subplot(2,2,i+1);ax.add_collection(PolyCollection(xy[order],facecolors=colors[order],edgecolors='none',antialiased=False));lo,hi=xy.min(axis=(0,1)),xy.max(axis=(0,1));ax.set(xlim=(lo[0]-2,hi[0]+2),ylim=(lo[1]-2,hi[1]+2));ax.set_aspect('equal');ax.axis('off');ax.set_title(title,loc='left',fontsize=12,color='#183c4b')
g['MESH']=current
ax=fig.add_subplot(2,2,4);ax.axis('off')
ax.text(.03,.82,'前後とも幅4 mmの連続した端壁\n\n可動側の頂点 21 → 19 mm\n固定側の接触線 16 → 18 mm\n\n磁石2組・回転軸・収納厚39.4 mmは維持\n\n強度・反復耐久・磁石保持力は実物確認前',fontsize=13,va='top',color='#34515d',linespacing=1.5)
fig.subplots_adjust(left=.04,right=.97,bottom=.05,top=.88,wspace=.15,hspace=.28);fig.savefig(HERE/'generated/end-rim-comparison.png',dpi=160,facecolor=fig.get_facecolor());plt.close(fig)
