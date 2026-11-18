#!/usr/bin/env python3
"""Rough Érd area estimates from retained OSM road/rail/water map and place names."""
import json,hashlib
from pathlib import Path
from shapely.geometry import Polygon,mapping,shape,Point
from shapely.ops import transform
from shapely import make_valid
from pyproj import Transformer
OUT=Path(__file__).resolve().parent
# Manually estimated map-pixel outlines. Major road/rail/water courses inform
# orientation and extent; local connectors/quarter subdivisions remain inferred.
SPECS=[
 ('Parkváros',[(245,130),(375,45),(570,150),(695,245),(828,307),(897,430),(948,473),(840,580),(735,477),(618,540),(552,550),(430,500),(298,462),(305,275)]),
 ('Fenyves-Parkváros',[(245,130),(375,45),(510,118),(450,229),(390,375),(305,275)]),
 ('Fundoklia',[(300,350),(390,320),(460,352),(515,409),(550,450),(530,483),(425,497),(298,463)]),
 ('Dombosváros',[(460,350),(520,370),(575,420),(618,470),(610,540),(552,505),(516,451),(485,400)]),
 ('Vincellér',[(550,398),(617,376),(694,355),(802,443),(790,472),(726,490),(696,460)]),
 ('Kutyavár',[(846,424),(897,430),(948,473),(934,495),(903,504),(867,489),(862,460)]),
 ('Érdliget',[(795,472),(867,489),(903,504),(934,495),(936,525),(842,577),(826,539)]),
 ('Papiföldek',[(935,525),(1016,453),(1041,447),(1076,508),(1072,549),(1090,633),(1032,659),(947,668),(924,594)]),
 ('Györgyliget',[(842,577),(934,525),(940,609),(920,656),(845,682),(830,632)]),
 ('Postástelep',[(618,540),(726,490),(790,472),(826,539),(842,577),(830,632),(748,646),(688,595)]),
 ('Tusculanum',[(489,559),(552,540),(618,540),(688,595),(748,646),(681,672),(565,685),(514,715),(453,737),(422,641),(489,618)]),
 ('Imretelep',[(453,700),(501,678),(550,668),(565,685),(605,720),(580,746),(545,766),(505,782),(469,776),(440,766)]),
 ('Sasváros',[(491,770),(540,750),(580,746),(605,720),(624,747),(616,779),(557,802),(526,817)]),
 ('Újtelep',[(440,766),(469,776),(505,782),(526,817),(472,831),(431,799)]),
 ('Szent Ilona-telep',[(414,844),(472,831),(526,817),(551,861),(551,908),(500,902),(414,908),(386,892)]),
 ('Istvántelep',[(526,817),(557,802),(616,779),(634,815),(634,879),(627,930),(551,908),(551,861)]),
 ('Tisztviselőtelep',[(617,779),(660,762),(719,751),(748,739),(768,755),(744,812),(730,861),(704,918),(627,930),(634,879),(634,815)]),
 ('Bécsihegy',[(748,739),(810,720),(837,720),(867,744),(853,803),(834,830),(802,850),(744,876),(730,861),(744,812),(768,755)]),
 ('Mihálytelep',[(627,900),(670,885),(711,894),(744,876),(802,850),(834,830),(865,812),(902,809),(845,863),(799,886),(745,915),(719,936),(682,944),(660,968),(627,962)]),
 ('Újfalu',[(818,730),(837,720),(910,709),(924,746),(912,782),(902,809),(865,812),(838,800),(832,760)]),
 ('Béke téri lakótelep',[(813,710),(837,705),(867,710),(864,732),(842,742),(815,736)]),
 ('Erzsébetváros',[(816,785),(842,775),(865,780),(896,780),(912,782),(923,790),(918,812),(895,831),(865,846),(821,836)]),
 ('Ófalu',[(865,846),(895,831),(918,812),(953,820),(1016,880),(1095,910),(1095,1020),(1043,1085),(1048,1131),(975,1158),(920,1140),(882,1090),(860,1010),(840,950),(888,931)]),
 ('Kálvária-hegy',[(840,950),(888,931),(920,948),(919,983),(895,1015),(860,1010)]),
 ('Kakukkhegy',[(865,1015),(895,1015),(935,997),(1003,1029),(1043,1085),(1048,1131),(975,1158),(920,1140),(882,1090)]),
 ('Sánc-hegy',[(920,1140),(975,1158),(1048,1131),(1073,1195),(990,1201),(904,1197),(885,1160)]),
]
def enc(v):return json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
 reg=json.loads((OUT/'erd-map-registration.json').read_text());points=json.loads((OUT/'erd-source-points.geojson').read_text())['features'];parent=json.loads((OUT/'erd-source-municipality.geojson').read_text());municipality=shape(parent['geometry']);inverse=Transformer.from_crs(23700,4326,always_xy=True)
 def world(x,y,z=None):return inverse.transform((x-reg['padding'])/reg['scale']+reg['minimumEast'],reg['maximumNorth']-(y-reg['padding'])/reg['scale'])
 fs=[];spec=[]
 for i,(name,vertices) in enumerate(SPECS):
  pixel=Polygon(vertices);fixed=not pixel.is_valid
  if fixed:pixel=make_valid(pixel)
  geo=transform(world,pixel).intersection(municipality)
  if geo.geom_type=='GeometryCollection':
   ps=[p for p in geo.geoms if p.geom_type in ['Polygon','MultiPolygon']]
   from shapely.ops import unary_union
   geo=unary_union(ps)
  assert not geo.is_empty and geo.is_valid and geo.geom_type in ['Polygon','MultiPolygon']
  evidence=[{'name':p['properties']['name'],'coordinates':p['geometry']['coordinates'],'osmUrl':p['properties']['source'].get('url')} for p in points if p['properties']['name']==name]
  source={'provider':'osm-road-map-inference','url':'https://www.openstreetmap.org/relation/112435','mapPath':str((OUT/'erd-road-map.png').relative_to(OUT.parents[3])),'barrierSourcePath':str((OUT/'erd-source-barriers.geojson').relative_to(OUT.parents[3])),'barrierSourceSha256':sha(OUT/'erd-source-barriers.geojson'),'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','method':'Manual coarse subdivision based on actual OSM major-road/rail/water geometry and place positions; quarter connectors inferred; clipped to municipality.'}
  prop={'municipality':'Érd','name':name,'estimated':True,'method':'map_partition_estimate','candidateBoundaryKind':'neighbourhood','boundaryKind':'neighbourhood','qualityScore':25,'sourcePeriod':'OSM2026-11-12 snapshot, inferred2026-11-14','sourceUrl':source['url'],'source':source,'evidenceUrls':[source['url']]+[p['osmUrl'] for p in evidence if p['osmUrl']],'nameEvidence':evidence,'coordinateReferenceSystem':'EPSG:4326','absoluteAccuracyMetres':None,'approximationNote':'Approximate hand-drawn area using a map rendered from actual OSM major-road, railway and watercourse geometry plus named-place positions. The OSM source contains NO quarter boundary for these names; connector segments and neighborhood extents are inferred. No circle/Voronoi or claim of legal/current exact boundary. Parkváros is a broad parent including its two same-name source points; overlapping children retained.','pointRadiusFallback':False}
  fs.append({'type':'Feature','id':f'expansion:erd:map-inference:{i+1}','geometry':mapping(geo),'properties':prop});spec.append({'name':name,'mapPixelVertices':vertices,'selfIntersectionResolved':fixed,'nameEvidencePointsInside':[geo.covers(Point(p['coordinates'])) for p in evidence]})
 return fs,spec
if __name__=='__main__':
 fs,spec=build();summary={'schemaVersion':1,'featureCount':len(fs),'municipalities':{'Érd':len(fs)},'sourceNamedPoints':27,'distinctNamedPlaces':26,'duplicateParkvarosPointsMerged':True,'method':'rough hand-inferred subdivision of actual OSM major-road/rail/water map','sourceDefinedQuarterBoundaryClaimed':False,'pointRadiusFallbacks':0,'allGeometryValid':True,'namePointsOutsideEstimates':[s['name'] for s in spec if not all(s['nameEvidencePointsInside'])],'earlierPacketsModified':False}
 for n,d in [('erd-features.geojson',{'type':'FeatureCollection','features':fs}),('erd-summary.json',summary),('erd-pixel-specifications.json',spec)]: (OUT/n).write_text(enc(d))
 print(enc(summary))
