#!/usr/bin/env python3
"""Extract selected municipal identity evidence; do not borrow map accuracy."""
from pathlib import Path
import fitz,json,hashlib,re
from PIL import Image
P=Path(__file__).resolve().parent;ROOT=P.parents[3];F=ROOT/'.local/neighborhoods/supplement-official-next/debrecen-fvs2023.pdf'
URL='https://hbmo.hu/portal/wp-content/uploads/2023/12/01A_eloterj.mell_DMJV-FVS-2021-27-megalapozo-vizsgalat.pdf';SHA='97c9375414895a34c82a7968625e8196e2fd4882af1019ce74ee07e89236bd01'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
assert sha(F)==SHA;D=fitz.open(F);assert len(D)==274
image=D.extract_image(1179);assert image['width']==2714 and image['height']==1228
(P/('debrecen-fvs-p208-original.'+image['ext'])).write_bytes(image['image'])
# Preserve the map only; no full narrative source pages are archived.
# Right-hand fine-quarter names only: exclude larger FVS aggregation column.
clip=fitz.Rect(294,94,552,715);labels=D[205].get_text(clip=clip)
entries=[]
for m in re.finditer(r'(?<!\d)(\d{1,2})(\*)?\.\s+([^;\n]+)',labels):
 entries.append({'historicalQuarterId':int(m[1]),'name':m[3].strip(),'starredAsAbsentFrom2007Ordinance':bool(m[2])})
assert len(entries)==79 and {r['historicalQuarterId']for r in entries}==set(range(1,80))
byname={r['name']:r for r in entries};six={6:('Ispotály',19),42:('Tócóskert',57),59:('Kerekestelep',23),60:('Homokkert',17),61:('Lencztelep',31),65:('Vargakert',61)}
proof=[];label_crops=[]
for fid,(n,i) in six.items():
 assert byname[n]['historicalQuarterId']==i
 rects=[list(r)for r in D[205].search_for(n) if r.x0>=294];assert rects
 exact=[r for r in D[205].search_for(str(i)+'. '+n) if r.x0>=294];assert len(exact)==1
 cr=exact[0]+(-1,-1,1,1);pix=D[205].get_pixmap(matrix=fitz.Matrix(3,3),clip=cr,alpha=False)
 label_crops.append(Image.frombytes('RGB',[pix.width,pix.height],pix.samples))
 proof.append({'arcgisFID':fid,'literalArcgisName':n,'historicalQuarterId':i,'literalMunicipalTableName':n,'exactNameMatch':True,'sourceNameRectanglesPdfPoints':rects,'meaning':'Independent municipal historical quarter-name identity evidence only; no boundary/placement accuracy transfer.'})
crop_canvas=Image.new('RGB',(max(im.width for im in label_crops)+20,sum(im.height for im in label_crops)+10*(len(label_crops)+1)),(255,255,255));yy=10
for im in label_crops:crop_canvas.paste(im,(10,yy));yy+=im.height+10
crop_canvas.save(P/'debrecen-fvs-six-table-label-crops.png')
write('debrecen-fvs-quarter-name-inventory.json',{'schemaVersion':1,'sourcePdfSha256':SHA,'pdfPageOneBased':206,'printedPage':206,'table':79,'columnHeading':'DMJV által elfogadott városrészek','sourceClipPdfPoints':list(clip),'namesCount':79,'historicalOrdinanceQuarterCount':75,'additionalStarredCount':4,'scope':'Names from municipal FVS historical-quarter comparison table; not a current law or completeness claim','entries':sorted(entries,key=lambda r:r['historicalQuarterId'])})
(P/'debrecen-fvs-short-name-evidence.txt').write_text('Debrecen Fenntartható Városfejlesztési Stratégiája 2021–2027, Megalapozó Vizsgálat; EDC Debrecen Nonprofit Kft; 2023. november.\n\nPage205 says the75historical quarters were designated by32/2007.(VI.28.) ordinance, already repealed by publication. FVS aggregates historical quarters into functional units and modifies Homokkert/József-Attila-telep/Zsibogó boundaries for the eastern industrial aggregate; Lóskúti is also newly separated.\n\nPage206 Table79, right column “DMJV által elfogadott városrészek”:\n'+''.join(f"{i}. {n} (ArcGIS FID{fid})\n"for fid,(n,i)in six.items())+'\nPage208 map55: “Az FVS városrészek és Debrecen történelmi városrészeinek egymáshoz való viszonya”; source: saját szerkesztés.\n\nThis evidence corroborates names; it does not validate ArcGIS source boundaries, coordinates, current legal status, original lineage or reuse rights.\n',encoding='utf-8')
write('debrecen-fvs-name-evidence.json',{'schemaVersion':1,'sourceUrl':URL,'originalLocalPath':str(F.relative_to(ROOT)),'sourcePdfSha256':SHA,'sourceBytes':F.stat().st_size,'sourcePages':len(D),'documentTitle':'Debrecen Megyei Jogú Város Fenntartható Városfejlesztési Stratégiája2021–2027, Megalapozó Vizsgálat','documentPreparer':'EDC Debrecen Nonprofit Kft','documentPublicationPeriod':'2023. november (printed title page1)','strategyHorizon':'2021–2027','urlUploadDirectory':'2023/12; this is not the boundary survey date','pdfMetadata':D.metadata,'identityEvidencePagesOneBased':[205,206,208],'pageOffsets':'Physical PDF pages equal printed pages for205,206,208','historicalSchema':'75historical quarters in32/2007.(VI.28.) ordinance; page205 explicitly says ordinance already repealed. Four starred additional areas appear in table79.','currentOrdinanceValidityNotEstablished':True,'fvsSchemaIsAggregatedAndDistinct':True,'fvsSpecificBoundaryChanges':['Homokkert/József-Attila-telep/Zsibogó adjusted for continuous eastern industrial FVS unit','Lóskúti separated from portions ofTócóvölgy andTéglagyár'],'homokkertCaveat':'Historical name confirmed; document explicitly notes a boundary modification for FVS aggregation. This does not identify which footprint or reference date the unknown-lineage ArcGIS source represents.','nameTableSixLabelsCropArchive':'debrecen-fvs-six-table-label-crops.png','nameTableSixLabelsCropSha256':sha(P/'debrecen-fvs-six-table-label-crops.png'),'sourceNarrativeArchived':False,'narrativeFactsParaphrased':True,'retainedCaptionQuotedNarrativeWordsApprox':13,'fineNameInventoryPath':'debrecen-fvs-quarter-name-inventory.json','nameTablePageOneBased':206,'nameTableNumber':79,'mapPageOneBased':208,'mapNumber':55,'mapCaption':'Az FVS városrészek és Debrecen történelmi városrészeinek egymáshoz való viszonya','mapSourceCaption':'saját szerkesztés','mapImageXref':1179,'mapImageSizePixels':[2714,1228],'mapImageArchive':'debrecen-fvs-p208-original.'+image['ext'],'mapImageArchiveSha256':sha(P/('debrecen-fvs-p208-original.'+image['ext'])),'mapRawEmbeddedImageStreamSha256':hashlib.sha256(D.xref_stream_raw(1179)).hexdigest(),'mapDecodedImageStreamSha256':hashlib.sha256(D.xref_stream(1179)).hexdigest(),'mapNativeDrawingCount':len(D[207].get_drawings()),'mapBoundaryRepresentation':'One embedded Flate-compressed raster image; no native quarter polygon paths on this page. No georeferencing or contours derived for this frozen batch.','identityCorroborations':proof,'sourceMapAccuracyTransferredToArcgis':False,'arcgisOriginalLineageProvenByThisDocument':False,'sourceMapCoordinatesUsedForFit':False,'usableForAddressAssignment':False,'fullOriginalPdfArchivedHere':False,'rightsStatus':'Official municipal strategy text/map publicly hosted by county portal; unrestricted map reuse rights not independently established.'})
print('Archived six exact historical-name corroborations;79nameinventory; rastermap proof; no boundary/accuracy transfer')
