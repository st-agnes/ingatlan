import assert from 'node:assert/strict';
import test from 'node:test';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {boundsIntersect,chooseVisibleCities,pointInGeometry,geometryArea,neighborhoodZoom,chooseVisibleNeighborhoods,chooseSmallestFeature,validateNeighborhoodHierarchy,neighborhoodAncestors,validatePlaceLabels,chooseVisiblePlaceLabels,chooseLabelHit,selectablePlaceLabelLayout} from '../dist/location-map.js';

// Synthetic WGS84 rectangles exercise display picking, never address geocoding.
const ring=(west,south,east,north)=>[[west,south],[east,south],[east,north],[west,north],[west,south]];
const polygon={type:'Polygon',coordinates:[ring(19,47,20,48)]};

test('the preserved legacy Leaflet assets retain their verified release and license',async()=>{
 for(const [file,expected]of Object.entries({
  'leaflet.js':'db49d009c841f5ca34a888c96511ae936fd9f5533e90d8b2c4d57596f4e5641a',
  'leaflet.css':'337bfca5cabd03b39815b2700febe2b3b7edf55921c59cd49f88ecb328212303',
  'LICENSE':'bbc959aaef7488b38942e7f05cfd1244351f8bce54261951ea17dd7cf60f894b'
 })){
  const bytes=await readFile(new URL('../dist/vendor/leaflet/'+file,import.meta.url));
  assert.equal(createHash('sha256').update(bytes).digest('hex'),expected,file+' must match the verified upstream release');
 }
});

const labelFeature=(id,coordinates,{kind='neighborhood',city='Budapest',minZoom=10,priority=100,boundaryId=id}={})=>({
 type:'Feature',id,geometry:{type:'Point',coordinates},properties:{id,name:id,label:id,city,kind,minZoom,priority,boundaryId}
});
const labelFixture=()=>{
 const manifest={version:'map-label-fixture-v1',sourceSha256:'a'.repeat(64),count:1};
 const features=[labelFeature('city:Budapest',[19.04,47.5],{kind:'city',minZoom:6,priority:0}),
  labelFeature('neighborhood:ward',[19.05,47.51]),
  labelFeature('district:Budapest:5',[19.05,47.51],{kind:'district',priority:50,boundaryId:'neighborhood:ward'})];
 const locations=new Map(features.map(feature=>[feature.id,{id:feature.id,label:feature.id,kind:feature.properties.kind,city:feature.properties.city}]));
 const value={schemaVersion:1,type:'FeatureCollection',version:'labels-v1',mapVersion:manifest.version,
  sourceSha256:manifest.sourceSha256,displayOnly:true,features,towns:[{id:'city:Budapest',file:'town-aaaaaaaaaaaaaaaaaaaa.json',bounds:[18.9,47.3,19.3,47.7]}],
  districtBoundaries:{'district:Budapest:5':'neighborhood:ward'},coverage:{type:'Polygon',coordinates:[ring(16,45.6,23,48.7)]}};
 return {manifest,value,locations,getLocation:id=>locations.get(id)||null};
};

test('selectable names carry a constant visible plus without state-dependent layout or changed canonical names',()=>{
 const fixture=labelFixture(),before=JSON.stringify(fixture.value),layout=selectablePlaceLabelLayout();
 const formatted=layout['text-field'];
 assert.equal(formatted[0],'format');assert.equal(formatted[1].trim(),'+');
 assert.ok(formatted[2]['font-scale']>0&&formatted[2]['font-scale']<=1,'The add marker remains a discreet readable part of each selectable name');
 assert.deepEqual(formatted[3],['get','name'],'The visible name comes from the original feature, never from a rewritten location label');
 assert.doesNotMatch(JSON.stringify(layout),/feature-state|selected|variable-anchor/,'Toggling may change paint, never text content, offset or collision layout');
 const labels=validatePlaceLabels(fixture.value,fixture.manifest,fixture.getLocation);
 for(const selected of [[],['city:Budapest'],['neighborhood:ward']]){
  const visible=chooseVisiblePlaceLabels(labels.features,[19,47,20,48],12,selected);
  assert.ok(visible.every(feature=>feature.properties.name===fixture.value.features.find(original=>original.id===feature.id).properties.name));
  assert.deepEqual(selectablePlaceLabelLayout(),layout);
 }
 assert.equal(JSON.stringify(fixture.value),before,'Adding the click affordance never changes catalogue identities or geographic anchors');
});

test('canonical label metadata binds points, district aliases and lazy town outlines without changing its source',()=>{
 const f=labelFixture(),before=JSON.stringify(f.value),labels=validatePlaceLabels(f.value,f.manifest,f.getLocation);
 assert.equal(labels.features.length,3);assert.equal(labels.byId.size,3);assert.equal(labels.towns.size,1);
 assert.equal(labels.byId.get('district:Budapest:5').properties.boundaryId,'neighborhood:ward');
 assert.equal(labels.towns.get('city:Budapest').file,'town-aaaaaaaaaaaaaaaaaaaa.json');
 assert.equal(JSON.stringify(f.value),before);
 labels.features[0].geometry.coordinates[0]=99;
 assert.equal(f.value.features[0].geometry.coordinates[0],19.04,'Runtime point preparation must not rewrite the shared registry');
});

test('stale, unknown, malformed or unsafe label records fail before becoming selectable map targets',()=>{
 for(const mutate of [
  f=>f.value.schemaVersion=2,f=>f.value.mapVersion='stale',f=>f.value.sourceSha256='b'.repeat(64),
  f=>f.value.displayOnly=false,f=>f.value.features=[],f=>f.value.features.push(structuredClone(f.value.features[0])),
  f=>f.value.features[0].id='unknown',f=>f.value.features[0].properties.id='different',
  f=>f.value.features[0].properties.city='Wrong town',f=>f.value.features[0].properties.kind='street',
  f=>f.value.features[0].properties.boundaryId='unknown',f=>f.value.features[0].geometry.type='Polygon',
  f=>f.value.features[0].geometry.coordinates=[NaN,47],f=>f.value.features[0].geometry.coordinates=[47,19],
  f=>f.value.features[0].properties.minZoom=Infinity,f=>f.value.features[0].properties.minZoom=19,
  f=>f.value.towns[0].file='../private.json',f=>f.value.towns[0].bounds=[20,48,19,47],
  f=>f.value.districtBoundaries['district:Budapest:5']='unknown',f=>f.value.coverage={type:'Point',coordinates:[19,47]}
 ]){
  const f=labelFixture();mutate(f);assert.throws(()=>validatePlaceLabels(f.value,f.manifest,f.getLocation),/nem érvényes/);
 }
});

test('labels use semantic zoom thresholds and keep adjacent peers eligible together',()=>{
 const town=labelFeature('town',[19.1,47.1],{kind:'city',minZoom:7,priority:10});
 const left=labelFeature('left',[19.2,47.2]),right=labelFeature('right',[19.8,47.8]);
 const farther=labelFeature('far',[22,48]),bounds=[19,47,20,48],features=[town,left,right,farther];
 assert.deepEqual(chooseVisiblePlaceLabels(features,bounds,7).map(f=>f.id),['town']);
 assert.deepEqual(new Set(chooseVisiblePlaceLabels(features,bounds,10).map(f=>f.id)),new Set(['town','left','right']));
 assert.deepEqual(chooseVisiblePlaceLabels(features,bounds,18).map(f=>f.id).sort(),['left','right','town']);
 assert.deepEqual(features.map(f=>f.id),['town','left','right','far']);
});

test('a district and its same-boundary alias render once while preserving an exact selected identity',()=>{
 const f=labelFixture(),bounds=[19,47,20,48];
 assert.deepEqual(chooseVisiblePlaceLabels(f.value.features,bounds,12).map(f=>f.id),['district:Budapest:5','city:Budapest']);
 assert.deepEqual(chooseVisiblePlaceLabels(f.value.features,bounds,12,['neighborhood:ward']).map(f=>f.id),['neighborhood:ward','city:Budapest']);
 assert.ok(chooseVisiblePlaceLabels(f.value.features,bounds,7,['neighborhood:ward']).some(feature=>feature.id==='neighborhood:ward'),'A selected name remains eligible at a distant view');
});

test('viewport labels remain bounded and retain selected names without reordering their peers',()=>{
 const features=Array.from({length:900},(_,i)=>labelFeature('label:'+i,[19+i*.00001,47.5],{priority:10}));
 const bounds=[19,47,20,48],visible=chooseVisiblePlaceLabels(features,bounds,12,['label:899']);
 const ordinary=chooseVisiblePlaceLabels(features,bounds,12);
 assert.equal(visible.length,650);assert.ok(visible.some(feature=>feature.id==='label:899'));
 const shared=new Set(ordinary.filter(feature=>visible.some(other=>other.id===feature.id)).map(feature=>feature.id));
 assert.deepEqual(visible.filter(feature=>shared.has(feature.id)).map(feature=>feature.id),ordinary.filter(feature=>shared.has(feature.id)).map(feature=>feature.id));
 assert.equal(chooseVisiblePlaceLabels(features,bounds,12,[],4).length,4);
 assert.deepEqual(chooseVisiblePlaceLabels(features,[22,48,23,49],12),[]);
 assert.deepEqual(chooseVisiblePlaceLabels(features,bounds,NaN),[]);
});

test('selection does not change ordinary labels, their geometry or their placement priority',()=>{
 const features=[labelFeature('town',[19.1,47.1],{kind:'city',minZoom:7,priority:10}),labelFeature('first',[19.2,47.2]),labelFeature('second',[19.3,47.3])];
 const before=JSON.stringify(features),bounds=[19,47,20,48];
 for(const zoom of [10,12,15]){
  const ordinary=chooseVisiblePlaceLabels(features,bounds,zoom);
  for(const id of ['town','first','second'])assert.deepEqual(chooseVisiblePlaceLabels(features,bounds,zoom,[id]),ordinary);
 }
 assert.equal(JSON.stringify(features),before);
});

test('whole-city labels yield collision priority when that city\'s first quarters become eligible',()=>{
 const town=labelFeature('city:Budapest',[19.1,47.5],{kind:'city',minZoom:6,priority:0});
 const buda=labelFeature('neighborhood:Buda',[19.0,47.5],{minZoom:8,priority:100});
 const pest=labelFeature('neighborhood:Pest',[19.2,47.5],{minZoom:8,priority:100});
 const distantTown=labelFeature('city:Another',[19.5,47.6],{kind:'city',city:'Another',minZoom:7,priority:10});
 const laterQuarter=labelFeature('neighborhood:Later',[19.5,47.6],{city:'Another',minZoom:10,priority:100});
 const features=[town,buda,pest,distantTown,laterQuarter],bounds=[18.9,47.3,19.7,47.8];
 assert.equal(chooseVisiblePlaceLabels(features,bounds,7).find(feature=>feature.id===town.id).properties.priority,0);
 const visible=chooseVisiblePlaceLabels(features,bounds,8),whole=visible.find(feature=>feature.id===town.id);
 for(const quarter of [buda,pest])assert.ok(visible.find(feature=>feature.id===quarter.id).properties.priority<whole.properties.priority);
 assert.equal(visible.find(feature=>feature.id===distantTown.id).properties.priority,10,'A different city keeps its distance priority until its own quarters appear');
 assert.deepEqual(chooseVisiblePlaceLabels(features,bounds,8,[town.id]),visible,'Selection must never change placement priority');
 assert.equal(town.properties.priority,0,'The registry remains immutable');
});

test('coincident real city and downtown anchors prioritize the quarter at close zoom without hiding selected names',async()=>{
 const registry=JSON.parse(await readFile(new URL('../dist/data/map/labels.json',import.meta.url),'utf8'));
 const town=registry.features.find(feature=>feature.id==='city:Debrecen');
 const downtown=registry.features.find(feature=>feature.properties.city==='Debrecen'&&feature.properties.name==='Belváros');
 assert.ok(town&&downtown);assert.deepEqual(town.geometry.coordinates,downtown.geometry.coordinates,'Keep this real coincident-anchor regression meaningful');
 const bounds=[21.5,47.4,21.8,47.7],features=[town,downtown];
 const distant=chooseVisiblePlaceLabels(features,bounds,7);assert.deepEqual(distant.map(feature=>feature.id),[town.id]);
 const close=chooseVisiblePlaceLabels(features,bounds,12);
 assert.equal(close[0].id,downtown.id);assert.ok(close[0].properties.priority<close[1].properties.priority,'The whole city must not permanently win the same label position');
 assert.deepEqual(new Set(chooseVisiblePlaceLabels(features,bounds,12,[town.id]).map(feature=>feature.id)),new Set([town.id,downtown.id]));
 assert.ok(town.properties.priority<downtown.properties.priority,'Zoom priority must not mutate the canonical source records');
});

test('rendered label hits resolve directly with a stable nearest-name choice and ignore polygon interiors',()=>{
 const first=labelFeature('first',[19.1,47.1]),second=labelFeature('second',[19.2,47.2]);
 const project=coordinates=>({x:coordinates[0]*100,y:coordinates[1]*100});
 assert.equal(chooseLabelHit([first,second],{x:1910,y:4710},project),first);
 assert.equal(chooseLabelHit([second,first,first],{x:1910,y:4710},project),first,'Tile duplicates and result order must not change a label choice');
 const tied=labelFeature('aaa',[19.1,47.1]);
 assert.equal(chooseLabelHit([first,tied],{x:1910,y:4710},project),tied);
 assert.equal(chooseLabelHit([{type:'Feature',id:'polygon',properties:{id:'polygon'},geometry:polygon}],{x:1950,y:4750},project),null);
 assert.equal(chooseLabelHit([], {x:1950,y:4750},project),null);
 assert.equal(chooseLabelHit([first],{x:NaN,y:4700},project),null);
});

test('map picking uses longitude/latitude and includes the polygon boundary',()=>{
 assert.equal(pointInGeometry([19.5,47.5],polygon),true);
 for(const point of [[19,47],[20,48],[19,47.5],[19.5,48]])assert.equal(pointInGeometry(point,polygon),true);
 for(const point of [[47.5,19.5],[18.99,47.5],[20.01,47.5],[19.5,46.99]])assert.equal(pointInGeometry(point,polygon),false);
});

test('hole interiors are excluded while their boundary remains selectable',()=>{
 const geometry={type:'Polygon',coordinates:[ring(19,47,20,48),ring(19.3,47.3,19.7,47.7)]};
 assert.equal(pointInGeometry([19.1,47.1],geometry),true);
 assert.equal(pointInGeometry([19.5,47.5],geometry),false);
 for(const point of [[19.3,47.5],[19.7,47.7],[19.5,47.3]])assert.equal(pointInGeometry(point,geometry),true);
});

test('ring orientation does not change picking and multipolygons retain their gaps',()=>{
 assert.equal(pointInGeometry([19.5,47.5],{type:'Polygon',coordinates:[polygon.coordinates[0].toReversed()]}),true);
 const multi={type:'MultiPolygon',coordinates:[[ring(19,47,19.2,47.2)],[ring(20,48,20.2,48.2)]]};
 assert.equal(pointInGeometry([19.1,47.1],multi),true);
 assert.equal(pointInGeometry([20.1,48.1],multi),true);
 assert.equal(pointInGeometry([19.5,47.5],multi),false);
});

test('independently named overlapping areas both remain selectable',()=>{
 const overlap={type:'Polygon',coordinates:[ring(19.4,47.4,20.4,48.4)]};
 assert.equal(pointInGeometry([19.6,47.6],polygon),true);
 assert.equal(pointInGeometry([19.6,47.6],overlap),true);
});

test('unsupported or malformed map geometry cannot become a selected area',()=>{
 for(const geometry of [null,{}, {type:'Point',coordinates:[19,47]}, {type:'Polygon',coordinates:[]}, {type:'MultiPolygon',coordinates:[]}])assert.equal(pointInGeometry([19,47],geometry),false);
 for(const point of [null,[],[19],[NaN,47],[19,Infinity]])assert.equal(pointInGeometry(point,polygon),false);
});

test('viewport intersection is inclusive and keeps longitude/latitude axis order',()=>{
 assert.equal(boundsIntersect([19,47,20,48],[19.5,47.5,20.5,48.5]),true);
 assert.equal(boundsIntersect([19,47,20,48],[20,48,21,49]),true);
 assert.equal(boundsIntersect([19,47,20,48],[20.01,47,21,48]),false);
 assert.equal(boundsIntersect([19,47,20,48],[47,19,48,20]),false);
});

test('visible city geometry requests are bounded and exclude distant towns',()=>{
 const cities=[
  {city:'B',bounds:[19.1,47.1,19.2,47.2],file:'city-b.json'},
  {city:'C',bounds:[19.7,47.7,19.8,47.8],file:'city-c.json'},
  {city:'Outside',bounds:[21,48,22,49],file:'city-outside.json'},
  {city:'A',bounds:[19.4,47.4,19.6,47.6],file:'city-a.json'}
 ];
 const chosen=chooseVisibleCities(cities,[19,47,20,48],{maxCities:2});
 assert.equal(chosen.items.length,2);assert.equal(chosen.truncated,true);
 assert.equal(chosen.items[0].city,'A');assert.ok(chosen.items.every(item=>item.city!=='Outside'));
 assert.deepEqual(cities.map(item=>item.city),['B','C','Outside','A'],'Viewport selection must not reorder the canonical index in place');
});

test('an empty viewport is a normal result and exact request limits are retained',()=>{
 const cities=Array.from({length:20},(_,index)=>({city:`City ${index}`,bounds:[19,47,20,48],file:`city-${index}.json`}));
 assert.deepEqual(chooseVisibleCities(cities,[21,48,22,49]),{items:[],truncated:false});
 assert.equal(chooseVisibleCities(cities,[19,47,20,48]).items.length,8);
 const exact=chooseVisibleCities(cities.slice(0,2),[19,47,20,48],{maxCities:2});assert.equal(exact.items.length,2);assert.equal(exact.truncated,false);
});

test('a focused city remains visible at its edge without fetching cities outside the viewport',()=>{
 const bounds=[19,47,20,48],villages=Array.from({length:9},(_,index)=>({city:`Nearby ${index}`,bounds:[19.40+index*.01,47.4,19.45+index*.01,47.45],file:`nearby-${index}.json`}));
 const large={city:'Focused large city',bounds:[19.95,47,23,49],file:'large-city.json'};
 const outside={city:'Outside preferred city',bounds:[21,47,22,48],file:'outside.json'};
 const cities=[...villages,large,outside];
 assert.equal(chooseVisibleCities(cities,bounds).items.some(item=>item.city===large.city),false,'The large city center is farther away than nine intersecting villages');
 const focused=chooseVisibleCities(cities,bounds,{preferredCity:large.city});assert.equal(focused.items.length,8);assert.equal(focused.truncated,true);assert.equal(focused.items[0],large,'An explicitly focused quarter must not lose its city geometry at the bounded request limit');
 const excluded=chooseVisibleCities(cities,bounds,{preferredCity:outside.city});assert.equal(excluded.items.length,8);assert.equal(excluded.items.some(item=>item.city===outside.city),false,'Preference cannot bypass viewport intersection');
});

const feature=(id,bounds,{city='Town',geometry}={})=>({type:'Feature',id,bbox:bounds,
 properties:{id,city,label:id},geometry:geometry||{type:'Polygon',coordinates:[ring(...bounds)]}});

test('actual spherical area accounts for latitude, ring direction, holes and every multipart island',()=>{
 const equator={type:'Polygon',coordinates:[ring(0,0,1,1)]},north={type:'Polygon',coordinates:[ring(0,60,1,61)]};
 assert.ok(geometryArea(equator)>12e9&&geometryArea(equator)<13e9);
 assert.ok(geometryArea(north)/geometryArea(equator)>.48&&geometryArea(north)/geometryArea(equator)<.51);
 const outer=ring(19,47,19.04,47.04),hole=ring(19.01,47.01,19.03,47.03);
 const holed={type:'Polygon',coordinates:[outer,hole]};
 assert.ok(Math.abs(geometryArea(holed)-(geometryArea({type:'Polygon',coordinates:[outer]})-geometryArea({type:'Polygon',coordinates:[hole]})))<.001);
 assert.ok(Math.abs(geometryArea(holed)-geometryArea({type:'Polygon',coordinates:[outer.toReversed(),hole.toReversed()]}))<.001);
 assert.ok(Math.abs(geometryArea({type:'MultiPolygon',coordinates:[[outer],[hole]]})-(geometryArea({type:'Polygon',coordinates:[outer]})+geometryArea({type:'Polygon',coordinates:[hole]})))<.001);
 for(const invalid of [null,{}, {type:'Point',coordinates:[19,47]}, {type:'Polygon',coordinates:[]}, {type:'Polygon',coordinates:[[[19,47],[20,47],[NaN,48],[19,47]]]}, {type:'Polygon',coordinates:[[[19,47],[20,47],[20,48],[19,48]]]}])assert.equal(geometryArea(invalid),0);
});

test('one overlap click chooses actual area rather than bounding box and is independent of input order',()=>{
 const smallWithLargeBox=feature('thin',[19,47,19.04,47.04],{geometry:{type:'Polygon',coordinates:[ring(19,47,19.04,47.04),ring(19.002,47.002,19.038,47.038)]}});
 const compact=feature('compact',[19,47,19.021,47.021]);
 assert.ok(geometryArea(smallWithLargeBox.geometry)<geometryArea(compact.geometry));
 for(const features of [[smallWithLargeBox,compact],[compact,smallWithLargeBox]])assert.equal(chooseSmallestFeature(features,[19.001,47.001]),smallWithLargeBox);
 assert.equal(chooseSmallestFeature([smallWithLargeBox,compact],[19.01,47.01]),compact,'A hole interior is not a hit');
 assert.equal(chooseSmallestFeature([compact],[20,48]),null);
});

test('equal-area overlapping regions have a stable canonical-ID tie break',()=>{
 const first=feature('area:a',[19,47,19.01,47.01]),second=feature('area:z',[19,47,19.01,47.01]);
 for(const features of [[first,second],[second,first]])assert.equal(chooseSmallestFeature(features,[19.005,47.005]),first);
 for(const point of [null,[],[NaN,47],[19,Infinity]])assert.equal(chooseSmallestFeature([first],point),null);
});

test('zoom levels follow containment and add child outlines without hiding ancestors',()=>{
 const broad=feature('broad',[19,47,19.2,47.2]),middle=feature('middle',[19,47,19.05,47.05]),fine=feature('fine',[19,47,19.01,47.01]);
 const features=[broad,middle,fine],parents={middle:'broad',fine:'middle'},bounds=[18.9,46.9,19.3,47.3];
 assert.equal(neighborhoodZoom(broad,features,parents),8);
 assert.equal(neighborhoodZoom(middle,features,parents),10);
 assert.equal(neighborhoodZoom(fine,features,parents),12);
 assert.deepEqual(chooseVisibleNeighborhoods(features,bounds,7,parents),[]);
 assert.deepEqual(chooseVisibleNeighborhoods(features,bounds,8,parents),[broad]);
 assert.deepEqual(chooseVisibleNeighborhoods(features,bounds,9.75,parents),[broad]);
 assert.deepEqual(chooseVisibleNeighborhoods(features,bounds,10,parents),[broad,middle]);
 assert.deepEqual(chooseVisibleNeighborhoods(features,bounds,12,parents),features);
 assert.deepEqual(chooseVisibleNeighborhoods(features,bounds,18,parents),features);
 assert.deepEqual(chooseVisibleNeighborhoods(features,bounds,NaN,parents),[]);
});

test('adjacent leaf neighborhoods remain visible together regardless of their different areas',()=>{
 const large=feature('large',[19,47,19.2,47.2]),small=feature('small',[19.25,47,19.251,47.001]);
 const child=feature('child',[19.01,47.01,19.02,47.02]),features=[large,small,child],parents={child:'large'},bounds=[18.9,46.9,19.3,47.3];
 assert.ok(geometryArea(large.geometry)>geometryArea(small.geometry)*1000);
 for(const zoom of [8,9,10,12,16,18]){
  const visible=chooseVisibleNeighborhoods(features,bounds,zoom,parents);
  assert.ok(visible.includes(large)&&visible.includes(small),'Unrelated quarters cannot disappear when another branch changes level');
  assert.equal(visible.includes(child),zoom>=10);
 }
 assert.deepEqual(chooseVisibleNeighborhoods([large,small],bounds,8),[large,small],'Size alone never creates a hierarchy');
});

test('map additions receive only their full true ancestor chain, never neighboring alternatives',()=>{
 const parents={ward:'Pest',quarter:'ward',otherQuarter:'Pest'};
 assert.deepEqual(neighborhoodAncestors('quarter',parents),['ward','Pest']);
 assert.deepEqual(neighborhoodAncestors('otherQuarter',parents),['Pest']);
 assert.deepEqual(neighborhoodAncestors('Pest',parents),[]);
 assert.deepEqual(neighborhoodAncestors('Buda',parents),[]);
 assert.deepEqual(neighborhoodAncestors('quarter',{quarter:'ward',ward:'quarter'}),['ward'],'Malformed caller data cannot loop forever');
});

test('panning filters geography without swapping an unrelated parent out of the viewport',()=>{
 const broad=feature('broad',[19,47,19.2,47.2]),child=feature('child',[19.18,47.18,19.19,47.19]);
 const features=[broad,child],parents={child:'broad'};
 assert.deepEqual(chooseVisibleNeighborhoods(features,[19,47,19.1,47.1],12,parents),[broad]);
 assert.deepEqual(chooseVisibleNeighborhoods(features,[19.18,47.18,19.2,47.2],12,parents),[broad,child]);
 assert.deepEqual(chooseVisibleNeighborhoods(features,[22,48,23,49],18,parents),[]);
});

test('all hierarchy levels remain reachable at zoom18 and unrelated tiny town areas start at8',()=>{
 const features=Array.from({length:9},(_,index)=>feature('level:'+index,[19,47,19+.1/(index+1),47+.1/(index+1)]));
 const parents=Object.fromEntries(features.slice(1).map((item,index)=>[item.id,features[index].id]));
 const smallTown=feature('small-town',[20,48,20.00001,48.00001],{city:'Village'});features.push(smallTown);
 assert.equal(neighborhoodZoom(features[8],features,parents),18);
 assert.equal(neighborhoodZoom(smallTown,features,parents),8);
 assert.deepEqual(chooseVisibleNeighborhoods(features,[18,46,21,49],18,parents),features);
 assert.deepEqual(chooseVisibleNeighborhoods(features,[18,46,21,49],8,parents),[features[0],smallTown]);
});

const hierarchyFixture=()=>{
 const manifest={version:'map-fixture-v1',sourceSha256:'a'.repeat(64),count:3};
 const locations=new Map(['parent','child','other'].map(id=>[id,{id,kind:'neighborhood',city:'Town'}]));
 const value={schemaVersion:1,mapVersion:manifest.version,sourceSha256:manifest.sourceSha256,count:3,
  policy:{minimumCoverage:.95,maximumChildAreaRatio:.8},parents:{child:'parent'}};
 return {manifest,locations,value,getLocation:id=>locations.get(id)||null};
};

test('precomputed hierarchy metadata is pinned, immutable and uses only same-city canonical areas',()=>{
 const f=hierarchyFixture(),parents=validateNeighborhoodHierarchy(f.value,f.manifest,f.getLocation);
 assert.deepEqual({...parents},{child:'parent'});assert.ok(Object.isFrozen(parents));
 assert.deepEqual(f.value.parents,{child:'parent'},'Validation must not rewrite source metadata');
});

test('malformed, stale, cyclic and cross-city hierarchy metadata fails before map selection',()=>{
 for(const mutate of [
  f=>f.value.schemaVersion=2,f=>f.value.mapVersion='stale',f=>f.value.sourceSha256='b'.repeat(64),
  f=>f.value.count=4,f=>f.value.parents=[],f=>f.value.parents={unknown:'parent'},
  f=>f.value.parents={child:'unknown'},f=>f.value.parents={child:'child'},
  f=>f.value.parents={child:'parent',parent:'child'},f=>f.locations.get('parent').city='Different town',
  f=>f.locations.get('parent').kind='city',f=>f.value.policy.minimumCoverage=.5,
  f=>f.value.policy.maximumChildAreaRatio=1
 ]){
  const f=hierarchyFixture();mutate(f);
  assert.throws(()=>validateNeighborhoodHierarchy(f.value,f.manifest,f.getLocation),/hierarchiája nem érvényes/);
 }
});
