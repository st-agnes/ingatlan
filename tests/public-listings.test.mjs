import test from 'node:test';
import assert from 'node:assert/strict';
import {listingHref,parsePublicListingRoute,publicAuthorMarkup,publicSearchCard,publicPropertyCard,publicListingMarkup,publicListingError,visibleListingAddress,safeListingImages,listingContextMarkup,listingProfileOptionsMarkup} from '../dist/public-listings.js';
import {interestIconMarkup,decisionDockMarkup,INTEREST_SENT_MESSAGE} from '../dist/interest.js';

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
 assert.match(markup,/data-action="public-listing-back"/);assert.doesNotMatch(markup,/href="#discover"/);assert.match(markup,/data-action="public-listing-decision" data-liked="false"/);assert.match(markup,/data-liked="true"/);assert.match(markup,/Vegyük fel a kapcsolatot!<\/span><small>2 kredit/);
 assert.doesNotMatch(markup,/secret-contact|data-action="auth-mode"/);
 assert.equal((markup.match(/id="public-listing-profile"/g)||[]).length,1,'The active profile is mounted once');
 assert.ok(markup.indexOf('id="public-listing-profile"')>markup.indexOf('<h1>'),'The active profile replaces the CTA beneath the listing heading');
 assert.equal((markup.match(/data-action="public-listing-profiles"/g)||[]).length,1);
 assert.match(markup,/data-action="public-listing-new-profile" data-kind="search"/);
 assert.doesNotMatch(markup,/data-action="public-listing-profile-top"|Vissza az aktív profilodhoz/);
 assert.doesNotMatch(markup,/data-action="onboarding-start"/,'A relevant active profile replaces the generic creation CTA');
 assert.match(markup,/Nem az igazi/);assert.match(markup,/data-part="phone"/);assert.match(markup,/data-part="message"/);
 const ownProfile=listingContextMarkup(activeContext,{kind:'property'}),dock=markup.slice(markup.indexOf('</main>')+7);
 assert.match(ownProfile,/Kertre néző lakás &lt;jó&gt;/);assert.doesNotMatch(ownProfile,/data-action="public-listing-decision"/,'The active profile only owns its management controls');
 assert.match(dock,/public-listing-decision-dock public-listing-decisions/);assert.equal((dock.match(/data-action="public-listing-decision"/g)||[]).length,2);
 assert.doesNotMatch(markup,/Erről az ingatlanról döntesz|public-listing-target-response/);assert.match(markup,/<h1>Világos otthon<\/h1>/);assert.doesNotMatch(dock,/Világos otthon/,'The viewed listing title is not repeated above the dock');
 assert.match(publicListingMarkup(property,{signedIn:true,context:{...activeContext,compatibilityScore:0}}),/0% <span>egyezés/);
 assert.doesNotMatch(publicListingMarkup(property,{context:activeContext}),/public-listing-context|public-listing-decision/);
 assert.equal(listingContextMarkup({...activeContext,active:{...activeContext.active,kind:'property'}},{kind:'property'}),'');
});
test('prior decisions and mutual matches stay visible without allowing another charge',()=>{
 for(const [state,text] of [[{myDecision:'liked'},INTEREST_SENT_MESSAGE],[{myDecision:'passed'},'Ezt az ajánlatot már elutasítottad.'],[{matchId:'match-id'},'Már kapcsolatban vagytok.']]){
  const markup=publicListingMarkup(property,{signedIn:true,context:{...activeContext,...state}}),buttons=markup.match(/<button\b[^>]*data-action="public-listing-decision"[^>]*>/g)||[];
  assert.ok(markup.includes(text));assert.equal(buttons.length,2);assert.ok(buttons.every(button=>/ disabled>/.test(button)),'Both choices become read-only');
  const selected=buttons.filter(button=>/is-selected/.test(button));assert.equal(selected.length,1);assert.match(selected[0],/aria-pressed="true"/);assert.match(selected[0],new RegExp(`data-liked="${state.myDecision==='passed'?'false':'true'}"`));assert.match(markup,/Ezt választottad/);
 }
 const lowCredits=publicListingMarkup(property,{signedIn:true,context:{...activeContext,credits:1}});
 assert.match(lowCredits,/<button[^>]*data-liked="true"[^>]* disabled>/);assert.match(lowCredits,/<button[^>]*data-liked="false"[^>]*aria-pressed="false">/);
});
test('direct partial public listing decisions need no discovery consent or exact-first prompt',()=>{
 const partial={...activeContext,isExact:false,compatibilityScore:74,requiresApproximateConsent:true};
 for(const hasUnseenExact of [false,true]){
  const markup=publicListingMarkup(property,{signedIn:true,context:{...partial,hasUnseenExact}});
  assert.equal((markup.match(/data-action="public-listing-decision"/g)||[]).length,2);
  assert.doesNotMatch(markup,/data-action="public-listing-approximate"|Előbb nézd meg|Részleges találatok megjelenítése/);
 }
 for(const denied of [{compatible:false},{canDecide:false}])assert.doesNotMatch(publicListingMarkup(property,{signedIn:true,context:{...partial,...denied}}),/data-action="public-listing-decision"/);
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

test('interest presentation combines phone and message and preserves the requested sent copy',()=>{
 const markup=interestIconMarkup('large " contact');
 assert.equal((markup.match(/<svg\b/g)||[]).length,1);assert.equal((markup.match(/<path\b/g)||[]).length,2);
 assert.match(markup,/data-icon="contact"/);assert.match(markup,/data-part="phone"/);assert.match(markup,/data-part="message"/);
 assert.match(markup,/class="large &quot; contact"/);
 assert.equal(INTEREST_SENT_MESSAGE,'Elküldtük érdeklődésedet! Most a másik félen a sor, hogy felvegyétek a kapcsolatot.');
});
test('shared decision docks always offer the same two choices and escape listing metadata',()=>{
 const markup=decisionDockMarkup({likeAction:'incoming-like',passAction:'incoming-pass',data:{id:'unsafe" onclick="bad',kind:'search','invalid"':'ignored'},cost:2,decision:'passed',message:'<untrusted>'});
 assert.equal((markup.match(/<button\b/g)||[]).length,2);assert.equal((markup.match(/ disabled>/g)||[]).length,2);
 assert.match(markup,/decision is-selected[^>]*data-action="incoming-pass"[^>]*aria-pressed="true"/);assert.match(markup,/data-part="phone"/);assert.match(markup,/data-part="message"/);
 assert.match(markup,/data-id="unsafe&quot; onclick=&quot;bad"/);assert.doesNotMatch(markup,/data-invalid|<untrusted>|Részletek/);assert.match(markup,/&lt;untrusted&gt;/);
});
test('signed-in missing or wrong-kind active profiles offer selecting or creating the opposite kind',()=>{
 for(const context of [{unavailableReason:'no_active_profile',active:null,item:null},{unavailableReason:'opposite_profile_required',active:{kind:'property',title:'Másik ingatlan'},item:null}]){
  const markup=publicListingMarkup(property,{signedIn:true,context});
  assert.match(markup,/data-action="public-listing-profiles"/);assert.match(markup,/data-action="public-listing-new-profile" data-kind="search"/);
  assert.doesNotMatch(markup,/data-action="public-listing-decision"/);assert.doesNotMatch(markup,/data-action="auth-mode"/);
 }
 const protectedMarkup=publicListingMarkup(property,{signedIn:true,context:{unavailableReason:'own_listing',active:activeContext.active,item:null}});
 assert.doesNotMatch(protectedMarkup,/data-action="public-listing-decision"|data-action="public-listing-profiles"/);
});
test('search detail replacement preserves the separate search-cloning action',()=>{
 const detail={kind:'search',key:searchKey,sourceKey:searchKey,title:'Házat keresek',listing:{type:'Ház',locations:['Debrecen'],maxPrice:90}};
 const context={...activeContext,active:{kind:'property',id:'own-property',title:'Saját házam',type:'Ház',locations:['Debrecen'],price:80}};
 const markup=publicListingMarkup(detail,{signedIn:true,context});
 assert.match(markup,/Aktív ingatlanod/);assert.match(markup,/Saját házam/);assert.match(markup,/data-action="public-listing-new-profile" data-kind="property"/);
 assert.doesNotMatch(markup,/Erről a keresési igényről döntesz|public-listing-target-response/);assert.match(markup,/<h1>Házat keresek<\/h1>/);assert.equal((markup.match(/data-action="public-listing-decision"/g)||[]).length,2);
 assert.doesNotMatch(markup,/data-action="onboarding-start"/);assert.equal((markup.match(/data-action="onboarding-copy-search"/g)||[]).length,1);
});
test('profile choices show only the expected owned kind with each score, active state and pagination',()=>{
 const page={kind:'search',hasMore:true,items:[
  {profile:{kind:'search',id:'mine-1',title:'Pontos keresés <jó>',locations:['Debrecen'],maxPrice:75,minRooms:2},score:94,isActive:true,compatible:true},
  {profile:{kind:'search',id:'mine-2',title:'Másik keresés',locations:['Szeged']},score:0,isActive:false,compatible:false},
  {profile:{kind:'property',id:'wrong-kind',title:'Másik oldali profil'},score:100}
 ]};
 const markup=listingProfileOptionsMarkup(page);
 assert.equal((markup.match(/data-action="public-listing-select-profile"/g)||[]).length,2);
 assert.match(markup,/94%/);assert.match(markup,/0%/);assert.match(markup,/aria-pressed="true"/);assert.match(markup,/Aktív/);
 assert.match(markup,/Pontos keresés &lt;jó&gt;/);assert.doesNotMatch(markup,/wrong-kind|Másik oldali profil/);
 assert.match(markup,/data-action="public-listing-profiles-more"/);assert.match(markup,/data-action="public-listing-new-profile" data-kind="search"/);
 const busy=listingProfileOptionsMarkup(page,{switchingId:'mine-1'});assert.match(busy,/data-id="mine-1" aria-pressed="true" disabled/);assert.match(busy,/Profilváltás/);
});
test('profile picker errors remain text and unavailable pair gates do not offer activating a profile',()=>{
 const failure=listingProfileOptionsMarkup({kind:'property',items:[]},{error:'<img src=x onerror=alert(1)>'});
 assert.match(failure,/data-action="public-listing-profiles-retry"/);assert.match(failure,/role="alert"/);assert.doesNotMatch(failure,/<img/);assert.match(failure,/&lt;img/);
 for(const reason of ['own_listing','agent_pair_forbidden']){
  const markup=listingProfileOptionsMarkup({kind:'search',items:[],unavailableReason:reason});
  assert.doesNotMatch(markup,/data-action="public-listing-select-profile"|data-action="public-listing-new-profile"/);assert.match(markup,/data-action="close"/);
 }
});
