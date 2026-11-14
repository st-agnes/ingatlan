#!/usr/bin/env python3
"""Verify explicit manually read source-stroke paths; no path inference or fitting."""
from pathlib import Path
import argparse,hashlib,json
from PIL import Image,ImageDraw
from shapely.geometry import Polygon

P=Path(__file__).resolve().parent
SOURCE=P.parent/'municipal-pecs-first-inferred/pecs-p48-names.jpeg'
PATHS={
 'arpadteto': [[324,75],[325,76],[326,77],[326,78],[327,79],[327,80],[328,81],[329,82],[329,83],[330,84],[330,85],[330,86],[329,87],[328,87],[327,88],[326,88],[325,89],[324,89],[323,90],[322,90],[321,90],[320,89],[320,88],[319,87],[319,86],[319,85],[319,84],[319,83],[319,82],[319,81],[319,80],[319,79],[320,78],[321,77],[322,77],[323,76],[324,75]],
 'm-utca': [[498,38],[499,38],[500,38],[501,38],[502,39],[502,40],[502,41],[502,42],[502,43],[502,44],[503,45],[503,46],[502,46],[501,46],[501,45],[501,44],[501,43],[500,42],[499,41],[499,40],[498,39],[498,38]],
}
META={
 'arpadteto':{'sourceName':'Árpádtető','sourceLabelAnchorPixel':[343,80],'crop':[316,72,335,94],
 'sourceObservation':'Complete purple island below the gray administration line. The north path uses [324,75] and [325,76] rather than the separate gray line near [327,72–73]. The western brown-purple stroke is adjacent to the yellow road. The pale right-upper edge pixel [329,82] is ambiguous even though the two neighbouring path vertices are dark purple strokes.',
 'completeStrokePathAuthorApproved':False},
 'm-utca':{'sourceName':'M utca','sourceLabelAnchorPixel':[514,43],'crop':[494,35,508,50],
 'sourceObservation':'Complete tiny dark curved/vertical island separate from the M utca label and neighbouring islands. The path follows the dark upper cap, eastern side, small southeastern foot, then inner western contour back to the cap. Figure12 shows the corresponding isolated curved island with a gray center, not a landuse surface.',
 'completeStrokePathAuthorApproved':True},
}

def encoded(x):return json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()

def build(images):
 im=Image.open(SOURCE).convert('RGB');out=[]
 for slug,points in PATHS.items():
  meta=META[slug];assert points[0]==points[-1]
  assert len(set(map(tuple,points[:-1])))==len(points)-1
  steps=[max(abs(a[0]-b[0]),abs(a[1]-b[1]))for a,b in zip(points,points[1:])]
  assert all(x==1 for x in steps)
  polygon=Polygon(points);assert polygon.is_valid and polygon.area>0
  vertices=[]
  for i,(x,y)in enumerate(points):
   if slug=='arpadteto':
    assessment='Manually read center of the continuous original purple/dark outer stroke in local source context.'
    ambiguity=False
    if [x,y]==[329,82]:
     assessment='Pale mixed purple edge between dark path pixels [328,81] and [329,83]; its exact stroke identity is not independently certain. No gap is bridged beyond one neighbouring pixel.';ambiguity=True
    if x==319 or (x==320 and y>=88):
     assessment+=' Brown/purple mixing with the adjacent yellow road limits edge-center precision.'
   else:
    assessment='Manually read dark original island outer-stroke center; adjacent non-island background and gray internal fill were compared in the native grid.';ambiguity=False
    if [x,y]==[503,46]:assessment+=' Gray antialias toe; connected directly to the dark foot [503,45] and [502,46].'
   vertices.append({'sequenceIndex':i,'sourcePixel':[x,y],'originalRgb':list(im.getpixel((x,y))),'manualOuterStrokeAssessment':assessment,'authorUnresolvedStrokeIdentity':ambiguity})
  row={k:v for k,v in meta.items()if k!='crop'}
  row.update({'id':slug,'coordinateSpace':'Original Figure9 integer pixel centers, x right/y down, zero-based; no geographic coordinates.','path':points,'vertices':vertices,'sourcePixelPathSha256':hashlib.sha256(json.dumps(points,separators=(',',':')).encode()).hexdigest(),'closed':True,'allStepsAre8Neighbour':True,'maximumChebyshevStepPixels':max(steps),'simpleValidSourcePixelRing':True,'sourcePixelCenterRingArea':polygon.area,'unresolvedVertexIndices':[v['sequenceIndex']for v in vertices if v['authorUnresolvedStrokeIdentity']],'cropBox':meta['crop'],'maskGrowthThresholdChangeClosingFillRepairSnapUsed':False,'sourceQuarterMapFootprintRoleSupported':True,'independentQaCompleted':False,'approvedForGeographicPolygon':False,'claimedAbsoluteAccuracy':None})
  out.append(row)
  if images:
   crop=meta['crop'];z=32;c=im.crop(crop).resize(((crop[2]-crop[0])*z,(crop[3]-crop[1])*z),Image.Resampling.NEAREST);draw=ImageDraw.Draw(c)
   coords=[((x-crop[0]+.5)*z,(y-crop[1]+.5)*z)for x,y in points];draw.line(coords,fill=(0,255,255),width=2)
   for v,(xx,yy)in zip(vertices,coords):draw.ellipse((xx-3,yy-3,xx+3,yy+3),fill=(255,150,0)if v['authorUnresolvedStrokeIdentity']else(0,255,255))
   c.save(P/('manual-islands-'+slug+'-path-preview.png'))
 return {'schemaVersion':1,'status':'author_paths_for_independent_source_qa','sourceImage':'../municipal-pecs-first-inferred/pecs-p48-names.jpeg','sourceImageSha256':sha(SOURCE),'method':'Explicit manually listed original pixel-center paths. Validation checks only literal RGB, 8-neighbour adjacency, closure, and simple ring arithmetic. No automatic pathfinding, mask expansion or stroke gap closure.','records':out,'newGeographicPolygons':0,'primaryApproval':False,'claimedAbsoluteAccuracy':None,'usableForAddressAssignment':False}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();d=build(not args.check);f=P/'manual-islands-author-paths.json';t=encoded(d)
 if args.check:assert f.read_text()==t
 else:f.write_text(t)
 print(encoded({'check':args.check,'closed8NeighbourPaths':2,'authorUnambiguousPaths':sum(r['completeStrokePathAuthorApproved']for r in d['records']),'independentQaCompleted':False,'geographicPolygons':0}))

if __name__=='__main__':main()
