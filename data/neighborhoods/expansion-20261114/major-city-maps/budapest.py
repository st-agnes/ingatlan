#!/usr/bin/env python3
"""Rough legal-sequence footprints for the remaining five Budapest names."""
import json,collections
from pathlib import Path
from shapely.geometry import Polygon,shape
import build
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
DEFINITIONS=build.read('data/neighborhoods/manual/budapest-definitions.json')['records']
REFERENCE='https://net.jogtar.hu/rendelet?council=fovaros&dbnum=104&docid=A1200094.FOV'

def common(name,g,method,sourcepaths,**extra):
 definition=next(x for x in DEFINITIONS if x['referenceName']==name)
 build.put(name,'Budapest',g,method,['data/neighborhoods/manual/budapest-definitions.json',*sourcepaths],[REFERENCE],district=23,referenceName=name,boundaryText=definition['boundaryText'],sourceParagraph=definition['sourceParagraph'],license='ODbL-1.0 for OSM geometries; statutory text source cited',attribution='© OpenStreetMap contributors',**extra)

if __name__=='__main__':
 anchors=json.loads((HERE/'evidence/budapest-rough-boundary-anchors.json').read_text())
 for x in anchors['units']:
  common(x['name'],Polygon(x['ring']),'legal_text_rough_trace',['data/neighborhoods/expansion-20261114/major-city-maps/evidence/budapest-rough-boundary-anchors.json','data/neighborhoods/expansion-20261114/major-city-maps/evidence/budapest-soroksar-streets.geojson','data/neighborhoods/manual/sources/budapest-torteneti-input.geojson','data/neighborhoods/manual/sources/budapest-wesselenyi-input.geojson'],approximationNotes=anchors['construction']+' '+x['uncertainSegments'])
 audit=build.read('data/neighborhoods/manual/budapest-wesselenyi-audit.json')
 assert len(audit['unidentifiedSourceFaces'])==1
 common('Wesselényi-telep',shape(audit['unidentifiedSourceFaces'][0]['geometry']),'legal_boundary_residential_proxy',['data/neighborhoods/manual/budapest-wesselenyi-audit.json','data/neighborhoods/manual/sources/budapest-wesselenyi-input.geojson'],approximationNotes='The retained face formed by railway, Vecsés út and residential edge is used as the explicitly approximate legal three-class footprint. Residential edge proxies the unknown historical built-up boundary. Source identity was previously deferred; accepted as a coarse estimate under the new collection policy.')
 (HERE/'budapest-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':build.FEATURES},ensure_ascii=False,separators=(',',':'))+'\n')
 print(collections.Counter(f['properties']['municipality'] for f in build.FEATURES))
