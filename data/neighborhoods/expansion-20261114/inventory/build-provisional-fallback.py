#!/usr/bin/env python3
"""Separate last-resort options, never automatically registered as mapped boundaries."""
import hashlib
import json
import math
from pathlib import Path

OUT=Path(__file__).resolve().parent
EARTH=6371008.8

def distance(a,b):
    lat1,lat2=map(math.radians,[a[1],b[1]])
    dlat=lat2-lat1; dlon=math.radians(b[0]-a[0])
    h=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 2*EARTH*math.asin(min(1,math.sqrt(h)))

def circle(point,radius):
    lon,lat=map(math.radians,point); d=radius/EARTH; coords=[]
    # Positive lon/lat winding for GeoJSON outer rings.
    for i in range(64):
        bearing=-2*math.pi*i/64
        latitude=math.asin(math.sin(lat)*math.cos(d)+math.cos(lat)*math.sin(d)*math.cos(bearing))
        longitude=lon+math.atan2(math.sin(bearing)*math.sin(d)*math.cos(lat),math.cos(d)-math.sin(lat)*math.sin(latitude))
        coords.append([round(math.degrees(longitude),8),round(math.degrees(latitude),8)])
    coords.append(coords[0])
    return {'type':'Polygon','coordinates':[coords]}

def main():
    src=OUT/'known-names.json'; source_bytes=src.read_bytes(); d=json.loads(source_bytes)
    rows=d['names']; centers={}
    for row in rows:
        if row['pointCandidates']:
            # Deterministic source ID tie break; all alternatives remain recorded.
            centers[(row['municipality'],row['nameKey'])]=sorted(row['pointCandidates'],key=lambda x:x['sourceId'])[0]
    bycity={}
    for (city,name),p in centers.items(): bycity.setdefault(city,[]).append((name,p['coordinates']))
    features=[]
    for row in rows:
        if row['hasCollectedPolygon'] or not row['pointCandidates']: continue
        city,name=row['municipality'],row['nameKey']; p=centers[(city,name)]
        base=600 if p['placeKind']=='suburb' else 300
        others=[distance(p['coordinates'],q) for other,q in bycity[city] if other!=name]
        nearest=min(others) if others else None
        radius=round(max(75,min(base,.45*nearest)) if nearest is not None else base,2)
        identity='provisional-point-radius:'+hashlib.sha256((city+'\0'+name).encode()).hexdigest()[:24]
        props={'id':identity,'municipality':city,'municipalityId':'city:'+city,
          'name':row['name'],'aliases':[n for n in row['sourceNames'] if n!=row['name']],
          'method':'point_radius_fallback','estimated':True,'registeredInDefaultCatalogue':False,
          'radiusMetres':radius,'uncappedRadiusMetres':base,
          'nearestDifferentKnownPointMetres':round(nearest,2) if nearest is not None else None,
          'radiusPolicy':'suburb600m; neighbourhood/quarter300m; cap at45% nearest other known-name center within same municipality, floor75m',
          'sourcePoint':p,'sourcePointAlternatives':row['pointCandidates'],
          'sourceUrl':p['sourceUrl'],'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors',
          'coordinateSystem':'EPSG:4326','coordinateOrder':'longitude,latitude',
          'uncertaintyNote':'Artificial search radius around a named point; no source boundary is implied. No usable named polygon occurs in the collected catalogue inputs at this checkpoint; this does not imply no map or polygon exists elsewhere.',
          'replacementPriority':'Replace with any usable mapped/source polygon or text-derived boundary when found.'}
        features.append({'type':'Feature','id':identity,'properties':props,'geometry':circle(p['coordinates'],radius)})
    counts={}
    for f in features: counts[f['properties']['municipality']]=counts.get(f['properties']['municipality'],0)+1
    body={'type':'FeatureCollection','schemaVersion':1,'status':'optional_provisional_fallback_not_default_catalogue',
      'featureCount':len(features),'completeNationalCoverage':False,'coordinateSystem':'EPSG:4326',
      'coordinateOrder':'longitude,latitude','sourceInventorySha256':hashlib.sha256(source_bytes).hexdigest(),
      'caveat':'These circles are optional last-resort search approximations, not collected neighbourhood outlines. They are excluded from polygon/map coverage statistics and the default search-area registry.',
      'features':features}
    (OUT/'provisional-fallback-features.geojson').write_text(json.dumps(body,ensure_ascii=False,separators=(',',':'))+'\n')
    report={'featureCount':len(features),'municipalityCount':len(counts),'mappedOrSourcePolygonCoverageCredit':False,
      'defaultRegistryEdited':False,'countsByMunicipality':dict(sorted(counts.items())),
      'sourceInventorySha256':hashlib.sha256(source_bytes).hexdigest(),
      'isolatedRuralRadius750mUsed':False,
      'note':'Only OSM suburb/neighbourhood/quarter points are present in this inventory; no unlocated name gets an invented center. Municipal boundaries do not clip these provisional circles. Overlap is intentional.'}
    (OUT/'provisional-fallback-summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='countsByMunicipality'},ensure_ascii=False))

if __name__=='__main__': main()
