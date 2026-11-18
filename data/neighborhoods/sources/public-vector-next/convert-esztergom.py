#!/usr/bin/env python3
"""Describe pinned historical Esztergom geometry without changing any source vertex.

All inputs are preserved local files. --check compares regenerated outputs only.
The dataset's government citation has not been independently retrieved; neither
the software's MIT licence nor later name evidence establishes data reuse rights
or present-day/legal boundary accuracy.
"""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import unicodedata

from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
COMMIT = '48ba05ad4c6969e3b3c25735492169227ae411f1'
REPO = 'codeforgermany/click_that_hood'
RAW = OUT/'esztergom.source.geojson'
META = OUT/'esztergom.metadata.source.json'
GIT_SHA = 'f24bdf1489d74c081b8f78086cf09bfb43016c81'
URL = f'https://github.com/{REPO}/blob/{COMMIT}/public/data/esztergom.geojson'
META_URL = f'https://github.com/{REPO}/blob/{COMMIT}/public/data/esztergom.metadata.json'
METHOD = ('Unmodified historical Esztergom quarter GeoJSON from a pinned public '
          'repository. Metadata cites a2008municipal proposal/decree location; '
          'feature timestamps are2013-11-28, not a verified survey date. '
          'No coordinate transformation, clipping, snapping, repair, buffer, '
          'or generated closing edges.')
LICENSE = 'Individual dataset licence not specified; upstream software MIT; cited municipal source not retrieved'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFD',s).casefold() if c.isalnum())

def encode(d):
    return (json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode()

def build():
    raw = RAW.read_bytes()
    assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==GIT_SHA
    source=json.loads(raw); meta=json.loads(META.read_bytes())
    assert source['type']=='FeatureCollection' and meta['locationName']=='Esztergom'
    assert len(source['features'])==33
    parent_path=ROOT/'data/neighborhoods/sources/country-osm/municipalities.geojson.gz'
    points_path=ROOT/'data/neighborhoods/sources/country-osm/named-nodes.geojson.gz'
    parents=json.loads(gzip.decompress(parent_path.read_bytes()))['features']
    parent=next(f for f in parents if f['properties'].get('name')=='Esztergom' and f['properties'].get('usedForAssociation'))
    points=json.loads(gzip.decompress(points_path.read_bytes()))['features']
    points=[f for f in points if f['properties'].get('municipality')=='Esztergom']
    names=json.loads((OUT/'official-name-evidence.json').read_bytes())
    name_set={norm(n) for n in names['names']}
    metric=Transformer.from_crs(4326,3035,always_xy=True).transform
    pg=shape(parent['geometry']); features=[]; reviews=[]; ids=set()
    for i, original in enumerate(source['features']):
        op=original['properties']; name=op['name']; ident=op['cartodb_id']
        assert ident not in ids
        ids.add(ident)
        g=shape(original['geometry']); assert g.is_valid and not g.is_empty
        area=transform(metric,g).area
        outside=transform(metric,g.difference(pg)).area
        match=[]
        for node in points:
            np=node['properties']; tags=np['source']['tags']
            aliases=[np['name']]+tags.get('alt_name','').split(';')
            if norm(name) not in {norm(a.strip()) for a in aliases}: continue
            match.append({'id':node['id'],'name':np['name'],'aliases':aliases,
                'coordinates':node['geometry']['coordinates'],
                'pointInsideHistoricalPolygon':g.covers(shape(node['geometry'])),
                'pointInsideCanonicalMunicipality':pg.covers(shape(node['geometry'])),
                'sourceUrl':np['source']['url']})
        municipal_name=norm(name) in name_set
        industrial=name=='Ipari park'
        kind='local_area' if industrial else 'neighbourhood'
        status=('current_osm_name_present' if match else
                'municipal_name_used_2023' if municipal_name else
                'not_separately_verified')
        audit={'sourceFeatureIndex':i,'sourceCartodbId':ident,'name':name,
               'validGeometry':True,'geometryChanged':False,'areaM2':area,
               'outsideParentAreaM2':outside,'insideParentAreaFraction':1-outside/area,
               'parentFullyContains':pg.covers(g),'boundaryKind':kind,
               'currentNameStatus':status,'municipalNameUse2023':municipal_name,
               'matchingCurrentOsmNamePoints':match}
        feature=copy.deepcopy(original)
        feature['id']=f'esztergom-2013:{ident}'
        feature['properties']={**op,'municipality':'Esztergom','sourceName':name,
            'boundaryKind':kind,'canonicalNameIsNeighborhood':not industrial,
            'method':METHOD,'evidenceUrls':[URL,META_URL]+([names['sourceUrl']] if municipal_name else []),
            'sourceDocuments':[{'url':URL,'sha256':sha(raw),'gitBlobSha1':GIT_SHA},
                {'url':META_URL,'sha256':sha(META.read_bytes()),'governmentCitationUrl':meta['dataUrl'],
                 'citationTitle':meta['dataTitle'],'citedGovernmentDocumentRetrieved':False}],
            'sourceFeatureIndex':i,'sourceProperties':copy.deepcopy(op),
            'historical':True,'sourcePeriod':'2013 feature timestamps; metadata references a2008municipal source; actual survey date unknown',
            'currentNameStatus':status,'currentNameEvidence':audit,
            'geometryVerificationStatus':'original_historical_source_coordinates_preserved_not_current_boundary_survey',
            'estimated':False,'sourceIsOfficial':False,'sourceIsHardBoundary':False,
            'usableForAddressAssignment':False,'license':LICENSE,
            'rightsStatus':'individual_dataset_reuse_rights_not_established',
            'attribution':'Click That Hood / VillyX; metadata cites Esztergom City Council Decree',
            'reviewNotes':['Upstream metadata cites a government source; the original government map/decree has not been retrieved here.',
                'Later municipal name use and actual OSM name points do not verify the historical polygon boundary.',
                'Same-name current points outside old geometry, and any municipal-border crossing, remain explicitly recorded.',
                'Industrial functional area kept out of the fine-quarter count pending explicit semantic corroboration.' if industrial else
                'A historical named-quarter candidate; neither complete city coverage nor current legal/address precision is asserted.']}
        assert feature['geometry']==original['geometry']
        features.append(feature);reviews.append(audit)
    collection={'type':'FeatureCollection','features':features}
    contents=encode(collection)
    proof={'schemaVersion':1,'sourceRepository':REPO,'sourceCommit':COMMIT,
        'sourceUrl':URL,'sourceGitBlobSha1':GIT_SHA,'sourceBytes':len(raw),'sourceSha256':sha(raw),
        'sourceFeatureCount':33,'quarterCandidates':32,'otherLocalAreas':1,
        'allSourceCoordinatesPreserved':True,'allGeometriesValid':True,
        'originalGovernmentCitationVerified':False,'absoluteBoundaryAccuracyMetres':None,
        'individualDatasetRightsEstablished':False,'softwareLicenseDoesNotEstablishDatasetLicense':True,
        'inputs':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p.read_bytes())} for p in [RAW,META,OUT/'official-name-evidence.json',parent_path,points_path]],
        'records':reviews,'convertedSha256':sha(contents),
        'reproduce':'PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/public-vector-next/convert-esztergom.py --check'}
    entry={'id':'public-vector-esztergom-2013','path':str((OUT/'esztergom-candidates.geojson').relative_to(ROOT)),
        'sha256':sha(contents),'municipality':'Esztergom','method':METHOD,'evidenceUrls':[URL,META_URL],
        'license':LICENSE,'propertyOverrides':{'usableForAddressAssignment':False},
        'reviewPath':str((OUT/'esztergom-proof.json').relative_to(ROOT)),
        'rightsStatus':'Individual dataset licence not explicit; MIT is preserved as software licence only.'}
    return {'esztergom-candidates.geojson':contents,'esztergom-proof.json':encode(proof),
        'esztergom-registry-entry.json':encode(entry),'esztergom-name-points.geojson':encode({'type':'FeatureCollection','features':points})}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    output=build()
    for name,raw in output.items():
        path=OUT/name
        if args.check:
            assert path.read_bytes()==raw, f'Stale output: {name}'
        else:path.write_bytes(raw)
    print(json.dumps({'features':33,'quarterCandidates':32,'otherLocalAreas':1,'checked':args.check}))

if __name__=='__main__':main()
