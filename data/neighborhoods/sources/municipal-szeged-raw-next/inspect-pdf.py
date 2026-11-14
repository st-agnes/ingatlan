"""Inventory incoming Szeged PDFs locally; do not package source narrative pages."""
import argparse,hashlib,json,re,unicodedata
from collections import Counter
from pathlib import Path
import fitz
P=Path(__file__).resolve().parent;ROOT=P.parents[3];SCRATCH=ROOT/'.local/neighborhoods/szeged-raw-review'
NAMES=['Tarján','Tarjánváros','Felsőváros','Felsővárosi lakótelep','Odessza','Klebelsberg','Hattyas','Kecskés','Kálvária','Móraváros','Rókus','Makkosház','Északi városrész','Petőfitelep','Fodor-kert','Újszeged','Baktó','Alsóváros','Tápé','Szentmihály','Szőreg','Gyálarét','Béketelep']
WORDS=['városrész','városrészek','lakótelep','területi','határ','határol','lehatárol','térkép','áttekintő','akcióterület','övezet','körzet']
def norm(s):return ''.join(c for c in unicodedata.normalize('NFD',s.casefold()) if not unicodedata.combining(c))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as stream:
  for chunk in iter(lambda:stream.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
def enc(x):return json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
def selected(value):
 out=set()
 for part in value.split(','):
  if not part:continue
  if '-' in part:
   a,b=map(int,part.split('-',1));out.update(range(a,b+1))
  else:out.add(int(part))
 return out
def serial(x):
 if isinstance(x,(fitz.Point,fitz.Rect,fitz.Quad)):return list(x)
 if isinstance(x,dict):return {k:serial(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [serial(v) for v in x]
 return x
pa=argparse.ArgumentParser();pa.add_argument('original',type=Path);pa.add_argument('--id');pa.add_argument('--render',default='');pa.add_argument('--native',default='');pa.add_argument('--vectors',default='');a=pa.parse_args()
original=a.original.resolve();ident=a.id or re.sub('[^a-z0-9]+','-',norm(original.stem)).strip('-');dest=SCRATCH/ident;dest.mkdir(parents=True,exist_ok=True)
with original.open('rb') as stream:magic=stream.read(5)
assert magic==b'%PDF-',f'Not actual PDF bytes: {original.name}'
D=fitz.open(original);assert not D.needs_pass,'Password-gated PDF; not inspected'
rows=[];rawtext=[]
for i,page in enumerate(D):
 text=page.get_text();rawtext.append(f'PDF PAGE {i+1}\n{text}');nt=norm(text)
 names=[n for n in NAMES if norm(n) in nt];words=[n for n in WORDS if norm(n) in nt]
 drawings=page.get_drawings();images=[]
 for im in page.get_images():
  xref=im[0];images.append({'xref':xref,'width':im[2],'height':im[3],'bitsPerComponent':im[4],'colorspace':im[5],'pageRects':[list(r) for r in page.get_image_rects(xref)]})
 fill=sum(d.get('fill') is not None for d in drawings);stroke=sum(d.get('color') is not None for d in drawings)
 large=sum(im['width']>=350 and im['height']>=250 for im in images)
 native_map=bool(len(drawings)>=40 or large)
 bottom_words=[w[4] for w in page.get_text('words') if w[1]>.9*page.rect.height and re.fullmatch(r'\d{1,4}',w[4])]
 score=3*len(names)+2*sum(w in words for w in ['térkép','határ','határol','lehatárol','városrész'])+4*large+min(len(drawings)//40,6)
 if not native_map:score-=5
 rows.append({'pdfPageOneBased':i+1,'sizePoints':[page.rect.width,page.rect.height],'textCharacterCount':len(text),'quarterNamesPresent':names,'mapOrScopeWordsPresent':words,'nativeVectorPathCount':len(drawings),'filledNativePathCount':fill,'strokedNativePathCount':stroke,'imageCount':len(images),'images':images,'printedPageCandidatesAtBottom':bottom_words,'pageViewportMetadata':D.xref_get_key(page.xref,'VP'),'candidateScore':score,'candidateNote':'Automated page ranking only; names/map words do not establish a quarter contour or source identity.'})
(Dest:=dest/'full-text-local-only.txt').write_text('\n\n'.join(rawtext))
(dest/'original-metadata-local-only.json').write_text(enc(D.metadata))
for num in selected(a.render):
 page=D[num-1];page.get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(dest/f'page-{num:04d}.png')
for num in selected(a.native):
 for im in D[num-1].get_images():
  data=D.extract_image(im[0]);(dest/f'p{num}-xref{im[0]}.{data["ext"]}').write_bytes(data['image'])
for num in selected(a.vectors):
 (dest/f'page-{num:04d}-native-paths-local-only.json').write_text(enc(serial(D[num-1].get_drawings())))
source_path=str(original.relative_to(ROOT)) if original.is_relative_to(ROOT) else str(original)
result={'schemaVersion':1,'status':'working_inventory_only_not_a_frozen_geometry_packet','sourceId':ident,'originalPath':source_path,'originalSha256':sha(original),'originalBytes':original.stat().st_size,'pageCount':len(D),'sourceNarrativeRetainedOnlyLocally':str(Dest.relative_to(ROOT)),'candidateRanking':[{'pdfPageOneBased':r['pdfPageOneBased'],'score':r['candidateScore'],'names':r['quarterNamesPresent'],'vectors':r['nativeVectorPathCount'],'largeImages':sum(im['width']>=350 and im['height']>=250 for im in r['images'])} for r in sorted(rows,key=lambda r:(-r['candidateScore'],r['pdfPageOneBased']))[:30]],'pages':rows,'noQuarterGeometryProduced':True,'noMapSemanticsOrPlacementCertified':True,'globalRegistryModified':False}
(dest/'inventory.json').write_text(enc(result));(P/f'{ident}-inventory.json').write_text(enc({k:v for k,v in result.items() if k!='pages'}))
print(enc({'id':ident,'pages':len(D),'sha256':result['originalSha256'],'inventory':str((dest/'inventory.json').relative_to(ROOT)),'topPages':result['candidateRanking'][:12]}))
