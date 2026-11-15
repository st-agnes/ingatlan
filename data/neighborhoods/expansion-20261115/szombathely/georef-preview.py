import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
P=Path(__file__).parent
GCP=[[[75,151],[16.58803,47.2437917]],[[219,272],[16.6218793,47.2271643]],[[296,176],[16.6387565,47.242498]]]
A=np.array([[*a,1] for a,b in GCP]);B=np.array([b for a,b in GCP]);M=np.linalg.lstsq(A,B,rcond=None)[0];I=np.linalg.inv(np.vstack([M.T,[0,0,1]]))
print(M)
im=Image.open(P/'source-overview.jpeg').convert('RGBA').resize((1440,1428)); overlay=Image.new('RGBA',im.size);d=ImageDraw.Draw(overlay)
for f in json.load(open(P/'source-ways.geojson'))['features']:
 t=f['properties']['source']['tags']
 if t.get('highway') not in ['primary','secondary','tertiary','residential','unclassified'] and not t.get('waterway') and not t.get('railway'):continue
 xy=[]
 for c in f['geometry']['coordinates']:
  x,y,_=I@[*c,1];xy.append((x*3,y*3))
 if min(x for x,y in xy)>1440 or max(x for x,y in xy)<0 or min(y for x,y in xy)>1428 or max(y for x,y in xy)<0:continue
 color=(0,0,255,120) if t.get('highway') else (255,0,255,120)
 d.line(xy,fill=color,width=2)
for xy,c in GCP:d.ellipse((xy[0]*3-8,xy[1]*3-8,xy[0]*3+8,xy[1]*3+8),fill='red')
Image.alpha_composite(im,overlay).save(P/'georef-preview.png')
(P/'control-points.json').write_text(json.dumps(GCP))
