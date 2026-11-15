#!/usr/bin/env python3
import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
P=Path(__file__).resolve().parent;W,H=1300,1000;bounds=(16.588,46.998,16.619,47.027)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17)
def xy(c):return ((c[0]-bounds[0])/(bounds[2]-bounds[0])*W,(bounds[3]-c[1])/(bounds[3]-bounds[1])*H)
im=Image.new('RGB',(W,H),'white');d=ImageDraw.Draw(im)
colors=['#c7571d','#9966cc','#267f3b','#bc2060','#2477cc','#a88c00']
for f in json.load(open(P/'source-ways.geojson'))['features']:
 tags=f['properties']['source']['tags'];cs=[xy(c) for c in f['geometry']['coordinates']]
 if tags.get('highway') or tags.get('waterway'):d.line(cs,fill='#6f9fce' if tags.get('waterway') else '#d3d3d3',width=1)
for f,col in zip(json.load(open(P/'features.geojson'))['features'],colors):
 cs=[xy(c) for c in f['geometry']['coordinates'][0]];d.line(cs,fill=col,width=4)
for f,col in zip(json.load(open(P/'features.geojson'))['features'],colors):
 p=next(x for x in json.load(open(P/'source-named-points.geojson'))['features'] if x['properties']['name']==f['properties']['name']);x,y=xy(p['geometry']['coordinates']);d.ellipse((x-4,y-4,x+4,y+4),fill=col);d.text((x+7,y),f['properties']['name'],font=font,fill=col,stroke_width=1,stroke_fill='white')
d.rectangle((8,8,720,40),fill='white');d.text((14,12),'Körmend: six low-confidence quarter estimates',font=font,fill='black')
im.save(P/'preview.png')
