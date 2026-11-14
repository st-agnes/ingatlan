#!/usr/bin/env python3
"""Offline source-only Veszprém TAK2019 archive; no world geometry or registration."""
from pathlib import Path
import hashlib,json
import fitz
from PIL import Image
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
SOURCE=ROOT/'.local/neighborhoods/supplement-originals/veszprem-tak2019.pdf'
EXPECTED='dea5b312edd534ffe5b1aca99618c5e5e346e20ad2d62a97bac8d41e15937f9b'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,x): (P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
assert sha(SOURCE)==EXPECTED
D=fitz.open(SOURCE); page=D[13]
assert len(D)==134 and [i[0] for i in page.get_images()]==[47]
image=D.extract_image(47)
(P/'page14-original.jpeg').write_bytes(image['image'])
page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False).save(P/'page14-inspection.png')
selected=fitz.open();selected.insert_pdf(D,from_page=13,to_page=13);selected.set_metadata({'title':'Veszprém TAK2019, selected source page14','subject':'Official quarter names with semantically ambiguous map extents; source-only research archive'});selected.save(P/'source-page14.pdf',garbage=4,deflate=True,no_new_id=True);selected.close()
(P/'page14-short-labels.txt').write_text(page.get_text(),encoding='utf-8')
names=[
 ('Belváros',[]),('Dózsaváros',['Temetőhegy','Pajtakert']),('Jeruzsálemhegy',['Endrődi Sándor lakótelep','Takácskert']),('Egyetemváros',['Nádortelep','Egry József utcai lakótelep','Hóvirágtelep']),('Füredidomb',[]),('Cholnokyváros',[]),('Újtelep',[]),('Jutasi úti lakótelep',[]),('Bakonyalja',[]),('Jutaspuszta',[]),('Csererdő',[]),('Iparváros',[]),('Csatár',[]),('Szabadságpuszta',[]),('Kádárta',[]),('Gyulafirátót',[])]
for name,subs in names:
 assert name in page.get_text()
 assert all(sub in page.get_text() for sub in subs)
positions=[[391,750],[347,706],[339,799],[393,835],[431,816],[466,781],[438,727],[429,677],[421,625],[357,575],[229,612],[316,651],[114,709],[428,985],[576,587],[576,430]]
write('names-and-source-markers.json',{'schemaVersion':1,'municipality':'Veszprém','sourcePdfPageOneBased':14,'sourcePrintedPage':14,'sourceImageXref':47,'coordinateSpace':'Native embedded JPEG pixels; origin top-left, x right, y down. Approximate observed number-marker centers only; no geographic coordinates.','referencePeriod':'2019 municipal architectural handbook; current completeness not established','officialMainNameCount':16,'subordinateSlashNamesAreNotIndependentGeometry':True,'sourceMarkersUsedForWorldRegistration':False,'names':[{'sourceNumber':i+1,'name':n,'subordinateNamesAfterSlash':sub,'sourceMarkerPixelApprox':xy,'markerReadingUncertaintyPixels':2,'geometryAssigned':False} for i,((n,sub),xy) in enumerate(zip(names,positions))]})
drawings=[]
for i,d in enumerate(page.get_drawings()):
 drawings.append({'index':i,'type':d['type'],'rectPdfPoints':list(d['rect']),'fill':list(d['fill']) if d['fill'] else None,'items':[{'operator':it[0],'rectPdfPoints':list(it[1]),'orientation':it[2]} for it in d['items']],'role':'Decorative light-gray vertical text-side bar; not map or boundary geometry'})
inventory=[]
for i,p in enumerate(D):
 inventory.append({'pdfPageOneBased':i+1,'images':[{'xref':im[0],'width':im[2],'height':im[3],'bitsPerComponent':im[4],'colorspace':im[5]} for im in p.get_images()],'vectorDrawingCount':len(p.get_drawings())})
write('pdf-primitive-inventory.json',{'schemaVersion':1,'sourcePdfSha256':EXPECTED,'inventoryContainsNoBulkPdfText':True,'pages':inventory})
write('source-extraction-proof.json',{'schemaVersion':1,'sourceUrl':'https://veszprem.hu/wp-content/uploads/2023/10/I-6_VMJV_TAK_2019_web.pdf','originalLocalPath':str(SOURCE.relative_to(ROOT)),'sourcePdfSha256':EXPECTED,'sourceBytes':SOURCE.stat().st_size,'sourcePages':len(D),'sourceDocumentTitle':'VESZPRÉM TELEPÜLÉS ARCULATI KÉZIKÖNYV 2019.','pdfMetadata':D.metadata,'selectedPdfPageOneBased':14,'selectedPrintedPage':14,'selectedPageSizePdfPoints':list(page.rect),'mapImageXref':47,'mapImageDimensionsPixels':[image['width'],image['height']],'imageBitsPerComponent':image['bpc'],'imageColorspaceComponents':image['colorspace'],'imageEncoding':image['ext'],'imageArchivePath':'page14-original.jpeg','imageArchiveSha256':sha(P/'page14-original.jpeg'),'imageBytes':len(image['image']),'extractionMethod':'PyMuPDF Document.extract_image(47), original embedded JPEG encoded bytes; no image resampling or color change. The separate page14-inspection.png is a 1.5× rendered page for review.','mapImagePlacementPdfPoints':[list(r) for r in page.get_image_rects(47)],'nativeMapBoundaryPathsPresent':False,'selectedPageNativeDrawings':drawings,'nativeDrawingCount':len(drawings),'sourceBlueLineLegendPresent':False,'sourceBlueLineMeaning':'Unresolved. Built-up/cadastral or settlement-piece extent is plausible; statutory quarter extent is not established.','geographicCoordinateReferenceSystemPresent':False,'sourceQuarterGeometriesGenerated':0,'finalWorldRegistrationPerformed':False,'worldGeometryPublished':False,'discardedExploration':'An initial municipality-only placement was evaluated then discarded before any world candidate geometry or final registration was produced; this source-only archive has no geolocation output.','sourceMarkersUsedAsFitControls':False,'wholeOriginalPdfArchivedHere':False,'reproductionCommand':'python data/neighborhoods/sources/municipal-veszprem-tak2019-next/reproduce-source.py'})
print('source-only archive verified;16 main names;0 polygons')
