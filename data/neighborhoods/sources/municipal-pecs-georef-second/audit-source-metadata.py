#!/usr/bin/env python3
from pathlib import Path
import fitz,json,hashlib,io,sys
from PIL import Image,ExifTags
P=Path(__file__).resolve().parent;ROOT=P.parents[3];pdf=ROOT/'.local/neighborhoods/nationwide-docs/originals/pecs-its.pdf';doc=fitz.open(pdf)
def sha(b):return hashlib.sha256(b).hexdigest()
assert sha(pdf.read_bytes())=='995d0db03e454a34046b248526e0882aee26ffbf40ba916e996afa4c8b49f6b1'
keys=['/LGIDict','/GPTS','/LPTS','/GCS','/Neatline','/WKT','/Projection','/GEO','/Measure'];hits=[]
for x in range(1,doc.xref_length()):
 s=doc.xref_object(x,compressed=False)
 found=[k for k in keys if k in s]
 if found:hits.append({'xref':x,'keys':found})
pages=[]
for onebased,xref,filename in [(48,616,'pecs-p48-names.jpeg'),(63,642,'pecs-p63-density.jpeg')]:
 p=doc[onebased-1];im=doc.extract_image(xref);raw=im['image'];expected=ROOT/'data/neighborhoods/sources/municipal-pecs-first-inferred'/filename;assert raw==expected.read_bytes();pil=Image.open(io.BytesIO(raw));exif={str(ExifTags.TAGS.get(k,k)):str(v)for k,v in pil.getexif().items()}
 pages.append({'originalPdfPageOneBased':onebased,'pageXref':p.xref,'pageGeospatialKeys':{k:doc.xref_get_key(p.xref,k)for k in ['VP','LGIDict','Measure','PieceInfo','Metadata']},'imageXref':xref,'imageSize':[im['width'],im['height']],'imageSha256':sha(raw),'frozenOriginalJpegBytesEqual':True,'imageExif':exif,'imageInfoNonPixel':{k:str(v)for k,v in pil.info.items()if k in ['dpi','comment','jfif','jfif_unit','jfif_density']}})
out={'schemaVersion':1,'scope':'Local original PDF object dictionaries and exact embedded JPEG metadata; text content and other external authoring files are not inspected by this metadata audit.','originalPdfPath':str(pdf.relative_to(ROOT)),'originalPdfSha256':sha(pdf.read_bytes()),'pdfPages':len(doc),'pdfObjects':doc.xref_length()-1,'searchedObjectDictionaryTokens':keys,'matchingObjects':hits,'sourcePages':pages,'recognizedGeospatialRegistrationFoundInInspectedMetadata':bool(hits),'jpegGpsRegistrationFound':any('GPSInfo'in p['imageExif']for p in pages),'interpretation':'Absence in these dictionaries/EXIF does not prove that no external original GIS/georeferencing data exists. It means the inspected local PDF/JPEG metadata did not provide usable geographic control.','networkUsed':False,'georeferenceModelFitted':False,'claimedAbsoluteAccuracy':None}
s=json.dumps(out,ensure_ascii=False,indent=2)+'\n';target=P/'source-metadata-review.json'
if '--check'in sys.argv:assert target.read_text()==s;print('source metadata exact reproduction: PASS')
else:target.write_text(s);print(json.dumps({'geospatialDictionaryHits':hits,'jpegGpsRegistrationFound':out['jpegGpsRegistrationFound'],'sourceImagesByteExact':True}))
