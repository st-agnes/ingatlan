/** Offline integration smoke tests with a minimal simulated DOM. These do not replace browser QA. */
import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs/promises';
import {createModel} from '../dist/model.js';
import {searchLocations,getLocation,resolveLegacyLocations,locations} from '../dist/locations.js';
import * as propertyAttributes from '../dist/attributes.js';
import * as accountHelpers from '../dist/accounts.js';
import * as feedbackHelpers from '../dist/feedback.js';
import * as onboardingHelpers from '../dist/onboarding.js';


const publicSourceKey=(kind,character='a')=>kind+'-'+character.repeat(64);
const landingRegions=[{id:'HU110',label:'Budapest'},{id:'HU321',label:'Hajdú-Bihar'},{id:'HU232',label:'Somogy'}];
function landingFixture(region){const selected=landingRegions.find(item=>item.id===region)||null;return {regions:landingRegions,region:selected,scope:selected?'region':'national',searches:region==='HU232'?[]:[{key:'s-public',sourceKey:publicSourceKey('search','b'),title:'Kertes otthont keresünk',ownerFirstName:'Anna',type:'Lakás',locations:[region==='HU321'?'Debrecen':'Budapest XIII. kerület'],minPrice:null,maxPrice:90,minArea:50,maxArea:null,minRooms:2,maxRooms:null,ownerAccountType:'private'}],properties:region==='HU232'?[]:[{key:'p-public',sourceKey:publicSourceKey('property','a'),title:'Napfényes erkélyes otthon',ownerFirstName:'Péter',type:'Lakás',location:region==='HU321'?'Debrecen':'Budapest',price:82,area:60,wholeRooms:2,halfRooms:1,rooms:2.5,lotArea:null,ownerAccountType:'agent'}]};}

const source=await fs.readFile(new URL('../dist/app.js',import.meta.url),'utf8');
const decodeHtmlValue=value=>String(value).replace(/&(?:amp|lt|gt|quot|apos|#(?:x[0-9a-f]+|\d+));/gi,encoded=>{
 const key=encoded.slice(1,-1).toLowerCase(),named={amp:'&',lt:'<',gt:'>',quot:'"',apos:"'"};
 if(!key.startsWith('#'))return named[key];const code=key[1]==='x'?parseInt(key.slice(2),16):Number(key.slice(1));return code>=0&&code<=0x10ffff?String.fromCodePoint(code):encoded;
});
class Element {
 constructor(id,doc,markup='') {
  this.id=id;this.doc=doc;this.markup=markup;this._innerHTML='';this.textContent='';
  this.tagName=(markup.match(/^<([a-z][\w-]*)/i)?.[1]||'div').toUpperCase();
  this.attributes=Object.fromEntries([...markup.split('>')[0].matchAll(/([\w-]+)="([^"]*)"/g)].map(match=>[match[1],decodeHtmlValue(match[2])]));
  this.dataset=new Proxy(Object.fromEntries(Object.entries(this.attributes).filter(([name])=>name.startsWith('data-')).map(([name,value])=>[name.slice(5).replace(/-([a-z])/g,(_match,letter)=>letter.toUpperCase()),value])),{set:(target,key,value)=>{target[key]=String(value);this.attributes['data-'+String(key).replace(/[A-Z]/g,letter=>'-'+letter.toLowerCase())]=String(value);return true;}});
  this.className=this.attributes.class||'';this.value=this.attributes.value||'';this.name=this.attributes.name||'';this.step=this.attributes.step||'';this.type=this.attributes.type||'';
  this.required=/\srequired(?:\s|>)/.test(markup);this.validity={badInput:false};
  if(markup.startsWith('<select')) {const option=[...markup.matchAll(/<option\b([^>]*)>([^<]*)/g)],selected=option.find(match=>/\bselected\b/.test(match[1]))||option[0];this.value=decodeHtmlValue(selected?.[1].match(/\bvalue="([^"]*)"/)?.[1]??selected?.[2]??'');}
  if(markup.startsWith('<textarea'))this.value=decodeHtmlValue(markup.match(/^[^>]*>([\s\S]*?)<\/textarea>/)?.[1]||'');
  this.checked=/\schecked(?:\s|>)/.test(markup);this.disabled=/\sdisabled(?:\s|>)/.test(markup);this.hidden=/\shidden(?:\s|>)/.test(markup);
  this.style={};this.handlers={};this.scrollHeight=500;this.scrollTop=0;this.validationMessage='';this.reportedValidity=0;
  this.classList={toggle:(name,on)=>{const classes=new Set(this.className.split(' ').filter(Boolean));if(on??!classes.has(name))classes.add(name);else classes.delete(name);this.className=[...classes].join(' ');},remove:name=>this.classList.toggle(name,false),add:name=>this.classList.toggle(name,true),contains:name=>this.className.split(' ').includes(name)};
 }
 set innerHTML(value){const previous=this._innerHTML;this._innerHTML=value;this.innerHTMLWasAssigned=true;if(['app','modal-root'].includes(this.id)){for(const match of previous.matchAll(/\bid=["']([^"']+)["']/g))if(!['app','modal-root','toast'].includes(match[1]))this.doc.elements.delete(match[1]);}else this.doc.replaceContents(this.id,value);if(this.id==='modal-root'){const markup=value.match(/<[^>]*class="modal(?:\s[^"]*)?"[^>]*>/)?.[0];this.doc.currentModal=markup?new Element('__modal-'+(++this.doc.modalSerial),this.doc,markup):null;if(this.doc.currentModal)this.doc.currentModal.isModal=true;}}
 get innerHTML(){return this._innerHTML;}
 addEventListener(type,handler){const prior=this.handlers[type];this.handlers[type]=prior?event=>{prior(event);return handler(event);}:handler;}
 querySelectorAll(selector){return this.doc.selectWithin(this,selector);}
 setAttribute(name,value){this.attributes[name]=String(value);if(name==='hidden')this.hidden=true;}
 getAttribute(name){return this.attributes[name]??null;}
 removeAttribute(name){delete this.attributes[name];if(name==='hidden')this.hidden=false;}
 setCustomValidity(message){this.validationMessage=message;}
 checkValidity(){
  if(this.disabled)return true;
  if(this.validationMessage||this.validity.badInput)return false;
  const value=String(this.value??'');
  if(this.required&&((this.type==='checkbox'||this.type==='radio')?!this.checked:!value))return false;
  if(!value)return true;
  if(this.type==='number'){
   const number=Number(value);if(!Number.isFinite(number))return false;
   const min=this.getAttribute('min'),max=this.getAttribute('max');if(min!==null&&number<Number(min)||max!==null&&number>Number(max))return false;
   const step=this.step==='any'?NaN:this.step?Number(this.step):1,base=min===null?0:Number(min);
   if(Number.isFinite(step)&&step>0&&Math.abs((number-base)/step-Math.round((number-base)/step))>1e-7)return false;
  }
  const minlength=this.getAttribute('minlength'),maxlength=this.getAttribute('maxlength');
  return !(minlength!==null&&value.length<Number(minlength)||maxlength!==null&&value.length>Number(maxlength));
 }
 reportValidity(){this.reportedValidity++;return this.checkValidity();}
 focus(){this.doc.activeElement=this;this.doc.focusEvents.push(this.id);}
 get offsetParent(){if(this.type==='hidden')return null;for(let node=this;node;node=node.parentElement)if(node.hidden||node.classList?.contains('hidden')||node.style?.display==='none')return null;return this.doc.getElementById('modal-root');}
 scrollIntoView(){}
 get parentElement(){return this.doc.parentOf(this.id);}
 contains(node){if(this.isModal)return this.doc.currentModal===this&&this.doc.getElementById(node?.id)===node&&this.doc.getElementById('modal-backdrop')?.contains(node)===true;for(let current=node;current;current=current.parentElement){if(current===this)return true;}return false;}
}

class Document {
 constructor(){this.visibilityState='visible';this.hidden=false;this.hasFocus=()=>!this.hidden;this.elements=new Map();this.handlers={};this.listeners=new Map();this.currentModal=null;this.modalSerial=0;this.focusEvents=[];for(const id of ['app','modal-root','toast'])this.elements.set(id,new Element(id,this));}
 get html(){return [...this.elements.entries()].filter(([id])=>['app','modal-root'].includes(id)).map(([,e])=>e.innerHTML).join('');}
 replaceContents(id,value){for(const rootId of ['app','modal-root']){const root=this.elements.get(rootId),html=root._innerHTML,opening=[...html.matchAll(/<([a-z][\w-]*)\b[^>]*>/gi)].find(match=>match[0].includes(`id="${id}"`)||match[0].includes(`id='${id}'`));if(!opening)continue;const start=opening.index+opening[0].length,tag=opening[1].toLowerCase();let depth=1,end=start;for(const token of html.slice(start).matchAll(new RegExp(`</?${tag}\\b[^>]*>`,'gi'))){depth+=token[0].startsWith('</')?-1:1;if(depth===0){end=start+token.index;break;}}const old=html.slice(start,end);for(const match of old.matchAll(/\bid=["']([^"']+)["']/g))this.elements.delete(match[1]);root._innerHTML=html.slice(0,start)+value+html.slice(end);return;}}
 getElementById(id){if(this.elements.has(id))return this.elements.get(id);const markup=this.html.match(new RegExp(`<[^>]*\\bid=["']${id}["'][^>]*>`))?.[0];if(!markup)return null;const full=markup.startsWith('<select')||markup.startsWith('<textarea')?this.html.match(new RegExp(`<${markup.startsWith('<select')?'select':'textarea'}[^>]*\\bid=["']${id}["'][^>]*>[\\s\\S]*?</${markup.startsWith('<select')?'select':'textarea'}>`))?.[0]||markup:markup;const element=new Element(id,this,full);this.elements.set(id,element);return element;}
 querySelector(selector){if(selector==='.modal')return this.currentModal;if(selector.startsWith('.modal '))return this.currentModal?.querySelectorAll(selector)[0]||null;if(selector.startsWith('#'))return this.getElementById(selector.slice(1).split(' ')[0]);return null;}
 selectWithin(root,selector){
  const selectors=selector.split(',').map(value=>value.trim().replace(/^\.modal\s+/,'')),markup=root.isModal?this.elements.get('modal-root').innerHTML:this.html,selected=[];
  for(const match of markup.matchAll(/<([a-z][\w-]*)\b[^>]*\bid="([^"]+)"[^>]*>/gi)){
   const element=this.getElementById(match[2]);if(!element||!root.isModal&&!root.contains(element))continue;
   if(selectors.some(value=>{const tag=value.match(/^[a-z]+/)?.[0];if(tag&&tag!==match[1].toLowerCase())return false;if(value.includes(':not(.modal-close)')&&element.classList.contains('modal-close'))return false;const type=value.match(/\[type="([^"]+)"\]/)?.[1];return !type||element.type===type;}))selected.push(element);
  }
  return selected;
 }

 parentOf(id){const stack=[],voidTags=new Set(['area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr']);for(const token of this.html.matchAll(/<\/?([a-z][\w-]*)\b[^>]*>/gi)){const tag=token[1].toLowerCase(),markup=token[0];if(markup.startsWith('</')){const index=stack.findLastIndex(item=>item.tag===tag);if(index>=0)stack.length=index;continue;}const currentId=markup.match(/\bid=["']([^"']+)["']/)?.[1];if(currentId===id){const parent=stack.findLast(item=>item.id);return parent?this.getElementById(parent.id):null;}if(!voidTags.has(tag)&&!markup.endsWith('/>'))stack.push({tag,id:currentId});}return null;}
 addEventListener(type,handler,options){const capture=typeof options==='boolean'?options:!!options?.capture,list=this.listeners.get(type)||[];if(!list.some(item=>item.handler===handler&&item.capture===capture))list.push({handler,capture});this.listeners.set(type,list);this.handlers[type]=event=>{const pending=[...(this.listeners.get(type)||[])].sort((a,b)=>Number(b.capture)-Number(a.capture)).map(item=>item.handler(event)).filter(value=>value?.then);return pending.length?Promise.all(pending):undefined;};}
 removeEventListener(type,handler,options){const capture=typeof options==='boolean'?options:!!options?.capture;this.listeners.set(type,(this.listeners.get(type)||[]).filter(item=>item.handler!==handler||item.capture!==capture));}
 listenerCount(type){return(this.listeners.get(type)||[]).length;}
}
async function setup(options={}){
 const storage={getItem:()=>options.initialRaw?JSON.stringify(options.initialRaw):null,setItem:()=>{}},demoModel=createModel(storage),document=new Document();
 // This minimal DOM fixture exercises the immediate legacy picker unless a
 // test explicitly opts into the async catalogue callbacks below.
 delete demoModel.findLocations;delete demoModel.findStreets;
 const apiModel=Object.assign({...demoModel},{mode:'api'},options.apiOverrides||{});
 if(options.apiOverrides?.feed&&!options.apiOverrides?.recommendations)apiModel.recommendations=async request=>{const items=await apiModel.feed(request);return {items,stage:items.length?'exact':'empty'};};
 let selected=options.hosted?(options.authenticated?apiModel:null):demoModel;
 const timers=[],connected=[],disconnected=[],landingCalls=[],windowEvents={},windowListeners=new Map(),regionStorage=new Map(Object.entries(options.regionStorage||{})),maps=[];
 let currentHash=options.hash??(options.hosted&&!options.authenticated?'#login':'');
 const ctx=vm.createContext({
  document,console,Intl,Date:options.Date||Date,Promise,URL,URLSearchParams,AbortController,IntersectionObserver:options.IntersectionObserver,setTimeout:(callback,delay)=>{if(options.captureTimers)timers.push({callback,delay});return timers.length;},clearTimeout:()=>{},
  location:{get hash(){return currentHash;},set hash(value){const next=value?(value.startsWith('#')?value:'#'+value):'';if(next===currentHash)return;currentHash=next;if(options.dispatchHashChanges)Promise.resolve().then(()=>windowEvents.hashchange?.());},search:'',origin:'https://test.example'},window:{scrollTo:()=>{},addEventListener:(type,handler)=>{const listeners=windowListeners.get(type)||[];listeners.push(handler);windowListeners.set(type,listeners);windowEvents[type]=event=>{const pending=[...(windowListeners.get(type)||[])].map(callback=>callback(event)).filter(value=>value?.then);return pending.length?Promise.all(pending):undefined;};}},
  OTTHONRA_CONFIG:options.hosted?{mode:'api',environment:options.environment||'test'}:{mode:'demo',environment:'local'},
  searchLocations,getLocation,resolveLegacyLocations,...propertyAttributes,...accountHelpers,...feedbackHelpers,...Object.fromEntries(Object.entries(onboardingHelpers).filter(([name])=>!['loadDraft','saveDraft','clearDraft'].includes(name))),
  loadDraft:()=>onboardingHelpers.loadDraft(ctx.localStorage),saveDraft:draft=>onboardingHelpers.saveDraft(draft,ctx.localStorage),clearDraft:id=>onboardingHelpers.clearDraft(id,ctx.localStorage),
  findPublicLocations:async(query,limit,options)=>searchLocations(query,limit,options),findPublicStreets:async()=>[],API_CONFIG_KEY:'otthonra.api',
  hostedMode:()=>!!options.hosted,deploymentEnvironment:()=>options.hosted?(options.environment||'test'):'local',
  getModel:()=>selected,
  __createLocationMap:(container,{selectedIds,onSelect})=>{const map={id:container.id,ids:[...selectedIds],disposed:false,select:onSelect,setSelection(ids){this.ids=[...ids];},destroy(){this.disposed=true;}};maps.push(map);return map;},
  fetchLanding:async(input={})=>{landingCalls.push(input);if(options.fetchLanding)return options.fetchLanding(input);return landingFixture(input.region);},
  detectLandingRegion:options.detectLandingRegion||(async()=>null),
  localStorage:{getItem:key=>regionStorage.get(key)||null,setItem:(key,value)=>regionStorage.set(key,value),removeItem:key=>regionStorage.delete(key)},
  disconnectApi:()=>{disconnected.push(true);selected=options.hosted?null:demoModel;return selected;},
  connectApi:async(...args)=>{connected.push(args);if(options.connectApi)await options.connectApi(...args);selected=apiModel;return apiModel;},
  FormData:class {constructor(form){this.values=form.values===undefined?mountedFormValues(document,form):Array.isArray(form.values)?form.values:Object.entries(form.values||{});}get(k){return this.values.find(([key])=>key===k)?.[1]}has(k){return this.values.some(([key])=>key===k)}[Symbol.iterator](){return this.values[Symbol.iterator]()}}
 });
 const body=source.replace(/^import[^\n]+\n/gm,'').replace("import('./location-map.js')",options.mockMaps?'Promise.resolve({createLocationMap: __createLocationMap})':"import('./location-map.js')");
 options.onDocument?.(document);
 await vm.runInContext(`(async()=>{${body}\nglobalThis.ui={render,changePage,startOnboarding,openEditor,openDetails,openModal,closeModal,openActivation,matchingTags,openFeedbackPackages,openFeedbackPurchase,openFeedbackPrompt,propertyInsightsPage,getFeedbackPrompt:()=>feedbackPrompt,getModelState:()=>state};})()`,ctx);
 const click=async(dataset)=>{const target={dataset,closest:()=>target};await document.handlers.click({target,preventDefault(){}})};
 return{model:options.hosted?apiModel:demoModel,document,ctx,click,ui:ctx.ui,connected,disconnected,getSelectedModel:()=>selected,landingCalls,regionStorage,windowEvents,timers,maps,runNextTimer:()=>timers.shift()?.callback(),runTimers:()=>{for(const timer of timers.splice(0))timer.callback();}};
}
const settle=async()=>{for(let i=0;i<16;i++)await Promise.resolve();};

const activeMap=(t,id)=>{const map=t.maps.findLast(item=>item.id===id&&!item.disposed);assert.ok(map,`Missing active map ${id}`);return map;};
const debrecenQuarter=name=>{const location=searchLocations(name,12).find(item=>item.kind==='neighborhood'&&item.city==='Debrecen'&&item.name===name);assert.ok(location,`Missing canonical ${name}`);return location;};

function chooseLocation(t,id){const input=t.document.getElementById('location-input');input.value=getLocation(id).label;input.handlers.input();const list=t.document.getElementById('location-options');assert.match(list.innerHTML,new RegExp(id.replaceAll('.','\\.')));const target={dataset:{locationId:id},closest:()=>target};list.handlers.click({target});}
function mountedFormValues(document,form){
 const values=[];
 for(const match of document.html.matchAll(/<(?:input|select|textarea)\b[^>]*\bid="([^"]+)"[^>]*>/g)){
  const input=document.getElementById(match[1]);
  if(!input?.name||!form.contains(input)||input.disabled)continue;
  let disabledByGroup=false;for(let parent=input.parentElement;parent&&parent!==form;parent=parent.parentElement)if(parent.disabled)disabledByGroup=true;
  if(disabledByGroup||['checkbox','radio'].includes(input.type)&&!input.checked)continue;
  values.push([input.name,input.type==='checkbox'?(input.value||'on'):input.value]);
 }
 return values;
}
function setEditorValues(t,values){
 const entries=Array.isArray(values)?values:Object.entries(values);
 for(const [name,value] of entries){
  const control=t.document.getElementById(name==='images'?'property-images':'f-'+name);
  if(control&&control.type!=='checkbox')control.value=String(value??'');
 }
 if(entries.some(([name])=>name==='title')){const title=t.document.getElementById('f-title');title?.handlers.input?.({target:title,currentTarget:title});}
 const type=t.document.getElementById('f-type');type?.handlers.change?.({target:type,currentTarget:type});
 for(const name of ['wholeRooms','halfRooms']){const control=t.document.getElementById('f-'+name);control?.handlers.input?.({target:control,currentTarget:control,inputType:'insertText'});}
}
function editorStep(t){return Array.from({length:5},(_value,index)=>t.document.getElementById('editor-step-'+index)).findIndex(step=>step&&!step.hidden);}
function editorAction(t,id){const button=t.document.getElementById(id);assert.ok(button,`Missing editor control ${id}`);assert.equal(button.disabled,false,`${id} must be enabled`);return button.handlers.click({target:button,currentTarget:button,preventDefault(){}});}
function submitEditor(t){const form=t.document.getElementById('entity-form');return form.handlers.submit({preventDefault(){},currentTarget:form});}
function submitEntity(t,values){
 const form=t.document.getElementById('entity-form');form.values=values;setEditorValues(t,values);
 if(!t.document.getElementById('editor-step-0')){submitEditor(t);return;}
 for(let attempts=0;attempts<5;attempts++){
  const before=editorStep(t);submitEditor(t);
  if(before===4||editorStep(t)===before)return;
 }
}

function key(input,key){const event={key,preventDefault(){this.defaultPrevented=true;},stopPropagation(){}};input.handlers.keydown(event);return event;}
const searchValues=title=>({title,type:'Lakás',minPrice:'',maxPrice:'90',minArea:'40',maxArea:'',minRooms:'2',maxRooms:'',moveIn:'Rugalmas'});
async function createSearch(t,title='Új keresési igény'){t.ui.openEditor('search');chooseLocation(t,'district:Budapest:13');submitEntity(t,searchValues(title));await settle();return t.model.getState().searches.find(item=>item.title===title);}
test('initial app renders recommendation without private contacts',async()=>{const t=await setup(),html=t.document.getElementById('app').innerHTML;assert.match(html,/page-heading/);assert.match(html,/A következő fejezeted/);assert.match(html,/72,9/);assert.equal(html.includes('peter@example.hu'),false);assert.equal(html.includes('+36 30 555 0141'),false);});
test('buyer like opens mutual-match dialog; seller activation and recommendation debit exactly two credits',async()=>{const t=await setup();await t.click({action:'like'});assert.match(t.document.getElementById('modal-root').innerHTML,/Egymásra találtatok/);assert.equal(t.model.getState().credits,24);await t.click({action:'activate-one',kind:'property',id:'own-p1'});assert.match(t.document.getElementById('app').innerHTML,/<span class="decision-like-caption"><span>Kedvelés<\/span><small>2 kredit<\/small>/);await t.click({action:'like'});assert.equal(t.model.getState().credits,22);assert.equal(t.model.getState().ledger.filter(x=>x.type==='seller_like').length,1);});
test('passing removes a candidate persistently from current feed',async()=>{const t=await setup(),id=t.model.feed()[0].id;await t.click({action:'pass'});assert.equal(t.model.feed().some(x=>x.id===id),false);assert.equal(t.model.getState().credits,24);});
test('every navigation page renders, settings inputs have unique IDs',async()=>{const t=await setup();for(const page of ['matches','messages','properties','searches','credits','settings']){await t.click({page});assert.doesNotMatch(t.document.getElementById('app').innerHTML,/Nem érhető el a munkatér/);}const html=t.document.getElementById('app').innerHTML;const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);assert.equal(new Set(ids).size,ids.length,'all IDs within settings must be unique');assert.match(html,/for="api-email"/);});
test('new search form creates a saved entity and profile form persists changes',async()=>{const t=await setup();await t.click({page:'searches'});await t.click({action:'new',kind:'search'});let form=t.document.getElementById('entity-form');chooseLocation(t,'district:Budapest:11');form.values={title:'Kertvárosi terveink',type:'Lakás',minPrice:'30',maxPrice:'65',minArea:'40',maxArea:'75',minRooms:'2',maxRooms:'4',description:'Zöld környezetben keresünk.',moveIn:'Rugalmas'};submitEntity(t,form.values);await settle();assert.equal(t.model.getState().searches.some(x=>x.title==='Kertvárosi terveink'),true);await t.click({page:'settings'});form=t.document.getElementById('profile-form');form.values={name:'Teszt Anna',email:'anna@test.hu',phone:'+36 30 123 4567'};form.handlers.submit({preventDefault(){},currentTarget:form});await settle();assert.equal(t.model.getState().user.name,'Teszt Anna');});
test('matched conversation accepts a message through the chat form',async()=>{const t=await setup();await t.click({action:'open-chat',id:'m1'});const form=t.document.getElementById('chat-form');form.values={message:'Vasárnap délután megfelel a megtekintés?'};form.handlers.submit({preventDefault(){},currentTarget:form});await settle();assert.equal(t.model.matches().find(m=>m.id==='m1').messages.at(-1).text,'Vasárnap délután megfelel a megtekintés?');assert.match(t.document.getElementById('app').innerHTML,/Vasárnap délután megfelel/);});
test('card resets drag transform when a horizontal gesture becomes vertical',async()=>{const t=await setup(),card=t.document.getElementById('candidate');const target={closest:s=>s==='#candidate'?card:null};t.document.handlers.pointerdown({target,clientX:0,clientY:0,pointerId:1});t.document.handlers.pointermove({clientX:40,clientY:0,pointerId:1});assert.notEqual(card.style.transform,'');t.document.handlers.pointermove({clientX:40,clientY:100,pointerId:1});assert.equal(card.style.transform,'');assert.equal(card.style.opacity,'');});


test('location picker selects multiple canonical towns, removes chips and accepts keyboard district selection',async()=>{const t=await setup();t.ui.openEditor('search');for(const name of ['Debrecen','Hajdúszoboszló','Hajdúsámson'])chooseLocation(t,`city:${name}`);let chips=t.document.getElementById('location-chips');assert.match(chips.innerHTML,/Hajdúszoboszló/);const target={dataset:{removeLocation:'city:Debrecen'},closest:()=>target};chips.handlers.click({target});assert.doesNotMatch(chips.innerHTML,/Debrecen/);const input=t.document.getElementById('location-input');input.value='Budapest V. kerület';input.handlers.input();key(input,'ArrowDown');assert.equal(input.getAttribute('aria-activedescendant'),'location-option-0');key(input,'Enter');assert.match(chips.innerHTML,/Budapest V\. kerület/);assert.equal(input.value,'');assert.equal(input.getAttribute('aria-expanded'),'false');submitEntity(t,{title:'Több helyen keresünk',type:'Lakás',minPrice:'',maxPrice:'100',minArea:'40',maxArea:'',minRooms:'2',maxRooms:'',moveIn:'Rugalmas'});await settle();const saved=t.model.getState().searches.find(x=>x.title==='Több helyen keresünk');assert.ok(saved);assert.deepEqual([...saved.locationIds],['city:Hajdúszoboszló','city:Hajdúsámson','district:Budapest:5']);for(const name of ['minPrice','maxArea','maxRooms'])assert.equal(saved[name],null);await t.click({page:'searches'});const html=t.document.getElementById('app').innerHTML;assert.match(html,/legalább 40 m²/);assert.match(html,/legfeljebb 100 M Ft/);assert.doesNotMatch(html,/NaN/);});
test('unselected typed location cannot save and Escape closes only autocomplete options',async()=>{const t=await setup();t.ui.openEditor('search');const input=t.document.getElementById('location-input');input.value='Debrceeen';input.handlers.input();assert.equal(key(input,'Escape').defaultPrevented,true);assert.equal(t.document.getElementById('location-options').hidden,true);assert.match(t.document.getElementById('modal-root').innerHTML,/entity-form/);submitEntity(t,{title:'Elírt hely',type:'Lakás',maxPrice:'100',minArea:'40',minRooms:'2'});await settle();assert.equal(t.model.getState().searches.some(x=>x.title==='Elírt hely'),false);assert.match(input.validationMessage,/Válassz/);chooseLocation(t,'city:Debrecen');assert.equal(input.validationMessage,'');});
test('property uses a single canonical location and house lot size toggles without replacing other fields',async()=>{const t=await setup();t.ui.openEditor('property');chooseLocation(t,'city:Solymár');chooseLocation(t,'city:Pilisvörösvár');const chips=t.document.getElementById('location-chips');assert.doesNotMatch(chips.innerHTML,/Solymár/);assert.match(chips.innerHTML,/Pilisvörösvár/);const title=t.document.getElementById('f-title');title.value='Családi ház';const type=t.document.getElementById('f-type'),lot=t.document.getElementById('f-lotArea'),wrapper=t.document.getElementById('lot-area-field');type.value='Ház';type.handlers.change({currentTarget:type});assert.equal(lot.disabled,false);assert.doesNotMatch(wrapper.className,/hidden/);assert.equal(title.value,'Családi ház');submitEntity(t,{street:'Teszt utca',houseNumber:'12/A',title:'Családi ház',type:'Ház',price:'95',area:'120',wholeRooms:'4',halfRooms:'0',floor:'0',lotArea:'650',images:'',condition:'Jó állapotú',building:'Tégla'});await settle();const saved=t.model.getState().properties.find(x=>x.title==='Családi ház');assert.ok(saved);assert.equal(saved.locationId,'city:Pilisvörösvár');assert.equal(saved.lotArea,650);await t.click({page:'properties'});assert.match(t.document.getElementById('app').innerHTML,/650 m² telek/);t.ui.openEditor('property',saved.id);const type2=t.document.getElementById('f-type');type2.value='Lakás';type2.handlers.change({currentTarget:type2});assert.equal(t.document.getElementById('f-lotArea').disabled,true);submitEntity(t,{street:'Teszt utca',houseNumber:'12/A',title:'Családi ház',type:'Lakás',price:'95',area:'120',wholeRooms:'4',halfRooms:'0',floor:'0',lotArea:'650',images:'',condition:'Jó állapotú',building:'Tégla'});await settle();assert.equal(t.model.getState().properties.find(x=>x.id===saved.id).lotArea,null);});

test('creating a search confirms the saved title and offers discovery without changing the active profile',async()=>{
 const t=await setup(),before=t.model.getState().active;
 const saved=await createSearch(t,'Kert <és> fény & nyugalom');
 assert.ok(saved);
 assert.deepEqual(t.model.getState().active,before);
 const dialog=t.document.getElementById('modal-root').innerHTML;
 assert.match(dialog,/Kert &lt;és&gt; fény &amp; nyugalom/);
 assert.doesNotMatch(dialog,/Kert <és>/);
 assert.match(dialog,/Ingatlanok felfedezése/);
 assert.match(dialog,/data-action="discover-search"/);
 assert.ok(dialog.includes(`data-id="${saved.id}"`));
 assert.match(dialog,/Később/);
});

test('dismissing a saved search confirmation keeps the search and the previous active profile',async()=>{
 const t=await setup(),before=t.model.getState().active;
 const saved=await createSearch(t);
 await t.click({action:'close'});
 assert.equal(t.document.getElementById('modal-root').innerHTML,'');
 assert.ok(t.model.getState().searches.some(item=>item.id===saved.id));
 assert.deepEqual(t.model.getState().active,before);
});

test('discovering a newly saved search waits for activation then opens its recommended properties',async()=>{
 const t=await setup();
 await t.click({action:'tab',tab:'liked'});
 await t.click({page:'searches'});
 const saved=await createSearch(t),before=t.model.getState().active;
 let release;
 const activation=new Promise(resolve=>{release=resolve;});
 const calls=[],activate=t.model.activate;
 t.model.activate=async(kind,id)=>{calls.push({kind,id});await activation;return activate(kind,id);};
 const clicked=t.click({action:'discover-search',id:saved.id});
 await settle();
 assert.deepEqual(calls,[{kind:'search',id:saved.id}]);
 assert.deepEqual(t.model.getState().active,before);
 assert.equal(t.ctx.location.hash,'#searches','navigation must wait for the API activation');
 assert.match(t.document.getElementById('modal-root').innerHTML,/Ingatlanok felfedezése/);
 release();
 await clicked;
 assert.deepEqual(t.model.getState().active,{kind:'search',id:saved.id});
 assert.equal(t.ctx.location.hash,'#discover');
 assert.equal(t.document.getElementById('modal-root').innerHTML,'');
 const html=t.document.getElementById('app').innerHTML;
 assert.match(html,/Neked ajánljuk/);
 assert.match(html,/Új keresési igény/);
 assert.match(html,/class="tab active" data-action="tab" data-tab="recommended"/);
 assert.match(html,/class="property-card"/);
 assert.ok(html.includes(t.model.feed()[0].title));
});

test('a failed activation leaves the saved-search discovery action available to retry',async()=>{
 const t=await setup(),before=t.model.getState().active;
 const saved=await createSearch(t);
 t.model.activate=async()=>{throw new Error('Az aktiválás nem sikerült.');};
 await t.click({action:'discover-search',id:saved.id});
 assert.deepEqual(t.model.getState().active,before);
 const dialog=t.document.getElementById('modal-root').innerHTML;
 assert.match(dialog,/Ingatlanok felfedezése/);
 assert.ok(dialog.includes(`data-id="${saved.id}"`));
 assert.match(t.document.getElementById('toast').textContent,/Az aktiválás nem sikerült/);
});

test('editing an existing search confirms the update without offering a new-search discovery dialog',async()=>{
 const t=await setup(),before=t.model.getState();
 t.ui.openEditor('search','own-s1');
 submitEntity(t,searchValues('Átgondolt keresési igény'));
 await settle();
 assert.equal(t.model.getState().searches.length,before.searches.length);
 assert.equal(t.model.getState().searches.find(item=>item.id==='own-s1').title,'Átgondolt keresési igény');
 assert.deepEqual(t.model.getState().active,before.active);
 assert.equal(t.document.getElementById('modal-root').innerHTML,'');
 assert.match(t.document.getElementById('toast').textContent,/módosításokat elmentettük/);
});

test('a failed new search save keeps its editor data and reports the failure',async()=>{
 const t=await setup(),count=t.model.getState().searches.length;
 t.ui.openEditor('search');
 chooseLocation(t,'city:Debrecen');
 const form=t.document.getElementById('entity-form');
 t.model.saveEntity=async()=>{throw new Error('A mentés most nem érhető el.');};
 submitEntity(t,searchValues('Ezt még nem mentettük el'));
 await settle();
 assert.equal(t.model.getState().searches.length,count);
 assert.equal(t.document.getElementById('entity-form'),form);
 assert.equal(form.values.title,'Ezt még nem mentettük el');
 assert.match(t.document.getElementById('location-chips').innerHTML,/Debrecen/);
 assert.doesNotMatch(t.document.getElementById('modal-root').innerHTML,/data-action="discover-search"/);
 assert.match(t.document.getElementById('toast').textContent,/A mentés most nem érhető el/);
 assert.match(t.document.getElementById('toast').className,/error/);
});

test('clicking outside location suggestions dismisses them without changing the typed query or selected towns',async()=>{
 const t=await setup();
 t.ui.openEditor('search');
 chooseLocation(t,'city:Debrecen');
 const input=t.document.getElementById('location-input'),list=t.document.getElementById('location-options');
 input.value='Pilis';input.handlers.input();
 assert.equal(list.hidden,false);
 assert.equal(input.value,'Pilis');
 t.document.handlers.pointerdown({target:input,clientX:0,clientY:0,pointerId:1});
 assert.equal(list.hidden,false,'pressing the input must not dismiss its own suggestions');
 t.document.handlers.pointerdown({target:t.document.getElementById('f-title'),clientX:0,clientY:0,pointerId:1});
 assert.equal(list.hidden,true);
 assert.equal(input.getAttribute('aria-expanded'),'false');
 assert.equal(input.value,'Pilis');
 assert.match(t.document.getElementById('location-chips').innerHTML,/Debrecen/);
 input.handlers.focus();
 assert.equal(list.hidden,false);
 chooseLocation(t,'city:Pilisvörösvár');
 assert.match(t.document.getElementById('location-chips').innerHTML,/Debrecen/);
 assert.match(t.document.getElementById('location-chips').innerHTML,/Pilisvörösvár/);
});

test('moving focus outside a property picker dismisses suggestions and preserves unselected text',async()=>{
 const t=await setup();
 t.ui.openEditor('property');
 const input=t.document.getElementById('location-input'),list=t.document.getElementById('location-options');
 input.value='Solym';input.handlers.input();
 assert.equal(list.hidden,false);
 t.document.handlers.focusin({target:t.document.getElementById('f-title')});
 assert.equal(list.hidden,true);
 assert.equal(input.value,'Solym');
 assert.equal(t.document.getElementById('location-chips').innerHTML,'');
 input.handlers.focus();
 assert.equal(list.hidden,false);
 chooseLocation(t,'city:Solymár');
 assert.match(t.document.getElementById('location-chips').innerHTML,/Solymár/);
});

test('closing or replacing the editor removes its outside-picker document listeners',async()=>{
 const t=await setup(),pointerListeners=t.document.listenerCount('pointerdown'),focusListeners=t.document.listenerCount('focusin');
 t.ui.openEditor('search');
 assert.equal(t.document.listenerCount('pointerdown'),pointerListeners+1);
 assert.equal(t.document.listenerCount('focusin'),focusListeners+1);
 t.ui.openEditor('property');
 assert.equal(t.document.listenerCount('pointerdown'),pointerListeners+1);
 assert.equal(t.document.listenerCount('focusin'),focusListeners+1);
 t.ui.closeModal();
 assert.equal(t.document.listenerCount('pointerdown'),pointerListeners);
 assert.equal(t.document.listenerCount('focusin'),focusListeners);
});

function submitHostedAuth(t,values){
 const form=t.document.getElementById('hosted-auth-form');
 assert.ok(form,'a hosted authentication form must be available');
 form.values=values;
 return form.handlers.submit({preventDefault(){},currentTarget:form});
}
const hostedCredentials={email:'anna@test.example',password:'HostedTestPassword2026!'};
const apiError=(message,status)=>Object.assign(new Error(message),{status});

test('hosted visitors can open labelled login without a demo workspace or API address selector',async()=>{
 const t=await setup({hosted:true});
 const html=t.document.getElementById('app').innerHTML;
 assert.match(html,/Tesztkörnyezet/);
 assert.match(html,/Jelentkezz be az Otthonrába/);
 assert.ok(t.document.getElementById('hosted-auth-form'));
 assert.ok(t.document.getElementById('f-email'));
 assert.ok(t.document.getElementById('f-password'));
 assert.doesNotMatch(html,/name="baseUrl"|api-form|Demó munkatér|Vissza a demóhoz|A következő fejezeted/);
 assert.equal(t.getSelectedModel(),null);
});

test('hosted login uses the current origin and waits for authentication before opening the API workspace',async()=>{
 let release;
 const login=new Promise(resolve=>{release=resolve;});
 const t=await setup({hosted:true,connectApi:()=>login});
 const submitted=submitHostedAuth(t,hostedCredentials);
 await settle();
 assert.equal(t.connected.length,1);
 assert.deepEqual(t.connected[0].slice(0,3),['https://test.example',hostedCredentials.email,hostedCredentials.password]);
 assert.equal(t.getSelectedModel(),null);
 assert.ok(t.document.getElementById('hosted-auth-form'),'the login page must remain while the API is pending');
 release();await submitted;await settle();
 assert.equal(t.getSelectedModel(),t.model);
 const html=t.document.getElementById('app').innerHTML;
 assert.match(html,/Tesztkörnyezet/);
 assert.match(html,/page-heading/);
 assert.doesNotMatch(html,/Demó munkatér|Vissza a demóhoz/);
});

test('hosted registration sends profile details to the same-origin API without server selection',async()=>{
 const t=await setup({hosted:true});
 await t.click({action:'auth-mode',mode:'register'});
 const html=t.document.getElementById('app').innerHTML;
 assert.match(html,/Hozd létre a fiókodat/);
 assert.ok(t.document.getElementById('f-name'));
 assert.ok(t.document.getElementById('f-phone'));
 assert.doesNotMatch(html,/name="baseUrl"/);
 await submitHostedAuth(t,{...hostedCredentials,name:'Új Teszt Anna',phone:'+36 30 123 4567'});await settle();
 assert.equal(t.connected.length,1);
 assert.equal(t.connected[0][0],'https://test.example');
 assert.deepEqual(JSON.parse(JSON.stringify(t.connected[0][3])),{name:'Új Teszt Anna',phone:'+36 30 123 4567',accountType:'private'});
 assert.equal(t.getSelectedModel(),t.model);
});

test('failed hosted authentication stays on the form and reports the failure without opening demo data',async()=>{
 const t=await setup({hosted:true,connectApi:async()=>{throw apiError('Hibásak a bejelentkezési adatok.',401);}});
 await submitHostedAuth(t,hostedCredentials);await settle();
 assert.equal(t.getSelectedModel(),null);
 assert.ok(t.document.getElementById('hosted-auth-form'));
 const error=t.document.getElementById('auth-error');
 assert.ok(error);assert.match(error.textContent,/Hibásak a bejelentkezési adatok/);
 assert.doesNotMatch(t.document.getElementById('app').innerHTML,/Demó munkatér|A következő fejezeted/);
});

test('hosted settings omit the developer API selector and explicit logout returns to the public landing',async()=>{
 const t=await setup({hosted:true,authenticated:true});
 await t.click({page:'settings'});
 const settings=t.document.getElementById('app').innerHTML;
 assert.match(settings,/Kijelentkezés/);
 assert.doesNotMatch(settings,/id="api-form"|name="baseUrl"|vissza a demóhoz/i);
 await t.click({action:'disconnect'});
 assert.equal(t.getSelectedModel(),null);
 assert.equal(t.disconnected.length,1);
 assert.equal(t.ctx.location.hash,'#landing');
 assert.equal(t.document.getElementById('hosted-auth-form'),null);
 assert.ok(t.document.getElementById('landing-region'));
 assert.match(t.document.getElementById('app').innerHTML,/landing-search-card/);
 assert.doesNotMatch(t.document.getElementById('app').innerHTML,/sidebar|Demó munkatér/);
 assert.ok(t.landingCalls.length>0,'Explicit logout loads the anonymous public preview');
 await t.click({action:'auth-mode',mode:'login'});
 assert.equal(t.ctx.location.hash,'#login');assert.ok(t.document.getElementById('hosted-auth-form'));
});

test('an expired hosted session detected during workspace loading clears the session and requests login',async()=>{
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{getState:async()=>{throw apiError('A munkameneted lejárt.',401);}}});
 assert.equal(t.getSelectedModel(),null);
 assert.equal(t.disconnected.length,1);
 const html=t.document.getElementById('app').innerHTML;
 assert.ok(t.document.getElementById('hosted-auth-form'));
 assert.match(html,/lejárt/);
 assert.doesNotMatch(html,/Vissza a demóhoz|Demó munkatér/);
});

test('an expired hosted session during an action also returns to login without switching to the local demo',async()=>{
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{decide:async()=>{throw apiError('A munkameneted lejárt.',401);}}});
 await t.click({action:'pass'});
 assert.equal(t.getSelectedModel(),null);
 assert.ok(t.document.getElementById('hosted-auth-form'));
 assert.match(t.document.getElementById('app').innerHTML,/lejárt/);
 assert.doesNotMatch(t.document.getElementById('app').innerHTML,/Vissza a demóhoz|Demó munkatér/);
});

test('a hosted API outage offers retry and keeps the authenticated API mode instead of substituting demo data',async()=>{
 const fixture=createModel({getItem:()=>null,setItem:()=>{}}).getState();
 let attempts=0;
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{getState:async()=>{if(++attempts===1)throw apiError('A szerver átmenetileg nem érhető el.',503);return fixture;}}});
 const failed=t.document.getElementById('app').innerHTML;
 assert.match(failed,/A szerver átmenetileg nem érhető el/);
 assert.match(failed,/data-action="retry"/);
 assert.doesNotMatch(failed,/Vissza a demóhoz|Demó munkatér|A következő fejezeted/);
 assert.equal(t.getSelectedModel(),t.model);
 assert.equal(t.disconnected.length,0);
 await t.click({action:'retry'});
 assert.equal(t.getSelectedModel(),t.model);
 assert.match(t.document.getElementById('app').innerHTML,/page-heading/);
 assert.match(t.document.getElementById('app').innerHTML,/Tesztkörnyezet/);
});

test('hosted test credits use the server method and wait for its persisted balance before confirming success',async()=>{
 const persisted=createModel({getItem:()=>null,setItem:()=>{}}).getState();
 const before=persisted.credits,calls=[];
 let release;
 const granted=new Promise(resolve=>{release=resolve;});
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{
  getState:async()=>JSON.parse(JSON.stringify(persisted)),
  buyDemoCredits:async amount=>{calls.push(amount);await granted;persisted.credits+=amount;persisted.ledger.unshift({id:'server-test-grant',amount,description:'Szerveren mentett tesztfeltöltés',createdAt:'2026-11-03T10:00:00Z'});return{credits:persisted.credits};}
 }});
 await t.click({page:'credits'});
 const credits=t.document.getElementById('app').innerHTML;
 assert.match(credits,/Tesztkreditek feltöltése/);
 assert.doesNotMatch(credits,/Demófeltöltés|Stripe|data-action="checkout"|1 990|4 990|9 990/);
 await t.click({action:'buy',amount:'50'});
 assert.match(t.document.getElementById('modal-root').innerHTML,/Ez ingyenes/);
 const clicked=t.click({action:'confirm-test-credits',amount:'50'});
 await settle();
 assert.deepEqual(calls,[50]);
 assert.equal(persisted.credits,before,'credits must not be changed before the API grant succeeds');
 assert.match(t.document.getElementById('modal-root').innerHTML,/Tesztkreditek hozzáadása/);
 release();await clicked;
 assert.equal(persisted.credits,before+50);
 assert.equal(t.document.getElementById('modal-root').innerHTML,'');
 const updated=t.document.getElementById('app').innerHTML;
 assert.match(updated,new RegExp(`${before+50} <small>tesztkredit`));
 assert.match(updated,/Szerveren mentett tesztfeltöltés/);
 assert.match(t.document.getElementById('toast').textContent,/tesztkrediteket jóváírtuk/);
});

test('a rejected hosted test-credit grant preserves the balance and confirmation instead of reporting success',async()=>{
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{buyDemoCredits:async()=>{throw apiError('A tesztfeltöltés most nem sikerült.',503);}}});
 const before=t.model.getState();
 await t.click({page:'credits'});
 await t.click({action:'buy',amount:'20'});
 await t.click({action:'confirm-test-credits',amount:'20'});
 assert.equal(t.model.getState().credits,before.credits);
 assert.equal(t.model.getState().ledger.length,before.ledger.length);
 assert.match(t.document.getElementById('modal-root').innerHTML,/Tesztkreditek hozzáadása/);
 assert.match(t.document.getElementById('toast').textContent,/A tesztfeltöltés most nem sikerült/);
 assert.doesNotMatch(t.document.getElementById('toast').textContent,/jóváírtuk/);
});


test('new property attributes are optional and unknown floor or amenities do not become false defaults',async()=>{
 const t=await setup();t.ui.openEditor('property');
 const html=t.document.getElementById('modal-root').innerHTML;
 for(const name of ['condition','building','constructionAge','view','ceilingHeight','floor','insulated','airConditioning','solarPanels']){
  const select=html.match(new RegExp(`<select id="f-${name}"[^>]*>([\\s\\S]*?)</select>`))?.[1];
  assert.ok(select,`${name} select must be present`);
  assert.match(select,/<option value="" selected>Nincs megadva<\/option>/);
 }
 assert.match(html,/<select id="f-heatingType"/);assert.match(html,/<select id="f-secondaryHeatingType"/);assert.match(html,/>Nincs fűtés<\/option>/);assert.equal((html.match(/name="parkingTypes"/g)||[]).length,propertyAttributes.PARKING_OPTIONS.length);
 chooseLocation(t,'city:Solymár');
 submitEntity(t,{street:'Teszt utca',houseNumber:'12/A',title:'Opcionális jellemzők',type:'Lakás',price:'82',area:'64',wholeRooms:'3',halfRooms:'0',floor:'',condition:'',building:'',constructionAge:'',view:'',ceilingHeight:'',insulated:'',airConditioning:'',solarPanels:'',images:''});
 await settle();
 const saved=t.model.getState().properties.find(item=>item.title==='Opcionális jellemzők');
 assert.ok(saved);
 for(const name of ['floor','insulated','airConditioning','solarPanels'])assert.equal(saved[name],null,name);
 for(const name of ['condition','building','constructionAge','view','ceilingHeight'])assert.equal(saved[name],'',name);
});

test('search checkboxes serialize several choices per category and can all be cleared',async()=>{
 const t=await setup();t.ui.openEditor('search');chooseLocation(t,'district:Budapest:13');
 const html=t.document.getElementById('modal-root').innerHTML;
 assert.match(html,/<fieldset id="conditions-group" class="attribute-group"><legend>Állapot/);
 assert.match(html,/Többet is megjelölhetsz/);
 assert.equal((html.match(/name="buildings"/g)||[]).length,12);
 submitEntity(t,[...Object.entries(searchValues('Részletes keresés')),['conditions','Jó'],['conditions','Új/felújított'],['buildings','Tégla'],['buildings','Panel'],['constructionAges','10 évnél fiatalabb'],['constructionAges','10–30 év közötti'],['views','Kertre néző'],['views','Panorámás'],['ceilingHeight','3 m feletti'],['floors','-1'],['floors','0'],['floors','11']]);
 await settle();
 let saved=t.model.getState().searches.find(item=>item.title==='Részletes keresés');assert.ok(saved);
 assert.deepEqual([...saved.conditions],['Jó','Új/felújított']);assert.deepEqual([...saved.buildings],['Tégla','Panel']);
 assert.deepEqual([...saved.constructionAges],['10 évnél fiatalabb','10–30 év közötti']);assert.deepEqual([...saved.views],['Kertre néző','Panorámás']);
 assert.deepEqual([...saved.floors],[-1,0,11]);assert.equal(saved.ceilingHeight,'3 m feletti');
 t.ui.openEditor('search',saved.id);
 const edited=t.document.getElementById('modal-root').innerHTML;
 assert.match(edited,/name="conditions" value="Jó" checked/);assert.match(edited,/name="floors" value="-1" checked/);
 submitEntity(t,searchValues('Részletes keresés'));await settle();
 saved=t.model.getState().searches.find(item=>item.id===saved.id);
 for(const name of ['conditions','buildings','constructionAges','views','heatingTypes','floors'])assert.equal(saved[name].length,0,name);
 assert.equal(saved.ceilingHeight,'');
});

test('seller inputs preserve explicit no, unknown amenities and existing higher floor values',async()=>{
 const t=await setup();t.ui.openEditor('property');chooseLocation(t,'district:Budapest:13');
 submitEntity(t,{street:'Teszt utca',houseNumber:'12/A',title:'Részletes eladó lakás',type:'Lakás',price:'78',area:'65',wholeRooms:'3',halfRooms:'0',floor:'12',condition:'Jó',building:'Csúsztatott zsalu',constructionAge:'31–40 év közötti',view:'Panorámás',ceilingHeight:'3 m feletti',heatingType:'Hőszivattyú',secondaryHeatingType:'Klíma',energyRating:'A+',parkingTypes:'Mélygarázs',insulated:'false',airConditioning:'true',solarPanels:'',images:''});await settle();
 const saved=t.model.getState().properties.find(item=>item.title==='Részletes eladó lakás');assert.ok(saved);
 assert.equal(saved.floor,12);assert.equal(saved.insulated,false);assert.equal(saved.airConditioning,true);assert.equal(saved.solarPanels,null);
 assert.equal(saved.building,'Csúsztatott zsalu');assert.equal(saved.energyRating,'A+');
 t.ui.openEditor('property',saved.id);
 const html=t.document.getElementById('modal-root').innerHTML;
 assert.match(html,/<option value="12" selected>12\. emelet<\/option>/);
 assert.match(html,/<option value="false" selected>Nem<\/option>/);
 assert.match(html,/value="Hőszivattyú" selected/);
});

test('candidate details show chosen attributes and amenities without inventing an unknown floor',async()=>{
 const item={id:'detail-p',kind:'property',title:'Részletes jelölt',city:'Budapest',locationId:'district:Budapest:13',type:'Lakás',price:75,area:60,rooms:3,condition:'Felújított',building:'Tégla',floor:null,constructionAge:'10–30 év közötti',view:'Kertre néző',ceilingHeight:'3 m alatti',heatingType:'Hőszivattyú',insulated:false,energyRating:'A+',airConditioning:true,solarPanels:null,parkingType:'Fedett beálló',images:[]};
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{feed:async()=>[item]}});
 let html=t.document.getElementById('app').innerHTML;assert.doesNotMatch(html,/Földszint|0\. emelet/);
 t.ui.openDetails();html=t.document.getElementById('modal-root').innerHTML;
 for(const value of ['Új/felújított','Kertre néző','10–30 év közötti','3 m alatti','Hőszivattyú','Fedett beálló','Szigetelés az épületen','Nincs','Légkondi','Van'])assert.ok(html.includes(value),value);
 assert.doesNotMatch(html,/Napelem/,'unknown solar panels must not be rendered as no');
});

test('search city-region choices show settlement counts and preserve compact IDs beside exact towns through edit and removal',async()=>{
 const t=await setup();t.ui.openEditor('search');
 const html=t.document.getElementById('modal-root').innerHTML;
 assert.match(html,/A településszám a központot is tartalmazza/);
 assert.match(html,/<small class="location-source"><a href="\/THIRD-PARTY-NOTICES\.txt"[^>]*>Források<\/a><\/small>/);
 assert.doesNotMatch(html,/class="neighborhood-source"|Városkörnyékek:|Magyar Posta Partner Extra/);
 chooseLocation(t,'area:Debrecen');chooseLocation(t,'city:Solymár');
 let chips=t.document.getElementById('location-chips');
 assert.match(chips.innerHTML,/Debrecen és környéke \(13 település\)/);
 assert.match(chips.innerHTML,/Solymár/);
 submitEntity(t,searchValues('Városkörnyék és másik település'));await settle();
 let saved=t.model.getState().searches.find(item=>item.title==='Városkörnyék és másik település');
 assert.ok(saved);assert.deepEqual([...saved.locationIds],['area:Debrecen','city:Solymár']);
 assert.equal(saved.locationIds.length,2,'a region remains one selected location instead of expanding its members');
 await t.click({page:'searches'});
 assert.match(t.document.getElementById('app').innerHTML,/Debrecen és környéke \(13 település\)/);
 t.ui.openEditor('search',saved.id);chips=t.document.getElementById('location-chips');
 assert.match(chips.innerHTML,/Debrecen és környéke \(13 település\)/);
 const target={dataset:{removeLocation:'area:Debrecen'},closest:()=>target};chips.handlers.click({target});
 assert.doesNotMatch(chips.innerHTML,/Debrecen/);assert.match(chips.innerHTML,/Solymár/);
 submitEntity(t,searchValues('Városkörnyék és másik település'));await settle();
 saved=t.model.getState().searches.find(item=>item.id===saved.id);
 assert.deepEqual([...saved.locationIds],['city:Solymár']);
});

test('a city-region is selectable by keyboard as one counted search location',async()=>{
 const t=await setup();t.ui.openEditor('search');
 const input=t.document.getElementById('location-input');input.value='Budapest és környéke';input.handlers.input();
 assert.match(t.document.getElementById('location-options').innerHTML,/Budapest és környéke \(81 település\)/);
 key(input,'ArrowDown');key(input,'Enter');
 assert.equal(input.value,'');assert.equal(input.getAttribute('aria-expanded'),'false');
 assert.match(t.document.getElementById('location-chips').innerHTML,/Budapest és környéke \(81 település\)/);
 submitEntity(t,searchValues('Főváros és környéke'));await settle();
 const saved=t.model.getState().searches.find(item=>item.title==='Főváros és környéke');
 assert.ok(saved);assert.deepEqual([...saved.locationIds],['area:Budapest']);
});

test('seller suggestions and a forged picker action cannot assign a broad city-region to a property',async()=>{
 const t=await setup();t.ui.openEditor('property');
 const input=t.document.getElementById('location-input'),list=t.document.getElementById('location-options');
 input.value='Debrecen';input.handlers.input();
 assert.match(list.innerHTML,/data-location-id="city:Debrecen"/);
 assert.doesNotMatch(list.innerHTML,/data-location-id="area:/);
 assert.doesNotMatch(t.document.getElementById('modal-root').innerHTML,/Városkörnyékek:/);
 const target={dataset:{locationId:'area:Debrecen'},closest:()=>target};list.handlers.click({target});
 assert.equal(t.document.getElementById('location-chips').innerHTML,'');
 assert.equal(input.value,'Debrecen','rejecting a forged region action must not silently consume the typed query');
 chooseLocation(t,'city:Debrecen');
 submitEntity(t,{street:'Teszt utca',houseNumber:'12/A',title:'Pontos településen lévő lakás',type:'Lakás',price:'65',area:'62',wholeRooms:'3',halfRooms:'0',floor:'',images:'',condition:'',building:''});await settle();
 const saved=t.model.getState().properties.find(item=>item.title==='Pontos településen lévő lakás');
 assert.ok(saved);assert.equal(saved.locationId,'city:Debrecen');
});

test('seller heating lists, supplemental heating and multiple parking choices persist together with exact room counts',async()=>{
 const t=await setup();t.ui.openEditor('property');chooseLocation(t,'city:Debrecen');
 const html=t.document.getElementById('modal-root').innerHTML;
 const options=name=>[...html.match(new RegExp(`<select id="f-${name}"[^>]*>([\\s\\S]*?)</select>`))[1].matchAll(/<option value="([^"]*)"/g)].map(match=>match[1]);
 assert.deepEqual(options('heatingType'),['',...propertyAttributes.HEATING_OPTIONS]);assert.deepEqual(options('secondaryHeatingType'),options('heatingType'));
 assert.doesNotMatch(html,/id="f-rooms"|id="f-parkingType"/);
 submitEntity(t,[...Object.entries({street:'Teszt utca',houseNumber:'12/A',title:'Egész és fél szobák',type:'Lakás',price:'82.5',area:'64.5',wholeRooms:'2',halfRooms:'3',floor:'-1',heatingType:'Nincs fűtés',secondaryHeatingType:'Klíma',images:''}),['parkingTypes','Garázs'],['parkingTypes','Udvari beálló']]);await settle();
 const saved=t.model.getState().properties.find(item=>item.title==='Egész és fél szobák');assert.ok(saved);assert.equal(saved.wholeRooms,2);assert.equal(saved.halfRooms,3);assert.equal(saved.rooms,3.5);assert.equal(saved.floor,-1);assert.equal(saved.heatingType,'Nincs fűtés');assert.equal(saved.secondaryHeatingType,'Klíma');assert.deepEqual([...saved.parkingTypes],['Garázs','Udvari beálló']);
 t.ui.openEditor('property',saved.id);assert.equal(t.document.getElementById('f-wholeRooms').value,'2');assert.equal(t.document.getElementById('f-halfRooms').value,'3');
 assert.match(t.document.getElementById('modal-root').innerHTML,/name="parkingTypes" value="Garázs" checked/);
 await t.click({page:'properties'});assert.match(t.document.getElementById('app').innerHTML,/2 egész \+ 3 fél szoba/);
});

function guardedEvent(values={}){return {...values,defaultPrevented:false,preventDefault(){this.defaultPrevented=true;}};}
test('all entity numeric inputs block signs through keys, mobile beforeinput, paste and input fallback while preserving decimals and empty bounds',async()=>{
 const t=await setup();
 for(const kind of ['property','search']){
  t.ui.openEditor(kind);
  const inputs=t.document.getElementById('entity-form').querySelectorAll('input[type="number"]');assert.ok(inputs.length>=5);
  for(const input of inputs){
   for(const character of ['-','−','+','e','E'])assert.equal(key(input,character).defaultPrevented,true,`${kind} ${input.id} blocks ${character}`);
   const mobile=guardedEvent({data:'-12',inputType:'insertText'});input.handlers.beforeinput(mobile);assert.equal(mobile.defaultPrevented,true);
   const paste=guardedEvent({clipboardData:{getData:()=>'-12'}});input.handlers.paste(paste);assert.equal(paste.defaultPrevented,true);
   input.value='12';input.handlers.input();input.value='-12';input.handlers.input();assert.equal(input.value,'12');input.value='1e-2';input.handlers.input();assert.equal(input.value,'12');
   input.value='';input.handlers.input();assert.equal(input.value,'');
  }
  const decimal=t.document.getElementById(kind==='property'?'f-price':'f-minPrice');decimal.value='12.5';decimal.handlers.input();assert.equal(decimal.value,'12.5');
 }
 t.ui.openEditor('property');const whole=t.document.getElementById('f-wholeRooms'),half=t.document.getElementById('f-halfRooms');
 assert.equal(key(whole,'.').defaultPrevented,true);assert.equal(key(half,',').defaultPrevented,true);
 whole.value='0';whole.handlers.input();half.value='0';half.handlers.input();assert.match(whole.validationMessage,/legalább egy/);half.value='1';half.handlers.input();assert.equal(whole.validationMessage,'');
 assert.doesNotMatch(t.document.getElementById('modal-root').innerHTML,/negatív/);
});

test('house forms require lot area only for sellers and hide or disable floor, balcony and elevator on both sides',async()=>{
 const t=await setup();
 for(const kind of ['property','search']){
  t.ui.openEditor(kind);const type=t.document.getElementById('f-type');type.value='Ház';type.handlers.change();
  assert.match(t.document.getElementById('entity-amenities').className,/hidden/);for(const name of ['balcony','elevator'])assert.equal(t.document.getElementById(`f-${name}`).disabled,true);
  if(kind==='property'){assert.equal(t.document.getElementById('f-lotArea').required,true);assert.equal(t.document.getElementById('f-lotArea').disabled,false);assert.equal(t.document.getElementById('f-floor').disabled,true);assert.match(t.document.getElementById('property-floor-field').className,/hidden/);}
  else{assert.equal(t.document.getElementById('floors-group').disabled,true);assert.match(t.document.getElementById('floors-group').className,/hidden/);}
  type.value='Lakás';type.handlers.change();assert.doesNotMatch(t.document.getElementById('entity-amenities').className,/hidden/);assert.equal(t.document.getElementById('f-balcony').disabled,false);
  if(kind==='property'){assert.equal(t.document.getElementById('f-lotArea').required,false);assert.equal(t.document.getElementById('f-lotArea').disabled,true);assert.equal(t.document.getElementById('f-floor').disabled,false);}else assert.equal(t.document.getElementById('floors-group').disabled,false);
 }
 t.ui.openEditor('property');chooseLocation(t,'city:Debrecen');submitEntity(t,{street:'Teszt utca',houseNumber:'12/A',title:'Ház mezőtisztítás',type:'Ház',price:'99.5',area:'120.5',wholeRooms:'2',halfRooms:'3',lotArea:'650',floor:'3',balcony:'on',elevator:'on',images:''});await settle();
 const property=t.model.getState().properties.find(item=>item.title==='Ház mezőtisztítás');assert.ok(property);assert.equal(property.floor,null);assert.equal(property.balcony,false);assert.equal(property.elevator,false);
 t.ui.openEditor('search');chooseLocation(t,'city:Debrecen');submitEntity(t,[...Object.entries({...searchValues('Ház keresési mezőtisztítás'),type:'Ház',balcony:'on',elevator:'on'}),['floors','-1'],['heatingTypes','Gázkazán'],['heatingTypes','Hőszivattyú']]);await settle();
 const search=t.model.getState().searches.find(item=>item.title==='Ház keresési mezőtisztítás');assert.ok(search);assert.deepEqual([...search.floors],[]);assert.equal(search.balcony,false);assert.equal(search.elevator,false);assert.deepEqual([...search.heatingTypes],['Gázkazán','Hőszivattyú']);
});

test('legacy arbitrary room totals are never rounded and existing heating or parking text remains selectable',async()=>{
 const demo=createModel({getItem:()=>null,setItem:()=>{}}).getState();demo.properties[0]={...demo.properties[0],id:'legacy-property',rooms:3.2,wholeRooms:null,halfRooms:null,heatingType:'Régi vegyes rendszer',parkingType:'Régi garázs és beálló',parkingTypes:undefined};
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{getState:async()=>demo}});t.ui.openEditor('property','legacy-property');const html=t.document.getElementById('modal-root').innerHTML;
 assert.equal(t.document.getElementById('f-wholeRooms').value,'');assert.equal(t.document.getElementById('f-halfRooms').value,'');assert.match(html,/<option value="Régi vegyes rendszer" selected>Meglévő érték: Régi vegyes rendszer<\/option>/);assert.match(html,/name="parkingTypes" value="Régi garázs és beálló" checked/);
});


function chooseReport(t,reason){for(const option of accountHelpers.REPORT_REASON_OPTIONS){const input=t.document.getElementById('f-reportReason-'+option.value);if(input)input.checked=option.value===reason;}}
function accountFixture(mutate){let raw;const local=createModel({getItem:()=>null,setItem:(_key,value)=>{raw=JSON.parse(value);}});local.activate('search','own-s1');mutate(raw);return raw;}
test('hosted and settings registration both offer account types and send the selected agent role',async()=>{
 const hosted=await setup({hosted:true});await hosted.click({action:'auth-mode',mode:'register'});
 const registration=hosted.document.getElementById('app').innerHTML;assert.match(registration,/id="f-accountType"/);assert.match(registration,/value="private">Magánszemély/);assert.match(registration,/value="agent">Ingatlanközvetítő/);
 await submitHostedAuth(hosted,{...hostedCredentials,name:'Közvetítő Anna',accountType:'agent'});await settle();assert.equal(hosted.connected[0][3].accountType,'agent');
 const legacy=await setup();await legacy.click({page:'settings'});const select=legacy.document.getElementById('api-accountType');assert.ok(select);assert.equal(select.value,'private');
 legacy.document.getElementById('register-toggle').handlers.change({target:{checked:true}});assert.doesNotMatch(legacy.document.getElementById('register-name').className,/hidden/);
 const form=legacy.document.getElementById('api-form');form.values={baseUrl:'https://api.example.test',email:'agent@example.test',password:'LongPassword2026!',register:'on',registerName:'Közvetítő Eszter',accountType:'agent'};form.handlers.submit({preventDefault(){},currentTarget:form});await settle();assert.equal(legacy.connected[0][3].accountType,'agent');
});
test('foreign owner labels are explicit while agent-owned workspace cards, summaries and activation choices hide them',async()=>{
 const t=await setup();assert.match(t.document.getElementById('app').innerHTML,/account-badge private-badge/);
 while(t.model.feed()[0]?.ownerAccountType!=='agent'){t.model.decide(t.model.feed()[0],false);await t.ui.render();}
 assert.match(t.document.getElementById('app').innerHTML,/account-badge agent-badge/);t.ui.openDetails();assert.match(t.document.getElementById('modal-root').innerHTML,/Ingatlanközvetítő/);await t.click({action:'close'});
 await t.click({action:'like'});await t.click({action:'close'});await t.click({action:'tab',tab:'liked'});assert.match(t.document.getElementById('app').innerHTML,/account-badge agent-badge/);await t.click({page:'matches'});assert.match(t.document.getElementById('app').innerHTML,/account-badge agent-badge/);
 const raw=accountFixture(raw=>{raw.users.find(user=>user.id==='me').accountType='agent';});const agent=await setup({initialRaw:raw});assert.ok(agent.model.feed().every(item=>item.ownerAccountType==='private'));
 for(const page of ['properties','searches']){await agent.click({page});assert.doesNotMatch(agent.document.getElementById('app').innerHTML,/account-badge/);}
 agent.ui.openActivation();assert.doesNotMatch(agent.document.getElementById('modal-root').innerHTML,/account-badge/);await agent.click({action:'close'});
 await agent.click({action:'activate-one',kind:'property',id:'own-p1'});assert.ok(agent.model.feed().every(item=>item.ownerAccountType==='private'));assert.match(agent.document.getElementById('app').innerHTML,/account-badge private-badge/);
 await agent.click({page:'settings'});const html=agent.document.getElementById('app').innerHTML;assert.match(html,/Fióktípus: <strong>Ingatlanközvetítő/);assert.doesNotMatch(html.match(/<form[^>]*id="profile-form"[\s\S]*?<\/form>/)[0],/name="accountType"/);
});
test('reporting requires one reason, awaits persistence and allows another reason without revealing timestamps',async()=>{
 const t=await setup(),before=t.model.getState();await t.click({action:'report-account',kind:'property',id:'p1'});let html=t.document.getElementById('modal-root').innerHTML;assert.match(html,/Milyen szabálytalanságot tapasztaltál\?/);assert.doesNotMatch(html,/<select|Jelentés oka|Korábban jelzett ok/);for(const option of accountHelpers.REPORT_REASON_OPTIONS)assert.ok(html.includes(`value="${option.value}"`));
 await t.click({action:'confirm-report',kind:'property',id:'p1'});assert.equal(t.document.activeElement.id,'f-reportReason-suspected_agent');assert.deepEqual(t.model.getState().reportedEntities,[]);await t.click({action:'close'});
 let release;const wait=new Promise(resolve=>{release=resolve;});const original=t.model.reportAccount;t.model.reportAccount=async(...args)=>{await wait;return original(...args);};
 await t.click({action:'report-account',kind:'property',id:'p1'});chooseReport(t,'suspected_agent');const sending=t.click({action:'confirm-report',kind:'property',id:'p1'});await settle();assert.deepEqual(t.model.getState().reportedEntities,[]);assert.match(t.document.getElementById('modal-root').innerHTML,/Jelentés elküldése/);
 release();await sending;assert.deepEqual(t.model.getState().reportedEntities,[{entityKind:'property',entityId:'p1',reason:'suspected_agent'}]);assert.equal(t.model.getState().credits,before.credits);assert.equal(t.document.getElementById('modal-root').innerHTML,'');assert.match(t.document.getElementById('toast').textContent,/A jelentésedet elmentettük/);
 html=t.document.getElementById('app').innerHTML;assert.match(html,/data-action="report-account" data-kind="property" data-id="p1">/);assert.doesNotMatch(html,/\d{4}-\d{2}-\d{2}T|reportedAt|CreatedAt/);
 await t.click({action:'report-account',kind:'property',id:'p1'});assert.doesNotMatch(t.document.getElementById('modal-root').innerHTML,/Korábban jelzett ok|Jelentés oka/);chooseReport(t,'misleading_content');await t.click({action:'confirm-report',kind:'property',id:'p1'});assert.equal(t.model.getState().reportedEntities.length,2);
 await t.click({action:'report-account',kind:'property',id:'p1'});chooseReport(t,'misleading_content');await t.click({action:'confirm-report',kind:'property',id:'p1'});assert.equal(t.model.getState().reportedEntities.length,2);assert.match(t.document.getElementById('toast').textContent,/már jelentetted/);
});
test('agent listings offer applicable report reasons and failed saves retain the selected reason for retry',async()=>{
 const t=await setup(),original=t.model.reportAccount;await t.click({action:'report-account',kind:'property',id:'own-p1'});assert.equal(t.document.getElementById('modal-root').innerHTML,'');
 while(t.model.feed()[0]?.id!=='p2'){t.model.decide(t.model.feed()[0],false);await t.ui.render();}
 await t.click({action:'report-account',kind:'property',id:'p2'});const html=t.document.getElementById('modal-root').innerHTML;assert.doesNotMatch(html,/value="suspected_agent"/);assert.match(html,/value="misleading_content"/);assert.match(html,/value="other_violation"/);
 chooseReport(t,'misleading_content');t.model.reportAccount=async()=>{throw new Error('A jelentés mentése most nem sikerült.');};await t.click({action:'confirm-report',kind:'property',id:'p2'});assert.match(t.document.getElementById('modal-root').innerHTML,/Jelentés elküldése/);assert.match(t.document.getElementById('toast').textContent,/mentése most nem sikerült/);assert.equal(t.document.getElementById('f-reportReason-misleading_content').checked,true);assert.deepEqual(t.model.getState().reportedEntities,[]);
 t.model.reportAccount=original;await t.click({action:'confirm-report',kind:'property',id:'p2'});assert.deepEqual(t.model.getState().reportedEntities,[{entityKind:'property',entityId:'p2',reason:'misleading_content'}]);
});
test('agent search likes show one credit and button, keyboard and swipe cannot consume an unaffordable candidate',async()=>{
 const raw=accountFixture(raw=>{raw.users.find(user=>user.id==='me').accountType='agent';raw.credits=1;});const t=await setup({initialRaw:raw});assert.match(t.document.getElementById('app').innerHTML,/<span class="decision-like-caption"><span>Kedvelés<\/span><small>1 kredit<\/small>/);t.ui.openDetails();assert.match(t.document.getElementById('modal-root').innerHTML,/Tetszik · 1 kredit/);await t.click({action:'close'});await t.click({action:'like'});assert.equal(t.model.getState().credits,0);await t.click({action:'close'});
 const before=t.model.getState(),candidate=t.model.feed()[0].id;await t.click({action:'like'});assert.match(t.document.getElementById('modal-root').innerHTML,/Kreditekre van szükséged/);assert.equal(t.model.feed()[0].id,candidate);assert.equal(t.model.getState().decisions.length,before.decisions.length);await t.click({action:'close'});
 await t.document.handlers.keydown({key:'ArrowRight',target:{closest:()=>null},preventDefault(){}});assert.match(t.document.getElementById('modal-root').innerHTML,/Kreditekre van szükséged/);await t.click({action:'close'});
 const card=t.document.getElementById('candidate'),target={closest:selector=>selector==='#candidate'?card:null};t.document.handlers.pointerdown({target,clientX:0,clientY:0,pointerId:7});await t.document.handlers.pointerup({clientX:130,clientY:3,pointerId:7});assert.match(t.document.getElementById('modal-root').innerHTML,/Kreditekre van szükséged/);assert.equal(t.model.feed()[0].id,candidate);assert.equal(t.model.getState().credits,0);assert.equal(t.model.getState().ledger.length,before.ledger.length);await t.click({action:'close'});await t.click({action:'pass'});assert.notEqual(t.model.feed()[0]?.id,candidate);assert.equal(t.model.getState().credits,0);
});

function incomingFixture(type='private') {return accountFixture(raw=>{
 raw.users.find(user=>user.id==='me').accountType=type;raw.matches=[];raw.reports=[];
 // Keep the incoming-action target distinct from the best-value discovery card.
 raw.properties.find(item=>item.id==='p2').area=50;
 const received=(id,actorKind,actorId,propertyId,searchId)=>({id,actorKind,actorId,propertyId,searchId,liked:true,createdAt:'2026-11-07T10:00:00.000Z'});
 raw.decisions=[received('in-p1','property','p1','p1','own-s1'),received('in-p2','property','p2','p2','own-s1'),received('in-p4','property','p4','p4','own-s2'),received('in-s1','search','s1','own-p1','s1')];
 const second=raw.searches.find(search=>search.id==='own-s2');Object.assign(second,{locationIds:['district:Budapest:13'],city:'Budapest',districts:['XIII.']});
});}
test('Kedveltek uses the active profile and reciprocal actions target the chosen pair instead of the discovery first card',async()=>{
 const t=await setup({initialRaw:incomingFixture()});await t.click({page:'incoming'});let html=t.document.getElementById('app').innerHTML;assert.match(html,/Téged kedveltek/);assert.match(html,/incoming-card/);assert.match(html,/data-id="p1"/);assert.match(html,/data-id="p2"/);assert.doesNotMatch(html,/peter@example.hu|eszter@example.hu|\+36 30/);
 const before=t.model.getState();assert.equal(t.model.feed()[0].id,'p1');await t.click({action:'incoming-details',kind:'property',id:'p2'});assert.match(t.document.getElementById('modal-root').innerHTML,/Zöldre néző otthon/);await t.click({action:'close'});
 await t.click({action:'incoming-like',kind:'property',id:'p2'});assert.equal(t.model.getState().credits,before.credits);assert.ok(t.model.getState().decisions.some(decision=>decision.actorKind==='search'&&decision.propertyId==='p2'&&decision.liked));assert.equal(t.model.getState().decisions.some(decision=>decision.actorKind==='search'&&decision.propertyId==='p1'),false);assert.match(t.document.getElementById('modal-root').innerHTML,/Egymásra találtatok/);await t.click({action:'close'});assert.match(t.document.getElementById('app').innerHTML,/Beszélgetés megnyitása/);
 await t.click({action:'incoming-pass',kind:'property',id:'p1'});html=t.document.getElementById('app').innerHTML;assert.match(html,/korábban elutasítottad/);assert.ok(t.model.incomingLikes().items.find(item=>item.id==='p1').myDecision==='passed');
 await t.click({action:'activate-one',kind:'search',id:'own-s2'});assert.equal(t.ctx.location.hash,'#incoming');assert.match(t.document.getElementById('app').innerHTML,/data-id="p4"/);assert.doesNotMatch(t.document.getElementById('app').innerHTML,/incoming-card" data-id="p1"/);
 await t.click({action:'activate-one',kind:'property',id:'own-p1'});assert.match(t.document.getElementById('app').innerHTML,/incoming-card" data-id="s1"/);await t.click({action:'incoming-like',kind:'search',id:'s1'});assert.equal(t.model.getState().credits,before.credits-2);
});
test('incoming likes are free to inspect and agent reciprocity checks credit before changing the received pair',async()=>{
 const raw=incomingFixture('agent');raw.credits=0;const t=await setup({initialRaw:raw});await t.click({page:'incoming'});const before=t.model.getState();assert.equal(t.model.incomingLikes().items.length,1);assert.doesNotMatch(t.document.getElementById('app').innerHTML,/incoming-card" data-id="p2"/);await t.click({action:'incoming-like',kind:'property',id:'p1'});assert.match(t.document.getElementById('modal-root').innerHTML,/Kreditekre van szükséged/);assert.deepEqual(t.model.getState(),before);await t.click({action:'close'});
 t.model.buyDemoCredits(1);await t.ui.render();await t.click({action:'incoming-like',kind:'property',id:'p1'});assert.equal(t.model.getState().credits,0);assert.equal(t.model.getState().ledger.filter(entry=>entry.amount===-1).length,1);
});
test('incoming pagination appends unique rows and discards an old load after navigation',async()=>{
 const local=createModel({getItem:()=>JSON.stringify(incomingFixture()),setItem:()=>{}}),all=local.incomingLikes().items,calls=[];let release;
 const more=new Promise(resolve=>{release=resolve;});const active=local.getState().active;
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{getState:()=>local.getState(),incomingLikes:async({offset=0,limit=50}={})=>{calls.push({offset,limit});return offset?more:{active,items:[all[0]],total:2,offset:0,limit:1,hasMore:true,likeCost:0};}}});
 await t.click({page:'incoming'});assert.match(t.document.getElementById('app').innerHTML,/incoming-more/);const loading=t.click({action:'incoming-more'});await settle();assert.deepEqual(calls,[{offset:0,limit:50},{offset:1,limit:1}]);await t.click({page:'settings'});release({active,items:[all[1]],total:2,offset:1,limit:1,hasMore:false,likeCost:0});await loading;assert.equal(t.ctx.location.hash,'#settings');assert.doesNotMatch(t.document.getElementById('app').innerHTML,/incoming-grid/);
 const appended=await setup({hosted:true,authenticated:true,apiOverrides:{getState:()=>local.getState(),incomingLikes:({offset=0}={})=>({active,items:offset?[all[0],all[1]]:[all[0]],total:2,offset,limit:1,hasMore:offset===0,likeCost:0})}});await appended.click({page:'incoming'});await appended.click({action:'incoming-more'});const html=appended.document.getElementById('app').innerHTML;assert.equal((html.match(/class="entity-card incoming-card"/g)||[]).length,2);assert.doesNotMatch(html,/data-action="incoming-more"/);
});
test('incoming view handles no active profile and incompatible interests without actionable likes',async()=>{
 const empty=createModel({getItem:()=>null,setItem:()=>{}}).getState();empty.active={kind:'search',id:null};const t=await setup({hosted:true,authenticated:true,apiOverrides:{getState:()=>empty,incomingLikes:()=>({active:null,items:[],total:0,offset:0,limit:50,hasMore:false,likeCost:0})}});await t.click({page:'incoming'});assert.match(t.document.getElementById('app').innerHTML,/Válassz aktív profilt/);
 const raw=incomingFixture();raw.properties.find(item=>item.id==='p1').area=999;const incompatible=await setup({initialRaw:raw});await incompatible.click({page:'incoming'});assert.match(incompatible.document.getElementById('app').innerHTML,/Részleges egyezés/);assert.match(incompatible.document.getElementById('app').innerHTML,/engedélyezd a részleges egyezéseket/);const before=incompatible.model.getState();await incompatible.click({action:'incoming-like',kind:'property',id:'p1'});assert.deepEqual(incompatible.model.getState(),before);
});

test('hosted root is a public demand-focused landing with independent login and registration routes',async()=>{
 const t=await setup({hosted:true,hash:''}),html=t.document.getElementById('app').innerHTML;
 assert.match(html,/Unod a passzív várakozást és a kéretlen telefonokat\?/);assert.match(html,/Érd el a vevőidet egy kattintással!/);assert.match(html,/Tedd közzé a keresési igényed és maradj inkognitóban!/);assert.match(html,/Nézd meg, mit keresnek a vevők/);assert.ok(html.indexOf('landing-search-card')<html.indexOf('landing-property-card'));assert.match(html,/Megtalálom a vevőmet/);assert.match(html,/Megtalálom az otthonom/);assert.match(html,/Illusztráció/);assert.match(html,/geojs.io\/privacy/);assert.ok(html.indexOf('landing-property-card')<html.indexOf('class="landing-how"'),'Both teaser types precede the longer explanation');assert.doesNotMatch(html,/landing-region-status|landing-region-note|aria-describedby="landing-region-note"|Hozzávetőleges régió|Bármikor választhatsz másikat/);assert.equal(t.document.getElementById('hosted-auth-form'),null);assert.equal(t.getSelectedModel(),null);assert.doesNotMatch(html,/sidebar|api-email|Demó munkatér/);
 await t.click({action:'auth-mode',mode:'register'});assert.equal(t.ctx.location.hash,'#register');assert.ok(t.document.getElementById('f-name'));await t.click({action:'landing'});assert.equal(t.ctx.location.hash,'#landing');assert.ok(t.document.getElementById('landing-region'));await t.click({action:'auth-mode',mode:'login'});assert.equal(t.ctx.location.hash,'#login');assert.equal(t.document.getElementById('f-name'),null);assert.ok(t.document.getElementById('hosted-auth-form'));
});
test('local landing preview does not alter the saved demo workspace',async()=>{
 const t=await setup({hash:'#landing'}),before=t.model.getState();assert.ok(t.document.getElementById('landing-region'));await t.click({page:'discover'});assert.match(t.document.getElementById('app').innerHTML,/A következő fejezeted/);assert.deepEqual(t.model.getState(),before);
});
test('landing uses public structured teaser fields only, escapes markup and bounds demand and property cards',async()=>{
 const data=landingFixture();data.searches=Array.from({length:12},(_,i)=>({...data.searches[0],key:'s'+i,title:'Lakást <keresnek>',description:'hidden@example.hu',ownerId:'secret-owner',ownerName:'Titkos Név'}));data.properties=Array.from({length:6},(_,i)=>({...data.properties[0],key:'p'+i,title:'Eladó <lakás>',address:'Titkos utca 42.',images:['https://tracker.test/photo.jpg'],ownerEmail:'hidden@example.hu'}));
 const t=await setup({hosted:true,hash:'',fetchLanding:async()=>data}),html=t.document.getElementById('app').innerHTML;assert.equal((html.match(/class="landing-search-card"/g)||[]).length,8);assert.equal((html.match(/class="landing-property-card"/g)||[]).length,4);assert.match(html,/Lakást &lt;keresnek&gt;/);assert.doesNotMatch(html,/hidden@example|secret-owner|Titkos|tracker.test|<keresnek>/);assert.doesNotMatch(source,/navigator\s*\.\s*geolocation|watchPosition|getCurrentPosition/);
});
test('manual region choice wins a delayed approximate lookup and only its canonical ID is remembered',async()=>{
 let detected;const geo=new Promise(resolve=>{detected=resolve});const t=await setup({hosted:true,hash:'',detectLandingRegion:()=>geo});assert.deepEqual(JSON.parse(JSON.stringify(t.landingCalls)),[{}]);let select=t.document.getElementById('landing-region');select.value='HU321';select.handlers.change({currentTarget:select});await settle();assert.equal(t.regionStorage.get('otthonra.landing.region'),'HU321');assert.match(t.document.getElementById('app').innerHTML,/Debrecen/);detected('HU110');await settle();assert.deepEqual(JSON.parse(JSON.stringify(t.landingCalls)),[{},{region:'HU321'}]);assert.equal(t.document.getElementById('landing-region').value,'HU321');
});
test('approximate region is optional and not persisted; saved manual region bypasses lookup',async()=>{
 const auto=await setup({hosted:true,hash:'',detectLandingRegion:async()=> 'HU321'});await settle();assert.deepEqual(JSON.parse(JSON.stringify(auto.landingCalls)),[{},{region:'HU321'}]);assert.equal(auto.regionStorage.size,0);
 let lookups=0;const saved=await setup({hosted:true,hash:'',regionStorage:{'otthonra.landing.region':'HU321'},detectLandingRegion:async()=>{lookups++;return 'HU110'}});assert.deepEqual(JSON.parse(JSON.stringify(saved.landingCalls)),[{},{region:'HU321'}]);assert.equal(lookups,0);assert.match(saved.document.getElementById('app').innerHTML,/Debrecen/);
});
test('regional empty results remain honest and national fallback clears remembered choice',async()=>{
 const t=await setup({hosted:true,hash:''});const select=t.document.getElementById('landing-region');select.value='HU232';select.handlers.change({currentTarget:select});await settle();let html=t.document.getElementById('app').innerHTML;assert.match(html,/Ebben a régióban még nincs keresési igény/);assert.match(html,/Somogy/);assert.doesNotMatch(html,/class="landing-search-card"|class="landing-property-card"/);await t.click({action:'landing-national'});html=t.document.getElementById('app').innerHTML;assert.match(html,/Országos válogatás/);assert.match(html,/class="landing-search-card"/);assert.equal(t.regionStorage.has('otthonra.landing.region'),false);
});
test('public API failure offers retry without substituting demo or erasing regional choices',async()=>{
 let requests=0;const t=await setup({hosted:true,hash:'',fetchLanding:async input=>{if(++requests===1)throw new Error('Átmeneti hálózati hiba.');return landingFixture(input.region)}});let html=t.document.getElementById('app').innerHTML;assert.match(html,/A válogatás most nem elérhető/);assert.doesNotMatch(html,/class="landing-search-card"|sidebar/);assert.equal(t.getSelectedModel(),null);await t.click({action:'landing-retry'});html=t.document.getElementById('app').innerHTML;assert.match(html,/class="landing-search-card"/);
});
test('a late public response cannot replace the authentication page',async()=>{
 let release,requests=0;const pending=new Promise(resolve=>{release=resolve}),t=await setup({hosted:true,hash:'',fetchLanding:()=>++requests===1?landingFixture():pending});const retry=t.click({action:'landing-retry'});await settle();await t.click({action:'auth-mode',mode:'register'});assert.ok(t.document.getElementById('hosted-auth-form'));release(landingFixture('HU321'));await retry;assert.ok(t.document.getElementById('hosted-auth-form'));assert.equal(t.ctx.location.hash,'#register');
});
test('refund notifications show unread balance feedback, escape text, and await persisted mark-read',async()=>{
 let readAt=null,resolveRead;const wait=new Promise(resolve=>{resolveRead=resolve});const item={id:'notice-1',kind:'like_refund',amount:2,text:'A 2 kreditedet visszatérítettük. <b>biztonságos</b>',decisionId:'decision-1',createdAt:'2026-11-08T10:00:00Z',readAt:null};const state=createModel({getItem:()=>null,setItem:()=>{}}).getState();const t=await setup({hosted:true,authenticated:true,apiOverrides:{getState:async()=>({...state,unreadNotificationCount:readAt?0:1}),notifications:async()=>({items:[{...item,readAt}],total:1,unreadCount:readAt?0:1,offset:0,limit:50,hasMore:false}),markNotificationRead:async()=>{await wait;readAt='2026-11-08T11:00:00Z';return {...item,readAt,unreadCount:0}}}});
 assert.match(t.document.getElementById('app').innerHTML,/aria-label="Értesítések, 1 olvasatlan"/);await t.click({page:'notifications'});let html=t.document.getElementById('app').innerHTML;assert.match(html,/Kreditvisszatérítés/);assert.match(html,/\+2 kredit/);assert.match(html,/&lt;b&gt;biztonságos&lt;\/b&gt;/);assert.match(html,/is-unread/);const marking=t.click({action:'notification-read',id:item.id});await settle();assert.match(t.document.getElementById('app').innerHTML,/is-unread/);resolveRead();await marking;html=t.document.getElementById('app').innerHTML;assert.doesNotMatch(html,/is-unread/);assert.equal(t.document.getElementById('notifications-nav-count').hidden,true);assert.equal(t.document.getElementById('notifications-top-count').hidden,true);assert.match(html,/Elolvasva/);assert.equal((await t.model.getState()).credits,24);
});
test('notification paging appends unique items and ignores late results after navigation',async()=>{
 const first={id:'n1',kind:'like_refund',amount:1,text:'Első visszatérítés.',createdAt:'2026-11-08T10:00:00Z',readAt:null},second={...first,id:'n2',text:'Második visszatérítés.'};let release;const pending=new Promise(resolve=>{release=resolve});const t=await setup({hosted:true,authenticated:true,apiOverrides:{notifications:async({offset=0}={})=>offset?pending:{items:[first],total:2,unreadCount:2,offset:0,limit:1,hasMore:true}}});await t.click({page:'notifications'});const loading=t.click({action:'notifications-more'});await settle();await t.click({page:'settings'});release({items:[first,second],total:2,unreadCount:2,offset:1,limit:1,hasMore:false});await loading;assert.equal(t.ctx.location.hash,'#settings');assert.doesNotMatch(t.document.getElementById('app').innerHTML,/Második visszatérítés/);
 const appended=await setup({hosted:true,authenticated:true,apiOverrides:{notifications:async({offset=0}={})=>({items:offset?[first,second]:[first],total:2,unreadCount:2,offset,limit:1,hasMore:!offset})}});await appended.click({page:'notifications'});await appended.click({action:'notifications-more'});const html=appended.document.getElementById('app').innerHTML;assert.equal((html.match(/data-notification-id=/g)||[]).length,2);assert.doesNotMatch(html,/notifications-more/);
});
test('empty notifications explain account activity and failed read preserves the unread state',async()=>{
 const empty=await setup({hosted:true,authenticated:true,apiOverrides:{notifications:async()=>({items:[],total:0,unreadCount:0,offset:0,limit:50,hasMore:false})}});await empty.click({page:'notifications'});assert.match(empty.document.getElementById('app').innerHTML,/Még nincs értesítésed/);assert.match(empty.document.getElementById('app').innerHTML,/profiljaid kedveléseit, párosításait, üzeneteit/);
 const item={id:'n1',kind:'like_refund',amount:1,text:'Visszatérítés',createdAt:'2026-11-08T10:00:00Z',readAt:null};const t=await setup({hosted:true,authenticated:true,apiOverrides:{notifications:async()=>({items:[item],total:1,offset:0,limit:50,hasMore:false}),markNotificationRead:async()=>{throw new Error('Nem sikerült menteni.')}}});await t.click({page:'notifications'});await t.click({action:'notification-read',id:'n1'});assert.match(t.document.getElementById('app').innerHTML,/is-unread/);assert.match(t.document.getElementById('toast').textContent,/Nem sikerült menteni/);
});
function activityNotice(id,kind,target=null){return{id,kind,amount:0,text:`${kind} <img src=x onerror=alert(1)>`,createdAt:'2026-11-19T10:00:00Z',readAt:null,target};}
test('notifications gather every profile and event family without activating or reading anything on entry',async()=>{
 const base=createModel({getItem:()=>null,setItem:()=>{}}).getState(),kinds=['incoming_like','match_created','message_received','feedback_received','feedback_completed','feedback_expired','credit_added','like_refund','feedback_refund'];let reads=0,activations=0;
 const items=kinds.map((kind,index)=>({...activityNotice('all-'+index,kind,{page:index<3?'incoming':index<6?'insights':'credits',entityKind:index<3?'search':'property',entityId:index<3?'own-s2':'own-p1'}),amount:index>=6?index+1:0}));
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{getState:async()=>({...base,unreadNotificationCount:items.length}),notifications:async()=>({items,total:items.length,unreadCount:items.length,offset:0,limit:50,hasMore:false}),markNotificationRead:async()=>{reads++;},activate:async()=>{activations++;}}});
 await t.click({page:'notifications'});const html=t.document.getElementById('app').innerHTML;assert.equal((html.match(/data-notification-id=/g)||[]).length,kinds.length);assert.match(html,/Új kedvelés|Új párosítás|Új üzenet/);assert.match(html,/Új visszajelzés|Teljesült a visszajelzés-csomagod|Lejárt a visszajelzés-csomagod/);assert.match(html,/Kreditjóváírás|Kreditvisszatérítés/);assert.match(html,/Keresési igény ·/);assert.match(html,/Eladó ingatlan ·/);assert.match(html,/&lt;img src=x onerror=alert\(1\)&gt;/);assert.doesNotMatch(html,/<img src=x/);assert.equal(reads,0);assert.equal(activations,0);assert.equal(t.document.getElementById('notifications-nav-count').hidden,false);assert.equal(t.ui.getModelState().unreadNotificationCount,kinds.length);assert.match(html,/Téged kedveltek/);
});
test('selected read receipt updates both unread badges without waiting for another account refresh',async()=>{
 const base=createModel({getItem:()=>null,setItem:()=>{}}).getState(),item=activityNotice('read-current','incoming_like');let freeze=false,reads=0,stateReads=0;
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{getState:async()=>{stateReads++;if(freeze)return await new Promise(()=>{});return{...base,unreadNotificationCount:7};},notifications:async()=>({items:[item],total:7,unreadCount:7,offset:0,limit:50,hasMore:false}),markNotificationRead:async id=>{reads++;assert.equal(id,item.id);return{...item,readAt:'2026-11-19T11:00:00Z',unreadCount:4};}}});
 await t.click({page:'notifications'});const before=stateReads;freeze=true;await t.click({action:'notification-read',id:item.id});assert.equal(stateReads,before);assert.equal(reads,1);assert.equal(t.document.getElementById('notifications-nav-count').textContent,'4');assert.equal(t.document.getElementById('notifications-top-count').textContent,'4');assert.equal(t.document.getElementById('notifications-top-button').getAttribute('aria-label'),'Értesítések, 4 olvasatlan');assert.doesNotMatch(t.document.getElementById('notifications-list').innerHTML,/is-unread/);await t.click({action:'notification-read',id:item.id});assert.equal(reads,1,'Already-read selection must not repeat the write');
});
test('notification opens an exact older incoming pair on its inactive own profile even outside the first incoming page',async()=>{
 const raw=incomingFixture(),store=createModel({getItem:()=>JSON.stringify(raw),setItem:()=>{}});store.activate('search','own-s2');const older=store.incomingLikes().items.find(item=>item.id==='p4');assert.ok(older);store.activate('search','own-s1');const notice=activityNotice('old-like','incoming_like',{page:'incoming',entityKind:'search',entityId:'own-s2',propertyId:'p4',searchRequestId:'own-s2'}),calls=[];
 const t=await setup({hosted:true,authenticated:true,initialRaw:raw,apiOverrides:{getState:async()=>({...store.getState(),unreadNotificationCount:notice.readAt?0:1}),notifications:async()=>({items:[notice],total:1,unreadCount:notice.readAt?0:1,offset:0,limit:50,hasMore:false}),incomingLikes:async()=>({items:[],total:60,unreadCount:60,offset:0,limit:50,hasMore:true,active:store.getState().active}),getNotificationContext:async(id,options)=>{calls.push('context');assert.equal(id,notice.id);assert.ok(options.signal);return{notification:notice,available:true,target:notice.target,canActivate:true,item:older};},markNotificationRead:async id=>{calls.push('read');assert.equal(id,notice.id);notice.readAt='2026-11-19T11:00:00Z';return{...notice,unreadCount:0};},activate:async(kind,id)=>{calls.push('activate:'+id);store.activate(kind,id);}}});
 await t.click({page:'notifications'});assert.equal(store.getState().active.id,'own-s1');await t.click({action:'notification-open',id:notice.id});assert.deepEqual(calls,['context','read','activate:own-s2']);assert.equal(store.getState().active.id,'own-s2');assert.equal(t.ctx.location.hash,'#incoming');assert.match(t.document.getElementById('modal-root').innerHTML,new RegExp(older.title));assert.match(t.document.getElementById('modal-root').innerHTML,/data-id="p4"/);assert.doesNotMatch(t.document.getElementById('modal-root').innerHTML,/peter@example.hu|eszter@example.hu|\+36 30/);
});
test('deleted notification remains readable and unavailable without changing the active profile',async()=>{
 const notice=activityNotice('gone-profile','incoming_like',{page:'incoming',entityKind:'search',entityId:'deleted-own-search'});let activated=0,read=0;
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{notifications:async()=>({items:[notice],total:1,unreadCount:1,offset:0,limit:50,hasMore:false}),getNotificationContext:async()=>({notification:notice,available:false,target:notice.target,canActivate:false,item:null}),markNotificationRead:async()=>{read++;return{...notice,readAt:'2026-11-19T11:00:00Z',unreadCount:0};},activate:async()=>{activated++;}}});await t.click({page:'notifications'});const active=t.ui.getModelState().active.id;await t.click({action:'notification-open',id:notice.id});assert.equal(activated,0);assert.equal(read,1);assert.equal(t.ui.getModelState().active.id,active);assert.equal(t.ctx.location.hash,'#notifications');assert.match(t.document.getElementById('modal-root').innerHTML,/már nem nyitható meg|már törölve lett/);assert.equal(t.document.getElementById('notifications-top-count').hidden,true);
});
for(const leave of ['navigation','modal','logout','session'])test(`late notification context cannot activate or mark after ${leave}`,async()=>{
 let release,signal,reads=0,activations=0;const notice=activityNotice('late-like','incoming_like',{page:'incoming',entityKind:'search',entityId:'own-s2'}),pending=new Promise(resolve=>{release=resolve;});
 const t=await setup({hosted:true,authenticated:true,regionStorage:{'otthonra.api':'session-before'},apiOverrides:{notifications:async()=>({items:[notice],total:1,unreadCount:1,offset:0,limit:50,hasMore:false}),getNotificationContext:async(_id,options)=>{signal=options.signal;return await pending;},markNotificationRead:async()=>{reads++;return{...notice,readAt:'2026-11-19T11:00:00Z',unreadCount:0};},activate:async()=>{activations++;}}});await t.click({page:'notifications'});const opening=t.click({action:'notification-open',id:notice.id});await settle();assert.ok(signal);
 if(leave==='navigation')await t.click({page:'settings'});else if(leave==='modal')t.ui.openModal('<h2>Másik ablak</h2>');else if(leave==='logout')await t.click({action:'disconnect'});else t.regionStorage.set('otthonra.api','session-after');
 release({notification:notice,available:true,target:notice.target,canActivate:true,item:{id:'p4',kind:'property',title:'Késői magánadat'}});await opening;assert.equal(reads,0);assert.equal(activations,0);assert.doesNotMatch(t.document.getElementById('modal-root').innerHTML,/Késői magánadat/);if(leave==='modal')assert.match(t.document.getElementById('modal-root').innerHTML,/Másik ablak/);if(leave==='navigation')assert.equal(t.ctx.location.hash,'#settings');
});
test('profile deletion tells users it cannot be restored while preserving existing matched history',async()=>{
 const t=await setup();await t.click({page:'properties'});await t.click({action:'delete',kind:'property',id:'own-p1'});const html=t.document.getElementById('modal-root').innerHTML;assert.match(html,/Törlöd ezt a profilt\?/);assert.match(html,/nem állítható vissza/);assert.match(html,/korábbi párosítások és beszélgetések megmaradnak/);assert.doesNotMatch(html,/Archivál|archivál/);assert.match(html,/>Törlés<\/button>/);const before=t.model.matches().map(item=>item.id);await t.click({action:'confirm-delete',kind:'property',id:'own-p1'});assert.equal(t.model.getState().properties.find(item=>item.id==='own-p1').archived,true);assert.doesNotMatch(t.document.getElementById('app').innerHTML,/data-action="edit" data-kind="property" data-id="own-p1"/);assert.deepEqual(t.model.matches().map(item=>item.id),before);assert.match(t.document.getElementById('toast').textContent,/töröltük/);
});
test('refund ledger and saved paid interest show the credited amount without hiding the original like',async()=>{
 const state=createModel({getItem:()=>null,setItem:()=>{}}).getState();state.decisions=[{id:'refunded',actorKind:'search',actorId:'own-s1',propertyId:'p1',searchId:'own-s1',liked:true,charged:1,createdAt:'2026-10-01T00:00:00Z',refundedAt:'2026-10-15T00:00:00Z',property:{id:'p1',ownerId:'u1',ownerAccountType:'private',title:'Visszatérített otthon',city:'Budapest',price:70,area:60,rooms:2,images:[]}}];state.matches=[];state.ledger=[{id:'refund-ledger',kind:'like_refund',amount:1,description:'Kreditvisszatérítés: 14 napig nem érkezett válasz.',createdAt:'2026-10-15T00:00:00Z'}];const t=await setup({hosted:true,authenticated:true,apiOverrides:{getState:async()=>state,matches:async()=>[]}});await t.click({action:'tab',tab:'liked'});let html=t.document.getElementById('app').innerHTML;assert.match(html,/Kredit visszatérítve/);assert.match(html,/\+1 kredit visszatérítve/);assert.match(html,/Visszatérített otthon/);await t.click({page:'credits'});html=t.document.getElementById('app').innerHTML;assert.match(html,/14 nap után visszatérítve/);assert.match(html,/\+1 kredit/);
});

test('public and authentication routes cannot act on a hidden paid discovery candidate',async()=>{
 const t=await setup();await t.click({action:'activate-one',kind:'property',id:'own-p1'});const before=t.model.getState();
 for(const route of ['landing','login','register']){
  if(route==='landing')await t.click({action:'landing'});else await t.click({action:'auth-mode',mode:route});
  for(const key of ['ArrowLeft','ArrowRight'])await t.document.handlers.keydown({key,target:{closest:()=>null},preventDefault(){}});
  await t.click({action:'like'});assert.deepEqual(t.model.getState(),before,'A hidden candidate must never make a decision or spend credits');
 }
});

test('a delayed auth route event preserves entered registration details while browser navigation still switches forms',async()=>{
 const t=await setup({hosted:true});await t.click({action:'auth-mode',mode:'register'});
 t.document.getElementById('f-name').value='Teszt Név';t.document.getElementById('f-email').value='teszt@example.test';
 t.windowEvents.hashchange();await settle();assert.equal(t.document.getElementById('f-name').value,'Teszt Név');assert.equal(t.document.getElementById('f-email').value,'teszt@example.test');
 t.ctx.location.hash='#login';t.windowEvents.hashchange();await settle();assert.equal(t.document.getElementById('f-name'),null);assert.ok(t.document.getElementById('hosted-auth-form'));
});

function partialOnlyFixture(){return accountFixture(raw=>{
 raw.matches=[];raw.decisions=[];raw.reports=[];
 raw.properties=raw.properties.filter(item=>item.ownerId==='me'||['p1','p2'].includes(item.id));
 Object.assign(raw.searches.find(item=>item.id==='own-s1'),{minPrice:null,maxPrice:10,minArea:50,maxArea:85,minRooms:2,maxRooms:4,conditions:[],buildings:[],heatingTypes:[],balcony:false,elevator:false});
});}

test('partial recommendations remain hidden without clicking the single consent action',async()=>{
 const t=await setup({initialRaw:partialOnlyFixture()}),before=t.model.getState();
 assert.equal(t.document.getElementById('candidate'),null);assert.match(t.document.getElementById('app').innerHTML,/Elfogytak a tökéletes egyezések/);
 assert.doesNotMatch(t.document.getElementById('app').innerHTML,/approximate-decline|Csak tökéletes egyezések|Nem, csak/);
 assert.equal((t.document.getElementById('app').innerHTML.match(/data-action="approximate-accept"/g)||[]).length,1);
 await t.ui.render();assert.deepEqual(t.model.getState(),before);assert.equal(t.document.getElementById('modal-root').innerHTML,'');
 await t.click({action:'approximate-accept'});assert.ok(t.document.getElementById('candidate'));assert.match(t.document.getElementById('app').innerHTML,/Részleges egyezések/);
 const candidate=t.model.feed({includeApproximate:true})[0];await t.click({action:'pass'});
 assert.ok(t.model.getState().decisions.some(item=>item.propertyId===candidate.id&&item.actorKind==='search'&&item.liked===false));
});

test('partial consent resets when the active profile or its criteria change',async()=>{
 const t=await setup({initialRaw:partialOnlyFixture()});await t.click({action:'approximate-accept'});assert.ok(t.document.getElementById('candidate'));
 await t.click({action:'activate-one',kind:'search',id:'own-s2'});
 await t.click({action:'activate-one',kind:'search',id:'own-s1'});assert.equal(t.document.getElementById('candidate'),null);assert.match(t.document.getElementById('app').innerHTML,/Elfogytak a tökéletes egyezések/);
 await t.click({action:'approximate-accept'});const search=t.model.getState().searches.find(item=>item.id==='own-s1');t.model.saveEntity('search',{...search,maxPrice:11},search.id);await t.ui.render();
 assert.equal(t.document.getElementById('candidate'),null);assert.match(t.document.getElementById('app').innerHTML,/Elfogytak a tökéletes egyezések/);
});

test('zero-percent partial cards stay zero and describe deviations without positive hardcoded tags',async()=>{
 const seed=createModel({getItem:()=>null,setItem:()=>{}}).feed()[0];
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{recommendations:({includeApproximate=false}={})=>includeApproximate?{items:[{...seed,score:0,isExact:false,reasons:['Az ár meghaladja a keretet'],matchDetails:[]}],stage:'approximate'}:{items:[],stage:'empty',requiresApproximateConsent:true,hasApproximate:true}}});
 await t.click({action:'approximate-accept'});const html=t.document.getElementById('app').innerHTML;
 assert.match(html,/0% egyezés/);assert.doesNotMatch(html,/97% egyezés|Árkereten belül|Kedvenc környékeden/);assert.match(html,/Az ár meghaladja a keretet/);
});

test('a late partial response cannot transfer consent or recommendations to another active profile',async()=>{
 const local=createModel({getItem:()=>JSON.stringify(partialOnlyFixture()),setItem:()=>{}}),seed=local.feed({includeApproximate:true})[0];let release;
 const pending=new Promise(resolve=>{release=resolve;});
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{getState:()=>local.getState(),activate:(kind,id)=>local.activate(kind,id),recommendations:({includeApproximate=false}={})=>{
  const active={...local.getState().active};return includeApproximate?pending.then(()=>({active,items:[{...seed,score:15,isExact:false}],stage:'approximate'})):{active,items:[],stage:'empty',requiresApproximateConsent:true,hasApproximate:true};
 }}});
 const accepting=t.click({action:'approximate-accept'});await settle();local.activate('search','own-s2');await t.ui.render();release();await accepting;
 assert.equal(t.ui.getModelState().active.id,'own-s2');assert.equal(t.document.getElementById('candidate'),null);assert.match(t.document.getElementById('app').innerHTML,/Elfogytak a tökéletes egyezések/);
});

test('search specialization appears on seller recommendation cards and own searches',async()=>{
 const t=await setup();await t.click({action:'activate-one',kind:'property',id:'own-p1'});assert.match(t.document.getElementById('app').innerHTML,/[\d,]+%-ban fókuszált keresés/);
 await t.click({page:'searches'});assert.match(t.document.getElementById('app').innerHTML,/[\d,]+%-ban fókuszált keresés/);
});


test('discovery shows concise fulfilled conditions and only the other party value for unmet conditions',async()=>{
 const local=createModel({getItem:()=>null,setItem:()=>{}}),seed=local.feed()[0],matchDetails=[
  {key:'rooms',label:'Szobaszám',expected:'legalább 3 szoba',actual:'2 szoba',matches:false},
  {key:'area',label:'Alapterület',expected:'50–80 m²',actual:'65 m²',matches:true},
  {key:'price',label:'Ár',expected:'legfeljebb 85 M Ft',actual:'72,9 M Ft',matches:true},
  {key:'building',label:'Falazat',expected:'Tégla <és> kő',actual:'Panel',matches:false},
  {key:'location',label:'Helyszín',expected:'PRIVATE-LOCATION',actual:'PRIVATE-LOCATION',matches:true},
  {key:'type',label:'Ingatlantípus',expected:'PRIVATE-TYPE',actual:'PRIVATE-TYPE',matches:true}];
 for(const kind of ['property','search']){
  const own=local.getState();own.active={kind:kind==='property'?'search':'property',id:kind==='property'?'own-s1':'own-p1'};
  const card={...seed,kind,score:77,isExact:false,ownerFirstName:'Anna <teszt>',matchDetails};
  const t=await setup({hosted:true,authenticated:true,apiOverrides:{getState:()=>own,recommendations:({includeApproximate=false}={})=>includeApproximate?{items:[card],stage:'approximate'}:{items:[],stage:'empty',requiresApproximateConsent:true}}});
  await t.click({action:'approximate-accept'});
  const html=t.ui.matchingTags(card);
  assert.match(html,/Eltérő feltételek/);assert.match(html,/Teljesülő feltételek/);
  assert.match(html,/Árban megfelelő/);assert.match(html,/Megfelelő alapterület/);
  assert.doesNotMatch(html,/PRIVATE-LOCATION|PRIVATE-TYPE|data-criterion="(?:location|type)"/);
  assert.doesNotMatch(html,/50–80|65 m²|85 M Ft|72,9 M Ft|Keresés:|Ingatlan:/,'Fulfilled criteria never repeat detailed bounds or listing values');
  assert.match(html,/criterion-passed/);assert.match(html,/criterion-different/);
  if(kind==='property'){
   assert.match(html,/2 szoba/);assert.match(html,/Panel/);
   assert.doesNotMatch(html,/legalább 3 szoba|Tégla/,'A buyer sees only the foreign property values, not their own search');
  }else{
   assert.match(html,/legalább 3 szoba/);assert.match(html,/Tégla &lt;és&gt; kő/);
   assert.doesNotMatch(html,/2 szoba|Panel|<és>/,'A seller sees only the foreign search values, escaped as plain text');
  }
  assert.match(t.document.getElementById('app').innerHTML,/Anna &lt;teszt&gt;/);
 }
});

test('hard-only match details do not produce a fulfilled condition section or revive legacy hard-gate reasons',async()=>{
 const t=await setup(),card={kind:'property',isExact:true,reasons:['Megfelelő elhelyezkedés','Megfelelő ingatlantípus'],matchDetails:[
  {key:'location',label:'Helyszín',expected:'Debrecen',actual:'Debrecen',matches:true},
  {key:'type',label:'Ingatlantípus',expected:'Lakás',actual:'Lakás',matches:true}]};
 assert.equal(t.ui.matchingTags(card),'');
});

test('public cards display listing titles, discreet types and first names',async()=>{
 const t=await setup({hosted:true,hash:''}),html=t.document.getElementById('app').innerHTML;
 for(const text of ['Kertes otthont keresünk','Napfényes erkélyes otthon','Anna','Péter','lakást keres','landing-ad-title','landing-type','owner-first-name'])assert.ok(html.includes(text),text);
 assert.doesNotMatch(html,/Lakást keresnek|Eladó lakás/);
});

test('seller insights are property scoped, anonymous and show an active package without another purchase',async()=>{
 const m=createModel({getItem:()=>null,setItem:()=>{}}),own=m.getState(),property=own.properties[0],calls=[];
 const insights={propertyId:property.id,stats:{uniqueViewers:24,buyerLikes:7,sellerLikes:5,matchedViewers:3,matchRate:12.5},feedback:{total:2,items:[{id:'r1',reason:'layout',label:'Elrendezés',createdAt:'2026-11-10T10:00:00Z'}],reasonCounts:[{reason:'layout',label:'Elrendezés',count:2}],offset:0,limit:50,hasMore:false},activePackage:{id:'pack',size:10,receivedCount:2,remaining:8,enabled:true,createdAt:'2026-11-10T10:00:00Z',expiresAt:'2026-11-24T10:00:00Z',status:'active'},packages:[]};
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{getPropertyInsights:async(id)=>{calls.push(id);return insights;}}});
 await t.click({action:'property-insights',id:property.id});const html=t.document.getElementById('app').innerHTML;
 assert.equal(calls.at(-1),property.id);for(const text of ['Statisztikák és visszajelzések','Látták','Kedvelték','Kedvelt keresések','12,5','2 db','2 / 10','8 még hiányzik','név nélkül'])assert.ok(html.includes(text),text);
 assert.doesNotMatch(html,/data-action="feedback-packages"/,'An active package cannot offer another purchase');
 assert.doesNotMatch(html,/data-action="feedback-toggle"|szüneteltet|folytathatod/,'An active paid package cannot be paused');
 await t.click({action:'feedback-toggle',id:property.id,enabled:'false'});assert.equal(insights.activePackage.enabled,true,'An obsolete pause action cannot alter the package');
 assert.doesNotMatch(t.document.getElementById('app').innerHTML,/buyerId|searchRequestId|PRIVATE-CONTACT/);
});

test('package purchase shows sizes and cost, and retains its UUID when a failed payment is retried',async()=>{
 const attempts=[],t=await setup({hosted:true,authenticated:true,apiOverrides:{buyFeedbackPackage:async(id,size,request)=>{attempts.push({id,size,request});throw new Error('Átmeneti hiba');}}});
 const property=t.model.getState().properties[0];t.ui.openFeedbackPackages(property.id);let html=t.document.getElementById('modal-root').innerHTML;
 for(const size of [10,20,50])assert.match(html,new RegExp('data-size="'+size+'"'));assert.match(html,/két hétig/);assert.match(html,/kreditet írunk jóvá/);assert.doesNotMatch(html,/válaszok árát|visszajelzések árát/);
 await t.click({action:'feedback-plan',id:property.id,size:'10'});html=t.document.getElementById('modal-root').innerHTML;assert.match(html,/Csomag indítása · 10 kredit/);
 const request=html.match(/data-request="([^"]+)"/)[1];assert.match(request,/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
 await t.click({action:'feedback-buy',id:property.id,size:'10',request});await t.click({action:'feedback-buy',id:property.id,size:'10',request});
 assert.equal(attempts.length,2);assert.equal(attempts[0].request,request);assert.equal(attempts[1].request,request);assert.match(t.document.getElementById('modal-root').innerHTML,/Csomag indítása/);
});

test('pending feedback blocks the next card and sends a single button choice before closing',async()=>{
 const options=feedbackHelpers.FEEDBACK_OPTIONS,prompt={id:'invitation',propertyId:'p1',title:'Segíts Péternek egy visszajelzéssel',question:'Miért nem tetszett az ingatlan?',options},impressions=[],answers=[];let pending=prompt,finish;
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{pendingFeedback:async()=>({feedbackPrompt:pending}),recordImpression:async(...args)=>{impressions.push(args);},answerFeedback:async(id,reason)=>{answers.push({id,reason});await new Promise(resolve=>{finish=resolve;});pending=null;return{accepted:true,alreadyAnswered:false};}}});
 let html=t.document.getElementById('modal-root').innerHTML;assert.equal(t.document.getElementById('candidate'),null);assert.equal(impressions.length,0);
 assert.match(html,/Segíts Péternek egy visszajelzéssel/);assert.match(html,/Miért nem tetszett az ingatlan/);assert.equal((html.match(/data-action="feedback-answer"/g)||[]).length,8);assert.doesNotMatch(html,/modal-close|data-action="close"/);
 await t.click({action:'close'});assert.match(t.document.getElementById('modal-root').innerHTML,/feedback-survey/);
 const answering=t.click({action:'feedback-answer',reason:'layout'});await settle();assert.deepEqual(answers,[{id:'invitation',reason:'layout'}]);assert.match(t.document.getElementById('modal-root').innerHTML,/feedback-survey/,'The window stays until persistence succeeds');
 finish();await answering;await settle();assert.equal(t.document.getElementById('modal-root').innerHTML,'');assert.ok(t.document.getElementById('candidate'));assert.equal(impressions.length,1);
});

test('feedback decline and expired requests continue discovery without sending a paid response',async()=>{
 for(const expired of [false,true]){let pending={id:'survey',propertyId:'p1',title:'Segíts Annának egy visszajelzéssel',options:feedbackHelpers.FEEDBACK_OPTIONS},answer;
  const t=await setup({hosted:true,authenticated:true,apiOverrides:{pendingFeedback:async()=>pending,answerFeedback:async(id,reason)=>{answer={id,reason};pending=null;if(expired)throw Object.assign(new Error('Lejárt'),{status:410});return {accepted:false,alreadyAnswered:false};}}});
  await t.document.handlers.keydown({key:'Escape',preventDefault(){this.defaultPrevented=true;}});assert.deepEqual(answer,{id:'survey',reason:'decline'});assert.equal(t.document.getElementById('modal-root').innerHTML,'');assert.ok(t.document.getElementById('candidate'));
 }
});

test('discovery records only the visible buyer card once and ignores stale visibility callbacks',async()=>{
 const observers=[],calls=[];class Observer{constructor(callback){this.callback=callback;observers.push(this);}observe(){}disconnect(){}}
 const t=await setup({hosted:true,authenticated:true,IntersectionObserver:Observer,apiOverrides:{recordImpression:async(...args)=>calls.push(args)}});
 assert.equal(calls.length,0);const first=observers.at(-1);first.callback([{isIntersecting:false,intersectionRatio:0}]);await settle();assert.equal(calls.length,0);
 first.callback([{isIntersecting:true,intersectionRatio:.5}]);await settle();assert.equal(calls.length,1);assert.equal(calls[0][1],t.model.getState().active.id);
 await t.ui.render();observers.at(-1).callback([{isIntersecting:true,intersectionRatio:.5}]);await settle();assert.equal(calls.length,1,'Repaints do not add another viewer');
 await t.click({page:'properties'});first.callback([{isIntersecting:true,intersectionRatio:1}]);await settle();assert.equal(calls.length,1,'A stale callback cannot count a hidden candidate');
 await t.click({action:'activate-one',kind:'property',id:'own-p1'});assert.equal(calls.length,1,'Seller-side search cards never count as property exposure');
});

test('focused-search badge opens a plain explanation and separates focus from the match percentage',async()=>{
 const t=await setup();await t.click({action:'activate-one',kind:'property',id:'own-p1'});
 let html=t.document.getElementById('app').innerHTML;assert.match(html,/[\d,]+%-ban fókuszált keresés/);assert.match(html,/data-action="focus-info"/);assert.doesNotMatch(html,/Specializáltság:/);
 await t.click({action:'focus-info'});html=t.document.getElementById('modal-root').innerHTML;
 assert.match(html,/Mit jelent a fókuszált keresés\?/);assert.match(html,/szűkebb ár-, méret- és szobatartomány/);assert.match(html,/kártya tetején látható egyezési százalék/);
});

test('the report dialog contains ordered radios only and a duplicate report persists as its own reason',async()=>{
 const t=await setup();await t.click({action:'report-account',kind:'property',id:'p1'});const html=t.document.getElementById('modal-root').innerHTML;
 assert.match(html,/aria-labelledby="report-question"/);assert.equal((html.match(/type="radio"/g)||[]).length,accountHelpers.REPORT_REASON_OPTIONS.length);assert.doesNotMatch(html,/<select|Jelentés oka|A következő fejezeted|profilnál|Korábban jelzett/);
 const values=[...html.matchAll(/type="radio" name="reportReason" value="([^"]+)"/g)].map(match=>match[1]);assert.deepEqual(values,accountHelpers.REPORT_REASON_OPTIONS.map(option=>option.value));
 chooseReport(t,'duplicate_listing');await t.click({action:'confirm-report',kind:'property',id:'p1'});assert.equal(t.model.getState().reportedEntities[0].reason,'duplicate_listing');
});

test('seller insights omit measurement and frequency boilerplate and express refunds only as credits',async()=>{
 const t=await setup();await t.click({action:'property-insights',id:'own-p1'});let html=t.document.getElementById('app').innerHTML;
 assert.doesNotMatch(html,/A megjelenések mérése|1 visszajelzés = 1 kredit|A keresők csak ritkán kapnak/);
 await t.click({action:'feedback-packages',id:'own-p1'});html=t.document.getElementById('modal-root').innerHTML;assert.match(html,/kreditet írunk jóvá/);assert.doesNotMatch(html,/hiányzó.*árát/);
 await t.click({action:'feedback-plan',id:'own-p1',size:'10'});html=t.document.getElementById('modal-root').innerHTML;assert.match(html,/kreditet írunk jóvá/);assert.doesNotMatch(html,/hiányzó.*árát/);
});

test('feedback trial controls require explicit hosted-test capability and reset through the model',async()=>{
 const scenario={available:true,role:'buyer',propertyId:'own-p1',searchId:'own-s1',buyerEmail:'visszajelzes-kereso@otthonra.local',sellerEmail:'visszajelzes-elado@otthonra.local'};let resets=0,release;
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{getFeedbackScenario:()=>scenario,resetFeedbackScenario:()=>{resets++;return new Promise(resolve=>{release=resolve;});}}});
 assert.match(t.document.getElementById('app').innerHTML,/Visszajelzés-próba|visszajelzes-kereso@otthonra.local/);
 assert.ok(t.document.getElementById('candidate'));const pending=t.click({action:'feedback-scenario-reset'});await settle();assert.equal(resets,1);assert.equal(t.document.getElementById('candidate'),null);assert.match(t.document.getElementById('app').innerHTML,/feedback-scenario-resetting/);release();await pending;assert.equal(t.ctx.location.hash,'#discover');assert.ok(t.document.getElementById('candidate'));
 const selected=[];const seller=await setup({hosted:true,authenticated:true,apiOverrides:{getFeedbackScenario:()=>({...scenario,role:'seller'}),resetFeedbackScenario:()=>{},getPropertyInsights:id=>{selected.push(id);return {stats:{},feedback:{items:[],reasonCounts:[]}};}}});await seller.click({action:'feedback-scenario-reset'});assert.equal(seller.ctx.location.hash,'#insights');assert.equal(selected.at(-1),scenario.propertyId);
 const ordinary=await setup({hosted:true,authenticated:true,apiOverrides:{getFeedbackScenario:()=>({available:false})}});assert.doesNotMatch(ordinary.document.getElementById('app').innerHTML,/feedback-scenario-reset/);
 const production=await setup({hosted:true,authenticated:true,environment:'production',apiOverrides:{getFeedbackScenario:()=>{throw new Error('No test endpoint in production');}}});assert.doesNotMatch(production.document.getElementById('app').innerHTML,/feedback-scenario-reset|Nem érhető el a munkatér/);
});

function editorChoice(t,name,value){
 const ids=[...t.document.html.matchAll(new RegExp('<input\\b[^>]*\\bid="([^\"]+)"[^>]*\\bname="'+name+'"[^>]*>','g'))].map(match=>match[1]);
 const choice=ids.map(id=>t.document.getElementById(id)).find(input=>input.value===String(value));assert.ok(choice,`Missing ${name} choice ${value}`);return choice;
}
async function advanceEditor(t,target){
 for(let attempt=0;editorStep(t)<target&&attempt<5;attempt++){
  const before=editorStep(t);await editorAction(t,'editor-next');assert.equal(editorStep(t),before+1,'A valid step must advance exactly once');
 }
 assert.equal(editorStep(t),target);
}

test('search editor exposes named stages, validates the current topic and retains all mounted values when revisiting',async()=>{
 const t=await setup(),saved=[],save=t.model.saveEntity;t.model.saveEntity=(...args)=>{saved.push(args);return save(...args);};
 t.ui.openEditor('search');const form=t.document.getElementById('entity-form'),html=t.document.getElementById('modal-root').innerHTML;
 for(const label of ['Helyszín és típus','Ár és méret','Ingatlanjellemzők','Kényelem és felszereltség','További elképzelések'])assert.ok(html.includes(label),label);
 assert.equal(editorStep(t),0);assert.equal(t.document.getElementById('editor-back').hidden,true);
 await editorAction(t,'editor-next');assert.equal(editorStep(t),0);assert.equal(t.document.activeElement.id,'f-type');
 assert.ok(t.document.getElementById('f-type').reportedValidity>0);assert.equal(saved.length,0);
 const type=t.document.getElementById('f-type');type.value='Lakás';type.handlers.change({target:type,currentTarget:type});chooseLocation(t,'city:Debrecen');chooseLocation(t,'city:Hajdúszoboszló');
 await editorAction(t,'editor-next');assert.equal(editorStep(t),1);
 assert.equal(t.document.getElementById('editor-step-button-1').getAttribute('aria-current'),'step');
 assert.equal(t.document.getElementById('editor-step-button-0').getAttribute('data-editor-state'),'completed');
 t.document.getElementById('f-maxPrice').value='125';t.document.getElementById('f-minArea').value='65';t.document.getElementById('f-minRooms').value='3';
 for(const name of ['minPrice','maxArea','maxRooms'])t.document.getElementById('f-'+name).value='';
 await editorAction(t,'editor-next');assert.equal(editorStep(t),2);
 editorChoice(t,'conditions','Jó').checked=true;editorChoice(t,'conditions','Új/felújított').checked=true;editorChoice(t,'buildings','Tégla').checked=true;
 await editorAction(t,'editor-next');assert.equal(editorStep(t),3);
 editorChoice(t,'heatingTypes','Hőszivattyú').checked=true;editorChoice(t,'floors','0').checked=true;t.document.getElementById('f-ceilingHeight').value='3 m feletti';
 await editorAction(t,'editor-next');assert.equal(editorStep(t),4);const title=t.document.getElementById('f-title');assert.match(title.value,/Debrecen/);assert.match(title.value,/125/);title.value='Megőrzött keresési elképzelés';title.handlers.input({target:title});t.document.getElementById('f-description').value='Fényes, csendes otthont szeretnénk.';
 await editorAction(t,'editor-back');assert.equal(editorStep(t),3);assert.equal(editorChoice(t,'heatingTypes','Hőszivattyú').checked,true);
 await editorAction(t,'editor-step-button-0');assert.equal(editorStep(t),0);
 assert.match(t.document.getElementById('location-chips').innerHTML,/Debrecen/);assert.match(t.document.getElementById('location-chips').innerHTML,/Hajdúszoboszló/);
 assert.equal(t.document.getElementById('f-title').value,'Megőrzött keresési elképzelés');assert.equal(t.document.getElementById('f-maxPrice').value,'125');
 assert.equal(editorChoice(t,'conditions','Új/felújított').checked,true);assert.equal(t.document.getElementById('f-description').value,'Fényes, csendes otthont szeretnénk.');
 assert.equal(t.document.getElementById('entity-form'),form,'Step navigation must preserve the mounted form');assert.equal(saved.length,0,'Navigation never saves a draft entity');
 await editorAction(t,'editor-step-button-4');assert.equal(editorStep(t),4);submitEditor(t);await settle();
 assert.equal(saved.length,1);const result=t.model.getState().searches.find(item=>item.title==='Megőrzött keresési elképzelés');assert.ok(result);
 assert.deepEqual([...result.locationIds],['city:Debrecen','city:Hajdúszoboszló']);assert.equal(result.maxPrice,125);assert.equal(result.minArea,65);assert.equal(result.minRooms,3);
 for(const name of ['minPrice','maxArea','maxRooms'])assert.equal(result[name],null);
 assert.deepEqual([...result.conditions],['Jó','Új/felújított']);assert.deepEqual([...result.heatingTypes],['Hőszivattyú']);assert.deepEqual([...result.floors],[0]);assert.equal(result.description,'Fényes, csendes otthont szeretnénk.');
 assert.match(t.document.getElementById('modal-root').innerHTML,/Ingatlanok felfedezése/);
});

test('seller wizard preserves required house plot, nullable amenities, image URLs and multiple parking choices through backtracking',async()=>{
 const t=await setup(),before=t.model.getState(),saved=[],save=t.model.saveEntity;t.model.saveEntity=(...args)=>{saved.push(args);return save(...args);};
 t.ui.openEditor('property');const html=t.document.getElementById('modal-root').innerHTML;
 for(const label of ['Alapadatok','Ár és méret','Ingatlanjellemzők','Felszereltség','Képek és leírás'])assert.ok(html.includes(label),label);
 chooseLocation(t,'city:Solymár');t.document.getElementById('f-street').value='Teszt utca';t.document.getElementById('f-houseNumber').value='12/A';
 const type=t.document.getElementById('f-type');type.value='Ház';type.handlers.change({target:type,currentTarget:type});
 await editorAction(t,'editor-next');assert.equal(editorStep(t),1);
 for(const [name,value] of Object.entries({price:'110.5',area:'130.5',wholeRooms:'3',halfRooms:'1'}))t.document.getElementById('f-'+name).value=value;
 await editorAction(t,'editor-next');assert.equal(editorStep(t),1,'A house cannot advance without its plot');assert.equal(t.document.activeElement.id,'f-lotArea');
 t.document.getElementById('f-lotArea').value='720';await editorAction(t,'editor-next');assert.equal(editorStep(t),2);
 t.document.getElementById('f-condition').value='Jó';t.document.getElementById('f-building').value='Tégla';
 await editorAction(t,'editor-next');assert.equal(editorStep(t),3);
 for(const [name,value] of Object.entries({heatingType:'Hőszivattyú',secondaryHeatingType:'Klíma',insulated:'false',airConditioning:'true',solarPanels:'',energyRating:'A+'}))t.document.getElementById('f-'+name).value=value;
 editorChoice(t,'parkingTypes','Garázs').checked=true;editorChoice(t,'parkingTypes','Udvari beálló').checked=true;
 await editorAction(t,'editor-next');assert.equal(editorStep(t),4);
 const title=t.document.getElementById('f-title');assert.match(title.value,/Solymár/);assert.match(title.value,/Ház/);title.value='Lépésenként megőrzött családi ház';title.handlers.input({target:title});
 t.document.getElementById('property-images').value='https://example.test/elol.jpg\nhttps://example.test/kert.jpg';t.document.getElementById('f-description').value='Az eddig bevitt részletek maradjanak meg.';
 await editorAction(t,'editor-step-button-1');assert.equal(editorStep(t),1);assert.equal(t.document.getElementById('f-lotArea').value,'720');
 await editorAction(t,'editor-step-button-3');assert.equal(t.document.getElementById('f-insulated').value,'false');assert.equal(t.document.getElementById('f-solarPanels').value,'');assert.equal(editorChoice(t,'parkingTypes','Garázs').checked,true);
 await editorAction(t,'editor-step-button-4');assert.match(t.document.getElementById('property-images').value,/kert\.jpg/);assert.equal(saved.length,0);
 submitEditor(t);await settle();assert.equal(saved.length,1);
 const result=t.model.getState().properties.find(item=>item.title==='Lépésenként megőrzött családi ház');assert.ok(result);assert.equal(result.lotArea,720);assert.equal(result.insulated,false);assert.equal(result.airConditioning,true);assert.equal(result.solarPanels,null);assert.equal(result.wholeRooms,3);assert.equal(result.halfRooms,1);
 assert.deepEqual([...result.parkingTypes],['Udvari beálló','Garázs']);assert.deepEqual([...result.images],['https://example.test/elol.jpg','https://example.test/kert.jpg']);assert.equal(result.floor,null);assert.equal(result.balcony,false);assert.equal(result.elevator,false);
 assert.deepEqual(t.model.getState().active,before.active);
});

test('final wizard submission revisits an invalid earlier topic instead of silently saving hidden invalid controls',async()=>{
 const t=await setup(),calls=[],save=t.model.saveEntity;t.model.saveEntity=(...args)=>{calls.push(args);return save(...args);};
 t.ui.openEditor('search','own-s1');await advanceEditor(t,4);
 t.document.getElementById('f-maxPrice').value='';submitEditor(t);await settle();
 assert.equal(editorStep(t),1);assert.equal(t.document.activeElement.id,'f-maxPrice');assert.equal(calls.length,0);assert.equal(t.document.getElementById('f-maxPrice').hidden,false);
 t.document.getElementById('f-maxPrice').value='95';await advanceEditor(t,4);submitEditor(t);await settle();assert.equal(calls.length,1);assert.equal(t.model.getState().searches.find(item=>item.id==='own-s1').maxPrice,95);
 assert.equal(t.document.getElementById('modal-root').innerHTML,'','An edit does not open the new-search activation offer');
});

test('wizard range errors stay in the price and size topic and future-step clicks cannot bypass validation',async()=>{
 const t=await setup();t.ui.openEditor('search');
 await editorAction(t,'editor-step-button-4');assert.equal(editorStep(t),0,'A future topic cannot bypass missing required earlier details');assert.equal(t.document.activeElement.id,'f-type');
 const type=t.document.getElementById('f-type');type.value='Lakás';type.handlers.change({target:type,currentTarget:type});chooseLocation(t,'city:Debrecen');await editorAction(t,'editor-next');
 t.document.getElementById('f-minPrice').value='100';t.document.getElementById('f-maxPrice').value='80';await editorAction(t,'editor-next');assert.equal(editorStep(t),1);assert.ok(t.document.activeElement.validationMessage);
 t.document.getElementById('f-minPrice').value='';t.document.getElementById('f-minArea').value='40';await editorAction(t,'editor-next');assert.equal(editorStep(t),2);
 await editorAction(t,'editor-back');assert.equal(editorStep(t),1);assert.equal(t.document.getElementById('f-maxPrice').value,'80');
});

test('wizard editing and cancellation preserve the saved entity and clean up location listeners',async()=>{
 const t=await setup(),before=t.model.getState(),pointers=t.document.listenerCount('pointerdown'),focus=t.document.listenerCount('focusin');
 t.ui.openEditor('search','own-s1');const originalTitle=t.document.getElementById('f-title').value;assert.equal(originalTitle,before.searches.find(item=>item.id==='own-s1').title);
 t.document.getElementById('f-title').value='Ez még csak piszkozat';await advanceEditor(t,3);await editorAction(t,'editor-step-button-0');assert.equal(t.document.getElementById('f-title').value,'Ez még csak piszkozat');
 await t.click({action:'close'});assert.equal(t.document.getElementById('modal-root').innerHTML,'');assert.deepEqual(t.model.getState(),before);
 assert.equal(t.document.listenerCount('pointerdown'),pointers);assert.equal(t.document.listenerCount('focusin'),focus);
});

test('discovery dock follows the active candidate and disappears for empty feeds, partial consent and pending feedback',async()=>{
 const t=await setup();let html=t.document.getElementById('app').innerHTML;assert.match(html,/discovery-decision-dock/);assert.match(html,/class="card-actions"/);
 await t.click({action:'activate-one',kind:'property',id:'own-p1'});html=t.document.getElementById('app').innerHTML;assert.match(html,/discovery-decision-dock/);assert.match(html,/Kedvelés<\/span><small>2 kredit/);
 await t.click({page:'properties'});assert.doesNotMatch(t.document.getElementById('app').innerHTML,/discovery-decision-dock/);
 const empty=await setup({hosted:true,authenticated:true,apiOverrides:{recommendations:()=>({items:[],stage:'empty'})}});assert.doesNotMatch(empty.document.getElementById('app').innerHTML,/discovery-decision-dock/);
 const partial=await setup({hosted:true,authenticated:true,apiOverrides:{recommendations:()=>({items:[],stage:'empty',requiresApproximateConsent:true})}});assert.doesNotMatch(partial.document.getElementById('app').innerHTML,/discovery-decision-dock/);
 const pending=await setup({hosted:true,authenticated:true,apiOverrides:{pendingFeedback:()=>({feedbackPrompt:{id:'pending',title:'Segíts egy visszajelzéssel',options:feedbackHelpers.FEEDBACK_OPTIONS}})}});assert.doesNotMatch(pending.document.getElementById('app').innerHTML,/discovery-decision-dock/);
});

test('wizard final-save retries cannot duplicate a pending write or navigate away from the submitted topic',async()=>{
 const t=await setup(),save=t.model.saveEntity,calls=[];let release;
 t.ui.openEditor('search','own-s1');await advanceEditor(t,4);
 t.document.getElementById('f-description').value='Egyetlen mentésből létrejövő módosítás.';
 t.model.saveEntity=async(...args)=>{calls.push(args);await new Promise(resolve=>{release=resolve;});return save(...args);};
 submitEditor(t);await settle();assert.equal(calls.length,1);
 submitEditor(t);await editorAction(t,'editor-back');assert.equal(editorStep(t),4);assert.equal(calls.length,1);
 release();await settle();assert.equal(calls.length,1);assert.equal(t.document.getElementById('modal-root').innerHTML,'');
 assert.equal(t.model.getState().searches.find(item=>item.id==='own-s1').description,'Egyetlen mentésből létrejövő módosítás.');
});

test('editing a saved holiday-home property or search preserves its existing type throughout the wizard and final save',async()=>{
 let raw;const seed=createModel({getItem:()=>null,setItem:(_key,value)=>{raw=JSON.parse(value);}});seed.activate('search','own-s1');
 raw.properties.find(item=>item.id==='own-p1').type='Nyaraló';raw.searches.find(item=>item.id==='own-s1').type='Nyaraló';
 for(const kind of ['property','search']){
  const t=await setup({initialRaw:raw}),id=kind==='property'?'own-p1':'own-s1';
  t.ui.openEditor(kind,id);const type=t.document.getElementById('f-type');assert.equal(type.value,'Nyaraló','A saved type outside the creation choices must remain selected');
  await advanceEditor(t,4);await editorAction(t,'editor-step-button-0');assert.equal(t.document.getElementById('f-type'),type);assert.equal(type.value,'Nyaraló');
  await editorAction(t,'editor-step-button-4');submitEditor(t);await settle();
  const collection=kind==='property'?t.model.getState().properties:t.model.getState().searches;
  assert.equal(collection.find(item=>item.id===id).type,'Nyaraló','Saving unrelated edits must not silently convert a holiday home into a flat');
  assert.equal(t.document.getElementById('modal-root').innerHTML,'');
 }
});


test('modal focus chooses the first visible enabled field before progress buttons and ignores closed or replaced modal timers',async()=>{
 const t=await setup({captureTimers:true});t.ui.openEditor('search');
 assert.equal(t.document.querySelector('.modal input,.modal select,.modal button,.modal textarea').id,'editor-step-button-0','Selector unions follow DOM order, so the original mixed query would focus a progress button');
 const before=t.document.focusEvents.length;t.runTimers();assert.equal(t.document.activeElement.id,'location-input');assert.deepEqual(t.document.focusEvents.slice(before),['location-input'],'Opening focus moves once directly to the first field');
 t.ui.openModal('<div id="hidden-fields" hidden><input id="hidden-field"></div><input id="disabled-field" disabled><textarea id="visible-field"></textarea><button id="visible-action">Folytatás</button>');
 t.runTimers();assert.equal(t.document.activeElement.id,'visible-field','Hidden ancestors and disabled controls cannot receive opening focus');
 t.ui.openModal('<button id="disabled-action" disabled>Nem</button><button id="hidden-action" hidden>Nem</button><button id="fallback-action">Rendben</button>');
 t.runTimers();assert.equal(t.document.activeElement.id,'fallback-action','An action-only dialog focuses its first enabled visible action');
 t.ui.openModal('<input id="replaced-field">');const replaced=t.document.querySelector('.modal');t.ui.openModal('<input id="replacement-field">');assert.notEqual(t.document.querySelector('.modal'),replaced);
 const replacementStart=t.document.focusEvents.length;t.runNextTimer();assert.equal(t.document.focusEvents.length,replacementStart,'The replaced dialog timer must not move focus into the new dialog');
 t.runNextTimer();assert.equal(t.document.activeElement.id,'replacement-field');assert.deepEqual(t.document.focusEvents.slice(replacementStart),['replacement-field']);
 t.ui.openModal('<input id="closed-field">');t.ui.closeModal();const closedStart=t.document.focusEvents.length;t.runTimers();assert.equal(t.document.focusEvents.length,closedStart,'A closed dialog timer cannot steal focus');
});

test('deferred modal opening focus preserves an editor control the user already focused',async()=>{
 const t=await setup({captureTimers:true});t.ui.openEditor('property','own-p1');
 const street=t.document.getElementById('f-street'),list=t.document.getElementById('street-options');
 street.focus();street.value='Pozsonyi';street.handlers.input();assert.equal(list.hidden,false);
 const before=t.document.focusEvents.length;t.runNextTimer();
 assert.equal(t.document.activeElement.id,street.id,'The opening focus timer must not interrupt typing in the street field');
 assert.equal(t.document.focusEvents.length,before,'A focused editor control must not be focused elsewhere again');
 assert.equal(street.value,'Pozsonyi');assert.equal(list.hidden,false);
});

function configuredCriteriaRaw(kind){
 let raw;const model=createModel({getItem:()=>null,setItem:(_key,value)=>{raw=JSON.parse(value);}});model.activate(kind,kind==='property'?'own-p1':'own-s1');
 Object.assign(raw.properties.find(item=>item.id==='own-p1'),{
  title:'Minden adat <otthon> & fény',type:'Lakás',locationId:'district:Budapest:5',city:'Budapest',district:'V.',neighborhood:'Belváros',address:'Budapest, Napfény utca 12.',addressDetails:{street:'Napfény utca',houseNumber:'12.',postalCode:'1051'},
  price:92.5,area:66.5,wholeRooms:2,halfRooms:1,rooms:2.5,floor:0,condition:'Átlagos',building:'Tégla',constructionAge:'31–40 év közötti',view:'Udvari',ceilingHeight:'3 m feletti',
  heatingType:'Nincs fűtés',secondaryHeatingType:'Klíma',insulated:false,energyRating:'BB',airConditioning:false,solarPanels:true,parkingTypes:['Udvari beálló','Garázs'],
  balcony:false,elevator:true,images:['https://example.test/elol.jpg','https://example.test/udvar.jpg'],description:'Tágas <belső> & csendes udvar.'
 });
 Object.assign(raw.searches.find(item=>item.id==='own-s1'),{
  title:'Minden feltétel <keresés> & tér',type:'Lakás',locationIds:['city:Debrecen','district:Budapest:5'],city:'Debrecen',districts:['V.'],
  minPrice:0,maxPrice:120.5,minArea:0,maxArea:150,minRooms:0,maxRooms:5.5,conditions:['Átlagos','Jó'],buildings:['Tégla','Panel'],
  constructionAges:['10 évnél fiatalabb','31–40 év közötti'],views:['Kertre néző','Panorámás'],heatingTypes:['Hőszivattyú','Klíma'],ceilingHeight:'3 m alatti',floors:[-1,0,11],
  balcony:true,elevator:true,moveIn:'Azonnal',financing:'Saját forrásból',description:'Csendes <kert> & tágas tér.'
 });
 return raw;
}
function criteriaRow(t,key){
 const html=t.document.getElementById('modal-root').innerHTML,match=html.match(new RegExp('<div\\b(?=[^>]*\\bdata-summary-field="'+key+'")[^>]*>\\s*<dt\\b[^>]*>([\\s\\S]*?)<\\/dt>\\s*<dd\\b[^>]*>([\\s\\S]*?)<\\/dd>'));
 assert.ok(match,`The criteria summary must include the configured ${key} parameter`);
 return {label:match[1].replace(/<[^>]*>/g,''),html:match[2],text:match[2].replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').trim()};
}

test('only the location query is a search input while editor progress retains accessible state without visible status captions',async()=>{
 for(const kind of ['search','property']){
  const t=await setup();t.ui.openEditor(kind,kind==='property'?'own-p1':'own-s1');const form=t.document.getElementById('entity-form'),location=t.document.getElementById('location-input');
  assert.equal(location.type,'search');assert.equal(location.getAttribute('role'),'combobox');assert.equal(location.getAttribute('autocomplete'),'off');assert.equal(location.getAttribute('aria-autocomplete'),'list');
  assert.deepEqual(form.querySelectorAll('input[type="search"]').map(input=>input.id),['location-input'],'Other fields must retain their actual input semantics');
  assert.equal(t.document.getElementById('f-title').type,'text');assert.equal(t.document.getElementById(kind==='property'?'f-price':'f-maxPrice').type,'number');assert.equal(t.document.getElementById('f-description').tagName,'TEXTAREA');
  let html=t.document.getElementById('modal-root').innerHTML;assert.doesNotMatch(html,/id="editor-state-\d|<small[^>]*>\s*(?:Kitöltve|Aktuális|Hátravan)/);assert.equal(t.document.getElementById('editor-step-button-0').getAttribute('aria-current'),'step');
  await editorAction(t,'editor-next');assert.equal(editorStep(t),1);assert.equal(t.document.getElementById('editor-step-button-0').getAttribute('data-state'),'completed');assert.equal(t.document.getElementById('editor-step-button-1').getAttribute('aria-current'),'step');
  assert.match(t.document.getElementById('editor-step-status').textContent,/2\. lépés az 5-ből/);
 }
});

test('discovery filters first show every configured search criterion read-only, including zero bounds and multiple choices',async()=>{
 const t=await setup({initialRaw:configuredCriteriaRaw('search'),captureTimers:true}),before=t.model.getState(),writes=[],save=t.model.saveEntity;t.model.saveEntity=(...args)=>{writes.push(args);return save(...args);};
 assert.match(t.document.getElementById('app').innerHTML,/<button[^>]*class="filter-button"[^>]*data-action="active-criteria-summary"/);
 await t.click({action:'active-criteria-summary'});t.runTimers();assert.equal(t.document.activeElement.id,'criteria-summary-heading','The read-only overview starts at its heading');const html=t.document.getElementById('modal-root').innerHTML;
 assert.match(html,/class="criteria-summary"[^>]*data-kind="search"[^>]*data-id="own-s1"/);assert.match(html,/Beállított feltételek/);assert.match(html,/Minden feltétel &lt;keresés&gt; &amp; tér/);assert.doesNotMatch(html,/<form\b|<input\b|<select\b|<textarea\b|id="entity-form"/);
 assert.equal(criteriaRow(t,'type').text,'Lakás');assert.match(criteriaRow(t,'locationIds').text,/Debrecen/);assert.match(criteriaRow(t,'locationIds').text,/Budapest V\. kerület/);
 for(const key of ['minPrice','minArea','minRooms'])assert.match(criteriaRow(t,key).text,/^0(?:\s|,|\.|$)/,`${key}=0 is a configured value`);
 assert.match(criteriaRow(t,'maxPrice').text,/120,5.*M Ft/);assert.match(criteriaRow(t,'maxArea').text,/150.*m²/);assert.match(criteriaRow(t,'maxRooms').text,/5,5.*szoba/);
 for(const [key,values] of Object.entries({conditions:['Átlagos','Jó'],buildings:['Tégla','Panel'],constructionAges:['10 évnél fiatalabb','31–40 év közötti'],views:['Kertre néző','Panorámás'],heatingTypes:['Hőszivattyú','Klíma'],floors:['Szuterén','Földszint','11']}))for(const value of values)assert.ok(criteriaRow(t,key).text.includes(value),`${key} must show ${value}`);
 assert.equal(criteriaRow(t,'ceilingHeight').text,'3 m alatti');assert.equal(criteriaRow(t,'balcony').text,'Szükséges');assert.equal(criteriaRow(t,'elevator').text,'Szükséges');assert.equal(criteriaRow(t,'moveIn').text,'Azonnal');assert.equal(criteriaRow(t,'financing').text,'Saját forrásból');
 assert.match(criteriaRow(t,'description').html,/Csendes &lt;kert&gt; &amp; tágas tér\./);assert.doesNotMatch(html,/<keresés>|<kert>/);
 assert.deepEqual(t.model.getState(),before);assert.equal(writes.length,0,'Opening the overview neither saves nor debits');
 await t.click({action:'edit-criteria',kind:'search',id:'own-s1'});assert.ok(t.document.getElementById('entity-form'));assert.equal(t.document.getElementById('f-title').value,before.searches.find(item=>item.id==='own-s1').title);assert.equal(writes.length,0);
});

test('property filter overview shows saved details, known negative amenities and ground floor without treating them as missing',async()=>{
 const t=await setup({initialRaw:configuredCriteriaRaw('property')}),before=t.model.getState();await t.click({action:'active-criteria-summary'});let html=t.document.getElementById('modal-root').innerHTML;
 assert.match(html,/class="criteria-summary"[^>]*data-kind="property"[^>]*data-id="own-p1"/);assert.match(html,/Az ingatlan adatai/);assert.match(html,/Minden adat &lt;otthon&gt; &amp; fény/);assert.doesNotMatch(html,/<form\b|<input\b|<select\b|<textarea\b/);
 assert.equal(criteriaRow(t,'type').text,'Lakás');assert.match(criteriaRow(t,'locationId').text,/Budapest V\. kerület/);assert.equal(criteriaRow(t,'neighborhood').text,'Belváros');assert.equal(criteriaRow(t,'address').text,'1051, Napfény utca 12.');
 assert.match(criteriaRow(t,'price').text,/92,5.*M Ft/);assert.match(criteriaRow(t,'area').text,/66,5.*m²/);assert.match(criteriaRow(t,'rooms').text,/2.*egész.*1.*fél/);assert.equal(criteriaRow(t,'floor').text,'Földszint');
 for(const [key,value] of Object.entries({condition:'Átlagos',building:'Tégla',constructionAge:'31–40 év közötti',view:'Udvari',ceilingHeight:'3 m feletti',heatingType:'Nincs fűtés',secondaryHeatingType:'Klíma',energyRating:'BB'}))assert.equal(criteriaRow(t,key).text,value);
 for(const key of ['insulated','airConditioning','balcony'])assert.equal(criteriaRow(t,key).text,'Nincs',`${key}=false must remain distinguishable from unknown`);
 for(const key of ['solarPanels','elevator'])assert.equal(criteriaRow(t,key).text,'Van');
 for(const choice of ['Udvari beálló','Garázs'])assert.ok(criteriaRow(t,'parkingTypes').text.includes(choice));
 assert.match(criteriaRow(t,'images').html,/<img[^>]*src="https:\/\/example\.test\/elol\.jpg"/);assert.match(criteriaRow(t,'images').html,/https:\/\/example\.test\/udvar\.jpg/);assert.match(criteriaRow(t,'description').html,/Tágas &lt;belső&gt; &amp; csendes udvar\./);assert.deepEqual(t.model.getState(),before);
 await t.click({action:'close'});assert.equal(t.document.getElementById('modal-root').innerHTML,'');assert.deepEqual(t.model.getState(),before);
});

test('the filter overview distinguishes unconstrained search bounds and house-only plot size',async()=>{
 const searchRaw=configuredCriteriaRaw('search');Object.assign(searchRaw.searches.find(item=>item.id==='own-s1'),{minPrice:null,maxArea:null,maxRooms:null,balcony:false,elevator:false});
 const search=await setup({initialRaw:searchRaw});await search.click({action:'active-criteria-summary'});
 for(const key of ['minPrice','maxArea','maxRooms'])assert.equal(criteriaRow(search,key).text,'Nincs megkötés',`${key}=null must never become zero or a synthetic maximum`);
 for(const key of ['balcony','elevator'])assert.equal(criteriaRow(search,key).text,'Nem feltétel');
 const propertyRaw=configuredCriteriaRaw('property');Object.assign(propertyRaw.properties.find(item=>item.id==='own-p1'),{type:'Ház',lotArea:650,floor:null,balcony:false,elevator:false});
 const property=await setup({initialRaw:propertyRaw});await property.click({action:'active-criteria-summary'});assert.match(criteriaRow(property,'lotArea').text,/650.*m²/);
 assert.doesNotMatch(property.document.getElementById('modal-root').innerHTML,/data-summary-field="(?:floor|balcony|elevator)"/,'House summaries retain the existing applicability rules');
});

test('a stale filter-summary edit action cannot open an inactive, foreign or replaced profile',async()=>{
 const t=await setup({initialRaw:configuredCriteriaRaw('search')}),writes=[],save=t.model.saveEntity;t.model.saveEntity=(...args)=>{writes.push(args);return save(...args);};
 await t.click({action:'active-criteria-summary'});await t.model.activate('search','own-s2');const before=t.model.getState();
 await t.click({action:'edit-criteria',kind:'search',id:'own-s1'});assert.equal(t.document.getElementById('entity-form'),null);assert.equal(writes.length,0);assert.deepEqual(t.model.getState(),before,'An active change outside the cached workspace must also invalidate the summary');
 await t.click({action:'edit-criteria',kind:'search',id:'s1'});assert.equal(t.document.getElementById('entity-form'),null);assert.equal(writes.length,0);
 await t.ui.render();await t.click({action:'active-criteria-summary'});const getState=t.model.getState;let release;
 t.model.getState=async()=>{const snapshot=getState();await new Promise(resolve=>{release=resolve;});return snapshot;};
 const pending=t.click({action:'edit-criteria',kind:'search',id:'own-s2'});await settle();assert.equal(typeof release,'function');
 t.ui.openModal('<h2>Másik megnyitott ablak</h2>');t.model.getState=getState;release();await pending;
 assert.match(t.document.getElementById('modal-root').innerHTML,/Másik megnyitott ablak/);assert.equal(t.document.getElementById('entity-form'),null);assert.equal(writes.length,0);
});

test('editing unrelated fields preserves legacy exact address and financing in the actual save payload',async()=>{
 for(const kind of ['property','search']){
  const t=await setup({initialRaw:configuredCriteriaRaw(kind)}),id=kind==='property'?'own-p1':'own-s1',field=kind==='property'?'address':'financing',collection=kind==='property'?'properties':'searches',before=t.model.getState()[collection].find(item=>item.id===id),calls=[],save=t.model.saveEntity;
  t.model.saveEntity=(savedKind,data,savedId)=>{calls.push({kind:savedKind,data:JSON.parse(JSON.stringify(data)),id:savedId});return save(savedKind,data,savedId);};
  await t.click({action:'active-criteria-summary'});await t.click({action:'edit-criteria',kind,id});await advanceEditor(t,4);t.document.getElementById('f-description').value='Csak a leírást módosítom, a meglévő adatok megmaradnak.';submitEditor(t);await settle();
  assert.equal(calls.length,1);assert.equal(calls[0].kind,kind);assert.equal(calls[0].id,id);assert.equal(calls[0].data[field],before[field],`The API update must receive the unchanged ${field}, even though it has no editable input`);
  assert.equal(t.model.getState()[collection].find(item=>item.id===id)[field],before[field]);
 }
});

test('anonymous search wizard is a page and restores every saved topic and partial query',async()=>{
 let draft=onboardingHelpers.createDraft('search',{title:'Saját otthon',type:'Lakás',locationIds:['city:Debrecen'],minPrice:null,maxPrice:'91.5',minArea:'40',maxArea:'',minRooms:null,maxRooms:'3',description:'Csendes környék',conditions:['Jó állapotú']},{editor:{locations:[getLocation('city:Debrecen')],query:'Csapó',completedSteps:[0,1,2],titleGenerated:false}});
 draft=onboardingHelpers.updateDraft(draft,{step:3});
 const t=await setup({hosted:true,hash:'#onboarding',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(draft)}});
 assert.equal(t.document.currentModal,null);assert.equal(editorStep(t),3);
 assert.equal(t.document.getElementById('f-title').value,'Saját otthon');
 assert.equal(t.document.getElementById('location-input').value,'Csapó');
 assert.equal(t.document.getElementById('f-minRooms').value,'');
 assert.equal(t.document.getElementById('f-maxPrice').value,'91.5');
 assert.match(t.document.getElementById('location-chips').innerHTML,/Debrecen/);
 const form=t.document.getElementById('entity-form');
 t.document.getElementById('f-description').value='Új, még befejezetlen leírás';
 form.handlers.input({target:t.document.getElementById('f-description')});
 const saved=JSON.parse(t.regionStorage.get(onboardingHelpers.DRAFT_STORAGE_KEY));
 assert.equal(saved.step,3);assert.equal(saved.data.description,'Új, még befejezetlen leírás');assert.equal(saved.editor.query,'Csapó');
 await t.click({action:'landing'});
 const preserved=JSON.parse(t.regionStorage.get(onboardingHelpers.DRAFT_STORAGE_KEY));assert.equal(preserved.data.description,'Új, még befejezetlen leírás');
 t.ctx.location.hash='#onboarding';await t.ui.render();assert.equal(editorStep(t),3);assert.equal(t.document.getElementById('location-input').value,'Csapó');
});

test('anonymous final validation freezes the completed draft before registration and never saves intermediate topics',async()=>{
 let draft=onboardingHelpers.createDraft('search',{title:'Első saját keresésem',type:'Lakás',locationIds:['city:Debrecen'],minPrice:null,maxPrice:90,minArea:40,maxArea:null,minRooms:null,maxRooms:3,moveIn:'Rugalmas'},{editor:{locations:[getLocation('city:Debrecen')],titleGenerated:false}});
 draft=onboardingHelpers.updateDraft(draft,{step:4});
 let saves=0;
 const t=await setup({hosted:true,hash:'#onboarding',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(draft)},apiOverrides:{saveEntity:async()=>{saves++;}}});
 await submitEditor(t);
 assert.equal(t.ctx.location.hash,'#register');assert.ok(t.document.getElementById('hosted-auth-form'));assert.equal(saves,0);
 const saved=JSON.parse(t.regionStorage.get(onboardingHelpers.DRAFT_STORAGE_KEY));
 assert.equal(saved.phase,'awaiting-auth');assert.equal(saved.completedData.title,'Első saját keresésem');assert.equal(saved.completedData.minPrice,null);assert.equal(saved.completedData.minRooms,null);assert.match(saved.creationRequestId,/^[\da-f-]{36}$/);assert.equal(saved.expectedEmail,undefined);
 assert.equal(saved.data.password,undefined);assert.equal(saved.data.token,undefined);
});

test('completed onboarding saves once after matching authentication and waits for explicit discovery activation',async()=>{
 const data={title:'Vendégből mentett keresés',type:'Lakás',locationIds:['city:Debrecen'],minPrice:null,maxPrice:90,minArea:40,maxArea:null,minRooms:null,maxRooms:3};
 const draft=onboardingHelpers.prepareDraftForAuth(onboardingHelpers.createDraft('search',data));
 let saves=0,activated=0,received;
 const t=await setup({hosted:true,hash:'#register',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(draft)},apiOverrides:{saveEntity:async(...args)=>{saves++;received=args;return{id:'saved-guest-search',...data};},activate:async()=>{activated++;}}});
 const form=t.document.getElementById('hosted-auth-form');form.values={name:'Nagy Anna',email:'anna@example.hu',password:'secret-password-123',accountType:'private'};
 await form.handlers.submit({preventDefault(){},currentTarget:form});
 assert.equal(saves,1);assert.equal(activated,0);assert.equal(received[0],'search');assert.equal(received[3].creationRequestId,draft.creationRequestId);
 assert.equal(t.regionStorage.has(onboardingHelpers.DRAFT_STORAGE_KEY),false);assert.equal(t.ctx.location.hash,'#searches');
 assert.match(t.document.getElementById('modal-root').innerHTML,/Elkészült a keresési igényed/);
 assert.match(t.document.getElementById('modal-root').innerHTML,/data-action="discover-search" data-id="saved-guest-search"/);
});

test('failed completed-draft save preserves a stable request and retries only for its bound account',async()=>{
 const data={title:'Biztosan megmaradó keresés',type:'Lakás',locationIds:['city:Debrecen'],minPrice:null,maxPrice:90,minArea:40,maxArea:null,minRooms:null,maxRooms:3};
 const draft=onboardingHelpers.prepareDraftForAuth(onboardingHelpers.createDraft('search',data),'anna@example.hu');
 const requests=[];let fail=true;
 const t=await setup({hosted:true,hash:'#register',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(draft)},apiOverrides:{saveEntity:async(kind,payload,id,options)=>{requests.push(options.creationRequestId);if(fail)throw new Error('Ideiglenes hiba');return{id:'retry-saved',...payload};}}});
 const form=t.document.getElementById('hosted-auth-form');form.values={name:'Nagy Anna',email:'anna@example.hu',password:'secret-password-123',accountType:'private'};
 await form.handlers.submit({preventDefault(){},currentTarget:form});
 assert.match(t.document.getElementById('onboarding-save-error').innerHTML||t.document.getElementById('app').innerHTML,/Ideiglenes hiba/);
 const pending=JSON.parse(t.regionStorage.get(onboardingHelpers.DRAFT_STORAGE_KEY));assert.equal(pending.phase,'saving');assert.equal(pending.ownerId,'me');assert.equal(pending.expectedEmail,'anna@example.hu');
 fail=false;await t.click({action:'onboarding-save-retry'});
 assert.deepEqual(requests,[draft.creationRequestId,draft.creationRequestId]);assert.equal(t.regionStorage.has(onboardingHelpers.DRAFT_STORAGE_KEY),false);
});

test('a stale guest editor cannot overwrite a draft completed in another tab',async()=>{
 const draft=onboardingHelpers.createDraft('search',{title:'Eredeti piszkozat',type:'Lakás',locationIds:['city:Debrecen'],maxPrice:90,minArea:40,minRooms:null},{editor:{locations:[getLocation('city:Debrecen')],titleGenerated:false}});
 const t=await setup({hosted:true,hash:'#onboarding',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(draft)}});
 const completed=onboardingHelpers.prepareDraftForAuth(draft,'anna@example.hu');t.regionStorage.set(onboardingHelpers.DRAFT_STORAGE_KEY,JSON.stringify(completed));
 t.document.getElementById('f-title').value='Késői szerkesztés';t.document.getElementById('entity-form').handlers.input({});
 assert.deepEqual(JSON.parse(t.regionStorage.get(onboardingHelpers.DRAFT_STORAGE_KEY)),completed);
 await t.click({action:'landing'});assert.deepEqual(JSON.parse(t.regionStorage.get(onboardingHelpers.DRAFT_STORAGE_KEY)),completed);
});

test('an account change during draft save retains the bound receipt and hides the old-account result',async()=>{
 const data={title:'Fiókhoz kötött mentés',type:'Lakás',locationIds:['city:Debrecen'],maxPrice:90,minArea:40,minRooms:null};
 const draft=onboardingHelpers.prepareDraftForAuth(onboardingHelpers.createDraft('search',data),'anna@example.hu');
 let resolveSave,started=false;
 const t=await setup({hosted:true,hash:'#register',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(draft)},apiOverrides:{saveEntity:async()=>{started=true;return await new Promise(resolve=>{resolveSave=resolve;});}}});
 const form=t.document.getElementById('hosted-auth-form');form.values={name:'Nagy Anna',email:'anna@example.hu',password:'secret-password-123',accountType:'private'};
 const submitted=form.handlers.submit({preventDefault(){},currentTarget:form});await settle();assert.equal(started,true);
 t.regionStorage.set('otthonra.api','different-session');resolveSave({id:'old-account-search',...data});await submitted;
 const preserved=JSON.parse(t.regionStorage.get(onboardingHelpers.DRAFT_STORAGE_KEY));assert.equal(preserved.ownerId,'me');assert.equal(preserved.creationRequestId,draft.creationRequestId);
 assert.ok(t.document.getElementById('hosted-auth-form'));assert.match(t.document.getElementById('app').innerHTML,/munkamenet időközben megváltozott/);
 assert.doesNotMatch(t.document.getElementById('modal-root').innerHTML,/old-account-search/);
});

const storedOnboarding=t=>{const raw=t.regionStorage.get(onboardingHelpers.DRAFT_STORAGE_KEY);return raw?JSON.parse(raw):null;};
const onboardingProperty=(key='chosen-property',sourceKey=publicSourceKey('property'))=>({key,sourceKey,title:'Forrás otthon',type:'Lakás',price:66.65,area:57.6,rooms:2.5,location:'Debrecen',prefill:{type:'Lakás',price:66.65,area:57.6,rooms:2.5,locations:[getLocation('city:Debrecen')]}});
const recentSearchMarkup=t=>{const slot=t.document.getElementById('landing-recent-search-slot');return slot?.innerHTMLWasAssigned?slot.innerHTML:t.document.getElementById('app').innerHTML.match(/<div id="landing-recent-search-slot">([\s\S]*?)<\/div>/)?.[1]||'';};

test('a different teaser automatically replaces the previous draft with a fresh receipt and no overwrite question',async()=>{
 const existing=onboardingHelpers.createDraft('property',{title:'Korábbi ingatlan',type:'Ház'});
 const source=onboardingProperty();
 const t=await setup({hosted:true,hash:'#landing',fetchLanding:async()=>({...landingFixture(''),properties:[source]}),regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(existing)}});
 await t.click({action:'onboarding-start',kind:'search',source:'chosen-property'});
 assert.equal(t.document.getElementById('modal-root').innerHTML,'');assert.ok(t.document.getElementById('entity-form'));
 const replacement=storedOnboarding(t);assert.notEqual(replacement.id,existing.id);assert.notEqual(replacement.creationRequestId,existing.creationRequestId);assert.equal(replacement.kind,'search');assert.deepEqual(replacement.origin,{kind:'property',key:source.sourceKey});
 assert.equal(Number(t.document.getElementById('f-maxPrice').value),75);assert.equal(Number(t.document.getElementById('f-minArea').value),50);assert.equal(t.document.getElementById('f-maxArea').value,'');assert.equal(t.document.getElementById('f-minRooms').value,'2.5');assert.equal(t.document.getElementById('f-maxRooms').value,'');
 assert.equal(t.document.getElementById('f-maxPrice').checkValidity(),true);assert.equal(t.document.getElementById('f-minArea').checkValidity(),true);
 assert.match(t.document.getElementById('location-chips').innerHTML,/Debrecen/);assert.equal(replacement.data.sourceKey,undefined);
});

test('the same listing resumes edited fields and its step when its landing slot and public parameters change',async()=>{
 let source=onboardingProperty();
 const t=await setup({hosted:true,hash:'#landing',fetchLanding:async()=>({...landingFixture(''),properties:[source]})});
 await t.click({action:'onboarding-start',kind:'search',source:source.key});await advanceEditor(t,4);
 const title=t.document.getElementById('f-title');title.value='Saját megőrzött keresésem';title.handlers.input({target:title});t.document.getElementById('entity-form').handlers.input({target:title});
 await editorAction(t,'editor-step-button-1');const price=t.document.getElementById('f-maxPrice');price.value='123';t.document.getElementById('entity-form').handlers.input({target:price});
 await t.click({action:'landing'});const before=storedOnboarding(t);assert.equal(before.step,1);
 source={...source,key:'property-new-slot',price:199,prefill:{...source.prefill,price:199}};
 await t.click({action:'landing-retry'});await t.click({action:'onboarding-start',kind:'search',source:source.key});
 const resumed=storedOnboarding(t);assert.equal(resumed.id,before.id);assert.equal(resumed.creationRequestId,before.creationRequestId);assert.equal(editorStep(t),1);assert.equal(t.document.getElementById('f-maxPrice').value,'123');assert.equal(t.document.getElementById('f-title').value,'Saját megőrzött keresésem');assert.equal(t.document.getElementById('modal-root').innerHTML,'');
});

test('identical-looking listings have separate origins and an opposite-kind teaser also replaces without a prompt',async()=>{
 const first=onboardingProperty('first',publicSourceKey('property','a')),second=onboardingProperty('second',publicSourceKey('property','c'));
 const sellerSource={key:'search-source',sourceKey:publicSourceKey('search','a'),title:'Ugyanilyen otthont keresünk',type:'Lakás',locations:['Debrecen'],prefill:{locations:[getLocation('city:Debrecen')],type:'Lakás',minPrice:50,maxPrice:50,minArea:60,maxArea:60,minRooms:2,maxRooms:2}};
 const t=await setup({hosted:true,hash:'#landing',fetchLanding:async()=>({...landingFixture(''),properties:[first,second],searches:[sellerSource]})});
 await t.click({action:'onboarding-start',kind:'search',source:first.key});const initial=storedOnboarding(t);await t.click({action:'landing'});await t.click({action:'onboarding-start',kind:'search',source:second.key});const distinct=storedOnboarding(t);
 assert.notEqual(distinct.id,initial.id);assert.deepEqual(distinct.origin,{kind:'property',key:second.sourceKey});assert.equal(t.document.getElementById('modal-root').innerHTML,'');
 await t.click({action:'landing'});await t.click({action:'onboarding-start',kind:'property',source:sellerSource.key});const seller=storedOnboarding(t);
 assert.notEqual(seller.id,distinct.id);assert.equal(seller.kind,'property');assert.deepEqual(seller.origin,{kind:'search',key:sellerSource.sourceKey});assert.equal(t.document.getElementById('modal-root').innerHTML,'');assert.equal(t.document.getElementById('f-street').value,'');
});

test('the same source resumes finalized authentication and uncertain-save phases with the original receipt',async()=>{
 const source=onboardingProperty();
 const base=onboardingHelpers.prepareDraftForAuth(onboardingHelpers.createDraft('search',{title:'Befejezett saját keresésem',type:'Lakás',locationIds:['city:Debrecen'],maxPrice:85,minArea:45},{origin:onboardingHelpers.originFromListing('property',source.sourceKey)}),'anna@example.hu');
 for(const pending of [base,onboardingHelpers.prepareDraftSave(base,{id:'original-owner',email:'anna@example.hu'})]){
  const t=await setup({hosted:true,hash:'#landing',fetchLanding:async()=>({...landingFixture(''),properties:[source]}),regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(pending)}});
  await t.click({action:'onboarding-start',kind:'search',source:source.key});const resumed=storedOnboarding(t);
  assert.equal(resumed.id,pending.id);assert.equal(resumed.phase,pending.phase);assert.equal(resumed.creationRequestId,pending.creationRequestId);assert.deepEqual(resumed.completedData,pending.completedData);assert.equal(resumed.expectedEmail,pending.expectedEmail);
  assert.equal(t.document.getElementById('entity-form'),null,'Reusing a pending source cannot reopen editing and mutate an uncertain saved payload');
  if(pending.phase==='saving')assert.match(t.document.getElementById('app').innerHTML,/onboarding-save-retry/);else{assert.equal(t.ctx.location.hash,'#register');assert.ok(t.document.getElementById('hosted-auth-form'));}
 }
});

test('changing a pending source starts a new unbound draft without carrying the old frozen request or credentials',async()=>{
 const first=onboardingProperty('first'),second=onboardingProperty('second',publicSourceKey('property','d'));
 const completed=onboardingHelpers.prepareDraftForAuth(onboardingHelpers.createDraft('search',{title:'Régi lezárt keresés',type:'Lakás',locationIds:['city:Debrecen'],maxPrice:85,minArea:45},{origin:onboardingHelpers.originFromListing('property',first.sourceKey)}),'anna@example.hu');
 const pending=onboardingHelpers.prepareDraftSave(completed,{id:'original-owner',email:'anna@example.hu'});
 const t=await setup({hosted:true,hash:'#landing',fetchLanding:async()=>({...landingFixture(''),properties:[first,second]}),regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(pending)}});
 await t.click({action:'onboarding-start',kind:'search',source:second.key});const replacement=storedOnboarding(t);
 assert.notEqual(replacement.id,pending.id);assert.notEqual(replacement.creationRequestId,pending.creationRequestId);assert.equal(replacement.phase,'editing');assert.equal(replacement.expectedEmail,undefined);assert.equal(replacement.ownerId,undefined);assert.equal(replacement.completedData,undefined);assert.deepEqual(replacement.origin,{kind:'property',key:second.sourceKey});assert.ok(t.document.getElementById('entity-form'));assert.equal(t.document.getElementById('modal-root').innerHTML,'');
});

test('location search reuses a search with exactly its current places regardless of order or original listing',async()=>{
 let existing=onboardingHelpers.createDraft('search',{title:'Átírt saját keresés',type:'Ház',locationIds:['city:Debrecen','city:Szeged'],maxPrice:130,minArea:60,description:'A saját részleteim'},{origin:onboardingHelpers.originFromListing('property',publicSourceKey('property','e')),editor:{locations:[getLocation('city:Debrecen'),getLocation('city:Szeged')],titleGenerated:false,completedSteps:[0,1]}});
 existing=onboardingHelpers.updateDraft(existing,{step:2});
 const t=await setup({hosted:true,hash:'#landing',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(existing)}});
 t.ui.startOnboarding('search',null,[getLocation('city:Szeged'),getLocation('city:Debrecen'),getLocation('city:Szeged')]);
 assert.equal(storedOnboarding(t).id,existing.id);assert.equal(editorStep(t),2);assert.equal(t.document.getElementById('f-title').value,existing.data.title);assert.equal(t.document.getElementById('f-description').value,existing.data.description);assert.equal(t.document.getElementById('modal-root').innerHTML,'');
 await t.click({action:'landing'});t.ui.startOnboarding('search',null,[getLocation('city:Debrecen')]);const changed=storedOnboarding(t);
 assert.notEqual(changed.id,existing.id);assert.deepEqual(changed.data.locationIds,['city:Debrecen']);assert.equal(changed.data.maxPrice,'');assert.equal(editorStep(t),0);assert.equal(t.document.getElementById('modal-root').innerHTML,'');
});

test('location source matching follows edits to the draft rather than its initial selected set',async()=>{
 const oldPlaces=[getLocation('city:Debrecen')],currentPlaces=[getLocation('city:Szeged')];
 let existing=onboardingHelpers.createDraft('search',{title:'Új helyszínnel keresek',type:'Lakás',locationIds:currentPlaces.map(x=>x.id),maxPrice:80,minArea:40},{origin:onboardingHelpers.originFromLocations(oldPlaces),editor:{locations:currentPlaces,titleGenerated:false}});
 existing=onboardingHelpers.updateDraft(existing,{step:1});
 const t=await setup({hosted:true,hash:'#landing',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(existing)}});
 t.ui.startOnboarding('search',null,currentPlaces);assert.equal(storedOnboarding(t).id,existing.id);await t.click({action:'landing'});t.ui.startOnboarding('search',null,oldPlaces);assert.notEqual(storedOnboarding(t).id,existing.id);
});

test('recent search is below the landing picker, escapes its details and resumes the stored step by its guarded id',async()=>{
 let existing=onboardingHelpers.createDraft('search',{title:'Saját <keresés> & terv',type:'Lakás',locationIds:['city:Debrecen'],maxPrice:80,minArea:40},{editor:{locations:[getLocation('city:Debrecen')],titleGenerated:false}});
 existing=onboardingHelpers.updateDraft(existing,{step:3});
 const t=await setup({hosted:true,hash:'#landing',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(existing)}});
 const html=t.document.getElementById('app').innerHTML,markup=recentSearchMarkup(t);assert.ok(html.indexOf('id="landing-recent-search-slot"')>html.indexOf('id="landing-search-form"'));assert.match(markup,/Legutóbbi keresésed/);assert.match(markup,/Saját &lt;keresés&gt; &amp; terv/);assert.match(markup,/Debrecen/);assert.doesNotMatch(markup,/<keresés>|property-[a-f0-9]{64}/);
 await t.click({action:'onboarding-resume-draft',id:existing.id});assert.equal(editorStep(t),3);assert.equal(storedOnboarding(t).id,existing.id);
 await t.click({action:'landing'});const replacement=onboardingHelpers.createDraft('property',{title:'Másik lapon készült ingatlan'});t.regionStorage.set(onboardingHelpers.DRAFT_STORAGE_KEY,JSON.stringify(replacement));await t.click({action:'onboarding-resume-draft',id:existing.id});assert.equal(t.ctx.location.hash,'#landing');assert.equal(t.document.getElementById('entity-form'),null);assert.equal(storedOnboarding(t).id,replacement.id);
});

test('recent search follows cross-tab storage, focus and pageshow without showing property, expired or consumed drafts',async()=>{
 const t=await setup({hosted:true,hash:'#landing'});assert.equal(recentSearchMarkup(t),'');
 const existing=onboardingHelpers.createDraft('search',{title:'Másik fül keresése',type:'Lakás',locationIds:['city:Szeged']});t.regionStorage.set(onboardingHelpers.DRAFT_STORAGE_KEY,JSON.stringify(existing));await t.windowEvents.storage({type:'storage',key:onboardingHelpers.DRAFT_STORAGE_KEY});assert.match(recentSearchMarkup(t),/Másik fül keresése/);
 const other=onboardingHelpers.createDraft('property',{title:'Eladó ingatlan'});t.regionStorage.set(onboardingHelpers.DRAFT_STORAGE_KEY,JSON.stringify(other));await t.windowEvents.focus({type:'focus'});assert.equal(recentSearchMarkup(t),'');
 t.regionStorage.set(onboardingHelpers.DRAFT_STORAGE_KEY,JSON.stringify(existing));await t.windowEvents.pageshow({type:'pageshow'});assert.match(recentSearchMarkup(t),/Másik fül keresése/);
 t.regionStorage.delete(onboardingHelpers.DRAFT_STORAGE_KEY);await t.windowEvents.storage({type:'storage',key:onboardingHelpers.DRAFT_STORAGE_KEY});assert.equal(recentSearchMarkup(t),'');
 const expired=onboardingHelpers.createDraft('search',{title:'Lejárt keresés'},{now:Date.now()-8*86400000});t.regionStorage.set(onboardingHelpers.DRAFT_STORAGE_KEY,JSON.stringify(expired));await t.windowEvents.focus({type:'focus'});assert.equal(recentSearchMarkup(t),'');assert.equal(t.regionStorage.has(onboardingHelpers.DRAFT_STORAGE_KEY),false);
});


test('an uncertain save result keeps the completed payload frozen when browser navigation revisits the wizard',async()=>{
 const data={title:'Bizonytalan válaszú keresés',type:'Lakás',locationIds:['city:Debrecen'],maxPrice:90,minArea:40,minRooms:null};
 const draft=onboardingHelpers.prepareDraftForAuth(onboardingHelpers.createDraft('search',data),'anna@example.hu');
 const t=await setup({hosted:true,hash:'#register',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(draft)},apiOverrides:{saveEntity:async()=>{throw Object.assign(new Error('A válasz elveszett'),{status:503});}}});
 const form=t.document.getElementById('hosted-auth-form');form.values={name:'Nagy Anna',email:'anna@example.hu',password:'secret-password-123',accountType:'private'};await form.handlers.submit({preventDefault(){},currentTarget:form});
 assert.doesNotMatch(t.document.getElementById('app').innerHTML,/data-action="onboarding-edit"/);
 t.ctx.location.hash='#onboarding';await t.ui.render();assert.equal(t.document.getElementById('entity-form'),null);assert.match(t.document.getElementById('app').innerHTML,/data-action="onboarding-save-retry"/);
 const preserved=JSON.parse(t.regionStorage.get(onboardingHelpers.DRAFT_STORAGE_KEY));assert.equal(preserved.phase,'saving');assert.deepEqual(preserved.completedData,data);assert.equal(preserved.creationRequestId,draft.creationRequestId);
});

test('generated draft titles follow location and type until the user supplies a title',async()=>{
 const draft=onboardingHelpers.createDraft('search',{title:'Lakás keresés',type:'Lakás',locationIds:['city:Debrecen']},{editor:{locations:[getLocation('city:Debrecen')],titleGenerated:true}});
 const t=await setup({hosted:true,hash:'#onboarding',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(draft)}});
 const form=t.document.getElementById('entity-form'),type=t.document.getElementById('f-type'),title=t.document.getElementById('f-title');
 type.value='Ház';type.handlers.change({currentTarget:type});form.handlers.change({target:type});assert.equal(title.value,'Ház keresés – Debrecen');
 title.value='A saját címem';title.handlers.input({target:title});form.handlers.input({target:title});type.value='Lakás';type.handlers.change({currentTarget:type});form.handlers.change({target:type});
 assert.equal(title.value,'A saját címem');const saved=JSON.parse(t.regionStorage.get(onboardingHelpers.DRAFT_STORAGE_KEY));assert.equal(saved.editor.titleGenerated,false);assert.equal(saved.data.title,'A saját címem');
});

test('a stale authentication form cannot replace a newer draft from another tab',async()=>{
 const draft=onboardingHelpers.prepareDraftForAuth(onboardingHelpers.createDraft('search',{title:'Régi keresés'}));
 const newer=onboardingHelpers.createDraft('property',{title:'Másik lapon elkezdett ingatlan'});
 const t=await setup({hosted:true,hash:'#register',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(draft)}});
 const form=t.document.getElementById('hosted-auth-form');t.regionStorage.set(onboardingHelpers.DRAFT_STORAGE_KEY,JSON.stringify(newer));form.values={name:'Nagy Anna',email:'anna@example.hu',password:'secret-password-123',accountType:'private'};
 await form.handlers.submit({preventDefault(){},currentTarget:form});assert.equal(t.connected.length,0);assert.deepEqual(JSON.parse(t.regionStorage.get(onboardingHelpers.DRAFT_STORAGE_KEY)),newer);assert.match(t.document.getElementById('auth-error').textContent,/másik lapon megváltozott/);
});

test('a completed draft changed during account lookup is never replaced by its older callback',async()=>{
 const data={title:'Régi lezárt keresés',type:'Lakás',locationIds:['city:Debrecen'],maxPrice:90,minArea:40,minRooms:null};
 const draft=onboardingHelpers.prepareDraftForAuth(onboardingHelpers.createDraft('search',data),'anna@example.hu');
 const baseline=await createModel({getItem:()=>null,setItem:()=>{}}).getState();let resolveState,reads=0,writes=0;
 const t=await setup({hosted:true,hash:'#register',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(draft)},apiOverrides:{getState:async()=>++reads===1?await new Promise(resolve=>{resolveState=resolve;}):baseline,saveEntity:async()=>{writes++;return{id:'unexpected',...data};}}});
 const form=t.document.getElementById('hosted-auth-form');form.values={name:'Nagy Anna',email:'anna@example.hu',password:'secret-password-123',accountType:'private'};const submitted=form.handlers.submit({preventDefault(){},currentTarget:form});await settle();
 const current=JSON.parse(t.regionStorage.get(onboardingHelpers.DRAFT_STORAGE_KEY));const updated=onboardingHelpers.prepareDraftForAuth(onboardingHelpers.updateDraft(current,{phase:'editing',data:{title:'Másik lapon javított keresés'}}),'anna@example.hu');t.regionStorage.set(onboardingHelpers.DRAFT_STORAGE_KEY,JSON.stringify(updated));resolveState(baseline);await submitted;
 assert.equal(writes,0);assert.deepEqual(JSON.parse(t.regionStorage.get(onboardingHelpers.DRAFT_STORAGE_KEY)),updated);
});

test('a successful old save cannot clear a newly reopened same-key editing draft',async()=>{
 const data={title:'Mentés közben javított keresés',type:'Lakás',locationIds:['city:Debrecen'],maxPrice:90,minArea:40,minRooms:null};
 const draft=onboardingHelpers.prepareDraftForAuth(onboardingHelpers.createDraft('search',data),'anna@example.hu');let resolveSave;
 const t=await setup({hosted:true,hash:'#register',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(draft)},apiOverrides:{saveEntity:async()=>await new Promise(resolve=>{resolveSave=resolve;})}});
 const form=t.document.getElementById('hosted-auth-form');form.values={name:'Nagy Anna',email:'anna@example.hu',password:'secret-password-123',accountType:'private'};const submitted=form.handlers.submit({preventDefault(){},currentTarget:form});await settle();
 const pending=JSON.parse(t.regionStorage.get(onboardingHelpers.DRAFT_STORAGE_KEY));const editing=onboardingHelpers.updateDraft(pending,{phase:'editing',data:{title:'Új, megőrzendő szerkesztés'}});t.regionStorage.set(onboardingHelpers.DRAFT_STORAGE_KEY,JSON.stringify(editing));resolveSave({id:'old-success',...data});await submitted;
 const preserved=JSON.parse(t.regionStorage.get(onboardingHelpers.DRAFT_STORAGE_KEY));assert.equal(preserved.id,editing.id);assert.equal(preserved.phase,'editing');assert.equal(preserved.creationRequestId,editing.creationRequestId);assert.equal(preserved.data.title,'Új, megőrzendő szerkesztés');assert.equal(preserved.completedData,undefined);assert.doesNotMatch(t.document.getElementById('modal-root').innerHTML,/old-success/);
});

test('an expired session during draft saving requests login and preserves the completed request for retry',async()=>{
 const data={title:'Lejárt munkamenettel mentett keresés',type:'Lakás',locationIds:['city:Debrecen'],maxPrice:90,minArea:40,minRooms:null};
 const draft=onboardingHelpers.prepareDraftForAuth(onboardingHelpers.createDraft('search',data),'anna@example.hu');
 const t=await setup({hosted:true,hash:'#register',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(draft)},apiOverrides:{saveEntity:async()=>{throw Object.assign(new Error('A munkameneted lejárt.'),{status:401});}}});
 const form=t.document.getElementById('hosted-auth-form');form.values={name:'Nagy Anna',email:'anna@example.hu',password:'secret-password-123',accountType:'private'};await form.handlers.submit({preventDefault(){},currentTarget:form});
 assert.equal(t.ctx.location.hash,'#login');assert.equal(t.disconnected.length,1);assert.ok(t.document.getElementById('hosted-auth-form'));assert.match(t.document.getElementById('app').innerHTML,/munkameneted lejárt/);
 const saved=JSON.parse(t.regionStorage.get(onboardingHelpers.DRAFT_STORAGE_KEY));assert.equal(saved.phase,'saving');assert.equal(saved.creationRequestId,draft.creationRequestId);assert.deepEqual(saved.completedData,data);
});

test('reload completion coalesces hash navigation and presents discovery only after its workspace read commits',async()=>{
 const data={title:'Újratöltés után is visszaigazolt keresés',type:'Lakás',locationIds:['city:Debrecen'],maxPrice:90,minArea:40,minRooms:null};
 const initial=onboardingHelpers.prepareDraftForAuth(onboardingHelpers.createDraft('search',data),'anna@example.hu');
 const baseline=await createModel({getItem:()=>null,setItem:()=>{}}).getState();const draft=onboardingHelpers.prepareDraftSave(initial,baseline.user);
 let reads=0,resolveCommitted,writes=0,mounted;
 const pending=setup({hosted:true,authenticated:true,hash:'#register',dispatchHashChanges:true,onDocument:document=>{mounted=document;},regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(draft)},apiOverrides:{getState:async()=>{reads++;if(reads===2)return await new Promise(resolve=>{resolveCommitted=resolve;});return baseline;},saveEntity:async()=>{writes++;return{id:'reload-confirmed',...data};}}});
 await settle();assert.equal(reads,2,'Native hash navigation must share the already pending read for the saved collection');assert.doesNotMatch(mounted.getElementById('modal-root').innerHTML,/reload-confirmed/);
 resolveCommitted(baseline);const t=await pending;await settle();
 assert.equal(reads,2);assert.equal(writes,1);assert.equal(t.ctx.location.hash,'#searches');assert.equal(t.regionStorage.has(onboardingHelpers.DRAFT_STORAGE_KEY),false);
 assert.match(t.document.getElementById('modal-root').innerHTML,/data-action="discover-search" data-id="reload-confirmed"/);assert.match(t.document.getElementById('app').innerHTML,/Keresési igényeim/);
});


test('new guest and private forms require a chosen type and keep numeric intent blank until entered',async()=>{
 for(const kind of ['search','property']){
  for(const guest of [false,true]){
   const draft=onboardingHelpers.createDraft(kind,{}, {editor:{titleGenerated:true}});
   const t=await setup(guest?{hosted:true,hash:'#onboarding',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(draft)}}:{});
   if(!guest)t.ui.openEditor(kind);
   const type=t.document.getElementById('f-type'),title=t.document.getElementById('f-title');
   assert.equal(type.value,'');assert.equal(type.required,true);assert.equal(type.checkValidity(),false);
   assert.equal(title.parentElement.id,'editor-step-4','The optional name belongs to the final topic');assert.equal(title.required,false);
   for(const name of kind==='property'?['price','area','wholeRooms','halfRooms']:['minPrice','maxPrice','minArea','maxArea','minRooms','maxRooms'])assert.equal(t.document.getElementById('f-'+name).value,'',`${guest?'guest':'private'} ${kind} ${name}`);
   if(kind==='property')assert.equal(t.document.getElementById('f-halfRooms').required,false,'An absent half-room count must not force a meaningless zero entry');
  }
 }
});

test('new private search gets a short final name and clearing a customized name restores an automatic title',async()=>{
 const t=await setup();t.ui.openEditor('search');chooseLocation(t,'city:Debrecen');
 const type=t.document.getElementById('f-type');type.value='Lakás';type.handlers.change({target:type});
 const price=t.document.getElementById('f-maxPrice'),area=t.document.getElementById('f-minArea');price.value='80';area.value='50';
 await advanceEditor(t,4);const title=t.document.getElementById('f-title');assert.match(title.value,/Lakás/);assert.match(title.value,/Debrecen/);assert.match(title.value,/80/);assert.ok(title.value.length<=70);
 title.value='Egyéni név';title.handlers.input({target:title});await editorAction(t,'editor-step-button-1');price.value='95';price.handlers.input({target:price});await editorAction(t,'editor-step-button-4');assert.equal(title.value,'Egyéni név');
 title.value='';title.handlers.input({target:title});submitEditor(t);await settle();
 const created=t.model.getState().searches.find(item=>!['own-s1','own-s2'].includes(item.id)&&item.ownerId==='me');assert.ok(created);assert.match(created.title,/95/);assert.match(created.title,/Debrecen/);assert.ok(created.title.length<=70);
});

test('blank half rooms serializes as zero without pre-filling that control',async()=>{
 const t=await setup();t.ui.openEditor('property');chooseLocation(t,'city:Debrecen');
 const values={type:'Lakás',street:'Teszt utca',houseNumber:'12',price:'65',area:'60',wholeRooms:'2',halfRooms:'',title:'Két egész szoba'};
 assert.equal(t.document.getElementById('f-halfRooms').value,'');submitEntity(t,values);await settle();
 const created=t.model.getState().properties.find(item=>item.title==='Két egész szoba');assert.ok(created);assert.equal(created.wholeRooms,2);assert.equal(created.halfRooms,0);assert.equal(created.rooms,2);
});

async function finishReplacementSearch(t,source,title){
 await t.click({action:'landing'});await t.click({action:'onboarding-start',kind:'search',source:source.key});
 const replacement=storedOnboarding(t);await advanceEditor(t,4);
 const name=t.document.getElementById('f-title');name.value=title;name.handlers.input({target:name});t.document.getElementById('entity-form').handlers.input({target:name});
 await submitEditor(t);assert.equal(t.ctx.location.hash,'#register','A replacement wizard must remain usable while the abandoned request is pending');
 const form=t.document.getElementById('hosted-auth-form');form.values={name:'Nagy Anna',email:'anna@example.hu',password:'secret-password-123',accountType:'private'};await form.handlers.submit({preventDefault(){},currentTarget:form});
 return replacement;
}

test('an abandoned POST response cannot block, clear or navigate over a completed replacement draft',async()=>{
 for(const outcome of ['success','failure']){
  const first=onboardingProperty('first'),second=onboardingProperty('second',publicSourceKey('property','f'));
  const data={title:'Régi, lecserélt keresés',type:'Lakás',locationIds:['city:Debrecen'],maxPrice:85,minArea:45};
  const initial=onboardingHelpers.prepareDraftForAuth(onboardingHelpers.createDraft('search',data,{origin:onboardingHelpers.originFromListing('property',first.sourceKey)}),'anna@example.hu');
  let resolveOld,rejectOld;const writes=[];
  const t=await setup({hosted:true,hash:'#register',fetchLanding:async()=>({...landingFixture(''),properties:[first,second]}),regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(initial)},apiOverrides:{saveEntity:async(kind,payload,id,options)=>{
   writes.push(options.creationRequestId);if(options.creationRequestId===initial.creationRequestId)return await new Promise((resolve,reject)=>{resolveOld=resolve;rejectOld=reject;});return{id:'new-source-saved',...payload};
  }}});
  const form=t.document.getElementById('hosted-auth-form');form.values={name:'Nagy Anna',email:'anna@example.hu',password:'secret-password-123',accountType:'private'};const submitted=form.handlers.submit({preventDefault(){},currentTarget:form});await settle();assert.equal(typeof resolveOld,'function');
  const replacement=await finishReplacementSearch(t,second,'Az új forráshoz mentett keresésem');
  assert.notEqual(replacement.id,initial.id);assert.deepEqual(writes,[initial.creationRequestId,replacement.creationRequestId]);assert.equal(storedOnboarding(t),null);assert.equal(t.ctx.location.hash,'#searches');
  const app=t.document.getElementById('app').innerHTML,confirmation=t.document.getElementById('modal-root').innerHTML;assert.match(confirmation,/Az új forráshoz mentett keresésem/);
  if(outcome==='success')resolveOld({id:'abandoned-source-saved',...data});else rejectOld(Object.assign(new Error('A korábbi mentés hibája'),{status:503}));await submitted;await settle();
  assert.equal(storedOnboarding(t),null);assert.equal(t.ctx.location.hash,'#searches');assert.equal(t.document.getElementById('app').innerHTML,app);assert.equal(t.document.getElementById('modal-root').innerHTML,confirmation);assert.deepEqual(writes,[initial.creationRequestId,replacement.creationRequestId]);
 }
});

test('an abandoned account lookup cannot create or disturb the replacement saved before its result arrives',async()=>{
 const first=onboardingProperty('first'),second=onboardingProperty('second',publicSourceKey('property','d'));
 const data={title:'Lecserélt, még be sem küldött keresés',type:'Lakás',locationIds:['city:Debrecen'],maxPrice:85,minArea:45};
 const initial=onboardingHelpers.prepareDraftForAuth(onboardingHelpers.createDraft('search',data,{origin:onboardingHelpers.originFromListing('property',first.sourceKey)}),'anna@example.hu');
 const baseline=await createModel({getItem:()=>null,setItem:()=>{}}).getState();let reads=0,resolveOld;const writes=[];
 const t=await setup({hosted:true,hash:'#register',fetchLanding:async()=>({...landingFixture(''),properties:[first,second]}),regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(initial)},apiOverrides:{getState:async()=>++reads===1?await new Promise(resolve=>{resolveOld=resolve;}):baseline,saveEntity:async(kind,payload,id,options)=>{writes.push(options.creationRequestId);return{id:'replacement-after-lookup',...payload};}}});
 const form=t.document.getElementById('hosted-auth-form');form.values={name:'Nagy Anna',email:'anna@example.hu',password:'secret-password-123',accountType:'private'};const submitted=form.handlers.submit({preventDefault(){},currentTarget:form});await settle();assert.equal(typeof resolveOld,'function');
 const replacement=await finishReplacementSearch(t,second,'Mentés a gyorsabb új kereséshez');assert.deepEqual(writes,[replacement.creationRequestId]);assert.equal(storedOnboarding(t),null);const confirmation=t.document.getElementById('modal-root').innerHTML;assert.match(confirmation,/Mentés a gyorsabb új kereséshez/);
 resolveOld(baseline);await submitted;await settle();assert.deepEqual(writes,[replacement.creationRequestId]);assert.equal(storedOnboarding(t),null);assert.equal(t.ctx.location.hash,'#searches');assert.equal(t.document.getElementById('modal-root').innerHTML,confirmation);
});

test('an abandoned save completion cannot unlock a replacement authentication or save that is still pending',async()=>{
 for(const stage of ['authentication','save'])for(const outcome of ['success','failure']){
  const first=onboardingProperty('first'),second=onboardingProperty('second',publicSourceKey('property','9'));
  const data={title:'Lecserélt, késleltetett régi mentés',type:'Lakás',locationIds:['city:Debrecen'],maxPrice:85,minArea:45};
  const initial=onboardingHelpers.prepareDraftForAuth(onboardingHelpers.createDraft('search',data,{origin:onboardingHelpers.originFromListing('property',first.sourceKey)}),'anna@example.hu');
  let resolveOld,rejectOld,releaseAuth,resolveNew,authCount=0;const writes=[];
  const t=await setup({hosted:true,hash:'#register',fetchLanding:async()=>({...landingFixture(''),properties:[first,second]}),regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(initial)},connectApi:async()=>{authCount++;if(stage==='authentication'&&authCount===2)await new Promise(resolve=>{releaseAuth=resolve;});},apiOverrides:{saveEntity:async(kind,payload,id,options)=>{
   writes.push(options.creationRequestId);if(options.creationRequestId===initial.creationRequestId)return await new Promise((resolve,reject)=>{resolveOld=resolve;rejectOld=reject;});return await new Promise(resolve=>{resolveNew=()=>resolve({id:'current-pending-source-saved',...payload});});
  }}});
  const oldForm=t.document.getElementById('hosted-auth-form');oldForm.values={name:'Nagy Anna',email:'anna@example.hu',password:'secret-password-123',accountType:'private'};const oldSubmitted=oldForm.handlers.submit({preventDefault(){},currentTarget:oldForm});await settle();assert.equal(typeof resolveOld,'function');
  await t.click({action:'landing'});await t.click({action:'onboarding-start',kind:'search',source:second.key});const replacement=storedOnboarding(t);await advanceEditor(t,4);await submitEditor(t);assert.equal(t.ctx.location.hash,'#register');
  const newForm=t.document.getElementById('hosted-auth-form');newForm.values={name:'Nagy Anna',email:'anna@example.hu',password:'secret-password-123',accountType:'private'};const newSubmitted=newForm.handlers.submit({preventDefault(){},currentTarget:newForm});await settle();
  if(stage==='authentication')assert.equal(typeof releaseAuth,'function');else assert.equal(typeof resolveNew,'function');
  if(outcome==='success')resolveOld({id:'obsolete-success',...data});else rejectOld(Object.assign(new Error('obsolete request failed'),{status:503}));await oldSubmitted;await settle();
  assert.equal(storedOnboarding(t).id,replacement.id);assert.equal(authCount,2);assert.doesNotMatch(t.document.getElementById('app').innerHTML,/obsolete request failed|obsolete-success/);
  await newForm.handlers.submit({preventDefault(){},currentTarget:newForm});assert.equal(authCount,2,'An old callback cannot release the busy guard of the current authentication');
  if(stage==='authentication'){releaseAuth();await settle();assert.equal(typeof resolveNew,'function');}
  await t.click({action:'onboarding-save-retry'});assert.deepEqual(writes,[initial.creationRequestId,replacement.creationRequestId],'An old finally block cannot release the replacement save marker or cause another POST');
  resolveNew();await newSubmitted;await settle();assert.equal(storedOnboarding(t),null);assert.equal(t.ctx.location.hash,'#searches');assert.match(t.document.getElementById('modal-root').innerHTML,/current-pending-source-saved/);assert.deepEqual(writes,[initial.creationRequestId,replacement.creationRequestId]);
 }
});

// A suspended foreground read must not make a navigation click look ignored.
test('cached workspace navigation responds before a resumed account read completes',async()=>{
 const baseline=await createModel({getItem:()=>null,setItem:()=>{}}).getState();let delayed=false,release;
 const t=await setup({hosted:true,authenticated:true,hash:'#discover',apiOverrides:{getState:async()=>delayed?await new Promise(resolve=>{release=()=>resolve(baseline);}):baseline}});
 delayed=true;const navigation=t.click({page:'settings'});await settle();
 try{
  assert.ok(t.document.getElementById('profile-form'),'The selected settings screen must appear immediately from the same-account snapshot, before a slow resumed GET returns');
  assert.match(t.document.getElementById('app').innerHTML,/Beállítások/);
 }finally{release?.();await navigation;}
});

test('an acknowledged decision does not lock local wizard controls behind its slow read refresh',async()=>{
 const baseline=await createModel({getItem:()=>null,setItem:()=>{}}).getState();let paused=false;const releases=[];
 const t=await setup({hosted:true,authenticated:true,hash:'#discover',apiOverrides:{getState:async()=>paused?await new Promise(resolve=>{releases.push(()=>resolve(baseline));}):baseline}});
 const decide=t.model.decide;t.model.decide=async(...args)=>{const value=await decide(...args);paused=true;return value;};
 const pending=t.click({action:'pass'});let nextWrite=Promise.resolve();await settle();assert.ok(releases.length,'The write has completed and its subsequent read is deliberately delayed');
 try{
  t.ui.openEditor('search');chooseLocation(t,'city:Debrecen');const type=t.document.getElementById('f-type');type.value='Lakás';type.handlers.change({target:type,currentTarget:type});
  await editorAction(t,'editor-next');assert.equal(editorStep(t),1,'A local Next action must remain usable after the write is acknowledged, even while refreshed data is pending');
  let topups=0;const topup=t.model.buyDemoCredits;t.model.buyDemoCredits=async(...args)=>{topups++;return topup(...args);};nextWrite=t.click({action:'confirm-test-credits',amount:'100'});await settle();assert.equal(topups,1,'The acknowledged decision must also release the write guard before its unrelated read refresh returns');
 }finally{paused=false;for(const release of releases)release();await Promise.all([pending,nextWrite]);}
});

function emitVisibility(t,state){t.document.visibilityState=state;t.document.hidden=state==='hidden';return t.document.handlers.visibilitychange?.({type:'visibilitychange',target:t.document});}
function foregroundBurst(t){emitVisibility(t,'visible');return [t.windowEvents.focus?.({type:'focus'}),t.windowEvents.pageshow?.({type:'pageshow',persisted:true})].filter(value=>value?.then);}

test('a foreground lifecycle burst never releases an unacknowledged decision for another POST',async()=>{
 let writes=0,resolveWrite;
 const t=await setup({hosted:true,authenticated:true,hash:'#discover',apiOverrides:{decide:async()=>{writes++;return await new Promise(resolve=>{resolveWrite=resolve;});}}});
 const first=t.click({action:'like'});await settle();assert.equal(writes,1);
 emitVisibility(t,'hidden');t.windowEvents.pagehide?.({type:'pagehide',persisted:true});const foreground=foregroundBurst(t);await settle();
 await t.click({action:'like'});await t.click({action:'pass'});assert.equal(writes,1,'Returning to a tab must not clear the mutation guard while its POST is still unresolved');
 t.ui.openEditor('search');chooseLocation(t,'city:Debrecen');const type=t.document.getElementById('f-type');type.value='Lakás';type.handlers.change({target:type,currentTarget:type});
 const form=t.document.getElementById('entity-form');await editorAction(t,'editor-next');assert.equal(editorStep(t),1,'Local editing must remain available even while a different write is still pending');await editorAction(t,'editor-back');assert.equal(editorStep(t),0);
 resolveWrite({match:null,charged:0,feedbackPrompt:null});await first;await Promise.all(foreground);await settle();assert.equal(writes,1,'Foreground handling must never replay a write automatically');assert.equal(t.document.getElementById('entity-form'),form,'A late decision acknowledgement cannot close a newly opened unrelated wizard');
});

test('foreground revalidation clears an old-account private snapshot before waiting for the new account',async()=>{
 const baseline=await createModel({getItem:()=>null,setItem:()=>{}}).getState();let paused=false,current=baseline;const releases=[];
 const t=await setup({hosted:true,authenticated:true,hash:'#settings',regionStorage:{'otthonra.api':'session-anna'},apiOverrides:{getState:async()=>paused?await new Promise(resolve=>{releases.push(resolve);}):current}});
 assert.ok(t.document.getElementById('profile-form'));assert.match(t.document.getElementById('app').innerHTML,/anna@example.hu/);
 emitVisibility(t,'hidden');paused=true;current={...baseline,user:{...baseline.user,id:'other-account',name:'Másik Fiók',email:'other@example.hu'},properties:[],searches:[],active:null};t.regionStorage.set('otthonra.api','session-other');const foreground=foregroundBurst(t);await settle();
 try{
  assert.doesNotMatch(t.document.getElementById('app').innerHTML,/anna@example.hu|Nagy Anna/,'A session change on another tab must remove the previous user before a potentially slow new account read');
 }finally{
  paused=false;for(const release of releases)release(current);await Promise.all(foreground);await settle();
 }
});

function inputEvent(t,input){const event={type:'input',target:input,currentTarget:input};for(let node=input;node;node=node.parentElement)node.handlers.input?.(event);t.document.handlers.input?.(event);}

test('late foreground reads preserve the mounted form and text entered before the response',async()=>{
 const baseline=await createModel({getItem:()=>null,setItem:()=>{}}).getState();let paused=false;const releases=[];
 const t=await setup({hosted:true,authenticated:true,hash:'#discover',apiOverrides:{getState:async()=>paused?await new Promise(resolve=>{releases.push(resolve);}):baseline}});
 paused=true;const navigation=t.click({page:'settings'});await settle();
 const form=t.document.getElementById('profile-form'),name=t.document.getElementById('f-name');
 try{
  assert.ok(form,'Cached navigation must make the form available before background reads');
  name.value='Még el nem mentett saját név';name.focus();inputEvent(t,name);
  emitVisibility(t,'hidden');const foreground=foregroundBurst(t);await settle();
  paused=false;for(const release of releases)release(baseline);await navigation;await Promise.all(foreground);await settle();
  assert.equal(t.document.getElementById('profile-form'),form,'A foreground revalidation must retain the interactive form node');assert.equal(t.document.getElementById('f-name'),name);assert.equal(name.value,'Még el nem mentett saját név');
 }finally{paused=false;for(const release of releases)release(baseline);await navigation;}
});

test('profile save captures its form before awaiting and preserves newer edits after its acknowledgement',async()=>{
 const baseline=await createModel({getItem:()=>null,setItem:()=>{}}).getState();let current=baseline,release;const writes=[];
 const t=await setup({hosted:true,authenticated:true,hash:'#settings',apiOverrides:{getState:async()=>current,updateProfile:async data=>{writes.push(data);return await new Promise(resolve=>{release=()=>{current={...baseline,user:{...baseline.user,...data}};resolve(current.user);};});}}});
 const form=t.document.getElementById('profile-form'),name=t.document.getElementById('f-name');name.value='Első, beküldött név';inputEvent(t,name);
 const event={preventDefault(){},currentTarget:form};form.handlers.submit(event);event.currentTarget=null;await settle();assert.equal(typeof release,'function');assert.equal(writes[0].name,'Első, beküldött név');
 name.value='Közben tovább szerkesztett név';inputEvent(t,name);release();await settle();
 assert.equal(t.document.getElementById('profile-form'),form);assert.equal(name.value,'Közben tovább szerkesztett név');assert.equal(form.dataset.unsaved,'true','Acknowledging the submitted snapshot must not mark a newer edit as already saved');assert.match(t.document.getElementById('toast').textContent,/profiladataidat elmentettük/);
});

test('a cancelled earlier page read cannot replace the newer navigation when its transport answers late',async()=>{
 const baseline=await createModel({getItem:()=>null,setItem:()=>{}}).getState();let delayNext=false,release;const receivedSignals=[];
 const t=await setup({hosted:true,authenticated:true,hash:'#discover',apiOverrides:{getState:async options=>{receivedSignals.push(options?.signal);if(delayNext){delayNext=false;return await new Promise(resolve=>{release=()=>resolve(baseline);});}return baseline;}}});
 delayNext=true;const older=t.click({page:'settings'});await settle();assert.ok(t.document.getElementById('profile-form'));
 const signal=receivedSignals.at(-1);await t.click({page:'properties'});assert.equal(t.ctx.location.hash,'#properties');assert.equal(t.document.getElementById('profile-form'),null);assert.equal(signal.aborted,true,'Changing pages must cancel the retired view read');
 release();await older;await settle();assert.equal(t.ctx.location.hash,'#properties');assert.equal(t.document.getElementById('profile-form'),null);assert.match(t.document.getElementById('app').innerHTML,/Saját ingatlanok/);
});

test('opening liked profiles first still resolves mutual matches and exposes the existing conversation action',async()=>{
 const t=await setup();const match=t.model.matches()[0];assert.ok(match);
 await t.click({action:'tab',tab:'liked'});
 const html=t.document.getElementById('app').innerHTML;assert.match(html,/Kölcsönös találat/);assert.ok(html.includes(`data-action="open-chat" data-id="${match.id}"`),'The liked view must load mutual-match data even when Matches has never been opened');
});

test('stale discovery details cannot open an inert modal and fresh detail actions target the newly verified candidate',async()=>{
 const base=createModel({getItem:()=>null,setItem:()=>{}}),baseline=base.getState(),candidates=base.feed();assert.ok(candidates.length>1);let paused=false,refreshed=false;const releases=[],decisions=[];
 const t=await setup({hosted:true,authenticated:true,hash:'#discover',apiOverrides:{getState:async()=>paused?await new Promise(resolve=>{releases.push(()=>resolve(baseline));}):baseline,recommendations:async()=>({items:[candidates[refreshed?1:0]],stage:'exact',active:baseline.active}),decide:async(item,liked)=>{decisions.push({id:item.id,liked});return{match:null,charged:0,feedbackPrompt:null};}}});
 paused=true;emitVisibility(t,'hidden');const foreground=foregroundBurst(t);await settle();
 try{
  await t.click({action:'details'});assert.equal(t.document.getElementById('modal-root').innerHTML,'','A stale cached card cannot create a details dialog whose decisions remain blocked forever');assert.deepEqual(decisions,[]);
 }finally{paused=false;refreshed=true;for(const release of releases)release();await Promise.all(foreground);await settle();}
 await t.click({action:'details'});assert.match(t.document.getElementById('modal-root').innerHTML,new RegExp(candidates[1].title.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')));await t.click({action:'pass'});assert.deepEqual(decisions,[{id:candidates[1].id,liked:false}]);
});

test('a focus-only resume retires an aged read once even when the operating system sent no hidden event',async()=>{
 let clock=Date.now();class ResumeDate extends Date{static now(){return clock;}}
 const baseline=await createModel({getItem:()=>null,setItem:()=>{}}).getState();let reads=0,releaseOld,releaseFresh;const signals=[];
 const t=await setup({Date:ResumeDate,hosted:true,authenticated:true,hash:'#discover',apiOverrides:{getState:async options=>{reads++;signals.push(options?.signal);if(reads===2)return await new Promise(resolve=>{releaseOld=resolve;});if(reads===3)return await new Promise(resolve=>{releaseFresh=resolve;});return baseline;}}});
 const older=t.click({page:'settings'});await settle();assert.equal(reads,2);const oldSignal=signals.at(-1);
 clock+=60000;const resumed=[t.windowEvents.focus({type:'focus'}),t.windowEvents.pageshow({type:'pageshow',persisted:true})];await settle();
 try{
  assert.equal(reads,3,'Focus and pageshow must share one fresh read instead of reusing the aged request');assert.equal(oldSignal.aborted,true);assert.equal(t.document.hidden,false,'No hidden/visibility event was involved in this reproduction');
  releaseFresh({...baseline,user:{...baseline.user,name:'Frissen ellenőrzött név'}});await Promise.all(resumed);await settle();assert.equal(t.ui.getModelState().user.name,'Frissen ellenőrzött név');
 }finally{releaseFresh?.(baseline);releaseOld?.({...baseline,user:{...baseline.user,name:'Elavult, késői név'}});await older;await Promise.all(resumed);await settle();}
 assert.equal(t.ui.getModelState().user.name,'Frissen ellenőrzött név','The old read cannot overwrite the fresh response when it finally arrives');
});

test('queued impression writes and old impression errors cannot cross a raw session-token change',async()=>{
 for(const stage of ['queued','inflight']){
  const observers=[];class Observer{constructor(callback){this.callback=callback;observers.push(this);}observe(){}disconnect(){}}
  let calls=0,rejectOld;
  const t=await setup({hosted:true,authenticated:true,hash:'#discover',regionStorage:{'otthonra.api':'session-a'},IntersectionObserver:Observer,apiOverrides:{recordImpression:async()=>{calls++;if(stage==='inflight')return await new Promise((_resolve,reject)=>{rejectOld=reject;});return{recorded:true};}}});
  observers.at(-1).callback([{isIntersecting:true,intersectionRatio:1}]);
  if(stage==='inflight'){await settle();assert.equal(calls,1);}
  t.regionStorage.set('otthonra.api','session-b');
  if(stage==='inflight')rejectOld(Object.assign(new Error('An old impression session expired'),{status:401}));
  await settle();assert.equal(calls,stage==='queued'?0:1,'A queued old impression must recheck credentials before its POST starts');assert.equal(t.regionStorage.get('otthonra.api'),'session-b');assert.equal(t.disconnected.length,0,'An old impression 401 must not log the newer session out');assert.equal(t.document.getElementById('hosted-auth-form'),null);
 }
});

test('landing map clicks toggle the exact selected quarter and hand off only the remaining locations',async()=>{
 const t=await setup({hosted:true,hash:'#landing',mockMaps:true});await settle();
 const venkert=debrecenQuarter('Vénkert'),sestakert=debrecenQuarter('Sestakert'),map=activeMap(t,'landing-location-map');
 assert.equal(map.select(venkert.id),true);assert.equal(map.select(sestakert.id),true);
 assert.deepEqual(map.ids,[venkert.id,sestakert.id]);
 assert.equal(map.select(venkert.id),true,'A second map click must remove the same selected quarter');
 assert.deepEqual(map.ids,[sestakert.id]);
 const chips=t.document.getElementById('landing-location-chips').innerHTML;
 assert.doesNotMatch(chips,/Vénkert/);assert.match(chips,/Sestakert/);
 const form=t.document.getElementById('landing-search-form');form.handlers.submit({preventDefault(){},currentTarget:form});await settle();
 const draft=storedOnboarding(t);assert.deepEqual(draft.data.locationIds,[sestakert.id]);
 assert.equal(map.disposed,true,'The old map is cleaned up when the draft editor opens');
});

test('owned search map addition narrows a city and toggling off preserves every other selected place',async()=>{
 const t=await setup({mockMaps:true});t.ui.openEditor('search');await settle();
 chooseLocation(t,'city:Debrecen');chooseLocation(t,'city:Solymár');
 const venkert=debrecenQuarter('Vénkert'),map=activeMap(t,'search-location-map');
 assert.equal(map.select(venkert.id),true);assert.deepEqual(map.ids,['city:Solymár',venkert.id]);
 assert.equal(map.select(venkert.id),true);assert.deepEqual(map.ids,['city:Solymár']);
 chooseLocation(t,'city:Debrecen');assert.equal(map.select(venkert.id),true);
 chooseLocation(t,'city:Debrecen');assert.deepEqual(map.ids,['city:Solymár',venkert.id,'city:Debrecen']);
 assert.equal(map.select(venkert.id),true);assert.deepEqual(map.ids,['city:Solymár','city:Debrecen'],'Removing a selected quarter must not silently remove a separately selected city');
 submitEntity(t,searchValues('Térképes kijelölés visszavonása'));await settle();
 const saved=t.model.getState().searches.find(item=>item.title==='Térképes kijelölés visszavonása');
 assert.deepEqual([...saved.locationIds],['city:Solymár','city:Debrecen']);
});

test('guest search map removal persists to its draft and does not restore the removed quarter on reload',async()=>{
 const t=await setup({hosted:true,hash:'#landing',mockMaps:true});
 t.ui.startOnboarding('search',null,[getLocation('city:Solymár')]);await settle();
 const venkert=debrecenQuarter('Vénkert'),map=activeMap(t,'search-location-map');
 assert.equal(map.select(venkert.id),true);assert.ok(storedOnboarding(t).data.locationIds.includes(venkert.id));
 assert.equal(map.select(venkert.id),true);assert.deepEqual(storedOnboarding(t).data.locationIds,['city:Solymár']);
 const saved=JSON.parse(t.regionStorage.get(onboardingHelpers.DRAFT_STORAGE_KEY));
 const reloaded=await setup({hosted:true,hash:'#onboarding',mockMaps:true,regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(saved)}});await settle();
 assert.deepEqual(activeMap(reloaded,'search-location-map').ids,['city:Solymár']);
 assert.doesNotMatch(reloaded.document.getElementById('location-chips').innerHTML,/Vénkert/);
});

test('landing and guest search/property pickers show one compact source link with complete notices retained',async()=>{
 const t=await setup({hosted:true,hash:'#landing',mockMaps:true});await settle();
 const assertCompact=html=>{assert.equal((html.match(/>Források<\/a>/g)||[]).length,1);assert.match(html,/href="\/THIRD-PARTY-NOTICES\.txt"[^>]*>Források/);assert.doesNotMatch(html,/Városkörnyékek:|Városrészek: <a|Utcák: <a|Magyar Posta Partner Extra/);};
 assertCompact(t.document.getElementById('app').innerHTML);
 t.ui.startOnboarding('search',null,[getLocation('city:Debrecen')]);await settle();assertCompact(t.document.getElementById('app').innerHTML);
 await t.click({action:'landing'});t.ui.startOnboarding('property',null,[]);await settle();assertCompact(t.document.getElementById('app').innerHTML);
 assert.ok(t.document.getElementById('street-source'),'The address input keeps its accessible source description target');
 assert.match(t.document.getElementById('f-street').getAttribute('aria-describedby'),/street-source/);
 const notices=await fs.readFile(new URL('../dist/THIRD-PARTY-NOTICES.txt',import.meta.url),'utf8');
 for(const provider of ['KSH','OpenStreetMap contributors','Magyar Posta'])assert.ok(notices.includes(provider),provider+' attribution must remain available from the single source link');
});

test('map child selection replaces its selected ancestors on landing and owned search while retaining unrelated places',async()=>{
 const pest=getLocation('neighborhood:3c4a84155a32b95a18f2e0da'),ward=getLocation('neighborhood:0ab2e492e16ec4c7f9ec10f8'),child=getLocation('neighborhood:004a6fde01726bde5e318d21'),other=debrecenQuarter('Vénkert');
 assert.equal(pest.name,'Pest');assert.equal(ward.name,'VIII. kerület');assert.equal(child.name,'Ganznegyed');
 for(const landing of [true,false]){
  const t=await setup(landing?{hosted:true,hash:'#landing',mockMaps:true}:{mockMaps:true});
  if(!landing)t.ui.openEditor('search');await settle();
  const map=activeMap(t,landing?'landing-location-map':'search-location-map');
  assert.equal(map.select(other.id),true);assert.equal(map.select(pest.id),true);
  assert.equal(map.select(ward.id,{ancestorIds:[pest.id,other.id,'city:Debrecen','not-a-canonical-id']}),true);
  assert.deepEqual(map.ids,[other.id,ward.id],'Only canonical ancestors from the target city may be replaced');
  assert.equal(map.select(child.id,{ancestorIds:[ward.id,pest.id]}),true);
  assert.deepEqual(map.ids,[other.id,child.id],'A finer neighborhood must narrow its whole selected ward instead of leaving broad OR criteria');
  assert.equal(map.select(child.id,{ancestorIds:[ward.id,pest.id]}),true);
  assert.deepEqual(map.ids,[other.id],'Toggling off still removes only the exact target');
 }
});

test('ancestor replacement succeeds at the fifty-place limit and text selection remains additive',async()=>{
 const pest=getLocation('neighborhood:3c4a84155a32b95a18f2e0da'),ward=getLocation('neighborhood:0ab2e492e16ec4c7f9ec10f8'),child=getLocation('neighborhood:004a6fde01726bde5e318d21');
 const other=locations.filter(item=>item.kind==='city'&&item.city!=='Budapest').slice(0,49);
 const t=await setup({hosted:true,hash:'#landing',mockMaps:true});t.ui.startOnboarding('search',null,[pest,...other]);await settle();
 const map=activeMap(t,'search-location-map');assert.equal(map.ids.length,50);
 assert.equal(map.select(ward.id,{ancestorIds:[pest.id]}),true);assert.equal(map.ids.length,50);assert.ok(!map.ids.includes(pest.id));
 assert.equal(map.select(child.id,{ancestorIds:[ward.id,pest.id]}),true);assert.equal(map.ids.length,50);assert.ok(!map.ids.includes(ward.id));
 assert.deepEqual(storedOnboarding(t).data.locationIds,[...other.map(item=>item.id),child.id]);
 const owned=await setup({mockMaps:true});owned.ui.openEditor('search');await settle();
 const ownedMap=activeMap(owned,'search-location-map');ownedMap.select(child.id);
 chooseLocation(owned,pest.id);assert.deepEqual(ownedMap.ids,[child.id,pest.id],'The text picker must keep its ordinary multi-location OR semantics');
});

test('map town and administrative district labels work on both landing and owned search forms',async()=>{
 const city=getLocation('city:Debrecen'),other=getLocation('city:Solymár'),ward=getLocation('district:Budapest:8');
 const pest=getLocation('neighborhood:3c4a84155a32b95a18f2e0da'),wardArea=getLocation('neighborhood:0ab2e492e16ec4c7f9ec10f8'),child=getLocation('neighborhood:004a6fde01726bde5e318d21');
 for(const landing of [true,false]){
  const t=await setup(landing?{hosted:true,hash:'#landing',mockMaps:true}:{mockMaps:true});
  if(!landing)t.ui.openEditor('search');await settle();
  const map=activeMap(t,landing?'landing-location-map':'search-location-map');
  assert.equal(map.select(city.id),true);assert.equal(map.select(other.id),true);
  assert.equal(map.select(city.id),true);assert.deepEqual(map.ids,[other.id]);
  assert.equal(map.select(pest.id),true);assert.equal(map.select(ward.id,{ancestorIds:[pest.id]}),true);
  assert.deepEqual(map.ids,[other.id,ward.id]);
  assert.equal(map.select(child.id,{ancestorIds:[ward.id,wardArea.id,pest.id]}),true);
  assert.deepEqual(map.ids,[other.id,child.id],'A finer neighborhood replaces its canonical administrative district alias');
  assert.equal(map.select(child.id),true);assert.deepEqual(map.ids,[other.id]);
 }
});
