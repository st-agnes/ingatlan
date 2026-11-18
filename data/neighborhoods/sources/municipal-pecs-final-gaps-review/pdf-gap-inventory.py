#!/usr/bin/env python3
from pathlib import Path
import fitz,re,json,hashlib,unicodedata,argparse
P=Path(__file__).resolve().parent;ROOT=P.parents[3];PDF=ROOT/'.local/neighborhoods/nationwide-docs/originals/pecs-its.pdf'
def enc(x):return json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
def norm(s):return ''.join(c for c in unicodedata.normalize('NFD',s.lower())if not unicodedata.combining(c))
patterns={'Murom':r'\bmurom\w*','Köztemető':r'\bkoztemeto\w*','Kisbalokány':r'\bkisbalokany\w*','Siklósi külváros':r'\bsiklosi\s+kulvaros\w*','Árpádtető':r'\barpadteto\w*','Petőfi-akna':r'\bpetofi[- –—]?akna\w*','M utca':r'\bm\.?\s+(?:utca|u\.)'}
reasons={
'Murom':'Page55 locates the Muromi garden zone between Pecs and Pecs-Somogy; page191 identifies segregation risk. Neither is a closed street circuit. No-data hatching is thematic graphics, not several named fine units. Direct original Figure9 or full outer-stroke interpretation remains a separate task.',
'Köztemető':'Lists and statistical tables establish the separate named unit. Page133 describes cemetery modernization/internal paths; the southern-group narrative is broader. These do not delimit the complete fine neighbourhood. No-data hatching must not be exported as constituent half-cells.',
'Kisbalokány':'Positive map finding: actual closed Figure12 cell89 at visible thin eastern interior[530,520] is separate from92. The former projected label-start was not a reliable interior. In Figures13–15 its thin wedge is hatched as the tables specify n.a.-adatvedelem. Development/connections text at44/87/97/125/267 is not a closed street circuit. Literal Figure9/name-shape approval belongs to a separate peer review.',
'Siklósi külváros':'Positive map finding: actual closed Figure12 cell92 at[480,550] is the long southwestern body. The3.46 age value,63.8 active percentage and32.6 diploma percentage match its Figure13/14/15 fills while the thin eastern Kisbalokany wedge remains no-data. Page87 is functional planning narrative, not a complete street circuit. Literal Figure9/name-shape approval is separate.',
'Árpádtető':'Page55 gives forestry-related development,73/100 discuss Mecsextrém,149 a cycle route to Zobakpuszta/Hosszuheteny. No matched passage supplies the complete fine-area street circuit. The demographic island has no-data graphics; separate direct Figure9 silhouette review is needed.',
'Petőfi-akna':'Page55 lists a mining-created settlement;100 describes the former Vasas mine property as a mini industrial park. Mine-property use does not automatically delimit the entire fine named area. No complete street circuit was found; direct Figure9 silhouette review remains separate.',
'M utca':'Only the fine-name lists11/48 and mining/segregation discussion55 were found, including M. utca spelling. A street name or segregation mention is not a closed neighbourhood circuit. Exact tiny Figure9 silhouette tracing is a separate source-pixel review; this text pass does not approve or reject that trace.'}
def build():
 doc=fitz.open(PDF);digest=hashlib.sha256(PDF.read_bytes()).hexdigest();assert digest=='995d0db03e454a34046b248526e0882aee26ffbf40ba916e996afa4c8b49f6b1';assert len(doc)==316;blocks={n:[]for n in patterns}
 for i,page in enumerate(doc):
  for b in page.get_text('blocks'):
   text=' '.join(b[4].split());nt=norm(text)
   for n,pat in patterns.items():
    if re.search(pat,nt):blocks[n].append({'pdfPageOneBased':i+1,'blockIndex':int(b[5]),'blockBboxPoints':[float(x)for x in b[:4]],'text':text,'hasBoundaryVocabulary':bool(re.search(r'hatar|hatarol|torkolat|korulhatar',nt)),'hasStreetVocabulary':bool(re.search(r'\butca\b|\but\b|\bter\b|\bsetany\b',nt))})
 sourceblocks={'sourcePdfSha256':digest,'all316TextPagesSearched':True,'normalization':'NFD lowercase without diacritics; whitespace collapsed; inflected names and M./M street variants included.','patterns':patterns,'records':blocks}
 maps=json.loads((P/'additional-demographic-map-images.json').read_text());maprecords=[]
 for r in maps:
  if r['figureNumber']==9:continue
  for im in r['images']:
   if 'path'in im:maprecords.append({'pdfPageOneBased':r['pdfPageOneBased'],'figureNumber':r['figureNumber'],**im})
 rows=[{'sourceName':n,'pdfNameHitPages':sorted({r['pdfPageOneBased']for r in blocks[n]}),'textualClosedStreetCircuitFound':False,'boundedFinding':reasons[n],'sourceBlockEvidence':'pdf-name-source-blocks.json','newGeographicGeometryCreatedByThisReview':0}for n in patterns]
 report={'schemaVersion':1,'reviewDate':'2026-11-14','reviewer':'Independent remaining_pixel_audit agent','scope':'Bounded local full-PDF evidence inventory for seven previously missing Pecs fine units. No geographic geometry, source repair, clipping or registry writes.','sourcePdfPath':str(PDF.relative_to(ROOT)),'sourcePdfSha256':digest,'pdfPageCount':316,'fullExtractedPdfTextSearched':True,'rasterizedMapTextOcrSearched':False,'recognizedFineThematicMapImages':maprecords,'mapCanvasFinding':'Figures12–15 all have1341x946 canvases but differ in footprint placement; direct coordinate reuse is invalid. Seven visually matched central I junction/source-pixel pairs support local12-to13 delta[-8,-8], without fitting or geographic accuracy approval.','localImagePairEvidence':'figure12-13-image-pair-control-evidence.json','centralCellFinding':'Two distinct original Figure12 closed free cells89/92 already exist. Separate peer literal name/shape review is required. Alternate-map registration may therefore be unnecessary for production; other themes provide corroborating stroke/fill evidence only.','centralRawPixelEvidence':'central-cells-raw-pixel-evidence.json','sameMaskProbeScope':'additional-figures-same-mask-probe.json is a search diagnostic. The frozen colour/ridge formula fragments some different-colour/hatched fills in other themes. No additional Figure13/14/15 source cell is approved by this probe.','sourceStatisticalCrossCheck':{'densityPdf61Table10':{'Siklósi külváros':'3964/km2','Kisbalokány':'3000/km2','meaning':'Same Figure12 colour class2712.40–4512.90; shared fill does not imply a shared fine unit.'},'agePdf64Table11':{'Siklósi külváros':'3.46','Kisbalokány':'n.a.-adatvédelem'},'activePdf66Table12':{'Siklósi külváros':'63.8%','Kisbalokány':'n.a.-adatvédelem'},'diplomaPdf68Table13':{'Siklósi külváros':'32.6%','Kisbalokány':'n.a.-adatvédelem'}},'perNameReview':rows,'interpretationLimits':['Matched text sections did not yield a complete fine-unit street circuit. This is a bounded negative result, not proof about every external or image-only source.','Group descriptions, project streets, mine/cemetery infrastructure and thematic no-data hatching do not define whole fine boundaries.','An eventual contour must follow actual original source pixels/free cells and pass separate name, topology and all60-cohort overlap QA. No mask-complement, subtraction, intersection or arbitrary closing shortcut is authorized.'],'networkUsed':False,'oldFrozenSourcesChanged':False,'globalRegistriesOrExportsChanged':False,'newGeographicGeometryCreated':0,'geographicRegistrationEvaluated':False,'claimedAbsoluteAccuracy':None}
 return {'pdf-name-source-blocks.json':sourceblocks,'pdf-bounded-seven-gap-review.json':report}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args()
 for n,d in build().items():
  text=enc(d)
  if a.check:assert(P/n).read_text()==text,n
  else:(P/n).write_text(text)
 print('Bounded full-PDF seven-name inventory: PASS'+(' readback'if a.check else''))
