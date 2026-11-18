from pathlib import Path
import gzip,json,shutil,hashlib
P=Path(__file__).resolve().parent;R=P.parent.parent
raw=json.load(gzip.open(R/'residual-buildings/sandipuszta.geojson.gz','rt'))
ids=list(range(210,214))+list(range(214,221))+list(range(221,240))
selected=[raw['features'][i] for i in ids]
assert len(selected)==30 and all(f['properties']['tags'].get('building') for f in selected)
# All 30 footprints are the distinct cluster around the Sandipuszta source label,
# between the northern vineyard, southern wooded strip and eastern Kenderesi track.
# None of the buildings in the separate Alsómajor village surface is selected.
selected.append(next(f for f in json.load(open(R/'contexts/gyugy-90c0585a/labels.geojson'))['features'] if f['id']=='osm:node:1132188873'))
(P/'source-inputs').mkdir(exist_ok=True)
with open(P/'source-inputs/selected-source-objects.geojson.gz','wb') as out:
 with gzip.GzipFile(fileobj=out,mode='wb',mtime=0) as z:z.write((json.dumps({'type':'FeatureCollection','features':selected},ensure_ascii=False,separators=(',',':'))+'\n').encode())
shutil.copyfile(R/'contexts/gyugy-90c0585a/municipality.geojson',P/'source-inputs/gyugy-municipality.geojson')
shutil.copyfile(P.parent/'evidence/sandipuszta-academic-place-definitions.json',P/'evidence/sandipuszta-academic-place-definitions.json')
# Preserve the full anonymous-building snapshots and extraction provenance to document
# both the selected current compound and the absence near the disappeared hamlet.
for n in ['sandipuszta.geojson.gz','arkoshaza.geojson.gz','manifest.json']:shutil.copyfile(R/'residual-buildings'/n,P/'source-inputs'/n)
recipe={'municipality':'Gyugy','name':'Sandipuszta','operation':'occupied-building-envelope','buildingIds':[f['id'] for f in selected if f['geometry']['type']!='Point'],'sourceNameAssociationPoint':[17.6649526,46.6866203],'yardAllowanceM':20,'partialFootprint':True,'sourceUrl':'https://mdh.unideb.hu/telepules.php?adatlap=13-15-37/1&c=13-15-37&t=Gyugy','supportingUrls':['https://www.openstreetmap.org/node/1132188873','https://fotoport.hu/hng/somogy/index-fonyodi-jaras.htm','https://www.openstreetmap.org/way/1392072597','https://www.openstreetmap.org/way/1392072616','https://www.openstreetmap.org/way/1392072623'],'approximationNote':'Low-confidence occupied-locality estimate: the outer envelope of 30 actual mapped buildings in the distinct Sandipuszta compound around its OSM name point, with a 20 m allowance for yards and frontage. Native tracks show their shared access; the northern vineyard and southern forest help distinguish the cluster. The historical place-name register identifies Sandipuszta separately from the Sandi field and vineyard names. No point radius, Voronoi cell or track-only hull is used. This covers the currently mapped built compound rather than the full historical estate or cadastral district; gaps between buildings are generalized and the yard edges are estimated. The separate Alsómajor surface southeast of this cluster is not aliased or included. No unseen PDF map has been digitized.'}
(P/'recipe.json').write_text(json.dumps(recipe,ensure_ascii=False,indent=2)+'\n')
print('Prepared',len(recipe['buildingIds']),'source footprints plus name identity')
