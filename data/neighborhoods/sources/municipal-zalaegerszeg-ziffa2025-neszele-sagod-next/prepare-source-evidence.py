"""Create a map-only evidence packet; original study narrative remains local."""
import argparse,hashlib,json
from pathlib import Path
import fitz
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
ORIGINAL=ROOT/'.local/neighborhoods/supplement-originals/zalaegerszeg-ziffa2025.pdf'
EXPECTED='b132fd75d6c95538023ced5eda3ad8ac7f7131c6e27f889ed7206c23e4a44745'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def enc(x):return json.dumps(x,ensure_ascii=False,indent=2)+'\n'
pa=argparse.ArgumentParser();pa.add_argument('--check',action='store_true');args=pa.parse_args()
assert sha(ORIGINAL)==EXPECTED
D=fitz.open(ORIGINAL);assert len(D)==229
assert all(x in D[137].get_text() for x in ['NESZELE-SÁGOD','53. ábra'])
assert all(x in D[138].get_text() for x in ['Neszele','Ságod','összevonva'])
panels=[]
for xref in [758,759,768,769]:
 im=D.extract_image(xref);name=f'p138-xref{xref}.{im["ext"]}'
 assert any(item[0]==xref for item in D[137].get_images())
 if args.check:assert (P/name).read_bytes()==im['image']
 else:(P/name).write_bytes(im['image'])
 panels.append({'path':name,'sourcePdfPageOneBased':138,'imageXref':xref,'sha256':hashlib.sha256(im['image']).hexdigest(),'dimensionsPixels':[im['width'],im['height']],'neighborhood':'Neszele' if xref in [758,768] else 'Ságod','role':'satellite companion' if xref in [758,759] else 'native thematic map with quarter contour'})
name='source-map-only-p138.pdf'
if args.check:
 maps=fitz.open(P/name);assert len(maps)==4
 assert not any(page.get_text().strip() for page in maps)
 got=[hashlib.sha256(maps.extract_image(im[0])['image']).hexdigest() for page in maps for im in page.get_images()]
 assert got==[p['sha256'] for p in panels]
else:
 maps=fitz.open()
 for item in panels:
  w,h=item['dimensionsPixels'];page=maps.new_page(width=w,height=h);page.insert_image(page.rect,filename=str(P/item['path']))
 maps.save(P/name,garbage=4,deflate=True,no_new_id=True)
facts={'schemaVersion':1,'source':{'url':'https://zalaegerszeg.hu/wp-content/uploads/2025/09/ZEG_ZIFFA_egyeztetesi-valt.pdf','localOriginal':str(ORIGINAL.relative_to(ROOT)),'sha256':EXPECTED,'title':'Zalaegerszeg Zöldinfrastruktúra-fejlesztési és -fenntartási akcióterv','documentDate':'2025-08-30','status':'consultation_draft; adoption_not_independently_established','pageCount':229,'fullRawPdfStaysLocal':True},'selectedMapPdf':{'path':name,'sha256':sha(P/name),'mapOnlyPages':4,'sourceNarrativeTextObjects':0},'selectedPanels':panels,'pageFacts':[{'pdfPageOneBased':63,'fact':'Study methodology defines neighborhood analysis boundaries using settlement structure and administrative data. Paraphrase only.'},{'pdfPageOneBased':138,'fact':'Figure53 has distinct individually labeled Neszele and Ságod map contours within shared chapter section3.4.16.'},{'pdfPageOneBased':139,'fact':'Separate neighborhood descriptions appear for Neszele and Ságod; green-space provision is evaluated jointly. This page has no retained narrative or rendered page. Paraphrase only.'}],'identity':'Shared section/unit16 does not make the two individual maps aliases of one grouped parent polygon. This batch admits only Neszele; Ságod literal raster extraction remains quarantined.','contentMinimization':{'verbatimNarrativeQuotationWords':0,'fullNarrativeTextOrRenderedPagesRetained':False,'geographicLabelsAndBibliographicFactsRetained':True}}
content=enc(facts);path=P/'source-page-facts.json'
if args.check:assert path.read_text()==content
else:path.write_text(content)
print(json.dumps({'check':args.check,'nativeMapPanels':4,'verbatimNarrativeQuotationWords':0}))
