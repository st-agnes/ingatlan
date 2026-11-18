from pathlib import Path
import sys,argparse
sys.dont_write_bytecode=True
cli=argparse.ArgumentParser(description='Independent offline pypdf/Fraction Tatabánya source audit; default and --check are read-only.')
group=cli.add_mutually_exclusive_group()
group.add_argument('--check',action='store_true',help='Recompute all checks and compare the frozen independent review without writes.')
group.add_argument('--write-review',action='store_true',help='Explicitly regenerate only independent-review.json after all checks pass.')
cli_options=cli.parse_args()
from fractions import Fraction as F
from collections import Counter
import itertools,hashlib,json,gzip,math
import fitz,numpy as np,pyproj
from pypdf import PdfReader
from pypdf.generic import ContentStream
from shapely.geometry import Polygon,Point,shape
from shapely.ops import transform,nearest_points
from shapely.affinity import affine_transform
from pyproj import Transformer,Geod
R=Path(__file__).resolve().parents[4];P=R/'data/neighborhoods/sources/municipal-tatabanya-more';O=R/'data/neighborhoods/sources/municipal-west'
def read(n):return json.loads((P/n).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def need(v,s):
 if not v:raise AssertionError(s)
trace=read('source-vector-trace.json');geo=read('georeference-proof.json');manifest=read('generated-manifest.json');proof=read('conversion-proof.json');unresolved=read('unresolved-fine-areas.json');visualhash=sha(P/'visual-review.json')
source=O/'tatabanya-map.source.pdf';doc=fitz.open(source);page=doc[0];mupdf=page.get_drawings();reader=PdfReader(source);pdfpage=reader.pages[0];ops=ContentStream(pdfpage['/Contents'],reader).operations
need(sha(source)==trace['sourcePdfSha256']==manifest['originalPdfSha256'],'PDF hash');need([float(x) for x in pdfpage.mediabox]==[0,0,842,1191],'PDF MediaBox');height=F(str(pdfpage.mediabox.top));sourcebytes=b'\n'.join(doc.xref_stream(x) for x in page.get_contents());need(hashlib.sha256(sourcebytes).hexdigest()==trace['decodedConcatenatedContentSha256'],'decoded actual PDF streams');need(page.get_contents()==trace['contentStreamRefs'],'stream refs')
archived={d['sourceDrawingIndex']:d for d in trace['selectedOriginalDrawings']};selected=set(archived);paths={};allbboxes=[];allcolors=[]
I=((F(1),F(0),F(0)),(F(0),F(1),F(0)),(F(0),F(0),F(1)))
def matrixmul(a,b):return tuple(tuple(sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)) for i in range(3))
def point(c,values):
 x,y=map(lambda x:F(str(x)),values);return (c[0][0]*x+c[0][1]*y+c[0][2],height-(c[1][0]*x+c[1][1]*y+c[1][2]))
def matrixsix(c):return [c[0][0],c[1][0],c[0][1],c[1][1],c[0][2],c[1][2]]
ctm=I;stroke=(F(0),)*3;fill=stroke;stack=[];items=[];commands=[];current=start=None;paintindex=0;all_sequence_deltas=[];worstbbox=0.0
for operands,op in ops:
 if op==b'q':stack.append((ctm,stroke,fill))
 elif op==b'Q':ctm,stroke,fill=stack.pop()
 elif op==b'cm':
  a,b,c,d,e,f=[F(str(x)) for x in operands];ctm=matrixmul(ctm,((a,c,e),(b,d,f),(F(0),F(0),F(1))))
 elif op in [b'RG',b'rg']:
  value=tuple(F(str(x)) for x in operands)
  if op==b'RG':stroke=value
  else:fill=value
 elif op in [b'G',b'g']:
  value=(F(str(operands[0])),)*3
  if op==b'G':stroke=value
  else:fill=value
 elif op in [b'm',b'l',b'c']:
  args=[str(x) for x in operands];commands.append({'operator':op.decode(),'operands':args,'ctm':matrixsix(ctm)})
  if op==b'm':current=start=point(ctm,operands)
  elif op==b'l':following=point(ctm,operands);items.append(('l',current,following));current=following
  else:
   control1=point(ctm,operands[:2]);control2=point(ctm,operands[2:4]);following=point(ctm,operands[4:]);items.append(('c',current,control1,control2,following));current=following
 elif op==b'h':
  commands.append({'operator':'h','operands':[],'ctm':None})
  if current!=start:items.append(('l',current,start))
  current=start
 elif op in [b'S',b'f',b'f*',b'B',b'B*',b's',b'b',b'b*']:
  if op in [b's',b'b',b'b*'] and current!=start:items.append(('l',current,start))
  color=None if op.startswith(b'f') else stroke;fc=None if op in [b'S',b's'] else fill;d=mupdf[paintindex]
  for got,key in [(color,'color'),(fc,'fill')]:
   need((got is None)==(d[key] is None),'paint color None mismatch')
   if got is not None:need(max(abs(float(a)-b) for a,b in zip(got,d[key]))<1e-6,'paint color sequence mismatch')
  exactxy=[p for i in items for p in i[1:]];approxxy=[]
  for it in d['items']:
   if it[0]=='qu':approxxy.extend(tuple(p) for p in it[1])
   elif it[0]=='re':approxxy.extend([tuple(it[1].tl),tuple(it[1].br)])
   else:approxxy.extend(tuple(p) for p in it[1:])
  if exactxy and approxxy:
   dif=max(abs(float(fn(p[axis] for p in exactxy))-fn(p[axis] for p in approxxy)) for axis in [0,1] for fn in [min,max]);worstbbox=max(worstbbox,dif);need(dif<=.0003,'all-path bounding coordinates mismatch')
  if paintindex in selected:
   arch=archived[paintindex];need(arch['paintOperator']==op.decode(),'selected paint op');need((tuple(F(x) for x in arch['strokeRgbDecimal']) if arch['strokeRgbDecimal'] is not None else None)==color,'selected archived literal stroke RGB')
   archiveditems=[(it[0],*(tuple(F(x) for x in pt) for pt in it[1:])) for it in arch['exactPageLineItems']];need(items==archiveditems,'selected source-item exact Fraction reconstruction')
   need(len(commands)==len(arch['originalCommands']),'selected command count')
   for cmd,raw in zip(commands,arch['originalCommands']):
    need(cmd['operator']==raw['operator'] and [F(x) for x in cmd['operands']]==[F(x) for x in raw['operands']],'original raw operands mismatch')
    need(cmd['ctm']==([F(x) for x in arch['graphicsMatricesDecimal'][raw['ctmIndex']]] if raw['ctmIndex'] is not None else None),'independent CTM mismatch')
   # Compare selected original item order point-by-point with separately parsed MuPDF.
   need(len(items)==len(d['items']) and all(it[0]=='l' and ap[0]=='l' for it,ap in zip(items,d['items'])),'selected MuPDF line sequence')
   dd=max(abs(float(v)-ap[k][axis]) for it,ap in zip(items,d['items']) for k in [1,2] for axis,v in enumerate(it[k]));all_sequence_deltas.append(dd)
   need(dd<.0003,'selected full source coordinate sequence mismatch')
   paths[paintindex]=items.copy()
  paintindex+=1;items=[];commands=[];current=start=None
 elif op==b'n':items=[];commands=[];current=start=None
 elif op in [b're',b'v',b'y',b'Do',b'BI',b'ID',b'EI']:raise AssertionError('Unexpected unsupported PDF geometry operator')
need(not stack and paintindex==len(mupdf)==trace['parsedDrawingCount']==12864,'all paint mapping count')
need(len(paths)==len(selected)==17,'all selected source paths reconstructed')
original_labels={}
for block in page.get_text('dict')['blocks']:
 for line in block.get('lines',[]):
  for span in line['spans']:
   if span['text'] in trace['sourceLabels']:
    x0,y0,x1,y1=span['bbox'];original_labels[span['text']]={'bbox':list(span['bbox']),'centre':[(x0+x1)/2,(y0+y1)/2]}
need(original_labels==trace['sourceLabels'] and len(original_labels)==16,'original PDF labels/bboxes/centres differ from trace')
need(abs(worstbbox-trace['maximumMuPdfFloatBoundingCoordinateDifferencePoints'])<1e-7,'all path worst discrepancy exceeds pypdf decimal-normalization tolerance')

def points(i):
 its=paths[i];need(all(it[0]=='l' for it in its),'source is not all lines');need(all(a[2]==b[1] for a,b in zip(its,its[1:])),'selected source path disjoint');return [its[0][1]]+[it[2] for it in its]
def signarea(ring):return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ring,ring[1:]))/2
need(points(6325)==points(5531),'actual green inner versus orange outer identity');need(signarea(points(1286))*signarea(points(6325))<0,'forest opposite winding')
need(points(1815)[366]==points(1815)[368] and points(4851)[11]==points(4851)[13],'retraced spurs not exact');need(points(3277)[:21]==points(3696)[203:224][::-1],'north shared internal reversed chain')
legacy_path=R/geo['frozenEarlierProofPath'];legacy=json.loads(legacy_path.read_text());affine=legacy['affinePdfToEov'];need(sha(legacy_path)==geo['frozenEarlierProofSha256'] and affine==geo['affinePdfToEov'],'frozen affine changed');need(geo['reoptimisedOrShiftedToFitNewSourceCycles'] is False,'reoptimization')
pyproj.network.set_network_enabled(False);inverse=Transformer.from_crs('EPSG:23700','EPSG:4326',always_xy=True);to_metric=Transformer.from_crs('EPSG:4326','EPSG:23700',always_xy=True);geod=Geod(ellps='WGS84')
parentpath=R/geo['currentReferenceMunicipalityArchivePath'];need(sha(parentpath)==geo['currentReferenceMunicipalityArchiveSha256'],'parentarchive hash');fcs=json.loads(gzip.decompress(parentpath.read_bytes()));parent=shape(next(f['geometry'] for f in fcs['features'] if f['properties']['name']=='Tatabánya' and f['properties'].get('usedForAssociation')));parentm=transform(to_metric.transform,parent)
ctrl=[]
for c in legacy['registration']['controlPoints']:
 x,y=c['sourcePdfPoint'];mx=affine[0]*x+affine[1]*y+affine[4];my=affine[2]*x+affine[3]*y+affine[5];q=Point(mx,my);r=q.distance(parentm.boundary);near=nearest_points(q,parentm.boundary)[1]
 need(math.dist([mx,my],c['transformedEovPoint'])<1e-7 and abs(r-c['residualM'])<1e-5 and near.distance(Point(c['referenceEovPoint']))<1e-5,'frozen17control mismatch');ctrl.append(r)
need(len(ctrl)==17==len(geo['recomputedSampledControlChecks']),'17controls');need(all(abs(c-r['recomputedResidualM'])<1e-7 for c,r in zip(ctrl,geo['recomputedSampledControlChecks'])),'newcontrolsrecord')
primary=read('additional-quarter-vectors.geojson')['features'];groups=read('compound-source-groups.geojson')['features'];features={f['properties']['name']:f for f in primary+groups};need(len(primary)==3 and len(groups)==4 and len(features)==7,'output counts');old_names={'Kertváros','Alsógalla','Óváros','Síkvölgy'};need(not(old_names&set(features)),'old names reexported')
sourcepolys={};metricpolys={};record=[];edgecount=0;names=[]
def floatpoints(r):return [[float(v) for v in xy] for xy in r]
def worldring(r):
 ar=np.asarray(floatpoints(r));mx=affine[0]*ar[:,0]+affine[1]*ar[:,1]+affine[4];my=affine[2]*ar[:,0]+affine[3]*ar[:,1]+affine[5];lon,lat=inverse.transform(mx,my);return np.column_stack([lon,lat]).tolist()
for cir in trace['extractedCircuits']:
 name=cir['name'];f=features[name];rings=[[tuple(F(x) for x in xy) for xy in r] for r in cir['literalSourceRings']];need(len(rings)==len(cir['sourceArcs'])==len(cir['edgeOrigins']),'circuit provenance counts')
 for r,arcs,origins in zip(rings,cir['sourceArcs'],cir['edgeOrigins']):
  reconstructed=[];expectedorigin=[]
  for i,a,b,rev in arcs:
   part=points(i)[a:b+1];need(len(part)==b-a+1,'arcindices')
   if rev:part=part[::-1]
   need(not reconstructed or reconstructed[-1]==part[0],'exact arc junction')
   reconstructed+=part if not reconstructed else part[1:]
   expectedorigin.extend((i,j,rev) for j in (range(b-1,a-1,-1) if rev else range(a,b)))
  need(r==reconstructed and r[0]==r[-1] and len(origins)==len(r)-1,'ring reconstruction/closure')
  need(expectedorigin==[(o['sourceDrawingIndex'],o['sourceLineItemIndex'],o['reversed']) for o in origins],'origin sequence')
  for a,b,o in zip(r,r[1:],origins):
   it=paths[o['sourceDrawingIndex']][o['sourceLineItemIndex']];expectededge=(it[2],it[1]) if o['reversed'] else(it[1],it[2]);need((a,b)==expectededge,'invented output edge')
  edgecount+=len(origins)
 sourcepoly=Polygon(floatpoints(rings[0]),[floatpoints(r) for r in rings[1:]]);need(sourcepoly.is_valid and not sourcepoly.is_empty,'invalid exact source circuit');need(sourcepoly.area==cir['sourcePdfSquaredPointArea'],'source area')
 labels=[label for label,info in trace['sourceLabels'].items() if sourcepoly.covers(Point(info['centre']))];need(set(labels)==set(cir['labelCentresInside'])==set(f['properties']['sourceLabels']),'label coverage')
 expectedcoords=[worldring(r) for r in rings];need(expectedcoords==f['geometry']['coordinates'],'WGS84 exact reconstruction')
 world=shape(f['geometry']);need(world.is_valid,'invalid world output');metric=affine_transform(sourcepoly,affine);sourcepolys[name]=sourcepoly;metricpolys[name]=metric;names.append(name)
 props=f['properties'];isprimary=f in primary;need(props['boundaryKind']==('neighbourhood' if isprimary else'planning_unit') and props['canonicalNameIsNeighborhood']==isprimary and props['estimated'] is False,'kind classification');need(props['usableForAddressAssignment'] is False and props['sourceIsOfficial'] is False and props['sourceIsHardBoundary'] is False and props['claimedAbsoluteAccuracyMetres'] is None,'limitsflags');need(props['currentNameEvidence']['currentNameIndependentlyConfirmed'] is False,'currentnameclaim')
 if not isprimary:need(props['notIndividualFineNeighbourhood'] is True and props['nameIsDescriptiveCombination'] is True,'compound mislabeledfine')
 area,perim=geod.geometry_area_perimeter(world);need(abs(abs(area)-props['areaM2'])<1e-6 and abs(perim-props['perimeterM'])<1e-6,'ellipsoidmetrics')
 outside=metric.difference(parentm);fraction=outside.area/metric.area;maxdist=max(Point(xy).distance(parentm) for xy in metric.exterior.coords);cmp=props['referenceMunicipalityComparison']
 need(abs(outside.area-cmp['outsideAreaM2'])<1e-6 and abs(fraction-cmp['outsideFraction'])<1e-12 and abs(maxdist-cmp['maximumOutsideDistanceAmongExteriorVerticesM'])<1e-6 and cmp['sourceClippedToReference'] is False,'parent comparison mismatch');need(parentm.covers(metric)==cmp['fullyContained'],'containment boolean')
 record.append({'name':name,'kind':props['boundaryKind'],'sourceRings':len(rings),'sourceVertexCounts':[len(r) for r in rings],'sourceAreaPdfSquared':sourcepoly.area,'allEdgesReconstructedFromLiteralOriginalItems':True,'exactClosedFractionEndpoints':True,'worldCoordinatesReconstructedExactly':True,'sourceLabelsCovered':labels,'areaM2':abs(area),'currentMunicipalityOutsideAreaM2':outside.area,'currentMunicipalityOutsidePercent':fraction*100,'maximumOutsideDistanceAmongExteriorVerticesM':maxdist,'sourceClipped':False})
need(points(4851)[95]==points(4557)[0] and points(4851)[96]==points(4558)[-1],'Nyugat sharededge exact source operand endpoints')
westtri=Polygon(floatpoints(points(5527)[336:340]));a,b=points(4836),points(4851);southloop=Polygon(floatpoints(a[3:6]+b[3:5][::-1]+[a[3]]));need(sourcepolys['Nyugati ipari park – Erőmű ltp.'].covers(westtri) and sourcepolys['VI-os telep – Felsőgalla'].covers(southloop),'interior discarded loops extend outside');need(abs(westtri.area-.0216)<1e-10 and abs(southloop.area-.54)<1e-10,'tinyloopactualarea')
for name,index in trace['existingFourNotReexported'].items():
 po=Polygon(floatpoints(points(index)));sourcepolys[name]=po;metricpolys[name]=affine_transform(po,affine)
overlaps=[]
for a,b in itertools.combinations(sourcepolys,2):
 s=sourcepolys[a].intersection(sourcepolys[b]).area;m=metricpolys[a].intersection(metricpolys[b]).area
 if s>1e-9:overlaps.append({'names':[a,b],'sourcePdfSquaredPoints':s,'approximateMetricOverlapM2':m})
need(len(overlaps)==len(trace['sourceOverlapsPreserved']),'source overlap count')
for got,claimed in zip(overlaps,trace['sourceOverlapsPreserved']):
 need(got['names']==claimed['names'] and abs(got['sourcePdfSquaredPoints']-claimed['sourcePdfSquaredPoints'])<1e-12 and abs(got['approximateMetricOverlapM2']-claimed['approximateMetricOverlapM2'])<1e-6,'overlap metrics');need(claimed['overlapAlreadyInOriginalSource'] is True and claimed['trimmedOrRepaired'] is False,'overlapclaim')
need(unresolved['individuallyUnresolvedFineNames']==sum(len(x['names']) for x in unresolved['blockers'])==9 and unresolved['inventedFineSplitsProduced'] is False,'fineunresolved9');need(unresolved['previousFineQuarterCount']==4 and unresolved['newFineQuarterCount']==3 and unresolved['sourceLabelCount']==16,'source16labelpartition')
for name,h in manifest['artifactsSha256'].items():need(sha(P/name)==h,'artifacthash '+name)
need(sha(R/manifest['converterPath'])==manifest['converterSha256'],'converterhash');need(sha(P/'parse_exact_pdf.py')==manifest['parserSha256']==trace['parserSha256'],'parserhash');need(sha(P/'visual-review.json')==manifest['visualReviewSha256']==visualhash,'visualfrozenhash')
for n in ['registry-entry.json','planning-registry-entry.json']:
 reg=read(n);need(sha(R/reg['path'])==reg['sha256'],'registry geometryhash')
report={'schemaVersion':1,'independentAuditorPath':str(Path(__file__).resolve().relative_to(R)),'independentAuditorSha256':sha(Path(__file__)),'reviewer':'independent fig81_visual agent, offline final numeric/visual audit','verdict':'PASS_WITH_RECORDED_SOURCE_OVERLAPS_AND_HISTORICAL_REFERENCE_DIFFERENCES','scope':'3 distinct named source-quarter polygons and4 separate compound source groups; source fidelity verified, current/legal/geodetic/address accuracy not certified.','independentMethod':'Independent pypdf ContentStream tokenization of original publisher PDF; Fraction 3x3 graphics-matrix composition and exact rational source-point reconstruction; separately compared original source paint order/colors/all-path bboxes and selected complete item sequences with MuPDF, then independently verified edge provenance, georeference, labels, source overlap and reference differences. Converter/helper output booleans were not used as sole proof.','source':{'pdfSha256':sha(source),'decodedStreamsSha256':hashlib.sha256(sourcebytes).hexdigest(),'sourcePageSizePdfPoints':[842,1191],'contentOperatorCount':len(ops),'allPaintPathCount':paintindex,'selectedDrawingCount':len(selected),'selectedDrawingIndices':sorted(selected),'sourceLabelCount':16,'originalContentAndArchiveOperandsAndCtmsExactlyMatch':True,'maximumAllMuPdfBoundingDifferencePoints':worstbbox,'maximumSelectedMuPdfItemCoordinateDifferencePoints':max(all_sequence_deltas),'allPathMaximumStatisticDifferenceFromDecimalHelperPoints':abs(worstbbox-trace['maximumMuPdfFloatBoundingCoordinateDifferencePoints']),'allPathPypdfNormalizationNote':'pypdf normalizes long nonselected numeric operands; all selected source-line operands and CTMs reconstruct exactly by Fraction.','floatAliasResolution':'Actual original decimal CTMs/operands agree exactly by Fraction, despite MuPDF float32 aliases; no coordinate snapping.'},'visualReview':{'frozenSemanticReviewSha256':visualhash,'originalSourceAndFinalCycleOverlayInspected':True,'observations':['Three red named source extents follow the published map: Galla industrial outline, Nyugat-Gerecse and Észak-Vértes. Industrial/forest function is not a reason to misclassify a distinct named source quarter.','Észak-Vértes explicitly excludes the orange Síkvölgy island using the identical green inner source ring; correct opposite winding was checked.','Four blue areas are visibly multi-label source compounds, retained as planning_unit and never copied under individual fine names.','Turquoise6326 is Erőmű-tó lake, outside the Erőmű LTP. label centre; it is not substituted as a residential quarter.','No separate Szőlőhegy/Újváros/Sárberek or VI-os/Felsőgalla divider is invented from road ink strips.']},'literalCircuitChecks':record,'literalExportedSourceEdgeCount':edgecount,'sourceIdentities':{'forestInner6325ExactlyEqualsExistingSikvolgy5531':True,'forestOuterInnerOppositeWinding':True,'forestSignedSourceAreas':{k:str(signarea(points(i))) for k,i in [('outer1286',1286),('inner6325',6325)]},'gallaOnlyOmittedRetracedSpurVertices':[366,367,368],'gallaSpurEndpointsExactlyEqual':True,'nyugatClosureActualSourceDrawingItem':[4851,95],'northSharedInternalChainReversedExactly':True,'westernInteriorLoopAreaPdfSquared':westtri.area,'southernInteriorLoopAreaPdfSquared':southloop.area,'omittedSmallLoopsWhollyInsideChosenActualSourceCycles':True,'newClosingEdgesGenerated':False,'sourceGeometryRepairedSmoothedOrClipped':False},'frozenGeoreference':{'frozenEarlierProofSha256':sha(legacy_path),'affinePdfToEov':affine,'originalCalibrationVertexCount':geo['frozenCalibrationVertexCount'],'originalCalibrationRmsM':geo['frozenCalibrationRmsM'],'calibrationInterpretation':'Frozen earlier779-vertex affine fit reused; all17 archived sample controls independently re-evaluated against actual current canonical municipality. This audit did not refit the779 calibration vertices.','independentlyRecheckedArchivedSampleControls':len(ctrl),'recomputedSampleResidualsM':ctrl,'currentCanonicalMunicipalitySha256':sha(parentpath),'reoptimisedForNewPolygons':False,'pyprojVersion':pyproj.__version__,'projVersion':pyproj.proj_version_str,'projNetworkDisabled':True,'claimedAbsoluteAccuracyMetres':None},'nonzeroOriginalSourceOverlapChecks':overlaps,'overlapCount':len(overlaps),'overlapsAlreadyPresentInSourceAndPreserved':True,'outputs':{'primaryCount':3,'compoundCount':4,'oldFourReexported':False,'unresolvedIndividualFineNames':9,'inventedFineSplitsProduced':False,'fullyContainedInCurrentCanonicalMunicipalityClaimed':False,'sourceClippedToCurrentReference':False,'usableForAddressAssignment':False,'currentNamesIndependentlyConfirmed':False,'currentLegalForceIndependentlyChecked':False,'sourceOpenReuseRightsIndependentlyEstablished':False},'artifactHashesSha256':{name:sha(P/name) for name in ['additional-quarter-vectors.geojson','compound-source-groups.geojson','source-vector-trace.json','georeference-proof.json','unresolved-fine-areas.json','conversion-proof.json','generated-manifest.json','registry-entry.json','planning-registry-entry.json']},'limitations':['2018 statutory-map source; present-day fine names, current legal force and underlying-data date unverified.','The original source contains twelve measured pairwise overlaps; none has been trimmed or hidden.','Historical source plus frozen approximate registration differs slightly from contemporary OSM municipality; measured outside fractions/distances remain present.','Control residuals and library datum-operation accuracy do not establish absolute source-boundary accuracy.','No automatic address assignment or cadastral/current-legal boundary certification.','Municipal map open-reuse license remains unverified; ODbL attribution applies to OSM geographic reference.']}
review_bytes=(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode();review_path=P/'independent-review.json'
if cli_options.write_review:review_path.write_bytes(review_bytes)
elif cli_options.check:need(review_path.exists() and review_path.read_bytes()==review_bytes,'frozen independent review differs')
print(json.dumps({'review':'data/neighborhoods/sources/municipal-tatabanya-more/independent-review.json','verdict':report['verdict'],'primary':3,'groups':4,'literalEdges':edgecount,'sourceOverlaps':len(overlaps),'reviewSha256':hashlib.sha256(review_bytes).hexdigest(),'reviewWritten':cli_options.write_review,'readOnlyCheck':not cli_options.write_review,'outsidePercent':{r['name']:r['currentMunicipalityOutsidePercent'] for r in record}},ensure_ascii=False))
