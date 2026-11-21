#!/usr/bin/env python3
"""Make a contact sheet of the actual Blender renders."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / 'generated'
FONT = '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc'
font = ImageFont.truetype(FONT, 26)
title = ImageFont.truetype(FONT, 38)
canvas = Image.new('RGB', (1860, 1375), '#edf0f1')
draw = ImageDraw.Draw(canvas)
draw.text((30, 20), 'Blenderモデル：上下左右・収納状態', font=title, fill='#183c4b')
views = [('Top', '上面'), ('Bottom', '下面'), ('Battery_open', '電池カバーを外した状態'),
         ('Front', '正面'), ('Back', '背面'), ('Left', '左側'),
         ('Right', '右側'), ('Folded', '閉じた状態'), ('Service', '底ぶたを外した下面')]
for i, (name, label) in enumerate(views):
    x, y = 20 + (i % 3) * 615, 90 + (i // 3) * 425
    picture = Image.open(OUT / 'blender-views' / (name + '.png')).convert('RGB')
    picture.thumbnail((600, 380), Image.Resampling.LANCZOS)
    canvas.paste(picture, (x, y + 35))
    draw.text((x, y), label, font=font, fill='#183c4b')
canvas.save(OUT / 'blender-views.png')
