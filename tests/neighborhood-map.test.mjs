import assert from 'node:assert/strict';
import test from 'node:test';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {boundsIntersect,chooseVisibleCities,pointInGeometry,geometryArea,neighborhoodZoom,chooseVisibleNeighborhoods,chooseSmallestFeature} from '../dist/location-map.js';

// Synthetic WGS84 rectangles exercise display picking, never address geocoding.
const ring=(west,south,east,north)=>[[west,south],[east,south],[east,north],[west,north],[west,south]];
const polygon={type:'Polygon',coordinates:[ring(19,47,20,48)]};

test('the shipped map renderer is the pinned official Leaflet release with its license',async()=>{
 for(const [file,expected]of Object.entries({
  'leaflet.js':'db49d009c841f5ca34a888c96511ae936fd9f5533e90d8b2c4d57596f4e5641a',
  'leaflet.css':'337bfca5cabd03b39815b2700febe2b3b7edf55921c59cd49f88ecb328212303',
  'LICENSE':'bbc959aaef7488b38942e7f05cfd1244351f8bce54261951ea17dd7cf60f894b'
 })){
  const bytes=await readFile(new URL('../dist/vendor/leaflet/'+file,import.meta.url));
  assert.equal(createHash('sha256').update(bytes).digest('hex'),expected,file+' must match the verified upstream release');
 }
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

test('zoom bands replace broad regions with finer areas instead of stacking every ancestor',()=>{
 const broad=feature('broad',[19,47,19.2,47.2]),middle=feature('middle',[19,47,19.05,47.05]),fine=feature('fine',[19,47,19.01,47.01]);
 const features=[fine,broad,middle],bounds=[18.9,46.9,19.3,47.3];
 assert.deepEqual(chooseVisibleNeighborhoods(features,bounds,11),[broad]);
 const middleZoom=neighborhoodZoom(middle,features),fineZoom=neighborhoodZoom(fine,features);
 assert.ok(middleZoom>11&&fineZoom>middleZoom);
 assert.deepEqual(chooseVisibleNeighborhoods(features,bounds,middleZoom),[middle]);
 assert.deepEqual(chooseVisibleNeighborhoods(features,bounds,fineZoom),[fine]);
 assert.equal(chooseVisibleNeighborhoods(features,bounds,10).length,0);
 assert.equal(chooseVisibleNeighborhoods(features,bounds,NaN).length,0);
});

test('an empty finer band falls back in that viewport without revealing future fine areas',()=>{
 const broad=feature('broad',[19,47,19.2,47.2]),fine=feature('fine',[19.18,47.18,19.19,47.19]),features=[broad,fine];
 const zoom=neighborhoodZoom(fine,features);
 assert.deepEqual(chooseVisibleNeighborhoods(features,[19,47,19.1,47.1],zoom),[broad]);
 assert.deepEqual(chooseVisibleNeighborhoods(features,[19,47,19.2,47.2],zoom-1),[broad]);
 assert.deepEqual(chooseVisibleNeighborhoods(features,[19.18,47.18,19.2,47.2],zoom),[fine]);
});

test('each town uses its own scale and every very tiny quarter becomes reachable by zoom18',()=>{
 const broad=feature('broad',[19,47,19.2,47.2]),tiny=feature('tiny',[19.1,47.1,19.100001,47.100001]);
 const smallTown=feature('small-town',[20,48,20.00001,48.00001],{city:'Village'}),features=[broad,tiny,smallTown],bounds=[18,46,21,49];
 assert.equal(neighborhoodZoom(tiny,features),18);
 assert.deepEqual(new Set(chooseVisibleNeighborhoods(features,bounds,11).map(item=>item.id)),new Set(['broad','small-town']));
 assert.deepEqual(new Set(chooseVisibleNeighborhoods(features,bounds,18).map(item=>item.id)),new Set(['tiny','small-town']));
 assert.deepEqual(chooseVisibleNeighborhoods(features,[22,48,23,49],18),[]);
});
