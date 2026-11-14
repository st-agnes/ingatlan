#!/usr/bin/env python3
"""Broad named-quarter estimates from actual local road corridors and legal facts."""
import json,gzip,collections
from pathlib import Path
from shapely.geometry import shape,Point,LineString
from shapely.ops import unary_union,polygonize,split
import build
HERE=Path(__file__).resolve().parent
LINES='data/neighborhoods/expansion-20261114/major-city-more/evidence/dunaujvaros-major-source-lines.geojson'
CITY='data/neighborhoods/sources/municipal-dunaujvaros-next/municipality.geojson'
FACTS='data/neighborhoods/sources/municipal-dunaujvaros-next/source-facts.json'
POINTS='data/neighborhoods/sources/country-osm/named-nodes.geojson.gz'
SOURCE_URL='https://dunaujvaros.hu/sites/all/files/dokumentumok/8060/35496.pdf'
METHOD='road_corridor_inferred_area'
if __name__=='__main__':
 lines=build.read(LINES)['features'];city=shape(build.read(CITY)['features'][0]['geometry'])
 faces=list(polygonize(unary_union([shape(f['geometry'])for f in lines]+[city.boundary])))
 pts=json.loads(gzip.decompress((build.ROOT/POINTS).read_bytes()))['features']
 pts={f['properties']['name']:f for f in pts if f['properties'].get('municipality')=='Dunaújváros'}
 # These coarse dividers distinguish named sectors inside a larger actual road face.
 # They deliberately do not assert cadastral parcel edges or exact legal limits.
 dividers={'Óváros':[[18.90,46.985],[18.95,46.985]],'Északi lakóterület':[[18.90,46.985],[18.95,46.985]],'Béke városrész':[[18.90,46.9675],[18.94,46.9675]],'Újpentele':[[18.90,46.9675],[18.94,46.9675]],'Kertváros':[[18.927,46.95],[18.927,46.98]],'Technikum városrész':[[18.927,46.95],[18.927,46.98]]}
 selections=[]
 for name in ['Belváros','Óváros','Északi lakóterület','Béke városrész','Újpentele','Kertváros','Technikum városrész','Dunai Vasmű']:
  point=Point(pts[name]['geometry']['coordinates'])
  chosen=[f for f in faces if f.covers(point)];assert len(chosen)==1,name
  g=chosen[0].intersection(city)
  if name in dividers:
   parts=[f for f in split(g,LineString(dividers[name])).geoms if f.geom_type=='Polygon']
   side=[f for f in parts if f.covers(point)];assert len(side)==1,name;g=side[0]
  build.put('Dunaújváros',name,g,[LINES,CITY,FACTS,POINTS],[SOURCE_URL,'https://njt.jog.gov.hu/jogszabaly/2003-19-SP-5Y3929',pts[name]['properties']['source']['url']],METHOD,approximationNotes='LOW-CONFIDENCE broad search-area estimate. Actual named major roads and the municipal contour form the outer sectors. The municipal concept/legal facts establish these quarter names and corridor-style divisions, but exact parcel/terrace edges are not known. Larger shared road faces use a simple explicit manual north/south or east/west divider; the named point only selects the proper side. These estimated internal lines are not claimed as observed source boundaries. No radius or circular footprint.',estimatedDividerWgs84=dividers.get(name),sourcePoint=pts[name],sourceSubdivisionKind='coarse_quarter_search_estimate',license='ODbL-1.0',attribution='© OpenStreetMap contributors')
  selections.append({'name':name,'outerFaceAreaSquareDegrees':chosen[0].area,'outputAreaSquareDegrees':g.area,'estimatedDividerWgs84':dividers.get(name)})
 (HERE/'dunaujvaros-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':build.FEATURES},ensure_ascii=False,separators=(',',':'))+'\n')
 (HERE/'evidence/dunaujvaros-inference.json').write_text(json.dumps({'actualSourceLineCount':len(lines),'derivedRoadFaceCount':len(faces),'selectedQuarterCount':len(selections),'circleFallbackCount':0,'lowConfidence':True,'sourceMapShapeVerificationPerformed':False,'selections':selections},ensure_ascii=False,indent=2)+'\n')
 print(collections.Counter(f['properties']['municipality']for f in build.FEATURES))
