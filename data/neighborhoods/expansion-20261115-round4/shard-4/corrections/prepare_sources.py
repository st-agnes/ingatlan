from pathlib import Path
import json,shutil,gzip
R=Path(__file__).resolve().parent;P=R.parent;REPO=R.parents[4]
def dump(p,j):p.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
for src,name in [(P/'kecskemet/page138-xref164.png','municipal-figure71.png'),(P/'kecskemet/registration.json','registration.json'),(P/'source-inputs/salgotarjan-c84905b5/municipality.geojson','salgotarjan-municipality.geojson'),(P/'source-inputs/salgotarjan-c84905b5/labels.geojson','salgotarjan-labels.geojson'),(P/'source-inputs/kecskemet-34828e67/municipality.geojson','kecskemet-municipality.geojson')]:shutil.copy2(src,R/name)
# Frozen previous sources; retain only their full, unchanged geographic geometries.
base=Path('data/neighborhoods')
sources=[(base/'expansion-20261114/machine-footprints/raw-source-footprints.geojson','native-residential-relations.geojson'),(base/'sources/municipal-salgotarjan-next/salgotarjan-inferred.geojson','municipal-profile-estimates.geojson'),(base/'expansion-20261114-next/gyula-salgo/salgotarjan-features.geojson','municipal-urban-quarter-estimates.geojson')]
for src,name in sources:
 fs=json.loads(src.read_text())['features'];fs=[f for f in fs if f.get('properties',{}).get('municipality')=='Salgótarján'];dump(R/name,{'type':'FeatureCollection','features':fs});print(name,len(fs))
shutil.copy2(P/'salgotarjan/source-pages125-139.pdf',R/'salgotarjan-source-pages125-139.pdf')
shutil.copy2(P/'salgotarjan/source-text-p139.txt',R/'salgotarjan-source-text-p139.txt')
shutil.copy2(P/'salgotarjan/eresztveny-prior-estimate.geojson',R/'eresztveny-prior-estimate.geojson')
dump(R/'source-paths.json',{'sourceSubsets':[{'originalPath':str(a),'subsetPath':b} for a,b in sources],'sourceMapOriginal':'../kecskemet/page138-xref164.png','municipalKecskemetUrl':'https://kecskemet.hu/uploaded_files/files/document/2022-11/126_2021._%28XII.16%29_hatarozat_1._melleklete_II-es_kotet.pdf','municipalSalgotarjanUrl':'https://www.salgotarjan.hu/wp-content/uploads/fejlesztesidokumentumok_20220629_its.pdf'})
