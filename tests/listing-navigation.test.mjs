/** Focused routing and async-lifecycle checks for the full public listing view. */
import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs/promises';
import {listingHref,parsePublicListingRoute,publicListingMarkup,publicListingLoading,publicListingError,listingProfileOptionsMarkup} from '../dist/public-listings.js';
import * as interestHelpers from '../dist/interest.js';

const source=await fs.readFile(new URL('../dist/app.js',import.meta.url),'utf8');
const listingSource=source.slice(source.indexOf('let currentPublicListing='),source.indexOf('function toggleAccountTypeHelp('));
const key='property-'+'a'.repeat(64),route='#listing/property/'+key;
const detail={kind:'property',key,sourceKey:key,title:'A kiválasztott ingatlan',listing:{type:'Lakás',location:'Debrecen',price:70,area:60,rooms:2,images:[]}};
const pair={kind:'property',id:'target-property',pair:{propertyId:'target-property',searchId:'active-search'},isExact:true};
const context={available:true,active:{kind:'search',id:'active-search',title:'Az aktív keresésem',locations:['Debrecen'],maxPrice:90},item:pair,canDecide:true,compatible:true,isExact:true,compatibilityScore:100,credits:10,likeCost:2,myDecision:null,hasUnseenExact:false,requiresApproximateConsent:false};
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};};
function harness(overrides={}){
 const app={innerHTML:''},inserted=[],buttons=[{disabled:false},{disabled:false}],calls={render:[],decisions:[],toasts:[],push:[],replace:[],back:0,expired:[],credits:0,scroll:0,activations:[],profiles:[],editors:[],modals:[]};let modal=null;
 const ctx=vm.createContext({console,Promise,AbortController,location:{hash:route},session:'session-a',busy:false,state:{user:{id:'viewer'}},modalCleanup:null,incoming:[],incomingPage:null,workspaceCacheModel:null,workspaceCacheSession:null,imageIndex:0,page:'discover',tab:'recommended',feedbackPrompt:null,deferredFeedbackPrompt:null,matches:[],
  listingHref,parsePublicListingRoute,publicListingMarkup,publicListingLoading,publicListingError,listingProfileOptionsMarkup,...interestHelpers,
  document:{title:'',getElementById(id){if(id==='app')return app;if(id==='public-listing'&&app.innerHTML.includes('id="public-listing"'))return {insertAdjacentHTML:(_position,value)=>inserted.push(value)};return null;},querySelector:selector=>selector==='.modal'?modal:null,querySelectorAll:()=>buttons},
  model:{getState:async()=>({active:{kind:'search',id:'active-search'}}),decide:async(item,liked,options)=>{calls.decisions.push({item,liked,options});return {}; }},
  onboardingSessionKey:()=>ctx.session,sameActive:(a,b)=>a?.id===b?.id&&a?.kind===b?.kind,fetchPublicListing:async()=>detail,getListingContext:async()=>context,getListingProfiles:async(...args)=>{calls.profiles.push(args);return {kind:'search',items:[{profile:context.active,score:100,isExact:true,compatible:true,isActive:true},{profile:{...context.active,id:'second-search',title:'Másik keresésem'},score:73,isExact:false,compatible:true,isActive:false}],total:2,offset:0,limit:50,hasMore:false};},getListingMap:async()=>({kind:'property',available:true,locationIds:['city:Debrecen'],externalUrl:null}),
  toast:(...args)=>calls.toasts.push(args),expireSession:async message=>{calls.expired.push(message);ctx.model=null;},openModal:html=>{modal={innerHTML:html};calls.modals.push(modal);},closeModal:()=>{ctx.modalCleanup?.();ctx.modalCleanup=null;modal=null;},openEditor:(...args)=>calls.editors.push(args),ensureWorkspaceSession:()=>true,resetRecommendations:()=>{},markDiscoveryStale:()=>{},normalizeFeedbackPrompt:()=>null,openFeedbackPrompt:()=>{},openCreditsNeeded:()=>{calls.credits++;},celebrate:()=>{},scrollToNextRecommendation:()=>{calls.scroll++;},render:async options=>{calls.render.push(options);},changePage:async page=>{ctx.page=page;},getLocation:()=>null,icon:()=>'',esc:value=>String(value),
  run:async fn=>{const owner=ctx.model,session=ctx.session,origin=ctx.location.hash,release=()=>ctx.model===owner&&ctx.session===session;release.sameView=()=>release()&&ctx.location.hash===origin;release.closeModal=()=>{if(release())ctx.closeModal();};return fn(release);},
  history:{state:{otthonraListingReturn:'discover'},pushState(state,_title,url){this.state=state;calls.push.push({state,url});ctx.location.hash=url;},replaceState(state,_title,url){this.state=state;calls.replace.push({state,url});ctx.location.hash=url;},back(){calls.back++;}},window:{scrollTo:()=>{},location:{assign:url=>{calls.assigned=url;}}},...overrides});
 ctx.model.activate=async(kind,id)=>{calls.activations.push({kind,id});};
 vm.runInContext(listingSource+`;globalThis.listingTest={publicListingPage,openListingDetails,backFromListing,openListingMap,decidePublicListing,cancelPublicListingRequest,drawPublicListing,openListingProfiles,loadListingProfiles,selectListingProfile,openListingNewProfile,get picker(){return listingProfilePicker;},get view(){return publicListingView;},set view(value){publicListingView=value;}};`,ctx);
 return {ctx,api:ctx.listingTest,calls,app,buttons,inserted,setView(value={}){ctx.listingTest.view={route,detail,context,model:ctx.model,session:ctx.session,includeApproximate:false,...value};}};
}

test('a full listing uses its own pair and returns a discovery decision to discovery without consulting feed[0]',async()=>{
 const h=harness();h.setView();h.ctx.feed=[{pair:{propertyId:'wrong-first-property',searchId:'wrong-search'}}];
 await h.api.decidePublicListing(true);
 assert.equal(h.calls.decisions.length,1);assert.equal(h.calls.decisions[0].item,pair);assert.equal(h.calls.decisions[0].liked,true);assert.equal(Object.hasOwn(h.calls.decisions[0].options,'allowApproximate'),false);assert.equal(h.calls.decisions[0].options.resolveMatch,false);assert.equal(h.calls.decisions[0].options.listingKey,key);
 assert.equal(h.ctx.location.hash,'#discover');assert.equal(h.calls.replace[0].url,'#discover');assert.equal(h.ctx.page,'discover');assert.equal(h.ctx.tab,'recommended');assert.equal(h.api.view,null);
 assert.deepEqual(h.calls.toasts,[[interestHelpers.INTEREST_SENT_MESSAGE]]);
});

test('interest confirmation uses the same exact message when a match is created',async()=>{
 const h=harness();h.setView();h.ctx.model.decide=async()=>({match:{id:'matched-pair'}});
 await h.api.decidePublicListing(true);assert.deepEqual(h.calls.toasts,[[interestHelpers.INTEREST_SENT_MESSAGE]]);
});

test('a directly viewed partial listing is actionable even when unseen exact recommendations remain',async()=>{
 for(const hasUnseenExact of [false,true]){
  const h=harness(),partial={...context,isExact:false,item:{...pair,isExact:false},requiresApproximateConsent:true,hasUnseenExact};
  h.setView({context:partial});await h.api.decidePublicListing(false);
  assert.equal(h.calls.decisions.length,1,'Public details do not require the discovery partial-results opt-in');
  assert.equal(h.calls.decisions[0].item,partial.item);assert.equal(h.calls.decisions[0].options.listingKey,key,'The server validates the viewed listing against this exact pair');
  assert.equal(h.ctx.location.hash,'#discover');
 }
});

test('already handled listings, stale sessions and insufficient credits never submit another paid decision',async()=>{
 const h=harness();
 for(const changed of [{context:{...context,myDecision:'liked'}},{context:{...context,canDecide:false}},{contextError:true},{session:'old-session'},{route:'#listing/property/other'}]){h.setView(changed);await h.api.decidePublicListing(true);}
 assert.equal(h.calls.decisions.length,0);
 h.setView({context:{...context,credits:1}});await h.api.decidePublicListing(true);assert.equal(h.calls.credits,1);assert.equal(h.calls.decisions.length,0);
 await h.api.decidePublicListing(false);assert.equal(h.calls.decisions.length,1);assert.equal(h.calls.decisions[0].liked,false);
});

test('a decision completing after a route change does not pull the user back from another page',async()=>{
 const response=deferred(),h=harness();h.setView();h.ctx.model.decide=async(...args)=>{h.calls.decisions.push(args);return response.promise;};
 const pending=h.api.decidePublicListing(true);h.ctx.location.hash='#credits';response.resolve({});await pending;
 assert.equal(h.calls.decisions.length,1);assert.equal(h.ctx.location.hash,'#credits');assert.equal(h.calls.replace.length,0);assert.equal(h.calls.render.length,0);
});

test('stale listing loads cannot replace a newer route or authenticated account',async()=>{
 const load=deferred(),h=harness({fetchPublicListing:()=>load.promise});
 const pending=h.api.publicListingPage();h.ctx.location.hash='#landing';load.resolve(detail);assert.equal(await pending,false);assert.doesNotMatch(h.app.innerHTML,/A kiválasztott ingatlan/);
 const next=deferred();h.ctx.fetchPublicListing=()=>next.promise;h.ctx.location.hash=route;
 const other=h.api.publicListingPage();h.ctx.session='session-b';next.resolve(detail);assert.equal(await other,false);assert.doesNotMatch(h.app.innerHTML,/A kiválasztott ingatlan/);
});

test('same-route in-flight loads are scoped to the account session',async()=>{
 const old=deferred(),fresh=deferred();let loads=0;
 const h=harness({fetchPublicListing:()=>++loads===1?old.promise:fresh.promise});
 const first=h.api.publicListingPage();h.ctx.session='session-b';
 const second=h.api.publicListingPage();assert.equal(loads,2,'A new session must load its own context instead of reusing the old promise');
 fresh.resolve({...detail,title:'Az új fiók nézete'});assert.equal(await second,true);old.resolve(detail);assert.equal(await first,false);assert.match(h.app.innerHTML,/Az új fiók nézete/);
});

test('a concurrent active-profile change leaves public content visible but refuses an obsolete decision context',async()=>{
 const h=harness();h.ctx.model.getState=async()=>({active:{kind:'search',id:'new-active-search'}});
 assert.equal(await h.api.publicListingPage(),true);assert.equal(h.api.view.context,null);assert.equal(h.api.view.contextError,true);assert.ok(h.inserted.some(value=>value.includes('Újrapróbálom')));assert.match(h.app.innerHTML,/A kiválasztott ingatlan/);
 await h.api.decidePublicListing(true);assert.equal(h.calls.decisions.length,0);
});

test('expiry from either authenticated listing read ends the session instead of leaving actionable stale context',async()=>{
 for(const where of ['context','state']){
  const h=harness(),error=Object.assign(new Error('A munkamenet lejárt.'),{status:401});
  if(where==='context')h.ctx.getListingContext=async()=>{throw error;};else h.ctx.model.getState=async()=>{throw error;};
  assert.equal(await h.api.publicListingPage(),false);assert.equal(h.calls.expired.length,1);assert.equal(h.ctx.model,null);assert.doesNotMatch(h.app.innerHTML,/public-listing-decision/);
 }
});

test('a completed listing write from an older account session cannot navigate the newly selected account',async()=>{
 const response=deferred(),h=harness();h.setView();h.ctx.model.decide=async()=>response.promise;
 const pending=h.api.decidePublicListing(true);h.ctx.session='new-account-session';response.resolve({});await pending;
 assert.equal(h.calls.replace.length,0);assert.equal(h.calls.render.length,0);assert.equal(h.ctx.location.hash,route);
});

test('listing navigation records its origin and an explicit back action uses browser history',async()=>{
 const h=harness();h.ctx.location.hash='#incoming';h.api.openListingDetails({...pair,publicListingKey:key},'incoming');
 assert.equal(h.ctx.location.hash,route);assert.equal(h.calls.push.length,1);assert.equal(h.calls.push[0].state.otthonraListingReturn,'incoming');
 await h.api.backFromListing();assert.equal(h.calls.back,1);assert.equal(h.calls.render.length,1);
 h.ctx.history.state=null;await h.api.backFromListing();assert.equal(h.ctx.page,'discover');
});

test('map navigation keeps the listing return origin and exact-address external links are opened directly',async()=>{
 const h=harness();h.setView({map:{available:true,locationIds:['city:Debrecen'],externalUrl:null}});
 await h.api.openListingMap('property',key);assert.equal(h.ctx.location.hash,'#map-view/property/'+key);assert.equal(h.calls.push[0].state.otthonraMapReturn,route);assert.equal(h.calls.push[0].state.otthonraListingReturn,'discover');
 h.ctx.location.hash=route;h.setView({map:{available:true,locationIds:[],externalUrl:'https://www.google.com/maps/search/?api=1&query=Debrecen'}});
 await h.api.openListingMap('property',key);assert.match(h.calls.assigned,/google\.com\/maps/);assert.equal(h.calls.push.length,1);
});

test('an old-session map lookup cannot navigate or emit an error in a new session',async()=>{
 const lookup=deferred(),h=harness({getListingMap:()=>lookup.promise});
 const pending=h.api.openListingMap('property',key);h.ctx.session='session-b';lookup.reject(new Error('Old session request failed'));await pending;
 assert.equal(h.calls.toasts.length,0);assert.equal(h.calls.push.length,0);assert.equal(h.calls.assigned,undefined);
});

test('profile options are read-only until an offered opposite-kind profile is selected',async()=>{
 const h=harness();h.setView();await h.api.openListingProfiles();
 assert.equal(h.calls.profiles.length,1);assert.deepEqual(h.calls.profiles[0].slice(0,2),['property',key]);
 assert.equal(h.calls.profiles[0][2].offset,0);assert.equal(h.calls.profiles[0][2].limit,50);assert.ok(h.calls.profiles[0][2].signal instanceof AbortSignal);
 assert.match(h.api.picker.modal.innerHTML,/Másik keresésem/);assert.match(h.api.picker.modal.innerHTML,/73%/);assert.match(h.api.picker.modal.innerHTML,/100%/);
 await h.api.selectListingProfile('property','second-search');await h.api.selectListingProfile('search','not-offered');assert.equal(h.calls.activations.length,0);
 const picker=h.api.picker;h.ctx.closeModal();assert.equal(picker.controller.signal.aborted,true);assert.equal(h.calls.activations.length,0);assert.equal(h.api.picker,null);
 h.setView();await h.api.openListingProfiles();h.ctx.model.getState=async()=>({user:{id:'viewer'},active:{kind:'search',id:'second-search'}});h.ctx.getListingContext=async()=>({...context,active:{...context.active,id:'second-search',title:'Másik keresésem'},compatibilityScore:73,isExact:false});
 await h.api.selectListingProfile('search','second-search');
 assert.deepEqual(h.calls.activations,[{kind:'search',id:'second-search'}]);assert.equal(h.ctx.location.hash,route);assert.equal(h.api.view.context.active.id,'second-search');assert.equal(h.api.view.context.compatibilityScore,73);assert.equal(h.calls.decisions.length,0);assert.equal(h.api.picker,null);
});

test('profile pagination preserves earlier rows and never changes the active selection',async()=>{
 const h=harness();h.setView();let count=0;
 h.ctx.getListingProfiles=async(_kind,_key,options)=>{h.calls.profiles.push(options);return ++count===1?{kind:'search',items:[{profile:context.active,score:100,isExact:true,compatible:true,isActive:true}],total:51,offset:0,limit:50,hasMore:true}:{kind:'search',items:[{profile:{...context.active,id:'last-search',title:'Utolsó keresésem'},score:0,compatible:false,isExact:false,isActive:false}],total:51,offset:50,limit:50,hasMore:false};};
 await h.api.openListingProfiles();await h.api.loadListingProfiles(h.api.picker,true);
 assert.deepEqual(h.calls.profiles.map(value=>value.offset),[0,50]);assert.equal(h.api.picker.page.items.length,2);assert.match(h.api.picker.modal.innerHTML,/Utolsó keresésem/);assert.match(h.api.picker.modal.innerHTML,/0%/);assert.equal(h.calls.activations.length,0);assert.equal(h.calls.decisions.length,0);
});

test('profile reads completed after closing or leaving the page cannot reopen a stale picker',async()=>{
 for(const leave of ['close','route','session']){
  const reply=deferred(),h=harness({getListingProfiles:()=>reply.promise});h.setView();const pending=h.api.openListingProfiles(),picker=h.api.picker;
  if(leave==='close')h.ctx.closeModal();if(leave==='route')h.ctx.location.hash='#credits';if(leave==='session')h.ctx.session='next-session';
  const before=picker.modal.innerHTML;reply.resolve({kind:'search',items:[{profile:{...context.active,title:'STALE PROFILE'},score:100,compatible:true}],total:1,offset:0,limit:50,hasMore:false});await pending;
  assert.equal(picker.modal.innerHTML,before);assert.equal(h.calls.activations.length,0);assert.equal(h.calls.modals.length,1);
 }
});

test('profile activation completed after navigation or a session change cannot redraw the old detail',async()=>{
 for(const leave of ['route','session']){
  const h=harness(),write=deferred();h.setView();await h.api.openListingProfiles();h.ctx.model.activate=()=>write.promise;
  const pending=h.api.selectListingProfile('search','second-search');if(leave==='route')h.ctx.location.hash='#credits';else h.ctx.session='new-session';write.resolve();await pending;
  assert.equal(h.calls.render.length,0);assert.equal(h.app.innerHTML,'');assert.equal(h.calls.decisions.length,0);assert.equal(h.calls.push.length,0);
 }
});

test('creating a relevant profile autoactivates only the saved profile and refreshes the same detail',async()=>{
 const h=harness();h.setView();h.api.openListingNewProfile('property');assert.equal(h.calls.editors.length,0);
 h.api.openListingNewProfile('search');assert.equal(h.calls.editors.length,1);const [kind,id,options]=h.calls.editors[0];assert.equal(kind,'search');assert.equal(id,undefined);assert.equal(typeof options.afterSave,'function');assert.equal(h.calls.activations.length,0);
 h.ctx.model.getState=async()=>({user:{id:'viewer'},active:{kind:'search',id:'created-search'}});h.ctx.getListingContext=async()=>({...context,active:{...context.active,id:'created-search',title:'Új saját keresés'}});
 await options.afterSave({id:'created-search'});assert.deepEqual(h.calls.activations,[{kind:'search',id:'created-search'}]);assert.equal(h.ctx.location.hash,route);assert.equal(h.api.view.context.active.id,'created-search');assert.equal(h.calls.decisions.length,0);assert.equal(h.calls.push.length,0);
});

test('new-profile completion from a stale detail never activates a profile in a different route or account',async()=>{
 for(const leave of ['route','session']){
  const h=harness();h.setView();h.api.openListingNewProfile('search');const options=h.calls.editors[0][2];if(leave==='route')h.ctx.location.hash='#landing';else h.ctx.session='new-session';await options.afterSave({id:'created-search'});assert.equal(h.calls.activations.length,0);assert.equal(h.calls.render.length,0);
 }
});

test('own listings, forbidden agent pairs and signed-out viewers never open a protected profile picker',async()=>{
 const h=harness();for(const unavailableReason of ['own_listing','agent_pair_forbidden']){h.setView({context:{...context,unavailableReason}});await h.api.openListingProfiles();h.api.openListingNewProfile('search');}
 h.ctx.state=null;h.setView();await h.api.openListingProfiles();assert.equal(h.calls.profiles.length,0);assert.equal(h.calls.editors.length,0);assert.equal(h.calls.modals.length,0);
});
