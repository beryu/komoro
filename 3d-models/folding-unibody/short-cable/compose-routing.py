"""Compose the current inspection renders; requires Pillow in normal Python."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
OUT=Path(__file__).resolve().parent/'generated'
images=[Image.open(OUT/('cable-'+pose+'-render.png')).convert('RGB') for pose in ('open','folded')]
header=42
page=Image.new('RGB',(sum(im.width for im in images),max(im.height for im in images)+header),(225,228,227))
draw=ImageDraw.Draw(page)
try:font=ImageFont.truetype('Arial.ttf',26)
except OSError:font=ImageFont.load_default()
x=0
for label,im in zip(('OPEN','FOLDED'),images):
 draw.text((x+16,8),label,fill=(55,70,75),font=font)
 page.paste(im,(x,header));x+=im.width
page.save(OUT/'cable-routing.png')
