#!/usr/bin/env python3
"""Combine existing source/estimate statistics without claiming national completeness."""
from pathlib import Path
import argparse,csv,hashlib,io,json

ROOT=Path(__file__).resolve().parents[2]
def build():
    directory=ROOT/'data/neighborhoods'
    primary=(directory/'nationwide-report.csv').read_bytes()
    estimated=(directory/'estimated-report.json').read_bytes()
    rows=list(csv.DictReader(io.StringIO(primary.decode('utf-8-sig')),delimiter=';'))
    estimates=json.loads(estimated);by_city={r['municipality']:r for r in estimates['cities']}
    assert len(rows)==3155 and len({r['municipality'] for r in rows})==len(rows)
    assert set(by_city)<={r['municipality'] for r in rows}
    stream=io.StringIO(newline='');writer=csv.writer(stream,delimiter=';',lineterminator='\n')
    writer.writerow(['Település','Vármegye','Forrásalapú városrészjelöltek','Forrásalapú tervezési egységek',
                     'Becsült városrészjelöltek','Becsült tervezési csoportok','Becsült helyi területek',
                     'Becsült alakzatok összesen','Becsült alakzatok forrásnevei','Helyi névjegyzék státusza',
                     'Ismert teljes mai városrészszám','Ismert név szerinti hiányok','Hiányleltár forrásazonosítói'])
    totals={'primaryFeatures':0,'primaryMunicipalities':0,'planningFeatures':0,'estimatedFeatures':0,
            'estimatedNeighbourhoodCandidates':0,'estimatedPlanningCandidates':0,'estimatedLocalAreas':0,
            'estimatedMunicipalities':0,'municipalitiesWithPrimaryOrEstimatedGeometry':0}
    for row in rows:
        city=row['municipality'];e=by_city.get(city,{})
        p=int(row['quarter_geometry_count']);planning=int(row['planning_unit_geometry_count'])
        n=e.get('neighbourhoodCandidateCount',0);g=e.get('planningCandidateCount',0);a=e.get('localAreaCandidateCount',0)
        count=e.get('geometryCount',0);assert n+g+a==count
        totals['primaryFeatures']+=p;totals['primaryMunicipalities']+=bool(p);totals['planningFeatures']+=planning
        totals['estimatedFeatures']+=count;totals['estimatedNeighbourhoodCandidates']+=n
        totals['estimatedPlanningCandidates']+=g;totals['estimatedLocalAreas']+=a
        totals['estimatedMunicipalities']+=bool(count);totals['municipalitiesWithPrimaryOrEstimatedGeometry']+=bool(p or count)
        writer.writerow([city,row['county'],p,planning,n,g,a,count,' | '.join(e.get('names',[])),
                         row['name_inventory_status'],row['known_current_quarter_total'],
                         row['known_current_missing_boundaries'],row['reference_source_ids']])
    assert totals['estimatedFeatures']==estimates['geometryCount']
    assert totals['estimatedMunicipalities']==estimates['municipalityCount']
    metadata={'schemaVersion':1,'status':'incomplete_nationwide_research_checkpoint','municipalityRows':len(rows),
              **totals,'completeNationalCoverage':False,'approvedForAddressAssignment':False,
              'nationalTotalNumberOfNeighbourhoodsEstablished':False,
              'inputSha256':{'nationwide-report.csv':hashlib.sha256(primary).hexdigest(),
                             'estimated-report.json':hashlib.sha256(estimated).hexdigest()},
              'interpretation':['Counts represent source-specific geometry candidates, not a verified complete boundary register.',
                                'Estimated neighbourhoods, broader planning groups and local areas are counted separately.',
                                'Blank current totals or missing-name fields mean unknown/not established, not zero or complete coverage.',
                                'Named gaps belong to their cited local inventory and period. Different historical systems are not interchangeable.',
                                'A municipality with a geometry is only partly researched; no coverage percentage is computed.'],
              'regenerate':'python3 scripts/neighborhoods/combined-report.py'}
    return {'combined-report.csv':stream.getvalue().encode('utf-8-sig'),
            'combined-report.json':(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n').encode()}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    files=build()
    for name,data in files.items():
        path=ROOT/'data/neighborhoods'/name
        if args.check:assert path.read_bytes()==data,'Stale combined report: '+name
        else:path.write_bytes(data)
    summary=json.loads(files['combined-report.json'])
    print(json.dumps({'checked':args.check,'municipalityRows':summary['municipalityRows'],
                      'primaryFeatures':summary['primaryFeatures'],'estimatedFeatures':summary['estimatedFeatures'],
                      'completeNationalCoverage':False}))
