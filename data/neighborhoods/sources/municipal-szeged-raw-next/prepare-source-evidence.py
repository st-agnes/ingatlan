"""Retain selected map graphics and factual keys only; full publications stay local."""
from pathlib import Path
import argparse,hashlib,json
import fitz,numpy as np
from PIL import Image
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
RAW=ROOT/'.local/neighborhoods/quarter-map-batch';SCRATCH=ROOT/'.local/neighborhoods/szeged-raw-review'
SOURCES=[('henits2013','szeged-henits-ksh-map-2013.pdf','b490214f9f038afe38fb1c74e24c0d5b99aeb04e54f192c417b06018363b3d0f','https://doktori.bibl.u-szeged.hu/id/eprint/1759/1/doktori_HL.pdf'),('ksh2014','ksh-szeged-map-2014.pdf','9a61caa7d022e0d623bd78f21ce8d8953fa7e47f49ba48be5c18b13c44286995','https://www.ksh.hu/docs/hun/xftp/idoszaki/pdf/muhelytanulmanyok4.pdf'),('kleb2007','klebelsberg-history-2007.pdf','aa6b8466ea597f604691f6b4def6104b68e000a6348cb85c1f2ec47e33d136f3','https://www.klebelsberg-egyesulet.hu/wp-content/uploads/2016/04/helytortenet.pdf')]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def enc(x):return json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
pa=argparse.ArgumentParser();pa.add_argument('--check',action='store_true');a=pa.parse_args()
docs={}
for key,name,h,url in SOURCES:
 assert sha(RAW/name)==h;docs[key]=fitz.open(RAW/name)
H=docs['henits2013'];K=docs['ksh2014'];B=docs['kleb2007']
assert len(H)==119 and len(K)==89
im=H.extract_image(249);assert im['width']==1174 and im['height']==1018
assert any(z[0]==249 for z in H[23].get_images())
name='henits-p24-xref249.jpeg'
if a.check:assert (P/name).read_bytes()==im['image']
else:(P/name).write_bytes(im['image'])
# Restore local exact input needed by trace script if the scratch environment was reset.
local=SCRATCH/'henits2013/p24-xref249.jpeg';local.parent.mkdir(parents=True,exist_ok=True)
if not local.exists() and not a.check:local.write_bytes(im['image'])
assert local.read_bytes()==im['image']
# Native KSH graphic was embedded as five unscaled JPEG strips. Concatenate in
# page order, then apply a90degree viewing rotation; do not resample any pixel.
strips=[]
for xref in [159,160,161,162,163]:
 assert any(z[0]==xref for z in K[53].get_images());data=K.extract_image(xref);assert [data['width'],data['height']]==[914,278]
 pix=fitz.Pixmap(data['image']);strips.append(Image.frombytes('RGB',[pix.width,pix.height],pix.samples))
assembled=Image.new('RGB',(914,1390))
for i,strip in enumerate(strips):assembled.paste(strip,(0,i*278))
rotated=assembled.transpose(Image.Transpose.ROTATE_270);mapname='ksh-p54-map-assembled.png'
if a.check:assert np.array_equal(np.array(Image.open(P/mapname).convert('RGB')),np.array(rotated))
else:rotated.save(P/mapname)
# Read the full local text only to validate the small factual key. No narrative
# strings or narrative page images are retained in the public packet.
body25=H[24].get_text();body26=H[25].get_text()
assert all(s in body25+body26 for s in ['Klebersberg-telep','Kecskés','Odessza','Marostő'])
assert 'Klebelsberg' in K[52].get_text() and 'Klebelsberg-telep' in B[8].get_text()
pdfname='source-map-only.pdf'
if a.check:
 d=fitz.open(P/pdfname);assert len(d)==2 and not any(p.get_text().strip() for p in d)
 assert d.embfile_count()==0
 for p in d:assert not p.get_links() and not list(p.annots() or []) and not list(p.widgets() or [])
 first=d.extract_image(d[0].get_images()[0][0])['image'];assert first==im['image']
else:
 d=fitz.open()
 for filename in [name,mapname]:
  picture=Image.open(P/filename);page=d.new_page(width=picture.width,height=picture.height);page.insert_image(page.rect,filename=str(P/filename))
 d.save(P/pdfname,garbage=4,deflate=True,no_new_id=True)
for key in ['henits','ksh']:
 src=SCRATCH/f'{key}-six-junction-control-crop-working.png';target=P/f'{key}-road-junction-source-crop.png'
 if a.check:assert target.read_bytes()==src.read_bytes()
 else:target.write_bytes(src.read_bytes())
trace=SCRATCH/'henits2013/five-traces'
for number in [19,20,28,11]:
 src=trace/f'unit{number}-black60-overlay.png';dst=P/f'source-unit{number}-contour-preview.png'
 if a.check:assert dst.read_bytes()==src.read_bytes()
 else:dst.write_bytes(src.read_bytes())
source_facts={'schemaVersion':1,'sources':[{'id':key,'url':url,'localOriginal':str((RAW/name).relative_to(ROOT)),'sha256':h,'fullRawOriginalStaysLocal':True} for key,name,h,url in SOURCES],'selectedMaps':[{'path':'henits-p24-xref249.jpeg','sha256':sha(P/'henits-p24-xref249.jpeg'),'pdfPageOneBased':24,'printedPage':23,'figure':'3.2','xref':249,'dimensionsPixels':[1174,1018],'processing':'Bit-exact original native JPEG; no interpolation.'},{'path':mapname,'sha256':sha(P/mapname),'pdfPageOneBased':54,'printedPage':53,'figure':1,'originalImageXrefs':[159,160,161,162,163],'processing':'Exact decoded-pixel concatenation of five native914x278strips in page order, then90degree clockwise rotation; no resampling.','dimensionsPixels':[1390,914],'role':'Companion for physical road-junction identification and source-schema comparison only.'}],'mapOnlyPdf':{'path':pdfname,'sha256':sha(P/pdfname),'mapPages':2,'sourceNarrativeTextObjects':0},'bibliographicFacts':{'henits2013':{'author':'Henits László','year':2013,'title':'Szubpixel-alapú osztályozás alkalmazása a városi felszínborítás és területhasználat elemzésében','type':'University doctoral dissertation','upstreamMap':'KSH2003; original boundary delineation/survey date not established'},'ksh2014':{'author':'Rácz Attila','year':2014,'title':'Szegregáció a fejekben','publisher':'KSH','upstreamMap':'Kovács2003'},'kleb2007':{'editor':'Újvári Edit','year':2007,'title':'Szeged-Klebelsberg-telep története','isbn':'978-963-06-2610-1','role':'Correct place-name spelling and historical alias/perimeter context only, not a copied geometric circuit.'}},'nameKeyFacts':[{'sourceUnit':19,'nameAsPrinted':'Klebersberg-telep','candidateName':'Klebelsberg-telep','bodyPdfPageOneBased':26,'bodyPrintedPage':25,'normalization':'Explicit spelling correction supported by correct Klebelsberg name in KSH2014 PDF53 and local2007history PDF9; current OSM Klebelsbergtelep is a punctuation variant. Distinct southern Hattyas point is not merged.'},{'sourceUnit':20,'nameAsPrinted':'Kecskés-telep','candidateName':'Kecskés-telep','bodyPdfPageOneBased':25,'bodyPrintedPage':24,'currentEvidence':'OSM Kecskés István-telep explicitly lists Kecskés-telep in loc_name.'},{'sourceUnit':28,'nameAsPrinted':'Odessza','candidateName':'Odessza','bodyPdfPageOneBased':25,'bodyPrintedPage':24},{'sourceUnit':11,'nameAsPrinted':'Marostő','candidateName':'Marostő','bodyPdfPageOneBased':25,'bodyPrintedPage':24}],'scopeFacts':['Black individual numbered contours are fine named areas within nine functional color groups; functional colors are not whole-neighborhood identifiers.','The admitted four are historical source-map extents; equality with a present whole-quarter boundary or the2007 natural-perimeter description has not been established.','Tarján source-version identity and Felsőváros planning/name conflict remain outside this cohort.','KSH/Henits numbering32/34 and conflicting Bodomi27 references are not silently reconciled.','Újszőreg27 has an explicit source key but its label occludes its narrow map perimeter; no polygon is emitted.'],'contentMinimization':{'verbatimNarrativeQuotationWords':0,'fullNarrativeParagraphsOrPagesRetained':False,'onlySelectedMapGraphicsGeographicLabelsBibliographyAndParaphrasedFacts':True}}
content=enc(source_facts);target=P/'source-page-facts.json'
if a.check:assert target.read_text()==content
else:target.write_text(content)
print(json.dumps({'check':a.check,'mapOnlyPages':2,'sourceContours':4,'verbatimNarrativeQuotationWords':0}))
