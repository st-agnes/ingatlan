#!/usr/bin/env python3
"""Offline source-confirmed Kecskemét central circuit; no inferred closing edges."""
import argparse, gzip, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/neighborhoods/sources/municipal-offline-more'
ROADS=ROOT/'data/neighborhoods/sources/municipal-offline-next/kecskemet-all-local-roads.geojson'
ROADS_SHA='c8a1efef355fa22f676098d5dbf557bf2f308920c4af6da42ad58fce80c77a86'
SOURCE=ROOT/'data/neighborhoods/sources/municipal-maps-next/kecskemet-source-pages.pdf'
SOURCE_SHA='9b8663136f085c0c7ec307c3e92cbad02937336b5c5265f67128d623b45df2ee'
PDF_SHA='83f78c5dbb85964a1fc4aecb2df014254e1985fdb446d8135182dedad56da939'
URL='https://kecskemet.hu/uploaded_files/files/document/2022-11/126_2021._%28XII.16%29_hatarozat_1._melleklete_II-es_kotet.pdf'
CORE=['Dobó István körút','Horváth Döme körút','Batthyány utca','Csányi János körút','Koháry István körút','Hornyik János körút','Gáspár András körút']
TRANSITIONS=['Bajcsy-Zsilinszky Endre körút','Piaristák tere','Széchenyi tér','Szilády Károly utca','Kölcsey utca']
UNNAMED_CORRIDOR_CLASSES={'primary','secondary','tertiary','trunk','primary_link','secondary_link','tertiary_link','trunk_link'}
METHOD='Municipal2021 source-map-confirmed surface street circuit using literal2026 OSM vertices and consecutive-node edges. Named square transitions and the source-map eastern Bajcsy corridor resolve omissions in the short text. Grade-separated ways are excluded before polygonization; no clipping, repair, hole removal, snap, buffer or invented closure.'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def encode(d):return (json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode()
def save(path,d,check):
 b=encode(d)
 if check:
  if not path.exists() or path.read_bytes()!=b:raise ValueError('Missing/stale '+str(path))
 else:path.write_bytes(b)
def surface(f):
 t=f['properties']['source']['tags']
 return t.get('bridge') in [None,'no'] and t.get('tunnel') in [None,'no'] and t.get('layer') in [None,'0']
def main(check=False):
 from shapely.geometry import shape,mapping
 from shapely.ops import unary_union,polygonize
 from pyproj import Geod
 if sha(ROADS)!=ROADS_SHA or sha(SOURCE)!=SOURCE_SHA:raise ValueError('Changed actual source input')
 OUT.mkdir(parents=True,exist_ok=True)
 allroads=json.loads(ROADS.read_text())['features'];roads=[f for f in allroads if surface(f)]
 selected=[f for f in roads if f['properties']['name'] in CORE+TRANSITIONS]
 context=unary_union([shape(f['geometry']) for f in selected])
 # Acquisition only: this distance never creates an output polygon or vertex.
 selected += [f for f in roads if not f['properties']['name'] and (f['properties']['source']['tags'].get('junction')=='roundabout' or f['properties']['source']['tags']['highway'] in UNNAMED_CORRIDOR_CLASSES) and shape(f['geometry']).distance(context)<.0008]
 geoms=[shape(f['geometry'])for f in selected];matches=[]
 for g in polygonize(unary_union(geoms)):
  used=[f for f,line in zip(selected,geoms) if g.boundary.intersection(line).length>1e-10]
  names={f['properties']['name']for f in used}
  if set(CORE)<=names:matches.append((g,used,names))
 if len(matches)!=1:raise ValueError('Expected one source circuit fulfilling all seven core streets')
 g,used,names=matches[0]
 coords=list(g.exterior.coords)
 if not g.is_valid or g.interiors or coords[0]!=coords[-1]:raise ValueError('Invalid/holed/open source circuit; no repair permitted')
 edges={tuple(sorted((tuple(a),tuple(b))))for f in used for a,b in zip(f['geometry']['coordinates'],f['geometry']['coordinates'][1:])}
 if any(tuple(sorted((tuple(a),tuple(b))))not in edges for a,b in zip(coords,coords[1:])):raise ValueError('Nonliteral source edge')
 country=ROOT/'data/neighborhoods/sources/country-osm';parentraw=gzip.decompress((country/'municipalities.geojson.gz').read_bytes())
 parent=next(f for f in json.loads(parentraw)['features']if f['properties']['name']=='Kecskemét' and f['properties'].get('usedForAssociation'))
 if not shape(parent['geometry']).covers(g):raise ValueError('Outside canonical municipality')
 prior=[]
 for p in [ROOT/'data/neighborhoods/sources/municipal-maps-next/kecskemet-manual.geojson',ROOT/'data/neighborhoods/sources/municipal-offline-next/kecskemet-next.geojson']:
  prior += json.loads(p.read_text())['features']
 if any(g.intersection(shape(f['geometry'])).area>1e-13 for f in prior):raise ValueError('Interior overlap with previous source quarters')
 geod=Geod(ellps='WGS84');area,perimeter=geod.geometry_area_perimeter(g)
 docs=[{'url':URL,'sha256':PDF_SHA,'printedPage':143,'pdfPageOneBased':145,'corroboratingMapPrintedPage':141,'corroboratingMapPdfPageOneBased':143,'figure':73,'adjacentErzsebetvarosPrintedPage':150}]
 p={'name':'Városközpont','municipality':'Kecskemét','boundaryKind':'neighbourhood','canonicalNameIsNeighborhood':True,
    'method':METHOD,'evidenceUrls':[URL],'sourceDocuments':docs,'sourcePeriod':'2021municipal source with actual2026-11-12 OSM roads',
    'sourceLineIds':sorted(f['id']for f in used),'estimated':False,'sourceIsOfficial':False,'sourceIsHardBoundary':False,
    'usableForAddressAssignment':False,'currentNameEvidence':{'status':'municipal_document_name_only','matchingCurrentOsmLabelFound':False,'currentNameIndependentlyConfirmed':False},
    'reviewNotes':['The exact current Városközpont place-label point was not found; the2021document explicitly names and delimits this fine quarter. The broad Belváros point is not substituted as its label.',
       'Actual Bajcsy-Zsilinszky Endre körút forms the eastern source-map boundary and is corroborated by adjacent Erzsébetváros; its omission from the brief text does not justify the rejected Katona József tér interior shortcut.',
       'Underground ways and unnamed internal parking/service loops are excluded before topology; only actual arterial/link/roundabout unnamed pieces may complete this mapped ring. No resulting hole is deleted afterward.',
       'Square/current street-name transitions follow the published source map. Absolute/current/legal boundary accuracy and road-side assignment remain unverified.'],
    'geometryVerificationStatus':'source_map_corroborated_surface_street_circuit_not_surveyed','reviewStatus':'source_based_boundary_review_required',
    'areaM2':abs(area),'perimeterM':perimeter,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors; municipal boundary facts: Kecskemét2021 Megalapozó VizsgálatII, printed143 and figure73 printed141'}
 f={'type':'Feature','id':'manual:kecskemet-offline-more:varoskozpont','properties':p,'geometry':mapping(g)}
 output=OUT/'kecskemet-varoskozpont.geojson';save(output,{'type':'FeatureCollection','features':[f]},check)
 save(OUT/'source-way-subset.geojson',{'type':'FeatureCollection','features':sorted(used,key=lambda f:f['id'])},check)
 proof={'schemaVersion':1,'quarter':'Városközpont','actualRoadSource':{'path':str(ROADS.relative_to(ROOT)),'sha256':ROADS_SHA},'municipalSource':{'url':URL,'publisherPdfSha256':PDF_SHA,'archivedSubsetPath':str(SOURCE.relative_to(ROOT)),'archivedSubsetSha256':SOURCE_SHA},
    'method':METHOD,'coreStreetNames':CORE,'mapConfirmedTransitionNames':TRANSITIONS,'allUsedNames':sorted(names),
    'gradeSeparatedWaysExcludedBeforeTopology':True,'unnamedJunctionFilter':'actual roundabout or arterial/link class only; interior service/parking loops are not source quarter boundaries','excludedGradeSeparatedSourceIds':sorted(f['id']for f in allroads if not surface(f)),
    'valid':True,'literalClosed':True,'holes':0,'vertices':len(coords),'sourceWays':len(used),'allEdgesLiteralConsecutiveSourceEdges':True,
    'inferredEdgeCount':0,'canonicalParentContained':True,'interiorOverlapWithPriorFourQuarters':False,'currentFineNamePointPresent':False,
    'noAbsoluteAccuracyClaim':True,'usableForAddressAssignment':False,'rejectedDiagnostic':'Városközpont-ordered-diagnostic.geojson cuts through the quarter via Katona József tér; never import it.',
    'outputSha256':hashlib.sha256(encode({'type':'FeatureCollection','features':[f]})).hexdigest()}
 save(OUT/'trace-proof.json',proof,check)
 save(OUT/'registry-entry.json',{'id':'kecskemet-varoskozpont','path':str(output.relative_to(ROOT)),'sha256':proof['outputSha256'],'municipality':'Kecskemét','method':METHOD,'evidenceUrls':[URL],'sourceDocuments':docs,'license':'ODbL-1.0','propertyOverrides':{'boundaryKind':'neighbourhood','canonicalNameIsNeighborhood':True,'usableForAddressAssignment':False},'reviewPath':str((OUT/'south-source-review.json').relative_to(ROOT)),'rightsStatus':'OSM road geometry ODbL-1.0; municipal illustration reuse rights not independently established.'},check)
 print(json.dumps({'quarter':'Városközpont','vertices':len(coords),'areaM2':round(abs(area)),'sourceWays':len(used),'check':check},ensure_ascii=False))
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args();main(args.check)
