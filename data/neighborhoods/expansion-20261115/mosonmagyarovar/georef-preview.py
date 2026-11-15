import json,numpy as np
from pathlib import Path
from PIL import Image,ImageDraw
P=Path(__file__).parent
GCP=[[[281,207],[17.2736548,47.8807761]],[[146,241],[17.259426,47.8770322]],[[297,445],[17.2747011,47.8613656]]]
A=np.array([[*a,1] for a,b in GCP]);B=np.array([b for a,b in GCP]);M=np.linalg.lstsq(A,B,rcond=None)[0];I=np.linalg.inv(np.vstack([M.T,[0,0,1]]))
print(M);(P/'control-points.json').write_text(json.dumps(GCP))
im=Image.open(P/'source-clld-map.png').convert('RGBA').resize((1068,1474));over=Image.new('RGBA',im.size);d=ImageDraw.Draw(over)
for f in json.load(open(P/'source-ways.geojson'))['features']:
 t=f['properties']['source']['tags']
 if t.get('highway') not in ['primary','secondary','tertiary','residential','unclassified'] and not t.get('waterway'):continue
 cs=[tuple((I@[*c,1])[:2]*2) for c in f['geometry']['coordinates']]
 if min(x for x,y in cs)>1068 or max(x for x,y in cs)<0 or min(y for x,y in cs)>1474 or max(y for x,y in cs)<0:continue
 d.line(cs,fill=(0,0,255,130) if t.get('highway') else (255,0,0,170),width=2)
for xy,c in GCP:d.ellipse((xy[0]*2-5,xy[1]*2-5,xy[0]*2+5,xy[1]*2+5),fill='red')
Image.alpha_composite(im,over).save(P/'georef-preview.png')
