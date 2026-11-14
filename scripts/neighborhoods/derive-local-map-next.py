#!/usr/bin/env python3
"""Reproduce seven closed, individually named Zalaegerszeg raster source areas.

This digitizes the INSIDE EDGE of the original teal cartographic boundary band.
It does not substitute contemporary roads or claim that registration is a survey.
Numeric label disks are removed only when entirely enclosed; no gaps are bridged.
"""
import argparse, hashlib, json, unicodedata
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage
from shapely.geometry import shape, box, mapping
from shapely.ops import unary_union, transform
from pyproj import Transformer, Geod

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/neighborhoods/sources/municipal-local-map-next'
URL='https://zalaegerszeg.hu/wp-content/uploads/2023/05/Zalaegerszeg_ITS.pdf'
SOURCE_PDF_SHA='4534775c49466eba0460e583aa45a12127f0a46cd8c0e768ed689b830e4eb035'
SPECS=[(1,'Belváros',(780,1000),(845,978)),(2,'Ola',(650,910),(695,897)),
 (3,'Landorhegy',(610,1000),(670,1057)),(4,'Páterdomb',(910,1160),(930,1125)),
 (5,'Kertváros',(720,1240),(743,1182)),(7,'Csácsbozsok',(1110,940),(1162,964)),
 (8,'Vorhota',(430,855),(394,825))]
STRICT_QUARANTINE={2:'hole_outside_shell',3:'hole_outside_shell'}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def encode(value):return json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
def norm(value):return ''.join(c for c in unicodedata.normalize('NFD',value.lower()) if c.isalnum())

def pixel_geometry(mask):
    rectangles=[]
    for y in np.flatnonzero(mask.any(axis=1)):
        row=np.r_[False,mask[y],False];edges=np.flatnonzero(row[1:]!=row[:-1])
        rectangles.extend(box(float(x0)-.5,float(y)-.5,float(x1)-.5,float(y)+.5) for x0,x1 in zip(edges[::2],edges[1::2]))
    # Exact set union of actual included raster-cell runs, not a geometry repair.
    result=unary_union(rectangles)
    if result.geom_type!='Polygon' or not result.is_valid:raise ValueError('Source cell region is not a valid single polygon')
    return result

def boundary_blue_test(pixel,blue):
    missing=0;tested=0;h,w=blue.shape
    for ring in [pixel.exterior,*pixel.interiors]:
        cs=list(ring.coords)
        for a,b in zip(cs,cs[1:]):
            length=abs(b[0]-a[0])+abs(b[1]-a[1])
            if length!=int(length) or a[0]!=b[0] and a[1]!=b[1]:raise ValueError('Non-grid source-cell edge')
            for i in range(int(length)):
                x=a[0]+(b[0]-a[0])*(i+.5)/length;y=a[1]+(b[1]-a[1])*(i+.5)/length
                if a[0]==b[0]:neighbors=[(int(x-.5),int(y)),(int(x+.5),int(y))]
                else:neighbors=[(int(x),int(y-.5)),(int(x),int(y+.5))]
                valid=any(0<=xx<w and 0<=yy<h and blue[yy,xx] for xx,yy in neighbors)
                tested+=1;missing+=not valid
    if missing:raise ValueError(f'{missing} source boundary edges lack an adjacent original teal pixel')
    return tested

def build():
    raw=np.array(Image.open(OUT/'zalaegerszeg-p12-image0.jpeg').convert('RGB')).astype(int)
    blue=(raw[:,:,0]<135)&(raw[:,:,1]-raw[:,:,0]>30)&(raw[:,:,2]-raw[:,:,0]>30)&(raw[:,:,1]>65)
    free,count=ndimage.label(~blue)  # Four-neighbor actual non-stroke source pixels.
    reg=json.loads((OUT/'zalaegerszeg-registration.json').read_text());matrix=np.array(reg['matrixPixelToEov'])
    world=Transformer.from_crs(23700,4326,always_xy=True)
    def geographic(x,y,z=None):
        east=x*matrix[0,0]+y*matrix[1,0]+matrix[2,0]
        north=x*matrix[0,1]+y*matrix[1,1]+matrix[2,1]
        return world.transform(east,north)
    parent=shape(json.loads((OUT/'zalaegerszeg-calibration-municipality.geojson').read_text())['geometry'])
    points=json.loads((OUT/'zalaegerszeg-source-name-points.geojson').read_text())['features']
    metric=Transformer.from_crs(4326,23700,always_xy=True).transform
    features=[];proof=[]
    for number,name,seed,label in SPECS:
        cid=int(free[seed[1],seed[0]])
        if cid==0:raise ValueError('Source interior seed falls on a boundary stroke')
        region=free==cid
        if region[0].any() or region[-1].any() or region[:,0].any() or region[:,-1].any():raise ValueError('Open/cropped source region')
        holes=ndimage.binary_fill_holes(region)&~region;hl,_=ndimage.label(holes)
        label_hole=int(hl[label[1],label[0]])
        if not label_hole:raise ValueError(f'{name}: numeric label disk is not enclosed by the selected source interior; do not infer occluded geometry')
        graphic=hl==label_hole
        if not(1500<=graphic.sum()<=4000):raise ValueError('Unexpected source numeric-label disk size')
        filled=region|graphic;pixel=pixel_geometry(filled);edge_count=boundary_blue_test(pixel,blue)
        # Union may drop only exactly collinear grid vertices; its footprint remains the raster cells.
        geo=transform(geographic,pixel)
        if not geo.is_valid:raise ValueError('Invalid transformed source geography')
        matches=[p for p in points if norm(p['properties']['name'])==norm(name)]
        areas=transform(metric,geo);outside=transform(metric,geo.difference(parent)).area
        source_name_evidence=[{'id':p['id'],'name':p['properties']['name'],'coordinates':p['geometry']['coordinates'],
            'insideHistoricalSourceArea':geo.covers(shape(p['geometry'])),
            'distanceFromHistoricalSourceAreaMetres':areas.distance(transform(metric,shape(p['geometry']))),
            'sourceUrl':p['properties']['source']['url']} for p in matches]
        properties={'name':name,'municipality':'Zalaegerszeg','boundaryKind':'neighbourhood',
          'canonicalNameIsNeighborhood':True,'sourceUnitNumber':number,'sourcePeriod':'2014-08-28 ITS; statistical comparability for 2009/2011; original illustration survey date unknown',
          'method':'Original municipal raster source-region digitization at the INSIDE EDGE of the actual teal boundary band. Four-neighbor non-stroke cells are traced; only the fully enclosed numeric label disk is restored. Exact cell-run set union; no gap bridging, point buffers, clipping, current-road replacement, or geometric repair. Frozen affine municipal-perimeter registration to EOV and inverse projection to WGS84.',
          'evidenceUrls':[URL],'sourceDocuments':[{'url':URL,'sha256':SOURCE_PDF_SHA,'pdfPageOneBased':12,'printedPage':12,'figure':1}],
          'estimated':False,'georeferencingIsApproximate':True,'claimedAbsoluteAccuracyMetres':None,
          'sourceDocumentIsOfficialMunicipalPublication':True,
          'sourceIsOfficial':False,'sourceIsHardBoundary':False,'usableForAddressAssignment':False,
          'sourceLabelEvidence':source_name_evidence,'currentNameStatus':'same_city_exact_osm_name_observed' if matches else 'not_independently_confirmed',
          'reviewStatus':'historical_source_raster_review_required','areaM2':abs(Geod(ellps='WGS84').geometry_area_perimeter(geo)[0]),
          'localStrictImportStatus':'quarantined' if number in STRICT_QUARANTINE else 'passes_existing_js_geometry_validator',
          'localStrictQuarantineReason':STRICT_QUARANTINE.get(number),
          'municipalityOverlapFraction':1-outside/areas.area,'outsideCurrentMunicipalityAreaM2':outside,
          'reviewNotes':['This is a cartographic inside-stroke interpretation, not a cadastral/surveyed/current legal boundary.',
            'The source-city outline differs from today on the east; whole-perimeter fit residuals are not independent interior accuracy.',
            'Map-stroke width and unknown source projection/georeferencing create unknown positional uncertainty.',
            'Numerical label disks are cartographic annotation; removing their artificial interior hole does not fill any other source hole.'],
          'license':'Municipal map reuse rights not independently established; ODbL applies to OSM calibration and name evidence.'}
        f={'type':'Feature','id':f'manual:zala-source-raster:{number}','geometry':mapping(geo),'properties':properties};features.append(f)
        proof.append({'name':name,'sourceUnitNumber':number,'interiorSeedPixel':list(seed),'numericLabelCenterPixel':list(label),
          'freeComponentId':cid,'sourceInteriorPixelCount':int(region.sum()),'numericGraphicPixelCount':int(graphic.sum()),
          'originalTealAdjacentBoundaryUnitEdges':edge_count,'missingBoundarySourcePixels':0,
          'pixelCellGeometry':mapping(pixel),'geographicVertexCount':len(geo.exterior.coords),
          'otherSourceGraphicHolesPixels':[{'areaPixels':abs(shape({'type':'Polygon','coordinates':[list(h.coords)]}).area),'bboxPixels':list(h.bounds)} for h in pixel.interiors],
          'geometryValid':geo.is_valid,'geographicCoordinatesAreOsmNodes':False,'currentMunicipalityFullContainment':parent.covers(geo),
          'outsideCurrentMunicipalityAreaM2':outside,'sourceNameEvidence':source_name_evidence})
    for i,f in enumerate(features):
        for other in features[:i]:
            if shape(f['geometry']).intersection(shape(other['geometry'])).area>1e-16:raise ValueError('Source units overlap')
    inputs=[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in [OUT/'zalaegerszeg-p12-image0.jpeg',OUT/'zalaegerszeg-registration.json',OUT/'zalaegerszeg-calibration-municipality.geojson',OUT/'zalaegerszeg-source-name-points.geojson']]
    return {'type':'FeatureCollection','features':features},{'schemaVersion':1,'inputs':inputs,
      'sourcePdfSha256':SOURCE_PDF_SHA,'sourcePdfPageOneBased':12,'sourceEmbeddedImageXref':105,'sourceImageSizePixels':[1663,2360],
      'colorMask':'R<135, G-R>30, B-R>30, G>65; unmodified original JPEG pixels',
      'boundaryInterpretation':'Inside edge of original cartographic stroke; source-cell boundaries are half-integer pixel coordinates adjacent to actual teal pixels. They are not claimed to be source-pixel centers or OSM coordinates.',
      'registration':reg,'records':proof,'otherNumberedUnitsNotExported':'Thin units with numeric disks crossing their boundary require explicit occlusion interpretation; compound groups9/15/16 and outerareas17..20 are not individual fine quarters.',
      'absoluteBoundaryAccuracyMetres':None,'usableForAddressAssignment':False}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    fc,proof=build()
    admitted={'type':'FeatureCollection','features':[f for f in fc['features'] if f['properties']['sourceUnitNumber'] not in STRICT_QUARANTINE]}
    quarantined={'type':'FeatureCollection','features':[f for f in fc['features'] if f['properties']['sourceUnitNumber'] in STRICT_QUARANTINE]}
    outputs={'zalaegerszeg-source-raster.geojson':encode(fc),'zalaegerszeg-import.geojson':encode(admitted),
      'zalaegerszeg-quarantine.geojson':encode(quarantined),'zalaegerszeg-conversion-proof.json':encode(proof)}
    for name,text in outputs.items():
        p=OUT/name
        if args.check:
            if p.read_text()!=text:raise ValueError('Output differs: '+name)
        else:p.write_text(text)
    print(json.dumps({'sourceFeatures':len(fc['features']),'importFeatures':len(admitted['features']),
      'quarantinedFeatures':len(quarantined['features']),'names':[f['properties']['name'] for f in fc['features']],'check':args.check},ensure_ascii=False))
if __name__=='__main__':main()
