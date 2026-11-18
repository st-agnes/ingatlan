from pathlib import Path
import json,hashlib
import numpy as np
from PIL import Image
from scipy.ndimage import binary_closing,binary_fill_holes
from shapely.geometry import shape,Point,box,mapping
from shapely.ops import transform,unary_union
from pyproj import Transformer
R=Path(__file__).resolve().parent
D=lambda p:json.loads(p.read_text())
def dump(p,j):p.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
T=Transformer.from_crs(4326,23700,always_xy=True).transform;B=Transformer.from_crs(23700,4326,always_xy=True).transform
# Source greenX palette only; the old hand trace crossed cyanIX/pinkI/greenII.
a=np.asarray(Image.open(R/'municipal-figure71.png').convert('RGB'));x0,y0,x1,y1=610,260,701,337;crop=a[y0:y1,x0:x1];green=np.all(crop==[126,237,186],axis=2);mask=binary_fill_holes(binary_closing(green,structure=np.ones((5,5))))
neighbors={'cyanIX':[162,232,238],'pinkI':[244,157,174],'greenII':[194,237,140]}
for color in neighbors.values():mask[np.all(crop==color,axis=2)]=False
ys,xs=np.where(mask);px=unary_union([box(x+x0-.5,y+y0-.5,x+x0+.5,y+y0+.5) for y,x in zip(ys,xs)])
assert px.is_valid and px.geom_type in ['Polygon','MultiPolygon']
controls=D(R/'registration.json')['controls'];X=np.array([[*p['pixel'],1.] for p in controls]);Y=np.array([T(*p['coordinates']) for p in controls]);coef=np.linalg.lstsq(X,Y,rcond=None)[0]
def affine(x,y,z=None):return coef[0,0]*x+coef[1,0]*y+coef[2,0],coef[0,1]*x+coef[1,1]*y+coef[2,1]
km=unary_union([transform(T,shape(f['geometry'])) for f in D(R/'kecskemet-municipality.geojson')['features']]);budai=transform(affine,px).intersection(km)
counts={k:int(np.sum(mask & np.all(crop==v,axis=2))) for k,v in neighbors.items()};assert all(v==0 for v in counts.values())
colorproof={'sourcePixelBounds':list(px.bounds),'sourceGreenFillPixels':int(green.sum()),'retainedGreenFillPixels':int((mask&green).sum()),'enclosureMaskPixels':int(mask.sum()),'otherExactUnitFillPixelsInside':counts,'method':'Exact RGB126,237,186 sourcegreenX;5x5closing bridges internal black strokes; fill enclosed label/stroke holes; all exact neighboring-group fill pixels removed. No convex hull or hand extensions into adjacent groups. Pixel-sized outer-edge uncertainty remains.','georeference':'Unchanged nine-label affine;162mfitRMS remains uncertainty, not accuracy guarantee.'}
dump(R/'source-green-X-pixel-geometry.geojson',{'type':'FeatureCollection','coordinateSystem':'native source image pixels, NOT WGS84; do not import','features':[{'type':'Feature','properties':colorproof,'geometry':mapping(px)}]})
maskimage=Image.fromarray((mask*255).astype('uint8'));maskimage.save(R/'source-green-X-mask.png')
# Full assembled native residential relations plus previous complete municipalurbanunit estimates.
mun=unary_union([transform(T,shape(f['geometry'])) for f in D(R/'salgotarjan-municipality.geojson')['features']]);excluded=[];records=[]
for filename in ['native-residential-relations.geojson','municipal-profile-estimates.geojson','municipal-urban-quarter-estimates.geojson']:
 for f in D(R/filename)['features']:
  n=f['properties']['name']
  if filename=='native-residential-relations.geojson' and n=='Kotyháza':continue
  if filename=='municipal-urban-quarter-estimates.geojson' and n in ['Pécskőpuszta','Barackos']:continue
  g=transform(T,shape(f['geometry']));assert g.is_valid,(filename,n);excluded.append(g);records.append({'name':n,'archive':filename,'sourceUrl':f['properties'].get('sourceUrl'),'source':f['properties'].get('source'),'kind':'assembled native residential surface' if filename.startswith('native') else 'previous full municipalurbanunit estimate','areaKm2':g.area/1e6})
eresztveny=unary_union([transform(T,shape(f['geometry'])) for f in D(R/'eresztveny-prior-estimate.geojson')['features']]);excluded.append(eresztveny);urban=unary_union(excluded).intersection(mun);rural=mun.difference(urban);assert rural.is_valid and not rural.is_empty
labels=D(R/'salgotarjan-labels.geojson')['features'];checks=[]
for f in labels:
 g=transform(T,shape(f['geometry']));n=f['properties'].get('name')
 if g.geom_type=='Point':checks.append({'name':n,'coordinates':list(f['geometry']['coordinates']),'insideCorrectedRural':rural.covers(g),'insideExcludedUrbanOrEresztveny':urban.covers(g)})
required=['Belváros','Vásártér','Beszterce-lakótelep','Kemerovó-lakótelep','Gorkij-lakótelep','Zagyvapálfalva','Baglyasalja','Somoskő','Eresztvény']
def norm(s):return ''.join(c.lower() for c in s or '' if c.isalnum())
qa=[c for c in checks if norm(c['name']) in {norm(n) for n in required}]
print('URBAN CHECKS',qa)
assert len({norm(c['name']) for c in qa})==len(required),('missing QA labels',required,qa)
assert not any(c['insideCorrectedRural'] for c in qa),('urban still rural',qa)
features=[]
for city,name,g,method,note in [
 ('Kecskemét','Budaihegy-Vacshegy',budai,'municipal-raster-green-X-enclosure-corrected-estimate','Corrected whole greenX sourceunit only, figure71/PDFp138. The former hand trace materially crossed cyanIX,pinkI and greenII; it is superseded. Exact sourcepalette enclosure with internal-stroke/label holes filled, no neighboring exact unit fill pixels retained. The unchanged coarse nine-label affine has162mfitRMS; absolute modern boundary accuracy remains unknown.'),
 ('Salgótarján','Külterület (Eresztvény nélkül)',rural,'municipal-rural-remainder-full-urban-unit-proxy-corrected-estimate','Corrected low-confidence rural remainder from actual municipal outline after subtracting FULL archived assembled OSMresidentialrelations and complete earlier municipalITS urbanquarter estimates, with Eresztvény explicitly excluded. The earlier way-only subtraction missed residential relations and wrongly retained urban cores. This complete sourceproxy excludes the checked core/estate/satellite points but is not an exact current cadastralbelterület classification; sparse rural dwellings near old map boundaries can still be misclassified. Kotyháza/Pécskőpuszta rural identity is not treated as an urban exclusion solely from their native residential footprint.')]:
 props={'name':name,'municipality':city,'method':method,'estimated':True,'confidence':'low','lowConfidence':True,'qualityScore':30,'priority':25,'radiusFallback':False,'sourceUrl':D(R/'source-paths.json')['municipalKecskemetUrl' if city=='Kecskemét' else 'municipalSalgotarjanUrl'],'approximationNote':note,'areaKm2':round(g.area/1e6,6),'correctionOf':'../features.geojson','supersedesFrozenFeaturesSha256':'ac81dd61f69f96deb3599b0f594bf615f04f04f7fc39446c709889e2ae85ab78'}
 features.append({'type':'Feature','id':'round4-shard4-correction:'+city+':'+name,'properties':props,'geometry':mapping(transform(B,g))})
dump(R/'features.geojson',{'type':'FeatureCollection','features':features});dump(R/'excluded-urban-proxy.geojson',{'type':'FeatureCollection','features':[{'type':'Feature','properties':{'name':'Full source urban proxy plus Eresztvény','municipality':'Salgótarján','diagnosticOnly':True},'geometry':mapping(transform(B,urban))}]})
proof={'status':'FROZEN_INDEPENDENT_QA_PASSED' if (R/'independent-qa.json').exists() else 'AWAITING_INDEPENDENT_QA','correctionCount':2,'featuresSha256':hashlib.sha256((R/'features.geojson').read_bytes()).hexdigest(),'budaiGreenSource':colorproof,'salgotarjan':{'municipalityKm2':mun.area/1e6,'excludedUrbanAndEresztvenyKm2':urban.area/1e6,'ruralKm2':rural.area/1e6,'ruralMunicipalityFraction':rural.area/mun.area,'excludedSourceUnits':records,'checkedUrbanPlaces':qa,'allSourcePlaceChecks':checks,'eresztvenyOverlapM2':rural.intersection(eresztveny).area,'methodLimit':'A complete assembled physical/municipal-map proxy, not cadastrallegalclassification.'},'valid':all(shape(f['geometry']).is_valid for f in features),'sourceInputs':'All local archived within this correction folder; no PBF scan/network needed.'}
dump(R/'source-evidence.json',proof);print(json.dumps({k:proof[k] for k in ['status','featuresSha256','valid']},ensure_ascii=False));print('AREAS',budai.area/1e6,rural.area/1e6,'municipalityfraction',rural.area/mun.area)
