#!/usr/bin/env python3
from pathlib import Path
import json,gzip,math
from PIL import Image,ImageDraw,ImageFont
from shapely.geometry import shape,box,Point
from shapely.ops import transform,unary_union
from pyproj import Transformer
P=Path(__file__).resolve().parent;S=P/'source-inputs';tr=Transformer.from_crs(4326,23700,always_xy=True).transform
candidate=json.load(open(P/'arkoshaza-road-municipality-proposal.geojson'))['features'][0];g=shape(candidate['geometry']);municipality=unary_union([shape(f['geometry']) for f in json.load(open(S/'arkoshaza-municipality.geojson'))['features']]);pt=Point(16.7722417,46.8252895)
labels=json.load(open(S/'arkoshaza-labels.geojson'))['features'];buildings=json.load(gzip.open(S/'arkoshaza.geojson.gz','rt'))['features'];areas=json.load(gzip.open(S/'arkoshaza-areas.geojson.gz','rt'))['features'];roads=json.load(gzip.open(S/'arkoshaza-roads.geojson.gz','rt'))['features']
inside_labels=[{'name':f['properties']['name'],'sourceId':f['id'],'coordinates':f['geometry']['coordinates']} for f in labels if g.covers(shape(f['geometry']))]
inside_buildings=[f['id'] for f in buildings if g.intersects(shape(f['geometry']))]
inside_residential=[f['id'] for f in areas if f['properties']['tags'].get('landuse') in ['residential','farmyard','industrial'] and transform(tr,g.intersection(shape(f['geometry']))).area>100]
lon,lat=pt.coords[0];dy=1500/111320;dx=dy/math.cos(math.radians(lat));building_window=box(lon-dx,lat-dy,lon+dx,lat+dy)
proof={'name':'Árkosháza-puszta','municipality':'Babosdöbréte','geographicInterpretation':'Native-road-bounded rural tract north of the present Babosdöbréte village core and containing the historical name point. Its northern closure uses the actual municipal boundary. No other known place label or native residential/farmyard/industrial surface lies inside. This is representative landscape, not a recovered estate perimeter or an occupied village.','insidePlaceLabels':inside_labels,'insideExtractedBuildings':inside_buildings,'insideResidentialFarmyardIndustrialSurfaceIds':inside_residential,'buildingExtractionWindowCoverageOfTractFraction':round(transform(tr,g.intersection(building_window)).area/transform(tr,g).area,4),'buildingEvidenceLimitation':'Anonymous-building extraction is only within a 1.5 km rectangular window about the source point; the northern tip outside that window has no completeness claim for buildings. Full municipality labels and native land-use/road context were checked there.','coherentRuralTract':len(inside_labels)==1 and not inside_buildings and not inside_residential,'map':'arkoshaza-landscape-review.png','historicEstateBoundaryKnown':False,'representativeLandscapeTract':True,'disappearedSettlement':True,'partialFootprint':True,'lowConfidence':True,'recommendedQuality':9}
(P/'arkoshaza-geographic-review.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
bounds=(16.757,46.813,16.791,46.847);W,H=1000,1450;view=box(*bounds)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14);small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',11)
def xy(c):return ((c[0]-bounds[0])/(bounds[2]-bounds[0])*W,(bounds[3]-c[1])/(bounds[3]-bounds[1])*H)
im=Image.new('RGB',(W,H),'white');d=ImageDraw.Draw(im)
for f in areas:
 h=shape(f['geometry']);t=f['properties']['tags']
 if h.geom_type!='Polygon' or not h.intersects(view):continue
 color='#dceccf' if t.get('landuse')=='forest' or t.get('natural') in ['wood','scrub'] else '#dbeaff' if t.get('natural')=='water' else '#eadfd1' if t.get('landuse')=='residential' else '#f5f0dc'
 d.polygon([xy(c) for c in h.exterior.coords],fill=color,outline='#aaa')
for f in roads:
 h=shape(f['geometry']);t=f['properties']['tags']
 if not h.intersects(view):continue
 color='#2466aa' if t.get('waterway') else '#555' if t.get('highway') in ['secondary','tertiary','residential'] else '#aaa'
 d.line([xy(c) for c in h.coords],fill=color,width=2)
for f in buildings:
 h=shape(f['geometry'])
 if h.intersects(view):d.polygon([xy(c) for c in h.exterior.coords],fill='#333')
for ring in [g.exterior,*g.interiors]:d.line([xy(c) for c in ring.coords],fill='#d02c2c',width=4)
for h in [municipality] if municipality.geom_type=='Polygon' else municipality.geoms:d.line([xy(c) for c in h.exterior.coords],fill='#298a42',width=2)
# Dashed-looking building-window border is diagnostic context only, never a candidate edge.
x0,y1=xy((building_window.bounds[0],building_window.bounds[1]));x1,y0=xy((building_window.bounds[2],building_window.bounds[3]));d.rectangle((x0,y0,x1,y1),outline='#8f71af',width=1)
for f in labels:
 if f['geometry']['type']!='Point':continue
 x,y=xy(f['geometry']['coordinates'])
 if 0<x<W and 0<y<H:d.ellipse((x-5,y-5,x+5,y+5),fill='#174ce6');d.text((x+7,y),f['properties']['name'],font=font,fill='#174ce6',stroke_width=1,stroke_fill='white')
d.rectangle((0,0,W,65),fill='white');d.text((8,6),'Árkosháza: reviewed rural representative tract, NOT a recovered historic perimeter',font=font,fill='black');d.text((8,27),'Red = candidate; green = actual municipal border; purple = building-extract window',font=small,fill='black');d.text((8,44),'Buildings = black; land use/roads = native OSM context. The forest is an interior exclusion.',font=small,fill='black')
for x in range(0,W,200):d.text((x,H-22),str(round(bounds[0]+x/W*(bounds[2]-bounds[0]),5)),font=small,fill='blue')
for y in range(150,H-30,200):d.text((0,y),str(round(bounds[3]-y/H*(bounds[3]-bounds[1]),5)),font=small,fill='blue')
im.save(P/'arkoshaza-landscape-review.png');print(json.dumps(proof,ensure_ascii=False,indent=2))
