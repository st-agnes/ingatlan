#!/usr/bin/env python3
"""Offline source-map estimates, without a PBF/network dependency. See README."""
from pathlib import Path
import sys,json,gzip,hashlib
from shapely.geometry import shape,Polygon,Point,mapping
from shapely.ops import unary_union,transform
from shapely.validation import make_valid
from pyproj import Transformer
H=Path(__file__).resolve().parent; ROOT=H.parents[3]; CTX=H.parent/'contexts'
def read(p):return json.load(gzip.open(p,'rt')) if p.suffix=='.gz' else json.load(open(p))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def polygons(g):
 if g.geom_type in ('Polygon','MultiPolygon'):return g
 return unary_union([x for x in g.geoms if x.geom_type in ('Polygon','MultiPolygon')])
def area(g):return transform(Transformer.from_crs(4326,23700,always_xy=True).transform,g).area
batch=sys.argv[1] if len(sys.argv)>1 else '01'; traces=read(H/f'batch-{batch}-traces.json');out=[];validation=[]
for index,trace in traces.items():
 idx=int(index);meta=read(H/'maps'/f'{idx:02d}.json') if (H/'maps'/f'{idx:02d}.json').exists() else trace['registration']; c=CTX/meta['contextKey']; muni=unary_union([shape(f['geometry']) for f in read(c/'municipality.geojson')['features']]); native=None
 if trace.get('nativeAreaId'):
  native=next(f for f in read(c/'areas.geojson.gz')['features'] if f.get('id',f['properties'].get('source',{}).get('id'))==trace['nativeAreaId'] or f['properties'].get('source',{}).get('id')==trace['nativeAreaId']);g=shape(native['geometry'])
 else:
  b=meta['bounds'];pts=[[b[0]+x/meta['width']*(b[2]-b[0]),b[3]-y/meta['height']*(b[3]-b[1])] for x,y in trace['pixels']];g=Polygon(pts)
 g=polygons(make_valid(g).intersection(muni));point=meta.get('sourceNamePoint');pointok=not point or g.covers(Point(point['coordinates']))
 if g.is_empty or not g.is_valid or area(g)<200 or not pointok:raise ValueError((idx,meta['name'],g.is_valid,area(g),pointok))
 files=['roads.geojson.gz','areas.geojson.gz','addresses.geojson.gz','municipality.geojson','labels.geojson']; hashes={str((c/f).relative_to(ROOT)):sha(c/f) for f in files};np=point or{};urls=trace.get('urls',[]);sourceurl=urls[0] if urls else np.get('sourceUrl','https://www.openstreetmap.org')
 props={'name':meta['name'],'municipality':meta['municipality'],'municipalityId':'city:'+meta['municipality'],'method':'source_footprint_extent_estimate' if native else 'source_map_road_field_extent_estimate','boundaryKind':'neighbourhood','searchable':True,'estimated':True,'lowConfidence':True,'qualityScore':20,'pointRadiusFallback':False,'wholeQuarterAccuracyVerified':False,'sourceRole':'rough_whole_locality_extent','approximationNote':trace['note'],'namePoint':np,'manualTraceFile':str((H/f'batch-{batch}-traces.json').relative_to(ROOT)),'sourceContextHashes':hashes,'source':{'provider':'manual-openstreetmap-context-and-source-text-inference','url':sourceurl,'supportingUrls':urls,'sourcePath':str(c.relative_to(ROOT)),'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','snapshotDate':np.get('snapshotDate','2026-11-12T21:23:05Z')},'evidenceFile':str((H/'evidence').relative_to(ROOT)),'originalTaskIndex':idx}
 if native:props['sourceAreaId']=trace['nativeAreaId'];props['sourceNativeGeometry']=True
 fid='round4-s1:'+hashlib.sha256((meta['municipality']+'|'+meta['name']).encode()).hexdigest()[:20];out.append({'type':'Feature','id':fid,'geometry':mapping(g),'properties':props});validation.append({'index':idx,'municipality':meta['municipality'],'name':meta['name'],'areaM2':round(area(g)), 'valid':g.is_valid,'coversSourceNamePoint':pointok if point else None,'sourceNamePointAvailable':bool(point),'sourceNativeGeometry':bool(native)})
fc={'type':'FeatureCollection','features':out}; path=H/f'features-batch-{batch}.geojson';path.write_text(json.dumps(fc,ensure_ascii=False,separators=(',',':'))+'\n');report={'batch':batch,'count':len(out),'featureSha256':sha(path),'features':validation};(H/f'validation-batch-{batch}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
