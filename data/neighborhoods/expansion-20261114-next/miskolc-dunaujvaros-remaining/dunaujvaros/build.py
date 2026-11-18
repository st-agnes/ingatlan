#!/usr/bin/env python3
"""Six deliberately coarse Dunaújváros corridor/context traces, not official borders."""
from pathlib import Path
import collections, gzip, hashlib, json, shutil
from shapely.geometry import Point, Polygon, mapping, shape
from pyproj import Geod

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
DATA=ROOT/'data/neighborhoods'
PDF='https://dunaujvaros.hu/sites/all/files/dokumentumok/8060/35496.pdf'
LAW='https://njt.jog.gov.hu/jogszabaly/2003-19-SP-5Y3929'
write=lambda name,obj:(HERE/name).write_text(json.dumps(obj,ensure_ascii=False,separators=(',',':'))+'\n')

specs=[
 {'name':'Újtelep','page':11,'corridors':['6-os főút','Petőfi Sándor utca','Aranyvölgyi út','MÁV állomás'],
  'inference':'The unlocated southern cadastral edge is estimated from the visible station/road context. No cadastral precision claimed.',
  'ring':[[18.9126,46.9808],[18.91344,46.98058],[18.9155,46.9799],[18.91881,46.97915],[18.92017,46.9783],[18.9211,46.97755],[18.92276,46.97622],[18.92293,46.9758],[18.92453,46.9749],[18.92607,46.97436],[18.92732,46.97385],[18.9265,46.9727],[18.923,46.9732],[18.9189,46.9729],[18.9152,46.9725],[18.912,46.974],[18.911,46.9761],[18.9093,46.9781],[18.9126,46.9808]]},
 {'name':'Táborállás','page':11,'corridors':['Felsőfoki-patak','Üdülő sor','Barsi Dénes utca','Magyar út'],
  'inference':'Unlocated numbered parcel/road edges are estimated using the mapped Barsi/Üdülő/Magyar corridor arrangement and the source place label.',
  'ring':[[18.93148,46.98837],[18.93395,46.98912],[18.9358,46.9899],[18.93763,46.99036],[18.93992,46.98907],[18.9409,46.9885],[18.9411,46.9873],[18.9404,46.9857],[18.9397,46.9844],[18.93864,46.98294],[18.9366,46.9836],[18.93383,46.98501],[18.93262,46.98659],[18.93148,46.98837]]},
 {'name':'Római városrész','page':12,'corridors':['Apáczai Csere János utca','Batsányi út','Martinovics Ignác utca','Pince sor','felső partél'],
  'inference':'Cliff and unlocated cadastral portions are coarse connections estimated from nearby actual road/stream context. The inner Martinovics/Római streets are contextual references, not claimed to be every outer legal edge.',
  'ring':[[18.93317,46.97732],[18.9359,46.9768],[18.9366,46.9758],[18.9382,46.9742],[18.9386,46.9721],[18.93848,46.97089],[18.93739,46.97052],[18.93674,46.96991],[18.93639,46.96962],[18.93491,46.96826],[18.93452,46.96764],[18.93402,46.96739],[18.93252,46.96722],[18.93194,46.96932],[18.92961,46.97123],[18.92868,46.97271],[18.9298,46.974],[18.9319,46.9756],[18.93317,46.97732]]},
 {'name':'Barátság városrész','page':13,'corridors':['Eszperantó út','Sikló út','Duna sor','Velinszky László utca','partél'],
  'inference':'The eastern cliff and care-home parcel/fence edges are manually approximated from the actual surrounding street layout; cadastral details remain unlocated.',
  'ring':[[18.94731,46.95972],[18.94628,46.95895],[18.94588,46.95871],[18.9457,46.95849],[18.94621,46.95812],[18.94661,46.95784],[18.94881,46.9564],[18.94973,46.95578],[18.95103,46.95496],[18.95334,46.95527],[18.95355,46.9562],[18.9533,46.9571],[18.9525,46.9581],[18.9518,46.959],[18.9498,46.9604],[18.9481,46.9609],[18.94731,46.95972]]},
 {'name':'Duna sor','page':None,'corridors':['Duna sor','Velinszky László utca','Alsó Duna-parti út'],
  'inference':'Informal fine search area: a small manually drawn inhabited street-context patch around the source name point and the northern Duna sor frontage. No independent municipal quarter boundary is asserted; overlap with larger quarters is intentional.',
  'ring':[[18.9448,46.962],[18.946,46.962],[18.94675,46.961],[18.9472,46.9605],[18.9475,46.96],[18.9481,46.9595],[18.9474,46.959],[18.9463,46.9595],[18.9455,46.9598],[18.9449,46.9605],[18.9444,46.9614],[18.9448,46.962]]},
 {'name':'Dunapart','page':14,'corridors':['Alsó Duna-parti út','Duna sor','Batsányi út','Panoráma út','Duna-part'],
  'inference':'A coarse central riverfront/cliff-belt extent using the actual road and river context. The long legal parcel sequence is not reconstructed cadastrally; southern industrial riverfront detail is outside this approximate central footprint. This is an approximate useful search extent, not the complete legal border.',
  'ring':[[18.9369,46.977],[18.936,46.9749],[18.9381,46.9731],[18.9388,46.9709],[18.9396,46.9694],[18.9408,46.9672],[18.9427,46.9641],[18.9451,46.9616],[18.9473,46.9602],[18.9504,46.9571],[18.9533,46.9553],[18.9548,46.9549],[18.9549,46.9585],[18.9538,46.9615],[18.9527,46.965],[18.9511,46.9685],[18.949,46.9731],[18.9465,46.9773],[18.9425,46.9797],[18.9397,46.9794],[18.9382,46.9785],[18.9369,46.977]]},
]

if not (HERE/'source-context-lines.geojson').exists():
    source_path=Path('/workspace/ingatlan/.local/neighborhoods/dunaujvaros-all-local-source-lines.geojson')
    raw=json.loads(source_path.read_text())['features']
    wanted={name for spec in specs for name in spec['corridors']}
    wanted.update(['Magyar út','Üdülő sor','Felsőfoki-patak','Barsi Dénes utca','Duna','Római körút','Petőfi Sándor utca','Aranyvölgyi út','Baracsi út'])
    local=[f for f in raw if f['properties'].get('name') in wanted or f['properties'].get('source',{}).get('tags',{}).get('ref')=='6']
    write('source-context-lines.geojson',{'type':'FeatureCollection','features':local,
        'originalLocalPath':str(source_path),'originalLocalSha256':hashlib.sha256(source_path.read_bytes()).hexdigest(),
        'coordinatesUnchanged':True})
if not (HERE/'source-municipality.geojson').exists():
    shutil.copyfile(DATA/'sources/municipal-dunaujvaros-next/municipality.geojson',HERE/'source-municipality.geojson')
if not (HERE/'source-name-points.geojson').exists():
    nodes=json.loads(gzip.decompress((DATA/'sources/country-osm/named-nodes.geojson.gz').read_bytes()))['features']
    write('source-name-points.geojson',{'type':'FeatureCollection','features':[f for f in nodes if f['properties'].get('municipality')=='Dunaújváros']})

municipality=shape(json.loads((HERE/'source-municipality.geojson').read_text())['features'][0]['geometry'])
points={f['properties']['name']:f for f in json.loads((HERE/'source-name-points.geojson').read_text())['features']}
lines=json.loads((HERE/'source-context-lines.geojson').read_text())['features']
geod=Geod(ellps='WGS84');features=[];facts=[]
for spec in specs:
    name=spec['name'];g=Polygon(spec['ring']).intersection(municipality)
    assert g.is_valid and not g.is_empty and g.covers(shape(points[name]['geometry'])),name
    area=abs(geod.geometry_area_perimeter(g)[0])
    assert 5000 < area < 2500000,(name,area)
    fact={'name':name,'pdfPageOneBased':spec['page'],'corridors':spec['corridors'],'inference':spec['inference']}
    facts.append(fact)
    source={'provider':'manual-legal-corridor-context-inference' if spec['page'] else 'manual-osm-street-context-inference',
        'url':PDF if spec['page'] else points[name]['properties']['source']['url'],
        'contextPath':str((HERE/'source-context-lines.geojson').relative_to(ROOT)),
        'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors; municipal planning text cited as factual context.'}
    properties={'name':name,'municipality':'Dunaújváros','method':'legal_corridor_coarse_trace_estimate' if spec['page'] else 'named_street_context_coarse_estimate',
        'estimated':True,'semanticFootprint':True,'qualityScore':25 if spec['page'] else 20,'pointRadiusFallback':False,
        'source':source,'sourceUrl':source['url'],'evidenceUrls':[PDF,LAW] if spec['page'] else [source['url']],
        'sourceGeometryUnmodified':False,'manualCoarseConnections':True,'pdfPageOneBased':spec['page'],
        'referenceCorridors':spec['corridors'],'contextSourceWayIds':[f['id'] for f in lines if f['properties'].get('name') in spec['corridors']],
        'namePoint':{'id':points[name]['id'],'coordinates':points[name]['geometry']['coordinates'],'sourceUrl':points[name]['properties']['source']['url']},
        'approximateAreaSquareMetres':round(area,1),'approximationNote':spec['inference'],
        'geometryProcessing':'Manual coarse line trace informed by observed actual street/stream/river context and cited legal-corridor facts, clipped to the unchanged source municipality. Unlocated parcel/cliff edges use explicit approximate connectors. No circle or nearest-label partition.'}
    features.append({'type':'Feature','id':'dunaujvaros-coarse:'+name,'geometry':mapping(g),'properties':properties})
write('trace-specifications.json',{'schemaVersion':1,'specifications':specs})
write('source-facts.json',{'schemaVersion':1,'municipalConceptUrl':PDF,'corroboratingMunicipalLawUrl':LAW,
    'retrievalMethod':'Public read-only web connector; street geometry from existing local PBF extracts. No shell network requests.',
    'municipalPdfBytesArchived':False,'facts':facts,'statutoryBoundaryAccuracyAsserted':False})
write('features.geojson',{'type':'FeatureCollection','features':features})
summary={'schemaVersion':1,'featureCount':len(features),'municipality':'Dunaújváros','names':[f['properties']['name'] for f in features],
    'methods':dict(collections.Counter(f['properties']['method'] for f in features)),
    'sourceContextWayCount':len(lines),'circleCount':0,'voronoiCount':0,'manualCoarseConnections':True,
    'sourceGeometryUnmodified':False,'featuresSha256':hashlib.sha256((HERE/'features.geojson').read_bytes()).hexdigest(),
    'completeGeographicBoundaryAccuracy':False,'areasSquareMetres':{f['properties']['name']:f['properties']['approximateAreaSquareMetres'] for f in features}}
write('summary.json',summary)
write('validation.json',{'featureCount':len(features),'validGeometryCount':sum(shape(f['geometry']).is_valid for f in features),
    'allSixSourceNamePointsInside':True,'duplicateMunicipalityNameCount':0,'allInsideSourceMunicipality':all(municipality.covers(shape(f['geometry'])) for f in features),
    'circlesGenerated':0,'geographicAccuracyReviewed':False,'featuresSha256':summary['featuresSha256']})
print(json.dumps(summary,ensure_ascii=False))
