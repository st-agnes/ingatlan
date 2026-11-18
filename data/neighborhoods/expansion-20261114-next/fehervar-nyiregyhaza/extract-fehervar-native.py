#!/usr/bin/env python3
"""Adopt the actual coloured 2021 municipal PDF boundaries with rough placement."""
from pathlib import Path
import fitz,json,gzip,hashlib,collections
from shapely.geometry import Polygon,MultiPolygon,shape,mapping
from shapely.ops import unary_union,transform
from shapely.validation import make_valid
from pyproj import Transformer
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
PDF=OUT/'fehervar-oht2021.pdf';URL='https://www.szekesfehervar.hu/_upload/editor/2021/Onkormanyzat/f__epiteszi_2021/OTHT2021REV/00_oSSZESiTeS_oH2021__I-II_kotet.pdf'
MUNICIPAL=ROOT/'data/neighborhoods/sources/country-osm/municipalities.geojson.gz'
# PDF drawing indices are literal source records, not inferred namepoint hulls.
SPEC=[
 ('Belváros',[3881],['Történelmi belváros'],'neighbourhood'),
 ('Felsőváros',[7],[],'neighbourhood'),
 ('Palotaváros',[402],[],'neighbourhood'),
 ('Víziváros',[491],[],'neighbourhood'),
 ('Vezér- és író utcák',[581],['Vezérutcák'],'neighbourhood'),
 ('Öreghegy',[611],[],'neighbourhood'),
 ('Kisfalud',[650],[],'neighbourhood'),
 ('Csala',[715],[],'neighbourhood'),
 ('Ráchegy',[977],[],'neighbourhood'),
 ('Börgönd',[1796],[],'neighbourhood'),
 ('Maroshegy',[1241],[],'neighbourhood'),
 ('Sóstó-Alsóváros-Váralja',[1974],[],'planning_unit'),
 ('Szárazrét-Feketehegy',[2779],[],'planning_unit'),
 ('Felsőváros külterülete',[95],[],'planning_unit'),
 ('Öreghegy, Kisfalud és Csala külterülete',[747],[],'planning_unit'),
 ('Ráchegy-Börgönd északkeleti külterülete',[1127],[],'planning_unit'),
 ('Ráchegy-Börgönd délnyugati külterülete',[3156],[],'planning_unit'),
 ('Maroshegy északi külterülete',[1590],[],'planning_unit'),
 ('Maroshegy déli külterülete',[1895],[],'planning_unit'),
 ('Sóstó-Alsóváros-Váralja külterülete',[2236],[],'planning_unit'),
 ('Szárazrét-Feketehegy északi külterülete',[2953],[],'planning_unit'),
 ('Szárazrét-Feketehegy déli külterülete',[3039],[],'planning_unit'),
 ('Felsőváros és külterülete',[7,95],[],'planning_unit'),
 ('Öreghegy, Kisfalud, Csala és külterülete',[611,650,715,747],[],'planning_unit'),
 ('Ráchegy, Börgönd és külterülete',[977,1796,1127,3156],[],'planning_unit'),
 ('Maroshegy és külterülete',[1241,1590,1895],[],'planning_unit'),
 ('Sóstó-Alsóváros-Váralja és külterülete',[1974,2236],[],'planning_unit'),
 ('Szárazrét-Feketehegy és külterülete',[2779,2953,3039],[],'planning_unit'),
]
def valid_polygon(g):
 if not g.is_valid:g=make_valid(g)
 if g.geom_type=='GeometryCollection':
  parts=[]
  for x in g.geoms:
   if x.geom_type=='Polygon':parts.append(x)
   elif x.geom_type=='MultiPolygon':parts.extend(x.geoms)
  g=unary_union(parts)
 return g
raw={};geometries={};doc=fitz.open(PDF);page=doc[26];drawings=page.get_drawings()
for idx in sorted({n for row in SPEC for n in row[1]}):
 q=drawings[idx];rings=[];current=[]
 for item in q['items']:
  if item[0]!='l':raise ValueError('Unexpected non-line source item')
  start,end=tuple(item[1]),tuple(item[2])
  if current and current[-1]!=start:
   if len(current)>=3:rings.append(current)
   current=[]
  if not current:current=[start]
  current.append(end)
 if len(current)>=3:rings.append(current)
 polys=[valid_polygon(Polygon(r)) for r in rings if len(set(r))>=3]
 geometry=polys[0]
 for part in polys[1:]:geometry=geometry.symmetric_difference(part) if q['even_odd'] else geometry.union(part)
 geometry=valid_polygon(geometry)
 assert geometry.geom_type in ['Polygon','MultiPolygon'] and geometry.is_valid and not geometry.is_empty
 raw[str(idx)]={'drawingIndex':idx,'fill':q['fill'],'evenOdd':q['even_odd'],'sourceRect':list(q['rect']),'rings':rings}
 geometries[idx]=geometry
# The depicted map is the entire municipality, north-up. Extent fitting is a
# deliberate rough registration, not a statement of surveyed positional accuracy.
frame=unary_union(list(geometries.values())).bounds
source=json.loads(gzip.decompress(MUNICIPAL.read_bytes()))
municipality=next(f for f in source['features'] if f['properties']['name']=='Székesfehérvár')
forward=Transformer.from_crs(4326,23700,always_xy=True).transform
inverse=Transformer.from_crs(23700,4326,always_xy=True).transform
bounds=transform(forward,shape(municipality['geometry'])).bounds
sx0,sy0,sx1,sy1=frame;ex0,ey0,ex1,ey1=bounds

def place(x,y,z=None):
 return ex0+(x-sx0)/(sx1-sx0)*(ex1-ex0),ey1-(y-sy0)/(sy1-sy0)*(ey1-ey0)

features=[]
for name,indices,aliases,kind in SPEC:
 native=valid_polygon(unary_union([geometries[i] for i in indices]))
 geographic=valid_polygon(transform(inverse,transform(place,native)))
 p={'name':name,'municipality':'Székesfehérvár','aliases':aliases,'method':'native_pdf_vector_extent_registration','estimated':True,
    'candidateBoundaryKind':kind,'sourceSubdivisionKind':'parent_quarter' if kind=='planning_unit' else 'quarter',
    'sourceYear':2021,'sourcePage':27,'sourceDrawingIndices':indices,'sourceUrl':URL,
    'source':{'provider':'municipal-pdf-vector','url':URL,'path':PDF.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(PDF.read_bytes()).hexdigest(),'page':27},
    'georeferencingMethod':'Whole-municipality native map extent to current OSM municipality EOV extent; north-up assumption; WGS84 conversion.',
    'absoluteAccuracyMetres':None,'qualityScore':40,
    'approximationNotes':['Actual closed coloured source contours adopted. PDF implicit fill closure is preserved. Tiny native self-touch issues, if any, use make_valid.','Placement is approximate extent registration, not an independently measured georeference.','Distinct parent, urban and outer areas intentionally overlap; parent constituent names are not aliases for the full parent.']}
 features.append({'type':'Feature','id':'fehervar-oht2021:'+name,'properties':p,'geometry':mapping(geographic)})
(OUT/'fehervar-native-paths.json').write_text(json.dumps({'coordinateSpace':'PDF page27 points, NOT geographic','records':raw},ensure_ascii=False,separators=(',',':'))+'\n')
(OUT/'fehervar-registration.json').write_text(json.dumps({'sourcePdfRect':frame,'municipalityEovExtent':bounds,'method':'north-up extent fit','referenceMunicipalityOsm':municipality['properties']['source']['url'],'referenceSha256':hashlib.sha256(MUNICIPAL.read_bytes()).hexdigest(),'independentAccuracyTested':False},indent=2)+'\n')
(OUT/'fehervar-native-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
(OUT/'fehervar-native-summary.json').write_text(json.dumps({'featureCount':len(features),'sourceClosedDrawingCount':len(raw),'neighborhoodCount':sum(f['properties']['candidateBoundaryKind']=='neighbourhood' for f in features),'planningOrOuterAreaCount':sum(f['properties']['candidateBoundaryKind']=='planning_unit' for f in features),'sourceYear':2021,'sourceUrl':URL,'circleCount':0,'validGeometryCount':len(features),'nativeSourceBounds':frame},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'features':len(features),'sourceDrawingCount':len(raw),'sourceFrame':frame},ensure_ascii=False))
