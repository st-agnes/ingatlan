"""Extract native Eger map labels, legend and per-path crops for semantic review only."""
import fitz,json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent;S=P.parent/'municipal-east'
pdf=S/'eger-map-2016.pdf';doc=fitz.open(pdf);page=doc[0]
paths=json.loads((S/'eger-pdf-vector-paths.json').read_text());rows={r['pdfDrawingIndex']:r for r in paths['paths']}
fs=json.loads((S/'eger-planning-units.geojson').read_text())['features']
(P/'native-page-text.txt').write_text(page.get_text())
blocks=page.get_text('blocks');(P/'native-text-blocks.json').write_text(json.dumps([{'bbox':list(b[:4]),'text':b[4]} for b in blocks],ensure_ascii=False,indent=2)+'\n')
page.get_pixmap(matrix=fitz.Matrix(.5,.5)).save(P/'source-overview.png')
page.get_pixmap(matrix=fitz.Matrix(1,1),clip=fitz.Rect(1400,320,2260,1020)).save(P/'source-legend.png')
page.get_pixmap(matrix=fitz.Matrix(1,1),clip=fitz.Rect(1500,2800,2330,3275)).save(P/'source-title.png')
records=[]
for i,f in enumerate(fs):
 p=f['properties'];r=rows[p['sourcePdfDrawingIndex']];b=fitz.Rect(r['bounds']);b=b+(-60,-60,60,60);b=b & page.rect;scale=min(1.8,900/max(b.width,b.height));name=f"source-unit-{i:02d}-{p['sourcePdfDrawingIndex']}.png"
 page.get_pixmap(matrix=fitz.Matrix(scale,scale),clip=b).save(P/name)
 records.append({'featureIndex':i,'sourceFeatureId':f['id'],'name':p['name'],'sourcePlanId':p['sourcePlanId'],'pdfDrawingIndex':p['sourcePdfDrawingIndex'],'sourceBoundsPdfPoints':r['bounds'],'nativePathContainedText':r['nearbyText'],'sourceCrop':name,'cropMeaning':'Native PDF render of actual full source vector path bounds plus60PDFpoint context; rendering only, geometry never modified.'})
(P/'native-source-records.json').write_text(json.dumps({'sourcePdfPath':str(pdf.relative_to(P.parents[3])),'sourcePdfSha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'sourcePageOneBased':1,'sourceMapDate':'2016-08','sourceMapScale':'1:15000','pageSizePdfPoints':list(page.rect),'sourceLegendMeaning':'Four distinct schemas:2016 unified HESZ green,2014 northeast+legelo orange, older retained plans purple,2004TSZT general cyan. Cyan inset in legend is also not a quarter boundary.','records':records},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'records':len(records),'geometryModified':False}))
