#!/usr/bin/env python3
"""Render technical original-source and calibration evidence; no basemap service."""
from pathlib import Path
import json
import fitz,numpy as np
from PIL import Image,ImageDraw
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import Transformer
P=Path(__file__).resolve().parent;doc=fitz.open(P/'source-pages1-2.pdf');reg=json.loads((P/'registration.json').read_text());M1=np.array(reg['page1PdfPointsToEovMatrix']);M12=np.array(reg['page1PdfPointsToPage2PdfPointsMatrix']);M2=np.array(reg['page2PdfPointsToEovMatrix']);raw=json.loads((P/'native-source-polygons.json').read_text());cad=json.loads((P/'cross-page-cad-controls.json').read_text())
def render(pg,scale=1):
 pix=doc[pg].get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False);return Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
image=render(1,2);draw=ImageDraw.Draw(image);colors=['#ff00ff','#ff8c00','#008080','#ff0000']
for r,c in zip(raw['records'],colors):
 for ring in r['nativeGeometry']['coordinates']:draw.line([tuple(np.array(pt)*2) for pt in ring],fill=c,width=2)
image.crop((760,590,1530,1340)).save(P/'native-four-source-faces.png')
image=render(0,1.2);draw=ImageDraw.Draw(image);parent=shape(json.loads((P/'calibration-municipality.geojson').read_text())['geometry']);eov=transform(Transformer.from_crs(4326,23700,always_xy=True).transform,parent);parts=list(eov.geoms) if eov.geom_type=='MultiPolygon' else [eov]
for part in parts:
 coords=(np.array(part.exterior.coords)-M1[2])@np.linalg.inv(M1[:2]);draw.line([tuple(x*1.2) for x in coords],fill='#ff00ff',width=1)
image.save(P/'municipal-registration-overlay.png')
image=render(1,2);draw=ImageDraw.Draw(image)
for k,r in enumerate(cad['geographicallySpreadSourceExamples'],1):
 a=np.array(r['page1']['coordinates']);a=np.c_[a,np.ones(2)]@M12;b=np.array(r['page2']['coordinates']);draw.line([tuple(x*2)for x in b],fill='#ff00ff',width=3);draw.line([tuple(x*2)for x in a],fill='#00ffff',width=1);mid=b.mean(axis=0)*2
 draw.text(tuple(mid),str(k),fill='black')
image.crop((760,590,1530,1340)).save(P/'cross-page-cad-controls-overlay.png')
print('Rendered3 source/control evidence images; geographic accuracy not asserted.')
