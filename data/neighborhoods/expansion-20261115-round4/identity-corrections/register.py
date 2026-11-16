#!/usr/bin/env python3
"""Apply only the two verified global aliases and register the correction packet."""
import hashlib,json
from pathlib import Path
H=Path(__file__).resolve().parent;ROOT=H.parents[3];DATA=ROOT/'data/neighborhoods';EXP=DATA/'expansion-20261114'
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
feature=H/'features.geojson';summary=json.loads((H/'summary.json').read_text());digest=hashlib.sha256(feature.read_bytes()).hexdigest();assert digest==summary['featuresSha256']
path=feature.relative_to(ROOT).as_posix();entry={'path':path,'sha256':digest}
registry=json.loads((EXP/'input-registry.json').read_text());existing=next((r for r in registry['datasets'] if r['path']==path),None)
if existing:assert existing==entry
else:registry['datasets'].append(entry)
aliases=json.loads((EXP/'name-aliases.json').read_text())
for row in json.loads((H/'verified-aliases.json').read_text())['aliases']:
 old=next((r for r in aliases['aliases'] if r['municipality']==row['municipality'] and r['name']==row['name']),None)
 if old:assert old==row
 else:aliases['aliases'].append(row)
state=json.loads((H.parent/'WORK-STATE.json').read_text());packet={**entry,'featureCount':2,'role':'verified_identity_and_display_corrections_not_new_spatial_areas'}
old=next((r for r in state['completedPackets'] if r['path']==path),None)
if old:assert old==packet
else:state['completedPackets'].append(packet)
state['status']='collecting_and_checkpointing'
dump(EXP/'input-registry.json',registry);dump(EXP/'name-aliases.json',aliases);dump(H.parent/'WORK-STATE.json',state)
print(json.dumps({'registered':path,'sha256':digest,'verifiedAliasRows':2},ensure_ascii=False))
