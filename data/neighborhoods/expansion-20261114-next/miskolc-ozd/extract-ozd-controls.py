from pathlib import Path
import osmium,json
HERE=Path(__file__).resolve().parent
wanted={'Arló','Farkaslyuk','Borsodszentgyörgy','Ózd','Hódoscsépány','Somsály','Somsálybánya','Uraj','Susa','Center','Bánszállás','Tábla','Béketelep'}
rows=[]
class H(osmium.SimpleHandler):
 def node(self,n):
  if n.tags.get('name') in wanted and n.tags.get('place'):
   rows.append({'id':n.id,'name':n.tags.get('name'),'place':n.tags.get('place'),'coordinates':[n.location.lon,n.location.lat],'sourceUrl':'https://www.openstreetmap.org/node/'+str(n.id)})
H().apply_file('/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf')
(HERE/'ozd-locality-control-nodes.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n');print(rows)
