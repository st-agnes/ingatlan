"""Recheck eight literal name nodes against the already archived country PBF.

Name occurrence only; no point is a geometry control or boundary verification.
PYTHONPATH=.local/geodata python3 <this file>
"""
from pathlib import Path
import hashlib,json
import osmium

P=Path(__file__).resolve().parent
ROOT=P.parents[3]
PBF=ROOT/'.local/neighborhoods/hungary-latest.osm.pbf'
SHA='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
expected={}
source=json.loads((P/'current-source-name-points.geojson').read_text())['features']
for f in json.loads((P/'salgotarjan-inferred.geojson').read_text())['features']:
    record=next(x for x in source if x['id']==f['properties']['currentNameCorroboration']['sourceId'])
    expected[record['properties']['source']['osmId']]={'outputName':f['properties']['name'],'record':record}
h=hashlib.sha256()
with PBF.open('rb') as inp:
    for chunk in iter(lambda:inp.read(1024*1024),b''):h.update(chunk)
assert h.hexdigest()==SHA
rows=[]
class Check(osmium.SimpleHandler):
    def node(self,n):
        if n.id not in expected:return
        item=expected[n.id];record=item['record'];props=record['properties'];s=props['source'];tags=dict(n.tags)
        assert tags==s['tags']
        assert n.version==s['objectVersion']
        assert str(n.timestamp)==s['objectTimestamp']
        assert [n.location.lon,n.location.lat]==record['geometry']['coordinates']
        rows.append({'name':item['outputName'],'literalOsmName':tags['name'],'id':record['id'],'url':s['url'],'coordinates':[n.location.lon,n.location.lat],'tags':tags,'objectVersion':n.version,'objectTimestamp':str(n.timestamp),'pointGeometryUsedForGeoreference':False,'polygonBoundaryValidated':False})
Check().apply_file(str(PBF),locations=False)
assert len(rows)==8
review={'schemaVersion':1,'status':'EIGHT_LITERAL_CURRENT_OSM_NAME_NODES_RECHECKED_BOUNDARIES_NOT_VALIDATED','pbfSha256':SHA,'osmTimestamp':source[0]['properties']['source']['osmTimestamp'],'scope':'Source names and exact archived OSM node coordinates/tags/version/time only; not independent confirmation of neighborhood footprint, georeference or absolute accuracy.','records':sorted(rows,key=lambda x:x['name']),'polygonBoundaryValidated':False,'namePointsUsedForRegistration':False,'usableForAddressAssignment':False}
(P/'current-name-review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
print('Verified8 literal name nodes against archived PBF; no boundary geometry controls.')
