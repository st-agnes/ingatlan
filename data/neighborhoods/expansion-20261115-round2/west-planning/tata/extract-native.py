"""Re-extract native drawing9, preserving PDF even-odd filled-face semantics."""
import json,math
from pathlib import Path
import fitz
from shapely.geometry import Polygon,LineString,mapping
from shapely.ops import unary_union,polygonize
P=Path(__file__).parent;d=fitz.open(P/'source-quarter-map2022.pdf')[0].get_drawings()[9];rings=[];cs=[]
for typ,a,b in d['items']:
 a,b=tuple(a),tuple(b)
 if cs and math.dist(a,cs[-1])>.003:rings.append(cs);cs=[]
 if not cs:cs=[a]
 cs.append(b)
if cs:rings.append(cs)
poly=Polygon()
def inside(x,y,ring):return sum(1 for (a,b),(c,e) in zip(ring,ring[1:]) if (b>y)!=(e>y) and x<(c-a)*(y-b)/(e-b)+a)%2==1
for ring in rings:
 part=Polygon(ring)
 if not part.is_valid:
  faces=list(polygonize(unary_union(LineString(ring))));part=unary_union([face for face in faces if inside(face.representative_point().x,face.representative_point().y,ring)])
 poly=poly.symmetric_difference(part)
assert poly.is_valid
(P/'source-native-path9.geojson').write_text(json.dumps(dict(type='Feature',properties=dict(sourceDrawingIndex=9,name='Külterületek',coordinateFrame='PDF points'),geometry=mapping(poly)),ensure_ascii=False,indent=2)+'\n');print('Native countryside:',poly.geom_type,poly.area)
