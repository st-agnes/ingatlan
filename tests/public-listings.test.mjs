import test from 'node:test';
import assert from 'node:assert/strict';
import {listingHref,parsePublicListingRoute,publicAuthorMarkup,publicSearchCard,publicPropertyCard,publicListingMarkup,publicListingError,visibleListingAddress,safeListingImages,listingContextMarkup} from '../dist/public-listings.js';

const key='property-'+'a'.repeat(64),searchKey='search-'+'b'.repeat(64);
const property={kind:'property',key,sourceKey:key,title:'Világos otthon <szöveg>',ownerFirstName:'Anna',ownerAccountType:'private',listing:{
 title:'Világos otthon <szöveg>',type:'Lakás',location:'Debrecen',price:82.123456,area:72.5,rooms:2.5,wholeRooms:2,halfRooms:1,
 hideStreet:true,hideHouseNumber:true,street:'Titkos út',houseNumber:'99999',addressDetails:{latitude:47.53,longitude:21.62},
 description:'Világos és csendes otthon.\nNyugodt környék.',floor:0.5,buildingFloors:10,isAttic:false,balcony:false,airConditioning:true,privateGarden:null,
 insulated:false,solarPanels:false,energyRating:'B',energyRatingScheme:'2023',heatingType:'Gázkazán / cirkó',
 images:['https://example.test/one.jpg','https://example.test/two.jpg'],phone:'private-phone',email:'private-email',creationRequestHash:'private-hash',ownerId:'private-owner'
}};
test('public listing routes remain stable and reject unrelated or executable paths',()=>{
 assert.equal(listingHref('property',key),'#listing/property/'+key);
 assert.deepEqual(parsePublicListingRoute('#listing/search/'+searchKey),{kind:'search',key:searchKey});
 for(const route of ['#discover','#listing/user/a','#listing/property/a?b=x','#listing/property/%3Cscript%3E','#listing/property/'+ 'a'.repeat(101)])assert.equal(parsePublicListingRoute(route),null);
 assert.equal(listingHref('user',key),'');assert.equal(listingHref('property','javascript:alert(1)'),'');
});
test('street and house visibility are independent with street as the enclosing permission',()=>{
 const address={street:'Fő utca',houseNumber:'12',hideStreet:true,hideHouseNumber:false};
 assert.equal(visibleListingAddress(address),'');assert.equal(visibleListingAddress({...address,hideStreet:false,hideHouseNumber:true}),'Fő utca');
 assert.equal(visibleListingAddress({...address,hideStreet:false}),'Fő utca 12');assert.equal(visibleListingAddress({street:'Fő utca',houseNumber:'12'}),'');
});
test('author identity is an icon with an accessible explanation, never an inline account badge caption',()=>{
 const agent=publicAuthorMarkup({ownerFirstName:'Kata',ownerAccountType:'agent'}),privateOwner=publicAuthorMarkup({ownerFirstName:'Péter',ownerAccountType:'private'});
 assert.match(agent,/class="owner-first-name">Kata/);assert.match(agent,/aria-label="Ingatlanközvetítő"/);assert.match(agent,/data-account-help-panel role="tooltip">Ingatlanközvetítő/);
 assert.match(privateOwner,/aria-label="Magánszemély"/);assert.doesNotMatch(agent,/<button[^>]*>Ingatlanközvetítő/);
});
test('teaser cards use the actual title, a full-card destination and a separate prominent creation action',()=>{
 const markup=publicSearchCard({key:searchKey,sourceKey:searchKey,title:'Kertes otthont keresek',ownerFirstName:'Anna',locations:['Debrecen'],type:'Ház',maxPrice:95,minArea:85,minRooms:3});
 assert.match(markup,/h3 class="landing-ad-title">Kertes otthont keresek/);assert.match(markup,/href="#listing\/search\//);
 assert.match(markup,/data-action="onboarding-start" data-kind="property"/);assert.match(markup,/Ilyen ingatlanom van/);
 assert.doesNotMatch(markup,/Anna házat keres/);assert.match(markup,/listing-card-owner/);
});
test('property cards show a valid supplied photo and reject executable image schemes',()=>{
 const actual=publicPropertyCard({...property.listing,...property,image:'https://example.test/one.jpg'});
 assert.match(actual,/src="https:\/\/example.test\/one.jpg"/);assert.match(actual,/data-kind="search"/);
 const unsafe=publicPropertyCard({...property.listing,sourceKey:key,title:'Példa',image:'javascript:alert(1)',images:['data:text/html,secret']});
 assert.doesNotMatch(unsafe,/javascript:|data:text/);assert.match(unsafe,/Illusztráció/);
});
test('complete property pages retain all images and known negative amenities without leaking private fields',()=>{
 const markup=publicListingMarkup(property);
 for(const value of ['private-phone','private-email','private-hash','private-owner','Titkos út','99999','47.53','21.62'])assert.equal(markup.includes(value),false,value);
 assert.match(markup,/id="public-listing"/);assert.match(markup,/82\s?123\s?456/);assert.match(markup,/Magasföldszint/);assert.match(markup,/Fél szobák/);
 assert.match(markup,/Erkély<\/dt><dd>Nincs/);assert.match(markup,/Légkondi<\/dt><dd>Van/);assert.match(markup,/Szigetelés<\/dt><dd>Nincs/);
 assert.match(markup,/Világos otthon/);assert.doesNotMatch(markup,/<szöveg>/);assert.equal((markup.match(/https:\/\/example\.test\/one\.jpg/g)||[]).length,2);
 assert.match(markup,/https:\/\/example\.test\/two\.jpg/);assert.match(markup,/public-listing-gallery/);
});
test('public detail visibility cannot accidentally echo a hidden house number through legacy address fields',()=>{
 const detail={...property,listing:{...property.listing,hideStreet:false,hideHouseNumber:true,address:'Titkos út 99999'}};
 const markup=publicListingMarkup(detail);assert.match(markup,/Titkos út/);assert.doesNotMatch(markup,/99999/);
 assert.match(publicListingMarkup({...detail,listing:{...detail.listing,hideHouseNumber:false}}),/Titkos út 99999/);
});
test('complete search pages display every supplied criterion and offer selling or full search cloning',()=>{
 const detail={kind:'search',key:searchKey,sourceKey:searchKey,title:'Napfényes lakást keresek',ownerFirstName:'Péter',ownerAccountType:'agent',listing:{
 type:'Lakás',locations:[{label:'Debrecen Vénkert'}],maxPrice:95,minArea:55,minRooms:2.5,conditions:['Jó','Új/felújított'],floors:[0.5,8],
 atticPreference:'exclude',excludeTopFloor:true,elevator:true,heatingTypes:['Hőszivattyú'],minEnergyRating:'A+',balcony:true,airConditioning:true,
 moveIn:'3 hónapon belül',financing:'Saját forrás',description:'Fontos a csend.'}};
 const markup=publicListingMarkup(detail);
 for(const text of ['Debrecen Vénkert','Magasföldszint','8 vagy afölötti','Tetőtéri ingatlan kizárva','Zárószint kizárva','Hőszivattyú','Legalább A+','Saját forrás','Fontos a csend.'])assert.ok(markup.includes(text),text);
 assert.match(markup,/Ilyen ingatlanom van/);assert.match(markup,/Én is ilyet keresek/);assert.match(markup,/data-action="onboarding-copy-search"/);
});
test('image safety and missing listing fallbacks stay usable without authentication',()=>{
 assert.deepEqual(safeListingImages({images:['https://example.test/a.jpg','http://example.test/b.jpg','javascript:alert(1)']}),['https://example.test/a.jpg']);
 assert.match(publicListingError(true),/public-listing-error/);assert.match(publicListingError(true),/már nem elérhető/);
 assert.doesNotMatch(publicListingError(true),/data-action="public-listing-retry"/);assert.match(publicListingError(),/data-action="public-listing-retry"/);
});
test('demo detail pages retain every real local asset photo and the computed neighborhood',()=>{
 const detail={...property,listing:{...property.listing,neighborhood:'Vénkert',images:['/assets/living.jpg','/assets/kitchen.jpg','/assets/terrace.jpg']}};
 assert.equal(safeListingImages(detail.listing).length,3);
 const markup=publicListingMarkup(detail);for(const path of detail.listing.images)assert.ok(markup.includes(path));assert.match(markup,/Vénkert/);
 assert.doesNotMatch(markup,/public-listing-placeholder/);assert.deepEqual(safeListingImages({images:['/assets/../runtime-config.js']}),[]);
});

const activeContext={active:{kind:'search',id:'my-search',title:'Kertre néző lakás <jó>',locations:['Debrecen'],maxPrice:90,minArea:50,minRooms:2,phone:'secret-contact'},item:{pair:{propertyId:'property-id',searchId:'search-id'}},available:true,compatible:true,isExact:true,compatibilityScore:100,myDecision:null,matchId:null,likeCost:2,credits:10,canDecide:true,hasUnseenExact:false,requiresApproximateConsent:false};
test('signed-in detail pages show the authoritative active-profile score and available decision actions',()=>{
 const markup=publicListingMarkup(property,{signedIn:true,context:activeContext,returnPage:'discover'});
 assert.match(markup,/Aktív keresésed/);assert.match(markup,/Kertre néző lakás &lt;jó&gt;/);assert.match(markup,/100% <span>egyezés/);
 assert.match(markup,/data-action="public-listing-back"/);assert.match(markup,/data-action="public-listing-decision" data-liked="false"/);assert.match(markup,/data-liked="true"/);assert.match(markup,/Kapcsolatfelvétel<small>2 kredit/);
 assert.doesNotMatch(markup,/secret-contact|data-action="auth-mode"/);
 assert.match(publicListingMarkup(property,{signedIn:true,context:{...activeContext,compatibilityScore:0}}),/0% <span>egyezés/);
 assert.doesNotMatch(publicListingMarkup(property,{context:activeContext}),/public-listing-context|public-listing-decision/);
 assert.equal(listingContextMarkup({...activeContext,active:{...activeContext.active,kind:'property'}},{kind:'property'}),'');
});
test('prior decisions and mutual matches stay visible without allowing another charge',()=>{
 for(const [state,text] of [[{myDecision:'liked'},'Már kezdeményezted a kapcsolatfelvételt.'],[{myDecision:'passed'},'Ezt az ajánlatot már elutasítottad.'],[{matchId:'match-id'},'Már kapcsolatban vagytok.']]){
  const markup=listingContextMarkup({...activeContext,...state},{kind:'property'});
  assert.ok(markup.includes(text));assert.doesNotMatch(markup,/data-action="public-listing-decision"/);
 }
 const lowCredits=listingContextMarkup({...activeContext,credits:1},{kind:'property'});
 assert.match(lowCredits,/data-liked="true" disabled/);assert.match(lowCredits,/data-liked="false">/);
});
test('partial public listing decisions require consent and cannot jump ahead of unseen exact matches',()=>{
 const partial={...activeContext,isExact:false,compatibilityScore:74,requiresApproximateConsent:true};
 const prompt=listingContextMarkup(partial,{kind:'property'});
 assert.match(prompt,/data-action="public-listing-approximate"/);assert.doesNotMatch(prompt,/data-action="public-listing-decision"/);
 assert.match(listingContextMarkup(partial,{kind:'property',includeApproximate:true}),/data-action="public-listing-decision"/);
 const exactFirst=listingContextMarkup({...partial,hasUnseenExact:true},{kind:'property',includeApproximate:true});
 assert.match(exactFirst,/Előbb nézd meg/);assert.doesNotMatch(exactFirst,/data-action="public-listing-decision"|data-action="public-listing-approximate"/);
});
test('public locations link to the map only when a safe map descriptor is available',()=>{
 const linked=publicListingMarkup(property,{mapAvailable:true});assert.match(linked,/data-action="public-listing-map"/);assert.match(linked,/data-kind="property" data-key="property-/);
 for(const value of ['Titkos út','99999','47.53','21.62'])assert.equal(linked.includes(value),false,value);
 const streetSearch={kind:'search',key:searchKey,title:'Nádor utcában keresek',listing:{locations:['Budapest V. kerület, Nádor utca'],type:'Lakás'}};
 assert.doesNotMatch(publicListingMarkup(streetSearch,{mapAvailable:false}),/data-action="public-listing-map"/);
 assert.match(publicListingMarkup(streetSearch,{mapAvailable:true}),/data-action="public-listing-map"/);
});
test('detail creation actions are repeated at top and bottom without a redundant invitation heading',()=>{
 const markup=publicListingMarkup(property);assert.equal((markup.match(/data-action="onboarding-start"/g)||[]).length,2);assert.doesNotMatch(markup,/Ilyen otthont keresel\?/);
 const searchMarkup=publicListingMarkup({kind:'search',key:searchKey,listing:{type:'Lakás',minEnergyRating:'C'}});
 assert.equal((searchMarkup.match(/data-action="onboarding-copy-search"/g)||[]).length,2);assert.match(searchMarkup,/Minimum energetikai besorolás/);assert.doesNotMatch(searchMarkup,/Minimum energetikai tanúsítvány/);
});
test('floor alternatives and attic choices are described with their actual OR semantics',()=>{
 const markup=publicListingMarkup({kind:'search',key:searchKey,listing:{type:'Lakás',floors:[3],atticPreference:'only'}});
 assert.match(markup,/3\. emelet vagy tetőtér/);assert.doesNotMatch(markup,/Tetőtéri ingatlant keres|Csak tetőtéri/);
 assert.match(publicListingMarkup({kind:'search',key:searchKey,listing:{type:'Lakás',floors:[],atticPreference:'only'}}),/Csak tetőtéri ingatlan/);
});
