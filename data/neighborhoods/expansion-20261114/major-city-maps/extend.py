#!/usr/bin/env python3
"""Additional major-city approximations; does not mutate frozen Győr packet."""
import json,collections
import numpy as np
from pathlib import Path
from pyproj import Transformer
from shapely import make_valid
from shapely.geometry import Polygon,shape
from shapely.ops import transform
import build
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]

def nyiregyhaza():
 src='data/neighborhoods/sources/municipal-nyiregyhaza-fine2008-next/'
 controls=build.read(src+'control-specification.json')['controls']
 fit=[x for x in controls if x['role']=='fit']
 beta=np.linalg.lstsq(np.array([[*x['sourcePixel'],1] for x in fit]),np.array([x['targetEov'] for x in fit]),rcond=None)[0]
 doc=json.loads((HERE/'evidence/nyiregyhaza-rough-native-traces.json').read_text())
 for x in doc['units']:
  def ring(rr):
   return [build.TO_WGS(*xy) for xy in np.c_[np.array(rr),np.ones(len(rr))]@beta]
  world=Polygon(ring(x['ring']),[ring(x['hole'])] if 'hole' in x else [])
  build.put(x['name'],'Nyíregyháza',world,'map_trace_rough',[src+'ksh27-native.jpeg',src+'ivs11-native.jpeg',src+'control-specification.json','data/neighborhoods/expansion-20261114/major-city-maps/evidence/nyiregyhaza-rough-native-traces.json'],[doc['sourcePdfUrl']],sourceYear=2003,documentYear=2008,aliases=x.get('aliases',[]),sourceMapPrintedPage=43,sourceNameTextPages=doc['sourceNameTextPages'],sourceSubdivisionKind='historical_quarter_estimate',approximationNotes=doc['method']+' Existing affine silhouette fit reused; the25 manual rings are coarse and can overlap. No named-point circles.')

if __name__=='__main__':
 nyiregyhaza()
 (HERE/'additional-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':build.FEATURES},ensure_ascii=False,separators=(',',':'))+'\n')
 print(collections.Counter(f['properties']['municipality'] for f in build.FEATURES))
