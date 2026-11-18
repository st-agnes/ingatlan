#!/usr/bin/env python3
"""Eight quick municipal-map outlines; no radius fallbacks or new downloads."""
from pathlib import Path
import hashlib
import json
import numpy as np
from PIL import Image
from pyproj import Transformer
from shapely.geometry import Polygon, mapping

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
SOURCES = ROOT / 'data/neighborhoods/sources'
URL = 'https://kecskemet.hu/uploaded_files/files/document/2022-11/126_2021._%28XII.16%29_hatarozat_1._melleklete_II-es_kotet.pdf'

TRACES = {
  80: {
    'Arborétum–Kápolnarét': [[381,0],[483,118],[434,170],[407,209],[378,278],[338,335],[111,251],[160,210],[215,163],[275,108],[335,54]],
    'Arborétum lakópark': [[483,118],[535,146],[499,230],[434,170]],
    'Széktói szabadidőközpont': [[535,146],[704,222],[692,245],[681,280],[670,321],[652,379],[627,417],[612,435],[560,420],[502,401],[443,379],[388,356],[338,335],[354,302],[378,278],[407,209],[434,170],[499,230]],
    'Máriaváros': [[639,382],[681,386],[704,365],[731,338],[760,309],[788,268],[900,333],[888,358],[875,382],[884,404],[907,440],[937,468],[859,518],[842,575],[833,556],[812,523],[795,497],[747,450],[716,428],[684,419],[650,424],[612,435],[627,417]],
    'Széktó': [[338,335],[388,356],[443,379],[502,401],[560,420],[612,435],[650,424],[684,419],[716,428],[747,450],[795,497],[771,514],[718,545],[664,577],[606,610],[574,627],[546,644],[504,611],[470,578],[430,534],[398,491],[365,445],[343,416],[320,389],[328,361]],
    'Izsáki út': [[795,497],[812,523],[833,556],[842,575],[812,582],[788,591],[756,612],[719,634],[684,653],[652,680],[630,698],[612,705],[599,701],[588,691],[592,682],[574,627],[606,610],[664,577],[718,545],[771,514]],
  },
  82: {
    'Vacsiköz': [[65,299],[87,256],[134,209],[175,164],[170,150],[187,135],[199,132],[207,139],[246,101],[291,70],[308,61],[311,72],[354,61],[377,41],[396,27],[423,43],[456,61],[489,64],[512,50],[559,51],[588,62],[630,91],[668,115],[694,130],[696,113],[724,115],[743,103],[755,118],[779,88],[796,69],[808,63],[816,79],[805,92],[831,132],[852,163],[843,198],[800,180],[769,165],[738,139],[728,171],[717,205],[709,244],[701,254],[673,240],[666,276],[655,308],[641,351],[631,392],[664,413],[681,376],[722,403],[794,333],[783,378],[774,439],[767,486],[772,542],[776,584],[772,636],[768,694],[735,677],[704,660],[672,643],[641,626],[616,614],[589,593],[577,583],[560,580],[548,585],[539,601],[531,645],[523,687],[501,674],[471,646],[437,615],[401,583],[365,548],[327,515],[287,479],[252,446],[214,412],[177,381],[141,351],[103,323]],
    'Dárdai–Voelkertelep': [[738,139],[769,165],[800,180],[843,198],[794,333],[722,403],[681,376],[664,413],[631,392],[641,351],[655,308],[666,276],[673,240],[701,254],[709,244],[717,205],[728,171]],
  },
}


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    to_wgs = Transformer.from_crs(23700, 4326, always_xy=True)
    features = []
    specs = []
    for number, traces in TRACES.items():
        registration = read(OUT / f'figure{number}-registration.json')
        photo = np.array(registration['sourceToTargetAffineRows'])
        photo_h = np.vstack([photo.T, [0,0,1]])
        if number == 80:
            calibration = read(SOURCES / 'municipal-kecskemet-fig81/raster-georeference.json')
            metric = np.array(calibration['matrixSourcePixelRowToEov'])
            image_name = 'figure80-p171-xref212.jpeg'
        else:
            calibration = read(SOURCES / 'municipal-kecskemet-figure73-first/georeference.json')
            metric = np.array(calibration['affineImagePixelToEovRows'])
            image_name = 'figure82-p178-xref220.jpeg'
        original = OUT / image_name
        w,h = Image.open(original).size
        # Manual guides were measured in a 1000px-wide display preview. The image
        # resize is explicit; all archived source JPEG bytes are unchanged.
        display_scale = w / 1000
        pixel_to_eov = np.linalg.inv(photo_h).T @ metric
        for name, points in traces.items():
            points = points + [points[0]]
            source_pixels = np.array(points) * display_scale
            xy = np.c_[source_pixels, np.ones(len(source_pixels))] @ pixel_to_eov
            lon,lat = to_wgs.transform(xy[:,0],xy[:,1])
            poly = Polygon(np.c_[lon,lat])
            assert poly.is_valid and not poly.is_empty, name
            aliases = {'Széktói szabadidőközpont':['Széktói szabadidőpark'],
                       'Arborétum–Kápolnarét':['Arborétum - Kápolnarét'],
                       'Dárdai–Voelkertelep':['Dárdai-Woelker Telep','Dárdai–Woelker-telep'],
                       'Vacsiköz':['Vacsi-köz']}.get(name,[])
            features.append({'type':'Feature','id':f'kecskemet-map{number}:{name}',
                'geometry':mapping(poly),'properties':{
                    'name':name,'municipality':'Kecskemét','municipalityId':'city:Kecskemét',
                    'aliases':aliases,'method':'map_inferred','estimated':True,
                    'boundaryKind':'named_urban_area','usableForApproximateFiltering':True,
                    'accuracy':'Approximate hand trace; photographic registration inherits existing historical map controls.',
                    'approximationNote':'Coarse visible municipal-map outline; straight segments bridge small label/clip gaps. '
                                        'These estimates replace point-radius fallbacks where a named map area exists. '
                                        'Map edges, dates and alternative district hierarchies may overlap.',
                    'sourceFigure':number,'sourcePeriod':'May 2021 municipal consultation draft',
                    'source':{'path':str(original.relative_to(ROOT)),'url':URL,
                              'sha256':hashlib.sha256(original.read_bytes()).hexdigest(),
                              'georeferencePath':str((OUT/f'figure{number}-registration.json').relative_to(ROOT)),
                              'sourcePdfSha256':'83f78c5dbb85964a1fc4aecb2df014254e1985fdb446d8135182dedad56da939',
                              'rights':'Municipal map reuse licence unestablished; geographic controls use ODbL OpenStreetMap evidence.'}}})
            specs.append({'name':name,'sourceFigure':number,'originalImageSize':[w,h],
                          'manualPreviewWidth':1000,'previewPixelRing':points,
                          'matrixOriginalImagePixelToEov':pixel_to_eov.tolist()})
    save(OUT/'maps80-82-traces.json', {'schemaVersion':1,'traces':specs})
    save(OUT/'maps80-82-features.geojson',{'type':'FeatureCollection','features':features})
    save(OUT/'maps80-82-summary.json',{'schemaVersion':1,'featureCount':len(features),
        'names':[f['properties']['name']for f in features], 'mapInferredCount':len(features),
        'circleFallbackCount':0,'validPolygonCount':len(features),'noNationalCompletenessClaim':True})
    print(json.dumps({'features':len(features),'allValid':True},ensure_ascii=False))


if __name__ == '__main__':
    main()
