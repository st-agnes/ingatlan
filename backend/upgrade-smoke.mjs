import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';

// CI removes location/optional-attribute columns to simulate the initial release, then starts the API.
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
assert.equal(buyer.credits,fixture.expectedBuyerCredits);
assert.equal(seller.credits,fixture.expectedCredits);
assert.deepEqual(ledger,fixture.sellerLedger);
assert.deepEqual(sellerEntities.properties.map(item=>item.id).sort(),fixture.propertyIds);
assert.deepEqual(buyerEntities.searchRequests.map(item=>item.id).sort(),fixture.searchIds);
const property=sellerEntities.properties.find(item=>item.id===fixture.propertyId);
assert.ok(property);assert.equal(property.city,'Budapest');assert.equal(property.district,'XIII.');
assert.equal(property.locationId,'district:Budapest:13');assert.equal(property.location.id,'district:Budapest:13');
assert.equal(property.address,'Private street 12');assert.equal(property.lotArea,null);
for(const field of ['constructionAge','view','ceilingHeight','heatingType','energyRating','parkingType'])assert.equal(property[field],'',`Old property must have unset ${field}`);
for(const field of ['insulated','airConditioning','solarPanels'])assert.equal(property[field],null,`Old property must retain unknown ${field}`);
const search=buyerEntities.searchRequests.find(item=>item.id===fixture.searchId);
assert.ok(search);assert.deepEqual(search.locationIds,['district:Budapest:13']);
assert.equal(search.minPrice,null);assert.equal(search.maxArea,null);assert.equal(search.maxRooms,null);
for(const field of ['conditions','buildings','constructionAges','views','floors'])assert.deepEqual(search[field],[],`Old search must have no ${field} restriction`);
assert.equal(search.ceilingHeight,'');
const match=matches.find(item=>item.id===fixture.matchId);
assert.ok(match);assert.equal(match.property.id,fixture.propertyId);assert.equal(match.searchRequest.id,fixture.searchId);
assert.equal(match.property.address,'Private street 12');assert.equal(match.contact.id,fixture.sellerId);
assert.equal(match.messages.length,fixture.messageCount);
assert.ok(match.messages.some(item=>item.id===fixture.messageId&&item.text===fixture.messageText));
assert.ok(sellerMatches.some(item=>item.id===fixture.matchId&&item.messages.length===fixture.messageCount));
assert.equal(ledger.filter(item=>item.amount<0).length,1);
console.log('Schema upgrade preservation passed: original users, entities, Budapest XIII location, optional bounds, credits, match, and message survived.');
