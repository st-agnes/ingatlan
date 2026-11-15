import json,hashlib
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon,MultiPolygon,shape,mapping
from shapely.ops import unary_union
from pyproj import Geod
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
URL='https://www.mve1985.hu/images/CLLD/I_resz.pdf'; IVS='https://www.movinnov.hu/docs/IVS-1.pdf'
def write(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
gcps=json.load(open(P/'control-points.json')); A=np.array([[*p,1] for p,c in gcps]);B=np.array([c for p,c in gcps]);M=np.linalg.lstsq(A,B,rcond=None)[0];GEOD=Geod(ellps='WGS84');features=[]
for u in json.load(open(P/'map-traces.json'))['units']:
 parts=u.get('parts',[u.get('pixels')]);polys=[]
 for part in parts:
  poly=Polygon([list(np.array([*p,1])@M) for p in part])
  if not poly.is_valid:raise ValueError(u['name'])
  polys.append(poly)
 poly=unary_union(polys)
 if not poly.is_valid:raise ValueError(u['name'])
 features.append(dict(type='Feature',id='estimated:mosonmagyarovar:clld2021:'+u['name'],properties=dict(name=u['name'],municipality='Mosonmagyaróvár',method='Coarse manual trace of the coloured 2021 city-history neighbourhood map, affinely georeferenced to archived OSM landmarks and road intersections.',estimated=True,lowConfidence=True,confidence='low',sourceUrl=URL,supportingUrls=[IVS,'https://www.openstreetmap.org/copyright'],approximationNote=u['note']+' The small schematic map and manual georeference support rough search areas only; local error may be tens to hundreds of metres.',sourcePeriod='2021 city-history map',sourceDocuments=[dict(url=URL,path=str(P.relative_to(ROOT))+'/source-clld2021.pdf',pdfPageOneBased=5)],boundaryKind='neighbourhood',quality='estimated-historical-map-trace',usableForAddressAssignment=False,areaM2=round(abs(GEOD.geometry_area_perimeter(poly)[0])),attribution='Mosonmagyaróvári Városvédő Egyesület; © OpenStreetMap contributors'),geometry=mapping(poly)))
castle=next(f for f in json.load(open(P/'source-areas.geojson'))['features'] if f['id']=='osm:way:99716536')
poly=shape(castle['geometry']); features.append(dict(type='Feature',id='estimated:mosonmagyarovar:var',properties=dict(name='Vár',municipality='Mosonmagyaróvár',method='Reuse of the unchanged original OSM named castle-ground polygon as a rough footprint for the Vár locality.',estimated=True,lowConfidence=True,confidence='low',sourceUrl='https://www.openstreetmap.org/way/99716536',supportingUrls=['https://www.openstreetmap.org/node/11587462683',URL],approximationNote='The named Vár locality point lies in the mapped Mosonmagyaróvári vár grounds. This uses that recognizable source site as an approximate search footprint; the castle neighbourhood may extend beyond the site. No radius or generated perimeter is used.',sourcePeriod='OSM snapshot 2026-11-12',boundaryKind='neighbourhood',source=castle['properties']['source'],quality='estimated-named-source-footprint',usableForAddressAssignment=False,areaM2=round(abs(GEOD.geometry_area_perimeter(poly)[0])),license='ODbL-1.0',attribution='© OpenStreetMap contributors'),geometry=castle['geometry']))
if (P/'street-traces.json').exists():
 for u in json.load(open(P/'street-traces.json'))['units']:
  poly=shape(u['geometry']);properties={k:v for k,v in u.items() if k not in ['geometry','id']};properties.update(municipality='Mosonmagyaróvár',estimated=True,lowConfidence=True,confidence='low',boundaryKind='neighbourhood',quality='estimated-source-street-envelope',usableForAddressAssignment=False,areaM2=round(abs(GEOD.geometry_area_perimeter(poly)[0])),license='ODbL-1.0',attribution='© OpenStreetMap contributors')
  features.append(dict(type='Feature',id=u['id'],properties=properties,geometry=u['geometry']))
write('features.geojson',dict(type='FeatureCollection',features=features))
write('build-proof.json',dict(featureCount=len(features),allValid=all(shape(f['geometry']).is_valid for f in features),crs='EPSG:4326',manualGeometryRepairApplied=False,affinePixelToWgs84=M.tolist(),controls=gcps,controlNote='Approximate visually selected castle locality and road junctions, not a surveyed fit. Zero three-point residual is not an accuracy measure.',inputSha256={n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in ['map-traces.json','control-points.json','source-clld-map.png','source-clld2021.pdf','source-ivs2008.pdf','source-ways.geojson','source-areas.geojson','source-named-points.geojson','street-traces.json','web-source-evidence.json']}))
print(len(features),'valid estimated polygons')
