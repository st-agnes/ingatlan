import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';

// CI removes account/report, location, optional-attribute and seller-detail schema to simulate the initial release, then starts the API.
// This probe verifies that additive startup upgrades preserve real, related rows.
const base=(process.argv[2]||'http://localhost:5080').replace(/\/$/,'')+'/api';
const fixture=JSON.parse(await readFile(resolve(process.env.OTTHONRA_UPGRADE_FIXTURE||'.local/schema-upgrade-fixture.json'),'utf8'));
async function get(path,token){
 const response=await fetch(base+path,{signal:AbortSignal.timeout(10000),headers:{Authorization:`Bearer ${token}`}});
 assert.equal(response.status,200,`GET ${path} failed after the schema upgrade`);
 return response.json();
}
const [buyer,seller,buyerEntities,sellerEntities,matches,sellerMatches,ledger]=await Promise.all([
 get('/me',fixture.buyerToken),get('/me',fixture.sellerToken),
 get('/me/entities',fixture.buyerToken),get('/me/entities',fixture.sellerToken),
 get('/matches',fixture.buyerToken),get('/matches',fixture.sellerToken),get('/credits/ledger',fixture.sellerToken)
]);
assert.equal(buyer.id,fixture.buyerId);assert.equal(seller.id,fixture.sellerId);
assert.equal(buyer.accountType,'private','An existing account defaults to private without changing other profile data');
assert.equal(seller.accountType,'private');
assert.deepEqual(buyerEntities.reportedOwnerIds,[],'A pre-reporting account has no reported owners');
assert.deepEqual(sellerEntities.reportedOwnerIds,[]);
assert.equal(buyer.credits,fixture.expectedBuyerCredits);
assert.equal(seller.credits,fixture.expectedCredits);
assert.deepEqual(ledger,fixture.sellerLedger);
assert.deepEqual(sellerEntities.properties.map(item=>item.id).sort(),fixture.propertyIds);
assert.deepEqual(buyerEntities.searchRequests.map(item=>item.id).sort(),fixture.searchIds);
const property=sellerEntities.properties.find(item=>item.id===fixture.propertyId);
assert.ok(property);assert.equal(property.ownerAccountType,'private');assert.equal(property.city,'Budapest');assert.equal(property.district,'XIII.');
assert.equal(property.locationId,'district:Budapest:13');assert.equal(property.location.id,'district:Budapest:13');
assert.equal(property.address,'Private street 12');assert.equal(property.lotArea,null);
for(const field of ['constructionAge','view','ceilingHeight','heatingType','energyRating','parkingType'])assert.equal(property[field],'',`Old property must have unset ${field}`);
for(const field of ['insulated','airConditioning','solarPanels'])assert.equal(property[field],null,`Old property must retain unknown ${field}`);
assert.equal(property.rooms,3,'The original weighted room total must survive the schema upgrade');
assert.equal(property.wholeRooms,3,'A legacy three-room property derives three whole rooms');
assert.equal(property.halfRooms,0,'A legacy integer room total derives no half rooms');
assert.equal(property.secondaryHeatingType,'','Existing properties have no secondary heating restriction/data');
for(const oldProperty of sellerEntities.properties) {
 assert.equal(oldProperty.ownerAccountType,'private');
 const halfSteps=oldProperty.rooms*2;
 if(Number.isInteger(halfSteps)) {
  assert.equal(oldProperty.wholeRooms,Math.floor(oldProperty.rooms),`Legacy whole-room derivation failed for ${oldProperty.id}`);
  assert.equal(oldProperty.halfRooms,Number.isInteger(oldProperty.rooms)?0:1,`Legacy half-room derivation failed for ${oldProperty.id}`);
 } else {
  assert.equal(oldProperty.wholeRooms,null,'An older arbitrary decimal room total must not be silently rounded');
  assert.equal(oldProperty.halfRooms,null,'An older arbitrary decimal room total has no inferred half-room breakdown');
 }
 assert.equal(oldProperty.secondaryHeatingType,'');
 const legacyParking=typeof oldProperty.parkingType==='string'?oldProperty.parkingType.trim():'';
 assert.deepEqual(oldProperty.parkingTypes,legacyParking?[legacyParking]:[],'Legacy parking text remains one selection, or no selection when unset');
}
const search=buyerEntities.searchRequests.find(item=>item.id===fixture.searchId);
assert.ok(search);assert.equal(search.ownerAccountType,'private');assert.deepEqual(search.locationIds,['district:Budapest:13']);
assert.equal(search.minPrice,null);assert.equal(search.maxArea,null);assert.equal(search.maxRooms,null);
for(const field of ['conditions','buildings','constructionAges','views','floors','heatingTypes'])assert.deepEqual(search[field],[],`Old search must have no ${field} restriction`);
assert.equal(search.ceilingHeight,'');
const match=matches.find(item=>item.id===fixture.matchId);
assert.ok(match);assert.equal(match.property.ownerAccountType,'private');assert.equal(match.searchRequest.ownerAccountType,'private');assert.equal(match.property.id,fixture.propertyId);assert.equal(match.searchRequest.id,fixture.searchId);
assert.equal(match.property.address,'Private street 12');assert.equal(match.contact.id,fixture.sellerId);
assert.equal(match.property.wholeRooms,3);assert.equal(match.property.halfRooms,0);
assert.equal(match.property.secondaryHeatingType,'');assert.deepEqual(match.property.parkingTypes,[]);
assert.deepEqual(match.searchRequest.heatingTypes,[],'Historical matches must retain an unfiltered primary-heating selection');
assert.equal(match.messages.length,fixture.messageCount);
assert.ok(match.messages.some(item=>item.id===fixture.messageId&&item.text===fixture.messageText));
assert.ok(sellerMatches.some(item=>item.id===fixture.matchId&&item.messages.length===fixture.messageCount));
assert.equal(ledger.filter(item=>item.amount<0).length,1);
console.log('Schema upgrade preservation passed: private account defaults, owner labels, empty report receipts, original users, entities, Budapest XIII location, optional bounds, weighted rooms with derived whole/half breakdown, parking compatibility, empty secondary/search heating, credits, match, and message survived.');
