"""Offline source-map inspection; does not derive or approve geographic boundaries."""
import hashlib,json
from pathlib import Path
import fitz
ROOT=Path(__file__).resolve().parents[5]
HERE=Path(__file__).resolve().parent
SOURCES=[
 ('pecs-its',47,'https://logoweb.pecs.hu/download/koncepcio/ITS.pdf','41','9. ábra', 'Fine named quarters are visibly drawn within the thirteen planning colors; image is not merely a map of thirteen broad planning units.', 'No geographic polygons admitted: original raster is only 585×514 px; independent well-distributed control identification and boundary accuracy remain unresolved.'),
 ('miskolc-its',253,'https://miskolc.hu/sites/default/files/aktualitas/csatolmanyok/2024-09/megalapozo_vizsgalat_miskolc_mjv_its.pdf','253','74. ábra', 'Seventeen numbered ITS clusters, not the thirty-two underlying KSH quarter units. The linked table explicitly merges units.', 'Raster map884×557px; no vector quarter boundaries present on this page. Requires georeferencing; clusters must not be relabeled as individual fine quarters.'),
 ('salgotarjan-its',124,'https://www.salgotarjan.hu/wp-content/uploads/fejlesztesidokumentumok_20220629_its.pdf','125','III.3-1. ábra', 'Ten ITS units, several explicitly merging multiple local quarters; colored footprints include disconnected components.', 'Raster761×885px; no vector boundaries on map page. A cluster footprint cannot establish separate boundaries of its named constituents.'),
]
def sha(b):return hashlib.sha256(b).hexdigest()
records=[]
for key,index,url,printed,figure,semantic,limits in SOURCES:
 p=ROOT/'.local/neighborhoods/nationwide-docs/originals'/f'{key}.pdf'
 raw=p.read_bytes();d=fitz.open(stream=raw,filetype='pdf');page=d[index]; ims=[]
 for no,im in enumerate(page.get_images()):
  img=d.extract_image(im[0]);name=f'{key}-{index}-original-{no}.{img["ext"]}';(HERE/name).write_bytes(img['image'])
  ims.append({'path':name,'sha256':sha(img['image']),'width':img['width'],'height':img['height'],'pdfImageXref':im[0]})
 records.append({'sourceId':key,'sourceUrl':url,'sourceSha256':sha(raw),'sourceBytes':len(raw),'pdfPageZeroBased':index,'printedPage':printed,'figure':figure,'images':ims,'pageVectorDrawingCount':len(page.get_drawings()),'observedBoundaryMeaning':semantic,'remainingLimits':limits,'sourceReuseRights':'not_established','geometryDerived':False,'usableForAddressAssignment':False})
out={'schemaVersion':1,'inspectedAt':'2026-11-13','method':'Offline PyMuPDF extraction and visual inspection of original source images, not OCR-only interpretation. No generated or assumed boundaries.','records':records,'pecsCorrection':'The prior broad-planning-only characterization of figure9 is incomplete: the raster also visibly includes named fine-quarter edges. This observation establishes source availability, not georeferenced extents.','pecsControlAttempt':{'status':'rejected_not_independently_validated','knownClearControlCandidates':['M60/58 bridge','M60/578 bridge'],'remaining':'Northern/eastern junction matches are not independently resolved; a three-point affine fit has zero training residual by construction and cannot verify accuracy. No geographic polygons exported.'}}
(HERE/'inspection.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'sourcePages':len(records),'images':sum(len(r['images']) for r in records),'geographicPolygonsAdmitted':0}))
