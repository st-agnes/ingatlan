#!/usr/bin/env python3
"""Exact current/explicit-alias OSM name evidence, no polygon derivation or geometry writes."""
from pathlib import Path
import json,hashlib,unicodedata,os,sys
os.environ['PROJ_NETWORK']='OFF'
import osmium
from shapely.geometry import shape,Point,LineString,Polygon,MultiPolygon
P=Path(__file__).resolve().parent;ROOT=P.parents[2];PBF=ROOT/'.local/neighborhoods/hungary-latest.osm.pbf';BASE=ROOT/'data/neighborhoods/sources/municipal-pecs-grounded-next/source-municipality.geojson';COHORT=ROOT/'data/neighborhoods/sources/municipal-pecs-final-gaps-review/source-coverage-accounting.json'
def sha(q):return hashlib.sha256(q.read_bytes()).hexdigest()
def norm(s):return ''.join(c for c in unicodedata.normalize('NFD',s.casefold())if c.isalnum())
names=[r['sourceName']for r in json.loads(COHORT.read_text())['records']];wanted={norm(n):n for n in names};assert len(wanted)==67
municipal=json.loads(BASE.read_text());city=shape(municipal['geometry']);assert municipal['properties']['source']['osmId']==575380
fields=['name','name:hu','official_name','short_name','loc_name','alt_name','old_name','was:name'];aliasfields={'alt_name','loc_name','short_name','old_name','was:name'}
objects={};counts={'exactNameCandidatesRead':0,'nodes':0,'ways':0,'relations':0}
def matching(tags):
 out=[]
 for field in fields:
  if field not in tags:continue
  values=tags[field].split(';')if field in aliasfields else[tags[field]]
  for val in values:
   val=val.strip();name=wanted.get(norm(val))
   if name:out.append({'sourceName':name,'tagKey':field,'literalTagValue':tags[field],'matchedLiteralToken':val,'matchType':'literal_exact'if val==name else'orthographic_normalized_exact','role':'historical_name_only'if field in ['old_name','was:name']else'explicit_current_alias_tag'if field in aliasfields else'current_name_tag'})
 return out
for o in osmium.FileProcessor(str(PBF)).with_filter(osmium.filter.KeyFilter(*fields)):
 tags=dict(o.tags);matches=matching(tags)
 if not matches:continue
 if isinstance(o,osmium.osm.Node):typ='node'
 elif isinstance(o,osmium.osm.Way):typ='way'
 elif isinstance(o,osmium.osm.Relation):typ='relation'
 else:continue
 d={'osmType':typ,'osmId':o.id,'objectVersion':o.version,'objectTimestamp':str(o.timestamp),'tags':tags,'nameMatches':matches,'url':f'https://www.openstreetmap.org/{typ}/{o.id}'}
 if typ=='node':d['coordinates']=[o.lon,o.lat]
 elif typ=='way':d['nodeRefs']=[n.ref for n in o.nodes]
 else:d['members']=[{'type':{'n':'node','w':'way','r':'relation'}.get(m.type,m.type),'ref':m.ref,'role':m.role}for m in o.members]
 objects[(typ,o.id)]=d;counts[typ+'s']+=1
# Fetch complete original way/node references for exact relation/way objects. Nested relations are retained as unresolved, never inferred.
neededways={m['ref']for r in objects.values()if r['osmType']=='relation'for m in r['members']if m['type']=='way'};ways={r['osmId']:r for r in objects.values()if r['osmType']=='way'}
missingways=neededways-set(ways)
if missingways:
 for o in osmium.FileProcessor(str(PBF)).with_filter(osmium.filter.IdFilter(missingways)):
  if isinstance(o,osmium.osm.Way)and o.id in missingways:ways[o.id]={'osmId':o.id,'nodeRefs':[n.ref for n in o.nodes],'tags':dict(o.tags),'objectVersion':o.version,'objectTimestamp':str(o.timestamp)}
needednodes={n for w in ways.values()for n in w['nodeRefs']}|{m['ref']for r in objects.values()if r['osmType']=='relation'for m in r['members']if m['type']=='node'};nodes={r['osmId']:r for r in objects.values()if r['osmType']=='node'}
missingnodes=needednodes-set(nodes)
for o in osmium.FileProcessor(str(PBF)).with_filter(osmium.filter.IdFilter(missingnodes)):
 if isinstance(o,osmium.osm.Node)and o.id in missingnodes:nodes[o.id]={'osmId':o.id,'coordinates':[o.lon,o.lat],'objectVersion':o.version,'objectTimestamp':str(o.timestamp)}
missing_original_way_refs=sorted(neededways-set(ways));missing_original_node_refs=sorted(needednodes-set(nodes))

def waygeom(w):
 if any(n not in nodes for n in w['nodeRefs']):return None
 coords=[nodes[n]['coordinates']for n in w['nodeRefs']]
 if len(coords)<2:return None
 if w['nodeRefs'][0]==w['nodeRefs'][-1]and len(coords)>3:
  g=Polygon(coords)
  if g.is_valid:return g
 return LineString(coords)
def ringrefs(parts):
 parts=[list(p)for p in parts];rings=[]
 while parts:
  ring=parts.pop(0)
  while ring[0]!=ring[-1]:
   match=[]
   for i,part in enumerate(parts):
    if part[0]==ring[-1]:match.append((i,False))
    elif part[-1]==ring[-1]:match.append((i,True))
   if len(match)!=1:return None
   i,rev=match[0];part=parts.pop(i)
   if rev:part.reverse()
   ring.extend(part[1:])
  rings.append(ring)
 return rings

def relationgeom(r):
 if any(m['type']=='relation'for m in r['members']):return None,'nested_relation_members_not_expanded'
 if r['tags'].get('type')not in ['multipolygon','boundary']:return None,'non_area_relation_not_used_for_area_city_association'
 if any(m['ref']not in ways for m in r['members']if m['type']=='way'):return None,'source_country_extract_missing_relation_member_way_no_city_association'
 if any(n not in nodes for m in r['members']if m['type']=='way'for n in ways[m['ref']]['nodeRefs']):return None,'source_country_extract_missing_member_nodes_no_city_association'
 outer=ringrefs([ways[m['ref']]['nodeRefs']for m in r['members']if m['type']=='way'and m['role']in ['','outer']]);inner=ringrefs([ways[m['ref']]['nodeRefs']for m in r['members']if m['type']=='way'and m['role']=='inner'])
 if not outer or inner is None:return None,'original_member_ways_do_not_form_unique_exact_endpoint_rings'
 outers=[Polygon([nodes[n]['coordinates']for n in ring])for ring in outer];inners=[Polygon([nodes[n]['coordinates']for n in ring])for ring in inner]
 if not all(g.is_valid for g in outers+inners):return None,'raw_area_rings_invalid_no_repair'
 polys=[]
 for o in outers:
  selected=[i for i in inners if o.contains(i)];polys.append(Polygon(o.exterior.coords,[i.exterior.coords for i in selected]))
 if sum(sum(o.contains(i)for o in outers)for i in inners)!=len(inners):return None,'inner_members_not_uniquely_contained_no_repair'
 g=polys[0]if len(polys)==1 else MultiPolygon(polys)
 return (g,'literal_member_ring_geometry')if g.is_valid else(None,'raw_area_invalid_no_repair')

def category(tags):
 if 'place'in tags:return 'place_or_quarter_label'
 if tags.get('boundary')=='administrative':return 'administrative_named_area'
 if tags.get('highway')in ['bus_stop','platform']or tags.get('public_transport')in ['platform','stop_position','station']:return 'transport_stop_name_only'
 if 'highway'in tags:return 'street_or_highway_name_only'
 if any(k in tags for k in ['landuse','natural','leisure'])or tags.get('amenity')in ['grave_yard','cemetery']:return 'other_named_landuse_or_functional_area'
 if tags.get('type')=='route':return 'transport_route_name_only'
 return 'other_poi_or_named_feature_only'
kept=[];excluded=[]
for r in objects.values():
 typ=r['osmType'];g=None;method=''
 if typ=='node':g=Point(r['coordinates']);method='literal_node_point_covered_by_same_snapshot_Pecs_municipality'
 elif typ=='way':g=waygeom(r);method='complete_original_named_way_geometry_covered_by_same_snapshot_Pecs_municipality'if g is not None else'source_country_extract_missing_named_way_nodes_no_city_association'
 else:g,method=relationgeom(r)
 same=bool(g is not None and city.covers(g));r['sameCityAssociation']={'municipality':'Pécs','osmMunicipalityRelationId':575380,'samePbfSnapshot':True,'method':method,'completeObjectGeometryCovered':same,'addrCityTag':r['tags'].get('addr:city'),'noNearestPointOrFuzzyAssociation':True}
 if not same:
  # Keep bounded rejection metadata, avoiding huge nonlocal raw-way geometry dumps.
  excluded.append({'osmType':typ,'osmId':r['osmId'],'nameMatches':r['nameMatches'],'tags':{k:v for k,v in r['tags'].items()if k in fields+['place','highway','landuse','amenity','boundary','admin_level','addr:city']},'reason':method if g is None else'complete_source_object_geometry_not_covered_by_Pecs'})
  continue
 r['evidenceCategory']=category(r['tags'])
 if typ=='way':r['originalNodeCoordinates']=[nodes[n]['coordinates']for n in r['nodeRefs']]
 elif typ=='relation':r['originalMemberWays']=[ways[m['ref']]for m in r['members']if m['type']=='way'];r['originalMemberNodes']=[nodes[n]for n in sorted({n for m in r['members']if m['type']=='way'for n in ways[m['ref']]['nodeRefs']})]
 kept.append(r)
counts['exactNameCandidatesRead']=len(objects)
# Pecs typed place archive: independently match broader extraction against the earlier country cohort where relevant.
manifest=json.loads((ROOT/'data/neighborhoods/sources/country-osm/manifest.json').read_text());assert sha(PBF)==manifest['input']['sha256']=='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
result={'schemaVersion':1,'auditDate':'2026-11-14','scope':'67 exact normalized source names searched across all original PBF node/way/relation current name fields and explicit alias/historical name fields; retained only by complete-object containment in same-snapshot Pecs municipality. Name evidence only.','pbf':manifest['input'],'pbfBytesVerified':True,'municipalityGeometryReference':{'path':str(BASE.relative_to(ROOT)),'sha256':sha(BASE),'osmRelationId':575380,'sourceScope':'Current original OSM administrative reference for name-city association, not inferred quarter geometry or official/legal-boundary accuracy.'},'sourceNames':names,'nameNormalization':'Unicode NFD/casefold and retain alphanumeric characters; ignores diacritics/punctuation/spacing only. No substring, fuzzy, spelling substitution or nearest-point aliasing. Explicit multi-name tags split only on semicolon.','searchedTagKeys':fields,'candidateCounts':counts,'countryExtractMissingWayRefCountInAllCountryExactCandidates':len(missing_original_way_refs),'countryExtractMissingNodeRefCountInAllCountryExactCandidates':len(missing_original_node_refs),'missingSourceRefInterpretation':'Country-clipped nonlocal candidates with incomplete original references are retained as unresolved/excluded; no missing source coordinate or city association is invented.','sameCityMatchedObjectCount':len(kept),'sameCityObjects':sorted(kept,key=lambda r:(r['osmType'],r['osmId'])),'nonPecsOrUnresolvedExactMatchCandidateCount':len(excluded),'excludedCandidateEvidence':excluded,'geometryOrRegistryWritten':False,'georeferenceChanged':False,'claimedAbsoluteAccuracy':None,'usableForAddressAssignment':False,'networkUsed':False}
q=P/'pecs-current-name-osm-evidence.json';s=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
if '--check'in sys.argv:assert q.read_text()==s;print('Pecs raw OSM current-name extraction exact reproduction: PASS')
else:q.write_text(s);print(json.dumps({'countryExactNameCandidates':counts,'sameCityObjects':len(kept),'sameCityCategories':{c:sum(r['evidenceCategory']==c for r in kept)for c in sorted({r['evidenceCategory']for r in kept})}},ensure_ascii=False))
