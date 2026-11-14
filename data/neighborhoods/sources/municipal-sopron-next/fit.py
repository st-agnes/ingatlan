#!/usr/bin/env python3
"""Approximate calibration from actual municipal-perimeter source strokes.

The second page is tied to the first by the original turquoise filled geographic
scope appearing on page1 and the exact union of four source faces on page2.
No neighbourhood name coordinate is used as a control. Residuals quantify fit,
not independent geographic accuracy. Only archived local sources are read.
"""
from pathlib import Path
import json,hashlib
import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import shape,Point,LineString
from shapely.ops import transform,unary_union
from pyproj import Transformer
import shapely
P=Path(__file__).resolve().parent
read=lambda n:json.loads((P/n).read_text());sha=lambda n:hashlib.sha256((P/n).read_bytes()).hexdigest()

def sample_boundary(g,step):
 parts=list(g.geoms) if g.geom_type=='MultiLineString' else [g];arrays=[]
 for line in parts:
  ds=np.linspace(0,line.length,max(2,int(np.ceil(line.length/step))+1));arrays.append(shapely.get_coordinates(shapely.line_interpolate_point(line,ds)))
 return np.concatenate(arrays)

def fit(source,target_samples,initial,max_distance,iterations=150):
 A=np.c_[source,np.ones(len(source))];tree=cKDTree(target_samples);M=initial.copy();changes=[]
 for i in range(iterations):
  pred=A@M;distance,idx=tree.query(pred);limit=min(max_distance,float(np.quantile(distance,.9)));ok=distance<=limit
  assert ok.sum()>=20
  new=np.linalg.lstsq(A[ok],target_samples[idx[ok]],rcond=None)[0];delta=float(np.max(np.abs(new-M)));changes.append(delta);M=new
  if delta<1e-9:break
 dist,idx=tree.query(A@M)
 return M,dist,{'iterations':i+1,'keptNearestFraction':.9,'maximumControlDistance':max_distance,'finalDelta':changes[-1]}

native=read('calibration-native-perimeter.json');source=np.unique(np.array([p for s in native['segments'] for p in s['coordinates']]),axis=0)
ref=read('calibration-municipality.geojson');geo=shape(ref['geometry']);eov=transform(Transformer.from_crs(4326,23700,always_xy=True).transform,geo);largest=max(eov.geoms,key=lambda g:g.area) if eov.geom_type=='MultiPolygon' else eov;target=largest.exterior
minx,miny=source.min(axis=0);maxx,maxy=source.max(axis=0);e0,n0,e1,n1=target.bounds
M1=np.array([[(e1-e0)/(maxx-minx),0],[0,-(n1-n0)/(maxy-miny)],[e0-minx*(e1-e0)/(maxx-minx),n1+miny*(n1-n0)/(maxy-miny)]])
M1,d1,info1=fit(source,sample_boundary(target,2),M1,250)
print('Page1 to EOV',M1.tolist(),'nearest residual percentiles',np.percentile(d1,[0,50,80,90,95,99,100]).tolist(),flush=True)
# Check the frozen solution against exact archived municipal-boundary linework.
source_world=np.c_[source,np.ones(len(source))]@M1
exact1=shapely.distance(shapely.points(source_world),target)
raw=read('native-source-polygons.json');parts=[shape(r['nativeGeometry']) for r in raw['records']];scope2=unary_union(parts);scope1pts=np.array(read('cross-page-native-fill-scope.json')['actualSourceFillVertexPointCloud'])
a0,b0=scope1pts.min(axis=0);a1,b1=scope1pts.max(axis=0);x0,y0,x1,y1=scope2.bounds
M12=np.array([[(x1-x0)/(a1-a0),0],[0,(y1-y0)/(b1-b0)],[x0-a0*(x1-x0)/(a1-a0),y0-b0*(y1-y0)/(b1-b0)]])
M12,d12,info12=fit(scope1pts,sample_boundary(scope2.boundary,.03),M12,2)
exact12=shapely.distance(shapely.points(np.c_[scope1pts,np.ones(len(scope1pts))]@M12),scope2.boundary)
print('Page1 scope to page2',M12.tolist(),'exact crosspage percentiles',np.percentile(exact12,[0,50,80,90,95,99,100]).tolist(),flush=True)
coarse_M12=M12.copy();coarse_exact12=exact12.copy();cad_path=P/'cross-page-cad-controls.json'
if cad_path.exists():
 cad=read('cross-page-cad-controls.json');assert cad['sourcePdfSha256']==sha('source-pages1-2.pdf');M12=np.array(cad['page1PdfPointsToPage2PdfPointsMatrix']);exact12=shapely.distance(shapely.points(np.c_[scope1pts,np.ones(len(scope1pts))]@M12),scope2.boundary)
M21=np.vstack([np.linalg.inv(M12[:2]),-M12[2]@np.linalg.inv(M12[:2])]);M2=np.vstack([M21[:2]@M1[:2],M21[2]@M1[:2]+M1[2]])
output={'schemaVersion':1,'method':'Approximate affine point-to-line fitting of actual original page1 municipal-perimeter stroke vertices to archived current municipal exterior in EOV. Page2 is linked to page1 by actual turquoise source-scope strip vertices and the exact union of four source-blue faces. No name point, image/frame edge, synthetic closure or replacement road is used.','sourcePerimeterControlPointsPage1PdfPoints':source.tolist(),'sourcePerimeterExactResidualsMetres':exact1.tolist(),'page1PdfPointsToEovMatrix':M1.tolist(),'sourcePerimeterFit':info1,'crossPageSourceFillVertexPointsPage1':scope1pts.tolist(),'crossPageSourceVertexResidualsPage2PdfPoints':exact12.tolist(),'page1PdfPointsToPage2PdfPointsMatrix':M12.tolist(),'page2PdfPointsToPage1PdfPointsMatrix':M21.tolist(),'crossPageFit':info12,'page2PdfPointsToEovMatrix':M2.tolist(),'registrationGeographicNamePointCount':0,'independentSurveyOrInteriorWorldControlCount':0,'absoluteBoundaryAccuracyMetres':None,'usableForAddressAssignment':False,'inputs':[{'path':n,'sha256':sha(n)} for n in ['calibration-native-perimeter.json','calibration-municipality.geojson','cross-page-native-fill-scope.json','native-source-polygons.json']]}
output['coarseScopePage1ToPage2Matrix']=coarse_M12.tolist();output['coarseScopeSourceVertexResidualsPage2PdfPoints']=coarse_exact12.tolist()
if cad_path.exists():
 output['method']='Approximate actual page1 municipal-stroke-to-OSM-perimeter registration in EOV; page2 linked by 4888 actual paired original CAD segments, initialized by the common source geographic scope. All source endpoints and indices retained; no geographic name-point controls. Residuals are diagnostics, not independent absolute accuracy.'
 output['crossPageCadControlPairs']=cad['matchedActualSourceSegmentPairs'];output['crossPageCadControlResidualPercentilesPage2PdfPoints']=cad['pairedEndpointResidualPercentilesPage2PdfPoints'];output['inputs'].append({'path':'cross-page-cad-controls.json','sha256':sha('cross-page-cad-controls.json')})
(P/'registration.json').write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print('Crosspage source bounds',scope1pts.min(axis=0).tolist(),scope1pts.max(axis=0).tolist(),'page2',list(scope2.bounds),flush=True)
