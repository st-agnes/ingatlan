#!/usr/bin/env python3
"""Offline generation from archived source raster traces and source street polygons."""
import hashlib,json
from pathlib import Path
import numpy as np
from pyproj import Geod
from shapely.geometry import Polygon,shape,mapping
from shapely.ops import unary_union
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
URL='https://kbr.szombathely.hu/kbrfile/46469.pdf'
GEOD=Geod(ellps='WGS84')
def write(n,x): (P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(n): return hashlib.sha256((P/n).read_bytes()).hexdigest()
gcps=json.loads((P/'control-points.json').read_text())
A=np.array([[*xy,1] for xy,ll in gcps]); B=np.array([ll for xy,ll in gcps]); M=np.linalg.lstsq(A,B,rcond=None)[0]
traces=json.loads((P/'map-traces.json').read_text())
exclusion=unary_union([shape(f['geometry']) for f in json.loads((P/'source-unit15.geojson').read_text())['features']])
features=[]
core=json.loads((P/'existing-belvaros-documentary-trace.geojson').read_text())['features'][0]
corepoly=shape(core['geometry'])
features.append(dict(type='Feature',id='estimated:szombathely:ivs2013:1',properties=dict(name='Belváros (városmag)',municipality='Szombathely',method='Reuse of archived documentary road-centreline trace of municipal IVS annex1 unit1; source road geometry and ordered street-circuit proof are archived alongside this packet.',estimated=True,lowConfidence=True,confidence='low',sourceUrl=URL,supportingUrls=['https://www.openstreetmap.org/copyright'],approximationNote='Historical municipal unit1 is the narrower core described as Belváros (városmag). It is retained separately from the currently selected modern OSM Belváros footprint: areas approximately 0.662 versus 1.222 km² and intersection-over-union 0.483. Documentary street-side interpretation remains approximate. Existing archived coordinates are reused without alteration.',sourcePeriod='Municipal IVS 2013; OSM street geometry 2026',sourceUnitId=1,sourceDocuments=[dict(url=URL,path=str(P.relative_to(ROOT))+'/source-proof-pages.pdf',originalPdfPageOneBased=150,section='1. Belváros (városmag)')],sourceLineIds=core['properties'].get('sourceLineIds',[]),boundaryKind='neighbourhood',quality='estimated-documentary-street-trace',usableForAddressAssignment=False,areaM2=round(abs(GEOD.geometry_area_perimeter(corepoly)[0])),license='ODbL-1.0',attribution='Municipal IVS2013; © OpenStreetMap contributors'),geometry=core['geometry']))
for u in traces['units']:
 coords=[list(np.array([*xy,1])@M) for xy in u['pixels']]
 poly=Polygon(coords)
 if not poly.is_valid: raise ValueError('Invalid hand trace: '+u['name'])
 if u.get('excludeExistingSourceUnit15'):poly=poly.difference(exclusion)
 if not poly.is_valid or poly.is_empty:raise ValueError(u['name'])
 features.append(dict(type='Feature',id='estimated:szombathely:ivs2013:'+str(u['sourceId']),properties=dict(name=u['name'],municipality='Szombathely',method='Manual coarse trace of numbered historical municipal IVS overview-map unit; affine georeferencing to three archived OSM road junctions.',estimated=True,lowConfidence=True,confidence='low',sourceUrl=URL,supportingUrls=['https://www.openstreetmap.org/copyright'],approximationNote=u['note']+' The 480×476 raster supports only rough search-area geometry, with likely local uncertainty of tens to hundreds of metres. No point buffer or parent-place geometry was used.',sourcePeriod='KSH 2001 census / 2003 internal divisions, reproduced in municipal IVS 2013',sourceUnitId=u['sourceId'],sourceDocuments=[dict(url=URL,path=str(P.relative_to(ROOT))+'/source-proof-pages.pdf',originalPdfPageOneBased=50,section='Szombathely város belső tagozódása; numbered unit '+str(u['sourceId']))],boundaryKind='neighbourhood',quality='estimated-historical-map-trace',usableForAddressAssignment=False,areaM2=round(abs(GEOD.geometry_area_perimeter(poly)[0])),license='Source document evidence; OSM reference geometry ODbL-1.0',attribution='Municipal IVS2013 / KSH2003; © OpenStreetMap contributors'),geometry=mapping(poly)))
if (P/'estate-traces.json').exists():
 for u in json.loads((P/'estate-traces.json').read_text())['units']:
  poly=Polygon(u['coordinates'])
  if not poly.is_valid or poly.is_empty:raise ValueError(u['name'])
  features.append(dict(type='Feature',id='estimated:szombathely:estate:'+u['slug'],properties=dict(name=u['name'],municipality='Szombathely',method=u['method'],estimated=True,lowConfidence=True,confidence='low',sourceUrl=u['sourceUrl'],supportingUrls=u['supportingUrls'],approximationNote=u['approximationNote'],sourcePeriod='OSM snapshot 2026-11-12; contemporary textual location evidence',sourceLineIds=['way/'+str(i) for i in u['sourceWayIds']],namedPointSourceUrl='https://www.openstreetmap.org/node/'+str(u['node']),boundaryKind='neighbourhood',quality='estimated-source-street-block',usableForAddressAssignment=False,areaM2=round(abs(GEOD.geometry_area_perimeter(poly)[0])),license='ODbL-1.0',attribution='© OpenStreetMap contributors'),geometry=mapping(poly)))
write('features.geojson',dict(type='FeatureCollection',features=features))
write('build-proof.json',dict(schemaVersion=1,featureCount=len(features),geometryCrs='EPSG:4326',mapControlPoints=gcps,affinePixelToWgs84=M.tolist(),mapFitExplanation='Three visibly corresponding road junctions determine an affine transform. Zero fit residual at three controls is not an accuracy estimate; the old schematic raster and manual trace remain low-confidence.',manualRepairApplied=False,inputs={n:sha(n) for n in ['control-points.json','map-traces.json','source-overview.jpeg','source-proof-pages.pdf','source-boundary-definitions.json','source-unit15.geojson','source-ways.geojson','estate-traces.json','source-named-points.geojson','web-source-evidence.json','web-search-evidence.json','existing-belvaros-documentary-trace.geojson','source-unit1-trace-proof.json']},features=[dict(name=f['properties']['name'],valid=shape(f['geometry']).is_valid,areaM2=f['properties']['areaM2'],estimated=True) for f in features]))
print('Generated',len(features),'valid estimated source-defined polygons.')
