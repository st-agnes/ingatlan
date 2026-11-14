"""Read-only global context; enrich local candidates and create conversion proof.
Run after derive-remaining.py and extract-current-name-evidence.py, before validators.
"""
import json,hashlib
from pathlib import Path
import numpy as np
from shapely.geometry import shape,Point
from shapely.ops import transform
from pyproj import Transformer
P=Path(__file__).resolve().parent
def read(n):return json.loads((P/n).read_text())
def write(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(n):return hashlib.sha256((P/n).read_bytes()).hexdigest()
eov=Transformer.from_crs(4326,23700,always_xy=True);wgs=Transformer.from_crs(23700,4326,always_xy=True)
muni=transform(eov.transform,shape(read('calibration-municipality.geojson')['geometry']))
namepoints=read('current-name-evidence.geojson')['features'];names={r['name']:r for r in read('current-name-evidence.json')['nameResults']}
rows=[]
for file in ['remaining-literal-world.geojson','remaining-manual-world.geojson','remaining-iparterulet-one-pixel-inferred-world.geojson']:
 d=read(file)
 for f in d['features']:
  p=f['properties'];g=transform(eov.transform,shape(f['geometry']));name=p['name'];results=[]
  for n in namepoints:
   if n['properties']['requestedName']!=name:continue
   ng=transform(eov.transform,shape(n['geometry']));results.append(n['properties']|{'geometry':n['geometry'],'intersectsHistoricalCandidate':ng.intersects(g),'distanceFromHistoricalCandidateM':ng.distance(g)})
  p.update({'currentNameStatus':names[name]['status'],'sourceLabelEvidence':results,'namePointsUsedForGeoreferencing':False,'independentInteriorControlCount':0,'municipalityOverlapFraction':g.intersection(muni).area/g.area,'outsideCurrentMunicipalityAreaM2':g.difference(muni).area})
  rows.append({'name':name,'file':file,'areaM2':g.area,'geometryValid':g.is_valid,'municipalityOverlapFraction':p['municipalityOverlapFraction'],'sourceLabelEvidence':results,'currentNameStatus':p['currentNameStatus']})
 write(file,d)
reg=read('zalaegerszeg-registration.json');M=np.array(reg['matrixPixelToEov']);sv=np.linalg.svd(M[:2],compute_uv=False)
proof={'schemaVersion':1,'sourcePdfUrl':'https://zalaegerszeg.hu/wp-content/uploads/2023/05/Zalaegerszeg_ITS.pdf','sourcePdfSha256':'4534775c49466eba0460e583aa45a12127f0a46cd8c0e768ed689b830e4eb035','sourcePdfPageOneBased':12,'sourceNameTablePageOneBased':13,'sourceEmbeddedImageXref':105,'sourceImageSizePixels':[1663,2360],'sourceImageSha256':sha('zalaegerszeg-p12-image0.jpeg'),'registrationSha256':sha('zalaegerszeg-registration.json'),'sourcePixelConvention':'Original JPEG pixel index denotes center; the observed inside-stroke cell edges are half-integer coordinates.','colorMask':'R<135, G-R>30, B-R>30, G>65; original JPEG RGB values; four-neighbor non-mask interiors.','registration':{'matrixPixelToEov':M.tolist(),'inheritedUnchanged':True,'method':reg['method'],'independentInteriorControlCount':0,'absoluteAccuracyM':None,'pixelScaleSingularValuesM':sv.tolist(),'determinantM2PerPixel':float(abs(np.linalg.det(M[:2]))),'perimeterResidualMedianM':float(np.median(reg['residualsM'])),'perimeterResidualP95M':float(np.percentile(reg['residualsM'],95)),'residualMeaning':'Registration diagnostics against fitted municipal perimeter, not independent interior accuracy.','namePointsUsedAsControls':False,'currentRoadsUsedAsControls':False,'municipalGeometrySha256':sha('calibration-municipality.geojson')},'candidates':rows,'globalRegistriesModified':False,'admissionRecommendation':{'literalIparterulet':'Retain raw literal source quarantine because strict validator rejects a1px corner-touching hole. Functional industrial character does not exclude this explicit historical quarter.','onePixelIparteruletAlternative':'Retain as explicit estimated interpretation for review; current exact OSM name was not independently confirmed. No silent correction or primary admission.','fiveNamedManualCandidates':'Eligible only for existing inferred/estimated layer after independent review; same inherited approximate registration as original5 does not establish surveyed/current boundaries. Ebergény has extra semantic uncertainty about unlabelled lobe70, with alternative retained.','primaryAdmission':'No new primary candidates recommended from this subset without a consistent project decision on inherited georeferencing and current-quarter identity. Existing5 global records were not changed.'}}
write('remaining-conversion-proof.json',proof)
print(json.dumps([{'name':r['name'],'overlap':r['municipalityOverlapFraction'],'currentName':r['currentNameStatus']} for r in rows],ensure_ascii=False))
