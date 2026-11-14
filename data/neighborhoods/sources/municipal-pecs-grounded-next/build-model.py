#!/usr/bin/env python3
"""Five observed source/world control pairs; no automatic quarter/model approval."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from PIL import Image
from pyproj import Transformer,network
from shapely.geometry import shape,Point,MultiPoint,LineString
from shapely.ops import transform,unary_union
P=Path(__file__).resolve().parent
network.set_network_enabled(False)
TO=Transformer.from_crs(4326,23700,always_xy=True).transform
GEO=Transformer.from_crs(23700,4326,always_xy=True).transform
CHECKPOINTS=[('northwest',[80,160]),('north',[300,50]),('northeast',[500,90]),('west',[50,320]),('centre',[275,285]),('east',[530,155]),('southwest',[210,450]),('south',[275,495]),('southeast',[400,483])]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def encoded(o):return json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
def summaries(values):
 x=np.asarray(values,dtype=float)
 return {'count':len(x),'minimum':float(x.min()),'median':float(np.median(x)),'rms':float(np.sqrt(np.mean(x*x))),'percentile95':float(np.percentile(x,95)),'maximum':float(x.max())}
def build():
 image=np.array(Image.open(P/'source-name-map.jpeg').convert('RGB'));corners=json.loads((P/'source-corner-candidates.json').read_text())['records'];boundary=json.loads((P/'boundary-source-proof.json').read_text());road=json.loads((P/'source-road-controls.json').read_text());raw=json.loads((P/'source-road-ways.geojson').read_text());ways={f['properties']['osmWayId']:f for f in raw['features']};municipality=json.loads((P/'source-municipality.geojson').read_text());records=[]
 road_proof=json.loads((P/'source-road-proof.json').read_text())
 assert boundary['sourcePbfSha256']==raw['sourcePbfSha256']==road['sourcePbfSha256']==road_proof['sourcePbfSha256']
 assert road_proof['archiveSha256']==sha(P/'source-road-ways.geojson')
 assert boundary['sourceMunicipalitySha256']==sha(P/'source-municipality.geojson')
 literal_boundary_nodes={r['osmNodeId']:r['coordinates']for r in boundary['rawBoundaryNodes']}
 for i,c in enumerate(corners):
  links=boundary['cornerLinks'][i];assert links['worldCoordinates']==c['worldCoordinates'] and links['sourcePixel']==c['sourcePixel'];assert all(literal_boundary_nodes[node_id]==c['worldCoordinates']for node_id in links['actualBoundaryNodeIds']);x,y=c['sourcePixel'];rgb=image[y,x].astype(int);assert rgb.max()<195 and rgb.min()>90 and rgb.max()-rgb.min()<20
  records.append({'id':'gray-corner-'+str(i+1),'sourcePixel':c['sourcePixel'],'sourceRgb':rgb.tolist(),'sourceImageReadingUncertaintyPixels':[2,2],'sourceContext':c['sourceContext'],'targetWgs84':c['worldCoordinates'],'targetEov':list(TO(*c['worldCoordinates'])),'targetType':'Literal archived/PBF municipal boundary node coordinate, not a generated geographic point','actualOsmNodeIds':links['actualBoundaryNodeIds'],'actualSourceMemberWays':links['memberWaysContainingNode'],'correspondenceStatus':'Manual distinctive gray-corner candidate, source-stroke identity independently reviewed; historical/current exact boundary correspondence and absolute accuracy are not established.'})
 for i,c in enumerate(road['pointControls']):
  targets=[]
  for pair in c['sourceSegmentProof']:
   m=ways[pair['motorwayWayId']];r=ways[pair['crossRoadWayId']];mi=pair['motorwaySegmentIndex'];ri=pair['crossRoadSegmentIndex'];assert m['properties']['nodeRefs'][mi:mi+2]==pair['motorwayOriginalNodeRefs'] and r['properties']['nodeRefs'][ri:ri+2]==pair['crossRoadOriginalNodeRefs'];assert m['geometry']['coordinates'][mi:mi+2]==pair['motorwayOriginalCoordinates']and r['geometry']['coordinates'][ri:ri+2]==pair['crossRoadOriginalCoordinates'];intersection=LineString([TO(*v)for v in pair['motorwayOriginalCoordinates']]).intersection(LineString([TO(*v)for v in pair['crossRoadOriginalCoordinates']]));assert intersection.geom_type=='Point';recomputed=np.array(intersection.coords[0]);assert np.allclose(recomputed,pair['eovPlanCrossing'],atol=1e-7,rtol=0);targets.append(recomputed)
  target=np.array(targets).mean(0);assert np.allclose(target,c['targetEov'],atol=1e-7,rtol=0);x,y=c['sourcePixel']
  records.append({'id':'road-crossing-'+str(i+1),'sourcePixel':c['sourcePixel'],'sourceRgb':image[y,x].tolist(),'sourceImageReadingUncertaintyPixels':[3,3],'sourceContext':c['name'],'targetWgs84':list(GEO(*target)),'targetEov':target.tolist(),'targetType':c['targetType'],'originalRoadwayCrossingProof':c['sourceSegmentProof'],'correspondenceStatus':'Independently manually read actual source road crossing, identity corroborated by original current road topology; reading and historical/cartographic uncertainty retained.'})
 A=np.array([[*r['sourcePixel'],1.]for r in records]);B=np.array([r['targetEov']for r in records]);M,residual_sum,rank,singular=np.linalg.lstsq(A,B,rcond=None);assert rank==3
 fitted=A@M;res=fitted-B;inverse=np.linalg.inv(M[:2]);image_res=(B-M[2])@inverse-A[:,:2]
 # Independent centered two-by-two normal-equation calculation, rather than
 # repeating the augmented least-squares multiplication as a tautological check.
 centered_source=A[:,:2]-A[:,:2].mean(0);centered_world=B-B.mean(0)
 independent_linear=np.linalg.solve(centered_source.T@centered_source,centered_source.T@centered_world)
 independent=np.vstack([independent_linear,B.mean(0)-A[:,:2].mean(0)@independent_linear])
 independent_difference=float(np.max(np.linalg.norm(A@independent-fitted,axis=1)))
 assert independent_difference<1e-6
 for i,r in enumerate(records):r['fitPredictedEov']=fitted[i].tolist();r['fitResidualEov']=res[i].tolist();r['fitResidualMetres']=float(np.linalg.norm(res[i]));r['fitInverseImageResidualPixels']=image_res[i].tolist();r['fitInverseImageResidualPixelNorm']=float(np.linalg.norm(image_res[i]));r['fitResidualWithinDeclaredPixelReadingRange']=bool(np.all(np.abs(image_res[i])<=r['sourceImageReadingUncertaintyPixels']))
 world_boundary=transform(TO,shape(municipality['geometry'])).boundary
 gray=json.loads((P/'source-gray-control-pixels.json').read_text())['records'];fit_pixels={tuple(r['sourcePixel'])for r in records};held=[]
 for r in gray:
  if tuple(r['pixel'])in fit_pixels:continue
  w=np.r_[r['pixel'],1.]@M;held.append({'sourcePixel':r['pixel'],'origin':r['origin'],'usedInFit':False,'sharesPhysicalFeatureWithGrayCornerControls':True,'currentHistoricalBoundaryCorrespondenceUnverified':True,'predictedEov':w.tolist(),'distanceToArchivedCurrentMunicipalityMetres':float(world_boundary.distance(Point(w)))})
 line_reports=[]
 for l in road['lineControls']:
  target=unary_union([transform(TO,shape(ways[i]['geometry']))for i in l['targetOriginalWayIds']]);observations=[]
  for p in l['sourceObservations']:
   w=np.r_[p['sourcePixel'],1.]@M;observations.append({'sourcePixel':p['sourcePixel'],'sourceRgb':p['sourceRgb'],'predictedEov':w.tolist(),'crossTrackDistanceMetres':float(target.distance(Point(w))),'usedInFit':False})
  line_reports.append({'roadReference':l['roadReference'],'constraintType':'Along-track-ambiguous source-line observations, never treated as one-to-one point pairs','sharesPhysicalFeatureWithFitRoadCrossings':l['roadReference']=='M60','independentAbsoluteValidation':False,'summaryMetres':summaries([x['crossTrackDistanceMetres']for x in observations]),'observations':observations})
 hull=MultiPoint(A[:,:2]).convex_hull;test=np.array([[*p,1.]for n,p in CHECKPOINTS]);base=test@M;loo=[]
 for omitted in range(len(records)):
  keep=np.arange(len(records))!=omitted;mm=np.linalg.lstsq(A[keep],B[keep],rcond=None)[0];error=float(np.linalg.norm(A[omitted]@mm-B[omitted]));moves=np.linalg.norm(test@mm-base,axis=1);loo.append({'omittedControl':records[omitted]['id'],'matrixPixelToEov':mm.tolist(),'omittedControlPredictionErrorMetres':error,'checkpointDisplacementsMetres':moves.tolist(),'maximumCheckpointDisplacementMetres':float(moves.max()),'interpretation':'Leave-one-out leverage/sensitivity only; not an independent accuracy estimate.'})
 rng=np.random.default_rng(20261114);uncertainty=np.array([r['sourceImageReadingUncertaintyPixels']for r in records]);mc=[]
 for i in range(2000):
  perturbed=A.copy();perturbed[:,:2]+=rng.uniform(-1,1,(5,2))*uncertainty;mm=np.linalg.lstsq(perturbed,B,rcond=None)[0];mc.append(np.linalg.norm(test@mm-base,axis=1))
 mc=np.array(mc);sensitivity=[]
 for j,(name,pixel)in enumerate(CHECKPOINTS):sensitivity.append({'name':name,'sourcePixel':pixel,'insideFitControlConvexHull':hull.covers(Point(pixel)),'baselineEov':base[j].tolist(),'baselineWgs84':list(GEO(*base[j])),'readingPerturbationDisplacementMetres':summaries(mc[:,j])})
 pixel_scales=np.linalg.norm(M[:2],axis=1);area_scale=abs(np.linalg.det(M[:2]));model={'schemaVersion':1,'status':'rejected_pending_ground_control_reidentification','decisionEvidence':'decision.json; independent-review.json','rejectionReason':'The source/world identities of at least two inherited gray intermediate-vertex controls are not uniquely established; fit residuals cannot validate these correspondences.','fitMethod':'Standard unweighted affine least squares on exactly five observed image/world pairs. No gray-line or road-line observations enter the fit.','equation':'[source_x,source_y,1] @ matrixPixelToEov = [EOV_east,EOV_north]','sourcePixelOrigin':'Original Figure9 JPEG upper-left, x rightwards/y downwards, zero-based','worldCrs':'EPSG:23700','matrixPixelToEov':M.tolist(),'inverseLinearEovToPixel':inverse.tolist(),'sourcePixelScalesMetres':pixel_scales.tolist(),'absoluteJacobianAreaMetresSquaredPerPixel':float(area_scale),'leastSquaresRank':int(rank),'fitDesignSingularValues':singular.tolist(),'fitDesignConditionNumber':float(singular[0]/singular[-1]),'fitControlCount':5,'fitResidualSummaryMetres':summaries(np.linalg.norm(res,axis=1)),'fitInverseImageResidualSummaryPixels':summaries(np.linalg.norm(image_res,axis=1)),'allFiveFitResidualsInsideDeclaredPixelRanges':all(r['fitResidualWithinDeclaredPixelReadingRange']for r in records),'sourceImageReadingUncertaintyAcknowledged':True,'fitResidualIsAbsoluteAccuracy':False,'absoluteBoundaryAccuracyMetres':None,'surveyOrCadastralAccuracyApproved':False,'automaticPrimaryApproval':False,'usableForAddressAssignment':False,'quarterGeometriesGeneratedOrChanged':False}
 diagnostics={'schemaVersion':1,'heldoutGrayBoundary':{'sourceCount':len(held),'usedInFit':False,'summaryMetres':summaries([r['distanceToArchivedCurrentMunicipalityMetres']for r in held]),'limitations':'Shares current boundary physical feature with three fit corners; historical/current correspondence unverified, so this is not independent absolute validation. No source point resnapped.','records':held},'heldoutRoadLines':line_reports,'leaveOneOut':loo,'readingSensitivity':{'seed':20261114,'trials':2000,'scenario':'Independent uniform x/y image-reading perturbations within the declared 2 px corner / 3 px road boxes; targets held fixed. This is an assumed perturbation scenario, not a calibrated probability/confidence interval.','notIncluded':'Map generalisation, source/world correspondence mistakes, historical geometry changes, current OSM or geodetic errors','checkpoints':sensitivity},'noAutomaticModelOrPrimaryApproval':True}
 inputs=['source-name-map.jpeg','source-road-controls.json','source-road-ways.geojson','source-road-proof.json','source-corner-candidates.json','source-municipality.geojson','source-gray-control-pixels.json','source-gray-control-review.json','boundary-source-proof.json'];proof={'schemaVersion':1,'sourceDocumentUrl':'https://logoweb.pecs.hu/download/koncepcio/ITS.pdf','sourcePdfSha256':'995d0db03e454a34046b248526e0882aee26ffbf40ba916e996afa4c8b49f6b1','sourceImageOriginalPdfPageOneBased':48,'sourceImageOriginalXref':616,'sourcePbfSha256':raw['sourcePbfSha256'],'inputs':[{'path':n,'sha256':sha(P/n)}for n in inputs],'sourceRoadDataIndependentlyVerified':True,'sourceBoundaryRelationAndNodesIndependentlyVerified':True,'geographicNeighbourhoodNameCoordinatesUsed':False,'frozenSourceInputsMutated':False,'fitControls':records,'normalEquationMaximumResidual':float(np.max(np.abs(A.T@(A@M-B)))),'independentCenteredClosedFormMatrixPixelToEov':independent.tolist(),'independentArithmeticMaximumControlDifferenceMetres':independent_difference,'otherGrayAndRoadLinesUsedInFit':False,'automaticPrimaryApproval':False,'absoluteBoundaryAccuracyMetres':None}
 fc={'type':'FeatureCollection','features':[{'type':'Feature','id':r['id'],'geometry':{'type':'Point','coordinates':r['targetWgs84']},'properties':{k:v for k,v in r.items()if k not in ['targetWgs84','originalRoadwayCrossingProof']}}for r in records]}
 return {'model.json':model,'calculation-proof.json':proof,'diagnostics.json':diagnostics,'control-pairs.geojson':fc}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();outputs=build()
 for name,data in outputs.items():
  text=encoded(data)
  if a.check:
   if(P/name).read_text()!=text:raise ValueError('Model output differs: '+name)
  else:(P/name).write_text(text)
 print(json.dumps({'fitControls':5,'automaticPrimaryApproval':False,'check':a.check,'fitResidualRmsM':outputs['model.json']['fitResidualSummaryMetres']['rms']}))
if __name__=='__main__':main()
