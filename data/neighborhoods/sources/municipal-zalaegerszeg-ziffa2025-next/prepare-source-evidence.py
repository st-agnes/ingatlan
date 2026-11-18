"""Retain only selected native map panels; original narrative stays in local PDF."""
import argparse,hashlib,json
from pathlib import Path
import fitz
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
ORIGINAL=ROOT/'.local/neighborhoods/supplement-originals/zalaegerszeg-ziffa2025.pdf'
EXPECTED='b132fd75d6c95538023ced5eda3ad8ac7f7131c6e27f889ed7206c23e4a44745'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def enc(x):return json.dumps(x,ensure_ascii=False,indent=2)+'\n'
pa=argparse.ArgumentParser();pa.add_argument('--check',action='store_true');args=pa.parse_args()
assert sha(ORIGINAL)==EXPECTED
D=fitz.open(ORIGINAL)
assert len(D)==229
# Narrative is read only to verify page/topic evidence against the pinned original.
# No text bodies or rendered narrative pages are included in the public packet.
assert all(term in D[62].get_text() for term in ['városrészek','határait','településszerkezeti'])
assert '3.4.17 HATHÁZ' in D[140].get_text()
assert all(term in D[141].get_text() for term in ['Hatház','belterületének','0679/2'])
panels=[]
for xref in [773,778]:
 image=D.extract_image(xref);name=f'p141-xref{xref}.{image["ext"]}'
 assert any(item[0]==xref for item in D[140].get_images())
 if args.check:assert (P/name).read_bytes()==image['image']
 else:(P/name).write_bytes(image['image'])
 panels.append({'sourcePdfPageOneBased':141,'sourceImageXref':xref,'path':name,'sha256':hashlib.sha256(image['image']).hexdigest(),'dimensionsPixels':[image['width'],image['height']],'retainedContent':'Native map panel with geographic labels only; no source narrative.'})
name='source-map-only-p141.pdf'
if args.check:
 maps=fitz.open(P/name);assert len(maps)==2
 expectedHashes=[p['sha256'] for p in panels]
 assert not any(page.get_text().strip() for page in maps)
 got=[hashlib.sha256(maps.extract_image(im[0])['image']).hexdigest() for page in maps for im in page.get_images()]
 assert got==expectedHashes
else:
 maps=fitz.open()
 for item in panels:
  w,h=item['dimensionsPixels'];page=maps.new_page(width=w,height=h);page.insert_image(page.rect,filename=str(P/item['path']))
 maps.save(P/name,garbage=4,deflate=True,no_new_id=True)
facts={'schemaVersion':1,'originalPdf':{'localPath':str(ORIGINAL.relative_to(ROOT)),'sha256':EXPECTED,'sourceUrl':'https://zalaegerszeg.hu/wp-content/uploads/2025/09/ZEG_ZIFFA_egyeztetesi-valt.pdf','title':'Zalaegerszeg Zöldinfrastruktúra-fejlesztési és -fenntartási akcióterv','documentDate':'2025-08-30','status':'consultation_draft; adoption_not_independently_established','pageCount':229,'fullRawOriginalStaysLocal':True},'selectedMapPdf':{'path':name,'sha256':sha(P/name),'mapOnlyPages':2,'sourceNarrativeTextObjects':0},'selectedPanels':panels,'sourcePageFacts':[{'pdfPageOneBased':63,'fact':'Methodology describes defining neighborhood analysis boundaries using settlement structure and administrative data. Paraphrase only.'},{'pdfPageOneBased':99,'fact':'Section3.4 introduces a neighborhood-by-neighborhood green-infrastructure comparison. Paraphrase only.'},{'pdfPageOneBased':141,'fact':'Section3.4.17, figure54, provides separately labeled Hatház map panels.'},{'pdfPageOneBased':142,'fact':'Hatház is described as a small residential neighborhood outside belterület. A nearby recreation parcel0679/2 is outside the neighborhood extent. This page contains no map; no narrative image or text is retained. Paraphrase only.'}],'contentMinimization':{'verbatimNarrativeQuotationWords':0,'fullNarrativePagesRetained':False,'fullSourceTextRetained':False,'geographicLabelsAndBibliographicFactsRetained':True}}
content=enc(facts);path=P/'source-page-facts.json'
if args.check:assert path.read_text()==content
else:path.write_text(content)
print(json.dumps({'check':args.check,'nativeMapPanels':len(panels),'verbatimNarrativeQuotationWords':0}))
