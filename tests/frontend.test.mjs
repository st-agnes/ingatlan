/** Offline integration smoke tests with a minimal simulated DOM. These do not replace browser QA. */
import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs/promises';
import {createModel} from '../dist/model.js';
import {searchLocations,getLocation,resolveLegacyLocations,locations} from '../dist/locations.js';
import * as propertyAttributes from '../dist/attributes.js';
import * as attributeCardArt from '../dist/attribute-card-art.js';
import * as accountHelpers from '../dist/accounts.js';
import * as feedbackHelpers from '../dist/feedback.js';
import * as onboardingHelpers from '../dist/onboarding.js';
import * as contactPolicy from '../dist/contact-policy.js';
import * as energyRatingHelpers from '../dist/energy-rating.js';
import * as publicListingHelpers from '../dist/public-listings.js';


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
  this.style={setProperty(name,value){this[name]=String(value);},removeProperty(name){delete this[name];}};this.handlers={};this.scrollHeight=500;this.scrollTop=0;this.validationMessage='';this.reportedValidity=0;
  this.classList={toggle:(name,on)=>{const classes=new Set(this.className.split(' ').filter(Boolean));if(on??!classes.has(name))classes.add(name);else classes.delete(name);this.className=[...classes].join(' ');},remove:name=>this.classList.toggle(name,false),add:name=>this.classList.toggle(name,true),contains:name=>this.className.split(' ').includes(name)};
 }
 set innerHTML(value){const previous=this._innerHTML;this._innerHTML=value;this.innerHTMLWasAssigned=true;if(['app','modal-root'].includes(this.id)){for(const match of previous.matchAll(/\bid=["']([^"']+)["']/g))if(!['app','modal-root','toast'].includes(match[1]))this.doc.elements.delete(match[1]);}else this.doc.replaceContents(this.id,value);if(this.id==='modal-root'){const markup=value.match(/<[^>]*class="modal(?:\s[^"]*)?"[^>]*>/)?.[0];this.doc.currentModal=markup?new Element('__modal-'+(++this.doc.modalSerial),this.doc,markup):null;if(this.doc.currentModal)this.doc.currentModal.isModal=true;}}
 get innerHTML(){return this._innerHTML;}
 addEventListener(type,handler){const prior=this.handlers[type];this.handlers[type]=prior?event=>{prior(event);return handler(event);}:handler;}
 dispatchEvent(event){event.target??=this;event.currentTarget=this;this.handlers[event.type]?.(event);if(event.bubbles&&!event.propagationStopped)this.parentElement?.dispatchEvent?.(event);return !event.defaultPrevented;}
 querySelectorAll(selector){return this.doc.selectWithin(this,selector);}
 querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
 setAttribute(name,value){this.attributes[name]=String(value);if(name==='hidden')this.hidden=true;}
 getAttribute(name){return this.attributes[name]??null;}
 removeAttribute(name){delete this.attributes[name];if(name==='hidden')this.hidden=false;}
 setCustomValidity(message){this.validationMessage=message;}
 checkValidity(){
  if(this.disabled||this.type==='hidden')return true;
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
 contains(node){return node?.doc===this;}
 querySelectorAll(selector){return this.selectWithin(this,selector);}
 querySelector(selector){if(selector==='.modal')return this.currentModal;if(selector.startsWith('.modal '))return this.currentModal?.querySelectorAll(selector)[0]||null;if(selector.startsWith('#'))return this.getElementById(selector.slice(1).split(' ')[0]);return null;}
 selectWithin(root,selector){
  const selectors=selector.split(',').map(value=>value.trim().replace(/^\.modal\s+/,'')),markup=root.isModal?this.elements.get('modal-root').innerHTML:this.html,selected=[];
  for(const match of markup.matchAll(/<([a-z][\w-]*)\b[^>]*\bid="([^"]+)"[^>]*>/gi)){
   const element=this.getElementById(match[2]);if(!element||!root.isModal&&!root.contains(element))continue;
   if(selectors.some(value=>{const tag=value.match(/^[a-z]+/)?.[0];if(tag&&tag!==match[1].toLowerCase())return false;if(value.includes(':not(.modal-close)')&&element.classList.contains('modal-close'))return false;const negative=[...value.matchAll(/:not\(([^)]+)\)/g)].map(match=>match[1]);const positive=value.replace(/:not\([^)]+\)/g,'');const leaf=positive.trim().split(/[ >]+/).at(-1);for(const [,name]of leaf.matchAll(/\.([\w-]+)/g))if(!element.classList.contains(name))return false;const attributesMatch=fragment=>[...fragment.matchAll(/\[([\w-]+)(?:="([^"]*)")?\]/g)].every(([,name,expected])=>{const actual=element.getAttribute(name);return actual!==null&&(expected===undefined||actual===expected);});if(!attributesMatch(positive))return false;for(const fragment of negative){if(fragment.startsWith('.')&&element.classList.contains(fragment.slice(1)))return false;if(fragment.startsWith('[')&&attributesMatch(fragment))return false;}return true;}))selected.push(element);
  }
  return selected;
 }

 parentOf(id){
  // SVG-rich choice cards reuse the parsed structure until markup changes.
  // Always resolve the current node; values, focus and visibility stay live.
  const markup=this.html;
  if(this.parentMarkup!==markup){
   const stack=[],parents=new Map(),voidTags=new Set(['area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr']);
   for(const token of markup.matchAll(/<\/?([a-z][\w-]*)\b[^>]*>/gi)){
    const tag=token[1].toLowerCase(),opening=token[0];
    if(opening.startsWith('</')){const index=stack.findLastIndex(item=>item.tag===tag);if(index>=0)stack.length=index;continue;}
    const currentId=opening.match(/\bid=["']([^"']+)["']/)?.[1];if(currentId)parents.set(currentId,stack.findLast(item=>item.id)?.id||null);
    if(!voidTags.has(tag)&&!opening.endsWith('/>'))stack.push({tag,id:currentId});
   }
   this.parentMarkup=markup;this.parentIds=parents;
  }
  const parent=this.parentIds.get(id);return parent?this.getElementById(parent):null;
 }

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
 const timers=[],connected=[],disconnected=[],landingCalls=[],windowEvents={},windowListeners=new Map(),regionStorage=options.regionStorage instanceof Map?options.regionStorage:new Map(Object.entries(options.regionStorage||{})),maps=[];
 let currentHash=options.hash??(options.hosted&&!options.authenticated?'#login':'');
 const ctx=vm.createContext({
  document,console,Intl,Date:options.Date||Date,Promise,URL,URLSearchParams,AbortController,Event:class{constructor(type,{bubbles=false}={}){this.type=type;this.bubbles=bubbles;this.defaultPrevented=false;}preventDefault(){this.defaultPrevented=true;}stopPropagation(){this.propagationStopped=true;}},IntersectionObserver:options.IntersectionObserver,ResizeObserver:options.ResizeObserver,visualViewport:options.visualViewport,innerWidth:options.innerWidth,innerHeight:options.innerHeight,setTimeout:(callback,delay)=>{if(options.captureTimers)timers.push({callback,delay});return timers.length;},clearTimeout:()=>{},
  location:{get hash(){return currentHash;},set hash(value){const next=value?(value.startsWith('#')?value:'#'+value):'';if(next===currentHash)return;currentHash=next;if(options.dispatchHashChanges)Promise.resolve().then(()=>windowEvents.hashchange?.());},search:'',origin:'https://test.example'},window:{scrollTo:()=>{},matchMedia:()=>({matches:!!options.mobile}),addEventListener:(type,handler)=>{const listeners=windowListeners.get(type)||[];listeners.push(handler);windowListeners.set(type,listeners);windowEvents[type]=event=>{const pending=[...(windowListeners.get(type)||[])].map(callback=>callback(event)).filter(value=>value?.then);return pending.length?Promise.all(pending):undefined;};},removeEventListener:(type,handler)=>{windowListeners.set(type,(windowListeners.get(type)||[]).filter(listener=>listener!==handler));}},
  OTTHONRA_CONFIG:options.hosted?{mode:'api',environment:options.environment||'test'}:{mode:'demo',environment:'local'},
  searchLocations,getLocation,resolveLegacyLocations,...propertyAttributes,...attributeCardArt,...accountHelpers,...feedbackHelpers,...contactPolicy,...energyRatingHelpers,...publicListingHelpers,...Object.fromEntries(Object.entries(onboardingHelpers).filter(([name])=>!['loadDraft','saveDraft','clearDraft'].includes(name))),
  loadDraft:()=>onboardingHelpers.loadDraft(ctx.localStorage),saveDraft:draft=>onboardingHelpers.saveDraft(draft,ctx.localStorage),clearDraft:id=>onboardingHelpers.clearDraft(id,ctx.localStorage),
  findPublicLocations:async(query,limit,options)=>searchLocations(query,limit,options),findPublicStreets:async()=>[],API_CONFIG_KEY:'otthonra.api',
  hostedMode:()=>!!options.hosted,deploymentEnvironment:()=>options.hosted?(options.environment||'test'):'local',
  getModel:()=>selected,
  __createLocationMap:(container,{selectedIds,onSelect})=>{const map={id:container.id,ids:[...selectedIds],disposed:false,select:onSelect,setSelection(ids){this.ids=[...ids];},destroy(){this.disposed=true;}};maps.push(map);return map;},
  fetchPublicListing:options.fetchPublicListing||(async()=>{const error=new Error('A hirdetés nem található.');error.status=404;throw error;}),
  fetchLanding:async(input={})=>{landingCalls.push(input);if(options.fetchLanding)return options.fetchLanding(input);return landingFixture(input.region);},
  detectLandingRegion:options.detectLandingRegion||(async()=>null),
  localStorage:{getItem:key=>regionStorage.get(key)||null,setItem:(key,value)=>regionStorage.set(key,value),removeItem:key=>regionStorage.delete(key)},
  disconnectApi:()=>{disconnected.push(true);selected=options.hosted?null:demoModel;return selected;},
  connectApi:async(...args)=>{connected.push(args);if(options.connectApi)await options.connectApi(...args);selected=apiModel;return apiModel;},
  FormData:class {constructor(form){this.values=form.values===undefined?mountedFormValues(document,form):Array.isArray(form.values)?form.values:Object.entries(form.values||{});}get(k){return this.values.find(([key])=>key===k)?.[1]}has(k){return this.values.some(([key])=>key===k)}[Symbol.iterator](){return this.values[Symbol.iterator]()}}
 });
 const body=source.replace(/^import[^\n]+\n/gm,'').replace("import('./location-map.js')",options.mockMaps?'Promise.resolve({createLocationMap: __createLocationMap})':"import('./location-map.js')");
 options.onDocument?.(document,windowEvents);
 await vm.runInContext(`(async()=>{${body}\nglobalThis.ui={render,changePage,startOnboarding,openEditor,openDetails,openModal,closeModal,openActivation,matchingTags,openFeedbackPackages,openFeedbackPurchase,openFeedbackPrompt,propertyInsightsPage,getFeedbackPrompt:()=>feedbackPrompt,getModelState:()=>state};})()`,ctx);
 const click=async(dataset)=>{const target={dataset,closest:()=>target};await document.handlers.click({target,preventDefault(){}})};
 return{model:options.hosted?apiModel:demoModel,document,ctx,click,ui:ctx.ui,connected,disconnected,getSelectedModel:()=>selected,landingCalls,regionStorage,windowEvents,windowListenerCount:type=>(windowListeners.get(type)||[]).length,timers,maps,runNextTimer:()=>timers.shift()?.callback(),runTimers:()=>{for(const timer of timers.splice(0))timer.callback();}};
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
function formInputEvent(t,input,type='change'){
 const event={type,target:input,currentTarget:input,bubbles:true,preventDefault(){this.defaultPrevented=true;},stopPropagation(){this.propagationStopped=true;}};
 input.dispatchEvent(event);return event;
}
function chooseOptionalCard(t,name,value){
 const input=t.document.getElementById('f-'+name);assert.ok(input,`Missing canonical ${name}`);
 const desired=value==null?'':String(name==='condition'?propertyAttributes.normalizeCondition(value):name==='building'?propertyAttributes.normalizeBuilding(value):value),buttons=t.document.getElementById('entity-form').querySelectorAll('button').filter(button=>button.dataset.attributeName===name);
 if(!buttons.length){input.value=desired;formInputEvent(t,input);return;}
 if(name==='floor'||name==='buildingFloors'){
  const choice=desired!==''&&Number(desired)>10?'other':desired;
  const button=buttons.find(button=>button.dataset.buildingNumberValue===choice);
  const selected=buttons.find(button=>button.getAttribute('aria-pressed')==='true');
  if(!desired){if(selected)selected.handlers.click({target:selected,currentTarget:selected,preventDefault(){}});return;}
  assert.ok(button,`Missing illustrated ${name} choice ${choice}`);
  if(button.getAttribute('aria-pressed')!=='true')button.handlers.click({target:button,currentTarget:button,preventDefault(){}});
  if(choice==='other'){const other=t.document.getElementById('f-'+name+'Other');other.value=desired;formInputEvent(t,other,'input');}
  return;
 }
 const selected=buttons.find(button=>button.getAttribute('aria-pressed')==='true');
 if(!desired){if(selected)selected.handlers.click({target:selected,currentTarget:selected,preventDefault(){}});return;}
 const button=buttons.find(button=>button.dataset.attributeValue===desired);assert.ok(button,`Missing illustrated ${name} value ${desired}`);
 if(button.getAttribute('aria-pressed')!=='true')button.handlers.click({target:button,currentTarget:button,preventDefault(){}});
}
function chooseRadio(t,name,value){
 const controls=t.document.getElementById('entity-form').querySelectorAll('input').filter(input=>input.type==='radio'&&input.name===name),chosen=controls.find(input=>input.value===String(value??''));
 assert.ok(chosen,`Missing ${name} radio ${value}`);for(const input of controls)input.checked=input===chosen;formInputEvent(t,chosen);return chosen;
}
function chooseEnergy(t,name,value){const slider=t.document.getElementById('f-'+name+'-slider');assert.ok(slider);slider.value=String(energyRatingHelpers.energySliderIndex(value));formInputEvent(t,slider,'input');}
function setEditorValues(t,values){
 const entries=Array.isArray(values)?values:Object.entries(values),type=t.document.getElementById('f-type'),desiredType=entries.find(([name])=>name==='type')?.[1];
 if(desiredType!==undefined){type.value=String(desiredType);type.handlers.change?.({target:type,currentTarget:type});}
 for(const [name,value] of entries){
  const control=t.document.getElementById(name==='images'?'property-images':'f-'+name);
  if(!control||control.type==='checkbox')continue;
  if(control.type==='hidden'&&['floor','buildingFloors','condition','view','building','ceilingHeight','heatingType','insulated','airConditioning','solarPanels','privateGarden','balcony'].includes(name)&&!control.disabled){chooseOptionalCard(t,name,value);continue;}
  if(name==='constructionAge'){chooseRadio(t,name,value);continue;}
  if(name==='energyRating'||name==='minEnergyRating'){chooseEnergy(t,name,value);continue;}
  control.value=String(value??'');
 }
 if(entries.some(([name])=>name==='title')){const title=t.document.getElementById('f-title');title?.handlers.input?.({target:title,currentTarget:title});}
 type?.handlers.change?.({target:type,currentTarget:type});
 for(const name of ['wholeRooms','halfRooms']){const control=t.document.getElementById('f-'+name);control?.handlers.input?.({target:control,currentTarget:control,inputType:'insertText'});}
}
function editorStep(t){return Array.from({length:6},(_value,index)=>t.document.getElementById('editor-step-'+index)).findIndex(step=>step&&!step.hidden);}
function editorAction(t,id){const button=t.document.getElementById(id);assert.ok(button,`Missing editor control ${id}`);assert.equal(button.disabled,false,`${id} must be enabled`);return button.handlers.click({target:button,currentTarget:button,preventDefault(){}});}
function propertyTypeCard(t,value){
 const cards=[...t.document.html.matchAll(/<button\b[^>]*\bid="([^"]+)"[^>]*\bdata-property-type="([^"]+)"[^>]*>/g)];
 const match=cards.find(match=>decodeHtmlValue(match[2])===value);assert.ok(match,`Missing illustrated property type ${value}`);return t.document.getElementById(match[1]);
}
function selectEditorType(t,value){
 if(editorStep(t)!==1)editorAction(t,'editor-step-button-1');
 assert.equal(editorStep(t),1,'A property type can only be chosen after validating the location topic');
 const button=propertyTypeCard(t,value);button.handlers.click({target:button,currentTarget:button,preventDefault(){}});
 assert.equal(editorStep(t),1,'Selecting a property type must not navigate before an explicit Next action');
 return button;
}
function chooseEditorType(t,value){selectEditorType(t,value);return editorAction(t,'editor-next');}

function submitEditor(t,submitter){const form=t.document.getElementById('entity-form');return form.handlers.submit({preventDefault(){},currentTarget:form,submitter});}
function submitEntity(t,values){
 const form=t.document.getElementById('entity-form');form.values=values;setEditorValues(t,values);
 if(!t.document.getElementById('editor-step-0')){submitEditor(t);return;}
 for(let attempts=0;attempts<6;attempts++){
  const before=editorStep(t),type=(Array.isArray(values)?values:Object.entries(values)).find(([name])=>name==='type')?.[1];
  if(before===1&&type)chooseEditorType(t,type);else submitEditor(t);
  if(before===5||editorStep(t)===before)return;
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

test('closing or replacing the editor removes its picker and responsive navigation resources',async()=>{
 const viewportListeners=new Map(),observers=new Set(),viewport={width:390,height:844,offsetLeft:0,offsetTop:0,addEventListener(type,listener){const listeners=viewportListeners.get(type)||[];listeners.push(listener);viewportListeners.set(type,listeners);},removeEventListener(type,listener){viewportListeners.set(type,(viewportListeners.get(type)||[]).filter(item=>item!==listener));}};
 class Observer{constructor(callback){this.callback=callback;}observe(){observers.add(this);}disconnect(){observers.delete(this);}}
 const t=await setup({mobile:true,innerWidth:390,innerHeight:844,visualViewport:viewport,ResizeObserver:Observer,onDocument:document=>{
  const lookup=document.getElementById.bind(document);document.getElementById=id=>{const node=lookup(id);if(node&&['entity-form','editor-navigation'].includes(id)){if(!node.style.setProperty){node.style.setProperty=function(name,value){this[name]=String(value);};node.style.removeProperty=function(name){delete this[name];};}if(id==='editor-navigation')node.getBoundingClientRect=()=>({height:48});}return node;};
 }}),before=Object.fromEntries(['pointerdown','focusin','keydown','visibilitychange'].map(type=>[type,t.document.listenerCount(type)])),resizeBefore=t.windowListenerCount('resize');
 t.ui.openEditor('search');
 const mounted=Object.fromEntries(Object.keys(before).map(type=>[type,t.document.listenerCount(type)]));
 for(const type of ['pointerdown','focusin'])assert.ok(mounted[type]>before[type],`${type} dismissal is mounted for the editor`);
 assert.ok(t.windowListenerCount('resize')>resizeBefore,'The mounted responsive menu observes viewport changes');assert.equal(observers.size,1);for(const type of ['resize','scroll'])assert.equal(viewportListeners.get(type)?.length,1);
 const previousForm=t.document.getElementById('entity-form');assert.ok(previousForm.style['--editor-nav-clearance'],'Mobile content reserves space for the fixed navigation');
 t.ui.openEditor('property');
 for(const [type,count] of Object.entries(mounted))assert.equal(t.document.listenerCount(type),count,`${type} listeners do not accumulate when replacing the editor`);
 assert.equal(previousForm.style['--editor-nav-clearance'],undefined,'Replacing a form removes its stale navigation clearance');assert.equal(observers.size,1);for(const type of ['resize','scroll'])assert.equal(viewportListeners.get(type)?.length,1);
 const form=t.document.getElementById('entity-form');t.ui.closeModal();
 for(const [type,count] of Object.entries(before))assert.equal(t.document.listenerCount(type),count,`${type} listeners are removed when the editor closes`);
 assert.equal(t.windowListenerCount('resize'),resizeBefore);assert.equal(observers.size,0);for(const type of ['resize','scroll'])assert.equal(viewportListeners.get(type)?.length,0);assert.equal(form.style['--editor-nav-clearance'],undefined);
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
 for(const name of ['constructionAge','floor','buildingFloors','balcony','insulated','airConditioning','solarPanels','privateGarden','condition','building','view','ceilingHeight','heatingType']){
  const control=t.document.getElementById('f-'+name);assert.ok(control,`${name} canonical control must be present`);assert.equal(control.type,'hidden');assert.equal(control.value,'');assert.equal(control.required,false);
 }
 const radios=t.document.getElementById('entity-form').querySelectorAll('input').filter(input=>input.name==='constructionAge');assert.equal(radios.length,propertyAttributes.CONSTRUCTION_AGE_OPTIONS.length+1);assert.equal(radios[0].checked,true);assert.equal(radios[0].value,'');
 const heaters=t.document.getElementById('entity-form').querySelectorAll('button').filter(button=>button.dataset.attributeName==='heatingType');assert.deepEqual(heaters.map(button=>button.dataset.attributeValue),[...propertyAttributes.HEATING_OPTIONS]);assert.equal(t.document.getElementById('f-secondaryHeatingType'),null);assert.ok(html.includes('Nincs fűtés'));assert.equal((html.match(/name="parkingTypes"/g)||[]).length,propertyAttributes.PARKING_OPTIONS.length);
 chooseLocation(t,'city:Solymár');
 submitEntity(t,{street:'Teszt utca',houseNumber:'12/A',title:'Opcionális jellemzők',type:'Lakás',price:'82',area:'64',wholeRooms:'3',halfRooms:'0',floor:'',condition:'',building:'',constructionAge:'',view:'',ceilingHeight:'',insulated:'',airConditioning:'',solarPanels:'',images:''});
 await settle();
 const saved=t.model.getState().properties.find(item=>item.title==='Opcionális jellemzők');
 assert.ok(saved);
 for(const name of ['floor','balcony','insulated','airConditioning','solarPanels'])assert.equal(saved[name],null,name);
 for(const name of ['condition','building','constructionAge','view','ceilingHeight'])assert.equal(saved[name],'',name);
});

test('search checkboxes serialize several choices per category and can all be cleared',async()=>{
 const t=await setup();t.ui.openEditor('search');chooseLocation(t,'district:Budapest:13');
 const html=t.document.getElementById('modal-root').innerHTML;
 assert.match(html,/<fieldset id="conditions-group" class="[^"]*attribute-group[^"]*"[^>]*><legend>Állapot/);
 assert.match(html,/Többet is megjelölhetsz/);
 assert.equal(t.document.getElementById('entity-form').querySelectorAll('input').filter(input=>input.name==='buildings').length,12);
 submitEntity(t,[...Object.entries(searchValues('Részletes keresés')),['conditions','Jó'],['conditions','Új/felújított'],['buildings','Tégla'],['buildings','Panel'],['constructionAges','10 évnél fiatalabb'],['constructionAges','10–30 év közötti'],['views','Kertre néző'],['views','Panorámás'],['ceilingHeight','3 m feletti'],['floors','-1'],['floors','0'],['floors','11']]);
 await settle();
 let saved=t.model.getState().searches.find(item=>item.title==='Részletes keresés');assert.ok(saved);
 assert.deepEqual([...saved.conditions],['Jó','Új/felújított']);assert.deepEqual([...saved.buildings],['Tégla','Panel']);
 assert.deepEqual([...saved.constructionAges],['10 évnél fiatalabb','10–30 év közötti']);assert.deepEqual([...saved.views],['Kertre néző','Panorámás']);
 assert.deepEqual([...saved.floors],[-1,0,9]);assert.equal(saved.ceilingHeight,'3 m feletti');
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
 submitEntity(t,{street:'Teszt utca',houseNumber:'12/A',title:'Részletes eladó lakás',type:'Lakás',price:'78',area:'65',wholeRooms:'3',halfRooms:'0',floor:'12',condition:'Jó',building:'Csúsztatott zsalu',constructionAge:'31–40 év közötti',view:'Panorámás',ceilingHeight:'3 m feletti',heatingType:'Hőszivattyú',energyRating:'A+',energyRatingScheme:'2023',parkingTypes:'Mélygarázs',insulated:'false',airConditioning:'true',solarPanels:'',images:''});await settle();
 const saved=t.model.getState().properties.find(item=>item.title==='Részletes eladó lakás');assert.ok(saved);
 assert.equal(saved.floor,12);assert.equal(saved.insulated,false);assert.equal(saved.airConditioning,true);assert.equal(saved.solarPanels,null);
 assert.equal(saved.building,'Csúsztatott zsalu');assert.equal(saved.energyRating,'A+');
 t.ui.openEditor('property',saved.id);
 const html=t.document.getElementById('modal-root').innerHTML;
 assert.equal(t.document.getElementById('f-floor').value,'12');assert.equal(t.document.getElementById('f-floorOther').value,'12');assert.equal(t.document.getElementById('floor-other-field').hidden,false);
 assert.equal(t.document.getElementById('entity-form').querySelectorAll('button').find(button=>button.dataset.attributeName==='insulated'&&button.dataset.attributeValue==='false').getAttribute('aria-pressed'),'true');
 assert.equal(t.document.getElementById('f-heatingType').value,'Hőszivattyú');
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

test('seller illustrated heating, preserved legacy supplemental heating and multiple parking choices persist with exact room counts',async()=>{
 const raw=configuredCriteriaRaw('property');raw.properties.find(property=>property.id==='own-p1').secondaryHeatingType='Klíma';
 const t=await setup({initialRaw:raw});t.ui.openEditor('property','own-p1');
 const html=t.document.getElementById('modal-root').innerHTML,buttons=t.document.getElementById('entity-form').querySelectorAll('button').filter(button=>button.dataset.attributeName==='heatingType');
 assert.deepEqual(buttons.map(button=>button.dataset.attributeValue),[...propertyAttributes.HEATING_OPTIONS]);assert.equal(t.document.getElementById('f-secondaryHeatingType'),null);assert.doesNotMatch(html,/Kiegészítő fűtés|id="f-rooms"|id="f-parkingType"/);
 submitEntity(t,[...Object.entries({street:'Teszt utca',houseNumber:'12/A',title:'Egész és fél szobák',type:'Lakás',price:'82.5',area:'64.5',wholeRooms:'2',halfRooms:'3',floor:'-1',heatingType:'Nincs fűtés',images:''}),['parkingTypes','Garázs'],['parkingTypes','Udvari beálló']]);await settle();
 const saved=t.model.getState().properties.find(item=>item.id==='own-p1');assert.equal(saved.title,'Egész és fél szobák');assert.equal(saved.wholeRooms,2);assert.equal(saved.halfRooms,3);assert.equal(saved.rooms,3.5);assert.equal(saved.floor,-1);assert.equal(saved.heatingType,'Nincs fűtés');assert.equal(saved.secondaryHeatingType,'Klíma','Removing the editor control must not erase an unchanged legacy value');assert.deepEqual([...saved.parkingTypes],['Garázs','Udvari beálló']);
 t.ui.openEditor('property',saved.id);assert.equal(t.document.getElementById('f-wholeRooms').value,'2');assert.equal(t.document.getElementById('f-halfRooms').value,'3');
 assert.match(t.document.getElementById('modal-root').innerHTML,/name="parkingTypes" value="Garázs" checked/);
 await t.click({page:'properties'});assert.match(t.document.getElementById('app').innerHTML,/2 egész \+ 3 fél szoba/);
});

function guardedEvent(values={}){return {...values,defaultPrevented:false,preventDefault(){this.defaultPrevented=true;}};}
test('all entity numeric inputs block signs through keys, mobile beforeinput, paste and input fallback while preserving decimals and empty bounds',async()=>{
 const t=await setup();
 for(const kind of ['property','search']){
  t.ui.openEditor(kind);
  const inputs=t.document.getElementById('entity-form').querySelectorAll('input[type="number"]');assert.ok(inputs.length>=(kind==='property'?5:4));if(kind==='search')for(const name of ['minRooms','maxRooms'])assert.equal(t.document.getElementById('f-'+name).type,'hidden','Room limits use readonly counters rather than editable numeric inputs');
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
 const property=t.model.getState().properties.find(item=>item.title==='Ház mezőtisztítás');assert.ok(property);assert.equal(property.floor,null);assert.equal(property.balcony,null);assert.equal(property.elevator,false);
 t.ui.openEditor('search');chooseLocation(t,'city:Debrecen');submitEntity(t,[...Object.entries({...searchValues('Ház keresési mezőtisztítás'),type:'Ház',balcony:'on',elevator:'on'}),['floors','-1'],['heatingTypes','Gázkazán'],['heatingTypes','Hőszivattyú']]);await settle();
 const search=t.model.getState().searches.find(item=>item.title==='Ház keresési mezőtisztítás');assert.ok(search);assert.deepEqual([...search.floors],[]);assert.equal(search.balcony,false);assert.equal(search.elevator,false);assert.deepEqual([...search.heatingTypes],['Gázkazán / cirkó','Hőszivattyú']);
});

test('legacy arbitrary room totals are never rounded and existing heating or parking text remains selectable',async()=>{
 const demo=createModel({getItem:()=>null,setItem:()=>{}}).getState();demo.properties[0]={...demo.properties[0],id:'legacy-property',rooms:3.2,wholeRooms:null,halfRooms:null,heatingType:'Régi vegyes rendszer',parkingType:'Régi garázs és beálló',parkingTypes:undefined};
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{getState:async()=>demo}});t.ui.openEditor('property','legacy-property');const html=t.document.getElementById('modal-root').innerHTML;
 assert.equal(t.document.getElementById('f-wholeRooms').value,'');assert.equal(t.document.getElementById('f-halfRooms').value,'');assert.equal(t.document.getElementById('f-heatingType').value,'Régi vegyes rendszer');const existing=t.document.getElementById('entity-form').querySelectorAll('button').find(button=>button.dataset.attributeName==='heatingType'&&button.dataset.attributeValue==='Régi vegyes rendszer');assert.ok(existing);assert.equal(existing.getAttribute('aria-pressed'),'true');assert.match(html,/name="parkingTypes" value="Régi garázs és beálló" checked/);
});


function chooseReport(t,reason){for(const option of accountHelpers.REPORT_REASON_OPTIONS){const input=t.document.getElementById('f-reportReason-'+option.value);if(input)input.checked=option.value===reason;}}
function accountFixture(mutate){let raw;const local=createModel({getItem:()=>null,setItem:(_key,value)=>{raw=JSON.parse(value);}});local.activate('search','own-s1');mutate(raw);return raw;}
test('hosted and settings registration both offer account types and send the selected agent role',async()=>{
 const hosted=await setup({hosted:true});await hosted.click({action:'auth-mode',mode:'register'});
 const registration=hosted.document.getElementById('app').innerHTML;assert.match(registration,/id="f-accountType"/);assert.match(registration,/name="accountType" value="private" type="radio"/);assert.match(registration,/name="accountType" value="agent" type="radio"/);assert.match(registration,/Magánszemély/);assert.match(registration,/Ingatlanközvetítő/);assert.doesNotMatch(registration,/<select[^>]*accountType/);
 await submitHostedAuth(hosted,{...hostedCredentials,name:'Közvetítő Anna',accountType:'agent'});await settle();assert.equal(hosted.connected[0][3].accountType,'agent');
 const legacy=await setup();await legacy.click({page:'settings'});const choices=legacy.document.getElementById('api-accountType');assert.ok(choices);assert.equal(legacy.document.getElementById('api-accountType-private').checked,true);assert.equal(legacy.document.getElementById('api-accountType-agent').checked,false);
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
 const data=landingFixture();data.searches=Array.from({length:22},(_,i)=>({...data.searches[0],key:'s'+i,title:'Lakást & kertet <keresnek>',description:'hidden@example.hu',ownerId:'secret-owner',ownerName:'Titkos Név'}));data.properties=Array.from({length:14},(_,i)=>({...data.properties[0],key:'p'+i,title:'Eladó <lakás>',address:'Titkos utca 42.',images:['https://images.example.test/photo.jpg?size=1&view=2','javascript:alert(1)'],ownerEmail:'hidden@example.hu'}));
 const t=await setup({hosted:true,hash:'',fetchLanding:async()=>data}),html=t.document.getElementById('app').innerHTML;assert.equal((html.match(/class="landing-search-card(?:\s[^"]*)?"/g)||[]).length,16);assert.equal((html.match(/class="landing-property-card(?:\s[^"]*)?"/g)||[]).length,8);assert.match(html,/Lakást &amp; kertet/);assert.match(html,/https:\/\/images.example.test\/photo.jpg\?size=1&amp;view=2/);assert.doesNotMatch(html,/hidden@example|secret-owner|Titkos|javascript:|<keresnek>/);assert.doesNotMatch(source,/navigator\s*\.\s*geolocation|watchPosition|getCurrentPosition/);
});
test('manual region choice wins a delayed approximate lookup and only its canonical ID is remembered',async()=>{
 let detected;const geo=new Promise(resolve=>{detected=resolve});const t=await setup({hosted:true,hash:'',detectLandingRegion:()=>geo});assert.deepEqual(JSON.parse(JSON.stringify(t.landingCalls)),[{}]);let select=t.document.getElementById('landing-region');select.value='HU321';select.handlers.change({currentTarget:select});await settle();assert.equal(t.regionStorage.get('otthonra.landing.region'),'HU321');assert.match(t.document.getElementById('app').innerHTML,/Debrecen/);detected('HU110');await settle();assert.deepEqual(JSON.parse(JSON.stringify(t.landingCalls)),[{},{region:'HU321'}]);assert.equal(t.document.getElementById('landing-region').value,'HU321');
});
test('approximate region is optional and not persisted; saved manual region bypasses lookup',async()=>{
 const auto=await setup({hosted:true,hash:'',detectLandingRegion:async()=> 'HU321'});await settle();assert.deepEqual(JSON.parse(JSON.stringify(auto.landingCalls)),[{},{region:'HU321'}]);assert.equal(auto.regionStorage.size,0);
 let lookups=0;const saved=await setup({hosted:true,hash:'',regionStorage:{'otthonra.landing.region':'HU321'},detectLandingRegion:async()=>{lookups++;return 'HU110'}});assert.deepEqual(JSON.parse(JSON.stringify(saved.landingCalls)),[{},{region:'HU321'}]);assert.equal(lookups,0);assert.match(saved.document.getElementById('app').innerHTML,/Debrecen/);
});
test('regional empty results remain honest and national fallback clears remembered choice',async()=>{
 const t=await setup({hosted:true,hash:''});const select=t.document.getElementById('landing-region');select.value='HU232';select.handlers.change({currentTarget:select});await settle();let html=t.document.getElementById('app').innerHTML;assert.match(html,/Ebben a régióban még nincs keresési igény/);assert.match(html,/Somogy/);assert.doesNotMatch(html,/class="landing-search-card(?:\s[^"]*)?"|class="landing-property-card(?:\s[^"]*)?"/);await t.click({action:'landing-national'});html=t.document.getElementById('app').innerHTML;assert.match(html,/Országos válogatás/);assert.match(html,/class="landing-search-card(?:\s[^"]*)?"/);assert.equal(t.regionStorage.has('otthonra.landing.region'),false);
});
test('public API failure offers retry without substituting demo or erasing regional choices',async()=>{
 let requests=0;const t=await setup({hosted:true,hash:'',fetchLanding:async input=>{if(++requests===1)throw new Error('Átmeneti hálózati hiba.');return landingFixture(input.region)}});let html=t.document.getElementById('app').innerHTML;assert.match(html,/A válogatás most nem elérhető/);assert.doesNotMatch(html,/class="landing-search-card(?:\s[^"]*)?"|sidebar/);assert.equal(t.getSelectedModel(),null);await t.click({action:'landing-retry'});html=t.document.getElementById('app').innerHTML;assert.match(html,/class="landing-search-card(?:\s[^"]*)?"/);
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
  assert.match(t.document.getElementById('app').innerHTML,/owner-first-name">Hirdető/);assert.doesNotMatch(t.document.getElementById('app').innerHTML,/Anna <teszt>|Anna &lt;teszt&gt;/,'Unsafe identity strings are replaced with a neutral public name');
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
 for(const text of ['Kertes otthont keresünk','Napfényes erkélyes otthon','Anna','Péter','landing-ad-title','landing-type','owner-first-name'])assert.ok(html.includes(text),text);
 assert.doesNotMatch(html,/Lakást keresnek|Eladó lakás|lakást keres/);assert.match(html,/<h3 class="landing-ad-title">Kertes otthont keresünk<\/h3>/);
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
 for(let attempt=0;editorStep(t)<target&&attempt<6;attempt++){
  const before=editorStep(t);await editorAction(t,'editor-next');assert.equal(editorStep(t),before+1,'A valid step must advance exactly once');
 }
 assert.equal(editorStep(t),target);
}

test('search editor exposes named stages, validates the current topic and retains all mounted values when revisiting',async()=>{
 const t=await setup(),saved=[],save=t.model.saveEntity;t.model.saveEntity=(...args)=>{saved.push(args);return save(...args);};
 t.ui.openEditor('search');const form=t.document.getElementById('entity-form'),html=t.document.getElementById('modal-root').innerHTML;
 for(const label of ['Helyszín','Ingatlan típusa','Ár és méret','Ingatlanjellemzők','Kényelem és felszereltség','További elképzelések'])assert.ok(html.includes(label),label);
 assert.equal(editorStep(t),0);assert.equal(t.document.getElementById('editor-back').hidden,true);
 await editorAction(t,'editor-next');assert.equal(editorStep(t),0);assert.equal(t.document.activeElement.id,'location-input');
 assert.ok(t.document.getElementById('location-input').reportedValidity>0);assert.equal(saved.length,0);
 chooseLocation(t,'city:Debrecen');chooseLocation(t,'city:Hajdúszoboszló');
 await editorAction(t,'editor-next');assert.equal(editorStep(t),1);
 assert.equal(t.document.getElementById('editor-step-button-1').getAttribute('aria-current'),'step');
 assert.equal(t.document.getElementById('editor-step-button-0').getAttribute('data-editor-state'),'completed');
 chooseEditorType(t,'Lakás');assert.equal(editorStep(t),2);
 t.document.getElementById('f-maxPrice').value='125';t.document.getElementById('f-minArea').value='65';t.document.getElementById('f-minRooms').value='3';
 for(const name of ['minPrice','maxArea','maxRooms'])t.document.getElementById('f-'+name).value='';
 await editorAction(t,'editor-next');assert.equal(editorStep(t),3);
 editorChoice(t,'conditions','Jó').checked=true;editorChoice(t,'conditions','Új/felújított').checked=true;editorChoice(t,'buildings','Tégla').checked=true;
 await editorAction(t,'editor-next');assert.equal(editorStep(t),4);
 editorChoice(t,'heatingTypes','Hőszivattyú').checked=true;editorChoice(t,'floors','0').checked=true;t.document.getElementById('f-ceilingHeight').value='3 m feletti';
 await editorAction(t,'editor-next');assert.equal(editorStep(t),5);const title=t.document.getElementById('f-title');assert.match(title.value,/Debrecen/);assert.match(title.value,/125/);title.value='Megőrzött keresési elképzelés';title.handlers.input({target:title});t.document.getElementById('f-description').value='Fényes, csendes otthont szeretnénk.';
 await editorAction(t,'editor-back');assert.equal(editorStep(t),4);assert.equal(editorChoice(t,'heatingTypes','Hőszivattyú').checked,true);
 await editorAction(t,'editor-step-button-0');assert.equal(editorStep(t),0);
 assert.match(t.document.getElementById('location-chips').innerHTML,/Debrecen/);assert.match(t.document.getElementById('location-chips').innerHTML,/Hajdúszoboszló/);
 assert.equal(t.document.getElementById('f-title').value,'Megőrzött keresési elképzelés');assert.equal(t.document.getElementById('f-maxPrice').value,'125');
 assert.equal(editorChoice(t,'conditions','Új/felújított').checked,true);assert.equal(t.document.getElementById('f-description').value,'Fényes, csendes otthont szeretnénk.');
 assert.equal(t.document.getElementById('entity-form'),form,'Step navigation must preserve the mounted form');assert.equal(saved.length,0,'Navigation never saves a draft entity');
 await editorAction(t,'editor-step-button-5');assert.equal(editorStep(t),5);submitEditor(t);await settle();
 assert.equal(saved.length,1);const result=t.model.getState().searches.find(item=>item.title==='Megőrzött keresési elképzelés');assert.ok(result);
 assert.deepEqual([...result.locationIds],['city:Debrecen','city:Hajdúszoboszló']);assert.equal(result.maxPrice,125);assert.equal(result.minArea,65);assert.equal(result.minRooms,3);
 for(const name of ['minPrice','maxArea','maxRooms'])assert.equal(result[name],null);
 assert.deepEqual([...result.conditions],['Jó','Új/felújított']);assert.deepEqual([...result.heatingTypes],['Hőszivattyú']);assert.deepEqual([...result.floors],[0]);assert.equal(result.description,'Fényes, csendes otthont szeretnénk.');
 assert.match(t.document.getElementById('modal-root').innerHTML,/Ingatlanok felfedezése/);
});

test('seller wizard preserves required house plot, nullable amenities, image URLs and multiple parking choices through backtracking',async()=>{
 const t=await setup(),before=t.model.getState(),saved=[],save=t.model.saveEntity;t.model.saveEntity=(...args)=>{saved.push(args);return save(...args);};
 t.ui.openEditor('property');const html=t.document.getElementById('modal-root').innerHTML;
 for(const label of ['Helyszín','Ingatlan típusa','Ár és méret','Ingatlanjellemzők','Felszereltség','Képek és leírás'])assert.ok(html.includes(label),label);
 chooseLocation(t,'city:Solymár');t.document.getElementById('f-street').value='Teszt utca';t.document.getElementById('f-houseNumber').value='12/A';
 await editorAction(t,'editor-next');assert.equal(editorStep(t),1);chooseEditorType(t,'Ház');assert.equal(editorStep(t),2);
 for(const [name,value] of Object.entries({price:'110.5',area:'130.5',wholeRooms:'3',halfRooms:'1'}))t.document.getElementById('f-'+name).value=value;
 await editorAction(t,'editor-next');assert.equal(editorStep(t),2,'A house cannot advance without its plot');assert.equal(t.document.activeElement.id,'f-lotArea');
 t.document.getElementById('f-lotArea').value='720';await editorAction(t,'editor-next');assert.equal(editorStep(t),3);
 t.document.getElementById('f-condition').value='Jó';t.document.getElementById('f-building').value='Tégla';
 await editorAction(t,'editor-next');assert.equal(editorStep(t),4);
 for(const [name,value] of Object.entries({heatingType:'Hőszivattyú',insulated:'false',airConditioning:'true',solarPanels:''}))chooseOptionalCard(t,name,value);chooseEnergy(t,'energyRating','A+');
 editorChoice(t,'parkingTypes','Garázs').checked=true;editorChoice(t,'parkingTypes','Udvari beálló').checked=true;
 await editorAction(t,'editor-next');assert.equal(editorStep(t),5);
 const title=t.document.getElementById('f-title');assert.match(title.value,/Solymár/);assert.match(title.value,/Ház/);title.value='Lépésenként megőrzött családi ház';title.handlers.input({target:title});
 t.document.getElementById('property-images').value='https://example.test/elol.jpg\nhttps://example.test/kert.jpg';t.document.getElementById('f-description').value='Az eddig bevitt részletek maradjanak meg.';
 await editorAction(t,'editor-step-button-2');assert.equal(editorStep(t),2);assert.equal(t.document.getElementById('f-lotArea').value,'720');
 await editorAction(t,'editor-step-button-4');assert.equal(t.document.getElementById('f-insulated').value,'false');assert.equal(t.document.getElementById('f-solarPanels').value,'');assert.equal(editorChoice(t,'parkingTypes','Garázs').checked,true);
 await editorAction(t,'editor-step-button-5');assert.match(t.document.getElementById('property-images').value,/kert\.jpg/);assert.equal(saved.length,0);
 submitEditor(t);await settle();assert.equal(saved.length,1);
 const result=t.model.getState().properties.find(item=>item.title==='Lépésenként megőrzött családi ház');assert.ok(result);assert.equal(result.lotArea,720);assert.equal(result.insulated,false);assert.equal(result.airConditioning,true);assert.equal(result.solarPanels,null);assert.equal(result.wholeRooms,3);assert.equal(result.halfRooms,1);
 assert.deepEqual([...result.parkingTypes],['Udvari beálló','Garázs']);assert.deepEqual([...result.images],['https://example.test/elol.jpg','https://example.test/kert.jpg']);assert.equal(result.floor,null);assert.equal(result.balcony,null);assert.equal(result.elevator,false);
 assert.deepEqual(t.model.getState().active,before.active);
});

test('final wizard submission revisits an invalid earlier topic instead of silently saving hidden invalid controls',async()=>{
 const t=await setup(),calls=[],save=t.model.saveEntity;t.model.saveEntity=(...args)=>{calls.push(args);return save(...args);};
 t.ui.openEditor('search','own-s1');await advanceEditor(t,5);
 t.document.getElementById('f-maxPrice').value='';submitEditor(t);await settle();
 assert.equal(editorStep(t),2);assert.equal(t.document.activeElement.id,'f-maxPrice');assert.equal(calls.length,0);assert.equal(t.document.getElementById('f-maxPrice').hidden,false);
 t.document.getElementById('f-maxPrice').value='95';await advanceEditor(t,5);submitEditor(t);await settle();assert.equal(calls.length,1);assert.equal(t.model.getState().searches.find(item=>item.id==='own-s1').maxPrice,95);
 assert.equal(t.document.getElementById('modal-root').innerHTML,'','An edit does not open the new-search activation offer');
});

test('wizard range errors stay in the price and size topic and future-step clicks cannot bypass validation',async()=>{
 const t=await setup();t.ui.openEditor('search');
 await editorAction(t,'editor-step-button-5');assert.equal(editorStep(t),0,'A future topic cannot bypass missing required earlier details');assert.equal(t.document.activeElement.id,'location-input');
 chooseLocation(t,'city:Debrecen');await editorAction(t,'editor-next');chooseEditorType(t,'Lakás');assert.equal(editorStep(t),2);
 t.document.getElementById('f-minPrice').value='100';t.document.getElementById('f-maxPrice').value='80';await editorAction(t,'editor-next');assert.equal(editorStep(t),2);assert.ok(t.document.activeElement.validationMessage);
 t.document.getElementById('f-minPrice').value='';t.document.getElementById('f-minArea').value='40';await editorAction(t,'editor-next');assert.equal(editorStep(t),3);
 await editorAction(t,'editor-back');assert.equal(editorStep(t),2);assert.equal(t.document.getElementById('f-maxPrice').value,'80');
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
 t.ui.openEditor('search','own-s1');await advanceEditor(t,5);
 t.document.getElementById('f-description').value='Egyetlen mentésből létrejövő módosítás.';
 t.model.saveEntity=async(...args)=>{calls.push(args);await new Promise(resolve=>{release=resolve;});return save(...args);};
 submitEditor(t);await settle();assert.equal(calls.length,1);
 submitEditor(t);await editorAction(t,'editor-back');assert.equal(editorStep(t),5);assert.equal(calls.length,1);
 release();await settle();assert.equal(calls.length,1);assert.equal(t.document.getElementById('modal-root').innerHTML,'');
 assert.equal(t.model.getState().searches.find(item=>item.id==='own-s1').description,'Egyetlen mentésből létrejövő módosítás.');
});

test('editing a saved holiday-home property or search preserves its existing type throughout the wizard and final save',async()=>{
 let raw;const seed=createModel({getItem:()=>null,setItem:(_key,value)=>{raw=JSON.parse(value);}});seed.activate('search','own-s1');
 raw.properties.find(item=>item.id==='own-p1').type='Nyaraló';raw.searches.find(item=>item.id==='own-s1').type='Nyaraló';
 for(const kind of ['property','search']){
  const t=await setup({initialRaw:raw}),id=kind==='property'?'own-p1':'own-s1';
  t.ui.openEditor(kind,id);const type=t.document.getElementById('f-type');assert.equal(type.value,'Nyaraló','A saved type outside the creation choices must remain selected');
  await advanceEditor(t,5);await editorAction(t,'editor-step-button-0');assert.equal(t.document.getElementById('f-type'),type);assert.equal(type.value,'Nyaraló');
  await editorAction(t,'editor-step-button-5');submitEditor(t);await settle();
  const collection=kind==='property'?t.model.getState().properties:t.model.getState().searches;
  assert.equal(collection.find(item=>item.id===id).type,'Nyaraló','Saving unrelated edits must not silently convert a holiday home into a flat');
  assert.equal(t.document.getElementById('modal-root').innerHTML,'');
 }
});


test('modal focus chooses the first visible enabled field before progress buttons and ignores closed or replaced modal timers',async()=>{
 const t=await setup({captureTimers:true});t.ui.openEditor('search');
 assert.equal(t.document.querySelector('.modal input,.modal select,.modal button,.modal textarea').id,'editor-step-button-0','The left progress menu precedes the form fields in DOM order');
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
  assert.equal(t.document.getElementById('editor-step-status'),null,'The step count is represented by the named step menu, without a redundant sentence');
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
 for(const [key,values] of Object.entries({conditions:['Átlagos','Jó'],buildings:['Tégla','Panel'],constructionAges:['10 évnél fiatalabb','31–40 év közötti'],views:['Kertre néző','Panorámás'],heatingTypes:['Hőszivattyú','Fűtő klíma'],floors:['Szuterén','Földszint','9']}))for(const value of values)assert.ok(criteriaRow(t,key).text.includes(value),`${key} must show ${value}`);
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
 for(const [key,value] of Object.entries({condition:'Átlagos',building:'Tégla',constructionAge:'31–40 év közötti',view:'Udvari',ceilingHeight:'3 m feletti',heatingType:'Nincs fűtés',energyRating:'BB'}))assert.equal(criteriaRow(t,key).text,value);
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
  await t.click({action:'active-criteria-summary'});await t.click({action:'edit-criteria',kind,id});await advanceEditor(t,5);t.document.getElementById('f-description').value='Csak a leírást módosítom, a meglévő adatok megmaradnak.';submitEditor(t);await settle();
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
 draft=onboardingHelpers.updateDraft(draft,{step:5});
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
 await t.click({action:'onboarding-start',kind:'search',source:source.key});await advanceEditor(t,5);
 const title=t.document.getElementById('f-title');title.value='Saját megőrzött keresésem';title.handlers.input({target:title});t.document.getElementById('entity-form').handlers.input({target:title});
 await editorAction(t,'editor-step-button-2');const price=t.document.getElementById('f-maxPrice');price.value='123';t.document.getElementById('entity-form').handlers.input({target:price});
 await t.click({action:'landing'});const before=storedOnboarding(t);assert.equal(before.step,2);
 source={...source,key:'property-new-slot',price:199,prefill:{...source.prefill,price:199}};
 await t.click({action:'landing-retry'});await t.click({action:'onboarding-start',kind:'search',source:source.key});
 const resumed=storedOnboarding(t);assert.equal(resumed.id,before.id);assert.equal(resumed.creationRequestId,before.creationRequestId);assert.equal(editorStep(t),2);assert.equal(t.document.getElementById('f-maxPrice').value,'123');assert.equal(t.document.getElementById('f-title').value,'Saját megőrzött keresésem');assert.equal(t.document.getElementById('modal-root').innerHTML,'');
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
   assert.equal(type.value,'');assert.equal(type.type,'hidden');assert.equal(type.tagName,'INPUT');assert.doesNotMatch(t.document.html,/<select[^>]*id="f-type"/);
   for(const value of ['Lakás','Ház','Telek','Üzlethelyiség'])assert.equal(propertyTypeCard(t,value).getAttribute('aria-pressed'),'false');
   assert.equal(title.parentElement.id,'editor-step-5','The optional name belongs to the final topic');assert.equal(title.required,false);
   for(const name of kind==='property'?['price','area','wholeRooms','halfRooms']:['minPrice','maxPrice','minArea','maxArea','minRooms','maxRooms'])assert.equal(t.document.getElementById('f-'+name).value,'',`${guest?'guest':'private'} ${kind} ${name}`);
   if(kind==='property')assert.equal(t.document.getElementById('f-halfRooms').required,false,'An absent half-room count must not force a meaningless zero entry');
  }
 }
});

test('new private search gets a short final name and clearing a customized name restores an automatic title',async()=>{
 const t=await setup();t.ui.openEditor('search');chooseLocation(t,'city:Debrecen');
 const type=t.document.getElementById('f-type');type.value='Lakás';type.handlers.change({target:type});
 const price=t.document.getElementById('f-maxPrice'),area=t.document.getElementById('f-minArea');price.value='80';area.value='50';
 await advanceEditor(t,5);const title=t.document.getElementById('f-title');assert.match(title.value,/Lakás/);assert.match(title.value,/Debrecen/);assert.match(title.value,/80/);assert.ok(title.value.length<=70);
 title.value='Egyéni név';title.handlers.input({target:title});await editorAction(t,'editor-step-button-2');price.value='95';price.handlers.input({target:price});await editorAction(t,'editor-step-button-5');assert.equal(title.value,'Egyéni név');
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
 const replacement=storedOnboarding(t);await advanceEditor(t,5);
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
  await t.click({action:'landing'});await t.click({action:'onboarding-start',kind:'search',source:second.key});const replacement=storedOnboarding(t);await advanceEditor(t,5);await submitEditor(t);assert.equal(t.ctx.location.hash,'#register');
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


function toggleSelectedPlaces(t,chips){
 const target={dataset:{locationSelectionToggle:''},closest:selector=>selector==='[data-location-selection-toggle]'?target:null};
 chips.handlers.click({target});
}
function removeSelectedPlace(chips,id){
 const target={dataset:{removeLocation:id},closest:selector=>selector==='[data-remove-location]'?target:null};
 chips.handlers.click({target});
}

test('mobile landing selections keep all removable IDs behind a truthful compact summary',async()=>{
 const t=await setup({hosted:true,hash:'#landing',mockMaps:true,mobile:true});await settle();
 const chips=t.document.getElementById('landing-location-chips'),map=activeMap(t,'landing-location-map');
 assert.ok(chips.classList.contains('compact-location-chips'));assert.equal(chips.innerHTML,'');
 const ids=['city:Debrecen','city:Solymár','city:Szeged','city:Pilisvörösvár'];
 for(const id of ids)assert.equal(map.select(id),true);
 assert.match(chips.innerHTML,/<span class="location-selection-names">Debrecen<\/span>/);
 assert.match(chips.innerHTML,/>\+ 3 helyszín<\/span>/);
 assert.equal((chips.innerHTML.match(/data-remove-location=/g)||[]).length,4,'Overflow does not discard hidden canonical selections');
 const toggle=t.document.getElementById('landing-location-chips-toggle');
 assert.equal(toggle.getAttribute('aria-expanded'),'false');toggleSelectedPlaces(t,chips);
 assert.equal(toggle.getAttribute('aria-expanded'),'true');assert.ok(chips.classList.contains('is-expanded'));
 const escape=key(chips,'Escape');assert.equal(escape.defaultPrevented,true);
 assert.equal(toggle.getAttribute('aria-expanded'),'false');assert.equal(t.document.activeElement,toggle);
 toggleSelectedPlaces(t,chips);removeSelectedPlace(chips,'city:Solymár');
 assert.deepEqual(map.ids,['city:Debrecen','city:Szeged','city:Pilisvörösvár']);
 assert.match(chips.innerHTML,/>\+ 2 helyszín<\/span>/);assert.ok(chips.classList.contains('is-expanded'));
 assert.equal(t.document.activeElement.id,'landing-location-chips-toggle','Removing an overflow item must not open the mobile keyboard');
 const outside=t.document.getElementById('landing-location-map');outside.closest=()=>null;await t.document.handlers.pointerdown({target:outside});
 assert.equal(t.document.getElementById('landing-location-chips-toggle').getAttribute('aria-expanded'),'false');
 for(const id of [...map.ids])removeSelectedPlace(chips,id);
 assert.equal(chips.innerHTML,'');assert.equal(t.document.activeElement,chips);
});

test('mobile owned and guest search summaries preserve draft selections and local editor state',async()=>{
 for(const guest of [false,true]){
  const t=await setup({hosted:guest,hash:guest?'#landing':'',mockMaps:true,mobile:true});await settle();
  if(guest)t.ui.startOnboarding('search',null,[]);else t.ui.openEditor('search');await settle();
  const chips=t.document.getElementById('location-chips'),map=activeMap(t,'search-location-map'),input=t.document.getElementById('location-input');
  assert.ok(chips.classList.contains('compact-location-chips'));
  for(const id of ['city:Debrecen','city:Solymár','city:Szeged'])assert.equal(map.select(id),true);
  input.value='megőrzött lekérdezés';toggleSelectedPlaces(t,chips);removeSelectedPlace(chips,'city:Debrecen');
  assert.equal(input.value,'megőrzött lekérdezés');assert.deepEqual(map.ids,['city:Solymár','city:Szeged']);
  assert.equal(t.document.activeElement.id,'location-chips-toggle');assert.ok(chips.classList.contains('is-expanded'));
  if(guest)assert.deepEqual(storedOnboarding(t).data.locationIds,['city:Solymár','city:Szeged']);
  const escaped=key(chips,'Escape');assert.equal(escaped.defaultPrevented,true);assert.equal(chips.classList.contains('is-expanded'),false);
  assert.ok(t.document.getElementById('entity-form'),'Closing selected places must not close the wizard');
 }
});

test('responsive search workspaces retain the exact property location form unchanged',async()=>{
 const t=await setup({mockMaps:true});t.ui.openEditor('search');await settle();
 assert.ok(t.document.getElementById('location-picker').classList.contains('location-search-layout'));
 assert.match(t.document.getElementById('modal-root').innerHTML,/class="location-search-controls"/);
 t.ui.openEditor('property');await settle();
 assert.equal(t.document.getElementById('location-picker').classList.contains('location-search-layout'),false);
 assert.equal(t.document.getElementById('location-chips').classList.contains('compact-location-chips'),false);
 assert.equal(t.document.getElementById('search-location-map'),null);
 assert.ok(t.document.getElementById('f-street'));assert.ok(t.document.getElementById('f-houseNumber'));
});


test('location-only first steps require an illustrated type choice and explicit Next without saving',async()=>{
 for(const kind of ['search','property'])for(const guest of [false,true]){
  const draft=onboardingHelpers.createDraft(kind,{}, {editor:{titleGenerated:true}});
  const t=await setup(guest?{hosted:true,captureTimers:true,hash:'#onboarding',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(draft)}}:{});
  if(!guest)t.ui.openEditor(kind);
  let writes=0;const save=t.model?.saveEntity;if(save)t.model.saveEntity=(...args)=>{writes++;return save(...args);};
  const first=t.document.getElementById('editor-step-0'),typeTopic=t.document.getElementById('editor-step-1'),group=t.document.getElementById('property-type-options'),form=t.document.getElementById('entity-form');
  assert.equal(first.contains(group),false,'The first screen contains no property-type choices');assert.equal(typeTopic.contains(group),true);
  assert.equal(first.contains(t.document.getElementById('location-input')),true);
  if(kind==='property')for(const name of ['street','houseNumber','postalCode'])assert.equal(first.contains(t.document.getElementById('f-'+name)),true);
  if(guest){const input=t.document.getElementById('location-input');input.value='Debrecen';input.handlers.input();const lookup=t.timers.findLast(timer=>timer.delay===200);assert.ok(lookup,'The guest picker schedules its bounded lookup');await lookup.callback();await settle();assert.match(t.document.getElementById('location-options').innerHTML,/data-location-id="city:Debrecen"/,kind+' guest suggestions');const target={dataset:{locationId:'city:Debrecen'},closest:()=>target};t.document.getElementById('location-options').handlers.click({target});}
  else chooseLocation(t,'city:Debrecen');
  if(kind==='property'){t.document.getElementById('f-street').value='Teszt utca';t.document.getElementById('f-houseNumber').value='12';}
  await editorAction(t,'editor-next');assert.equal(editorStep(t),1,`${kind}/${guest?'guest':'owned'}: A valid location advances without a type being selected (${t.document.getElementById('location-input').value}; ${t.document.getElementById('location-error').textContent})`);
  assert.equal(t.document.getElementById('f-type').value,'');assert.equal(t.document.getElementById('editor-save').hidden,true);
  for(const value of ['Lakás','Ház','Telek','Üzlethelyiség']){
   const card=propertyTypeCard(t,value);assert.equal(card.type,'button');assert.equal(card.getAttribute('aria-pressed'),'false');
  }
  assert.equal((t.document.html.match(/class="property-type-illustration"/g)||[]).length,4,'Each type has its own illustrated choice');
  await editorAction(t,'editor-next');assert.equal(editorStep(t),1,'The type step cannot be bypassed without a choice');assert.equal(t.document.getElementById('property-type-error').hidden,false);assert.equal(t.document.activeElement,propertyTypeCard(t,'Lakás'));
  selectEditorType(t,'Lakás');assert.equal(editorStep(t),1,'A type-card click only selects its value');await editorAction(t,'editor-next');assert.equal(editorStep(t),2,'Explicit Next advances to price and size');assert.equal(t.document.getElementById('f-type').value,'Lakás');assert.equal(propertyTypeCard(t,'Lakás').getAttribute('aria-pressed'),'true');assert.equal(writes,0);
  const price=t.document.getElementById(kind==='property'?'f-price':'f-maxPrice');price.value='83';
  await editorAction(t,'editor-back');assert.equal(editorStep(t),1);selectEditorType(t,'Lakás');assert.equal(editorStep(t),1,'Clicking the already selected required type preserves it without navigating');await editorAction(t,'editor-next');assert.equal(editorStep(t),2);assert.equal(price.value,'83');assert.equal(t.document.getElementById('entity-form'),form);assert.equal(writes,0);
  await editorAction(t,'editor-back');chooseEditorType(t,'Ház');assert.equal(editorStep(t),2);assert.equal(t.document.getElementById('f-type').value,'Ház');assert.equal(propertyTypeCard(t,'Lakás').getAttribute('aria-pressed'),'false');
  if(kind==='property')assert.equal(t.document.getElementById('f-lotArea').required,true);else assert.equal(t.document.getElementById('floors-group').disabled,true);
  assert.equal(price.value,'83');assert.equal(writes,0);
  if(guest){const saved=storedOnboarding(t);assert.equal(saved.data.type,'Ház');assert.equal(saved.step,2);assert.equal(saved.editor.layoutVersion,2);assert.equal(saved.phase,'editing');}
 }
});

test('restored and owned preselected types remain on their topic until explicit Next',async()=>{
 for(const kind of ['search','property']){
  const draft=onboardingHelpers.updateDraft(onboardingHelpers.createDraft(kind,{type:'Ház',locationIds:['city:Debrecen'],locationId:'city:Debrecen',street:'Teszt utca',houseNumber:'12'},{editor:{locations:[getLocation('city:Debrecen')],titleGenerated:true}}),{step:1});
  const guest=await setup({hosted:true,hash:'#onboarding',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(draft)}});
  assert.equal(editorStep(guest),1);assert.equal(propertyTypeCard(guest,'Ház').getAttribute('aria-pressed'),'true');assert.equal(storedOnboarding(guest).step,1);selectEditorType(guest,'Ház');assert.equal(storedOnboarding(guest).step,1);await editorAction(guest,'editor-next');assert.equal(editorStep(guest),2);
  const owned=await setup();owned.ui.openEditor(kind,kind==='property'?'own-p1':'own-s1');assert.equal(editorStep(owned),0);await editorAction(owned,'editor-next');assert.equal(editorStep(owned),1,'Opening or restoring a selected type is never an implicit navigation');
  const savedType=owned.document.getElementById('f-type').value;assert.equal(propertyTypeCard(owned,savedType).getAttribute('aria-pressed'),'true');chooseEditorType(owned,savedType);assert.equal(editorStep(owned),2);
 }
});

test('the mounted guest editor migrates legacy five-step storage once and persists edits through its equality fence',async()=>{
 const origin=onboardingHelpers.originFromListing('property',publicSourceKey('property','f'));
 const legacy=onboardingHelpers.createDraft('search',{title:'Régi, saját keresésem',type:'Lakás',locationIds:['city:Debrecen'],maxPrice:'89.5',minArea:'45',description:'Régi szabad szöveg'},{origin,editor:{locations:[getLocation('city:Debrecen')],query:'Csapó',titleGenerated:false,completedSteps:[0,1,2,3]}});
 delete legacy.editor.layoutVersion;legacy.step=4;
 const t=await setup({hosted:true,hash:'#onboarding',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(legacy)}});
 assert.equal(editorStep(t),5,'An old final topic restores at the new final topic, not the amenities screen');
 const field=t.document.getElementById('f-description');field.value='Az új felületen folytatott leírás';t.document.getElementById('entity-form').handlers.input({target:field});
 const saved=storedOnboarding(t);assert.equal(saved.id,legacy.id);assert.equal(saved.creationRequestId,legacy.creationRequestId);assert.deepEqual(saved.origin,origin);assert.equal(saved.editor.layoutVersion,2);assert.equal(saved.step,5);assert.equal(saved.editor.query,'Csapó');assert.equal(saved.data.description,field.value);assert.equal(saved.data.maxPrice,'89.5');assert.equal(saved.data.title,'Régi, saját keresésem');
 assert.deepEqual(saved.editor.completedSteps,[0,1,2,3,4]);
 await t.click({action:'landing'});t.ctx.location.hash='#onboarding';await t.ui.render();assert.equal(editorStep(t),5);assert.equal(t.document.getElementById('f-description').value,field.value);assert.equal(storedOnboarding(t).editor.layoutVersion,2);
});


function illustratedAttribute(t,name,index){const button=t.document.getElementById(`attribute-${name}-${index}`);assert.ok(button,`Missing illustrated ${name} option ${index}`);return button;}
function clickIllustrated(t,name,index){const button=illustratedAttribute(t,name,index);button.handlers.click({target:button,currentTarget:button,preventDefault(){}});return button;}
function changeChoice(t,input,checked){input.checked=checked;const event={target:input,currentTarget:input};input.handlers.change?.(event);t.document.getElementById('entity-form').handlers.change?.(event);}

test('optional illustrated seller attributes toggle off, retain other fields and keep help separate from selection',async()=>{
 const t=await setup(),listeners=Object.fromEntries(['pointerdown','focusin','keydown'].map(type=>[type,t.document.listenerCount(type)]));t.ui.openEditor('property','own-p1');await advanceEditor(t,3);
 const form=t.document.getElementById('entity-form'),title=t.document.getElementById('f-title'),originalTitle=title.value;let writes=0;t.model.saveEntity=()=>{writes++;};
 for(const name of ['condition','view','building','ceilingHeight']){
  const input=t.document.getElementById('f-'+name);assert.equal(input.type,'hidden');
  if(input.value){const matching=[0,1,2,3,4,5,6,7,8,9,10,11].map(index=>t.document.getElementById(`attribute-${name}-${index}`)).find(button=>button?.getAttribute('data-attribute-value')===input.value);assert.ok(matching);matching.handlers.click({target:matching,currentTarget:matching,preventDefault(){}});assert.equal(input.value,'');}
  const button=clickIllustrated(t,name,0),value=button.getAttribute('data-attribute-value');assert.equal(input.value,value);assert.equal(button.getAttribute('aria-pressed'),'true');assert.equal(editorStep(t),3);
  clickIllustrated(t,name,0);assert.equal(input.value,'','Clicking a selected optional single choice removes it');assert.equal(button.getAttribute('aria-pressed'),'false');assert.equal(editorStep(t),3);
  clickIllustrated(t,name,1);assert.equal(input.value,illustratedAttribute(t,name,1).getAttribute('data-attribute-value'));
 }
 const building=t.document.getElementById('f-building'),before=building.value,help=t.document.getElementById('building-help-property-0');assert.ok(help);help.handlers.click({target:help,currentTarget:help,preventDefault(){},stopPropagation(){}});
 assert.equal(t.document.getElementById('building-help-panel').hidden,false);assert.equal(help.getAttribute('aria-expanded'),'true');assert.equal(building.value,before);assert.equal(t.document.getElementById('entity-form'),form);assert.equal(editorStep(t),3);assert.equal(writes,0);
 await editorAction(t,'building-help-close');assert.equal(t.document.getElementById('building-help-panel').hidden,true);assert.equal(building.value,before);assert.equal(title.value,originalTitle);
 await editorAction(t,'editor-step-button-2');await editorAction(t,'editor-step-button-3');assert.equal(building.value,before);assert.equal(writes,0);
 await t.click({action:'close'});for(const [type,count] of Object.entries(listeners))assert.equal(t.document.listenerCount(type),count,`${type} help listeners are cleaned up when the editor closes`);
 const legacy=onboardingHelpers.updateDraft(onboardingHelpers.createDraft('property',{type:'Lakás',locationId:'city:Debrecen',street:'Teszt utca',houseNumber:'12',price:'85',area:'60',wholeRooms:'2',condition:'Felújított',building:'Vert fal'},{editor:{locations:[getLocation('city:Debrecen')],titleGenerated:true}}),{step:3});
 const guest=await setup({hosted:true,hash:'#onboarding',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(legacy)}}),condition=guest.document.getElementById('f-condition'),unknownBuilding=illustratedAttribute(guest,'building',propertyAttributes.BUILDING_OPTIONS.length);
 assert.equal(condition.value,'Felújított','Restoring a raw legacy draft keeps its saved text until an explicit edit');
 assert.equal(illustratedAttribute(guest,'condition',3).getAttribute('aria-pressed'),'true','The known legacy alias highlights its canonical illustrated option');
 assert.equal(unknownBuilding.getAttribute('data-attribute-value'),'Vert fal');assert.equal(unknownBuilding.getAttribute('aria-pressed'),'true','An unknown legacy wall value stays selected on its extra choice');
 clickIllustrated(guest,'condition',3);assert.equal(condition.value,'','One click clears an already-selected known alias');assert.equal(illustratedAttribute(guest,'condition',3).getAttribute('aria-pressed'),'false');assert.equal(storedOnboarding(guest).data.condition,'');assert.equal(storedOnboarding(guest).data.building,'Vert fal');assert.equal(editorStep(guest),3);
 await guest.click({action:'landing'});guest.ctx.location.hash='#onboarding';await guest.ui.render();assert.equal(guest.document.getElementById('f-condition').value,'');assert.equal(guest.document.getElementById('f-building').value,'Vert fal');assert.equal(illustratedAttribute(guest,'building',propertyAttributes.BUILDING_OPTIONS.length).getAttribute('aria-pressed'),'true');
});

test('guest illustrated search choices remain independent and persist explicit clearing without advancing',async()=>{
 const draft=onboardingHelpers.updateDraft(onboardingHelpers.createDraft('search',{type:'Lakás',locationIds:['city:Debrecen'],maxPrice:90,minArea:40},{editor:{locations:[getLocation('city:Debrecen')],titleGenerated:true}}),{step:3});
 const t=await setup({hosted:true,hash:'#onboarding',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(draft)}}),form=t.document.getElementById('entity-form');
 for(const [name,values] of [['conditions',propertyAttributes.CONDITION_OPTIONS],['views',propertyAttributes.VIEW_OPTIONS],['buildings',propertyAttributes.BUILDING_OPTIONS]]){
  const first=editorChoice(t,name,values[0]),second=editorChoice(t,name,values[1]);changeChoice(t,first,true);changeChoice(t,second,true);changeChoice(t,first,false);
  assert.deepEqual(storedOnboarding(t).data[name],[values[1]]);assert.equal(second.checked,true);assert.equal(editorStep(t),3);assert.equal(t.document.getElementById('entity-form'),form);
 }
 const ceiling=t.document.getElementById('f-ceilingHeight');clickIllustrated(t,'ceilingHeight',0);assert.ok(ceiling.value);clickIllustrated(t,'ceilingHeight',0);assert.equal(ceiling.value,'');assert.equal(storedOnboarding(t).data.ceilingHeight,'');
 const selected=storedOnboarding(t).data.buildings,help=t.document.getElementById('building-help-search-0');help.handlers.click({target:help,currentTarget:help,preventDefault(){},stopPropagation(){}});assert.equal(t.document.getElementById('building-help-panel').hidden,false);assert.deepEqual(storedOnboarding(t).data.buildings,selected);await editorAction(t,'building-help-close');
 await t.click({action:'landing'});t.ctx.location.hash='#onboarding';await t.ui.render();assert.equal(editorStep(t),3);assert.equal(editorChoice(t,'buildings',propertyAttributes.BUILDING_OPTIONS[1]).checked,true);assert.equal(editorChoice(t,'buildings',propertyAttributes.BUILDING_OPTIONS[0]).checked,false);assert.equal(t.document.getElementById('f-ceilingHeight').value,'');
});

test('the responsive step menu owns only named progress controls and the reordered attributes keep floor and lift together',async()=>{
 for(const kind of ['property','search'])for(const guest of [false,true]){
  const draft=onboardingHelpers.createDraft(kind,{type:'Lakás',locationIds:['city:Debrecen'],locationId:'city:Debrecen',street:'Teszt utca',houseNumber:'1',maxPrice:90,minArea:40},{editor:{locations:[getLocation('city:Debrecen')],titleGenerated:true}});
  const t=await setup(guest?{hosted:true,hash:'#onboarding',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(draft)}}:{});if(!guest)t.ui.openEditor(kind,kind==='property'?'own-p1':'own-s1');const nav=t.document.getElementById('editor-navigation'),form=t.document.getElementById('entity-form');assert.ok(nav);
  for(const id of Array.from({length:6},(_unused,index)=>`editor-step-button-${index}`))assert.equal(nav.contains(t.document.getElementById(id)),true,`${id} belongs to the common responsive step menu`);
  for(const id of ['editor-next','editor-back','editor-save','editor-next-top','editor-back-top','editor-save-top']){const action=t.document.getElementById(id);assert.ok(action,id);assert.equal(nav.contains(action),false,'Actions belong to the content, separate from the responsive step menu');assert.equal(form.contains(action),true);}
  assert.equal(form.contains(nav),true);assert.ok(t.document.html.indexOf('id="editor-navigation"')<t.document.html.indexOf('id="editor-step-0"'),'The named step navigation remains separate from the mounted content');
  const content=t.document.getElementById('editor-content'),header=t.document.getElementById('editor-header');assert.ok(content);assert.ok(header);assert.equal(content.contains(header),true,'The main title belongs to the form content rather than appearing over the step navigation');assert.equal(nav.contains(header),false);assert.equal(form.contains(header),true);
  assert.doesNotMatch(t.document.html,/<div class="eyebrow">(?:Keresési igény|Eladó ingatlan)<\/div>|Csak azt jelöld meg, ami fontos/);
  const bounds=t.document.getElementById('editor-step-2');for(const [id,label] of [['editor-price-heading','Ár'],['editor-size-heading','Méret']]){const heading=t.document.getElementById(id);assert.ok(heading);assert.equal(heading.tagName,'H3');assert.equal(bounds.contains(heading),true);assert.ok(t.document.html.includes(`id="${id}"`));assert.match(t.document.html,new RegExp(`<h3\\b[^>]*id="${id}"[^>]*>${label}<\\/h3>`));}
  const positionsInBounds=['editor-price-heading',kind==='property'?'f-price':'f-maxPrice','editor-size-heading',kind==='property'?'f-area':'f-minArea'].map(id=>t.document.html.indexOf(`id="${id}"`));assert.deepEqual(positionsInBounds,[...positionsInBounds].sort((left,right)=>left-right),'Price and size headings precede their existing editable fields');
  for(const index of [2,3]){const anchor=t.document.getElementById(`editor-heading-${index}`);assert.ok(anchor,'Accessible topic labels remain available for navigation and validation focus');assert.equal(t.document.getElementById('editor-step-'+index).getAttribute('aria-labelledby'),anchor.id);}
  const ids=kind==='property'?['f-condition','f-floor','f-elevator','f-constructionAge','f-view','f-building','f-ceilingHeight']:['conditions-group','floors-group','f-elevator','constructionAges-group','views-group','buildings-group','f-ceilingHeight'];
  const section=t.document.getElementById('editor-step-3');for(const id of ids)assert.equal(section.contains(t.document.getElementById(id)),true,`${id} belongs to the attribute topic`);
  const positions=ids.map(id=>t.document.html.indexOf(`id="${id}"`));assert.deepEqual(positions,[...positions].sort((left,right)=>left-right),'The attributes follow condition, floor/lift, age, view, wall and ceiling order');
  const floorGroup=t.document.getElementById(kind==='property'?'property-floor-field':'floors-group');assert.equal(floorGroup.contains(t.document.getElementById('f-elevator')),true);
 }
});

test('floor exclusions, raised ground floors and legacy exact upper floors survive actual owner saves',async()=>{
 const raw=configuredCriteriaRaw('property');Object.assign(raw.properties.find(item=>item.id==='own-p1'),{floor:12,buildingFloors:12,floorIsUpperRange:false});
 const t=await setup({initialRaw:raw});t.ui.openEditor('property','own-p1');const form=t.document.getElementById('entity-form');
 const floor=t.document.getElementById('f-floor'),floorCards=t.document.getElementById('entity-form').querySelectorAll('button').filter(button=>button.dataset.buildingNumber==='floor');
 assert.equal(floor.type,'hidden');assert.deepEqual(floorCards.map(button=>button.dataset.buildingNumberValue),['-1','0','0.5','1','2','3','4','5','6','7','8','9','10','other']);
 assert.equal(floor.value,'12','An existing exact upper floor remains available through the Other control');assert.equal(t.document.getElementById('f-floorOther').value,'12');
 const buildingFloors=t.document.getElementById('f-buildingFloors'),buildingOther=t.document.getElementById('f-buildingFloorsOther');assert.equal(buildingFloors.type,'hidden');assert.equal(buildingOther.type,'number');assert.equal(buildingOther.getAttribute('min'),'11');assert.equal(buildingOther.getAttribute('max'),'200');assert.equal(buildingOther.step,'1');assert.equal(buildingOther.required,true);
 await advanceEditor(t,5);submitEditor(t);await settle();let property=t.model.getState().properties.find(item=>item.id==='own-p1');assert.equal(property.floor,12);assert.equal(property.floorIsUpperRange,false);assert.equal(property.buildingFloors,12,'Opening and saving an old profile must preserve the exact floor used for top-floor checks');
 t.ui.openEditor('property','own-p1');await advanceEditor(t,3);chooseOptionalCard(t,'floor',9);await advanceEditor(t,5);submitEditor(t);await settle();property=t.model.getState().properties.find(item=>item.id==='own-p1');assert.equal(property.floor,9);assert.equal(property.floorIsUpperRange,false,'Selecting the numbered card means the exact ninth floor');
 t.ui.openEditor('property','own-p1');await advanceEditor(t,3);chooseOptionalCard(t,'floor',.5);chooseOptionalCard(t,'buildingFloors',0);await advanceEditor(t,4);chooseOptionalCard(t,'privateGarden',false);assert.equal(t.document.getElementById('f-sharedGarden'),null);
 await advanceEditor(t,5);submitEditor(t);await settle();property=t.model.getState().properties.find(item=>item.id==='own-p1');assert.equal(property.floor,.5);assert.equal(property.floorIsUpperRange,false);assert.equal(property.buildingFloors,0);assert.equal(property.privateGarden,false);assert.equal(property.sharedGarden,null);
 t.ui.openEditor('property','own-p1');assert.equal(t.document.getElementById('f-floor').value,'0.5');assert.equal(t.document.getElementById('f-buildingFloors').value,'0');assert.equal(t.document.getElementById('f-privateGarden').value,'false');
 await advanceEditor(t,3);chooseOptionalCard(t,'buildingFloors',null);await advanceEditor(t,4);chooseOptionalCard(t,'privateGarden',null);await advanceEditor(t,5);submitEditor(t);await settle();property=t.model.getState().properties.find(item=>item.id==='own-p1');for(const key of ['buildingFloors','privateGarden','sharedGarden'])assert.equal(property[key],null,`${key} remains unknown when cleared`);
 t.ui.openEditor('search','own-s1');for(const id of ['f-excludeTopFloor','f-excludeGroundFloorAndBelow','f-airConditioning','f-privateGarden'])changeChoice(t,t.document.getElementById(id),true);
 await advanceEditor(t,5);submitEditor(t);await settle();let search=t.model.getState().searches.find(item=>item.id==='own-s1');for(const key of ['excludeTopFloor','excludeGroundFloorAndBelow','airConditioning','privateGarden'])assert.equal(search[key],true,key);assert.equal(search.sharedGarden,false);
 t.ui.openEditor('search','own-s1');for(const id of ['f-excludeTopFloor','f-excludeGroundFloorAndBelow','f-airConditioning','f-privateGarden']){assert.equal(t.document.getElementById(id).checked,true);changeChoice(t,t.document.getElementById(id),false);}
 await advanceEditor(t,5);submitEditor(t);await settle();search=t.model.getState().searches.find(item=>item.id==='own-s1');for(const key of ['excludeTopFloor','excludeGroundFloorAndBelow','airConditioning','privateGarden','sharedGarden'])assert.equal(search[key],false,key);
 assert.notEqual(t.document.getElementById('entity-form'),form);
});

test('garden controls apply only to flats while air conditioning remains available on other search types',async()=>{
 for(const kind of ['property','search'])for(const type of ['Lakás','Ház','Telek','Üzlethelyiség']){
  const t=await setup();t.ui.openEditor(kind,kind==='property'?'own-p1':'own-s1');
  if(kind==='property')t.document.getElementById('f-privateGarden').value='true';else changeChoice(t,t.document.getElementById('f-privateGarden'),true);assert.equal(t.document.getElementById('f-sharedGarden'),null);
  chooseEditorType(t,type);if(kind==='property'&&type==='Ház')t.document.getElementById('f-lotArea').value='650';await advanceEditor(t,4);
  const applicable=type==='Lakás',group=t.document.getElementById('entity-gardens');assert.equal(group.offsetParent!==null,applicable);
  assert.equal(t.document.getElementById('f-privateGarden').disabled,!applicable);
  if(kind==='search')assert.equal(t.document.getElementById('f-airConditioning').disabled,false);
  if(type==='Ház'){await advanceEditor(t,5);submitEditor(t);await settle();const saved=t.model.getState()[kind==='property'?'properties':'searches'].find(item=>item.id===(kind==='property'?'own-p1':'own-s1'));for(const name of ['privateGarden','sharedGarden'])assert.equal(saved[name],kind==='property'?null:false,'Hidden flat-specific intent cannot leak into a saved house');}
 }
});


test('a late same-session save receipt leaves the saving screen after another tab has cleared their shared draft',async()=>{
 for(const deliverStorageEvent of [false,true]){
  const data={title:'Két fülből ugyanazzal a nyugtával mentett keresés',type:'Lakás',locationIds:['city:Debrecen'],maxPrice:90,minArea:40,minRooms:null};
  const account=createModel({getItem:()=>null,setItem:()=>{}}).getState().user;
  const draft=onboardingHelpers.prepareDraftSave(onboardingHelpers.prepareDraftForAuth(onboardingHelpers.createDraft('search',data),account.email),account);
  const sharedStorage=new Map([[onboardingHelpers.DRAFT_STORAGE_KEY,JSON.stringify(draft)],['otthonra.api','same-auth-session']]),requests=[];
  let releaseFirst,releaseSecond,secondDocument,secondWindowEvents;
  const secondPending=setup({hosted:true,authenticated:true,hash:'#register',regionStorage:sharedStorage,onDocument:(document,events)=>{secondDocument=document;secondWindowEvents=events;},apiOverrides:{saveEntity:async(kind,payload,id,options)=>{requests.push({tab:'second',receipt:options.creationRequestId});return await new Promise(resolve=>{releaseSecond=()=>resolve({id:'shared-receipt-search',...payload});});}}});
  await settle();assert.equal(typeof releaseSecond,'function','The second tab has its keyed POST in flight before the first tab finishes');
  const firstPending=setup({hosted:true,authenticated:true,hash:'#register',regionStorage:sharedStorage,apiOverrides:{saveEntity:async(kind,payload,id,options)=>{requests.push({tab:'first',receipt:options.creationRequestId});return await new Promise(resolve=>{releaseFirst=()=>resolve({id:'shared-receipt-search',...payload});});}}});
  await settle();assert.equal(typeof releaseFirst,'function');assert.deepEqual(requests.map(request=>request.receipt),[draft.creationRequestId,draft.creationRequestId]);
  releaseFirst();const first=await firstPending;await settle();assert.equal(first.ctx.location.hash,'#searches');assert.equal(sharedStorage.has(onboardingHelpers.DRAFT_STORAGE_KEY),false,'The first successful tab clears the shared completed draft');
  if(deliverStorageEvent){await secondWindowEvents.storage({type:'storage',key:onboardingHelpers.DRAFT_STORAGE_KEY,newValue:null});await settle();}
  assert.equal(secondDocument.getElementById('entity-form'),null,'A cleared in-flight draft must never be recreated as a fresh editor');
  releaseSecond();const second=await secondPending;await settle();
  assert.equal(second.ctx.location.hash,'#searches',`${deliverStorageEvent?'Delivered':'Undelivered'} storage event: a valid late receipt returns to the owned workspace`);
  assert.match(second.document.getElementById('app').innerHTML,/class="sidebar"/);assert.doesNotMatch(second.document.getElementById('app').innerHTML,/onboarding-save-panel|id="entity-form"|id="hosted-auth-form"/);
  assert.equal(sharedStorage.has(onboardingHelpers.DRAFT_STORAGE_KEY),false);assert.equal(sharedStorage.get('otthonra.api'),'same-auth-session');assert.ok(second.getSelectedModel());
  assert.deepEqual(requests.map(request=>request.receipt),[draft.creationRequestId,draft.creationRequestId],'Each tab uses its original idempotency receipt and completion triggers no extra POST');
 }
});


test('a same-session account lookup completing after another tab saved the draft opens the workspace without a new POST',async()=>{
 for(const deliverStorageEvent of [false,true]){
  const data={title:'Másik fülön már elmentett keresés',type:'Lakás',locationIds:['city:Debrecen'],maxPrice:90,minArea:40,minRooms:null};
  const baseline=createModel({getItem:()=>null,setItem:()=>{}}).getState(),draft=onboardingHelpers.prepareDraftSave(onboardingHelpers.prepareDraftForAuth(onboardingHelpers.createDraft('search',data),baseline.user.email),baseline.user);
  const sharedStorage=new Map([[onboardingHelpers.DRAFT_STORAGE_KEY,JSON.stringify(draft)],['otthonra.api','same-auth-session']]),requests=[];
  let releaseLookup,reads=0,secondDocument,secondWindowEvents;
  const secondPending=setup({hosted:true,authenticated:true,hash:'#register',regionStorage:sharedStorage,onDocument:(document,events)=>{secondDocument=document;secondWindowEvents=events;},apiOverrides:{getState:async()=>++reads===1?await new Promise(resolve=>{releaseLookup=()=>resolve(baseline);}):baseline,saveEntity:async()=>{requests.push('unexpected-second-post');throw new Error('The cleared draft must never be posted again');}}});
  await settle();assert.equal(typeof releaseLookup,'function');
  const first=await setup({hosted:true,authenticated:true,hash:'#register',regionStorage:sharedStorage,apiOverrides:{saveEntity:async(kind,payload,id,options)=>{requests.push(options.creationRequestId);return{id:'already-saved-in-first-tab',...payload};}}});
  assert.equal(first.ctx.location.hash,'#searches');assert.equal(sharedStorage.has(onboardingHelpers.DRAFT_STORAGE_KEY),false);
  if(deliverStorageEvent){await secondWindowEvents.storage({type:'storage',key:onboardingHelpers.DRAFT_STORAGE_KEY,newValue:null});await settle();}
  assert.equal(secondDocument.getElementById('entity-form'),null);
  releaseLookup();const second=await secondPending;await settle();
  assert.equal(second.ctx.location.hash,'#searches');assert.match(second.document.getElementById('app').innerHTML,/class="sidebar"/);assert.doesNotMatch(second.document.getElementById('app').innerHTML,/onboarding-save-panel|id="entity-form"|id="hosted-auth-form"/);
  assert.equal(sharedStorage.has(onboardingHelpers.DRAFT_STORAGE_KEY),false);assert.equal(sharedStorage.get('otthonra.api'),'same-auth-session');assert.deepEqual(requests,[draft.creationRequestId],'Only the first tab posts; the late read cannot resurrect a cleared request');
 }
});


test('top and bottom wizard actions share validation, preserve manual type choice and submit only once',async()=>{
 for(const kind of ['search','property'])for(const guest of [false,true]){
  const draft=onboardingHelpers.createDraft(kind,{locationId:'city:Debrecen',locationIds:['city:Debrecen'],street:'Teszt utca',houseNumber:'12'},{editor:{locations:[getLocation('city:Debrecen')],titleGenerated:true}});
  const t=await setup(guest?{hosted:true,hash:'#onboarding',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(draft)}}:{});
  if(!guest){t.ui.openEditor(kind);chooseLocation(t,'city:Debrecen');if(kind==='property'){t.document.getElementById('f-street').value='Teszt utca';t.document.getElementById('f-houseNumber').value='12';}}
  const form=t.document.getElementById('entity-form'),html=t.document.html,calls=[],save=t.model.saveEntity;let release;
  t.model.saveEntity=async(...args)=>{calls.push(args);await new Promise(resolve=>{release=resolve;});return save(...args);};
  assert.equal(t.document.getElementById('editor-step-status'),null);assert.doesNotMatch(html,/Később folytatom|\d\. lépés a \d-ból/);
  if(kind==='search')assert.ok(html.includes('Először a feltételeidnek mindenben megfelelő ingatlanokat mutatjuk. Ha ezek elfogynak, az igényeidhez legközelebb állókat nézheted meg.'));
  for(let step=0;step<6;step++){
   assert.equal(editorStep(t),step);assert.equal(t.document.getElementById('entity-form'),form);
   for(const suffix of ['', '-top']){assert.equal(t.document.getElementById('editor-back'+suffix).hidden,step===0);assert.equal(t.document.getElementById('editor-next'+suffix).hidden,step===5);assert.equal(t.document.getElementById('editor-save'+suffix).hidden,step!==5);assert.equal(t.document.getElementById('editor-save'+suffix).type,'submit');}
   if(step===1){selectEditorType(t,'Lakás');assert.equal(editorStep(t),1);}
   if(step===2){const required=t.document.getElementById(kind==='property'?'f-price':'f-maxPrice');required.value='';await editorAction(t,'editor-next-top');assert.equal(editorStep(t),2);assert.equal(t.document.activeElement.id,required.id);setEditorValues(t,kind==='property'?{price:'85',area:'65',wholeRooms:'2',halfRooms:'1'}:{maxPrice:'90',minArea:'40',minRooms:'1.5',maxRooms:''});}
   assert.equal(calls.length,0,'Neither topic navigation nor validation may save the entity');
   if(step<5)await editorAction(t,step%2?'editor-next':'editor-next-top');
  }
  await editorAction(t,'editor-back-top');assert.equal(editorStep(t),4);await editorAction(t,'editor-next');assert.equal(editorStep(t),5);
  submitEditor(t,t.document.getElementById('editor-save-top'));await settle();
  if(guest){assert.equal(t.ctx.location.hash,'#register');assert.equal(storedOnboarding(t).phase,'awaiting-auth');assert.equal(storedOnboarding(t).id,draft.id);assert.equal(calls.length,0,'Guest final navigation prepares authentication without creating an entity');}
  else{assert.equal(calls.length,1);submitEditor(t,t.document.getElementById('editor-save'));await editorAction(t,'editor-back-top');assert.equal(calls.length,1);assert.equal(editorStep(t),5);release();await settle();assert.equal(calls.length,1);const rows=t.model.getState()[kind==='property'?'properties':'searches'];assert.equal(rows.filter(row=>row.id===calls[0][2]||row.title===calls[0][1].title).length,1,'The two submit buttons must share one pending save');}
 }
});

test('retired shared garden never appears in legacy criteria summaries, editor controls or candidate comparisons',async()=>{
 for(const kind of ['property','search']){
  const raw=configuredCriteriaRaw(kind),row=raw[kind==='property'?'properties':'searches'].find(item=>item.id===(kind==='property'?'own-p1':'own-s1'));row.sharedGarden=true;row.privateGarden=true;
  const t=await setup({initialRaw:raw});await t.click({action:'edit-active'});
  let html=t.document.getElementById('modal-root').innerHTML;assert.doesNotMatch(html,/data-summary-field="sharedGarden"|Közös használatú kert/);assert.match(html,/saját kert/i);
  await t.click({action:'edit-criteria',kind,id:row.id});html=t.document.getElementById('modal-root').innerHTML;assert.equal(t.document.getElementById('f-sharedGarden'),null);assert.ok(t.document.getElementById('f-privateGarden'));assert.doesNotMatch(html,/name="sharedGarden"|Közös használatú kert/);
  const details=[{key:'sharedGarden',label:'RETIRED-GARDEN-ONLY',expected:'Régi kötelező kert',actual:'Ismeretlen',matches:false},{key:'airConditioning',label:'Légkondi',expected:'Szükséges',actual:'Van',matches:true}];
  const comparison=t.ui.matchingTags({kind,matchDetails:details});assert.doesNotMatch(comparison,/RETIRED-GARDEN-ONLY|Régi kötelező kert|data-criterion="sharedGarden"/);assert.match(comparison,/Légkondi|légkondi/);
 }
});

test('readonly search room counters cycle through unbounded and half-room values and preserve drafts and owner saves',async()=>{
 for(const guest of [false,true]){
  const draft=onboardingHelpers.updateDraft(onboardingHelpers.createDraft('search',{type:'Lakás',locationIds:['city:Debrecen'],maxPrice:90,minArea:40,minRooms:null,maxRooms:null},{editor:{locations:[getLocation('city:Debrecen')],titleGenerated:true,completedSteps:[0,1]}}),{step:2});
  const raw=configuredCriteriaRaw('search');Object.assign(raw.searches.find(item=>item.id==='own-s1'),{minRooms:null,maxRooms:null});
  const t=await setup(guest?{hosted:true,hash:'#onboarding',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(draft)}}:{initialRaw:raw});
  if(!guest){t.ui.openEditor('search','own-s1');await advanceEditor(t,2);}
  const pressRoom=async(name,direction)=>{const button=t.document.getElementById(`f-${name}-${direction}`);assert.ok(button);if(!button.disabled)await editorAction(t,button.id);};
  for(const name of ['minRooms','maxRooms']){
   const input=t.document.getElementById('f-'+name),readout=t.document.getElementById('f-'+name+'-value'),up=t.document.getElementById('f-'+name+'-up'),down=t.document.getElementById('f-'+name+'-down');
   assert.equal(input.type,'hidden','A room limit is never an editable text/number input');assert.equal(input.name,name);assert.equal(readout.tagName,'OUTPUT');assert.match(readout.textContent,new RegExp(name==='minRooms'?'Nincs minimum':'Nincs maximum'));assert.equal(up.type,'button');assert.equal(down.type,'button');
   const positions=[down.id,readout.id,up.id].map(id=>t.document.html.indexOf(`id="${id}"`));assert.deepEqual(positions,[...positions].sort((a,b)=>a-b),'The minus, value and plus controls follow the expected reading order');
   await pressRoom(name,'down');assert.equal(input.value,'','A downward action preserves an unbounded limit');
   await pressRoom(name,'up');assert.equal(Number(input.value),1,'The first explicitly selected room count is one');
   await pressRoom(name,'up');assert.equal(Number(input.value),1.5);assert.match(readout.textContent,/1[,\.]5/);
   await pressRoom(name,'down');assert.equal(Number(input.value),1);await pressRoom(name,'down');assert.equal(input.value,'','Decreasing below one restores an unbounded limit');assert.match(readout.textContent,new RegExp(name==='minRooms'?'Nincs minimum':'Nincs maximum'));assert.equal(editorStep(t),2,'Room controls never submit or navigate');
  }
  for(let count=0;count<5;count++)await pressRoom('minRooms','up');
  for(let count=0;count<4;count++)await pressRoom('maxRooms','up');
  assert.equal(Number(t.document.getElementById('f-minRooms').value),3);assert.equal(Number(t.document.getElementById('f-maxRooms').value),2.5);
  await editorAction(t,'editor-next-top');assert.equal(editorStep(t),2,'The independently adjustable room limits must still form a valid range');assert.ok(t.document.getElementById('room-bounds-error').textContent);assert.match(t.document.activeElement.id,/^f-(?:min|max)Rooms-(?:up|down)$/,'Invalid hidden values focus a visible room action');
  for(let count=0;count<3;count++)await pressRoom('maxRooms','up');await pressRoom('minRooms','down');
  const min=t.document.getElementById('f-minRooms'),max=t.document.getElementById('f-maxRooms');assert.equal(Number(min.value),2.5);assert.equal(Number(max.value),4);
  if(guest){assert.equal(Number(storedOnboarding(t).data.minRooms),2.5);assert.equal(Number(storedOnboarding(t).data.maxRooms),4);}
  await advanceEditor(t,5);submitEditor(t,t.document.getElementById('editor-save-top'));await settle();
  let saved=guest?storedOnboarding(t).data:t.model.getState().searches.find(row=>row.id==='own-s1');assert.equal(Number(saved.minRooms),2.5);assert.equal(Number(saved.maxRooms),4);
  if(guest){await t.click({action:'onboarding-edit'});await editorAction(t,'editor-step-button-2');}else{t.ui.openEditor('search','own-s1');await advanceEditor(t,2);}
  for(const name of ['minRooms','maxRooms']){const input=t.document.getElementById('f-'+name);for(let count=0;input.value!==''&&count<20;count++)await pressRoom(name,'down');assert.equal(input.value,'');}
  await advanceEditor(t,5);submitEditor(t);await settle();saved=guest?storedOnboarding(t).data:t.model.getState().searches.find(row=>row.id==='own-s1');assert.equal(saved.minRooms,null);assert.equal(saved.maxRooms,null,'Returning either counter to its unbounded state persists a null limit');
 }
});

test('move-in illustrations are optional single choices whose explicit clearing survives guest and owner saves',async()=>{
 for(const guest of [false,true]){
  const data={title:'Költözési elképzelés',type:'Lakás',locationIds:['city:Debrecen'],maxPrice:90,minArea:40,minRooms:null,maxRooms:null,moveIn:''};
  const draft=onboardingHelpers.updateDraft(onboardingHelpers.createDraft('search',data,{editor:{locations:[getLocation('city:Debrecen')],completedSteps:[0,1,2,3,4]}}),{step:5});
  const raw=configuredCriteriaRaw('search');Object.assign(raw.searches.find(item=>item.id==='own-s1'),{moveIn:''});
  const t=await setup(guest?{hosted:true,hash:'#onboarding',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(draft)}}:{initialRaw:raw});
  if(!guest){t.ui.openEditor('search','own-s1');await advanceEditor(t,5);}
  const input=t.document.getElementById('f-moveIn');assert.equal(input.type,'hidden');assert.equal(input.value,'','An optional move-in value is not silently filled with a default');
  assert.equal(t.document.querySelector('#f-moveIn').tagName,'INPUT');
  const options=Array.from({length:4},(_value,index)=>illustratedAttribute(t,'moveIn',index));assert.equal(new Set(options.map(option=>option.getAttribute('data-attribute-value'))).size,4);
  for(const option of options)assert.equal(option.getAttribute('aria-pressed'),'false');
  clickIllustrated(t,'moveIn',0);assert.equal(input.value,options[0].getAttribute('data-attribute-value'));assert.equal(options[0].getAttribute('aria-pressed'),'true');
  clickIllustrated(t,'moveIn',1);assert.equal(input.value,options[1].getAttribute('data-attribute-value'));assert.equal(options[0].getAttribute('aria-pressed'),'false');assert.equal(options[1].getAttribute('aria-pressed'),'true');
  clickIllustrated(t,'moveIn',1);assert.equal(input.value,'');assert.equal(options[1].getAttribute('aria-pressed'),'false');assert.equal(editorStep(t),5,'Choosing or clearing a move-in preference does not submit');
  if(guest)assert.equal(storedOnboarding(t).data.moveIn,'');
  submitEditor(t);await settle();const saved=guest?storedOnboarding(t).data:t.model.getState().searches.find(row=>row.id==='own-s1');assert.ok(saved.moveIn==null||saved.moveIn==='','A deselected preference remains unbounded after saving');
  if(guest){await t.click({action:'onboarding-edit'});await advanceEditor(t,5);}else{t.ui.openEditor('search','own-s1');await advanceEditor(t,5);}
  assert.equal(t.document.getElementById('f-moveIn').value,'');
 }
});

test('description contacts warn and block both wizard paths until corrected without changing private profile contacts',async()=>{
 for(const kind of ['property','search'])for(const guest of [false,true]){
  const data={title:'Leírás ellenőrzése',type:'Lakás',locationId:'city:Debrecen',locationIds:['city:Debrecen'],street:'Teszt utca',houseNumber:'12',price:85,area:65,wholeRooms:2,halfRooms:1,rooms:2.5,maxPrice:90,minArea:40,minRooms:null,maxRooms:null,description:'Világos, csendes otthon.'};
  const draft=onboardingHelpers.updateDraft(onboardingHelpers.createDraft(kind,data,{editor:{locations:[getLocation('city:Debrecen')],completedSteps:[0,1,2,3,4]}}),{step:5});
  const t=await setup(guest?{hosted:true,hash:'#onboarding',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(draft)}}:{});
  if(!guest){t.ui.openEditor(kind,kind==='property'?'own-p1':'own-s1');await advanceEditor(t,5);}
  const description=t.document.getElementById('f-description'),warning=t.document.getElementById('description-contact-warning');assert.ok(warning);assert.equal(warning.getAttribute('role'),'alert');assert.match(description.getAttribute('aria-describedby'),/description-contact-warning/);
  const requests=[],save=t.model.saveEntity;t.model.saveEntity=async(...args)=>{requests.push(args);return save(...args);};
  const inputText=value=>{description.value=value;description.handlers.input?.({target:description,currentTarget:description,inputType:'insertText'});t.document.getElementById('entity-form').handlers.input?.({target:description,currentTarget:t.document.getElementById('entity-form'),inputType:'insertText'});};
  for(const bad of ['Hívj a +36 30 123 4567 számon.','Hívj: nulla hat harminc egy kettő három négy öt hat hét.','Írj ide: peter kukac pelda pont hu.']){
   inputText(bad);assert.equal(warning.hidden,false);assert.match(warning.textContent,/Elérhetőséget nem adhatsz meg a leírásban/);assert.equal(description.checkValidity(),false);
   submitEditor(t,t.document.getElementById('editor-save-top'));await settle();assert.equal(editorStep(t),5);assert.ok(t.document.getElementById('entity-form'));assert.equal(requests.length,0,'A contact-bearing description must never reach an entity write');if(guest)assert.equal(storedOnboarding(t).phase,'editing');
  }
  const corrected='Világos, csendes otthont keresünk, 65 négyzetméterrel és két szobával.';inputText(corrected);assert.equal(warning.hidden,true);assert.equal(description.validationMessage,'');assert.equal(description.checkValidity(),true);
  submitEditor(t);await settle();
  if(guest){assert.equal(storedOnboarding(t).phase,'awaiting-auth');assert.equal(storedOnboarding(t).data.description,corrected);assert.equal(requests.length,0);}else{assert.equal(requests.length,1);assert.equal(t.model.getState()[kind==='property'?'properties':'searches'].find(row=>row.id===(kind==='property'?'own-p1':'own-s1')).description,corrected);}
 }
});

test('mandatory form fields have stars while optional labels and dynamic house fields remain accurate',async()=>{
 for(const kind of ['property','search'])for(const guest of [false,true]){
  const draft=onboardingHelpers.createDraft(kind,{type:'Lakás',locationId:'city:Debrecen',locationIds:['city:Debrecen'],street:'Teszt utca',houseNumber:'12',maxPrice:90,minArea:40},{editor:{locations:[getLocation('city:Debrecen')],titleGenerated:true}});
  const t=await setup(guest?{hosted:true,hash:'#onboarding',regionStorage:{[onboardingHelpers.DRAFT_STORAGE_KEY]:JSON.stringify(draft)}}:{});
  if(!guest)t.ui.openEditor(kind,kind==='property'?'own-p1':'own-s1');
  const form=t.document.getElementById('entity-form');
  for(const id of ['location-input','f-type',...(kind==='property'?['f-street','f-houseNumber','f-price','f-area','f-wholeRooms']:['f-maxPrice','f-minArea'])]){
   const marker=t.document.getElementById('required-'+id);assert.ok(marker,`Required ${id} needs a visible marker`);assert.equal(marker.hidden,false,id);assert.equal(marker.getAttribute('aria-hidden'),'true');assert.equal(form.contains(marker),true);
  }
  for(const id of ['f-title','f-description',...(kind==='property'?['f-postalCode','f-halfRooms','f-buildingFloors']:['f-minPrice','f-maxArea','f-minRooms','f-maxRooms'])]){const marker=t.document.getElementById('required-'+id);assert.ok(!marker||marker.hidden,`Optional ${id} must not show a required star`);}
  assert.doesNotMatch(t.document.html,/\(opcionális\)/i,'Optional fields need no repetitive optional suffix');
  if(kind==='property'){
   const lot=t.document.getElementById('f-lotArea'),marker=t.document.getElementById('required-f-lotArea');assert.ok(marker);assert.equal(lot.required,false);assert.equal(marker.hidden,true);
   chooseEditorType(t,'Ház');assert.equal(lot.required,true);assert.equal(lot.disabled,false);assert.equal(marker.hidden,false,'Choosing a house shows the mandatory plot marker');
   chooseEditorType(t,'Lakás');assert.equal(lot.required,false);assert.equal(lot.disabled,true);assert.equal(marker.hidden,true,'Leaving house type removes the obsolete mandatory marker');
  }else{
   assert.ok(t.document.html.includes('Keresés neve (ez fog megjelenni az ingatlan-tulajdonosoknak)'));
   const comfort=t.document.getElementById('editor-step-4');assert.ok(comfort);for(const caption of ['Legyen erkély','Legyen légkondi','Legyen saját kert'])assert.ok(t.document.html.includes(caption),caption);
   assert.match(t.document.html,/<h3\b[^>]*>Kényelem<\/h3>/);
  }
 }
});

test('legacy room limits below one remain unchanged until a counter action chooses a new supported value',async()=>{
 const raw=configuredCriteriaRaw('search');Object.assign(raw.searches.find(row=>row.id==='own-s1'),{minRooms:.5,maxRooms:.5});
 const t=await setup({initialRaw:raw});t.ui.openEditor('search','own-s1');await advanceEditor(t,2);
 for(const name of ['minRooms','maxRooms'])assert.equal(Number(t.document.getElementById('f-'+name).value),.5,'Opening a stored request is not an implicit edit');
 await advanceEditor(t,5);submitEditor(t);await settle();let saved=t.model.getState().searches.find(row=>row.id==='own-s1');assert.equal(saved.minRooms,.5);assert.equal(saved.maxRooms,.5);
 t.ui.openEditor('search','own-s1');await advanceEditor(t,2);
 for(const name of ['minRooms','maxRooms']){await editorAction(t,`f-${name}-up`);assert.equal(Number(t.document.getElementById('f-'+name).value),1);await editorAction(t,`f-${name}-down`);assert.equal(t.document.getElementById('f-'+name).value,'');}
 await advanceEditor(t,5);submitEditor(t);await settle();saved=t.model.getState().searches.find(row=>row.id==='own-s1');assert.equal(saved.minRooms,null);assert.equal(saved.maxRooms,null);
});


test('seller location collapses to an editable city name and nested address privacy never exposes a hidden house number',async()=>{
 const raw=configuredCriteriaRaw('property'),original=raw.properties.find(item=>item.id==='own-p1');original.hideStreet=true;original.hideHouseNumber=true;
 const t=await setup({initialRaw:raw});t.ui.openEditor('property','own-p1');
 const form=t.document.getElementById('entity-form'),query=t.document.getElementById('property-location-query'),chips=t.document.getElementById('location-chips'),edit=t.document.getElementById('property-location-edit');
 assert.equal(query.hidden,true);assert.ok(edit);assert.match(edit.getAttribute('aria-label'),/Budapest V.*szerkesztése/);assert.equal(t.document.getElementById('f-postalCode').type,'hidden');assert.doesNotMatch(t.document.html,/<label[^>]*for="f-postalCode"/);
 const streetBefore=t.document.getElementById('f-street').value;chips.handlers.click({target:{closest:selector=>selector==='#property-location-edit'?edit:null}});assert.equal(query.hidden,false);assert.equal(t.document.activeElement.id,'location-input');assert.equal(t.document.getElementById('f-street').value,streetBefore,'Entering location editing does not erase the verified street');
 t.document.handlers.pointerdown({target:t.document.getElementById('toast')});assert.equal(query.hidden,true,'Leaving an empty location editor restores the selected city');
 const hideStreet=t.document.getElementById('f-hideStreet'),hideHouse=t.document.getElementById('f-hideHouseNumber');assert.equal(hideStreet.checked,true);assert.equal(hideHouse.checked,true);assert.equal(hideHouse.disabled,true);
 changeChoice(t,hideStreet,false);assert.equal(hideHouse.disabled,false);assert.equal(hideHouse.checked,true,'Showing a street does not silently expose its house number');changeChoice(t,hideHouse,false);assert.equal(hideHouse.checked,false);
 changeChoice(t,hideStreet,true);assert.equal(hideHouse.checked,true);assert.equal(hideHouse.disabled,true);await advanceEditor(t,5);submitEditor(t);await settle();
 const saved=t.model.getState().properties.find(item=>item.id==='own-p1');assert.equal(saved.hideStreet,true);assert.equal(saved.hideHouseNumber,true);assert.equal(saved.addressDetails?.postalCode??saved.postalCode,'1051','Removing the visible postcode field preserves an unchanged existing value');
 assert.notEqual(t.document.getElementById('entity-form'),form);
});

test('seller nullable amenity cards cycle yes, no and unspecified without coercion on actual saves',async()=>{
 const t=await setup({initialRaw:configuredCriteriaRaw('property')});t.ui.openEditor('property','own-p1');await advanceEditor(t,4);
 const names=['balcony','airConditioning','privateGarden','insulated','solarPanels'];
 for(const name of names){const input=t.document.getElementById('f-'+name);assert.equal(input.type,'hidden');chooseOptionalCard(t,name,true);assert.equal(input.value,'true');chooseOptionalCard(t,name,false);assert.equal(input.value,'false');const chosen=t.document.getElementById('entity-form').querySelectorAll('button').find(button=>button.dataset.attributeName===name&&button.dataset.attributeValue==='false');chosen.handlers.click({target:chosen,currentTarget:chosen,preventDefault(){}});assert.equal(input.value,'');assert.equal(chosen.getAttribute('aria-pressed'),'false');}
 await advanceEditor(t,5);submitEditor(t);await settle();const property=t.model.getState().properties.find(item=>item.id==='own-p1');for(const name of names)assert.equal(property[name],null,`${name} remains unspecified after clearing its pair`);
});

test('energy sliders preserve legacy certificate text until changed and search minimum follows the official twelve grades',async()=>{
 const t=await setup({initialRaw:configuredCriteriaRaw('property')});t.ui.openEditor('property','own-p1');await advanceEditor(t,4);
 const input=t.document.getElementById('f-energyRating'),slider=t.document.getElementById('f-energyRating-slider'),scheme=t.document.getElementById('f-energyRatingScheme');assert.equal(input.value,'BB');assert.equal(slider.value,'0');assert.equal(scheme.value,'');assert.equal(slider.type,'range');assert.equal(slider.getAttribute('max'),'12');assert.match(t.document.html,/id="energyRating-legacy"[^>]*>Korábban megadott érték/);
 assert.deepEqual(energyRatingHelpers.ENERGY_SLIDER_OPTIONS.map(entry=>entry.value),['','I','H','G','F','E','D','C','B','A','A+','A++','A+++']);chooseEnergy(t,'energyRating','A++');assert.equal(input.value,'A++');assert.equal(scheme.value,'2023');assert.equal(slider.getAttribute('aria-valuetext'),'A++');assert.equal(t.document.getElementById('energyRating-legacy').hidden,true);
 await advanceEditor(t,5);submitEditor(t);await settle();let property=t.model.getState().properties.find(item=>item.id==='own-p1');assert.equal(property.energyRating,'A++');assert.equal(property.energyRatingScheme,'2023');
 t.ui.openEditor('property','own-p1');await advanceEditor(t,4);chooseEnergy(t,'energyRating','');await advanceEditor(t,5);submitEditor(t);await settle();property=t.model.getState().properties.find(item=>item.id==='own-p1');assert.equal(property.energyRating,'');assert.equal(property.energyRatingScheme,'');
 t.ui.openEditor('search','own-s1');await advanceEditor(t,4);assert.ok(t.document.html.indexOf('id="heatingTypes-group"')<t.document.html.indexOf('id="minEnergyRating-group"'));chooseEnergy(t,'minEnergyRating','C');await advanceEditor(t,5);submitEditor(t);await settle();assert.equal(t.model.getState().searches.find(item=>item.id==='own-s1').minEnergyRating,'C');
});

test('attic requirements and construction-age radio values survive backtracking while a legacy unknown upper floor stays imprecise',async()=>{
 const raw=configuredCriteriaRaw('property');Object.assign(raw.properties.find(item=>item.id==='own-p1'),{floor:9,buildingFloors:12,floorIsUpperRange:true,isAttic:null});
 const t=await setup({initialRaw:raw});t.ui.openEditor('property','own-p1');await advanceEditor(t,3);
 const cards=t.document.getElementById('entity-form').querySelectorAll('button');assert.equal(cards.find(button=>button.dataset.buildingNumberValue==='legacy-upper').getAttribute('aria-pressed'),'true');
 changeChoice(t,t.document.getElementById('f-isAttic'),true);chooseRadio(t,'constructionAge','10 évnél fiatalabb');await editorAction(t,'editor-back');await advanceEditor(t,3);assert.equal(t.document.getElementById('f-isAttic').checked,true);assert.equal(t.document.getElementById('f-constructionAge').value,'10 évnél fiatalabb');await advanceEditor(t,5);submitEditor(t);await settle();
 const property=t.model.getState().properties.find(item=>item.id==='own-p1');assert.equal(property.floor,9);assert.equal(property.floorIsUpperRange,true);assert.equal(property.isAttic,true);assert.equal(property.constructionAge,'10 évnél fiatalabb');
 t.ui.openEditor('search','own-s1');await advanceEditor(t,3);chooseRadio(t,'atticPreference','only');await advanceEditor(t,5);submitEditor(t);await settle();assert.equal(t.model.getState().searches.find(item=>item.id==='own-s1').atticPreference,'only');
 t.ui.openEditor('search','own-s1');await advanceEditor(t,3);chooseRadio(t,'atticPreference','exclude');await advanceEditor(t,5);submitEditor(t);await settle();assert.equal(t.model.getState().searches.find(item=>item.id==='own-s1').atticPreference,'exclude');
});

test('anonymous full listing routes show public facts and images without leaking hidden address or private contact metadata',async()=>{
 const key=publicSourceKey('property','c'),calls=[],detail={kind:'property',sourceKey:key,title:'Fényes kertkapcsolatos lakás',ownerFirstName:'Réka',ownerAccountType:'private',listing:{title:'Fényes kertkapcsolatos lakás',type:'Lakás',city:'Debrecen',price:85,area:63,rooms:2.5,wholeRooms:2,halfRooms:1,floor:.5,buildingFloors:2,isAttic:false,energyRating:'B',energyRatingScheme:'2023',airConditioning:true,balcony:null,privateGarden:true,hideStreet:true,hideHouseNumber:true,street:'PRIVATE-STREET',houseNumber:'PRIVATE-HOUSE',latitude:47.000123,longitude:21.000123,ownerEmail:'PRIVATE-CONTACT@example.test',description:'Világos <kert> & tágas szobák.',images:['https://example.test/otthon-1.jpg','https://example.test/otthon-2.jpg']}};
 const t=await setup({hosted:true,hash:'#listing/property/'+key,fetchPublicListing:async(...args)=>{calls.push(args);return detail;}}),html=t.document.getElementById('app').innerHTML;
 assert.deepEqual(calls.map(([kind,source])=>[kind,source]),[['property',key]]);assert.equal(t.getSelectedModel(),null);assert.match(html,/Fényes kertkapcsolatos lakás/);assert.match(html,/Réka/);assert.match(html,/example.test\/otthon-1.jpg/);assert.match(html,/example.test\/otthon-2.jpg/);assert.match(html,/Magasföldszint|Energetikai tanúsítvány/);assert.match(html,/Világos &lt;kert&gt; &amp; tágas szobák/);assert.match(html,/Ilyen otthont keresek/);assert.doesNotMatch(html,/PRIVATE-|47\.000123|21\.000123|<kert>|sidebar|hosted-auth-form/);
 const missing=await setup({hosted:true,hash:'#listing/property/'+key});assert.match(missing.document.getElementById('app').innerHTML,/Ez a hirdetés már nem elérhető/);assert.equal(missing.document.getElementById('hosted-auth-form'),null);
});

test('a late public listing read cannot replace registration after navigation',async()=>{
 const key=publicSourceKey('property','d');let resolveRead;const pending=new Promise(resolve=>{resolveRead=resolve;}),t=await setup({hosted:true,hash:'#landing',fetchPublicListing:()=>pending});
 t.ctx.location.hash='#listing/property/'+key;const read=t.ui.render();await settle();assert.match(t.document.getElementById('app').innerHTML,/Betöltjük a hirdetést/);
 await t.click({action:'auth-mode',mode:'register'});assert.ok(t.document.getElementById('hosted-auth-form'));const identity=t.document.getElementById('f-name');identity.value='Megőrzött név';
 resolveRead({kind:'property',sourceKey:key,title:'LATE-PUBLIC-CARD',listing:{type:'Lakás',price:10,area:20,description:'Kései nyilvános válasz'}});await read;await settle();assert.equal(t.ctx.location.hash,'#register');assert.equal(t.document.getElementById('f-name'),identity);assert.equal(identity.value,'Megőrzött név');assert.doesNotMatch(t.document.getElementById('app').innerHTML,/LATE-PUBLIC-CARD|Kései nyilvános/);
});

test('a public search can seed either a full matching search draft or a distinct property draft without replacing a same-source edit',async()=>{
 const key=publicSourceKey('search','e'),detail={kind:'search',sourceKey:key,title:'Csendes házat keresek',ownerFirstName:'Péter',ownerAccountType:'private',listing:{type:'Ház',city:'Debrecen',maxPrice:120,minArea:80,minRooms:3,minEnergyRating:'C'},clonePrefill:{locations:[getLocation('city:Debrecen')],type:'Ház',minPrice:null,maxPrice:120,minArea:80,maxArea:null,minRooms:3,maxRooms:null,conditions:['Jó'],heatingTypes:['Hőszivattyú'],minEnergyRating:'C',description:'Csendes kertet és világos szobákat szeretnék.',moveIn:'Azonnal'},prefill:{locations:[getLocation('city:Debrecen')],type:'Ház',maxPrice:120,minArea:80,minRooms:3,conditions:['Jó']}};
 const t=await setup({hosted:true,hash:'#listing/search/'+key,fetchPublicListing:async()=>detail});let html=t.document.getElementById('app').innerHTML;assert.match(html,/Ilyen ingatlanom van/);assert.match(html,/Én is ilyet keresek/);
 await t.click({action:'onboarding-copy-search',source:key});let draft=storedOnboarding(t);assert.equal(draft.kind,'search');assert.equal(Number(draft.data.maxPrice),120);assert.equal(Number(draft.data.minArea),80);assert.equal(Number(draft.data.minRooms),3);assert.equal(draft.data.minEnergyRating,'C');assert.deepEqual([...draft.data.heatingTypes],['Hőszivattyú']);assert.equal(draft.data.description,detail.clonePrefill.description);assert.deepEqual(draft.origin,onboardingHelpers.originFromSearchCopy(key));
 const identity=draft.id;t.document.getElementById('f-maxPrice').value='135';formInputEvent(t,t.document.getElementById('f-maxPrice'),'input');assert.equal(storedOnboarding(t).data.maxPrice,'135');
 t.ctx.location.hash='#listing/search/'+key;await t.ui.render();await t.click({action:'onboarding-copy-search',source:key});draft=storedOnboarding(t);assert.equal(draft.id,identity);assert.equal(draft.data.maxPrice,'135');
 t.ctx.location.hash='#listing/search/'+key;await t.ui.render();await t.click({action:'onboarding-start',kind:'property',source:key});draft=storedOnboarding(t);assert.equal(draft.kind,'property');assert.notEqual(draft.id,identity);assert.equal(draft.data.type,'Ház');assert.ok(draft.data.price==null||draft.data.price==='','A ranged search cannot invent an exact seller price');assert.deepEqual(draft.origin,onboardingHelpers.originFromListing('search',key));
});
