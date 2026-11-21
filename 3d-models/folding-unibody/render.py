#!/usr/bin/env python3
"""Render the actual exported CAD tessellations, plus labelled fit envelopes."""
import json
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR', '/tmp/folding-unibody-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

OUT = Path(__file__).resolve().parent / 'generated'
MESH = json.loads((OUT / 'preview-mesh.json').read_text())
CHECK = json.loads((OUT / 'validation.json').read_text())
font = Path('/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc')
if font.exists():
    font_manager.fontManager.addfont(str(font))
    plt.rcParams['font.family'] = font_manager.FontProperties(fname=str(font)).get_name()
plt.rcParams['axes.unicode_minus'] = False


def draw(ax, name, color, angle=0, alpha=1):
    item = MESH[name]
    v = np.array(item['vertices'])
    if angle:
        a = np.deg2rad(angle)
        c = np.array([0, 0, CHECK['axis_z_mm']])
        rot = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
        v = (v - c) @ rot.T + c
    f = v[np.array(item['triangles'])]
    # Subdivide large faces so depth sorting does not draw the floor over keys.
    done = []
    for _ in range(14):
        lengths = np.stack([np.linalg.norm(f[:, (j+1) % 3] - f[:, j], axis=1) for j in range(3)], axis=1)
        good = lengths.max(axis=1) < 8
        if good.any(): done.append(f[good])
        if good.all(): break
        bad = f[~good]; idx = lengths[~good].argmax(axis=1); row = np.arange(len(bad))
        a = bad[row, idx]; b = bad[row, (idx+1) % 3]; c = bad[row, (idx+2) % 3]; mid = (a+b)/2
        f = np.concatenate([np.stack([a, mid, c], axis=1), np.stack([mid, b, c], axis=1)])
    else:
        done.append(f)
    f = np.concatenate(done)
    # Subtle lighting makes the CAD faces readable without decorative bevels.
    normal = np.cross(f[:, 1] - f[:, 0], f[:, 2] - f[:, 0])
    normal /= np.maximum(np.linalg.norm(normal, axis=1)[:, None], 1e-12)
    shade = .72 + .28 * np.maximum(0, normal @ np.array([-.3, -.4, .866]))
    rgb = np.array(matplotlib.colors.to_rgb(color))
    colors = np.column_stack([shade[:, None] * rgb, np.full(len(f), alpha)])
    if name.startswith('Keys_'):
        centers = f.mean(axis=1)
        if angle:
            pivot = np.array([0, 0, CHECK['axis_z_mm']])
            centers = (centers - pivot) @ rot + pivot
        cx, cy = (-36.05, 8.5) if 'left' in name else (53.05, 12.5)
        accent = (np.abs(centers[:, 0] - cx) < 8.1) & (np.abs(centers[:, 1] - cy) < 8.1)
        colors[accent, :3] = shade[accent, None] * np.array([.22, .26, .29])
    if name == 'AAA_cell_reference':
        # Illustrative wrapper, not a specified battery brand.
        band = f.mean(axis=1)[:, 1] < np.array(MESH[name]['vertices'])[:, 1].min() + 6.75
        colors[band, :3] = shade[band, None] * np.array([.64, .20, .18])
    if not hasattr(ax, '_fold_faces'):
        ax._fold_faces, ax._fold_colors = [], []
    ax._fold_faces.append(f)
    ax._fold_colors.append(colors)


def assembly(ax, angle):
    for side in ('right', 'left'):
        a = angle if side == 'left' else 0
        draw(ax, side + '_tray', '#cacbc5', a)
        draw(ax, side + '_cable_cover', '#b8bab5', a)
        draw(ax, side + '_plate', '#e4e4dd', a)
        keys = 'Keys_left_closed' if side == 'left' and angle == 180 else 'Keys_' + side
        draw(ax, keys, '#efeee8', a)
    for name, color in [('power_lid', '#e4e4dd'), ('latch_cap', '#cacbc5'), ('latch_slider', '#41484c')]:
        draw(ax, name, color)
    for name in ('Hinge_hardware_front', 'Hinge_hardware_rear'):
        draw(ax, name, '#c5cbd0')
    draw(ax, 'Closure_magnets_right', '#c9cdd0')
    draw(ax, 'Closure_magnets_left', '#c9cdd0', angle)
    # Display references: the ball position is illustrative, while the CAD
    # validation uses the larger conservative reserved envelope.
    draw(ax, 'Trackball_visual_only', '#b9bec1')
    draw(ax, 'AAA_cell_reference', '#e8e8e1')


def scene(ax, angle):
    assembly(ax, angle)
    ax.add_collection3d(Poly3DCollection(np.concatenate(ax._fold_faces),
        facecolors=np.concatenate(ax._fold_colors), edgecolors='none', antialiased=False, zsort='average'))
    ax.set_axis_off()
    ax.set_proj_type('ortho')
    ax.view_init(elev=35, azim=-65)
    if angle == 0:
        ax.set(xlim=(-160,160), ylim=(-25,100), zlim=(0,60)); ax.set_box_aspect((320,125,60), zoom=1.3)
    elif angle == 180:
        ax.set(xlim=(-20,160), ylim=(-25,100), zlim=(0,65)); ax.set_box_aspect((180,125,65), zoom=1.15)
    else:
        ax.set(xlim=(-40,160), ylim=(-25,100), zlim=(0,180)); ax.set_box_aspect((200,125,180))


fig = plt.figure(figsize=(15,10), facecolor='#f4f6f7')
fig.suptitle('komoro  /  折りたたみ一体型ボディ  Rev A', x=.06, ha='left', y=.97, fontsize=21, color='#183c4b')
fig.text(.06,.915,'既存PCBを流用  ·  キー面を内側に収納  ·  中央に単4電池と昇圧回路', fontsize=12, color='#526670')
for i, (angle, title) in enumerate([(0,'01  開いて使用'), (90,'02  左側を持ち上げる'), (180,'03  キー面を内側に収納')],1):
    ax = fig.add_subplot(2,2,i,projection='3d',facecolor='#f4f6f7')
    scene(ax, angle)
    ax.set_title(title, loc='left', fontsize=13, color='#183c4b', pad=0)
ax = fig.add_subplot(2,2,4,facecolor='#f4f6f7')
ax.set_title('04  中央電源室（ふたを外した上面・寸法は仮定）',loc='left',fontsize=12,color='#183c4b')
ax.add_patch(Rectangle((-16,0),34,74,facecolor='#d9e9e9',edgecolor='#315e70',lw=2))
parts = [('AAA_holder_assumed','#78878c','電池ホルダー'), ('Boost_module_assumed','#5c9e80','昇圧'),
         ('PTC_assumed','#d7ac60','PTC'),('Switch_assumed','#78878c','EN'),
         ('Power_disconnect_reserved','#a1b5cb','切離し')]
for name,color,label in parts:
    v=np.array(MESH[name]['vertices']); lo=v.min(axis=0); hi=v.max(axis=0)
    ax.add_patch(Rectangle(lo[:2],*(hi-lo)[:2],facecolor=color,edgecolor='white',lw=1.5))
    if name=='AAA_holder_assumed':
        ax.text((lo[0]+hi[0])/2,(lo[1]+hi[1])/2,'単4×1',ha='center',va='center',rotation=90,fontsize=12,color='white')
    else:
        ax.text(20,(lo[1]+hi[1])/2,label,va='center',fontsize=10,color='#34515d')
        ax.plot([hi[0],19],[(lo[1]+hi[1])/2]*2,color='#7b959f',lw=.8)
ax.text(-16,-6,f"電源室 34 × 74 mm ／ 高さ {CHECK['power_room']['top_mm']:g} mm",fontsize=10,color='#526670')
ax.set(xlim=(-28,48),ylim=(-10,82)); ax.set_aspect('equal');ax.axis('off')
fig.text(.06,.04,'中央の前後に磁石を2組内蔵。キー押下の反力に対する保持力・接着・組付けは実物確認前。銀色ボールは配置イメージ。検証は従来の予約空間で実施。',fontsize=11,color='#7d6440')
fig.subplots_adjust(left=.05,right=.95,bottom=.09,top=.87,wspace=.13,hspace=.12)
fig.savefig(OUT/'overview.png',dpi=155,facecolor=fig.get_facecolor())
plt.close(fig)

# Fit a projected CAD view tightly to the page, without mplot3d margins.
def projected_scene(ax, angle=0, elev=60, azim=-75):
    from types import SimpleNamespace
    from matplotlib.collections import PolyCollection
    collector = SimpleNamespace()
    assembly(collector, angle)
    faces = np.concatenate(collector._fold_faces)
    colors = np.concatenate(collector._fold_colors)
    a, e = np.deg2rad([azim, elev])
    right = np.array([-np.sin(a), np.cos(a), 0])
    up = np.array([-np.cos(a)*np.sin(e), -np.sin(a)*np.sin(e), np.cos(e)])
    camera = np.array([np.cos(a)*np.cos(e), np.sin(a)*np.cos(e), np.sin(e)])
    xy = faces @ np.stack([right, up], axis=1)
    depth = faces.mean(axis=1) @ camera
    order = depth.argsort(kind='stable')
    ax.add_collection(PolyCollection(xy[order], facecolors=colors[order],
                                    edgecolors='none', antialiased=False))
    if angle == 0:
        cell = np.array(MESH['AAA_cell_reference']['vertices'])
        label = (cell.min(axis=0) + cell.max(axis=0)) / 2
        label[2] = cell[:, 2].max() + .05
        position = label @ np.stack([right, up], axis=1)
        rotation = np.rad2deg(np.arctan2(up[1], right[1]))
        ax.text(*position, 'AAA  1.5 V', fontsize=6, ha='center', va='center',
                rotation=rotation, rotation_mode='anchor', color='#343b40')
    lo, hi = xy.min(axis=(0,1)), xy.max(axis=(0,1))
    ax.set(xlim=(lo[0]-6, hi[0]+6), ylim=(lo[1]-5, hi[1]+5))
    ax.set_aspect('equal'); ax.axis('off')


fig = plt.figure(figsize=(14, 6), facecolor='#f4f6f7')
ax = fig.add_axes([.025,.12,.95,.73],facecolor='#f4f6f7')
projected_scene(ax)
fig.text(.045,.925,'前後の張り出しを抑えた中央ヒンジ',fontsize=20,color='#183c4b')
fig.text(.045,.06,f"同じPCBを使用 · 配線室を下面へ · 収納厚{CHECK['closed_size_mm'][2]:g} mm · 銀色ボールは仮配置",fontsize=11,color='#526670')
fig.savefig(OUT/'open-view.png',dpi=160,facecolor=fig.get_facecolor())
plt.close(fig)

fig = plt.figure(figsize=(14,6),facecolor='#f4f6f7')
ax=fig.add_axes([.025,.12,.95,.73],facecolor='#f4f6f7')
projected_scene(ax,elev=90,azim=-90)
fig.text(.045,.925,'上から見た輪郭と電池窓',fontsize=20,color='#183c4b')
fig.text(.045,.06,'窓10.5 × 43 mm ／ 回路側はカバーで覆う ／ キー形状・刻印は省略',fontsize=11,color='#526670')
fig.savefig(OUT/'top-view.png',dpi=160,facecolor=fig.get_facecolor())
plt.close(fig)
