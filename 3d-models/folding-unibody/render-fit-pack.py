#!/usr/bin/env python3
"""Render the full-scale fit pieces from their actual CAD tessellations."""
from pathlib import Path
import json
import os
import runpy
os.environ.setdefault('MPLCONFIGDIR', '/tmp/folding-unibody-mpl')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

HERE = Path(__file__).resolve().parent
ns = runpy.run_path(str(HERE / 'render.py'))
draw = ns['draw']
OUT = HERE / 'generated'
gap = json.loads((OUT / 'gap-gauge-validation.json').read_text())['nominal_internal_gap_mm']


def finish(ax, limits, aspect, elev=30, azim=-65):
    ax.add_collection3d(Poly3DCollection(np.concatenate(ax._fold_faces),
        facecolors=np.concatenate(ax._fold_colors), edgecolors='none', antialiased=False, zsort='average'))
    ax.set_axis_off()
    ax.set_proj_type('ortho')
    ax.set(xlim=limits[0], ylim=limits[1], zlim=limits[2])
    ax.set_box_aspect(aspect, zoom=1.05)
    ax.view_init(elev=elev, azim=azim)


fig = plt.figure(figsize=(13, 9), facecolor='#f4f6f7')
fig.suptitle('先に小さく印刷して、組付けを確認', x=.06, y=.96, ha='left', fontsize=21, color='#183c4b')
for i, angle in enumerate((0, 180), 1):
    ax = fig.add_subplot(2, 2, i, projection='3d', facecolor='#f4f6f7')
    draw(ax, 'fit_right_joint', '#315e70')
    draw(ax, 'fit_left_joint', '#71a3ab', angle)
    draw(ax, 'fit_front_power_lid', '#abcacf')
    draw(ax, 'latch_cap', '#609f9f')
    draw(ax, 'latch_slider', '#eda448')
    draw(ax, 'Hinge_hardware_front', '#c5cbd0')
    for side in ('left', 'right'):
        name = 'Closure_magnets_' + side
        item = ns['MESH'][name]
        vertices = np.array(item['vertices'])
        triangles = np.array(item['triangles'])
        front = triangles[vertices[triangles][:, :, 1].mean(axis=1) < 10]
        ns['MESH'][name + '_front'] = {'vertices': item['vertices'], 'triangles': front.tolist()}
        draw(ax, name + '_front', '#c9cdd0', angle if side == 'left' else 0)
    finish(ax, ((-35 if angle == 0 else -20, 36), (-5, 22), (0, 42)), (71 if angle == 0 else 56, 27, 42))
    ax.set_title('01  前側ヒンジ・ロック' if angle == 0 else '02  中央ブロックで閉じ止め',
                 loc='left', fontsize=13, color='#183c4b')
ax = fig.add_subplot(2, 2, 3, projection='3d', facecolor='#f4f6f7')
draw(ax, 'fit_power_room', '#609f9f', alpha=.28)
draw(ax, 'Closure_magnets_right', '#c9cdd0')
for name, color, alpha in [('AAA_holder_assumed', '#73818b', .28),
                            ('AAA_cell_reference', '#e5af4e', 1),
                            ('Boost_module_assumed', '#4a9471', 1),
                            ('PTC_assumed', '#c49c57', 1),
                            ('Switch_assumed', '#59636c', 1),
                            ('Diode_assumed', '#59636c', 1),
                            ('Power_disconnect_reserved', '#94a7bf', 1)]:
    draw(ax, name, color, alpha=alpha)
finish(ax, ((-20, 48), (-4, 78), (0, 28)), (68, 82, 28), elev=50)
ax.set_title('03  電源室だけで仮置き', loc='left', fontsize=13, color='#183c4b')
ax = fig.add_subplot(2, 2, 4, facecolor='#f4f6f7')
outline = [(0, 0), (28, 0), (28, 2), (3, 2), (3, gap+2), (28, gap+2), (28, gap+4), (0, gap+4)]
ax.add_patch(Polygon(outline, facecolor='#609f9f', edgecolor='#315e70', linewidth=1))
ax.annotate('', (16, gap+2), (16, 2), arrowprops={'arrowstyle': '<->', 'color': '#315e70', 'lw': 1.5})
ax.text(17.5, gap/2+2, f'{gap:g} mm', color='#183c4b', fontsize=16, va='center')
ax.text(5, -5, '締め付けず、ケースの脇へ添える', color='#526670', fontsize=10)
ax.set(xlim=(-3, 43), ylim=(-8, gap+10)); ax.set_aspect('equal'); ax.axis('off')
ax.set_title('04  収納厚の確認ゲージ（側面）', loc='left', fontsize=13, color='#183c4b')
fig.text(.06, .035, '軸：2 × 7.6 mm金属ピン ／ ばね：C101 ／ 抜け止め・軸受け強度・自動復帰は実物で確認する段階です。', fontsize=11, color='#7d6440')
fig.subplots_adjust(left=.06, right=.95, bottom=.1, top=.86, hspace=.15, wspace=.1)
fig.savefig(OUT / 'fit-pack.png', dpi=150, facecolor=fig.get_facecolor())
plt.close(fig)
