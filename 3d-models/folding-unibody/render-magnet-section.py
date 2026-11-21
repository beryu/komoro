#!/usr/bin/env python3
"""Dimensioned section of the magnetic catch, using generator dimensions."""
from pathlib import Path
import json
import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/folding-unibody-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle

OUT = Path(__file__).resolve().parent / 'generated'
v = json.loads((OUT / 'validation.json').read_text())
m = v['closure_magnets']
w, d, h = m['size_mm']
pw, pd, ph = m['pocket_mm']
face = 16.
recess = m['nominal_face_recess_mm']
font = Path('/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc')
if font.exists():
    font_manager.fontManager.addfont(str(font))
    plt.rcParams['font.family'] = font_manager.FontProperties(fname=str(font)).get_name()
plt.rcParams['axes.unicode_minus'] = False

fig, (ax, zoom) = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={'width_ratios': [2.1, 1]}, facecolor='#f4f6f7')
for a in (ax, zoom):
    a.set_facecolor('#f4f6f7')
    a.axis('off')
ax.add_patch(Rectangle((6, 0), 10, face, facecolor='#315e70'))
ax.add_patch(Rectangle((6, face), 10, 4, facecolor='#79aeb4'))
for z in (face-ph, face):
    ax.add_patch(Rectangle((12-pw/2, z), pw, ph, facecolor='#f4f6f7'))
for z in (face-recess-h, face+recess):
    ax.add_patch(Rectangle((12-w/2, z), w, h, facecolor='#c5cbd0', edgecolor='#627784', linewidth=.8))
ax.text(12, face-recess-h/2, '磁石 N', ha='center', va='center', fontsize=12, color='#314856')
ax.text(12, face+recess+h/2, '磁石 S', ha='center', va='center', fontsize=12, color='#314856')
ax.annotate('周囲の樹脂で閉じ止め', (7.4, face), (5.5, 21.1),
    arrowprops={'arrowstyle': '->', 'color': '#315e70'}, fontsize=11, color='#183c4b')
ax.text(6, 12.2, '中央ブロック側', fontsize=11, color='white')
ax.text(6, 19.4, '可動ツメ側', fontsize=11, color='#183c4b')
ax.set(xlim=(5.3, 16.7), ylim=(11.8, 22))
ax.set_aspect('equal')
zoom.add_patch(Rectangle((0, -.5), 4, .5-recess, facecolor='#c5cbd0', edgecolor='#627784'))
zoom.add_patch(Rectangle((0, recess), 4, .5-recess, facecolor='#c5cbd0', edgecolor='#627784'))
zoom.annotate('', (1, recess), (1, -recess), arrowprops={'arrowstyle': '<->', 'color': '#315e70', 'lw': 1.5})
zoom.text(1.35, 0, f"公称 {m['closed_face_gap_mm']:g} mm", fontsize=14, va='center', color='#183c4b')
zoom.text(.1, .29, '磁石面', fontsize=11, color='#314856')
zoom.text(.1, -.33, '磁石面', fontsize=11, color='#314856')
zoom.set(xlim=(-.1, 4.8), ylim=(-.6, .6))
zoom.set_title('面同士の隙間を拡大', fontsize=12, color='#183c4b')
fig.suptitle('中央の受け面に磁石を内蔵し、閉状態を保持', x=.05, ha='left', fontsize=18, color='#183c4b')
fig.text(.05, .075, '前後2組・計4個 ／ 6×2×2.3 mm ／ 磁石を樹脂面より0.1 mm奥へ配置', fontsize=11, color='#526670')
fig.text(.05, .025, '接着・印刷公差で隙間は変わります。キーを押し込む反力に対する保持力は実物確認前です。', fontsize=10, color='#7d6440')
fig.subplots_adjust(top=.83, bottom=.18, left=.05, right=.96, wspace=.2)
fig.savefig(OUT / 'magnet-section.png', dpi=160, facecolor=fig.get_facecolor())
plt.close(fig)
