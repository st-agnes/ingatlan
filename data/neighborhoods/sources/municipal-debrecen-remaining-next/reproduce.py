#!/usr/bin/env python3
"""Offline, self-contained reproduction; optional checks against ignored originals."""
from pathlib import Path
import argparse, copy, csv, hashlib, io, json, math
from itertools import combinations
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
DATASET = 'debrecen-arcgis-remaining-23-estimated'
SELECT = {2:'Pallag',10:'Epreskert',29:'Nyulas',30:'Úrrétje',31:'Tócóliget',32:'Akadémiakert',33:'Kertváros',34:'Köntöskert',36:'Nagysándortelep',37:'Hatvan utcai kert',38:'Kismacs',41:'Tócóvölgy',43:'Sóház',50:'Kondoros',58:'Júliatelep',62:'Boldogfalvikert',63:'Tégláskert',64:'Majorság',72:'Nagymacs',73:'Nagycsere',75:'Haláp',76:'Bánk',77:'Ondód'}
ARC_URL = 'https://www.arcgis.com/home/item.html?id=a04e2a4ff4d2467c8bb6eb640f515b51'
PDF_URL = 'https://hbmo.hu/portal/wp-content/uploads/2023/12/01A_eloterj.mell_DMJV-FVS-2021-27-megalapozo-vizsgalat.pdf'
PBF_SHA = '224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
PDF_SHA = '97c9375414895a34c82a7968625e8196e2fd4882af1019ce74ee07e89236bd01'
METHOD = 'Literal published EPSG:4326 service GeoJSON polygon, copied with every coordinate, vertex order and closing repeat unchanged. Archived original EPSG:3857 rings are independently reprojected vertexwise to verify equivalence. Classified ESTIMATED because source placement, current whole-quarter extent, lineage, reference period and reuse rights remain unresolved. No fitted shift, correction, snapping, clipping, repair, simplification, buffering, densification, closure or invented edge. Current OSM points and municipal historical labels corroborate names only; neither generates nor fits boundaries.'
UNCERTAINTY = 'Original boundary survey/reference period, present whole-quarter extent, absolute ground accuracy, original publisher lineage and reuse rights are unknown. Existing all77-source/all26-baseline review finds a consistent west/south relative offset across25same-name pairs (median source-minus-baseline -61.063m east,-27.218m north). The cause and the more accurate source are unestablished. This is not an accuracy bound; no correction is fitted. Source/polygon overlaps are retained and reported rather than repaired. Historical2007quarter names in the November2023FVS do not certify current legal status or transfer map accuracy to ArcGIS.'

def read(n): return json.loads((P/n).read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def objsha(x): return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def write(n,x): (P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def original_checks():
    import osmium, fitz
    from PIL import Image
    pbf = ROOT/'.local/neighborhoods/hungary-latest.osm.pbf'
    pdf = ROOT/'.local/neighborhoods/supplement-official-next/debrecen-fvs2023.pdf'
    assert sha(pbf)==PBF_SHA and sha(pdf)==PDF_SHA
    points=read('selected-osm-name-points.geojson')['features']; expected={int(f['id'].split(':')[-1]):f for f in points}; actual={}
    class Handler(osmium.SimpleHandler):
        def node(self,n):
            if n.id in expected:
                actual[n.id]={'id':n.id,'version':n.version,'timestamp':str(n.timestamp),'tags':dict(n.tags),'coordinates':[n.location.lon,n.location.lat]}
    Handler().apply_file(str(pbf))
    assert set(actual)==set(expected)
    for nodeid,e in expected.items():
        a=actual[nodeid]; q=e['properties']['source']
        assert a['tags']==q['tags'] and a['version']==q['objectVersion'] and a['timestamp']==q['objectTimestamp']
        assert a['coordinates']==e['geometry']['coordinates']
    d=fitz.open(pdf); ev=read('municipal-name-evidence.json')
    assert d.extract_image(1179)['image']==(P/'debrecen-fvs-p208-original.png').read_bytes()
    crops=[]
    for row in ev['names']:
        rects=[r for r in d[205].search_for(str(row['historicalQuarterId'])+'. '+row['name']) if r.x0>=294]
        assert len(rects)==1
        assert list(rects[0])==row['labelRectanglePdfPoints']
        pix=d[205].get_pixmap(matrix=fitz.Matrix(3,3),clip=rects[0]+(-1,-1,1,1),alpha=False)
        crops.append(Image.frombytes('RGB',[pix.width,pix.height],pix.samples))
    canvas=Image.new('RGB',(max(im.width for im in crops)+20,sum(im.height for im in crops)+10*(len(crops)+1)),(255,255,255)); y=10
    for im in crops: canvas.paste(im,(10,y)); y+=im.height+10
    b=io.BytesIO(); canvas.save(b,format='PNG'); assert b.getvalue()==(P/'selected-table-label-crops.png').read_bytes()
    return {'originalPbfSha256Verified':True,'exactActualPbfNodesVerified':len(actual),'originalPdfSha256Verified':True,'originalEmbeddedMapBytesVerified':True,'allSelectedLabelCropsVerified':True}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--verify-originals',action='store_true');args=ap.parse_args()
    # Raw source inputs are frozen by content hashes, not by derived manifest values.
    fixed={'debrecen-source-native.json':'d97a7d3ca556f3ed554a5e6c70381d196b41199ba1c5b1ee4f692a55e3e00792','debrecen-source-service.geojson':'fb7d0f0bae18b05263d5658221f0a612a2839193ce47413e05dc71401b18cf3e','debrecen-source-count.json':'9b3a218b2e4ed1da46308c6dcf68fe028fd0c8353ddcb4866757de12a62f90af','debrecen-source-ids.json':'f763185f4511f0caaccbb42282a54d75599a3acf6986c8c7e5b142046a1a74d2'}
    for n,h in fixed.items(): assert sha(P/n)==h
    native=read('debrecen-source-native.json');service=read('debrecen-source-service.geojson')
    by={f['properties']['FID']:f for f in service['features']}; nb={f['attributes']['FID']:f for f in native['features']}
    assert set(by)==set(nb)==set(read('debrecen-source-ids.json')['objectIds'])==set(range(1,78))
    assert read('debrecen-source-count.json')['count']==77 and len(service['features'])==len(native['features'])==77
    assert native['spatialReference']['latestWkid']==3857 and service['crs']['properties']['name']=='EPSG:4326'
    assert not native.get('exceededTransferLimit',False) and not service.get('exceededTransferLimit',False)
    points=read('selected-osm-name-points.geojson'); assert points['sourcePbfSha256']==PBF_SHA
    pt={f['properties']['name']:f for f in points['features']}; assert set(pt)==set(SELECT.values())
    hist=read('municipal-name-evidence.json'); names={r['name']:r for r in hist['names']}; assert set(names)==set(SELECT.values())
    city=read('debrecen-municipality-reference.geojson')['features'];assert len(city)==1 and city[0]['id']=='osm:relation:1444234'
    eov=Transformer.from_crs(4326,23700,always_xy=True); wgs=Transformer.from_crs(3857,4326,always_xy=True);merc=Transformer.from_crs(4326,3857,always_xy=True)
    cg=transform(eov.transform,shape(city[0]['geometry']));assert cg.is_valid
    prior=read('existing-32-reference.geojson')['features'];assert len(prior)==32
    primary=[f for f in prior if f['properties']['referenceRole']=='existing_primary'];six=[f for f in prior if f['properties']['referenceRole']=='previous_six_estimated']
    assert len(primary)==26 and len(six)==6 and not(set(SELECT.values()) & {f['properties']['name'] for f in prior})
    refhash=read('existing-32-reference-hashes.json')
    for f in prior: assert objsha(f['geometry'])==refhash['features'][f['id']]['geometryCanonicalSha256']
    features=[];rows=[];geoms={};outpairs=[]
    for fid,name in SELECT.items():
        f=by[fid]; nf=nb[fid];p=pt[name]
        assert f['properties']==nf['attributes'] and f['properties']['nev']==name
        assert f['properties']['tipus'] in ['kertvaros','lakotelep','egyeb_belteruletek']
        assert 1<=names[name]['historicalQuarterId']<=75
        assert p['properties']['municipality']=='Debrecen' and p['properties']['place']=='suburb'
        assert p['properties']['source']['pbfSha256']==PBF_SHA and p['properties']['source']['tags']['name']==name
        assert f['geometry']['type']=='Polygon' and len(f['geometry']['coordinates'])==len(nf['geometry']['rings'])==1
        ring=f['geometry']['coordinates'][0];nr=nf['geometry']['rings'][0]
        assert ring[0]==ring[-1] and nr[0]==nr[-1] and len(ring)==len(nr)>=4
        assert all(len(c)==2 and all(math.isfinite(v) for v in c) for c in ring)
        g=shape(f['geometry']); ng=shape({'type':'Polygon','coordinates':nf['geometry']['rings']})
        assert g.is_valid and not g.is_empty and ng.is_valid and g.area>0
        maxdiff=max(abs(a-b) for (x,y),out in zip(nr,ring) for a,b in zip(wgs.transform(x,y),out))
        assert maxdiff<1e-11
        backdiff=ng.hausdorff_distance(transform(merc.transform,g));assert backdiff<1e-5
        mg=transform(eov.transform,g);pg=transform(eov.transform,shape(p['geometry']))
        assert cg.covers(mg) and mg.covers(pg)
        evidence={'exactLiteralNameInMunicipalHistoricalTable':True,'historicalQuarterId':names[name]['historicalQuarterId'],'currentPbfNodeId':p['id'],'currentPbfPlace':'suburb','exactNodeTagsAndCoordinatesVerifiedAgainstPbf':True,'currentSameCityPointInsidePolygon':True,'pointsUsedAsFitControls':False,'identityEvidenceIsNotCurrentWholeExtentProof':True}
        caveat='The FVS2023 discusses separating Lóskúti from parts of Tócóvölgy/Téglagyár. This ArcGIS footprint has unknown reference period and may reflect another schema; current Tócóvölgy extent is unverified.' if fid==41 else None
        props={'name':name,'municipality':'Debrecen','municipalityId':'city:Debrecen','boundaryKind':'inferred_area','candidateBoundaryKind':'neighbourhood','estimated':True,'canonicalNameIsNeighborhood':False,'sourceContourIsObserved':True,'sourceGeometryIsPublishedNative':True,'sourceCoordinatesUnchangedFromPublished4326':True,'sourceFID':fid,'sourceCategory':f['properties']['tipus'],'sourceRecordId':f'arcgis:a04e2a4ff4d2467c8bb6eb640f515b51:0:{fid}','sourceNameEvidence':evidence,'georeferencingStatus':'literal_published_coordinates_with_unresolved_source_placement','georeferencingIsApproximate':True,'georeferenceFitPerformed':False,'claimedAbsoluteAccuracyMetres':None,'absoluteBoundaryAccuracyM':None,'wholeOrdinaryQuarterExtentVerified':False,'sourceIsOfficial':False,'sourceIsHardBoundary':False,'usableForAddressAssignment':False,'reviewStatus':'estimated_source_placement_candidate','sourcePeriod':'Hosted data edit2025-06-02T23:33:23.324Z; original boundary reference period unknown','method':METHOD,'placementUncertainty':UNCERTAINTY,'specificExtentCaveat':caveat,'sourceGeometryCanonicalSha256':objsha(f['geometry']),'nativeGeometryCanonicalSha256':objsha(nf['geometry']),'evidenceUrls':[ARC_URL,PDF_URL],'sourceDocuments':[{'url':ARC_URL,'localNativeResponse':'debrecen-source-native.json','localPublished4326Response':'debrecen-source-service.geojson','FID':fid},{'url':PDF_URL,'sha256':PDF_SHA,'pdfPageOneBased':206,'table':79,'role':'Historical quarter-name identity only','selectedEvidencePath':'municipal-name-evidence.json'}],'license':'ArcGIS geometry reuse licence unestablished; ODbL-1.0 for actual OSM identity-point and comparison evidence','rightsStatus':'Public access is not a reuse licence. Original provider, boundary lineage and reuse rights unestablished.'}
        features.append({'type':'Feature','id':f'manual:{DATASET}:FID-{fid}','properties':props,'geometry':copy.deepcopy(f['geometry'])}); geoms[fid]=mg
        rows.append({'FID':fid,'name':name,'sourceCategory':f['properties']['tipus'],'historicalQuarterId':names[name]['historicalQuarterId'],'currentExactNamePointId':p['id'],'pointInside':True,'wholePolygonInDebrecen':True,'sourceAndOutputGeometryCanonicalSha256':objsha(f['geometry']),'nativeGeometryCanonicalSha256':objsha(nf['geometry']),'verticesIncludingClosure':len(ring),'validClosedSingleShell':True,'maxNativeToPublishedVertexDifferenceDegrees':maxdiff,'nativeVsPublishedBackprojectionHausdorffM3857':backdiff,'areaM2Epsg23700':mg.area,'noPriorExactNameIdentity':True,'specificExtentCaveat':caveat})
        for old in prior:
            og=transform(eov.transform,shape(old['geometry']));a=mg.intersection(og).area
            outpairs.append({'FID':fid,'name':name,'referenceId':old['id'],'referenceName':old['properties']['name'],'referenceRole':old['properties']['referenceRole'],'intersectionM2':a,'sourceAreaCoveredFraction':a/mg.area,'referenceAreaCoveredFraction':a/og.area,'intersectionOverUnion':a/mg.union(og).area,'topologicallyEqual':mg.equals(og)})
    internal=[]
    for a,b in combinations(SELECT,2):
        ga,gb=geoms[a],geoms[b];inter=ga.intersection(gb).area
        if inter>0:
            internal.append({'FID1':a,'name1':SELECT[a],'FID2':b,'name2':SELECT[b],'intersectionM2':inter,'firstAreaCoveredFraction':inter/ga.area,'secondAreaCoveredFraction':inter/gb.area,'intersectionOverUnion':inter/ga.union(gb).area})
        assert inter/min(ga.area,gb.area)<.01 # Minor retained source disagreements; never repaired.
    assert not any(r['topologicallyEqual'] for r in outpairs)
    substantial=[r for r in outpairs if r['intersectionM2']>=1]
    assert max([r['sourceAreaCoveredFraction'] for r in substantial]+[0])<.10
    assert max([r['referenceAreaCoveredFraction'] for r in substantial]+[0])<.10
    write('debrecen-remaining-estimated.geojson',{'type':'FeatureCollection','scope':'23additional fine named quarter candidates only; ESTIMATED source placement/current extent, no completeness claim','coordinateSource':'Literal unchanged published EPSG4326 service coordinates','features':features})
    csvout=io.StringIO();cw=csv.DictWriter(csvout,fieldnames=list(outpairs[0]));cw.writeheader();cw.writerows(outpairs);(P/'all-736-prior-comparisons.csv').write_text(csvout.getvalue())
    review={'schemaVersion':1,'datasetId':DATASET,'featureCount':23,'classification':'ESTIMATED placement/source-extent neighborhood candidates','candidateBoundaryKind':'neighbourhood','method':METHOD,'placementUncertainty':UNCERTAINTY,'semanticSelection':'Exact literal names in FVS Table79 historical75quarter column, current exact-name same-city place=suburb points, ordinary garden/housing or distinct outlying built-up source categories. Not FVS coarse functional aggregates. Outlying Pallag,Kismacs,Nagymacs,Nagycsere,Haláp,Bánk,Ondód are inside Debrecen municipality, not separate municipality records.','wholeCurrentExtentVerified':False,'originalBoundaryReferencePeriodEstablished':False,'absoluteGroundAccuracyEstablished':False,'sourceLineageEstablished':False,'reuseRightsEstablished':False,'sourceOfficialStatusClaimed':False,'hardBoundaryClaimed':False,'addressAssignmentApproved':False,'primaryAdmissions':0,'existing26Preserved':True,'previousSixPreserved':True,'noSourceModification':True,'noAliasOrRenaming':True,'quarantinedFID11Unchanged':'Széchenyikert FID11 remains the suspected mislabel overlapping Újkert; neither renamed, merged, used nor added.','comparisonFeatures':32,'allPriorPairComparisons':736,'allPriorPairPath':'all-736-prior-comparisons.csv','positivePriorOverlapsAtLeast1M2':substantial,'positiveInternalOverlaps':internal,'overlapInterpretation':'All overlaps are preserved source-placement/extent disagreements, not proven shared official borders or duplicate identities. No overlap-based renaming or geometry repair.','features':rows}
    write('selection-review.json',review)
    dispositions=[]
    for fid,f in by.items():
        n=f['properties']['nev']; cat=f['properties']['tipus']
        if fid in SELECT: status='selected_estimated'; reason='Exact historical fine-quarter and current same-city point identity, valid published outline retained with estimate caveats.'
        elif fid==11: status='quarantine_suspected_source_mislabel';reason='Duplicate literal Széchenyikert FID11 overlaps Újkert and is not corrected, aliased, merged or admitted.'
        elif n in {x['properties']['name'] for x in primary}: status='existing_primary_identity';reason='Already represented by26baseline; no duplicate coverage increment.'
        elif n in {x['properties']['name'] for x in six}:status='previous_six_estimated_identity';reason='Already represented in earlier six-candidate packet; unchanged.'
        elif fid==4:status='excluded_generic_label';reason='Generic Közterület, no distinct named quarter identity.'
        elif fid==39:status='deferred_broad_parent';reason='Józsa is a broader parent; no invented split into Felsőjózsa/Alsójózsa.'
        elif fid in [45,53,74]:status='deferred_name_point_outside_extent';reason='Current exact-name point lies outside source footprint; no fitting or repair.'
        elif fid in [15,52,56,57,70]:status='deferred_name_variant';reason='Literal source spelling/wording differs from FVS75or current exact-name point; no alias invented in this cohort.'
        elif cat in ['erdo','ipari_uzem_terulet','egyeb_ovezet']:status='deferred_facility_use_or_forest_role';reason='Identity and whole-quarter extent beyond exact shared labels need separate semantic review; not a claim that all industrial/forest quarters are invalid.'
        elif fid==68:status='deferred_later_schema_area';reason='Lóskúti is starred outside the historical75schema; source reference period and separation need separate review.'
        else:status='deferred_other';reason='Outside this coherent cohort; no completeness claim.'
        dispositions.append({'FID':fid,'literalName':n,'sourceCategory':cat,'disposition':status,'reason':reason,'sourceNamePreserved':True,'sourceGeometryRetainedInRawResponse':True})
    write('all77-dispositions.json',{'sourceRecordCount':77,'selectedAdditionalCandidates':23,'existingPrimaryCount':26,'previousSixCandidateCount':6,'newPrimaryAdmissions':0,'records':dispositions})
    write('registry-entry.json',{'id':DATASET,'path':str((P/'debrecen-remaining-estimated.geojson').relative_to(ROOT)),'sha256':sha(P/'debrecen-remaining-estimated.geojson'),'municipality':'Debrecen','method':METHOD,'evidenceUrls':[ARC_URL,PDF_URL],'license':'ArcGIS geometry reuse licence unestablished; ODbL-1.0 for OSM identity and comparison evidence.','propertyOverrides':{'boundaryKind':'inferred_area','candidateBoundaryKind':'neighbourhood','estimated':True,'canonicalNameIsNeighborhood':False,'usableForAddressAssignment':False,'sourceIsOfficial':False,'sourceIsHardBoundary':False,'georeferencingIsApproximate':True,'claimedAbsoluteAccuracyMetres':None},'reviewPath':str((P/'selection-review.json').relative_to(ROOT)),'independentReviewPath':str((P/'independent-review.json').relative_to(ROOT)),'uncertaintyPath':str((P/'selection-review.json').relative_to(ROOT)),'uncertainties':[UNCERTAINTY,'Tócóvölgy current extent is additionally uncertain because FVS2023 describes Lóskúti separation from parts of it. Minor documented source/cohort/baseline overlaps remain unchanged.'],'frozenFeatureCount':23,'globalRegistryAdmissionPerformed':False})
    if args.verify_originals: write('original-source-revalidation.json',{'schemaVersion':1,'pbfSha256':PBF_SHA,'pdfSha256':PDF_SHA,**original_checks()})
    manifest={'schemaVersion':1,'selfContainedReproduction':True,'networkCalls':0,'globalWrites':False,'sourceRawHashes':fixed,'files':[]}
    excluded={'artifact-manifest.json','reproduction-check.json'}
    for f in sorted(P.iterdir()):
        if f.is_file() and f.name not in excluded:manifest['files'].append({'path':f.name,'bytes':f.stat().st_size,'sha256':sha(f)})
    write('artifact-manifest.json',manifest)
    print(json.dumps({'featureCount':23,'rawSourceCount':77,'existingPrimaryReferenceCount':26,'previousSixReferenceCount':6,'priorPairs':len(outpairs),'internalOverlaps':len(internal),'retainedPriorOverlapsAtLeast1M2':len(substantial),'networkCalls':0,'globalWrites':False}))

if __name__=='__main__':main()
