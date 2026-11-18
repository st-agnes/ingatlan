#!/usr/bin/env python3
"""Explicitly associate three actual crossing source polygons using literal label-node evidence.

Does not relax the nationwide containment rule, clip polygons, or fabricate edges.
Requires local preserved inputs only; no network operations.
"""
import gzip, hashlib, json
from pathlib import Path
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'data/neighborhoods/sources/country-parent-review'
SOURCE = ROOT/'data/neighborhoods/sources/country-osm'
SPECS = [('osm:way:971577592','Csenger','osm:node:8992354720'),
         ('osm:way:981846405','Csenger','osm:node:9080910862'),
         ('osm:way:988254771','Dorog','osm:node:6344717844')]

def sha(b): return hashlib.sha256(b).hexdigest()
def read(name):
    path=SOURCE/(name+'.gz'); raw=gzip.decompress(path.read_bytes())
    return json.loads(raw), {'path':str(path.relative_to(ROOT)), 'decompressedSha256':sha(raw)}
def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')

def main():
    polygons, ps=read('polygons.geojson'); nodes, ns=read('named-nodes.geojson'); parents, ms=read('municipalities.geojson')
    by_id={f['id']:f for f in polygons['features']}; points={f['id']:f for f in nodes['features']}
    municipality={f['properties']['name']:f for f in parents['features'] if f['properties'].get('usedForAssociation')}
    metric=Transformer.from_crs(4326,3035,always_xy=True).transform
    features=[]; reviews=[]
    for ident,city,node_id in SPECS:
        original=by_id[ident]; node=points[node_id]; parent=municipality[city]
        g,pt,pg=map(shape,[original['geometry'],node['geometry'],parent['geometry']])
        name=original['properties']['name']; tags=node['properties']['source']['tags']
        aliases=[tags.get('name','')]+tags.get('alt_name','').split(';')
        assert name in aliases and g.covers(pt) and pg.covers(pt), 'Explicit inside label evidence changed'
        area=transform(metric,g).area; inside=transform(metric,g.intersection(pg)).area
        urls=[original['properties']['source']['url'],node['properties']['source']['url'],parent['properties']['source']['url']]
        method='Explicit per-object municipality association review using an actual same-name/alias OSM label node inside both the unchanged source polygon and canonical municipality; no bulk overlap threshold, clipping, repair or generated edges.'
        properties={**original['properties'], 'name':tags['name'], 'sourceName':name,
          'municipality':city,'boundaryKind':'neighbourhood',
          'canonicalNameIsNeighborhood':True,'method':method,'evidenceUrls':urls,'usableForAddressAssignment':False,
          'sourceRecordId':ident,'sourceSnapshotSha256':ps['decompressedSha256'],
          'parentAssociationReview':{'municipality':city,'labelNodeId':node_id,'labelName':tags['name'],
             'labelAliases':aliases,'sameNameOrExplicitAlias':True,'pointInsideOriginalPolygon':True,
             'pointInsideCanonicalMunicipality':True,'independentProviderCorroboration':False,
             'fullContainment':False,'overlapFraction':inside/area,'outsideParentAreaM2':area-inside,
             'geometryChanged':False,'legalBoundaryVerified':False},
          'reviewNotes':['Actual source outline crosses the canonical municipal boundary. Preserve that discrepancy for review; never use this polygon for automatic address assignment.',
                         'The label is a separate OSM object, not independent official corroboration.']}
        f={**original,'id':'manual:country-parent-review:'+ident,'properties':properties}
        assert f['geometry']==original['geometry']
        features.append(f); reviews.append({'sourceId':ident,'sourceName':name,
          'canonicalName':tags['name'],**properties['parentAssociationReview']})
    OUT.mkdir(exist_ok=True,parents=True)
    path=OUT/'named-crossing-quarters.geojson'; write(path,{'type':'FeatureCollection','features':features})
    proof={'schemaVersion':1,'purpose':'Three explicit source parent associations; no change to general country association rules.',
           'inputs':[ps,ns,ms], 'records':reviews,'outputSha256':sha(path.read_bytes()),
           'limits':['No geometry or legal boundary verification is implied.','Full original crossing geometries and exact label identities are preserved.'],
           'reproduce':'PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-parent-review.py'}
    write(OUT/'proof.json',proof)
    entry={'id':'country-parent-review','path':str(path.relative_to(ROOT)),'sha256':sha(path.read_bytes()),
           'method':'Per-object source parent association with separate exact label nodes; original source geometry retained.',
           'evidenceUrls':['https://www.openstreetmap.org/copyright'],'license':'ODbL-1.0',
           'propertyOverrides':{'boundaryKind':'neighbourhood','canonicalNameIsNeighborhood':True,'usableForAddressAssignment':False},
           'reviewPath':str((OUT/'proof.json').relative_to(ROOT))}
    write(OUT/'registry-entry.json',entry)
    print(json.dumps({'features':len(features),'names':[r['canonicalName'] for r in reviews]},ensure_ascii=False))
if __name__=='__main__':main()
