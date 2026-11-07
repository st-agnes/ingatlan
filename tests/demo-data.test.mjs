/** Fictional hosted-test catalog compatibility and non-destructive batch identities. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {DEFAULT_BATCH, createDemoCatalog, DEMO_USERS, DEMO_FIXTURES, DEMO_PASSWORD} from '../scripts/gcp/demo-data.mjs';
import {getLocation, isPropertyLocation} from '../dist/locations.js';
import {normalizePropertyAttributes, normalizeSearchAttributes} from '../dist/attributes.js';
import {isCompatible} from '../dist/model.js';

const oldUsers = ['anna','peter','eszter'];
const oldFixtures = [
  'peter-pozsonyi','peter-rozsadomb','peter-debrecen','anna-solymar-house',
  'eszter-pilisvorosvar-house','eszter-ujlipotvaros','anna-budapest','anna-debrecen','peter-house','eszter-buda'
];
const hash = value => createHash('sha256').update(JSON.stringify(value)).digest('hex');
const kind = (catalog,name) => catalog.fixtures.filter(fixture=>fixture.kind===name);
const property = fixture => ({...fixture.input,ownerId:fixture.owner,id:fixture.key});
const search = fixture => ({...fixture.input,ownerId:fixture.owner,id:fixture.key});

test('default catalog contains twelve ready accounts including three agents and a substantial mixed-role inventory',()=>{
 const catalog=createDemoCatalog();
 assert.equal(DEFAULT_BATCH,'alap');assert.deepEqual(DEMO_USERS,catalog.users);assert.deepEqual(DEMO_FIXTURES,catalog.fixtures);
 assert.equal(catalog.users.length,12);assert.equal(catalog.users.filter(user=>user.accountType==='agent').length,3);
 assert.equal(kind(catalog,'property').length,114);assert.equal(kind(catalog,'search').length,112);
 assert.equal(new Set(catalog.users.map(user=>user.email)).size,catalog.users.length);
 assert.equal(new Set(catalog.users.map(user=>user.key)).size,catalog.users.length);
 assert.equal(new Set(catalog.fixtures.map(fixture=>fixture.key)).size,catalog.fixtures.length);
 for(const user of catalog.users){
  const own=catalog.fixtures.filter(fixture=>fixture.owner===user.key);
  assert.ok(own.some(fixture=>fixture.kind==='property'));assert.ok(own.some(fixture=>fixture.kind==='search'));
  assert.ok(own.some(fixture=>fixture.key===user.active.key&&fixture.kind===user.active.kind));
  if(!oldUsers.includes(user.key))assert.equal(own.length,24);
  if(user.accountType==='agent')assert.equal(user.active.kind,'search','Agent accounts must open directly into the 1-credit search flow');
 }
});

test('original accounts, active selections and every original entity body remain unchanged',()=>{
 const catalog=createDemoCatalog();
 assert.equal(DEMO_PASSWORD,'OtthonraDemo2026!');
 const legacyUsers=catalog.users.filter(user=>oldUsers.includes(user.key)).map(({accountType,...user})=>{assert.equal(accountType,'private');return user;});
 assert.equal(hash(legacyUsers),'6e6e71428372a5f3fca6303b5ad32e6b1308e79b4e439b73c917e12190cf52a8');
 const legacyFixtures=catalog.fixtures.filter(fixture=>oldFixtures.includes(fixture.key));
 assert.equal(hash(legacyFixtures),'ab21f1aabe76a260775dca9ee14cf587b318df357751dce8e44ebc0fb346dcca');
});

test('already exhausted original default profiles receive dozens of entirely new compatible counterparties',()=>{
 const catalog=createDemoCatalog(), fresh=catalog.fixtures.filter(fixture=>!oldUsers.includes(fixture.owner));
 const locate=key=>catalog.fixtures.find(fixture=>fixture.key===key);
 const checks=[
  ['anna-budapest','search',72],['eszter-buda','search',36],['peter-pozsonyi','property',36],
  ['peter-rozsadomb','property',54],['anna-solymar-house','property',36],['peter-house','search',18],
  ['anna-debrecen','search',18]
 ];
 for(const [key,activeKind,minimum] of checks){
  const active=locate(key);
  const matches=fresh.filter(fixture=>fixture.kind!==activeKind&&(
   activeKind==='search'?isCompatible(property(fixture),search(active)):isCompatible(property(active),search(fixture))
  ));
  assert.ok(matches.length>=minimum,`${key} must get at least ${minimum} new matches, got ${matches.length}`);
  assert.ok(matches.some(fixture=>catalog.users.find(user=>user.key===fixture.owner).accountType==='agent'),`${key} needs agent counterparties`);
  assert.ok(matches.some(fixture=>catalog.users.find(user=>user.key===fixture.owner).accountType==='private'),`${key} needs private counterparties`);
 }
});

test('new accounts have compatible initial recommendations and agent searches can like the original seller property',()=>{
 const catalog=createDemoCatalog();
 const peter=property(catalog.fixtures.find(fixture=>fixture.key==='peter-pozsonyi'));
 for(const user of catalog.users.filter(user=>!oldUsers.includes(user.key))){
  const active=catalog.fixtures.find(fixture=>fixture.key===user.active.key);
  const matches=catalog.fixtures.filter(fixture=>fixture.kind!==active.kind&&(
   active.kind==='search'?isCompatible(property(fixture),search(active)):isCompatible(property(active),search(fixture))
  ));
  assert.ok(matches.length>=30,`${user.key} needs many initial recommendations`);
  if(user.accountType==='agent')assert.ok(isCompatible(peter,search(active)),`${user.key} must match the original seller for the 1-credit test`);
 }
});

test('all fixture locations, categories, room compositions and house requirements are valid API data',()=>{
 const catalog=createDemoCatalog();
 for(const fixture of catalog.fixtures){
  const input=fixture.input;
  assert.ok(catalog.users.some(user=>user.key===fixture.owner));
  assert.ok(input.title.startsWith('Teszt · '));assert.ok(input.title.length<=150);
  assert.match(input.description,/Kitalált tesztadat/);
  assert.equal(Object.hasOwn(input,'ownerAccountType'),false,'The server must derive owner roles');
  if(fixture.kind==='property'){
   assert.ok(isPropertyLocation(getLocation(input.locationId)),fixture.key);
   const normalized=normalizePropertyAttributes(input,{strict:true});
   assert.equal(normalized.rooms,input.rooms);assert.ok(input.price>0);assert.ok(input.area>0);assert.ok(input.rooms>0);
   assert.ok(input.images.every(url=>new URL(url).protocol==='https:'));
   if(input.type==='Ház'){assert.ok(input.lotArea>0);assert.equal(input.floor,null);assert.equal(input.balcony,false);assert.equal(input.elevator,false);}
   else assert.equal(input.lotArea,null);
   if(input.wholeRooms!=null||input.halfRooms!=null){assert.ok(Number.isInteger(input.wholeRooms));assert.ok(Number.isInteger(input.halfRooms));assert.equal(input.rooms,input.wholeRooms+input.halfRooms/2);}
  }else{
   assert.ok(input.locationIds.length>0);assert.ok(input.locationIds.every(id=>getLocation(id)),fixture.key);
   assert.doesNotThrow(()=>normalizeSearchAttributes(input,{strict:true}));
   for(const [min,max] of [['minPrice','maxPrice'],['minArea','maxArea'],['minRooms','maxRooms']]){
    assert.ok(input[min]==null||input[min]>=0);assert.ok(input[max]==null||input[max]>0);assert.ok(input[min]==null||input[max]==null||input[min]<=input[max]);
   }
  }
 }
});

test('named batches have new account and fixture identities while keeping the original three accounts untouched',()=>{
 const original=createDemoCatalog(), next=createDemoCatalog('november-uj');
 assert.deepEqual(next.users.slice(0,3),original.users.slice(0,3));assert.deepEqual(next.fixtures.slice(0,10),original.fixtures.slice(0,10));
 const oldEmails=new Set(original.users.slice(3).map(user=>user.email)),oldKeys=new Set(original.fixtures.slice(10).map(fixture=>fixture.key));
 assert.ok(next.users.slice(3).every(user=>!oldEmails.has(user.email)&&user.email.includes('+november-uj@')));
 assert.ok(next.fixtures.slice(10).every(fixture=>!oldKeys.has(fixture.key)));
 assert.deepEqual(createDemoCatalog('november-uj'),next,'A named batch must stay deterministic across reruns');
 next.users[3].name='Edited in caller';next.fixtures[10].input.images.push('https://example.test/image.jpg');
 assert.notEqual(createDemoCatalog('november-uj').users[3].name,next.users[3].name);
 assert.equal(createDemoCatalog('november-uj').fixtures[10].input.images.length,2,'Caller mutations must not leak into later batches');
 for(const batch of ['',null,1,'UPPER','bad batch','../other','a'.repeat(33),'-start'])assert.throws(()=>createDemoCatalog(batch));
 assert.doesNotThrow(()=>createDemoCatalog('a'.repeat(32)));
});
