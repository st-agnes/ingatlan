from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from pyproj import Transformer
import json,numpy as np
P=Path(__file__).resolve().parent;source=Image.open(P/'source-name-map.jpeg').convert('RGB');model=json.loads((P/'model.json').read_text());proof=json.loads((P/'calculation-proof.json').read_text());M=np.array(model['matrixPixelToEov']);inverse=np.linalg.inv(M[:2]);to=Transformer.from_crs(4326,23700,always_xy=True).transform
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14)
# Source-only crops: no geographic projection markers.
contact=Image.new('RGB',(1200,860),'white');d=ImageDraw.Draw(contact)
for i,c in enumerate(proof['fitControls']):
 x,y=c['sourcePixel'];lo_x=max(0,x-30);lo_y=max(0,y-30);hi_x=min(source.width,x+30);hi_y=min(source.height,y+30);tile=Image.new('RGB',(380,390),'white');td=ImageDraw.Draw(tile);td.text((5,5),c['id']+f' source ({x},{y})',font=font,fill='black');crop=source.crop((lo_x,lo_y,hi_x,hi_y)).resize(((hi_x-lo_x)*6,(hi_y-lo_y)*6));cd=ImageDraw.Draw(crop);ux,uy=c['sourceImageReadingUncertaintyPixels'];cd.rectangle(((x-ux-lo_x)*6,(y-uy-lo_y)*6,(x+ux-lo_x)*6,(y+uy-lo_y)*6),outline='blue',width=2);tile.paste(crop,(5,28));contact.paste(tile,((i%3)*400,(i//3)*420))
d.text((8,835),'Original image observations only; boxes are reading ranges, not survey accuracy.',font=font,fill='black');contact.save(P/'source-control-crops.png')
# Geographic model overlay, separate from source-only reading proof.
out=Image.new('RGB',(1755,1605),'white');out.paste(source.resize((1755,1542)),(0,0));draw=ImageDraw.Draw(out)
def project(coords):
 w=np.array([to(*v)for v in coords]);return(w-M[2])@inverse
municipality=json.loads((P/'source-municipality.geojson').read_text())['geometry'];polys=[municipality['coordinates']]if municipality['type']=='Polygon'else municipality['coordinates']
for poly in polys:
 for ring in poly:draw.line([tuple(v*3)for v in project(ring)],fill='cyan',width=2)
ways=json.loads((P/'source-road-ways.geojson').read_text())['features']
for f in ways:
 t=f['properties']['tags']
 if t.get('ref')in['M60','66']:draw.line([tuple(v*3)for v in project(f['geometry']['coordinates'])],fill='magenta',width=2)
for c in proof['fitControls']:
 x,y=c['sourcePixel'];u,v=c['sourceImageReadingUncertaintyPixels'];draw.rectangle(((x-u)*3,(y-v)*3,(x+u)*3,(y+v)*3),outline='blue',width=2);fit=(np.array(c['targetEov'])-M[2])@inverse;draw.ellipse((fit[0]*3-2,fit[1]*3-2,fit[0]*3+2,fit[1]*3+2),fill='red');draw.text((x*3+8,y*3),c['id'],font=font,fill='blue')
draw.text((8,1550),'Candidate only: cyan=current boundary; magenta=original OSM roads; blue=source reading; red=inverse target.',font=font,fill='black');draw.text((8,1574),'All image residuals and extrapolation limits retained. Unknown absolute accuracy; no address assignment.',font=font,fill='black');out.save(P/'candidate-model-overlay.png')
print('rendered source-only controls and separate candidate-model overlay')
