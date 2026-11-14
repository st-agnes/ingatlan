#!/usr/bin/env python3
"""Record the acquired social-map lead without miscounting its merged units."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent
p=HERE/'miskolc-social-map-2011.pdf'
report={'sourceUrl':'https://atti.uni-miskolc.hu/docs/miskolcterkep.pdf',
 'title':'Miskolc Megyei Jogú Város Szociális Térképe, 2011',
 'path':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
 'pdfPages':179,'relevantPages':[12,19,26],
 'observedPartitionCount':17,'fine32GeometryFound':False,
 'newGeometryExportedFromThisSource':0,
 'disposition':'Archived useful historical source, but its maps again show17mergedgroups. No duplicate17cohort exported.',
 'notes':['Page12lists17mergedrespondentdistricts, including several constituent names in each.',
 'Page26shows17numberedchoroplethareas and citesKSH2003; this citation does not supply32fineoutlines.',
 'Numbering differs from the2014municipalmap, so labels must never be transferred using number alone.']}
(HERE/'miskolc-social-map-disposition.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'sourceBytes':report['bytes'],'partitionCount':17,'newGeometryCount':0}))
