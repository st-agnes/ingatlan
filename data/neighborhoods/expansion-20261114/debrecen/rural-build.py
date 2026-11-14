#!/usr/bin/env python3
"""Coarse Kecskemét rural-part map outlines; deliberately approximate."""
from pathlib import Path
import hashlib,json
import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation,binary_fill_holes,label
from shapely.geometry import box, mapping
from shapely.ops import unary_union,transform
from pyproj import Transformer

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
URL='https://kecskemet.hu/uploaded_files/files/document/2022-11/126_2021._%28XII.16%29_hatarozat_1._melleklete_II-es_kotet.pdf'
WHITE_SEEDS={
 'Méntelek':[275,90], 'Talfája':[510,104], 'Külsőnyír':[178,151],
 'Belsőnyír':[334,180], 'Budaihegy':[490,207], 'Vacsihegy':[525,196],
 'Északi logisztikai övezet':[464,185], 'Úrrét':[650,184], 'Borbás':[811,250],
 'Kisfái':[711,288], 'Törökfái':[503,480], 'Matkó':[480,615],
 'Úrihegy':[356,264], 'Szarkás':[295,290],
}
ORANGE_SEEDS={'Hetényegyháza':[289,219],'Kadafalva':[349,385],
              'Katonatelep':[593,126],'Halasi úti kiskertek':[487,425]}
CONTROL_PIXELS={'Méntelek':[279,62],'Talfája':[422,115],'Katonatelep':[593,126],
                'Hetényegyháza':[289,219],'Borbás':[738,214],'Matkó':[496,568],'Kadafalva':[349,385]}

def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

def polygon(mask):
    # Compress each filled row into runs, then union pixel cells. Text/village
    # islands within a broader rural part are filled before contour extraction.
    mask=binary_fill_holes(mask)
    runs=[]
    for y,row in enumerate(mask):
        starts=np.flatnonzero(np.diff(np.r_[False,row,False].astype(int))==1)
        ends=np.flatnonzero(np.diff(np.r_[False,row,False].astype(int))==-1)
        runs.extend(box(int(a),y,int(b),y+1)for a,b in zip(starts,ends))
    return unary_union(runs).simplify(1.5,preserve_topology=True)

def pick(L,x,y):
    xx,yy=round(x*1.277),round(y*1.277)
    near=L[yy-10:yy+11,xx-10:xx+11]
    u,c=np.unique(near[near>0],return_counts=True)
    return int(u[np.argmax(c)])

def main():
    original=OUT/'figure71-p138-xref164.png'
    image=np.array(Image.open(original).convert('RGB'))
    white_labels,_=label(~binary_dilation(image.min(axis=2)<240,iterations=1))
    orange=(image[:,:,0]>200)&(image[:,:,1]>60)&(image[:,:,1]<200)&(image[:,:,2]<100)
    orange_labels,_=label(orange)
    controls=json.loads((OUT/'rural-control-points.json').read_text())
    # A second identically named Talfája point denotes a different map position;
    # the northern built-up marker shown in this map is node984232820.
    controls=[c for c in controls if c['id']!='osm:node:9341026794']
    eov=Transformer.from_crs(4326,23700,always_xy=True)
    wgs=Transformer.from_crs(23700,4326,always_xy=True)
    X=np.array([[*CONTROL_PIXELS[c['name']],1]for c in controls])
    Y=np.array([eov.transform(*c['coordinates'])for c in controls])
    A=np.linalg.lstsq(X,Y,rcond=None)[0]
    residuals=np.linalg.norm(X@A-Y,axis=1)
    def world(x,y,z=None):
        xx,yy=np.asarray(x)/1.277,np.asarray(y)/1.277
        east=xx*A[0,0]+yy*A[1,0]+A[2,0]
        north=xx*A[0,1]+yy*A[1,1]+A[2,1]
        return wgs.transform(east,north)
    features=[];audit=[]
    for kind,seeds,L in [('rural_area',WHITE_SEEDS,white_labels),('built_up_area',ORANGE_SEEDS,orange_labels)]:
        used=set()
        for name,(x,y)in seeds.items():
            lab=pick(L,x,y)
            assert lab not in used,(name,lab)
            used.add(lab)
            mask=L==lab
            assert 80<int(mask.sum())<100000,(name,int(mask.sum()))
            pixels=polygon(mask)
            geo=transform(world,pixels)
            assert geo.is_valid and not geo.is_empty,name
            aliases={'Hetényegyháza':['Hetény']}.get(name,[])
            props={'name':name,'municipality':'Kecskemét','municipalityId':'city:Kecskemét',
                   'aliases':aliases,'method':'map_inferred','estimated':True,
                   'boundaryKind':'named_urban_area','areaScope':kind,
                   'usableForApproximateFiltering':True,
                   'accuracy':'Coarse municipal overview-map footprint; 7 manually located built-up-centre controls '
                              'have 17–210m fit residuals. This does not bound the true boundary error.',
                   'approximationNote':'Connected overview-map area selected beside its label. A one-pixel dilation '
                                       'bridges thin boundary gaps, internal text/built-up marker holes are filled, '
                                       'and a 1.5pixel simplification is applied. Map-edge closure of clipped rural '
                                       'parts is an explicit approximation. Overlap with finer urban divisions is allowed.',
                   'source':{'path':str(original.relative_to(ROOT)),'url':URL,'sourceFigure':71,
                             'sourcePdfPage':138,'sourceImageSha256':hashlib.sha256(original.read_bytes()).hexdigest(),
                             'registrationPath':str((OUT/'rural-registration.json').relative_to(ROOT)),
                             'sourcePeriod':'May2021 municipal consultation draft',
                             'rights':'Municipal map reuse licence unestablished; OSM geographical controls ODbL-1.0.'}}
            features.append({'type':'Feature','id':'kecskemet-rural:'+name,'properties':props,'geometry':mapping(geo)})
            audit.append({'name':name,'scope':kind,'labelId':lab,'previewSeed':[x,y],
                          'actualImagePixelCount':int(mask.sum()),'pixelGeometry':mapping(pixels),
                          'sourceImageBorderContact':bool(mask[:5].any()or mask[-5:].any()or mask[:,:5].any()or mask[:,-5:].any())})
    save(OUT/'rural-registration.json',{'schemaVersion':1,'controls':[
        {**c,'manuallyMeasured1000pxPreviewPoint':CONTROL_PIXELS[c['name']],
         'fitResidualMetres':float(r)}for c,r in zip(controls,residuals)],
        'matrixPreviewPixelToEov':A.tolist(),'originalImageSize':[1277,902],
        'sourcePixelToPreviewDivisor':1.277,'absoluteAccuracyClaimed':False,
        'note':'Built-up-centre matching is intentionally rough; no independent current-boundary verification required.'})
    save(OUT/'rural-trace-specifications.json',{'schemaVersion':1,'areas':audit})
    save(OUT/'rural-features.geojson',{'type':'FeatureCollection','features':features})
    save(OUT/'rural-summary.json',{'schemaVersion':1,'featureCount':len(features),
        'names':[f['properties']['name']for f in features],'circleFallbackCount':0,
        'allValid':True,'independentMunicipalitiesNotAdmitted':['Ballószög','Városföld'],
        'remainingUntracedLabels':['Katonatelepi tanyák','Kadafalvi tanyák','Csalánosi erdő','Boldog sor'],
        'nationalCompletenessClaimed':False})
    print(json.dumps({'features':len(features),'allValid':True},ensure_ascii=False))

if __name__=='__main__':main()
