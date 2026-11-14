#!/usr/bin/env python3
"""Quick documented map estimates under the 2026-11-14 throughput policy.

Run with PYTHONPATH=/workspace/ingatlan/.local/geodata python3 this-file.
These are approximate search areas, not surveyed/legal boundaries.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString, Polygon, box, mapping, shape
from shapely.ops import split

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
SOURCES = ROOT / 'data/neighborhoods/sources'
URL = 'https://kecskemet.hu/uploaded_files/files/document/2022-11/126_2021._%28XII.16%29_hatarozat_1._melleklete_II-es_kotet.pdf'
DEB_URL = 'https://hbmo.hu/portal/wp-content/uploads/2023/12/01A_eloterj.mell_DMJV-FVS-2021-27-megalapozo-vizsgalat.pdf'


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def read(path):
    return json.loads(path.read_text())


def ring(points):
    points = list(points)
    return points if points[0] == points[-1] else points + [points[0]]


def feature(name, municipality, geometry, method, source_path, **extra):
    assert geometry.is_valid and not geometry.is_empty, (name, geometry.is_valid)
    assert geometry.geom_type in ['Polygon', 'MultiPolygon'], name
    return {'type': 'Feature', 'id': 'additional:' + municipality + ':' + name,
            'geometry': mapping(geometry), 'properties': {
                'name': name, 'municipality': municipality, 'municipalityId': 'city:' + municipality,
                'method': method, 'estimated': method != 'source_polygon',
                'boundaryKind': 'named_urban_area', 'usableForApproximateFiltering': True,
                'accuracy': 'Approximate source-based search boundary; exact ground accuracy unmeasured.',
                'source': {'path': source_path,
                           'url': DEB_URL if municipality == 'Debrecen' else URL}, **extra}}


def main():
    features = []
    # Original municipal raster map. Józsa's approximate image bounding box is
    # paired with the existing service polygon's bbox; the red division is visible.
    # We retain the parent source footprint and split it along an estimated line.
    deb_root = SOURCES / 'municipal-debrecen-remaining-next'
    deb = read(deb_root / 'debrecen-source-service.geojson')
    jozsa = shape(deb['features'][38]['geometry'])
    x0, y0, x1, y1 = jozsa.bounds
    def deb_world(x, y):
        return [x0 + (x - 1694) / (1873 - 1694) * (x1 - x0),
                y1 - (y - 84) / (159 - 84) * (y1 - y0)]
    # Red map line from approximately (1774,108) to (1795,138), extended.
    divider = LineString([deb_world(1700, 2.285714), deb_world(1900, 288)])
    parts = sorted(split(jozsa, divider).geoms, key=lambda g: g.centroid.x)
    assert len(parts) == 2
    map_path = str((deb_root / 'debrecen-fvs-p208-original.png').relative_to(ROOT))
    for name, poly in [('Felsőjózsa', parts[0]), ('Alsójózsa', parts[1])]:
        features.append(feature(name, 'Debrecen', poly, 'map_inferred', map_path,
            approximationNote='Existing Józsa source polygon split along the red boundary visible on the municipal map. '
                              'Manual bbox registration and straight-line continuation are deliberately approximate.',
            parentName='Józsa', mapPage=208))
    nw_pixels = ring([[1652,171],[1690,168],[1734,236],[1631,240],[1637,207],[1652,199]])
    features.append(feature('Észak-Nyugati Gazdasági Övezet', 'Debrecen',
        Polygon([deb_world(*p) for p in nw_pixels]), 'map_inferred', map_path,
        sourceMapPixelRing=nw_pixels, mapPage=208,
        approximationNote='Coarse hand trace of the clearly labelled pink area79. Image registration inherits '
                          'the Józsa source bbox; topological overlaps with adjacent zones are intentionally allowed.'))
    cemetery_path = OUT / 'debrecen-koztemeto-osm-source.geojson'
    cemetery = read(cemetery_path)['features'][0]
    f = feature('Köztemető', 'Debrecen', shape(cemetery['geometry']), 'source_polygon',
                str(cemetery_path.relative_to(ROOT)), aliases=['Debreceni Köztemető', 'Nagyerdei temető'],
                approximationNote='Actual cemetery landuse footprint used for the identically located municipal Köztemető search area.')
    f['properties']['source'] = {'provider':'openstreetmap', 'path':str(cemetery_path.relative_to(ROOT)),
        'url':'https://www.openstreetmap.org/relation/3311677', 'sourceId':'osm:relation:3311677',
        'pbfSha256':'224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a',
        'license':'ODbL-1.0', 'attribution':'© OpenStreetMap contributors', 'geometryUnmodified':True}
    features.append(f)

    # Kecskemét: coarse hand traces of previously withheld named cells in already
    # archived maps. Existing geographic fits are reused directly; occlusions and
    # clipped map tips are closed by short estimated segments, as authorized.
    trace74 = {
      'Ceglédi út': [[420,30],[459,45],[468,76],[530,135],[570,210],[553,223],[508,194],[491,218],[471,208],[442,286],[430,306],[418,312],[452,333],[437,348],[432,345],[421,365],[424,370],[407,391],[420,403],[385,450],[355,520],[341,532],[346,537],[342,555],[392,581],[351,632],[329,615],[320,624],[314,617],[292,659],[280,660],[237,734],[214,785],[207,785],[207,847],[217,850],[226,837],[260,852],[268,842],[279,846],[309,886],[293,911],[254,948],[237,999],[200,1014],[179,971],[155,900],[147,835],[148,776],[158,722],[191,610],[229,490],[260,397],[296,297],[329,208],[358,131],[389,63]],
      'Vasútipark': [[200,1014],[149,1060],[185,1139],[228,1225],[266,1295],[304,1321],[369,1256],[337,1208],[304,1152],[265,1092],[237,1045]],
      'Békéscsabai úti gazdasági övezet': [[461,1179],[503,1107],[542,1047],[585,997],[596,999],[650,1033],[710,1071],[776,1119],[802,1150],[810,1171],[799,1205],[752,1194],[689,1178],[636,1164],[593,1155],[567,1159],[513,1171]],
    }
    trace75 = {
      'Külső Rákócziváros': [[150,184],[209,124],[418,477],[417,490],[321,457],[231,422],[243,394],[241,375],[200,289]],
      'Szolnokihegy': [[209,124],[250,85],[292,59],[324,44],[401,21],[448,18],[529,34],[662,78],[680,37],[694,41],[735,6],[761,15],[743,46],[770,63],[780,51],[794,66],[786,81],[803,94],[792,109],[816,118],[824,96],[842,103],[861,69],[841,47],[859,32],[879,40],[890,59],[911,47],[960,75],[971,96],[1010,125],[1008,134],[1024,141],[1030,132],[1044,143],[1035,164],[1057,168],[1063,134],[1093,149],[1103,141],[1108,187],[1367,184],[1367,250],[1462,251],[1407,315],[1371,372],[1340,447],[1300,447],[1249,481],[1194,520],[1176,474],[1157,433],[1137,428],[1126,414],[1092,504],[1061,586],[1035,646],[1008,689],[957,718],[882,741],[798,764],[733,783],[690,783],[650,773],[615,754],[589,724],[541,664],[496,597],[457,538],[418,477]],
      'Kisfái gazdasági övezet': [[1503,180],[1562,175],[1559,201],[1571,215],[1561,239],[1646,282],[1607,373],[1568,441],[1614,464],[1593,512],[1625,532],[1338,615],[1335,558],[1336,491],[1340,447],[1371,372],[1407,315],[1462,251],[1488,218]],
      'Parasztfőiskola gazdasági övezet': [[589,724],[615,754],[650,773],[690,783],[733,783],[798,764],[882,741],[957,718],[1008,689],[1035,646],[1061,586],[1092,504],[1126,414],[1137,428],[1157,433],[1176,474],[1194,520],[1249,481],[1300,447],[1340,447],[1336,491],[1335,558],[1338,615],[1332,695],[1318,752],[1295,833],[1260,912],[1223,982],[1178,1031],[1126,1072],[1062,1107],[985,1131],[910,1152],[824,1175],[753,1193],[710,1067],[675,951],[637,852]],
    }
    trace81 = {
      'Külső-Máriahegy': [[173,0],[128,68],[201,142],[128,236],[442,480],[482,450],[525,381],[570,311],[600,265],[630,240],[650,218],[662,194],[652,198],[558,164],[465,129],[371,96],[274,62],[183,29]],
      'Villanegyed': [[1066,536],[1171,624],[1170,653],[1161,695],[1149,736],[1132,775],[1128,783],[1115,810],[1105,834],[1100,850],[1096,870],[1092,887],[1057,859],[1016,831],[985,812],[962,798],[984,773],[1005,747],[1023,716],[1021,657],[1036,639],[1020,618],[1003,600]],
    }
    to_wgs = Transformer.from_crs(23700, 4326, always_xy=True)
    source_specs = [
      (74, trace74, 'municipal-kecskemet-figure74-first', 'figure74-p154-xref176.jpeg', 'composedFigure74PixelToEovRows'),
      (75, trace75, 'municipal-kecskemet-figure75-first', 'figure75-p158-xref180.jpeg', 'composedFigure75PixelToEovRows'),
      (81, trace81, 'municipal-kecskemet-fig81', 'page175-xref216.jpeg', 'matrixSourcePixelRowToEov'),
    ]
    specifications = []
    for figure, traces, directory, image_name, matrix_key in source_specs:
        source_root = SOURCES / directory
        registration_path = source_root / ('raster-georeference.json' if figure == 81 else 'georeference.json')
        registration = read(registration_path)
        matrix = np.array(registration[matrix_key])
        for name, points in traces.items():
            pixels = ring(points)
            xy = np.c_[np.array(pixels), np.ones(len(pixels))] @ matrix
            lon, lat = to_wgs.transform(xy[:,0], xy[:,1])
            geo = Polygon(np.c_[lon,lat])
            f = feature(name, 'Kecskemét', geo, 'map_inferred', str((source_root/image_name).relative_to(ROOT)),
                sourceMapPixelRing=pixels, sourceFigure=figure,
                georeferencePath=str(registration_path.relative_to(ROOT)),
                approximationNote='Coarse hand trace of the labelled municipal-map cell, reusing the existing affine '
                                  'map registration. Small obscured/clipped portions are joined by approximate straight '
                                  'segments; no point-circle fallback. Boundary is suitable as an approximate search area.')
            features.append(f)
            specifications.append({'name':name, 'figure':figure, 'sourceImage':str((source_root/image_name).relative_to(ROOT)),
                                   'registrationPath':str(registration_path.relative_to(ROOT)), 'pixelRing':pixels})
    save(OUT/'additional-trace-specifications.json', {'debrecenRegistration': {'sourceMapBboxPixels':[1694,84,1873,159],
        'sourceJozsaBboxWgs84':[x0,y0,x1,y1], 'splitControlPixels':[[1774,108],[1795,138]],
        'northWestZonePixelRing':nw_pixels}, 'kecskemetTraces':specifications})
    payload = {'type':'FeatureCollection', 'coordinateReferenceSystem':'EPSG:4326', 'features':features}
    save(OUT/'additional-features.geojson', payload)
    save(OUT/'additional-summary.json', {'schemaVersion':1, 'featureCount':len(features),
        'municipalities': {city: [f['properties']['name'] for f in features if f['properties']['municipality']==city]
                           for city in ['Debrecen','Kecskemét']},
        'sourcePolygonCount':sum(f['properties']['method']=='source_polygon' for f in features),
        'mapInferredCount':sum(f['properties']['method']=='map_inferred' for f in features),
        'circleFallbackCount':0, 'allValid':True,
        'outputSha256':hashlib.sha256((OUT/'additional-features.geojson').read_bytes()).hexdigest(),
        'scope':'Useful named alternate subdivisions retained; overlaps allowed. Existing historical layers unchanged.',
        'notSurveyed':True, 'noNationalCompletenessClaim':True})
    print(json.dumps({'features':len(features),'valid':all(shape(f['geometry']).is_valid for f in features)},ensure_ascii=False))


if __name__ == '__main__':
    main()
