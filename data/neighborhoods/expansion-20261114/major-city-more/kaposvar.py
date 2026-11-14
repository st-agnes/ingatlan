#!/usr/bin/env python3
"""Named source-map component extraction and coarse documented parent splits."""
import json,collections
from pathlib import Path
from shapely.geometry import shape,LineString
from shapely.ops import split
import build
HERE=Path(__file__).resolve().parent
SRC='data/neighborhoods/sources/municipal-kaposvar-raster-next/inferred-georeference.geojson'
GROUPS={f['properties']['name']:shape(f['geometry']) for f in build.read(SRC)['features']}
URL='https://kph.kaposvar.hu/data/dl/nagyprojektek/TOP_PLUSZ-1.3.1-21-SO1-2022-00001/J%C3%B3v%C3%A1hagyott%20FVS.pdf'
DEFINITION='data/neighborhoods/sources/municipal-west/kaposvar-boundary-definitions.json'
PROOF=[]
def put(name,g,method,**extra):
 build.put('Kaposvár',name,g,[SRC,DEFINITION], [URL],method,sourceSubdivisionKind='fine_name_within_source_map_group',approximationNotes='Named subarea selected from the already georeferenced municipal source map. Parent units and different historical overlaps remain allowed. No precision/current-boundary verification. '+extra.pop('note',''),**extra)

if __name__=='__main__':
 group='Toponár – Répáspuszta – Fészerlak – Deseda'
 g=GROUPS[group]
 for name,index in [('Toponár',0),('Deseda',1),('Répáspuszta',2),('Fészerlakpuszta',3)]:
  put(name,g.geoms[index],'source_map_component',parentAreaName=group,sourceComponentIndex=index,aliases=['Fészerlak'] if name=='Fészerlakpuszta'else[],note='The four disconnected actual map-colored components are associated by their geographic sector with the four names explicitly printed in the legend. Identity assignment is approximate; no new boundary vertices generated.')
 group='Töröcske – Zselic kertváros';g=GROUPS[group]
 for name,index in [('Zselic-kertváros',0),('Töröcske',1)]:
  put(name,g.geoms[index],'source_map_component',parentAreaName=group,sourceComponentIndex=index,aliases=['Zselic kertváros'] if index==0 else[],note='Actual disconnected northern/southern source components; southern village is Töröcske, northern elongated component is Zselic-kertváros.')
 group='Kecelhegy – Cser';g=GROUPS[group]
 divider=LineString([[17.74,46.351],[17.80,46.351]])
 parts=list(split(g,divider).geoms)
 for name,op in [('Kecelhegy',max),('Cser',min)]:
  p=op(parts,key=lambda x:x.centroid.y)
  put(name,p,'source_map_inferred_divider',parentAreaName=group,estimatedDividerWgs84=list(divider.coords),note='Coarse north/south split of actual outer source-map contour at the approximate transition between the Kecelhegy and Cser sectors. Internal dividing line is expressly estimated, not present as an exact line on the source diagram.')
 group='Donner – Rómahegy';g=GROUPS[group]
 donnerfile='data/neighborhoods/sources/municipal-kaposvar-donner-next/donner-candidate.geojson'
 donner=shape(build.read(donnerfile)['features'][0]['geometry'])
 remaining=g.difference(donner)
 # Keep the largest connected eastern remainder; tiny georeference overlap slivers are not separate named areas.
 if remaining.geom_type=='MultiPolygon':remaining=max(remaining.geoms,key=lambda x:x.area)
 put('Rómahegy',remaining,'source_map_parent_minus_named_neighbor',parentAreaName=group,neighborGeometryPath=donnerfile,note='The municipal text locates Donner west and Rómahegy east of the Zselic-patak. Subtract the already retained Donner street/watercourse footprint from the actual source-map parent. The remaining large component is the approximate Rómahegy extent.')
 (HERE/'kaposvar-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':build.FEATURES},ensure_ascii=False,separators=(',',':'))+'\n')
 (HERE/'evidence/kaposvar-summary.json').write_text(json.dumps({'features':len(build.FEATURES),'circleFallbackCount':0,'componentFeatures':6,'coarseParentSplitFeatures':3,'sourceContourVerticesRetainedExceptEstimatedSplitIntersections':True,'allNamesExplicitInMunicipalSource':True},ensure_ascii=False,indent=2)+'\n')
 print(collections.Counter(f['properties']['municipality']for f in build.FEATURES))
